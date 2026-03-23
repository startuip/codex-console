# Architecture

**Analysis Date:** 2026-03-23

## Pattern Overview

**Overall:** Layered FastAPI monolith with server-rendered pages, JSON APIs, WebSocket task streaming, and a stateful registration workflow engine.

**Key Characteristics:**
- `webui.py` is the runtime bootstrap. It loads environment overrides, creates `data/` and `logs/`, initializes the database, configures logging, and starts Uvicorn against `src.web.app:app`.
- `src/web/app.py` is the composition root. It creates the FastAPI app, mounts `static/`, points Jinja to `templates/`, wires page routes, mounts `/api` routers, and attaches WebSocket endpoints.
- The registration path is workflow-oriented rather than service-oriented. `src/core/register.py` owns the multi-step OpenAI flow end to end and mutates internal state across helper methods.
- Long-running work is pushed out of request handlers into the shared `ThreadPoolExecutor` in `src/web/task_manager.py`, then surfaced back to the browser over WebSockets and polling endpoints.
- Durable state is SQL-backed in `src/database/models.py`; transient progress state is process-local in `src/web/task_manager.py` and `src/web/routes/registration.py`.
- There is no dependency-injection container. Most modules import singleton-style globals directly: `get_settings()`, `get_db()`, `task_manager`, and `EmailServiceFactory`.

## Layers

**Bootstrap / Runtime Layer:**
- Purpose: Start the process, make runtime directories, initialize persistence, and hand control to the ASGI app.
- Location: `webui.py`, `src/database/init_db.py`, `src/core/utils.py`
- Contains: CLI parsing, `.env` loading, log setup, database bootstrap, Uvicorn startup.
- Depends on: `src.config.settings`, `src.database.session`, `src.web.app`, `uvicorn`
- Used by: `python webui.py`, the `codex-console` console script in `pyproject.toml`, `Dockerfile`, and `codex_register.spec`

**Web Composition Layer:**
- Purpose: Assemble the FastAPI application and the browser-facing page shell.
- Location: `src/web/app.py`
- Contains: FastAPI app creation, page routes, template setup, static mounting, login cookie handling, startup and shutdown hooks.
- Depends on: `src.config.settings`, `src.web.routes`, `src.web.task_manager`
- Used by: Uvicorn and all browser requests

**Route Layer:**
- Purpose: Convert HTTP requests into CRUD calls, workflow dispatch, and typed API responses.
- Location: `src/web/routes/`
- Contains: Domain routers in `accounts.py`, `registration.py`, `email.py`, `settings.py`, `payment.py`, and `upload/*.py`
- Depends on: `src.database.crud`, `src.database.session`, `src.core.*`, `src.services`, `src.config.settings`
- Used by: `static/js/*.js` and any external client hitting `/api/*`

**Task Orchestration Layer:**
- Purpose: Track running jobs, stream logs, manage cancellation, and aggregate batch progress.
- Location: `src/web/task_manager.py`, `src/web/routes/registration.py`, `src/web/routes/websocket.py`
- Contains: Shared thread pool, log queues, task status maps, batch status maps, WebSocket registration, executor dispatch, batch runners.
- Depends on: `asyncio`, `concurrent.futures`, `src.database.crud`, `src.core.register`
- Used by: Registration endpoints and the browser consoles in `static/js/app.js`

**Workflow / Protocol Layer:**
- Purpose: Implement OpenAI-facing automation and external account/export actions.
- Location: `src/core/register.py`, `src/core/http_client.py`, `src/core/dynamic_proxy.py`, `src/core/openai/*.py`, `src/core/upload/*.py`
- Contains: Registration workflow state machine, OAuth helpers, Sentinel handling, token refresh, payment-link generation, proxy fetch, outbound upload adapters.
- Depends on: `curl_cffi`, `src.config.*`, `src.database.*`, `src.services`
- Used by: Route handlers and background registration tasks

**Email Adapter Layer:**
- Purpose: Normalize multiple inbox providers behind one interface.
- Location: `src/services/base.py`, `src/services/*.py`, `src/services/outlook/**`
- Contains: `BaseEmailService`, `EmailServiceFactory`, provider implementations, Outlook provider failover, token handling, email parsing.
- Depends on: `src.config.constants`, `src.config.settings`, and for several providers `src.core.http_client`
- Used by: `src/core/register.py` and `src/web/routes/accounts.py`

**Persistence Layer:**
- Purpose: Own schema, sessions, initialization, and common queries.
- Location: `src/database/models.py`, `src/database/session.py`, `src/database/crud.py`, `src/database/init_db.py`
- Contains: SQLAlchemy ORM models, session manager singleton, manual SQLite migration logic, CRUD helpers.
- Depends on: SQLAlchemy, environment variables, `src.config.settings` during initialization
- Used by: Every backend layer

**Configuration Layer:**
- Purpose: Provide typed settings, defaults, and enums/constants shared across the backend.
- Location: `src/config/settings.py`, `src/config/constants.py`
- Contains: `SETTING_DEFINITIONS`, `Settings`, default values, env overrides, OpenAI constants, enums like `EmailServiceType`.
- Depends on: The database at runtime for persisted settings; environment variables for startup overrides.
- Used by: Bootstrap, web routes, workflow code, email services, and proxy helpers

## Data Flow

**Single Registration Flow:**

1. `templates/index.html` renders the registration console and loads `static/js/app.js`.
2. `static/js/app.js` submits to `POST /api/registration/start` in `src/web/routes/registration.py`.
3. The route creates a `registration_tasks` row through `crud.create_registration_task()` in `src/database/crud.py`, then schedules `run_registration_task()` as a FastAPI background task.
4. `run_registration_task()` in `src/web/routes/registration.py` hands work to `_run_sync_registration_task()` inside the shared executor from `src/web/task_manager.py`.
5. `_run_sync_registration_task()` resolves proxy selection, normalizes email-service config, instantiates the provider through `EmailServiceFactory.create()` in `src/services/base.py`, and builds a `RegistrationEngine`.
6. `RegistrationEngine.run()` in `src/core/register.py` performs IP validation, email creation, OpenAI OAuth start, Sentinel solving, signup or login continuation, OTP retrieval, workspace selection, redirect following, and OAuth token exchange.
7. On success, `RegistrationEngine.save_to_database()` writes an `accounts` row through `crud.create_account()`; the task row is updated in `registration_tasks`, and logs are appended to the task record.
8. `src/web/routes/websocket.py` and `src/web/task_manager.py` stream log and status events back to `static/js/app.js`, which updates the console UI and recent-account list.

**Batch Registration Flow:**

1. `static/js/app.js` submits either `POST /api/registration/batch` or `POST /api/registration/outlook-batch`.
2. `src/web/routes/registration.py` pre-creates one `registration_tasks` row per requested unit of work.
3. The route schedules `run_batch_registration()`, which selects `run_batch_parallel()` or `run_batch_pipeline()` based on the requested mode.
4. Each batch runner still delegates each individual task to `run_registration_task()`, so single-task behavior stays centralized.
5. Batch counters and logs are tracked twice: in local `batch_tasks` dicts inside `src/web/routes/registration.py` and in the process-wide batch state inside `src/web/task_manager.py`.
6. `static/js/app.js` consumes `/api/ws/batch/{batch_id}` for push updates and `/api/registration/batch/{batch_id}` or `/api/registration/outlook-batch/{batch_id}` for fallback polling and resume behavior.

**Email Service Configuration Flow:**

1. `templates/email_services.html` and `static/js/email_services.js` call `/api/email-services/*`.
2. `src/web/routes/email.py` reads and writes the `email_services` table directly through SQLAlchemy sessions and `crud` helpers.
3. Registration code in `src/web/routes/registration.py` looks up those records at run time and converts them into concrete provider instances through `EmailServiceFactory`.

**Settings and Proxy Flow:**

1. `templates/settings.html` and `static/js/settings.js` call `/api/settings/*`, `/api/cpa-services/*`, `/api/sub2api-services/*`, and `/api/tm-services/*`.
2. `src/web/routes/settings.py` persists settings through `update_settings()` in `src/config/settings.py`, which updates both the cached `Settings` instance and the `settings` table.
3. Proxy records are stored in `proxies` via `src/database/crud.py`, then consumed by registration and account actions through `crud.get_random_proxy()` or `settings.proxy_url`.

**Account Management Flow:**

1. `templates/accounts.html` and `static/js/accounts.js` call `/api/accounts/*`.
2. `src/web/routes/accounts.py` performs account CRUD against `accounts`, token refresh and validation through `src/core/openai/token_refresh.py`, exports through `src/core/upload/*.py`, and inbox-code checks by rebuilding an email-service instance.
3. The account page does not introduce a new domain service layer; routes call workflow helpers and CRUD functions directly.

**Payment Flow:**

1. `templates/payment.html` and `static/js/payment.js` call `/api/payment/*`.
2. `src/web/routes/payment.py` loads `Account` rows, resolves a proxy, and delegates to `src/core/openai/payment.py`.
3. `src/core/openai/payment.py` builds Plus or Team checkout links, optionally launches a local incognito browser, and inspects current subscription state using stored cookies.

**State Management:**
- Persistent state lives in database tables from `src/database/models.py`: `accounts`, `email_services`, `registration_tasks`, `settings`, `proxies`, `cpa_services`, `sub2api_services`, and `tm_services`.
- Transient backend state lives in in-memory dicts in `src/web/task_manager.py` and `src/web/routes/registration.py`. Restarting the process clears live progress metadata but not database task rows.
- Browser state is page-local in `static/js/*.js`, with some resume state kept in `sessionStorage` inside `static/js/app.js`.

## Key Abstractions

**`RegistrationEngine`:**
- Purpose: Own the end-to-end OpenAI signup/login/token acquisition workflow.
- Examples: `src/core/register.py`
- Pattern: Stateful workflow object with many private step methods and a final `RegistrationResult`.

**`RegistrationResult`:**
- Purpose: Carry workflow success/failure, account identifiers, tokens, logs, and metadata without throwing route-layer exceptions.
- Examples: `src/core/register.py`
- Pattern: Dataclass result DTO returned by `RegistrationEngine.run()`.

**`BaseEmailService` and `EmailServiceFactory`:**
- Purpose: Give the registration flow one interface for temp mail, custom mail, IMAP, DuckMail, Freemail, and Outlook.
- Examples: `src/services/base.py`, `src/services/__init__.py`, `src/services/duck_mail.py`, `src/services/imap_mail.py`
- Pattern: Abstract base class plus registry-based factory.

**`OutlookProvider`:**
- Purpose: Encapsulate one Outlook transport implementation.
- Examples: `src/services/outlook/providers/base.py`, `src/services/outlook/providers/imap_old.py`, `src/services/outlook/providers/imap_new.py`, `src/services/outlook/providers/graph_api.py`
- Pattern: Strategy objects selected by `OutlookService`, combined with health-based failover.

**`HealthChecker` and `FailoverManager`:**
- Purpose: Track provider failures and decide when Outlook should switch transports.
- Examples: `src/services/outlook/health_checker.py`
- Pattern: Stateful failover policy object used only inside the Outlook subdomain.

**`DatabaseSessionManager`:**
- Purpose: Hold the SQLAlchemy engine, create sessions, create tables, and run manual SQLite migrations.
- Examples: `src/database/session.py`
- Pattern: Process-level singleton initialized by `init_database()`.

**`Settings`:**
- Purpose: Present typed application configuration even though the source of truth is mostly the `settings` table.
- Examples: `src/config/settings.py`
- Pattern: Cached Pydantic model hydrated from database rows with environment-variable overrides layered on top.

**`TaskManager`:**
- Purpose: Bridge executor jobs, task logs, cancellation state, and WebSocket fan-out.
- Examples: `src/web/task_manager.py`, `src/web/routes/websocket.py`
- Pattern: Process-local coordinator over a shared `ThreadPoolExecutor`.

## Entry Points

**Process Entry Point:**
- Location: `webui.py`
- Triggers: `python webui.py`, the `codex-console` console script in `pyproject.toml`, Docker `CMD ["python", "webui.py"]`, and the PyInstaller executable defined by `codex_register.spec`
- Responsibilities: Load `.env`, create runtime directories, initialize database defaults, configure logging, apply CLI overrides, and start Uvicorn

**ASGI App Entry Point:**
- Location: `src/web/app.py`
- Triggers: Uvicorn importing `src.web.app:app`
- Responsibilities: Create the FastAPI app, mount routers and WebSockets, expose HTML pages, and attach startup hooks that reinitialize DB state and register the asyncio loop with `task_manager`

**Database Bootstrap Entry Point:**
- Location: `src/database/init_db.py`
- Triggers: `webui.py`, reload startup in `src/web/app.py`, or direct script execution
- Responsibilities: Create tables and seed default settings

**Browser Entry Points:**
- Location: `static/js/app.js`, `static/js/accounts.js`, `static/js/email_services.js`, `static/js/settings.js`, `static/js/payment.js`
- Triggers: Matching templates in `templates/index.html`, `templates/accounts.html`, `templates/email_services.html`, `templates/settings.html`, and `templates/payment.html`
- Responsibilities: Own each page’s fetch calls, polling loops, WebSocket connections, and DOM updates

## Error Handling

**Strategy:** Route-layer validation and HTTP status codes at the boundary, result-object and boolean returns inside workflow code, and best-effort log streaming for long-running tasks.

**Patterns:**
- Route handlers raise `HTTPException` for invalid input or missing records, for example in `src/web/routes/registration.py`, `src/web/routes/email.py`, `src/web/routes/settings.py`, and `src/web/routes/payment.py`.
- `RegistrationEngine` records most failures into `RegistrationResult.error_message` and task logs rather than propagating raw exceptions from `src/core/register.py`.
- Email-provider abstractions surface recoverable failures as `EmailServiceError`, `False`, or `None` in `src/services/base.py` and concrete services.
- WebSocket sends in `src/web/task_manager.py` and `src/web/routes/websocket.py` swallow connection errors and continue serving remaining clients.
- There is no centralized FastAPI exception middleware; handling is local to each route or workflow.

## Cross-Cutting Concerns

**Logging:** Module loggers are used throughout the backend. `webui.py` calls `setup_logging()` from `src/core/utils.py`, `RegistrationEngine._log()` mirrors messages into memory and the `registration_tasks.logs` column, and `TaskManager` rebroadcasts those logs to WebSocket subscribers.

**Validation:** Request payloads use Pydantic models inside `src/web/routes/*.py`. Configuration values are validated when `Settings` is instantiated in `src/config/settings.py`. Enum-like value checks are usually done manually by coercing `EmailServiceType(...)` or validating allowed strings in the route layer.

**Authentication:** HTML pages are protected by a cookie-based login flow in `src/web/app.py` using the `webui_auth` cookie derived from `webui_access_password`. OpenAI account authentication is a separate OAuth flow implemented in `src/core/openai/oauth.py` and consumed by `src/core/register.py`.

**Static Asset Versioning:** `src/web/app.py` computes a version token from the newest `static/` file mtime and injects it into templates as `static_version`, so each template links CSS and JS with cache-busting query strings.

**Schema Evolution:** There is no external migration tool. Schema updates currently require coordinated changes in `src/database/models.py` and `DatabaseSessionManager.migrate_tables()` in `src/database/session.py`.

---

*Architecture analysis: 2026-03-23*
