from src.core.upload import cpa_upload


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json payload")
        return self._payload


class FakeMime:
    def __init__(self):
        self.parts = []

    def addpart(self, **kwargs):
        self.parts.append(kwargs)


def test_upload_to_cpa_accepts_management_root_url(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, "kwargs": kwargs})
        return FakeResponse(status_code=201)

    monkeypatch.setattr(cpa_upload, "CurlMime", FakeMime)
    monkeypatch.setattr(cpa_upload.cffi_requests, "post", fake_post)

    success, message = cpa_upload.upload_to_cpa(
        {"email": "tester@example.com"},
        api_url="https://cpa.example.com/v0/management",
        api_token="token-123",
    )

    assert success is True
    assert message == "上传成功"
    assert calls[0]["url"] == "https://cpa.example.com/v0/management/auth-files"


def test_upload_to_cpa_does_not_double_append_full_endpoint(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, "kwargs": kwargs})
        return FakeResponse(status_code=201)

    monkeypatch.setattr(cpa_upload, "CurlMime", FakeMime)
    monkeypatch.setattr(cpa_upload.cffi_requests, "post", fake_post)

    success, _ = cpa_upload.upload_to_cpa(
        {"email": "tester@example.com"},
        api_url="https://cpa.example.com/v0/management/auth-files",
        api_token="token-123",
    )

    assert success is True
    assert calls[0]["url"] == "https://cpa.example.com/v0/management/auth-files"


def test_upload_to_cpa_falls_back_to_raw_json_when_multipart_returns_404(monkeypatch):
    calls = []
    responses = [
        FakeResponse(status_code=404, text="404 page not found"),
        FakeResponse(status_code=200, payload={"status": "ok"}),
    ]

    def fake_post(url, **kwargs):
        calls.append({"url": url, "kwargs": kwargs})
        return responses.pop(0)

    monkeypatch.setattr(cpa_upload, "CurlMime", FakeMime)
    monkeypatch.setattr(cpa_upload.cffi_requests, "post", fake_post)

    success, message = cpa_upload.upload_to_cpa(
        {"email": "tester@example.com", "type": "codex"},
        api_url="https://cpa.example.com",
        api_token="token-123",
    )

    assert success is True
    assert message == "上传成功"
    assert calls[0]["kwargs"]["multipart"] is not None
    assert calls[1]["url"] == "https://cpa.example.com/v0/management/auth-files?name=tester%40example.com.json"
    assert calls[1]["kwargs"]["headers"]["Content-Type"] == "application/json"
    assert calls[1]["kwargs"]["data"].startswith(b"{")


def test_test_cpa_connection_uses_get_and_normalized_url(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append({"url": url, "kwargs": kwargs})
        return FakeResponse(status_code=200, payload={"files": []})

    monkeypatch.setattr(cpa_upload.cffi_requests, "get", fake_get)

    success, message = cpa_upload.test_cpa_connection(
        "https://cpa.example.com/v0/management",
        "token-123",
    )

    assert success is True
    assert message == "CPA 连接测试成功"
    assert calls[0]["url"] == "https://cpa.example.com/v0/management/auth-files"
    assert calls[0]["kwargs"]["headers"]["Authorization"] == "Bearer token-123"


def test_list_cpa_auth_files_uses_normalized_url(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append({"url": url, "kwargs": kwargs})
        return FakeResponse(
            status_code=200,
            payload={
                "files": [
                    {"name": "alive.json", "status": "ok"},
                    {"name": "dead.json", "status_message": "401 Invalid"},
                ]
            },
        )

    monkeypatch.setattr(cpa_upload.cffi_requests, "get", fake_get)

    success, files, message = cpa_upload.list_cpa_auth_files(
        "https://cpa.example.com/v0/management",
        "token-123",
    )

    assert success is True
    assert message == "获取成功"
    assert [item["name"] for item in files] == ["alive.json", "dead.json"]
    assert calls[0]["url"] == "https://cpa.example.com/v0/management/auth-files"
    assert calls[0]["kwargs"]["headers"]["Authorization"] == "Bearer token-123"


def test_filter_unauthorized_cpa_auth_files_matches_401_status():
    auth_files = [
        {"name": "alive.json", "status": "ok"},
        {"name": "dead.json", "status_message": "401 Invalid"},
        {"name": "expired.json", "message": "Unauthorized token"},
    ]

    filtered = cpa_upload.filter_unauthorized_cpa_auth_files(auth_files)

    assert [item["name"] for item in filtered] == ["dead.json", "expired.json"]


def test_delete_cpa_auth_file_uses_name_query(monkeypatch):
    calls = []

    def fake_delete(url, **kwargs):
        calls.append({"url": url, "kwargs": kwargs})
        return FakeResponse(status_code=204)

    monkeypatch.setattr(cpa_upload.cffi_requests, "delete", fake_delete)

    success, message = cpa_upload.delete_cpa_auth_file(
        "dead.json",
        "https://cpa.example.com",
        "token-123",
    )

    assert success is True
    assert message == "删除成功"
    assert calls[0]["url"] == "https://cpa.example.com/v0/management/auth-files"
    assert calls[0]["kwargs"]["params"] == {"name": "dead.json"}
    assert calls[0]["kwargs"]["headers"]["Authorization"] == "Bearer token-123"
