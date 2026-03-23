# Codebase Concerns

**Analysis Date:** 2026-03-23

## Tech Debt

**God modules and duplicated workflow logic:**
- Issue: Core behavior is concentrated in very large mixed-responsibility files such as `src/web/routes/registration.py`, `src/web/routes/accounts.py`, `src/config/settings.py`, `src/core/register.py`, `src/database/crud.py`, and `src/services/outlook_legacy_mail.py`. Outlook logic exists in both `src/services/outlook_legacy_mail.py` and the newer `src/services/outlook/` package.
- Files: `src/web/routes/registration.py`, `src/web/routes/accounts.py`, `src/config/settings.py`, `src/core/register.py`, `src/database/crud.py`, `src/services/outlook_legacy_mail.py`, `src/services/outlook/service.py`
- Impact: Small changes require edits across routing, persistence, tasking, and transport code. Bug fixes can land in one Outlook path and miss the other.
- Fix approach: Split route files by capability, move orchestration into services, and retire one Outlook implementation so only one code path owns polling and account selection.

**Manual schema migration and half-finished secret model:**
- Issue: `src/database/session.py` performs ad hoc `ALTER TABLE` migrations in application startup, while `src/config/settings.py` defines an `encryption_key` that is never used by the model or CRUD layers.
- Files: `src/database/session.py`, `src/database/init_db.py`, `src/config/settings.py`, `src/database/models.py`, `src/database/crud.py`
- Impact: Schema evolution is hard to reason about, startup becomes migration time, and the presence of `encryption_key` suggests protection that does not exist.
- Fix approach: Introduce explicit migrations with version tracking and implement real field encryption or remove the misleading security setting.

**Debug artifacts committed at repo root:**
- Issue: Large root-level files `tmp_app_core.js` and `tmp_redirectToPage.js` are present but not referenced by the Python application or workflow files.
- Files: `tmp_app_core.js`, `tmp_redirectToPage.js`
- Impact: They increase review noise, confuse ownership, and make it harder to see what is part of the shipped product.
- Fix approach: Confirm whether they are fixtures or leftover debugging artifacts, then remove them or relocate them to a documented fixtures directory.

## Known Bugs

**Account metadata updates target the wrong attribute:**
- Symptoms: `PATCH /api/accounts/{account_id}` merges request metadata into `account.metadata`, but the ORM model stores custom data in `extra_data`.
- Files: `src/web/routes/accounts.py`, `src/database/models.py`, `src/database/crud.py`
- Trigger: Send `metadata` in `AccountUpdateRequest`.
- Workaround: Update `extra_data` directly in the database or fix the route before relying on the endpoint.

**Task status WebSocket broadcasting is effectively dead code:**
- Symptoms: `TaskManager.broadcast_status` exists, but task routes only call `update_status`, which mutates an in-memory dict and does not emit per-task status events to connected clients.
- Files: `src/web/task_manager.py`, `src/web/routes/websocket.py`, `src/web/routes/registration.py`
- Trigger: Start or finish a registration task while relying on WebSocket status updates rather than polling.
- Workaround: Poll task status endpoints; do not rely on live status broadcasts until `update_status` emits events.

**Payment auto-open can report success before browser launch actually succeeds:**
- Symptoms: `open_url_incognito` starts a daemon thread and returns `True` immediately. Browser launch failures are logged inside the thread after the API has already reported success.
- Files: `src/core/openai/payment.py`, `src/web/routes/payment.py`
- Trigger: Call `/api/payment/open-incognito` or `/api/payment/generate-link` with `auto_open=true` on a host without a usable browser or Playwright setup.
- Workaround: Treat the API response as a launch attempt, not a guarantee; verify browser launch on the host.

## Security Considerations

**API and WebSocket surface is unauthenticated while exposing secrets:**
- Risk: HTML pages in `src/web/app.py` check the `webui_auth` cookie, but `/api` routers and `/api/ws/*` do not require the same guard. Any network-reachable caller can enumerate accounts, read task logs, cancel tasks, and retrieve service configs.
- Files: `src/web/app.py`, `src/web/routes/__init__.py`, `src/web/routes/accounts.py`, `src/web/routes/settings.py`, `src/web/routes/email.py`, `src/web/routes/payment.py`, `src/web/routes/websocket.py`, `src/web/routes/upload/cpa_services.py`, `src/web/routes/upload/sub2api_services.py`, `src/web/routes/upload/tm_services.py`
- Current mitigation: UI page routes redirect to `/login`; secret-bearing list responses sometimes use `has_*` flags.
- Recommendations: Add a shared auth dependency or middleware for all `/api` and WebSocket entry points, then remove or heavily restrict full-secret endpoints.

**Passwords, tokens, cookies, proxy credentials, and service keys are stored and returned in plaintext:**
- Risk: Sensitive fields are stored directly in ORM columns and returned through routes such as account list/detail/token/cookie export endpoints and `/{service_id}/full` service endpoints. Registration also logs the generated password before persisting task logs.
- Files: `src/database/models.py`, `src/database/crud.py`, `src/core/register.py`, `src/web/routes/accounts.py`, `src/web/routes/email.py`, `src/web/routes/settings.py`, `src/web/routes/upload/cpa_services.py`, `src/web/routes/upload/sub2api_services.py`, `src/web/routes/upload/tm_services.py`
- Current mitigation: `SecretStr` is used in `src/config/settings.py` for some in-memory settings, and `src/web/routes/email.py` masks some list responses.
- Recommendations: Encrypt at rest, stop logging secrets, remove passwords/cookies/tokens from default account responses, and replace `full` endpoints with one-time reveal or masked edit flows.

**Insecure defaults remain production-reachable:**
- Risk: `webui_secret_key` defaults to `your-secret-key-change-in-production`, `webui_access_password` defaults to `admin123`, and the app logs `settings.database_url` at startup.
- Files: `src/config/settings.py`, `src/web/app.py`, `webui.py`
- Current mitigation: Operators can override settings through CLI, environment, or the database.
- Recommendations: Refuse startup with default secrets outside debug mode, stop logging connection strings, and rotate any existing deployments that still use defaults.

**Command injection and remote host abuse risk in payment browser launch:**
- Risk: Windows fallback uses `subprocess.Popen(..., shell=True)` with a user-supplied URL. Because payment APIs are unauthenticated, this is reachable from the network if the server exposes `/api/payment/open-incognito`.
- Files: `src/core/openai/payment.py`, `src/web/routes/payment.py`
- Current mitigation: If Playwright is installed, the code prefers a browser API path rather than `shell=True`.
- Recommendations: Remove the shell fallback, validate and normalize URLs, and keep browser-launch features behind authenticated admin-only routes.

**Overly broad browser trust policy:**
- Risk: CORS is configured with `allow_origins=["*"]`, `allow_methods=["*"]`, `allow_headers=["*"]`, and `allow_credentials=True`.
- Files: `src/web/app.py`
- Current mitigation: None beyond whatever network perimeter the deployment provides.
- Recommendations: Restrict origins to the actual UI hostnames and disable credentialed cross-origin access unless there is a real browser client requirement.

## Performance Bottlenecks

**Registration throughput is capped by blocking polling and a fixed thread pool:**
- Problem: Registration, email polling, Outlook polling, and HTTP retries use blocking `time.sleep` loops. Those flows run inside a shared `ThreadPoolExecutor(max_workers=50)` and some providers also limit IMAP work with a semaphore of 5.
- Files: `src/web/task_manager.py`, `src/web/routes/registration.py`, `src/core/register.py`, `src/services/base.py`, `src/services/outlook/service.py`, `src/services/outlook_legacy_mail.py`
- Cause: Long-lived registration tasks hold worker threads during OTP waits and retry delays instead of yielding cooperatively.
- Improvement path: Move registration into a real job queue, replace polling loops with async or event-driven waits where possible, and isolate provider-specific concurrency limits from the global worker pool.

**Batch maintenance endpoints do synchronous network work in request handlers:**
- Problem: Batch token refresh, batch token validation, and batch subscription checks loop over selected accounts in-line.
- Files: `src/web/routes/accounts.py`, `src/web/routes/payment.py`, `src/core/openai/token_refresh.py`, `src/core/openai/payment.py`
- Cause: Routes iterate account-by-account rather than scheduling background work or bounded concurrency.
- Improvement path: Push these jobs into the same task system or a dedicated worker queue and return task IDs instead of keeping the HTTP request open.

**Large exports and log reads load full payloads into memory:**
- Problem: Account exports materialize full JSON, CSV, and ZIP payloads in memory, and `/api/settings/logs` reads the whole log file before slicing the tail.
- Files: `src/web/routes/accounts.py`, `src/web/routes/settings.py`
- Cause: The implementation uses `json.dumps`, `StringIO`, `BytesIO`, `ZipFile`, and `readlines()` on full datasets.
- Improvement path: Stream exports in chunks, paginate large selections, and tail log files without reading them entirely.

## Fragile Areas

**Task state, logs, and batch progress live only in process memory:**
- Files: `src/web/task_manager.py`, `src/web/routes/registration.py`
- Why fragile: `_task_status`, `_log_queues`, `_ws_connections`, `_batch_status`, `_batch_logs`, and `batch_tasks` are process-local globals. `cleanup_task` only clears cancellation flags, and no code path removes completed task or batch data.
- Safe modification: Keep the current API surface, but move status/log storage to Redis or the database, add TTL cleanup, and make restart behavior explicit.
- Test coverage: No tests exercise restart recovery, cleanup, or long-running task fan-out.

**Legacy Outlook code can leak raw account config to logs:**
- Files: `src/services/outlook_legacy_mail.py`, `src/services/outlook/account.py`
- Why fragile: Invalid Outlook configs are logged with full `self.config` or `account_config`, which can include passwords and refresh tokens.
- Safe modification: Sanitize config before logging and route all Outlook validation errors through a shared masking helper.
- Test coverage: No tests cover invalid-config logging paths or secret redaction for Outlook services.

**Task log persistence is chatty and tightly coupled to runtime flow:**
- Files: `src/core/register.py`, `src/database/crud.py`, `src/database/models.py`
- Why fragile: Every `_log()` call can append to the registration task record, and success/failure handling mixes orchestration, persistence, and user-visible logging.
- Safe modification: Separate runtime events from persisted audit records and batch database writes instead of committing on every log append.
- Test coverage: Current tests cover parts of registration flow, not database log persistence under load or failure.

## Scaling Limits

**Single-process, best-effort background execution:**
- Current capacity: Registration uses `ThreadPoolExecutor(max_workers=50)` and route validation caps batch concurrency at 50 and batch size at 100.
- Limit: State is lost on restart, work is not distributable across processes, and memory growth is unbounded because logs and batch records accumulate.
- Scaling path: Use an external queue and state store, then let the web process become a stateless API surface.

**SQLite-first write pattern will struggle with high log volume:**
- Current capacity: Default `database_url` is SQLite, and registration writes task logs and status updates frequently through `db.commit()`.
- Limit: Concurrent workers will contend on the same file-backed database once task volume or log volume rises.
- Scaling path: Default production deployments to PostgreSQL and reduce write frequency with buffered event persistence.

**Outlook polling is intentionally throttled:**
- Current capacity: `src/services/outlook/service.py` and `src/services/outlook_legacy_mail.py` both gate IMAP work with a semaphore of 5.
- Limit: Large Outlook batches will queue behind provider throttling even when API concurrency is raised.
- Scaling path: Treat Outlook polling as a separate worker pool with its own queue and backpressure metrics.

## Dependencies at Risk

**`curl-cffi` is a critical operational dependency:**
- Risk: Registration, proxy tests, payment checkout, token refresh, and service uploads all depend on `curl-cffi` impersonation behavior matching current upstream expectations.
- Impact: A transport or fingerprinting change can break core flows across `src/core/http_client.py`, `src/core/register.py`, `src/core/openai/payment.py`, and `src/core/openai/token_refresh.py` at once.
- Migration plan: Isolate HTTP adapters behind narrower interfaces and add smoke tests for the few endpoints that define core product viability.

**`playwright` is optional, but payment UX depends on it for the safer launch path:**
- Risk: The project marks Playwright as an optional dependency, yet payment routes use it for the non-shell browser flow.
- Impact: Hosts without Playwright fall back to weaker behavior in `src/core/openai/payment.py`, including the Windows `shell=True` path.
- Migration plan: Either make browser automation a required, verified install for payment features or remove backend browser launching entirely.

## Missing Critical Features

**No real API authorization or role separation:**
- Problem: The application has a UI login gate, but no authenticated API boundary for secrets, exports, task control, or payment actions.
- Blocks: Safe multi-user deployment, reverse-proxy exposure, and any claim that secrets are admin-only.

**No persistent background job system:**
- Problem: Long-running work, cancellation, and log streaming are all in-memory.
- Blocks: Safe restarts, horizontal scaling, queue observability, and reliable post-crash recovery.

**No CI test gate before release builds:**
- Problem: `.github/workflows/build.yml` installs dependencies and produces release artifacts, but it never runs `pytest`.
- Blocks: Trustworthy release automation and safe refactoring of the registration/task/security paths.

## Test Coverage Gaps

**Auth and secret exposure paths are untested:**
- What's not tested: API auth enforcement, WebSocket auth, token/cookie/password redaction, and secret-returning `full` endpoints.
- Files: `src/web/app.py`, `src/web/routes/accounts.py`, `src/web/routes/settings.py`, `src/web/routes/payment.py`, `src/web/routes/websocket.py`, `src/web/routes/upload/cpa_services.py`, `src/web/routes/upload/sub2api_services.py`
- Risk: Security regressions can ship unnoticed because the current suite does not exercise them.
- Priority: High

**Task manager persistence and cleanup behavior are untested:**
- What's not tested: Batch cancellation, restart loss, in-memory cleanup, WebSocket delivery semantics, and status broadcasting.
- Files: `src/web/task_manager.py`, `src/web/routes/registration.py`
- Risk: Long-running operations can leak memory or fail silently under load without automated detection.
- Priority: High

**Database migration and secret-storage behavior are untested:**
- What's not tested: Startup migrations in `src/database/session.py`, plaintext secret handling in models/CRUD, and the broken `metadata` update path.
- Files: `src/database/session.py`, `src/database/models.py`, `src/database/crud.py`, `src/web/routes/accounts.py`
- Risk: Deployment-time breakage and data-shape bugs will surface first in production databases.
- Priority: High

**Performance-sensitive export and log endpoints are untested:**
- What's not tested: Large account exports, ZIP generation, and tailing large log files.
- Files: `src/web/routes/accounts.py`, `src/web/routes/settings.py`
- Risk: Memory-heavy paths can degrade or crash the service when account volume grows.
- Priority: Medium

---

*Concerns audit: 2026-03-23*
