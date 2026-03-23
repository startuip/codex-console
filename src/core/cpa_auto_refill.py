"""
CPA 失效账号自动补号。
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..database import crud
from ..database.models import CpaAutoRefillRun, EmailService
from ..database.session import get_db
from .upload.cpa_upload import (
    delete_cpa_auth_file,
    filter_unauthorized_cpa_auth_files,
    list_cpa_auth_files,
)

logger = logging.getLogger(__name__)

SCAN_INTERVAL_SECONDS = 30 * 60
REFILL_BATCH_SIZE = 100
PREFERRED_REFILL_EMAIL_SERVICE_TYPES = (
    "duck_mail",
    "moe_mail",
    "temp_mail",
    "freemail",
    "imap_mail",
    "outlook",
)


@dataclass
class CPAScanTarget:
    service_id: int
    service_name: str
    api_url: str
    api_token: str


@dataclass
class CPAAutoRefillResult:
    service_id: int
    service_name: str
    invalid_files: List[str] = field(default_factory=list)
    deleted_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    delete_failures: List[Dict[str, str]] = field(default_factory=list)
    refill_requested_count: int = 0
    batch_ids: List[str] = field(default_factory=list)
    refill_email_service_type: str = ""
    status: str = "noop"
    message: str = ""

    @property
    def invalid_count(self) -> int:
        return len(self.invalid_files)

    @property
    def deleted_count(self) -> int:
        return len(self.deleted_files)

    def to_details(self) -> Dict[str, Any]:
        return {
            "invalid_files": self.invalid_files,
            "deleted_files": self.deleted_files,
            "skipped_files": self.skipped_files,
            "delete_failures": self.delete_failures,
            "batch_ids": self.batch_ids,
            "refill_email_service_type": self.refill_email_service_type,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_id": self.service_id,
            "service_name": self.service_name,
            "invalid_count": self.invalid_count,
            "deleted_count": self.deleted_count,
            "refill_requested_count": self.refill_requested_count,
            "status": self.status,
            "message": self.message,
            "details": self.to_details(),
        }


def _auth_file_name(auth_file: Dict[str, Any]) -> str:
    for key in ("name", "filename", "id"):
        value = str(auth_file.get(key) or "").strip()
        if value:
            return value
    return ""


def _chunk_count(total: int, chunk_size: int = REFILL_BATCH_SIZE) -> List[int]:
    chunks: List[int] = []
    remaining = max(0, total)
    while remaining > 0:
        chunk = min(chunk_size, remaining)
        chunks.append(chunk)
        remaining -= chunk
    return chunks


def _load_enabled_cpa_targets() -> List[CPAScanTarget]:
    with get_db() as db:
        services = crud.get_cpa_services(db, enabled=True)
        return [
            CPAScanTarget(
                service_id=service.id,
                service_name=service.name,
                api_url=service.api_url,
                api_token=service.api_token,
            )
            for service in services
            if service.api_url and service.api_token
        ]


def _load_cpa_target_by_id(service_id: int, include_disabled: bool = False) -> Optional[CPAScanTarget]:
    with get_db() as db:
        service = crud.get_cpa_service_by_id(db, service_id)
        if not service:
            return None
        if not include_disabled and not service.enabled:
            return None
        if not service.api_url or not service.api_token:
            return None

        return CPAScanTarget(
            service_id=service.id,
            service_name=service.name,
            api_url=service.api_url,
            api_token=service.api_token,
        )


def _select_refill_email_service_type() -> str:
    with get_db() as db:
        for service_type in PREFERRED_REFILL_EMAIL_SERVICE_TYPES:
            service = db.query(EmailService).filter(
                EmailService.service_type == service_type,
                EmailService.enabled == True,
            ).order_by(EmailService.priority.asc(), EmailService.id.asc()).first()
            if service:
                return service_type
    return "tempmail"


def _create_batch_registration_records(count: int, proxy: Optional[str] = None) -> Tuple[str, List[str]]:
    batch_id = str(uuid.uuid4())
    task_uuids: List[str] = []

    with get_db() as db:
        for _ in range(count):
            task_uuid = str(uuid.uuid4())
            crud.create_registration_task(db, task_uuid=task_uuid, proxy=proxy)
            task_uuids.append(task_uuid)

    return batch_id, task_uuids


def _scan_and_delete_invalid_accounts(target: CPAScanTarget) -> CPAAutoRefillResult:
    result = CPAAutoRefillResult(
        service_id=target.service_id,
        service_name=target.service_name,
    )

    ok, auth_files, message = list_cpa_auth_files(target.api_url, target.api_token)
    if not ok:
        result.status = "scan_failed"
        result.message = message
        return result

    invalid_auth_files = filter_unauthorized_cpa_auth_files(auth_files)
    result.invalid_files = [_auth_file_name(item) or "<unknown>" for item in invalid_auth_files]

    if not invalid_auth_files:
        result.status = "noop"
        result.message = "未发现 401 失效账号"
        return result

    for auth_file in invalid_auth_files:
        auth_file_name = _auth_file_name(auth_file)
        if not auth_file_name:
            result.skipped_files.append("<unknown>")
            continue

        if bool(auth_file.get("runtime_only")):
            result.skipped_files.append(auth_file_name)
            continue

        deleted, delete_message = delete_cpa_auth_file(
            auth_file_name,
            target.api_url,
            target.api_token,
        )
        if deleted:
            result.deleted_files.append(auth_file_name)
        else:
            result.delete_failures.append({
                "name": auth_file_name,
                "error": delete_message,
            })

    if result.deleted_files:
        result.status = "deleted"
        result.message = f"扫描到 {result.invalid_count} 个 401 账号，成功删除 {result.deleted_count} 个"
    elif result.delete_failures or result.skipped_files:
        result.status = "partial"
        result.message = f"扫描到 {result.invalid_count} 个 401 账号，但未删除成功"
    else:
        result.status = "noop"
        result.message = "扫描完成，没有可删除的 401 账号"

    return result


def _record_auto_refill_result(result: CPAAutoRefillResult) -> None:
    with get_db() as db:
        db_run = CpaAutoRefillRun(
            service_id=result.service_id,
            service_name=result.service_name,
            invalid_count=result.invalid_count,
            deleted_count=result.deleted_count,
            refill_requested_count=result.refill_requested_count,
            status=result.status,
            message=result.message,
            details=result.to_details(),
        )
        db.add(db_run)
        db.commit()


class CPAAutoRefillScheduler:
    def __init__(self, scan_interval_seconds: int = SCAN_INTERVAL_SECONDS):
        self.scan_interval_seconds = scan_interval_seconds
        self._loop_task: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._run_lock: Optional[asyncio.Lock] = None

    async def launch_replenishment_batches(self, count: int, cpa_service_id: int) -> Tuple[int, List[str], str]:
        from ..web.routes.registration import run_batch_registration

        refill_email_service_type = await asyncio.to_thread(_select_refill_email_service_type)
        batch_ids: List[str] = []
        scheduled_count = 0

        for chunk_size in _chunk_count(count):
            batch_id, task_uuids = await asyncio.to_thread(_create_batch_registration_records, chunk_size, None)
            asyncio.create_task(
                run_batch_registration(
                    batch_id,
                    task_uuids,
                    refill_email_service_type,
                    None,
                    None,
                    None,
                    5,
                    30,
                    1,
                    "pipeline",
                    True,
                    [cpa_service_id],
                    False,
                    [],
                    False,
                    [],
                )
            )
            batch_ids.append(batch_id)
            scheduled_count += chunk_size

        return scheduled_count, batch_ids, refill_email_service_type

    async def _run_targets(self, targets: List[CPAScanTarget]) -> List[CPAAutoRefillResult]:
        if self._run_lock is None:
            self._run_lock = asyncio.Lock()

        if self._run_lock.locked():
            logger.warning("CPA 自动补号扫描仍在运行，跳过本轮")
            return []

        async with self._run_lock:
            if not targets:
                logger.debug("未发现可扫描的 CPA 服务，自动补号本轮跳过")
                return []

            results: List[CPAAutoRefillResult] = []
            for target in targets:
                result = await asyncio.to_thread(_scan_and_delete_invalid_accounts, target)

                if result.deleted_count > 0:
                    try:
                        scheduled_count, batch_ids, refill_email_service_type = await self.launch_replenishment_batches(
                            result.deleted_count,
                            target.service_id,
                        )
                        result.refill_requested_count = scheduled_count
                        result.batch_ids = batch_ids
                        result.refill_email_service_type = refill_email_service_type
                        result.status = "scheduled"
                        result.message = (
                            f"扫描到 {result.invalid_count} 个 401 账号，删除 {result.deleted_count} 个，"
                            f"已安排补号 {scheduled_count} 个"
                        )
                    except Exception as e:
                        logger.error("启动 CPA 自动补号批量注册失败(%s): %s", target.service_name, e)
                        result.status = "refill_failed"
                        result.message = (
                            f"删除 {result.deleted_count} 个 401 账号后，补号任务启动失败: {str(e)}"
                        )

                await asyncio.to_thread(_record_auto_refill_result, result)
                logger.info(
                    "[CPA Auto Refill] 服务=%s 状态=%s 401=%s 删除=%s 补号=%s",
                    result.service_name,
                    result.status,
                    result.invalid_count,
                    result.deleted_count,
                    result.refill_requested_count,
                )
                results.append(result)

            return results

    async def run_once(self) -> List[CPAAutoRefillResult]:
        targets = await asyncio.to_thread(_load_enabled_cpa_targets)
        return await self._run_targets(targets)

    async def run_for_service(self, service_id: int, include_disabled: bool = True) -> List[CPAAutoRefillResult]:
        target = await asyncio.to_thread(_load_cpa_target_by_id, service_id, include_disabled)
        if not target:
            return []
        return await self._run_targets([target])

    async def _run_loop(self) -> None:
        await self.run_once()
        while self._stop_event and not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.scan_interval_seconds)
            except asyncio.TimeoutError:
                await self.run_once()

    def start(self) -> None:
        if self._loop_task and not self._loop_task.done():
            return

        self._stop_event = asyncio.Event()
        self._loop_task = asyncio.create_task(self._run_loop())
        logger.info("CPA 自动补号调度器已启动，每 %s 分钟巡检一次", self.scan_interval_seconds // 60)

    async def stop(self) -> None:
        if not self._loop_task:
            return

        if self._stop_event:
            self._stop_event.set()

        await self._loop_task
        self._loop_task = None
        self._stop_event = None


cpa_auto_refill_scheduler = CPAAutoRefillScheduler()
