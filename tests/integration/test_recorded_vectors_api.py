"""Recorded-vector HTTP boundary using synthetic contracts in the actual SQLite store.

No physical camera or tank is used; MEASURED_TANK here exercises the existing
stored-record schema while explicit SYNTHETIC_CONTRACT_TEST flags are retained.
"""

from __future__ import annotations

import cv2
import httpx
import pytest
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.transport.reeftrace_transport.flow import fit_flow
from apps.vision.reeftrace_vision.calibration import fit_homography
from apps.vision.reeftrace_vision.tracking import flow_samples


@pytest.fixture
def app(tmp_path, monkeypatch):
    for variable in ("CHALK_ENABLED", "PHOTON_ENABLED", "GROK_VOICE_ENABLED"):
        monkeypatch.setenv(variable, "false")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "[]")
    for variable in ("CHALK_ROUTER_API_KEY", "PHOTON_API_KEY", "XAI_API_KEY"):
        monkeypatch.setenv(variable, "PRIVATE-RECORDED-VECTOR-TEST")
    app = create_app(Settings(data_dir=tmp_path / "store", local_token="PRIVATE-OPERATOR-TEST"))
    store = app.state.runtime.store
    calibration = fit_homography(
        [[0, 0], [200, 0], [200, 200], [0, 200]],
        [[0, 0], [20, 0], [20, 20], [0, 20]],
        [[20, 30], [80, 120], [180, 150]], [[2, 3], [8, 12], [18, 15]],
        image_size_px=[201, 201], camera_session_id="api-test-camera",
    )
    store.put("calibration", calibration, calibration["calibration_id"])
    runs = []
    for split, speed in (("training", 1), ("validation", 2)):
        points, frame_ids = [], []
        for index in range(6):
            frame_id = f"{split}-frame-{index}"
            store.put("frame", {"camera_session_id": "api-test-camera",
                "test_fixture_origin": "SYNTHETIC_CONTRACT_TEST", "physical_validation": False,
                "path": "/private/not-an-exposed-frame.jpg"}, frame_id)
            frame_ids.append(frame_id)
            points.append({"t_s": index * 0.2, "x_cm": 4 + index * 0.2 * speed,
                "y_cm": 5, "observed": True, "track_id": f"{split}-track", "frame_id": frame_id})
        runs.append(store.put("recording", {"points": points, "evidence_frame_ids": frame_ids,
            "data_origin": "MEASURED_TANK", "camera_session_id": "api-test-camera",
            "calibration_id": calibration["calibration_id"],
            "timestamp_kind": "host_receipt_not_exposure",
            "test_fixture_origin": "SYNTHETIC_CONTRACT_TEST", "physical_validation": False}, split))
    flow = fit_flow(flow_samples(runs[0]["points"]),
        {"x_min_cm": 0, "x_max_cm": 20, "y_min_cm": 0, "y_max_cm": 20},
        cell_size_cm=1, coverage_radius_cm=3, data_origin="MEASURED_TANK")
    flow["provenance"] = {"calibration_id": calibration["calibration_id"],
        "camera_session_id": "api-test-camera", "training_recording_ids": ["training"],
        "validation_recording_ids": ["validation"], "frame_splits_disjoint": True}
    store.put("flow", flow, "flow-api-test")
    return app


def _state(runtime):
    with runtime.store.connection() as db:
        return tuple(db.iterdump())


def test_actual_saved_flow_replays_through_public_http_without_actions_or_state_changes(app, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Stored-vector GET attempted acquisition, refitting or mutation")

    runtime = app.state.runtime
    monkeypatch.setattr(cv2, "VideoCapture", forbidden)
    monkeypatch.setattr(runtime.camera, "start", forbidden)
    monkeypatch.setattr(runtime.camera, "image", forbidden)
    monkeypatch.setattr(runtime.store, "put", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    monkeypatch.setattr("apps.transport.reeftrace_transport.flow.fit_flow", forbidden)
    with TestClient(app) as client:
        before, camera = _state(runtime), runtime.camera.status()
        response = client.get("/api/v1/flow/flow-api-test/vector-diagnostic")
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        report = response.json()
        assert report["kind"] == "RECORDED_FIELD_VECTOR_DIAGNOSTIC"
        assert report["data_origin"] == "SYNTHETIC_CAPTURE_REPLAY"
        assert report["physical_validation"] is False
        assert report["capture_independently_verified"] is False
        assert report["flow_id"] == "flow-api-test"
        assert report["provenance"]["validation_recording_ids"] == ["validation"]
        assert report["coverage"]["validation_sample_count"] == 3
        assert report["coverage"]["supported_sample_count"] == 3
        assert report["metrics"]["vector_rmse_cm_s"] == pytest.approx(1)
        assert report["metrics"]["mean_speed_bias_cm_s"] == pytest.approx(-1)
        assert report["refit_performed"] is False
        assert report["camera_started"] is False and report["store_written"] is False
        assert report["provider_calls"] is False
        assert "PRIVATE-" not in response.text and "/private/" not in response.text
        assert client.get("/api/v1/flow/flow-api-test/vector-diagnostic").content == response.content
        assert _state(runtime) == before
        assert runtime.camera.status() == camera
        assert camera["running"] is False


def test_unknown_frozen_flow_returns_uncached_404_without_partial_report(app):
    with TestClient(app) as client:
        before = _state(app.state.runtime)
        response = client.get("/api/v1/flow/flow-missing/vector-diagnostic")
        assert response.status_code == 404
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {"detail": "Recorded flow evidence not found"}
        assert _state(app.state.runtime) == before


def test_wrong_session_binding_returns_uncached_409_and_preserves_saved_evidence(app):
    store = app.state.runtime.store
    wrong = store.get("recording", "validation")
    wrong["camera_session_id"] = "another-camera"
    store.put("recording", wrong, "wrong-session-validation")
    flow = store.get("flow", "flow-api-test")
    flow["provenance"]["validation_recording_ids"] = ["wrong-session-validation"]
    store.put("flow", flow, "flow-wrong-binding")
    with TestClient(app) as client:
        before = _state(app.state.runtime)
        response = client.get("/api/v1/flow/flow-wrong-binding/vector-diagnostic")
        assert response.status_code == 409
        assert response.headers["cache-control"] == "no-store"
        assert "binding" in response.json()["detail"]
        assert "metrics" not in response.json() and "vectors" not in response.json()
        assert "PRIVATE-" not in response.text
        assert _state(app.state.runtime) == before
