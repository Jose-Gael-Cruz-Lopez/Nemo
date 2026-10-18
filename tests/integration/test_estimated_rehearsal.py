"""Real rehearsal API/capture loop with synthetic frames, never physical validation."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import time
from datetime import UTC, datetime

import cv2
import numpy as np
import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.api.v1.endpoints.estimated_rehearsal import (
    EstimatedRehearsalInput,
    create_estimated_rehearsal_router,
)
from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.api.reeftrace_api.services.estimated_rehearsal import EstimatedRehearsalService
from apps.vision.reeftrace_vision.calibration import fit_homography

TOKEN = "estimated-rehearsal-synthetic-only"
AUTH = {"Authorization": "Bearer " + TOKEN}
BASE = "/api/v1/camera/rehearsals"
WIDTH, HEIGHT = 160, 120


class SyntheticCamera:
    backend = "SYNTHETIC_FAKE_CAPTURE"

    def __init__(self):
        self.session_id = "usb-current-synthetic"
        self.running = self.fresh = True
        self.width, self.height, self.sequence = WIDTH, HEIGHT, 0
        self.cap = (0, 0, 255)
        self.gap_sequences = {4, 5, 6}
        self.restart_at = self.resize_at = None
        self.floor = np.random.default_rng(5).integers(80, 160, (HEIGHT, WIDTH, 3), np.uint8)

    def status(self):
        return {"running": self.running, "fresh": self.fresh, "session_id": self.session_id,
                "width": self.width, "height": self.height, "device_index": 1,
                "backend": self.backend}

    def stop(self):
        self.running = False
        self.session_id = None

    def image(self):
        self.sequence += 1
        if self.sequence == self.restart_at:
            self.session_id = "usb-restarted"
        if self.sequence == self.resize_at:
            self.width += 1
        image = self.floor.copy()
        if self.cap and self.sequence not in self.gap_sequences:
            cv2.circle(image, (50 + self.sequence // 4, 55), 7, self.cap, -1)
        ok, jpeg = cv2.imencode(".jpg", image)
        assert ok
        return image, {"session_id": self.session_id, "sequence": self.sequence,
                       "width": self.width, "height": self.height,
                       "received_mono_s": time.monotonic(),
                       "received_utc": datetime.now(UTC).isoformat(), "jpeg": jpeg.tobytes()}


@pytest.fixture
def env(tmp_path):
    app = create_app(Settings(_env_file=None, data_dir=tmp_path, local_token=TOKEN,
                              camera_sample_hz=20))
    runtime = app.state.runtime
    runtime.camera = SyntheticCamera()

    def operator(request: Request):
        if request.headers.get("Authorization") != AUTH["Authorization"]:
            raise HTTPException(401, "Operator token required")

    if BASE not in app.openapi()["paths"]:
        app.include_router(create_estimated_rehearsal_router(runtime, operator), prefix="/api/v1")
    fit = [[0, 0], [159, 0], [159, 119], [0, 119]]
    check = [[20, 20], [130, 30], [70, 100]]
    cm = lambda points: [[x / 10, y / 10] for x, y in points]
    report = fit_homography(fit, cm(fit), check, cm(check), max_error_cm=0.5,
                            image_size_px=[WIDTH, HEIGHT], camera_session_id="usb-historical")
    source = runtime.store.put("calibration", report, report["calibration_id"])
    with TestClient(app) as client:
        yield client, runtime, source, app


def body(source):
    return {"source": {"schema_version": "nemo_saved_calibration_v1", "calibration": source,
                       "calibration_json": json.dumps(source, sort_keys=True, allow_nan=False)},
            "camera_session_id": "usb-current-synthetic", "image_size_px": [WIDTH, HEIGHT],
            "duration_s": 1, "detector": "red_hsv", "acknowledge_estimated_mapping": True}


def post(client, payload, expected=200):
    response = client.post(BASE, headers=AUTH, json=payload)
    assert response.status_code == expected, response.text
    return response.json()


def test_local_rehearsal_captures_real_loop_points_gaps_and_private_frames_without_admission(env):
    client, runtime, source, _ = env
    before = copy.deepcopy(source)
    result = post(client, body(source))
    assert result["id"].startswith("rehearsal-")
    assert result["data_origin"] == "LOCAL_CAPTURE_ESTIMATED_COORDINATES"
    assert result["validation_status"] == "UNVALIDATED"
    assert result["calibration_id"] is result["profile_id"] is result["case_id"] is None
    assert result["current_alignment_verified"] is result["approved_for_inference"] is False
    assert result["capture_backend"] == "SYNTHETIC_FAKE_CAPTURE"
    assert result["timestamp_kind"] == "host_receipt_not_exposure"
    assert result["source_calibration_id"] == source["id"]
    assert result["warnings"] and "not current accuracy" in result["warnings"][0]
    observed = [p for p in result["points"] if p["observed"]]
    gaps = [p for p in result["points"] if not p["observed"]]
    assert observed and gaps
    assert all({"pixel_x", "pixel_y", "estimated_x_cm", "estimated_y_cm", "track_id",
                "association_break", "frame_id"} <= set(point) for point in observed)
    assert all("x_cm" not in point and "y_cm" not in point for point in result["points"])
    assert all(set(point) == {"observed", "t_s", "reason", "frame_id"} for point in gaps)
    assert all("estimated_x_cm" not in point and "pixel_x" not in point for point in gaps)
    assert len({p["frame_id"] for p in result["points"]}) == len(result["points"])
    assert all(b["t_s"] > a["t_s"] for a, b in zip(result["points"], result["points"][1:]))
    assert all(p["estimated_x_cm"] == pytest.approx(p["pixel_x"] / 10) for p in observed)
    assert len(runtime.store.list("estimated_rehearsal_frame")) == result["frames"]
    assert runtime.store.list("frame") == runtime.store.list("recording") == []
    assert runtime.store.list("profile") == runtime.store.cases() == []
    assert runtime.store.get("calibration", source["id"]) == before
    assert len(runtime.store.list("calibration")) == 1
    assert str(runtime.settings.data_dir) not in json.dumps(result)
    assert runtime.photon_task is None
    retrieved = client.get(BASE + "/" + result["id"], headers=AUTH)
    assert retrieved.status_code == 200 and retrieved.json() == result
    assert retrieved.headers["Cache-Control"] == "no-store"
    assert client.get(BASE + "/" + result["id"]).status_code == 401

    # The existing measured-data endpoints cannot find this separate record kind.
    assert client.post("/api/v1/recordings/" + result["id"] + "/case",
                       headers=AUTH, json={}).status_code == 404
    flow = client.post("/api/v1/flow/fit-recordings", headers=AUTH, json={
        "training_recording_ids": [result["id"]], "validation_recording_ids": ["not-a-recording"],
        "bounds": {"x_min_cm": 0, "x_max_cm": 16, "y_min_cm": 0, "y_max_cm": 12}})
    assert flow.status_code == 404
    assert client.post("/api/v1/profiles", headers=AUTH, json=result).status_code == 409
    measured = client.post("/api/v1/camera/record", headers=AUTH,
                           json={"calibration_id": source["id"], "duration_s": 1})
    assert measured.status_code == 409 and "session" in measured.json()["detail"]


def test_foreground_rehearsal_needs_current_reference_and_measured_pixel_size(env):
    client, runtime, source, _ = env
    payload = {**body(source), "detector": "foreground_reference_v1"}
    assert "reference_id" in post(client, payload, 409)["detail"]
    runtime.camera.cap = None
    reference = client.post("/api/v1/camera/reference", headers=AUTH, json={"frame_count": 5}).json()
    payload["reference_id"] = reference["reference_id"]
    assert "Measure one token" in post(client, payload, 409)["detail"]
    runtime.camera.cap = (20, 180, 20)
    runtime.camera.gap_sequences = set()
    measured = client.post("/api/v1/camera/reference/" + reference["reference_id"] + "/token-size",
                           headers=AUTH, json={})
    assert measured.status_code == 200, measured.text
    result = post(client, payload)
    assert result["observed"] > 0
    assert result["detection"]["reference_id"] == reference["reference_id"]
    runtime.camera.session_id = "usb-new-session"
    payload["camera_session_id"] = runtime.camera.session_id
    assert "another camera session" in post(client, payload, 409)["detail"]


@pytest.mark.parametrize("change", ["stopped", "stale", "session", "dimensions", "source_size"])
def test_rehearsal_refuses_unavailable_or_changed_capture(env, change):
    client, runtime, source, _ = env
    payload = body(source)
    if change == "stopped":
        runtime.camera.running = False
    elif change == "stale":
        runtime.camera.fresh = False
    elif change == "session":
        runtime.camera.session_id = "usb-another"
    elif change == "dimensions":
        runtime.camera.width += 1
    else:
        payload["image_size_px"][0] += 1
        runtime.camera.width += 1
    post(client, payload, 409)
    assert runtime.store.list("estimated_rehearsal") == []


@pytest.mark.parametrize("change", ["session", "dimensions"])
def test_mid_capture_change_discards_rehearsal_and_private_partial_files(env, change):
    client, runtime, source, _ = env
    if change == "session":
        runtime.camera.restart_at = 3
    else:
        runtime.camera.resize_at = 3
    post(client, body(source), 409)
    assert runtime.store.list("estimated_rehearsal") == []
    assert runtime.store.list("estimated_rehearsal_frame") == []
    assert list((runtime.settings.data_dir / "estimated_rehearsals").iterdir()) == []
    assert not runtime.record_lock.locked()


def test_busy_rehearsal_does_not_queue_or_capture_and_cancel_frees_lock(env):
    _, runtime, source, _ = env
    service = EstimatedRehearsalService(runtime)
    request = EstimatedRehearsalInput.model_validate(body(source))

    async def exercise():
        await runtime.record_lock.acquire()
        try:
            with pytest.raises(ValueError, match="active"):
                await asyncio.wait_for(service.capture(request), timeout=0.2)
            assert runtime.camera.sequence == 0
        finally:
            runtime.record_lock.release()
        task = asyncio.create_task(service.capture(request))
        while not runtime.camera.sequence:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not runtime.record_lock.locked()
        assert runtime.store.list("estimated_rehearsal") == []
        assert runtime.store.list("estimated_rehearsal_frame") == []
        assert list((runtime.settings.data_dir / "estimated_rehearsals").iterdir()) == []

    asyncio.run(exercise())


@pytest.mark.parametrize("change", ["acknowledgement", "duration", "missing_exact_json"])
def test_auth_and_explicit_unvalidated_acknowledgement_are_required(env, change):
    client, runtime, source, _ = env
    payload = body(source)
    assert client.post(BASE, json=payload).status_code == 401
    if change == "acknowledgement":
        payload["acknowledge_estimated_mapping"] = False
    elif change == "duration":
        payload["duration_s"] = 11
    else:
        del payload["source"]["calibration_json"]
    post(client, payload, 422)
    assert runtime.camera.sequence == 0


def test_local_rehearsal_is_disabled_in_cloud_even_if_router_is_mounted(env):
    client, runtime, source, app = env
    app.state.deployment_profile = "cloud_software_demo"
    assert client.post(BASE, headers=AUTH, json=body(source)).status_code == 503
    assert client.get(BASE + "/rehearsal-anything", headers=AUTH).status_code == 503
    assert runtime.camera.sequence == 0


@pytest.mark.parametrize("change", ["tampered", "unapproved"])
def test_historical_source_must_be_intact_and_previously_approved(env, change):
    client, runtime, source, _ = env
    changed = copy.deepcopy(source)
    if change == "tampered":
        changed["homography_image_to_cm"][0][2] += 1
    else:
        changed["approved"] = False
        report = {key: value for key, value in changed.items() if key not in {"id", "calibration_id"}}
        identity = "cal-" + hashlib.sha256(
            json.dumps(report, sort_keys=True, allow_nan=False).encode()).hexdigest()[:16]
        changed.update(id=identity, calibration_id=identity)
    post(client, body(changed), 409)
    assert runtime.camera.sequence == 0
    assert runtime.store.list("estimated_rehearsal") == []


def test_detector_scene_change_discards_capture_instead_of_inventing_coordinates(env, monkeypatch):
    client, runtime, source, _ = env

    def changed_scene(_image):
        raise ValueError("The camera moved; reference is no longer valid")

    monkeypatch.setattr(runtime.token_detection, "detector",
                        lambda *_args: (changed_scene, {"detector": "red_hsv"}))
    assert "camera moved" in post(client, body(source), 409)["detail"]
    assert runtime.store.list("estimated_rehearsal") == []
    assert runtime.store.list("estimated_rehearsal_frame") == []
    assert list((runtime.settings.data_dir / "estimated_rehearsals").iterdir()) == []
