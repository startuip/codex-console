# Coding Conventions

**Analysis Date:** 2026-03-23

## Naming Patterns

**Files:**
- Use `snake_case` for Python modules across `src/`, for example `src/core/http_client.py`, `src/web/routes/registration.py`, and `src/services/duck_mail.py`.
- Use package barrels in `__init__.py` files to re-export public APIs from `src/__init__.py`, `src/config/__init__.py`, `src/core/__init__.py`, `src/database/__init__.py`, `src/services/__init__.py`, and `src/web/__init__.py`.
- Use page-matched browser script names in `static/js/`, for example `static/js/app.js`, `static/js/accounts.js`, `static/js/settings.js`, and `static/js/payment.js` line up with `templates/index.html`, `templates/accounts.html`, `templates/settings.html`, and `templates/payment.html`.
- Use `test_*.py` names under `tests/`, for example `tests/test_registration_engine.py` and `tests/test_cpa_upload.py`.

**Functions:**
- Use `snake_case` for Python functions and methods, including CRUD verbs like `create_account`, `get_accounts`, `update_email_service`, and `delete_registration_task` in `src/database/crud.py`.
- Prefix internal helpers with `_` when they are file-local or normalization helpers, for example `_build_static_asset_version` in `src/web/app.py`, `_normalize_email_service_config` in `src/web/routes/registration.py`, and `_build_sqlalchemy_url` in `src/database/session.py`.
- Use `async def` for FastAPI handlers and WebSocket handlers in `src/web/app.py`, `src/web/routes/*.py`, and `src/web/routes/websocket.py`.
- Browser scripts use `camelCase` function names such as `loadAvailableServices`, `handleStartRegistration`, `loadOutlookSettings`, and `testCpaServiceById` in `static/js/app.js` and `static/js/settings.js`.

**Variables:**
- Use `snake_case` for Python locals and module state, for example `running_tasks`, `batch_tasks`, `_settings`, `proxy_url`, and `email_service_config` in `src/web/routes/registration.py` and `src/config/settings.py`.
- Use `camelCase` for browser globals and DOM references, for example `currentTask`, `batchCompleted`, `useWebSocket`, and `activeBatchId` in `static/js/app.js`.
- Use module-level `logger = logging.getLogger(__name__)` in operational modules such as `webui.py`, `src/core/http_client.py`, `src/database/session.py`, `src/web/task_manager.py`, and `src/services/duck_mail.py`.

**Types:**
- Use `PascalCase` for classes, dataclasses, enums, and Pydantic models, for example `Settings`, `RequestConfig`, `DatabaseSessionManager`, `EmailServiceFactory`, `RegistrationTaskCreate`, and `TokenRefreshResult`.
- Use `UPPER_CASE` for constants and enum members in `src/config/constants.py` and `src/config/settings.py`, for example `OPENAI_API_ENDPOINTS`, `OPENAI_PAGE_TYPES`, `SETTING_DEFINITIONS`, and `SECRET_FIELDS`.

## Code Style

**Formatting:**
- No formatter config is detected. There is no `ruff`, `black`, `isort`, `flake8`, `prettier`, `biome`, or `.editorconfig` file at the repo root.
- Python is hand-formatted in a mostly PEP 8 shape: 4-space indentation, grouped imports, blank lines between top-level definitions, and triple-quoted module docstrings, as seen in `webui.py`, `src/core/http_client.py`, and `src/services/base.py`.
- Large Python files use banner comments to carve sections, for example `src/database/crud.py`, `src/web/routes/registration.py`, and `src/web/routes/email.py`.
- Browser JavaScript is also hand-formatted: semicolons are common, `const`/`let` are preferred over `var`, async flows use `async`/`await`, and files begin with a block comment, as seen in `static/js/utils.js`, `static/js/app.js`, and `static/js/settings.js`.
- User-facing strings, comments, and logs are primarily Chinese across `webui.py`, `src/web/app.py`, `src/web/routes/websocket.py`, and `static/js/*.js`. Match that tone when extending existing modules.

**Linting:**
- No lint runner or lint rules are configured in `pyproject.toml`, root config files, or `.github/workflows/*.yml`.
- Style is enforced by existing file patterns rather than automation. When adding code, follow nearby spacing, naming, and section-comment conventions in the target module.

## Import Organization

**Order:**
1. Python standard library imports come first, for example `logging`, `os`, `asyncio`, `uuid`, `Path`, and `datetime`.
2. Third-party imports come next, for example `fastapi`, `pydantic`, `sqlalchemy`, `uvicorn`, and `curl_cffi` in `src/web/app.py`, `src/config/settings.py`, and `src/core/http_client.py`.
3. Project-local imports come last and are usually relative inside `src/`, for example `from ..config.settings import get_settings` in `src/web/app.py` and `from ...database import crud` in `src/web/routes/accounts.py`.

**Path Aliases:**
- Runtime package code prefers relative imports inside `src/`, for example `from ..database.session import get_db` and `from .routes import api_router`.
- Entry-point and tests prefer absolute imports from `src`, for example `from src.core.register import RegistrationEngine` in `tests/test_registration_engine.py` and `from src.web.app import app` indirectly through `webui.py`.
- Browser code has no module loader or aliasing layer. `templates/*.html` load shared utilities first and page-specific scripts second using plain script tags, which is why globals like `api`, `toast`, and `theme` from `static/js/utils.js` are consumed directly in `static/js/app.js` and `static/js/settings.js`.

**Lazy Imports:**
- Use in-function imports when avoiding circular dependencies, deferring optional integrations, or limiting startup work. This pattern appears in `src/config/settings.py`, `src/web/routes/registration.py`, `src/web/routes/settings.py`, `src/database/crud.py`, and `src/core/openai/payment.py`.
- Preserve this pattern when extending modules that already import peers lazily. Do not eagerly lift those imports to the top of the file unless you verify the dependency graph.

## Configuration Patterns

**Primary Source:**
- Centralize runtime settings in `src/config/settings.py` using `SettingDefinition`, `SETTING_DEFINITIONS`, `SETTING_TYPES`, `SECRET_FIELDS`, and the `Settings` Pydantic model.
- Access configuration through `get_settings()` and persist changes through `update_settings()` from `src/config/settings.py`. Most runtime modules follow this, including `src/web/app.py`, `src/core/http_client.py`, `src/core/openai/token_refresh.py`, and `src/core/register.py`.
- Treat secrets as `SecretStr` in the settings layer, for example `webui_secret_key`, `webui_access_password`, `proxy_password`, and `cpa_api_token` in `src/config/settings.py`.

**Bootstrap Flow:**
- `webui.py` bootstraps the app in a specific order: load `.env` if present, ensure `data/` and `logs/` exist, initialize the database, then load settings and configure logging.
- CLI flags and selected environment variables are translated into `update_settings(...)` calls in `webui.py`, after which normal runtime code still reads from `get_settings()`.
- `src/database/session.py` also accepts environment-driven database bootstrap through `APP_DATABASE_URL`, `DATABASE_URL`, and `APP_DATA_DIR` before the DB-backed settings layer is available.

**Schema-like Config Metadata:**
- Settings metadata is defined in one place and consumed indirectly elsewhere. When a new setting is added, the existing pattern is to update `SETTING_DEFINITIONS`, `SETTING_TYPES` if needed, and the `Settings` model in `src/config/settings.py`.
- Route-specific configuration schemas live next to the route handlers as local Pydantic models, for example `ProxySettings`, `RegistrationSettings`, and `OutlookSettings` in `src/web/routes/settings.py` and `GenerateLinkRequest` in `src/web/routes/payment.py`.

## Error Handling

**Patterns:**
- Use route-layer `HTTPException` for request validation failures, missing records, or user-facing API errors. This is consistent in `src/web/routes/accounts.py`, `src/web/routes/email.py`, `src/web/routes/payment.py`, and `src/web/routes/upload/*.py`.
- Use dedicated domain exceptions for reusable core/service abstractions, including `EmailServiceError` in `src/services/base.py`, `HTTPClientError` in `src/core/http_client.py`, and `SentinelPOWError` in `src/core/openai/sentinel.py`.
- Service and integration code frequently catches broad `Exception as e`, logs the failure, and returns `False`, `None`, or `(success, message)` tuples rather than bubbling rich exception types. This is the dominant operational pattern in `src/core/openai/token_refresh.py`, `src/core/upload/cpa_upload.py`, `src/services/duck_mail.py`, `src/services/outlook/service.py`, and `src/web/task_manager.py`.
- Database write helpers commit immediately and refresh ORM objects inside CRUD functions in `src/database/crud.py`. Transaction-scoped rollback logic exists in `DatabaseSessionManager.session_scope()` in `src/database/session.py`.

**API Sanitization:**
- Do not return raw secret values from route responses. Existing code strips them and replaces them with `has_*` flags through `filter_sensitive_config()` in `src/web/routes/email.py` and `Proxy.to_dict(include_password=False)` in `src/database/models.py`.
- Browser-side API failures are surfaced through `ApiClient.request()` in `static/js/utils.js`, which turns non-2xx responses into thrown `Error` instances using `detail` from the JSON body when available.

## Logging

**Framework:**
- Use the standard `logging` module. Root logging is configured once by `setup_logging()` in `src/core/utils.py` and used by modules through `logging.getLogger(__name__)`.

**Patterns:**
- Operational logs use f-strings heavily, for example in `webui.py`, `src/web/app.py`, `src/web/routes/websocket.py`, and `src/services/outlook/token_manager.py`.
- Startup, retry, websocket, and network code log at `info` and `warning` levels liberally. Reuse that style when adding new external calls or background task state transitions.
- Some logs are intentionally conversational or humorous in Chinese, especially in `webui.py`, `src/web/app.py`, `src/web/routes/websocket.py`, and `src/web/task_manager.py`. Match the surrounding file’s tone instead of normalizing it globally.
- Frontend code favors user-visible toast notifications for recoverable failures and leaves `console.error` mostly for developer diagnostics, as seen in `static/js/utils.js` and `static/js/settings.js`.

## Comments

**When to Comment:**
- Start modules with a short triple-quoted docstring explaining purpose, as in `src/web/app.py`, `src/core/http_client.py`, `src/database/models.py`, and `src/services/base.py`.
- Use section banners to split long files into functional areas, for example in `src/database/crud.py`, `src/web/routes/registration.py`, and `static/js/utils.js`.
- Add inline comments mainly for sequencing, bootstrap, or reliability-sensitive logic, such as the PyInstaller/static-path notes in `webui.py` and `src/web/app.py`, and the websocket send-order notes in `src/web/task_manager.py`.

**JSDoc/TSDoc:**
- Python relies on docstrings rather than separate API docs.
- Browser scripts use top-of-file block comments and targeted inline comments, not formal JSDoc. See `static/js/utils.js` and `static/js/app.js`.

## Function Design

**Size:**
- Utility and CRUD helpers stay small, but route and orchestration modules are large. Notable large files include `src/web/routes/registration.py`, `src/web/routes/accounts.py`, `src/core/register.py`, `src/config/settings.py`, and `src/database/crud.py`.
- The prevailing style is to keep related logic in one module and extract only the helper pieces that are reused or reliability-sensitive.

**Parameters:**
- Type-annotate Python function signatures broadly, including return types for helpers, CRUD functions, and services. This is visible in `src/core/http_client.py`, `src/services/base.py`, `src/database/session.py`, and `src/web/routes/registration.py`.
- Use route-local Pydantic models for request payloads and response bodies, for example `AccountUpdateRequest` in `src/web/routes/accounts.py`, `TempmailTestRequest` in `src/web/routes/email.py`, and `DynamicProxySettings` in `src/web/routes/settings.py`.
- Existing route models often use literal list defaults such as `cpa_service_ids: List[int] = []` in `src/web/routes/registration.py`. This is the current house pattern in those modules.

**Return Values:**
- CRUD helpers usually return ORM objects or booleans from `src/database/crud.py`.
- Route helpers convert ORM models into response models with explicit serializer functions like `task_to_response()` and `service_to_response()` in `src/web/routes/registration.py` and `src/web/routes/email.py`.
- Integration helpers often return tuples such as `(success, message)` instead of richer result objects, for example in `src/core/upload/cpa_upload.py`, `src/core/upload/sub2api_upload.py`, and `src/core/upload/team_manager_upload.py`.

## Module Design

**Exports:**
- Use `__all__` in package barrels to define the intended public surface, as in `src/__init__.py`, `src/core/__init__.py`, `src/config/__init__.py`, `src/database/__init__.py`, and `src/services/__init__.py`.
- Central registration side effects live in barrels when the package needs runtime discovery. The clearest example is `src/services/__init__.py`, which imports all email services and calls `EmailServiceFactory.register(...)` for each one.

**Barrel Files:**
- Barrels are used heavily and matter operationally. If a new service or top-level API is added, update the relevant `__init__.py` exports so tests and runtime imports continue to work through package roots.
- Route composition is centralized in `src/web/routes/__init__.py`, where each domain router is imported and mounted with a prefix and tag.

## Reliability-Oriented Implementation Conventions

**Network and Retry Logic:**
- Reuse `HTTPClient` and `RequestConfig` from `src/core/http_client.py` for HTTP integrations. The client centralizes proxy handling, request retries, and `HTTPClientError` generation.
- Generic retry/backoff helpers also exist in `src/core/utils.py` as `retry_with_backoff` and `RetryDecorator`. Prefer these patterns over open-coded retry loops when extending reusable utilities.

**State and Task Orchestration:**
- Long-running registration work is pushed off the event loop through `run_in_executor(...)` in `src/web/routes/registration.py`, while `src/web/task_manager.py` manages thread-safe logs, task state, cancellation flags, and websocket fan-out.
- WebSocket reliability uses heartbeats, unsent-log replay indexes, and explicit unregister cleanup in `src/web/routes/websocket.py` and `src/web/task_manager.py`. The browser side keeps reconnect state in `static/js/app.js`.

**Startup Safety:**
- Application startup ensures directories and DB state exist before serving requests. This pattern lives in `webui.py`, `src/web/app.py`, and `src/database/session.py`.
- SQLite schema drift is handled with additive startup migration logic in `DatabaseSessionManager.migrate_tables()` in `src/database/session.py`.

**User-Facing Cache/Secret Hygiene:**
- Static assets are cache-busted through `_build_static_asset_version()` in `src/web/app.py`, and templates consume `{{ static_version }}` in `templates/index.html` and `templates/email_services.html`.
- Secret-bearing configs are hidden in API responses through helpers in `src/web/routes/email.py` and model serializers in `src/database/models.py`.

---

*Convention analysis: 2026-03-23*
