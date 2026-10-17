"""Local login verification never runs an experiment, provider or hardware action."""

import pytest
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app

TOKEN = "operator-session-test-only"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("CHALK_ENABLED", "false")
    monkeypatch.setenv("PHOTON_ENABLED", "false")
    monkeypatch.setenv("GROK_VOICE_ENABLED", "false")
    return create_app(Settings(data_dir=tmp_path, local_token=TOKEN))


def test_valid_operator_session_verifies_without_data_provider_or_hardware_access(app, monkeypatch):
    runtime = app.state.runtime

    def forbidden(*args, **kwargs):
        pytest.fail("Verifying a local token must not access experiments, providers or hardware")

    # The authentication check needs no records, camera state or provider settings.
    # Do not enter the application's lifespan: that independently owns the worker.
    monkeypatch.setattr(runtime.store, "connection", forbidden)
    monkeypatch.setattr(runtime.camera, "start", forbidden)
    monkeypatch.setattr(runtime.camera, "stop", forbidden)
    monkeypatch.setattr(runtime.camera, "status", forbidden)
    monkeypatch.setattr(runtime, "chalk_settings", forbidden)
    monkeypatch.setattr(runtime, "photon_settings", forbidden)
    monkeypatch.setattr(runtime, "grok_settings", forbidden)
    client = TestClient(app, raise_server_exceptions=True)
    try:
        response = client.get("/api/v1/operator/session",
                              headers={"Authorization": f"Bearer {TOKEN}"})
    finally:
        client.close()
    assert response.status_code == 200
    assert response.json() == {"authenticated": True, "scope": "local_operator"}
    assert response.headers["cache-control"] == "no-store"
    assert TOKEN not in response.text
    assert runtime.photon_worker is None
    assert runtime.camera.session_id is None


@pytest.mark.parametrize("authorization", [
    None, "", "Bearer wrong-token", TOKEN, "Basic ignored",
    pytest.param(b"Bearer invalid-\xff\xe9", id="non_ascii_invalid_bytes"),
])
def test_operator_session_rejects_missing_or_invalid_credentials(app, authorization):
    headers = {} if authorization is None else {"Authorization": authorization}
    response = TestClient(app).get("/api/v1/operator/session", headers=headers)
    assert response.status_code == 401
    assert response.json() == {"detail": "Operator token required"}
    assert response.headers["cache-control"] == "no-store"
    assert TOKEN not in response.text
    assert app.state.runtime.store.cases() == []


def test_unconfigured_operator_session_cannot_authenticate(tmp_path):
    app = create_app(Settings(data_dir=tmp_path, local_token=""))
    response = TestClient(app).get("/api/v1/operator/session",
                                   headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Set REEFTRACE_LOCAL_TOKEN before changing local state"
    }
    assert response.headers["cache-control"] == "no-store"
    assert TOKEN not in response.text
    assert app.state.runtime.store.cases() == []
