"""Pinned training-only research through the real API, isolated from tank state.

No provider/account, current-data request, camera or model deployment is used.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.ocean.reeftrace_ocean import benchmark, diagnostics

ENDPOINT = "/api/v1/research/training-diagnostic"
MODEL_IDS = ["stationary", "last_drift", "ridge_ar1"]


@pytest.fixture
def app(tmp_path, monkeypatch):
    for variable in ("GEMINI_ENABLED", "PHOTON_ENABLED", "GROK_VOICE_ENABLED"):
        monkeypatch.setenv(variable, "false")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "[]")
    for variable in ("GEMINI_API_KEY", "PHOTON_API_KEY", "XAI_API_KEY"):
        monkeypatch.setenv(variable, "PRIVATE-RESEARCH-TEST-KEY")
    return create_app(Settings(data_dir=tmp_path / "store", local_token="PRIVATE-OPERATOR-TEST"))


def assert_finite(value):
    if isinstance(value, dict):
        for item in value.values():
            assert_finite(item)
    elif isinstance(value, list):
        for item in value:
            assert_finite(item)
    elif isinstance(value, float):
        assert math.isfinite(value)


def assert_no_tank_state(runtime):
    assert runtime.store.cases() == []
    for kind in ("profile", "estimate", "analysis", "investigation", "voice_receipt", "recording"):
        assert runtime.store.list(kind) == []
    with runtime.store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM actions").fetchone()[0] == 0


def test_real_training_diagnostic_has_pinned_provenance_finite_models_and_no_tank_side_effects(app, tmp_path):
    runtime = app.state.runtime
    assert_no_tank_state(runtime)
    with TestClient(app) as client:
        before = client.get("/api/v1/status").json()
        response = client.get(ENDPOINT)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        report = response.json()
        assert report["kind"] == "TRAINING_ONLY_RETROSPECTIVE_DIAGNOSTIC"
        assert report["status"] == "COMPLETED"
        assert report["split"] == {
            "method": "training_only_expanding_origin_no_heldout",
            "training_count": 18, "min_prefix": 8, "horizons": 6,
            "prefix_counts": [8, 9, 10, 11, 12], "origin_count": 5,
            "step_seconds": 3600.0, "test_data_used": False,
            "model_selection_performed": False,
        }
        assert report["test_data_used"] is False
        assert report["model_selection_performed"] is False
        assert "selected_model" not in report
        assert "heldout_track" not in report
        provenance = report["provenance"]
        assert provenance["integrity_verified"] is True
        assert provenance["sha256"] == benchmark.SAMPLE_SHA256
        assert provenance["row_count"] == 24
        assert provenance["bytes"] == 1950
        assert provenance["source_url"].startswith("https://erddap.aoml.noaa.gov/")
        assert provenance["license"] == "CC-BY-4.0"
        assert report["coordinate_system"]["error"] == "spherical_great_circle_metres"
        assert report["coordinate_system"]["sphere_not_wgs84_ellipsoid"] is True
        start = datetime(1987, 10, 3, tzinfo=UTC)
        assert len(report["origins"]) == 5
        for origin, prefix_count in zip(report["origins"], range(8, 13), strict=True):
            assert origin["prefix_count"] == prefix_count
            assert origin["fit_end_utc"] == (
                start + timedelta(hours=prefix_count - 1)).isoformat().replace("+00:00", "Z")
            assert [model["id"] for model in origin["models"]] == MODEL_IDS
            for model in origin["models"]:
                assert len(model["predictions"]) == 6
                for horizon, point in enumerate(model["predictions"], 1):
                    assert point["horizon_hours"] == horizon
                    assert point["time_utc"] == (
                        start + timedelta(hours=prefix_count + horizon - 1)).isoformat().replace("+00:00", "Z")
                    assert point["time_utc"] <= "1987-10-03T17:00:00Z"
                    assert point["error_m"] >= 0
        assert_finite(report)
        json.dumps(report, allow_nan=False)
        assert "PRIVATE-" not in response.text
        assert str(tmp_path) not in response.text
        assert str(benchmark.ROOT) not in response.text
        assert client.get("/api/v1/status").json() == before
        assert before["camera"]["running"] is False
        assert before["hardware_actuation"] is False
        assert_no_tank_state(runtime)


def test_api_aggregate_metrics_reconstruct_from_the_five_training_origins(app):
    with TestClient(app) as client:
        response = client.get(ENDPOINT)
        assert response.status_code == 200
        report = response.json()
    assert [model["id"] for model in report["aggregates"]] == MODEL_IDS
    for model in report["aggregates"]:
        assert len(model["per_horizon"]) == 6
        for row in model["per_horizon"]:
            errors, baselines = [], []
            for origin in report["origins"]:
                for model_id, values in ((model["id"], errors), ("stationary", baselines)):
                    candidate = next(item for item in origin["models"] if item["id"] == model_id)
                    prediction = next(item for item in candidate["predictions"]
                                      if item["horizon_hours"] == row["horizon_hours"])
                    values.append(prediction["error_m"])
            assert row["count"] == 5
            assert row["mean_error_m"] == pytest.approx(math.fsum(errors) / 5)
            assert row["rmse_error_m"] == pytest.approx(math.sqrt(math.fsum(
                error * error for error in errors) / 5))
            assert row["max_error_m"] == max(errors)
            assert row["per_horizon_error_lower_than_stationary_count"] == sum(
                error < baseline for error, baseline in zip(errors, baselines, strict=True))


def test_diagnostic_is_public_deterministic_and_does_not_relax_mutation_auth(app):
    with TestClient(app) as client:
        first = client.get(ENDPOINT)
        second = client.get(ENDPOINT, headers={"Authorization": "Bearer wrong"})
        assert first.status_code == second.status_code == 200
        assert first.content == second.content
        assert first.json() == second.json()
        assert client.post("/api/v1/demo/load", json={}).status_code == 401
    assert_no_tank_state(app.state.runtime)


def test_api_training_diagnostic_does_not_run_the_heldout_forecast(app, monkeypatch):
    def forbidden():
        raise AssertionError("Training-only API must not run the heldout forecast experiment")

    monkeypatch.setattr(benchmark, "run_real_data_example", forbidden)
    monkeypatch.setattr(diagnostics, "run_real_data_example", forbidden, raising=False)
    with TestClient(app) as client:
        response = client.get(ENDPOINT)
        assert response.status_code == 200
        assert response.json()["test_data_used"] is False
    assert_no_tank_state(app.state.runtime)


@pytest.mark.parametrize("failure", [FileNotFoundError, PermissionError])
def test_missing_or_unreadable_training_dataset_is_a_safe_503(app, monkeypatch, failure):
    def unavailable():
        raise failure("PRIVATE-PATH /private/unavailable-source.csv")

    monkeypatch.setattr(diagnostics, "run_training_diagnostic", unavailable)
    with TestClient(app) as client:
        response = client.get(ENDPOINT)
        assert response.status_code == 503
        assert response.json() == {"detail": "The pinned training dataset is unavailable locally"}
        assert "PRIVATE" not in response.text
        assert "/private/" not in response.text
    assert_no_tank_state(app.state.runtime)


def test_actual_corrupted_training_fixture_returns_integrity_409(app, tmp_path, monkeypatch):
    fixture_folder = tmp_path / "corrupted-source/data/public"
    fixture_folder.mkdir(parents=True)
    source = benchmark.ROOT / "data/public" / benchmark.SAMPLE_NAME
    payload = source.read_bytes()
    corrupt = payload.replace(b"-0.0736", b"-0.0735", 1)
    assert corrupt != payload
    target = fixture_folder / benchmark.SAMPLE_NAME
    target.write_bytes(corrupt)
    target.with_suffix(".provenance.json").write_bytes(
        source.with_suffix(".provenance.json").read_bytes())
    monkeypatch.setattr(diagnostics, "ROOT", tmp_path / "corrupted-source")
    monkeypatch.setattr(benchmark, "ROOT", tmp_path / "corrupted-source")
    with TestClient(app) as client:
        response = client.get(ENDPOINT)
        assert response.status_code == 409
        assert "hash" in response.json()["detail"].lower()
        assert "origins" not in response.json()
        assert "aggregates" not in response.json()
    assert_no_tank_state(app.state.runtime)
