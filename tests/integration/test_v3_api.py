from fastapi.testclient import TestClient

from apps.api.reeftrace_api.main import app
from apps.core.reeftrace_core.service import get_store


def test_local_auth_cases_and_no_truth(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("REEFTRACE_DB_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("REEFTRACE_LOCAL_TOKEN", "x" * 32)
    get_store.cache_clear()
    with TestClient(app) as client:
        assert client.get("/v1/cases").status_code == 401
        headers = {"Authorization": "Bearer " + "x" * 32}
        assert client.get("/v1/cases", headers=headers).json() == []
        assert client.get("/v1/system", headers=headers).json()["hardware_enabled"] is False
        assert (
            client.post(
                "/v1/actions/propose",
                json={"case_id": "x", "evidence_id": "y", "mode": "water_sample"},
                headers=headers,
            ).status_code
            == 422
        )
        assert client.get("/v1/cases/missing", headers=headers).status_code == 404
    get_store.cache_clear()
