"""
FastAPI 应用主文件
轻量级 Web UI，支持注册、账号管理、设置
"""

import logging
import sys
import secrets
import hmac
import hashlib
from typing import Optional, Dict, Any
from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse

from ..config.settings import get_settings
from ..config.project_notice import PROJECT_NOTICE
from ..core.cpa_auto_refill import cpa_auto_refill_scheduler
from .routes import api_router
from .routes.websocket import router as ws_router
from .task_manager import task_manager

logger = logging.getLogger(__name__)

if getattr(sys, "frozen", False):
    _RESOURCE_ROOT = Path(sys._MEIPASS)
else:
    _RESOURCE_ROOT = Path(__file__).parent.parent.parent

STATIC_DIR = _RESOURCE_ROOT / "static"
TEMPLATES_DIR = _RESOURCE_ROOT / "templates"


def _build_static_asset_version(static_dir: Path) -> str:
    latest_mtime = 0
    if static_dir.exists():
        for path in static_dir.rglob("*"):
            if path.is_file():
                latest_mtime = max(latest_mtime, int(path.stat().st_mtime))
    return str(latest_mtime or 1)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="OpenAI/Codex CLI 自动注册系统 Web UI",
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
        logger.info(f"静态文件目录: {STATIC_DIR}")
    else:
        STATIC_DIR.mkdir(parents=True, exist_ok=True)
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
        logger.info(f"创建静态文件目录: {STATIC_DIR}")

    if not TEMPLATES_DIR.exists():
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"创建模板目录: {TEMPLATES_DIR}")

    app.include_router(api_router, prefix="/api")
    app.include_router(ws_router, prefix="/api")

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    templates.env.globals["static_version"] = _build_static_asset_version(STATIC_DIR)
    templates.env.globals["project_notice"] = PROJECT_NOTICE

    def _render_template(
        request: Request,
        name: str,
        context: Optional[Dict[str, Any]] = None,
        status_code: int = 200,
    ) -> HTMLResponse:
        template_context: Dict[str, Any] = {"request": request}
        if context:
            template_context.update(context)

        try:
            return templates.TemplateResponse(
                request=request,
                name=name,
                context=template_context,
                status_code=status_code,
            )
        except TypeError:
            return templates.TemplateResponse(
                name,
                template_context,
                status_code=status_code,
            )

    def _auth_token(password: str) -> str:
        secret = get_settings().webui_secret_key.get_secret_value().encode("utf-8")
        return hmac.new(secret, password.encode("utf-8"), hashlib.sha256).hexdigest()

    def _is_authenticated(request: Request) -> bool:
        cookie = request.cookies.get("webui_auth")
        expected = _auth_token(get_settings().webui_access_password.get_secret_value())
        return bool(cookie) and secrets.compare_digest(cookie, expected)

    def _redirect_to_login(request: Request) -> RedirectResponse:
        return RedirectResponse(url=f"/login?next={request.url.path}", status_code=302)

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request, next: Optional[str] = "/"):
        return _render_template(
            request,
            "login.html",
            {"error": "", "next": next or "/"},
        )

    @app.post("/login")
    async def login_submit(request: Request, password: str = Form(...), next: Optional[str] = "/"):
        expected = get_settings().webui_access_password.get_secret_value()
        if not secrets.compare_digest(password, expected):
            return _render_template(
                request,
                "login.html",
                {"error": "密码错误", "next": next or "/"},
                status_code=401,
            )

        response = RedirectResponse(url=next or "/", status_code=302)
        response.set_cookie("webui_auth", _auth_token(expected), httponly=True, samesite="lax")
        return response

    @app.get("/logout")
    async def logout(request: Request, next: Optional[str] = "/login"):
        response = RedirectResponse(url=next or "/login", status_code=302)
        response.delete_cookie("webui_auth")
        return response

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        if not _is_authenticated(request):
            return _redirect_to_login(request)
        return _render_template(request, "index.html")

    @app.get("/accounts", response_class=HTMLResponse)
    async def accounts_page(request: Request):
        if not _is_authenticated(request):
            return _redirect_to_login(request)
        return _render_template(request, "accounts.html")

    @app.get("/accounts-overview", response_class=HTMLResponse)
    async def accounts_overview_page(request: Request):
        if not _is_authenticated(request):
            return _redirect_to_login(request)
        return _render_template(request, "accounts_overview.html")

    @app.get("/email-services", response_class=HTMLResponse)
    async def email_services_page(request: Request):
        if not _is_authenticated(request):
            return _redirect_to_login(request)
        return _render_template(request, "email_services.html")

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request):
        if not _is_authenticated(request):
            return _redirect_to_login(request)
        return _render_template(request, "settings.html")

    @app.get("/payment", response_class=HTMLResponse)
    async def payment_page(request: Request):
        return _render_template(request, "payment.html")

    @app.get("/card-pool", response_class=HTMLResponse)
    async def card_pool_page(request: Request):
        if not _is_authenticated(request):
            return _redirect_to_login(request)
        return _render_template(request, "card_pool.html")

    @app.get("/auto-team", response_class=HTMLResponse)
    async def auto_team_page(request: Request):
        if not _is_authenticated(request):
            return _redirect_to_login(request)
        return _render_template(request, "auto_team.html")

    @app.get("/logs", response_class=HTMLResponse)
    async def logs_page(request: Request):
        if not _is_authenticated(request):
            return _redirect_to_login(request)
        return _render_template(request, "logs.html")

    @app.on_event("startup")
    async def startup_event():
        import asyncio
        from ..database.init_db import initialize_database
        from ..core.db_logs import cleanup_database_logs

        try:
            initialize_database()
        except Exception as e:
            logger.warning(f"数据库初始化: {e}")

        loop = asyncio.get_event_loop()
        task_manager.set_loop(loop)
        cpa_auto_refill_scheduler.start()

        async def run_log_cleanup_once():
            try:
                result = await asyncio.to_thread(cleanup_database_logs)
                logger.info(
                    "后台日志清理完成: 删除 %s 条，剩余 %s 条",
                    result.get("deleted_total", 0),
                    result.get("remaining", 0),
                )
            except Exception as exc:
                logger.warning(f"后台日志清理失败: {exc}")

        async def periodic_log_cleanup():
            while True:
                try:
                    await asyncio.sleep(3600)
                    await run_log_cleanup_once()
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.warning(f"后台日志定时清理异常: {exc}")

        await run_log_cleanup_once()
        app.state.log_cleanup_task = asyncio.create_task(periodic_log_cleanup())

        logger.info("=" * 50)
        logger.info(f"{settings.app_name} v{settings.app_version} 启动中，程序正在伸懒腰...")
        logger.info(f"调试模式: {settings.debug}")
        logger.info(f"数据库连接已接好线: {settings.database_url}")
        logger.info("=" * 50)

    @app.on_event("shutdown")
    async def shutdown_event():
        cleanup_task = getattr(app.state, "log_cleanup_task", None)
        if cleanup_task:
            cleanup_task.cancel()
        await cpa_auto_refill_scheduler.stop()
        logger.info("应用关闭，今天先收摊啦")

    return app


app = create_app()
