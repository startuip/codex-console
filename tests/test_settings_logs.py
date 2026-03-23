import asyncio
from types import SimpleNamespace

from src.web.routes import settings as settings_routes


def test_resolve_log_path_prefers_runtime_logs_dir(monkeypatch, tmp_path):
    runtime_logs_dir = tmp_path / "runtime_logs"
    runtime_logs_dir.mkdir()
    runtime_log = runtime_logs_dir / "app.log"
    runtime_log.write_text("hello\n", encoding="utf-8")

    monkeypatch.setenv("APP_LOGS_DIR", str(runtime_logs_dir))

    resolved = settings_routes._resolve_log_path("logs/app.log")

    assert resolved == runtime_log


def test_filter_log_lines_supports_level_and_keyword():
    lines = [
        "2026-03-23 18:04:50,511 [INFO] src.core.cpa_auto_refill: [CPA Auto Refill] 服务=Demo 状态=noop",
        "2026-03-23 18:05:10,001 [ERROR] src.web.routes.registration: 注册失败",
        "2026-03-23 18:05:20,002 [WARNING] src.web.routes.registration: 任务重试中",
    ]

    filtered, level, keyword = settings_routes._filter_log_lines(
        lines,
        level="warning",
        keyword="任务",
    )

    assert level == "WARNING"
    assert keyword == "任务"
    assert filtered == ["2026-03-23 18:05:20,002 [WARNING] src.web.routes.registration: 任务重试中"]


def test_get_recent_logs_supports_offsets_and_resets(monkeypatch, tmp_path):
    log_file = tmp_path / "app.log"
    log_file.write_text(
        "\n".join(
            [
                "2026-03-23 18:04:50,511 [INFO] first",
                "2026-03-23 18:04:51,511 [INFO] second",
                "2026-03-23 18:04:52,511 [INFO] third",
            ]
        ) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        settings_routes,
        "get_settings",
        lambda: SimpleNamespace(log_file=str(log_file)),
    )

    initial = asyncio.run(settings_routes.get_recent_logs(lines=2))
    assert initial["logs"] == [
        "2026-03-23 18:04:51,511 [INFO] second",
        "2026-03-23 18:04:52,511 [INFO] third",
    ]
    assert initial["next_offset"] == 3
    assert initial["reset"] is False

    incremental = asyncio.run(settings_routes.get_recent_logs(lines=2, offset=2))
    assert incremental["logs"] == ["2026-03-23 18:04:52,511 [INFO] third"]
    assert incremental["next_offset"] == 3

    reset = asyncio.run(settings_routes.get_recent_logs(lines=2, offset=99))
    assert reset["reset"] is True
    assert reset["logs"] == [
        "2026-03-23 18:04:51,511 [INFO] second",
        "2026-03-23 18:04:52,511 [INFO] third",
    ]
