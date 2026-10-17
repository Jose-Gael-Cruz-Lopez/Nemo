"""Actual offline vector replay through HTTP; acquisition and sponsors stay untouched."""

from __future__ import annotations

import json
import math
import shutil

import cv2
import httpx
import pytest
from fastapi.testclient import TestClient

from adapters.chalk import agent as chalk_agent
from adapters.photon.transport import PhotonTransport
from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.ocean.reeftrace_ocean import benchmark, multidrifter, vector_diagnostics

ENDPOINT = "/api/v1/research/vector-diagnostic"
COHORT_ENDPOINT = "/api/v1/research/cohort-vectors"


@pytest.fixture
def app(tmp_path, monkeypatch):
    for variable in ("CHALK_ENABLED", "PHOTON_ENABLED", "GROK_VOICE_ENABLED"):
        monkeypatch.setenv(variable, "false")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "[]")
    for variable in ("CHALK_ROUTER_API_KEY", "PHOTON_API_KEY", "XAI_API_KEY"):
        monkeypatch.setenv(variable, "PRIVATE-VECTOR-TEST-KEY")
    return create_app(Settings(data_dir=tmp_path / "store", local_token="PRIVATE-OPERATOR-TEST"))


def _state(runtime):
    with runtime.store.connection() as db:
        return tuple(db.iterdump())


def _finite(value):
    if isinstance(value, dict):
        for child in value.values():
            _finite(child)
    elif isinstance(value, list):
        for child in value:
            _finite(child)
    elif isinstance(value, float):
        assert math.isfinite(value)


def test_vector_endpoint_scores_actual_pinned_noaa_and_image_extraction(app, tmp_path):
    with TestClient(app) as client:
        before = _state(app.state.runtime)
        response = client.get(ENDPOINT)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        report = response.json()
        assert report["schema_version"] == 1
        assert report["kind"] == "MOTION_VECTOR_DIAGNOSTIC"
        assert report["status"] == "COMPLETED"
        for key in ("camera_started", "hardware_actuation", "physical_validation",
                    "provider_calls", "store_written"):
            assert report[key] is False
        noaa = report["noaa"]
        assert noaa["data_origin"] == "REAL_HISTORICAL_NOAA_DRIFTER"
        assert noaa["velocity_units"] == "m/s"
        assert noaa["provenance"]["sha256"] == benchmark.SAMPLE_SHA256
        assert noaa["provenance"]["integrity_verified"] is True
        assert noaa["coverage"] == {
            "physical_drifters": 1, "models": 3, "intervals_per_model": 6,
            "attempted_model_intervals": 18, "scored_model_intervals": 18,
            "failed_model_intervals": 0, "unique_observed_intervals": 6,
        }
        assert [model["id"] for model in noaa["models"]] == list(benchmark.MODEL_IDS)
        assert noaa["independent_evaluation"] is False
        assert noaa["model_selection_performed"] is False
        assert noaa["field_forcing_available"] is False
        assert noaa["plastic_source_attribution_supported"] is False
        for model in noaa["models"]:
            intervals = model["intervals"]
            assert len(intervals) == 6
            for index, interval in enumerate(intervals):
                assert interval["interval_seconds"] == 3600
                assert interval["horizon_hours"] == index + 1
                assert interval["status"] == "SCORED"
                if index:
                    assert interval["predicted_start"] == intervals[index - 1]["predicted_end"]
                observed, predicted = interval["observed_velocity"], interval["predicted_velocity"]
                residual = interval["residual_predicted_minus_observed"]
                for axis in ("eastward_m_s", "northward_m_s"):
                    assert residual[axis] == pytest.approx(predicted[axis] - observed[axis])
            expected = math.sqrt(math.fsum(
                row["residual_predicted_minus_observed"]["speed_m_s"] ** 2
                for row in intervals) / 6)
            assert model["metrics"]["vector_rmse_m_s"] == pytest.approx(expected)
        stationary = next(model for model in noaa["models"] if model["id"] == "stationary")
        assert stationary["metrics"]["angular_scored_count"] == 0
        assert stationary["metrics"]["angular_withheld_count"] == 6
        assert stationary["metrics"]["angular_mae_deg"] is None
        tank = report["synthetic_tank"]
        assert tank["data_origin"] == "SYNTHETIC_SOFTWARE_REPLAY"
        assert tank["physical_validation"] is False
        assert tank["coordinates"]["velocity_units"] == "cm/s"
        assert tank["coordinates"]["timestamp_kind"] == "SYNTHETIC_MONOTONIC_OFFSETS"
        assert len(tank["frames"]) == len(tank["observations"]) == 8
        assert tank["metrics"]["sample_count"] == len(tank["vectors"]) == 4
        assert tank["metrics"]["vector_rmse_cm_s"] == pytest.approx(1)
        assert tank["metrics"]["mean_speed_bias_cm_s"] == pytest.approx(-1)
        assert tank["model"]["frozen_before_scoring"] is True
        assert tank["model"]["trained"] is False
        assert tank["admission"]["measured_profile_admitted"] is False
        for artifact in tank["frames"] + tank["observations"] + tank["vectors"]:
            assert artifact["data_origin"] == "SYNTHETIC_SOFTWARE_REPLAY"
            assert artifact["physical_validation"] is False
        _finite(report)
        json.dumps(report, allow_nan=False)
        assert "PRIVATE-" not in response.text
        assert str(tmp_path) not in response.text
        assert str(benchmark.ROOT) not in response.text
        assert _state(app.state.runtime) == before


def test_endpoint_cannot_start_acquisition_write_store_or_contact_sponsors(app, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Vector diagnostic crossed a read-only side-effect boundary")

    runtime = app.state.runtime
    monkeypatch.setattr(cv2, "VideoCapture", forbidden)
    for method in ("start", "image"):
        monkeypatch.setattr(runtime.camera, method, forbidden)
    for method in ("put", "put_case_result", "add_case", "update_case", "propose", "approve"):
        if hasattr(runtime.store, method):
            monkeypatch.setattr(runtime.store, method, forbidden)
    monkeypatch.setattr(runtime, "record", forbidden)
    monkeypatch.setattr(runtime, "investigate", forbidden)
    monkeypatch.setattr(chalk_agent, "investigate", forbidden)
    monkeypatch.setattr(PhotonTransport, "send_saved", forbidden)
    monkeypatch.setattr(PhotonTransport, "list_page", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    with TestClient(app) as client:
        before = _state(runtime)
        camera = runtime.camera.status()
        response = client.get(ENDPOINT)
        assert response.status_code == 200, response.text
        assert _state(runtime) == before
        assert runtime.camera.status() == camera
        assert camera["running"] is False


def test_public_replay_deterministic_but_mutation_remains_authenticated(app):
    with TestClient(app) as client:
        before = _state(app.state.runtime)
        first = client.get(ENDPOINT)
        second = client.get(ENDPOINT, headers={"Authorization": "Bearer wrong"})
        assert first.status_code == second.status_code == 200
        assert first.content == second.content
        assert client.post("/api/v1/demo/load", json={}).status_code == 401
        assert _state(app.state.runtime) == before


def test_actual_missing_noaa_fixture_returns_503_without_partial_report(app, tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "ROOT", tmp_path / "PRIVATE-missing-vector-source")
    with TestClient(app) as client:
        before = _state(app.state.runtime)
        response = client.get(ENDPOINT)
        assert response.status_code == 503
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {"detail": "The pinned vector dataset is unavailable locally"}
        assert "PRIVATE" not in response.text and str(tmp_path) not in response.text
        assert _state(app.state.runtime) == before


def test_unreadable_source_is_safe_503(app, monkeypatch):
    def unavailable():
        raise PermissionError("PRIVATE-PATH /private/source.csv")

    monkeypatch.setattr(vector_diagnostics, "run_noaa_vector_diagnostic", unavailable)
    with TestClient(app) as client:
        before = _state(app.state.runtime)
        response = client.get(ENDPOINT)
        assert response.status_code == 503
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {"detail": "The pinned vector dataset is unavailable locally"}
        assert "PRIVATE" not in response.text
        assert _state(app.state.runtime) == before


def test_actual_corrupted_noaa_fixture_returns_409_without_success_evidence(app, tmp_path, monkeypatch):
    source = benchmark.ROOT / "data/public" / benchmark.SAMPLE_NAME
    destination = tmp_path / "corrupted-source/data/public" / benchmark.SAMPLE_NAME
    destination.parent.mkdir(parents=True)
    payload = source.read_bytes()
    changed = payload.replace(b"-0.0736", b"-0.0735", 1)
    assert changed != payload
    destination.write_bytes(changed)
    destination.with_suffix(".provenance.json").write_bytes(
        source.with_suffix(".provenance.json").read_bytes())
    monkeypatch.setattr(benchmark, "ROOT", tmp_path / "corrupted-source")
    with TestClient(app) as client:
        before = _state(app.state.runtime)
        response = client.get(ENDPOINT)
        assert response.status_code == 409
        assert response.headers["cache-control"] == "no-store"
        assert "hash" in response.json()["detail"].lower()
        assert "noaa" not in response.json() and "synthetic_tank" not in response.json()
        assert str(tmp_path) not in response.text
        assert _state(app.state.runtime) == before


def test_cohort_endpoint_returns_actual_96_vector_scores_without_mutating_local_state(app, tmp_path):
    with TestClient(app) as client:
        before = _state(app.state.runtime)
        camera = app.state.runtime.camera.status()
        response = client.get(COHORT_ENDPOINT)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        report = response.json()
        assert report["kind"] == "NOAA_COHORT_VECTOR_MOTION_DIAGNOSTIC"
        assert report["status"] == "PARTIAL_COVERAGE"
        assert report["data_origin"] == "REAL_HISTORICAL_NOAA_DRIFTERS"
        assert report["velocity_units"] == "m/s"
        assert report["provenance"]["integrity_verified"] is True
        assert report["coverage"] == {
            "target_drifters": 6, "acquired_drifters": 4, "missing_drifters": 2,
            "models": 4, "model_tracks": 16, "intervals_per_track": 6,
            "planned_model_intervals": 144, "attempted_model_intervals": 96,
            "scored_model_intervals": 96, "failed_model_intervals": 0,
            "unique_observed_intervals": 24, "common_acquired_cohort_complete": True,
        }
        assert {group["drifter_id"] for group in report["groups"]} == {
            "12730", "12731", "300234063243480", "300234063472530"}
        assert all(len(group["models"]) == 4 for group in report["groups"])
        assert sum(len(track["intervals"]) for group in report["groups"]
                   for track in group["models"]) == 96
        for key in ("field_forcing_available", "physical_alias_resolution_verified",
                    "debris_survey_context_available", "independent_evaluation",
                    "model_selection_performed", "automatic_model_promotion",
                    "physical_validation", "calibrated_probability",
                    "plastic_source_attribution_supported", "new_trajectory_acquisition"):
            assert report[key] is False
        for index, aggregate in enumerate(report["models"]):
            tracks = [group["models"][index] for group in report["groups"]]
            expected = math.sqrt(math.fsum(
                track["metrics"]["vector_rmse_m_s"] ** 2 for track in tracks) / 4)
            assert aggregate["metrics"]["vector_rmse_m_s"] == pytest.approx(expected)
        _finite(report)
        json.dumps(report, allow_nan=False)
        assert "PRIVATE-" not in response.text and str(tmp_path) not in response.text
        assert _state(app.state.runtime) == before
        assert app.state.runtime.camera.status() == camera
        assert camera["running"] is False
        # Public research is independent of operator login; it still cannot mutate.
        repeated = client.get(COHORT_ENDPOINT, headers={"Authorization": "Bearer wrong"})
        assert repeated.status_code == 200 and repeated.content == response.content
        assert client.post("/api/v1/demo/load", json={}).status_code == 401
        assert _state(app.state.runtime) == before


def test_cohort_endpoint_cannot_start_acquisition_write_store_or_contact_sponsors(app, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Cohort vectors crossed a read-only side-effect boundary")

    runtime = app.state.runtime
    monkeypatch.setattr(cv2, "VideoCapture", forbidden)
    for method in ("start", "image"):
        monkeypatch.setattr(runtime.camera, method, forbidden)
    for method in ("put", "put_case_result", "add_case", "update_case", "propose", "approve"):
        if hasattr(runtime.store, method):
            monkeypatch.setattr(runtime.store, method, forbidden)
    monkeypatch.setattr(runtime, "record", forbidden)
    monkeypatch.setattr(runtime, "investigate", forbidden)
    monkeypatch.setattr(chalk_agent, "investigate", forbidden)
    monkeypatch.setattr(PhotonTransport, "send_saved", forbidden)
    monkeypatch.setattr(PhotonTransport, "list_page", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    with TestClient(app) as client:
        before = _state(runtime)
        response = client.get(COHORT_ENDPOINT)
        assert response.status_code == 200, response.text
        assert _state(runtime) == before
        assert runtime.camera.status()["running"] is False


def test_cohort_missing_source_returns_safe_503_and_no_partial_scores(app, tmp_path, monkeypatch):
    monkeypatch.setattr(multidrifter, "DIRECTORY", tmp_path / "PRIVATE-missing-cohort")
    with TestClient(app) as client:
        before = _state(app.state.runtime)
        response = client.get(COHORT_ENDPOINT)
        assert response.status_code == 503
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {"detail": "The pinned cohort vector data is unavailable locally"}
        assert "PRIVATE" not in response.text and str(tmp_path) not in response.text
        assert _state(app.state.runtime) == before


def test_cohort_corrupt_raw_source_returns_409_without_success_metrics(app, tmp_path, monkeypatch):
    _, _, manifest, _, _ = multidrifter.load_multidrifter_inputs()
    destination = tmp_path / "corrupted-cohort"
    shutil.copytree(multidrifter.DIRECTORY, destination)
    raw_path = destination / manifest["trajectories"][0]["raw_path"]
    raw_path.write_bytes(raw_path.read_bytes() + b"\n")
    monkeypatch.setattr(multidrifter, "DIRECTORY", destination)
    with TestClient(app) as client:
        before = _state(app.state.runtime)
        response = client.get(COHORT_ENDPOINT)
        assert response.status_code == 409
        assert response.headers["cache-control"] == "no-store"
        assert "hash" in response.json()["detail"].lower()
        assert "groups" not in response.json() and "models" not in response.json()
        assert str(tmp_path) not in response.text
        assert _state(app.state.runtime) == before
