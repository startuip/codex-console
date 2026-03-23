# Codebase Structure

**Analysis Date:** 2026-03-23

## Directory Layout

```text
codex-console/
├── webui.py                 # Runtime bootstrap and CLI entry point
├── src/                     # Python application package
│   ├── config/              # Typed settings, enums, constants
│   ├── core/                # OpenAI workflow logic, HTTP helpers, uploads, proxy helper
│   ├── database/            # SQLAlchemy models, sessions, CRUD, DB init
│   ├── services/            # Email-provider adapters and Outlook subdomain
│   └── web/                 # FastAPI app, routers, task manager
├── templates/               # Jinja2 page templates
├── static/                  # CSS and page-specific browser JavaScript
├── tests/                   # Pytest regression coverage
├── .github/workflows/       # Build and publish automation
├── .planning/codebase/      # Generated codebase map documents
├── Dockerfile               # Container runtime definition
├── docker-compose.yml       # Container orchestration file present
├── build.sh                 # POSIX PyInstaller packaging helper
├── build.bat                # Windows PyInstaller packaging helper
├── codex_register.spec      # PyInstaller spec file
├── pyproject.toml           # Packaging metadata and console-script entry point
├── requirements.txt         # Pip dependency lock-style input
├── tmp_app_core.js          # Standalone temporary JS artifact at repo root
└── tmp_redirectToPage.js    # Standalone temporary JS artifact at repo root
```

## Directory Purposes

**`src/config`:**
- Purpose: Centralize typed configuration and shared enums/constants.
- Contains: `settings.py`, `constants.py`, `__init__.py`
- Key files: `src/config/settings.py`, `src/config/constants.py`
- Use this directory when you need new persisted settings, new configuration defaults, or new enums/constants referenced in multiple backend modules.

**`src/core`:**
- Purpose: Hold workflow logic that talks to OpenAI or other external systems and should not live directly in route handlers.
- Contains: `register.py`, `http_client.py`, `dynamic_proxy.py`, `openai/`, `upload/`, `utils.py`
- Key files: `src/core/register.py`, `src/core/http_client.py`, `src/core/dynamic_proxy.py`
- Put multi-step backend workflows here, not in `src/web/routes/`.

**`src/core/openai`:**
- Purpose: Group OpenAI-specific protocol helpers that are reusable outside the main registration engine.
- Contains: `oauth.py`, `payment.py`, `sentinel.py`, `token_refresh.py`
- Key files: `src/core/openai/oauth.py`, `src/core/openai/token_refresh.py`, `src/core/openai/payment.py`
- Add new OpenAI protocol or token-management helpers here if they are not tightly coupled to the main `RegistrationEngine`.

**`src/core/upload`:**
- Purpose: Own outbound account export/upload adapters.
- Contains: `cpa_upload.py`, `sub2api_upload.py`, `team_manager_upload.py`
- Key files: `src/core/upload/cpa_upload.py`, `src/core/upload/sub2api_upload.py`, `src/core/upload/team_manager_upload.py`
- Add new third-party upload targets here, then expose them through route wrappers in `src/web/routes/upload/` or `src/web/routes/accounts.py`.

**`src/database`:**
- Purpose: Define the schema and common persistence API.
- Contains: `models.py`, `session.py`, `crud.py`, `init_db.py`, `__init__.py`
- Key files: `src/database/models.py`, `src/database/session.py`, `src/database/crud.py`
- Any schema change should touch this directory first.

**`src/services`:**
- Purpose: Provide concrete email adapters behind `BaseEmailService`.
- Contains: `base.py`, provider modules like `duck_mail.py`, `freemail.py`, `imap_mail.py`, `moe_mail.py`, `temp_mail.py`, `tempmail.py`, and the Outlook package
- Key files: `src/services/base.py`, `src/services/__init__.py`, `src/services/duck_mail.py`, `src/services/imap_mail.py`
- Add new email providers here and register them in `src/services/__init__.py`.

**`src/services/outlook`:**
- Purpose: Isolate the Outlook-specific mini-subsystem.
- Contains: `service.py`, `account.py`, `token_manager.py`, `health_checker.py`, `email_parser.py`, `providers/`, `base.py`
- Key files: `src/services/outlook/service.py`, `src/services/outlook/health_checker.py`, `src/services/outlook/providers/base.py`
- Keep Outlook transport changes inside this subtree instead of expanding `src/services/outlook_legacy_mail.py`.

**`src/web`:**
- Purpose: Compose the FastAPI server and expose browser-facing endpoints.
- Contains: `app.py`, `task_manager.py`, `routes/`, `__init__.py`
- Key files: `src/web/app.py`, `src/web/task_manager.py`
- This is where new routes, page shells, and task orchestration hooks attach to the running app.

**`src/web/routes`:**
- Purpose: Split the API surface by domain.
- Contains: `accounts.py`, `email.py`, `payment.py`, `registration.py`, `settings.py`, `websocket.py`, `upload/`, `__init__.py`
- Key files: `src/web/routes/__init__.py`, `src/web/routes/registration.py`, `src/web/routes/accounts.py`
- New route modules belong here and must be included from `src/web/routes/__init__.py` to become reachable under `/api`.

**`src/web/routes/upload`:**
- Purpose: Host CRUD-style route wrappers for upload-target configuration tables.
- Contains: `cpa_services.py`, `sub2api_services.py`, `tm_services.py`
- Key files: `src/web/routes/upload/cpa_services.py`, `src/web/routes/upload/sub2api_services.py`, `src/web/routes/upload/tm_services.py`
- Follow this subdirectory pattern when a new integration has its own configuration table and admin UI.

**`templates`:**
- Purpose: Serve as HTML shells for the browser UI.
- Contains: `index.html`, `accounts.html`, `email_services.html`, `payment.html`, `settings.html`, `login.html`
- Key files: `templates/index.html`, `templates/accounts.html`, `templates/settings.html`
- Add a new HTML page here, then expose it from `src/web/app.py` and back it with a matching script in `static/js/`.

**`static`:**
- Purpose: Store browser assets loaded by the templates.
- Contains: `css/style.css`, `js/app.js`, `js/accounts.js`, `js/email_services.js`, `js/payment.js`, `js/settings.js`, `js/utils.js`
- Key files: `static/js/app.js`, `static/js/accounts.js`, `static/js/utils.js`, `static/css/style.css`
- Keep shared browser helpers in `static/js/utils.js`; keep page behavior in page-specific scripts.

**`tests`:**
- Purpose: Hold pytest-based regression coverage.
- Contains: `test_registration_engine.py`, `test_duck_mail_service.py`, `test_email_service_duckmail_routes.py`, `test_cpa_upload.py`, `test_static_asset_versioning.py`
- Key files: `tests/test_registration_engine.py`, `tests/test_static_asset_versioning.py`
- New tests should stay in this top-level directory and follow the existing `test_<feature>.py` naming pattern.

## Key File Locations

**Entry Points:**
- `webui.py`: Primary process entry point for local runs, packaged executables, and container startup.
- `src/web/app.py`: FastAPI application factory and module-level `app`.
- `static/js/app.js`: Browser controller for the registration dashboard.
- `static/js/accounts.js`: Browser controller for the account-management page.
- `static/js/settings.js`: Browser controller for settings, proxy, and integration admin.

**Configuration:**
- `pyproject.toml`: Package metadata and the `codex-console = "webui:main"` entry point.
- `src/config/settings.py`: Setting definitions, defaults, DB loading, env overrides, and the cached `Settings` model.
- `src/config/constants.py`: Shared enums and protocol constants used throughout the backend.
- `Dockerfile`: Container build and runtime command.
- `codex_register.spec`: PyInstaller bundle definition, including which project assets are shipped.
- `docker-compose.yml`: Compose file exists at the repo root; inspect carefully before editing because deployment config may live there.

**Core Logic:**
- `src/core/register.py`: Main registration and token-acquisition workflow.
- `src/core/http_client.py`: HTTP/session wrapper and OpenAI-specific client behavior.
- `src/core/openai/oauth.py`: OAuth URL generation and callback exchange.
- `src/core/openai/token_refresh.py`: Account token refresh and validation.
- `src/core/openai/payment.py`: Payment link generation and browser launch helpers.
- `src/web/task_manager.py`: Executor, task logs, cancellation, and WebSocket fan-out.

**Persistence:**
- `src/database/models.py`: Schema definitions for accounts, services, tasks, settings, proxies, and upload targets.
- `src/database/crud.py`: Shared query and write helpers for those models.
- `src/database/session.py`: Engine/session lifecycle and manual SQLite migrations.

**Testing:**
- `tests/test_registration_engine.py`: Backend registration workflow coverage.
- `tests/test_email_service_duckmail_routes.py`: Route-level email service coverage.
- `tests/test_cpa_upload.py`: Upload adapter coverage.
- `tests/test_static_asset_versioning.py`: `src/web/app.py` static-version logic coverage.

## Naming Conventions

**Files:**
- Backend Python modules use `snake_case.py`, for example `src/web/routes/registration.py` and `src/core/upload/sub2api_upload.py`.
- Route modules are domain-named after their `/api` prefixes, for example `src/web/routes/email.py` for `/api/email-services` and `src/web/routes/payment.py` for `/api/payment`.
- Templates and page scripts mirror each other by page name: `templates/accounts.html` pairs with `static/js/accounts.js`, and `templates/settings.html` pairs with `static/js/settings.js`.
- Outlook transport implementations are nested and transport-named, for example `src/services/outlook/providers/imap_old.py`.
- Tests follow `test_<subject>.py` at the top level of `tests/`.

**Directories:**
- Backend directories are broad capability buckets under `src/`: `config`, `core`, `database`, `services`, and `web`.
- Deep subdirectories are used only when a capability becomes a subdomain with multiple implementations, such as `src/core/openai/`, `src/core/upload/`, and `src/services/outlook/providers/`.
- Upload-related admin routes are the one notable nested router area under `src/web/routes/upload/`.

## Where to Add New Code

**New Feature:**
- New API domain: create `src/web/routes/<domain>.py`, expose its `router`, and include it from `src/web/routes/__init__.py`.
- New browser page: add `templates/<page>.html`, add `static/js/<page>.js`, then add the page route in `src/web/app.py`.
- New long-running workflow: put the workflow code in `src/core/` and keep the route thin in `src/web/routes/`.

**New Component/Module:**
- OpenAI registration or auth step: modify `src/core/register.py` if it is part of the existing workflow sequence.
- Reusable OpenAI helper: add it under `src/core/openai/` and call it from routes or `RegistrationEngine`.
- Email provider: add a new implementation under `src/services/`, then register it in `src/services/__init__.py`.
- Outlook transport variant: add it under `src/services/outlook/providers/` and wire it through `src/services/outlook/service.py`.
- New upload target: add protocol code in `src/core/upload/<target>_upload.py`, config routes in `src/web/routes/upload/<target>_services.py`, and admin UI pieces in `templates/settings.html` plus `static/js/settings.js`.

**Utilities:**
- Shared backend HTTP behavior: `src/core/http_client.py`
- Shared dynamic proxy behavior: `src/core/dynamic_proxy.py`
- Shared frontend helpers: `static/js/utils.js`
- Shared persistence helpers: `src/database/crud.py`

**Schema and Settings Changes:**
- Table shape: update `src/database/models.py`
- Shared CRUD access: update `src/database/crud.py`
- SQLite compatibility/migration behavior: update `src/database/session.py`
- New persisted setting or default value: update `src/config/settings.py`

## Special Directories

**`.planning/codebase`:**
- Purpose: Generated repository map consumed by later planning/execution commands.
- Generated: Yes
- Committed: Yes, when the mapping output is kept in version control

**`.github/workflows`:**
- Purpose: CI/CD definitions for builds and container publishing.
- Generated: No
- Committed: Yes

**`src/services/outlook/providers`:**
- Purpose: Strategy implementations for Outlook transports.
- Generated: No
- Committed: Yes

**`static/js`:**
- Purpose: Browser-side controllers split by page plus shared fetch/UI utilities.
- Generated: No
- Committed: Yes

**Root temp JS files:**
- Purpose: `tmp_app_core.js` and `tmp_redirectToPage.js` are standalone root-level artifacts and are not part of the `static/js/` page-asset structure.
- Generated: Unclear from repository contents
- Committed: Yes

---

*Structure analysis: 2026-03-23*
