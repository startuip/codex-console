# Technology Stack

**Analysis Date:** 2026-03-23

## Languages

**Primary:**
- Python 3.10+ - application runtime and source code in `webui.py`, `src/**`, and `tests/*.py`; version floor is declared in `pyproject.toml`.

**Secondary:**
- HTML/Jinja templates - server-rendered UI in `templates/`, mounted from `src/web/app.py`.
- JavaScript/CSS/static assets - browser assets served from `static/` via `src/web/app.py`.
- YAML - CI and container config in `.github/workflows/build.yml`, `.github/workflows/docker-publish.yml`, and `docker-compose.yml`.
- Shell/Batch scripts - packaging helpers in `build.sh` and `build.bat`.

## Runtime

**Environment:**
- CPython 3.10+ is required by `pyproject.toml`.
- Python 3.11 is the pinned build/runtime target in `Dockerfile` and `.github/workflows/build.yml`.
- Uvicorn starts `src.web.app:app` from `webui.py` and explicitly enables the `websockets` backend.

**Package Manager:**
- `pip` is the default installer in `requirements.txt`, `Dockerfile`, `build.bat`, and `.github/workflows/build.yml`.
- `uv` is supported for local sync and packaging in `README.md` and `build.sh`.
- Lockfile: missing. No `uv.lock`, `poetry.lock`, `Pipfile.lock`, `package-lock.json`, `pnpm-lock.yaml`, or `yarn.lock` was detected at the repository root.

## Frameworks

**Core:**
- FastAPI - HTTP API, HTML routes, form handling, and WebSocket endpoints in `src/web/app.py` and `src/web/routes/*.py`.
- Uvicorn - ASGI server launcher in `webui.py`.
- Jinja2 and Starlette `StaticFiles` - HTML template rendering and static file serving in `src/web/app.py`.
- SQLAlchemy 2.x - ORM and session layer in `src/database/models.py`, `src/database/session.py`, and `src/database/crud.py`.
- Pydantic 2.x - request/response models and runtime settings schema in `src/web/routes/*.py` and `src/config/settings.py`.

**Testing:**
- pytest - declared in `pyproject.toml` and used by `tests/test_registration_engine.py`, `tests/test_cpa_upload.py`, `tests/test_duck_mail_service.py`, `tests/test_email_service_duckmail_routes.py`, and `tests/test_static_asset_versioning.py`.
- httpx - declared as a dev dependency in `pyproject.toml` for HTTP-level tests.
- Not detected: a separate coverage config, tox/nox, or an alternate test runner.

**Build/Dev:**
- Hatchling - build backend in `pyproject.toml`.
- PyInstaller - single-binary packaging in `codex_register.spec`, `build.sh`, `build.bat`, and `.github/workflows/build.yml`.
- Docker - container packaging and local runtime in `Dockerfile` and `docker-compose.yml`.
- GitHub Actions - binary release and container publish automation in `.github/workflows/build.yml` and `.github/workflows/docker-publish.yml`.
- Playwright - optional browser automation extra in `pyproject.toml` and `src/core/openai/payment.py`.

## Key Dependencies

**Critical:**
- `curl-cffi` - the outbound HTTP stack for OpenAI, Microsoft, proxy tests, payment flows, upload targets, and most mail providers in `src/core/http_client.py`, `src/core/openai/*.py`, `src/core/upload/*.py`, and `src/services/*.py`.
- `fastapi` - the only web framework; all API and HTML routing hangs off `src/web/app.py` and `src/web/routes/*.py`.
- `uvicorn` - runtime server entrypoint in `webui.py`.
- `sqlalchemy` - persistence layer for accounts, settings, proxies, and upload service definitions in `src/database/models.py` and `src/database/session.py`.
- `psycopg[binary]` and `aiosqlite` - PostgreSQL and SQLite drivers surfaced through SQLAlchemy URL handling in `src/database/session.py` and `src/config/settings.py`.
- `pydantic` - typed settings and API contracts in `src/config/settings.py` and `src/web/routes/*.py`.

**Infrastructure:**
- `jinja2` - template rendering in `src/web/app.py`.
- `python-multipart` - FastAPI form parsing for `/login` in `src/web/app.py`.
- `websockets` - Uvicorn WebSocket transport selected in `webui.py` and used by `src/web/routes/websocket.py`.
- `playwright` - optional runtime dependency for `open_url_incognito` in `src/core/openai/payment.py`; the code falls back to the system browser when it is absent.
- `pydantic-settings` - declared in `pyproject.toml` and bundled in `codex_register.spec`, but the active runtime config path is the custom DB-backed `Settings` model in `src/config/settings.py`.

## Configuration

**Environment:**
- Startup can read an optional `.env` beside the executable or project root in `webui.py`, but steady-state settings come from the database-backed `settings` table defined in `src/database/models.py` and loaded by `src/config/settings.py`.
- Database bootstrap honors `APP_DATABASE_URL` and `DATABASE_URL` in `src/database/session.py` and `src/config/settings.py`.
- HTTP listener bootstrap can be overridden by CLI flags or `WEBUI_HOST`, `WEBUI_PORT`, `WEBUI_ACCESS_PASSWORD`, `DEBUG`, and `LOG_LEVEL` in `webui.py`.
- DB-backed settings also honor `APP_HOST`, `APP_PORT`, and `APP_ACCESS_PASSWORD` in `src/config/settings.py`.
- Packaged/container runs inject writable paths through `APP_DATA_DIR` and `APP_LOGS_DIR` in `webui.py`.
- Secrets are modeled with `SecretStr` in memory in `src/config/settings.py`, but the application persists them through the app database rather than a dedicated secrets manager.

**Build:**
- Packaging metadata: `pyproject.toml`.
- Install surface: `requirements.txt`.
- Binary bundle recipe: `codex_register.spec`.
- Container image recipe: `Dockerfile`.
- Container runtime example: `docker-compose.yml`.
- Local packaging scripts: `build.sh` and `build.bat`.
- Release automation: `.github/workflows/build.yml`.
- Container publish automation: `.github/workflows/docker-publish.yml`.

## Platform Requirements

**Development:**
- Use Python 3.10+ with `pip` or `uv`; no Node toolchain or JS package manager manifest is present.
- Keep outbound HTTPS access available for OpenAI, Microsoft, email-provider APIs, proxy check endpoints, and upload destinations referenced from `src/core/*`, `src/services/*`, and `src/web/routes/settings.py`.
- Keep the filesystem writable for `data/` and `logs/`; `webui.py` creates both on startup.
- Install Playwright plus a Chromium browser only if the payment auto-open flow in `src/core/openai/payment.py` is needed.

**Production:**
- Supported deployment shapes are `python webui.py`, a PyInstaller binary built from `codex_register.spec`, or a Docker image from `Dockerfile`.
- Default persistence is local SQLite in `data/database.db`; remote PostgreSQL is enabled by connection URL without changing application code in `src/database/session.py`.
- The container path expects mounted `data/` and `logs/` volumes per `docker-compose.yml`.
- HTTP service is exposed through FastAPI/Uvicorn only; no reverse proxy, CDN, worker queue, or external scheduler is built into the repo.

---

*Stack analysis: 2026-03-23*
