from fastapi.testclient import TestClient

from apps.api.reeftrace_api.main import app
from apps.core.reeftrace_core.service import get_store


def test_registry_auth_and_read_only_external_records(tmp_path, monkeypatch):
    monkeypatch.setenv("REEFTRACE_LOCAL_TOKEN", "dataset-test-token-32-characters-long")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("REEFTRACE_DB_PATH", str(tmp_path / "store.db"))
    get_store.cache_clear()
    with TestClient(app) as client:
        assert client.get("/v1/datasets").status_code == 401
        headers = {"Authorization": "Bearer dataset-test-token-32-characters-long"}
        response = client.get("/v1/datasets", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["catalog"]) == 3
        assert response.json()["imports"] == []
        assert client.get("/v1/datasets/imports/missing", headers=headers).status_code == 404
    get_store.cache_clear()
