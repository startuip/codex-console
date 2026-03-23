import asyncio
from contextlib import contextmanager
from pathlib import Path

import src.core.cpa_auto_refill as cpa_auto_refill
import src.web.routes.registration as registration_routes
import src.web.routes.upload.cpa_services as cpa_services_routes
from src.database.models import Base, CpaAutoRefillRun, CpaService, RegistrationTask
from src.database.session import DatabaseSessionManager


def _build_temp_manager(db_name: str) -> DatabaseSessionManager:
    runtime_dir = Path("tests_runtime")
    runtime_dir.mkdir(exist_ok=True)
    db_path = runtime_dir / db_name
    if db_path.exists():
        db_path.unlink()

    manager = DatabaseSessionManager(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=manager.engine)
    return manager


def test_run_once_deletes_401_accounts_and_records_history(monkeypatch):
    manager = _build_temp_manager("cpa_auto_refill_run_once.db")

    with manager.session_scope() as session:
        session.add(
            CpaService(
                name="主 CPA",
                api_url="https://cpa.example.com",
                api_token="token-123",
                enabled=True,
                priority=0,
            )
        )

    @contextmanager
    def fake_get_db():
        session = manager.SessionLocal()
        try:
            yield session
        finally:
            session.close()

    deleted_names = []

    monkeypatch.setattr(cpa_auto_refill, "get_db", fake_get_db)
    monkeypatch.setattr(
        cpa_auto_refill,
        "list_cpa_auth_files",
        lambda api_url, api_token: (
            True,
            [
                {"name": "alive.json", "status": "ok"},
                {"name": "dead.json", "status_message": "401 Invalid"},
            ],
            "获取成功",
        ),
    )
    monkeypatch.setattr(
        cpa_auto_refill,
        "delete_cpa_auth_file",
        lambda name, api_url, api_token: (deleted_names.append(name) or True, "删除成功"),
    )

    async def fake_launch(self, count, cpa_service_id):
        return count, ["batch-1"], "tempmail"

    monkeypatch.setattr(cpa_auto_refill.CPAAutoRefillScheduler, "launch_replenishment_batches", fake_launch)

    scheduler = cpa_auto_refill.CPAAutoRefillScheduler(scan_interval_seconds=1)
    results = asyncio.run(scheduler.run_once())

    assert deleted_names == ["dead.json"]
    assert len(results) == 1
    assert results[0].status == "scheduled"
    assert results[0].invalid_count == 1
    assert results[0].deleted_count == 1
    assert results[0].refill_requested_count == 1
    assert results[0].batch_ids == ["batch-1"]

    with manager.session_scope() as session:
        runs = session.query(CpaAutoRefillRun).all()
        assert len(runs) == 1
        assert runs[0].service_name == "主 CPA"
        assert runs[0].invalid_count == 1
        assert runs[0].deleted_count == 1
        assert runs[0].refill_requested_count == 1
        assert runs[0].status == "scheduled"
        assert runs[0].details["batch_ids"] == ["batch-1"]


def test_launch_replenishment_batches_splits_large_counts(monkeypatch):
    manager = _build_temp_manager("cpa_auto_refill_launch_batches.db")

    @contextmanager
    def fake_get_db():
        session = manager.SessionLocal()
        try:
            yield session
        finally:
            session.close()

    calls = []

    async def fake_run_batch_registration(
        batch_id,
        task_uuids,
        email_service_type,
        proxy,
        email_service_config,
        email_service_id,
        interval_min,
        interval_max,
        concurrency,
        mode,
        auto_upload_cpa,
        cpa_service_ids,
        auto_upload_sub2api,
        sub2api_service_ids,
        auto_upload_tm,
        tm_service_ids,
    ):
        calls.append(
            {
                "batch_id": batch_id,
                "task_count": len(task_uuids),
                "email_service_type": email_service_type,
                "auto_upload_cpa": auto_upload_cpa,
                "cpa_service_ids": cpa_service_ids,
                "mode": mode,
            }
        )

    monkeypatch.setattr(cpa_auto_refill, "get_db", fake_get_db)
    monkeypatch.setattr(registration_routes, "run_batch_registration", fake_run_batch_registration)

    async def main():
        scheduler = cpa_auto_refill.CPAAutoRefillScheduler(scan_interval_seconds=1)
        scheduled_count, batch_ids, email_service_type = await scheduler.launch_replenishment_batches(120, 7)
        await asyncio.sleep(0)
        return scheduled_count, batch_ids, email_service_type

    scheduled_count, batch_ids, email_service_type = asyncio.run(main())

    assert scheduled_count == 120
    assert len(batch_ids) == 2
    assert email_service_type == "tempmail"
    assert [call["task_count"] for call in calls] == [100, 20]
    assert all(call["auto_upload_cpa"] is True for call in calls)
    assert all(call["cpa_service_ids"] == [7] for call in calls)
    assert all(call["mode"] == "pipeline" for call in calls)

    with manager.session_scope() as session:
        assert session.query(RegistrationTask).count() == 120


def test_manual_cpa_auto_refill_route_runs_specific_service(monkeypatch):
    manager = _build_temp_manager("cpa_auto_refill_route.db")

    with manager.session_scope() as session:
        session.add(
            CpaService(
                id=9,
                name="手动 CPA",
                api_url="https://cpa.example.com",
                api_token="token-123",
                enabled=False,
                priority=0,
            )
        )

    @contextmanager
    def fake_get_db():
        session = manager.SessionLocal()
        try:
            yield session
        finally:
            session.close()

    async def fake_run_for_service(service_id, include_disabled=True):
        return [
            cpa_auto_refill.CPAAutoRefillResult(
                service_id=service_id,
                service_name="手动 CPA",
                invalid_files=["dead.json"],
                deleted_files=["dead.json"],
                refill_requested_count=1,
                batch_ids=["batch-manual"],
                refill_email_service_type="tempmail",
                status="scheduled",
                message="扫描到 1 个 401 账号，删除 1 个，已安排补号 1 个",
            )
        ]

    monkeypatch.setattr(cpa_services_routes, "get_db", fake_get_db)
    monkeypatch.setattr(cpa_services_routes.cpa_auto_refill_scheduler, "run_for_service", fake_run_for_service)

    result = asyncio.run(
        cpa_services_routes.run_cpa_auto_refill_now(
            cpa_services_routes.CpaAutoRefillRunRequest(service_id=9)
        )
    )

    assert result["success"] is True
    assert result["count"] == 1
    assert result["results"][0]["service_id"] == 9
    assert result["results"][0]["deleted_count"] == 1
    assert result["results"][0]["refill_requested_count"] == 1
    assert result["results"][0]["details"]["batch_ids"] == ["batch-manual"]
