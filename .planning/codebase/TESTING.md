# Testing Patterns

**Analysis Date:** 2026-03-23

## Test Framework

**Runner:**
- `pytest>=7.0.0` is declared in the optional `dev` extra in `pyproject.toml`.
- Config file: Not detected. There is no `pytest.ini`, `tox.ini`, `setup.cfg`, or `[tool.pytest.*]` section in `pyproject.toml`.

**Assertion Library:**
- Plain `pytest` assertions with built-in `assert` statements.
- `monkeypatch` is the only pytest fixture used in the current test suite.

**Setup Notes:**
- Test dependencies are not in `requirements.txt`; they live in the optional `dev` extra in `pyproject.toml`.
- CI workflows in `.github/workflows/build.yml` and `.github/workflows/docker-publish.yml` do not install `pytest` or execute the test suite.

**Run Commands:**
```bash
pip install .[dev]                 # Or install pytest/httpx explicitly
python -m pytest                   # Run all tests
python -m pytest tests/test_registration_engine.py -q
```

## Test File Organization

**Location:**
- Tests live in a top-level `tests/` directory, not next to source files.
- Current suite:
  - `tests/test_registration_engine.py`
  - `tests/test_duck_mail_service.py`
  - `tests/test_email_service_duckmail_routes.py`
  - `tests/test_cpa_upload.py`
  - `tests/test_static_asset_versioning.py`

**Naming:**
- Files use `test_*.py`.
- Test functions use explicit behavior names such as `test_run_registers_then_relogs_to_fetch_token` and `test_upload_to_cpa_falls_back_to_raw_json_when_multipart_returns_404`.

**Structure:**
```text
tests/
├── test_registration_engine.py
├── test_duck_mail_service.py
├── test_email_service_duckmail_routes.py
├── test_cpa_upload.py
└── test_static_asset_versioning.py
```
- No `conftest.py`, no shared fixtures module, no test factories package, and no markers file are present.
- Each file is self-contained and defines its own fake clients, fake responses, and helper objects.

## Test Structure

**Suite Organization:**
```python
class QueueSession:
    def __init__(self, steps):
        self.steps = list(steps)
        self.calls = []

    def _request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, "kwargs": kwargs})
        expected_method, expected_url, response = self.steps.pop(0)
        assert method == expected_method
        assert url == expected_url
        return response


def test_run_registers_then_relogs_to_fetch_token():
    session_one = QueueSession([...])
    engine = RegistrationEngine(email_service)
    engine.http_client = FakeOpenAIClient([session_one, session_two], ["sentinel-1", "sentinel-2"])
    result = engine.run()
    assert result.success is True
```
- This pattern comes directly from `tests/test_registration_engine.py`.

**Patterns:**
- Build handwritten fake classes inside the test module instead of importing reusable mocks. Examples: `DummyResponse`, `QueueSession`, `FakeOAuthManager`, and `FakeOpenAIClient` in `tests/test_registration_engine.py`; `FakeHTTPClient` in `tests/test_duck_mail_service.py`; `FakeMime` in `tests/test_cpa_upload.py`.
- Assert both end results and outbound request details. Tests usually inspect captured calls and payloads, not just return values.
- Keep tests focused on one path each. The current suite favors narrow, behavior-specific tests over broad parameterized matrices.

## Mocking

**Framework:**
- `pytest` `monkeypatch` plus direct attribute reassignment on instances.
- No `unittest.mock`, no `responses`, no `respx`, and no `httpx.AsyncClient` usage are detected.

**Patterns:**
```python
monkeypatch.setattr(cpa_upload, "CurlMime", FakeMime)
monkeypatch.setattr(cpa_upload.cffi_requests, "post", fake_post)
```
- This comes from `tests/test_cpa_upload.py`.

```python
monkeypatch.setattr(registration_routes, "get_db", fake_get_db)
monkeypatch.setattr(settings_module, "get_settings", lambda: DummySettings())
result = asyncio.run(registration_routes.get_available_email_services())
```
- This comes from `tests/test_email_service_duckmail_routes.py`.

**What to Mock:**
- External network boundaries in `src/core/http_client.py`, `src/core/upload/cpa_upload.py`, and `src/services/duck_mail.py`.
- Factory registration and module-level dependency lookups such as `get_db` and `get_settings` when route functions are invoked directly.
- Low-level library entry points like `cpa_upload.cffi_requests.post` and `cpa_upload.CurlMime` rather than entire subsystems.

**What NOT to Mock:**
- Result serialization and payload construction. Existing tests prefer to inspect generated request bodies, URLs, and response shaping directly.
- Public route/helper functions themselves. Tests call functions such as `email_routes.get_service_types()` and `registration_routes.get_available_email_services()` directly.

## Fixtures and Factories

**Test Data:**
```python
service = DuckMailService({
    "base_url": "https://api.duckmail.test",
    "default_domain": "duckmail.sbs",
    "api_key": "dk_test_key",
    "password_length": 10,
})
service.http_client = fake_client
email_info = service.create_email()
assert email_info["email"] == "tester@duckmail.sbs"
```
- This pattern comes from `tests/test_duck_mail_service.py`.

**Location:**
- Fake objects live inside each test file.
- Temporary database state is created inline inside `tests/test_email_service_duckmail_routes.py` using `DatabaseSessionManager`, `Base.metadata.create_all(...)`, and a local `tests_runtime/duckmail_routes.db` file.
- There are no reusable fixture modules or factory helpers.

## Coverage

**Requirements:**
- None enforced.
- No coverage plugin, no threshold config, and no reporting step are configured in `pyproject.toml` or `.github/workflows/*.yml`.

**View Coverage:**
```bash
# Not configured in the repository
# Add pytest-cov manually before using coverage commands
```

## Test Types

**Unit Tests:**
- `tests/test_duck_mail_service.py` unit-tests `src/services/duck_mail.py` by replacing its HTTP client and asserting request composition plus OTP extraction.
- `tests/test_cpa_upload.py` unit-tests URL normalization and fallback behavior in `src/core/upload/cpa_upload.py` by monkeypatching `cffi_requests` and `CurlMime`.
- `tests/test_static_asset_versioning.py` unit-tests `_build_static_asset_version()` in `src/web/app.py` and verifies versioned asset references in `templates/index.html` and `templates/email_services.html`.

**Integration Tests:**
- `tests/test_registration_engine.py` is a logic-heavy orchestration test around `src/core/register.py` and `src/core/http_client.py`. It uses faked sessions and OAuth managers rather than real HTTP.
- `tests/test_email_service_duckmail_routes.py` is the closest thing to an integration test. It wires a temporary SQLite database, patches `get_db`, then calls async route functions in `src/web/routes/email.py` and `src/web/routes/registration.py` directly.

**E2E Tests:**
- Not used.
- No browser tests, no FastAPI `TestClient`, no Playwright suite, and no Docker smoke tests are present.

## CI Hooks

**GitHub Actions:**
- `.github/workflows/build.yml` builds release binaries with `pyinstaller` but does not run tests before publishing artifacts.
- `.github/workflows/docker-publish.yml` builds and optionally pushes the Docker image on push/PR, but it also does not run tests.

**Pre-Commit / Local Hooks:**
- Not detected. There is no `.pre-commit-config.yaml` or other hook runner config.

## Common Patterns

**Async Testing:**
```python
result = asyncio.run(email_routes.get_service_types())
result = asyncio.run(registration_routes.get_available_email_services())
```
- Async route handlers are called directly from tests rather than through an ASGI client.

**Database Testing:**
```python
manager = DatabaseSessionManager(f"sqlite:///{db_path}")
Base.metadata.create_all(bind=manager.engine)

@contextmanager
def fake_get_db():
    session = manager.SessionLocal()
    try:
        yield session
    finally:
        session.close()
```
- This is the current pattern for database-backed route tests in `tests/test_email_service_duckmail_routes.py`.

**Error/Fallback Testing:**
```python
responses = [
    FakeResponse(status_code=404, text="404 page not found"),
    FakeResponse(status_code=200, payload={"status": "ok"}),
]
success, message = cpa_upload.upload_to_cpa(...)
assert success is True
```
- Tests prefer asserting fallback behavior and recovery paths, not only happy paths. The best example is `tests/test_cpa_upload.py`.

## Coverage Gaps Inferred

**Untested Areas:**
- `src/web/routes/accounts.py`, `src/web/routes/settings.py`, `src/web/routes/payment.py`, and `src/web/routes/websocket.py` have no direct tests.
- `src/web/task_manager.py` has no test coverage around websocket replay indexes, cancellation flags, or thread-safety behavior.
- `src/config/settings.py` has no direct tests for DB serialization, `SecretStr` handling, or database URL normalization.
- Most Outlook-specific logic under `src/services/outlook/` and `src/services/outlook_legacy_mail.py` is untested.
- `src/core/openai/token_refresh.py`, `src/core/openai/payment.py`, and `src/core/dynamic_proxy.py` have no direct tests.
- Browser scripts in `static/js/*.js` have no automated test coverage. Template checks in `tests/test_static_asset_versioning.py` cover only static asset version placeholders, not runtime UI behavior.

**Risk:**
- Large orchestration modules and UI-facing flows can regress without automated detection, especially websocket delivery, token refresh, payment-link flows, settings persistence, and Outlook provider failover.

**Priority:**
- High for `src/web/routes/accounts.py`, `src/web/routes/settings.py`, `src/web/task_manager.py`, `src/config/settings.py`, and the Outlook service stack.
- Medium for `src/core/openai/token_refresh.py`, `src/core/openai/payment.py`, and front-end scripts under `static/js/`.

---

*Testing analysis: 2026-03-23*
