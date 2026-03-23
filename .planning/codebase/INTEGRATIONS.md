# External Integrations

**Analysis Date:** 2026-03-23

## APIs & External Services

**OpenAI account and identity surface:**
- OpenAI OAuth and account endpoints drive registration, login continuation, OTP validation, workspace selection, and token exchange from `src/config/constants.py`, `src/core/register.py`, and `src/core/openai/oauth.py`.
- Built-in domains are `https://auth.openai.com`, `https://chatgpt.com`, and `https://sentinel.openai.com` via `src/config/constants.py`, `src/core/http_client.py`, `src/core/openai/token_refresh.py`, and `src/core/openai/payment.py`.
- SDK/Client: custom `curl_cffi` wrappers in `src/core/http_client.py` plus direct `curl_cffi.requests` calls in `src/core/openai/*.py` and `src/core/register.py`.
- Auth: DB-backed `openai.client_id`, `openai.auth_url`, `openai.token_url`, `openai.redirect_uri`, and `openai.scope` settings from `src/config/settings.py`; per-account `access_token`, `refresh_token`, `id_token`, `session_token`, and `cookies` stored in `src/database/models.py`.

**Microsoft and Outlook mailbox access:**
- Outlook service supports password IMAP, Microsoft OAuth token refresh, and Graph mailbox polling in `src/services/outlook/service.py`, `src/services/outlook/token_manager.py`, `src/services/outlook/providers/imap_old.py`, `src/services/outlook/providers/imap_new.py`, and `src/services/outlook/providers/graph_api.py`.
- Built-in domains are `https://login.live.com`, `https://login.microsoftonline.com`, `https://graph.microsoft.com`, `outlook.office365.com`, and `outlook.live.com` via `src/config/constants.py` and `src/services/outlook/base.py`.
- SDK/Client: `curl_cffi` for token and Graph calls, `imaplib` for IMAP providers.
- Auth: per-service `email`, `password`, `client_id`, and `refresh_token` stored in `email_services.config` from `src/database/models.py`; fallback `outlook_default_client_id` comes from `src/config/settings.py`.

**Email providers:**
- `Tempmail.lol` uses `https://api.tempmail.lol/v2` and mailbox tokens returned by the provider in `src/services/tempmail.py` and `src/config/settings.py`.
- Self-hosted Temp-Mail worker uses `base_url`, `admin_password`, and `domain` against `/admin/*` and `/user_api/*` endpoints in `src/services/temp_mail.py`; auth is sent through `x-admin-auth`.
- MoeMail/custom-domain mail uses `base_url`, `api_key`, and a configurable header name against `/api/config` and `/api/emails/*` in `src/services/moe_mail.py`.
- DuckMail uses `base_url`, `default_domain`, optional `api_key`, and bearer mailbox tokens against `/accounts`, `/token`, `/messages`, and `/domains` in `src/services/duck_mail.py`.
- Freemail uses a self-hosted Cloudflare Worker plus `Authorization: Bearer <admin_token>` against `/api/domains`, `/api/create`, `/api/generate`, `/api/emails`, and related endpoints in `src/services/freemail.py`.
- IMAP mailboxes use direct host/port/login config in `src/services/imap_mail.py` and deliberately bypass proxy support because they rely on `imaplib`.
- Email services are user-configured through `src/web/routes/email.py` and persisted in the `email_services` table from `src/database/models.py`.

**Upload destinations:**
- CPA upload sends auth JSON files to a management endpoint derived from the configured base URL in `src/core/upload/cpa_upload.py` and `src/web/routes/upload/cpa_services.py`.
- SDK/Client: `curl_cffi` with multipart or raw JSON fallback in `src/core/upload/cpa_upload.py`.
- Auth: `Authorization: Bearer <api_token>`; service definitions are stored in the `cpa_services` table from `src/database/models.py`.
- Sub2API upload sends account batches to `/api/v1/admin/accounts/data` from `src/core/upload/sub2api_upload.py` and `src/web/routes/upload/sub2api_services.py`.
- Auth: `x-api-key`; service definitions are stored in the `sub2api_services` table from `src/database/models.py`.
- Team Manager upload sends single or batch imports to `/admin/teams/import` from `src/core/upload/team_manager_upload.py` and `src/web/routes/upload/tm_services.py`.
- Auth: `X-API-Key`; service definitions are stored in the `tm_services` table from `src/database/models.py`.

**Network utility endpoints:**
- Proxy and egress tests hit `https://api.ipify.org?format=json`, `https://httpbin.org/ip`, and `https://cloudflare.com/cdn-cgi/trace` in `src/web/routes/settings.py` and `src/core/http_client.py`.
- Registration and account operations can use DB proxy inventory, dynamic proxy APIs, or static proxy settings via `src/web/routes/accounts.py`, `src/core/dynamic_proxy.py`, and `src/config/settings.py`.

## Data Storage

**Databases:**
- SQLite is the default local database at `data/database.db`, resolved by `src/database/session.py` and `src/config/settings.py`.
- PostgreSQL is supported when `APP_DATABASE_URL` or `DATABASE_URL` is a `postgres://` or `postgresql://` URL; the app normalizes it to `postgresql+psycopg://` in `src/database/session.py` and `src/config/settings.py`.
- Client: SQLAlchemy ORM and session management in `src/database/models.py` and `src/database/session.py`.
- Stored integration state includes runtime settings in `settings`, managed OpenAI accounts and tokens in `accounts`, email service definitions in `email_services`, upload destination definitions in `cpa_services`, `sub2api_services`, and `tm_services`, and proxy inventory in `proxies` from `src/database/models.py`.

**File Storage:**
- Local filesystem only. `webui.py` creates and uses `data/` and `logs/` at runtime.
- Templates and static assets are bundled into PyInstaller builds through `codex_register.spec`.
- Export endpoints stream JSON, CSV, and ZIP from memory in `src/web/routes/accounts.py`; no object storage integration is present.

**Caching:**
- None external. No Redis, Memcached, or shared cache dependency was detected.
- In-process caches only: mailbox caches in `src/services/tempmail.py`, `src/services/temp_mail.py`, `src/services/duck_mail.py`, `src/services/moe_mail.py`, and `src/services/freemail.py`; Outlook token cache in `src/services/outlook/token_manager.py`.

## Authentication & Identity

**Auth Provider:**
- Web UI access is a custom password gate in `src/web/app.py`; it stores an HMAC-derived `webui_auth` cookie using `webui_secret_key` and `webui_access_password` from `src/config/settings.py`.
- Managed account identity comes from OpenAI OAuth, ChatGPT session tokens, and account cookies in `src/core/openai/oauth.py`, `src/core/openai/token_refresh.py`, `src/core/openai/payment.py`, and `src/core/register.py`.
- Outlook mailbox identity is either password-based IMAP or OAuth refresh-token based depending on provider and service config in `src/services/outlook/service.py`.

## Monitoring & Observability

**Error Tracking:**
- None detected. No Sentry, OpenTelemetry, Prometheus, or third-party APM package is declared in `pyproject.toml` or referenced from `src/**`.

**Logs:**
- Standard Python logging is configured by `src/core/utils.py` and initialized from `webui.py`.
- Log file location is DB-configurable through `log.file`; the default path is `logs/app.log` in `src/config/settings.py`.
- Live task logs and task status updates are pushed to browsers over WebSocket endpoints in `src/web/routes/websocket.py`, with connection state managed by `src/web/task_manager.py`.

## CI/CD & Deployment

**Hosting:**
- Local process or PyInstaller binary from `webui.py` and `codex_register.spec`.
- Docker container from `Dockerfile` and `docker-compose.yml`.
- GitHub Container Registry image publication to `ghcr.io/<owner>/<repo>` in `.github/workflows/docker-publish.yml`.

**CI Pipeline:**
- `.github/workflows/build.yml` builds Windows, Linux, and macOS binaries on tag pushes and creates GitHub releases.
- `.github/workflows/docker-publish.yml` builds and optionally pushes container images on `main`/`master`, pull requests, and semantic version tags.
- Not detected: Terraform, Helm, Kubernetes manifests, or a separate deployment orchestrator.

## Environment Configuration

**Required env vars:**
- None are strictly required for a default local boot because `src/config/settings.py` and `src/database/session.py` supply defaults.
- Use `APP_DATABASE_URL` or `DATABASE_URL` to switch from SQLite to PostgreSQL in `src/database/session.py` and `src/config/settings.py`.
- Use `WEBUI_HOST`, `WEBUI_PORT`, `WEBUI_ACCESS_PASSWORD`, `DEBUG`, and `LOG_LEVEL` in `webui.py` for startup overrides.
- Use `APP_HOST`, `APP_PORT`, and `APP_ACCESS_PASSWORD` in `src/config/settings.py` to override DB-backed listener settings.
- `APP_DATA_DIR` and `APP_LOGS_DIR` are runtime path hints set by `webui.py` for packaged or container deployments.
- Important DB-stored integration keys live under `openai.*`, `proxy.*`, `tempmail.*`, `tm.*`, `cpa.*`, `outlook.*`, and `email_code.*` in `src/config/settings.py`.

**Secrets location:**
- Bootstrap secrets may be loaded from an optional `.env` file by `webui.py`; treat that file as local-only configuration.
- Long-lived app secrets and integration credentials live in the database: `settings.value`, `email_services.config`, `cpa_services.api_token`, `sub2api_services.api_key`, `tm_services.api_key`, `proxies.password`, and the token/cookie fields on `accounts` in `src/database/models.py`.
- GitHub Actions uses `${{ secrets.GITHUB_TOKEN }}` in `.github/workflows/docker-publish.yml`.

## Network Behavior

**Proxy policy:**
- Registration and account-token operations can route through a selected proxy, a dynamic proxy API, or static proxy settings in that order via `src/web/routes/accounts.py` and `src/core/dynamic_proxy.py`.
- Some outbound integrations intentionally bypass the task proxy: CPA uploads in `src/core/upload/cpa_upload.py`, Sub2API uploads in `src/core/upload/sub2api_upload.py`, Team Manager uploads in `src/core/upload/team_manager_upload.py`, Temp-Mail worker calls in `src/services/temp_mail.py`, and IMAP mailbox polling in `src/services/imap_mail.py`.
- OpenAI, Tempmail.lol, MoeMail, DuckMail, Freemail, Outlook token refresh, and Graph API flows all support proxy injection through `proxy_url`-aware clients in `src/core/http_client.py`, `src/core/register.py`, `src/services/duck_mail.py`, `src/services/moe_mail.py`, `src/services/freemail.py`, and `src/services/outlook/token_manager.py`.

## Webhooks & Callbacks

**Incoming:**
- None detected as server-side webhook endpoints.
- The only callback-style URL in active config is `openai.redirect_uri` in `src/config/settings.py`, but the registration engine parses the returned OAuth URL internally in `src/core/register.py` and `src/core/openai/oauth.py`; no dedicated `/auth/callback` FastAPI route was found under `src/web/routes/*.py`.

**Outgoing:**
- None as webhook deliveries. External integrations are implemented as client-initiated HTTP requests from `src/core/*` and `src/services/*`, plus browser WebSocket sessions from `src/web/routes/websocket.py`.

---

*Integration audit: 2026-03-23*
