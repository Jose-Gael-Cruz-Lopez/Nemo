"""Real public data through FastAPI, with no model, network or camera mocks on success."""

from __future__ import annotations

import json
import math

import pytest
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.ocean.reeftrace_ocean import benchmark


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    monkeypatch.setenv("PHOTON_ENABLED", "false")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "[]")
    # Realistic secrets present in the server environment must never enter a
    # public scientific report. Live transports remain explicitly disabled.
    monkeypatch.setenv("GEMINI_API_KEY", "SECRET-GEMINI-REAL-DATA-TEST")
    monkeypatch.setenv("PHOTON_API_KEY", "SECRET-PHOTON-REAL-DATA-TEST")
    return create_app(Settings(data_dir=tmp_path, local_token="SECRET-LOCAL-OPERATOR"))


def _assert_finite_json(value):
    if isinstance(value, dict):
        for item in value.values():
            _assert_finite_json(item)
    elif isinstance(value, list):
        for item in value:
            _assert_finite_json(item)
    elif isinstance(value, float):
        assert math.isfinite(value)


def test_real_data_public_read_is_complete_finite_and_keeps_operator_auth(app, tmp_path):
    with TestClient(app) as client:
        before = client.get("/api/v1/status").json()
        response = client.get("/api/v1/research/real-data")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        report = response.json()
        assert report["data_origin"] == "REAL_HISTORICAL_NOAA_DRIFTER"
        assert report["provenance"]["integrity_verified"] is True
        assert report["provenance"]["sha256"] == benchmark.SAMPLE_SHA256
        assert report["provenance"]["row_count"] == 24
        assert report["provenance"]["source_url"].startswith("https://erddap.aoml.noaa.gov/")
        assert report["provenance"]["license"] == "CC-BY-4.0"
        assert len(report["training_track"]) == 18
        assert len(report["heldout_track"]) == 6
        assert report["source_attribution"]["status"] == "NOT_SUPPORTED_BY_THIS_DATASET"
        assert [model["id"] for model in report["models"]] == [
            "stationary",
            "last_drift",
            "ridge_ar1",
        ]
        assert all(len(model["predictions"]) == 6 for model in report["models"])
        _assert_finite_json(report)
        json.dumps(report, allow_nan=False)
        assert "SECRET-" not in response.text
        assert str(tmp_path) not in response.text
        assert str(benchmark.ROOT) not in response.text
        assert client.get("/api/v1/cases").json() == []
        assert client.get("/api/v1/profiles").json() == []
        assert app.state.runtime.store.list("estimate") == []
        assert client.get("/api/v1/status").json() == before
        # A public safe read does not relax mutation authentication.
        assert client.post("/api/v1/demo/load").status_code == 401
        assert (
            client.get(
                "/api/v1/research/real-data", headers={"Authorization": "Bearer wrong"}
            ).status_code
            == 200
        )


def test_real_data_repeated_requests_are_identical_and_never_create_tank_cases(app):
    with TestClient(app) as client:
        first = client.get("/api/v1/research/real-data")
        second = client.get("/api/v1/research/real-data")
        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()
        assert first.content == second.content
        assert app.state.runtime.store.cases() == []
        assert app.state.runtime.store.list("estimate") == []


@pytest.mark.parametrize("error", [FileNotFoundError, PermissionError])
def test_real_data_missing_or_unreadable_local_dataset_is_safe_503(app, monkeypatch, error):
    def unavailable():
        raise error("SECRET-PATH /private/noaa.csv")

    monkeypatch.setattr(benchmark, "run_real_data_example", unavailable)
    with TestClient(app) as client:
        response = client.get("/api/v1/research/real-data")
        assert response.status_code == 503
        assert response.json() == {"detail": "The pinned public dataset is unavailable locally"}
        assert "SECRET" not in response.text
        assert app.state.runtime.store.cases() == []


def test_real_data_corrupt_hash_is_409_and_cannot_publish_plausible_fake_result(app, monkeypatch):
    def corrupt():
        raise ValueError("Public NOAA sample hash does not match pinned provenance")

    monkeypatch.setattr(benchmark, "run_real_data_example", corrupt)
    with TestClient(app) as client:
        response = client.get("/api/v1/research/real-data")
        assert response.status_code == 409
        assert response.json() == {
            "detail": "Public NOAA sample hash does not match pinned provenance"
        }
        assert "models" not in response.json()
        assert app.state.runtime.store.cases() == []
