"""HTTP boundary for deterministic drift replay; every stored capture is synthetic.

The fixture deliberately uses the recorded-artifact schema to test admission,
while explicit synthetic markers prohibit upgrading it to physical evidence.
No webcam, external provider, physical trial or fitted-flow write is performed.
"""

from __future__ import annotations

import copy
import json
import math
import runpy
from pathlib import Path

import cv2
import httpx
import pytest
from fastapi.testclient import TestClient

from adapters.chalk import agent as chalk_agent
from adapters.photon.transport import PhotonTransport
from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app

URL = "/api/v1/flow/flow-test/trajectory-diagnostic"


@pytest.fixture
def app(tmp_path, monkeypatch):
    for name in ("CHALK_ENABLED", "PHOTON_ENABLED", "GROK_VOICE_ENABLED"):
        monkeypatch.setenv(name, "false")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "[]")
    # Reuse the real frozen flow/calibration constructor exercised by the unit
    # diagnostic tests, then persist its complete synthetic artifact graph.
    module = runpy.run_path(str(Path(__file__).with_name("test_recorded_field_vectors.py")))
    fake = module["stored"].__wrapped__()
    fake.records["flow", "flow-test"]["provenance"]["validation_recording_ids"] = ["validation-near"]
    application = create_app(Settings(_env_file=None, data_dir=tmp_path / "store",
                                      local_token="private-unit-operator"))
    for (kind, identifier), document in fake.records.items():
        application.state.runtime.store.put(kind, document, identifier)
    return application


def snapshot(app):
    with app.state.runtime.store.connection() as db:
        return tuple(db.iterdump())


def test_actual_stored_synthetic_trajectory_is_scored_through_public_http_without_mutation(app):
    with TestClient(app) as client:
        before, camera = snapshot(app), app.state.runtime.camera.status()
        response = client.get(URL)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        report = response.json()
        assert report["kind"] == "RECORDED_FIELD_TRAJECTORY_DIAGNOSTIC"
        assert report["status"] == "COMPLETED"
        assert report["data_origin"] == "SYNTHETIC_CAPTURE_REPLAY"
        assert report["position_units"] == "cm" and report["time_units"] == "s"
        assert report["scope"] == "ALREADY_REVIEWED_RECORDINGS_DETERMINISTIC_MEAN_FIELD_NOT_INDEPENDENT_TEST"
        assert report["coverage"] == {"validation_recordings": 1, "complete_recordings": 1,
            "planned_forecast_points": 5, "scored_forecast_points": 5, "withheld_forecast_points": 0}
        assert report["metrics"]["equal_recording_ade_cm"] == pytest.approx(.6)
        assert report["metrics"]["equal_recording_fde_cm"] == pytest.approx(1)
        assert report["metrics"]["pooled_position_rmse_cm"] == pytest.approx(math.sqrt(.44))
        assert [row["predicted_x_cm"] for row in report["recordings"][0]["comparisons"]] == pytest.approx(
            [4.2, 4.4, 4.6, 4.8, 5.0])
        assert report["model"]["initial_observation_only"] is True
        assert report["model"]["observed_position_updates"] is False
        for key in ("physical_validation", "capture_independently_verified", "camera_started",
                    "hardware_actuation", "store_written", "refit_performed",
                    "model_selection_performed", "independent_evaluation", "provider_calls",
                    "calibrated_probability"):
            assert report[key] is False
        assert "private-unit-operator" not in response.text
        assert "/private/" not in response.text and str(app.state.runtime.settings.data_dir) not in response.text
        json.dumps(report, allow_nan=False)
        # This public, read-only operation does not need or consume operator access.
        second = client.get(URL, headers={"Authorization": "Bearer wrong"})
        assert second.status_code == 200 and second.content == response.content
        assert snapshot(app) == before and app.state.runtime.camera.status() == camera
        assert camera["running"] is False


def test_http_trajectory_replay_cannot_capture_refit_contact_providers_or_write(app, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Read-only trajectory API crossed a side-effect boundary")

    runtime = app.state.runtime
    monkeypatch.setattr(cv2, "VideoCapture", forbidden)
    monkeypatch.setattr("apps.transport.reeftrace_transport.fit_flow", forbidden)
    monkeypatch.setattr("apps.transport.reeftrace_transport.flow.fit_flow", forbidden)
    for method in ("start", "image"):
        monkeypatch.setattr(runtime.camera, method, forbidden)
    for method in ("put", "put_case_result", "add_case", "update_case", "propose", "approve"):
        if hasattr(runtime.store, method):
            monkeypatch.setattr(runtime.store, method, forbidden)
    monkeypatch.setattr(runtime, "record", forbidden)
    monkeypatch.setattr(runtime, "investigate", forbidden)
    monkeypatch.setattr(runtime, "speak_briefing", forbidden)
    monkeypatch.setattr(chalk_agent, "investigate", forbidden)
    monkeypatch.setattr(PhotonTransport, "send_saved", forbidden)
    monkeypatch.setattr(PhotonTransport, "list_page", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    with TestClient(app) as client:
        before = snapshot(app)
        response = client.get(URL)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        assert snapshot(app) == before
        assert runtime.camera.status()["running"] is False


def test_missing_recorded_flow_returns_safe_no_store_404(app):
    with TestClient(app) as client:
        before = snapshot(app)
        response = client.get("/api/v1/flow/missing-flow/trajectory-diagnostic")
        assert response.status_code == 404
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {"detail": "Recorded flow evidence not found"}
        assert snapshot(app) == before


@pytest.mark.parametrize("change", ["wrong_origin", "split_overlap", "duplicate_reference"])
def test_invalid_frozen_provenance_returns_409_without_partial_metrics_or_writes(app, change):
    runtime = app.state.runtime
    invalid = copy.deepcopy(runtime.store.get("flow", "flow-test"))
    if change == "wrong_origin":
        invalid["data_origin"] = "SYNTHETIC"
    elif change == "split_overlap":
        invalid["provenance"]["validation_recording_ids"] = ["training"]
    else:
        invalid["provenance"]["validation_recording_ids"] *= 2
    runtime.store.put("flow", invalid, "invalid-flow")
    with TestClient(app) as client:
        before = snapshot(app)
        response = client.get("/api/v1/flow/invalid-flow/trajectory-diagnostic")
        assert response.status_code == 409
        assert response.headers["cache-control"] == "no-store"
        assert set(response.json()) == {"detail"}
        assert "metrics" not in response.json() and "recordings" not in response.json()
        assert snapshot(app) == before


def test_missing_referenced_capture_frame_is_404_instead_of_an_invented_trajectory(app):
    runtime = app.state.runtime
    flow = copy.deepcopy(runtime.store.get("flow", "flow-test"))
    recording = copy.deepcopy(runtime.store.get("recording", "validation-near"))
    recording["evidence_frame_ids"][0] = recording["points"][0]["frame_id"] = "absent-frame"
    runtime.store.put("recording", recording, "missing-frame-recording")
    flow["provenance"]["validation_recording_ids"] = ["missing-frame-recording"]
    runtime.store.put("flow", flow, "missing-frame-flow")
    with TestClient(app) as client:
        before = snapshot(app)
        response = client.get("/api/v1/flow/missing-frame-flow/trajectory-diagnostic")
        assert response.status_code == 404
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {"detail": "Recorded flow evidence not found"}
        assert snapshot(app) == before


def test_gap_is_a_withheld_required_run_not_http_success_with_a_fabricated_zero_error(app):
    runtime = app.state.runtime
    flow = copy.deepcopy(runtime.store.get("flow", "flow-test"))
    recording = copy.deepcopy(runtime.store.get("recording", "validation-near"))
    recording["points"][2]["observed"] = False
    runtime.store.put("recording", recording, "gapped-recording")
    flow["provenance"]["validation_recording_ids"] = ["gapped-recording"]
    runtime.store.put("flow", flow, "gapped-flow")
    with TestClient(app) as client:
        before = snapshot(app)
        response = client.get("/api/v1/flow/gapped-flow/trajectory-diagnostic")
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        report = response.json()
        assert report["status"] == "WITHHELD_INCOMPLETE_RUNS" and report["metrics"] is None
        assert report["coverage"]["scored_forecast_points"] == 0
        assert report["coverage"]["withheld_forecast_points"] == 5
        assert report["recordings"][0]["comparisons"] == []
        assert "MISSING_OR_BROKEN_TRACK" in report["recordings"][0]["reason_codes"]
        assert report["physical_validation"] is False
        assert snapshot(app) == before
