"""Cloud operator boundary: no automatic provider checks or messaging worker."""

import httpx
import pytest
from fastapi.testclient import TestClient

from adapters.photon.worker import PhotonWorker
from apps.api.reeftrace_api import cloud
from apps.api.reeftrace_api.services.photon_readonly import PhotonReadOnlyVerifier

TOKEN = "PHOTON-READONLY-TEST-OPERATOR-1234567890"
AUTH = {"Authorization": "Bearer " + TOKEN}


@pytest.fixture
def app(tmp_path, monkeypatch):
    for name in cloud._FORCED_ENV:
        monkeypatch.setenv(name, "UNTRUSTED-INITIAL-CONFIGURATION")
    monkeypatch.setenv("REEFTRACE_DATA_DIR", str(tmp_path / "cloud-store"))
    monkeypatch.setenv("REEFTRACE_LOCAL_TOKEN", TOKEN)
    monkeypatch.setenv("CHALK_ENABLED", "false")
    monkeypatch.setenv("PHOTON_READONLY_API_KEY", "private-test-read-key")
    monkeypatch.setenv("PHOTON_READONLY_PROJECT_ID", "private-test-project")
    monkeypatch.delenv("REEFTRACE_CLOUD_SEED_DIR", raising=False)

    def forbidden(*args, **kwargs):
        raise AssertionError("Cloud connection check attempted automatic HTTP or a worker")

    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    monkeypatch.setattr(PhotonWorker, "__init__", forbidden)
    return cloud.create_cloud_app()


@pytest.mark.parametrize("provider_status", ["VERIFIED", "AUTH_FAILED", "TIMEOUT", "COOLDOWN"])
def test_operator_click_is_required_and_normal_status_never_verifies_or_starts_worker(
        app, monkeypatch, provider_status):
    attempts = []

    async def verify(self):
        attempts.append(True)
        assert self._api_key == "private-test-read-key"
        assert self._project_id == "private-test-project"
        return {"status": provider_status, "checked_at": "2026-10-17T00:00:00+00:00",
                "scope": "project_authentication_only", "replies_enabled": False}

    monkeypatch.setattr(PhotonReadOnlyVerifier, "verify", verify)
    with TestClient(app) as client:
        for _ in range(2):
            status = client.get("/api/v1/status").json()
            assert status["photon"]["enabled"] is False
            assert status["photon"]["worker_running"] is False
        assert client.get("/api/v1/health").status_code == 200
        path = "/api/v1/integrations/photon/verify"
        for headers in ({}, {"Authorization": "Bearer wrong"}):
            response = client.post(path, headers=headers)
            assert response.status_code == 401
            assert response.headers["cache-control"] == "no-store"
        assert attempts == []
        response = client.post(path, headers=AUTH, json={})
        assert response.status_code == 200  # Upstream auth failure is not local operator failure.
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["status"] == provider_status
        assert response.json()["replies_enabled"] is False
        assert attempts == [True]
        for secret in (TOKEN, "private-test-read-key", "private-test-project"):
            assert secret not in response.text
        runtime = app.state.runtime
        assert not runtime.photon_settings().enabled and not runtime.photon_settings().api_key
        assert runtime.photon_worker is runtime.photon_task is None
        with runtime.store.connection() as db:
            for table in ("records", "inbox", "outbox", "cases", "actions"):
                assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
