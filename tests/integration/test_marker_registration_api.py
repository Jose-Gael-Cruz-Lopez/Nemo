"""Existing contracts plus marker admission; disposable store and constructed frames only."""
import asyncio
import copy
import time

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.api.reeftrace_api.services.registration import RegistrationService
from apps.vision.reeftrace_vision.registration import RegistrationConfig
from scripts.rehearse_tank_registration import constructed_frame, synthetic_config

AUTH = {"Authorization": "Bearer synthetic-registration-only"}
BASE = "/api/v1/vision/registration"


class DryCamera:
    def __init__(self):
        self.pixels, _ = constructed_frame()
        self.session_id = "dry"
        self.sequence = 2
        self.fresh = True
        self.moved_after = None

    def status(self):
        return {"running": True, "fresh": self.fresh, "session_id": self.session_id,
                "width": self.pixels.shape[1], "height": self.pixels.shape[0]}

    def image(self):
        self.sequence += 1
        pixels = self.pixels
        if self.moved_after is not None and time.monotonic() >= self.moved_after:
            pixels = cv2.warpAffine(pixels, np.float32([[1, 0, 15], [0, 1, 0]]), (1040, 840),
                                    borderValue=(235, 235, 235))
        _, encoded = cv2.imencode(".jpg", pixels)
        return pixels, {"session_id": self.session_id, "sequence": self.sequence,
                        "width": pixels.shape[1], "height": pixels.shape[0],
                        "received_mono_s": time.monotonic(), "received_utc": "2026-10-19T12:00:00Z",
                        "jpeg": encoded.tobytes()}

    def stop(self):
        self.fresh = False


@pytest.fixture
def env(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Registration attempted hardware/provider I/O")
    import httpx
    monkeypatch.setattr(cv2, "VideoCapture", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    app = create_app(Settings(_env_file=None, data_dir=tmp_path,
                              local_token="synthetic-registration-only", camera_sample_hz=20))
    runtime = app.state.runtime
    runtime.camera = DryCamera()
    with TestClient(app) as client:
        yield client, runtime, app


def configure_stable(runtime, origin="OPERATOR_SURVEYED"):
    config = synthetic_config().model_dump()
    config["data_origin"] = origin  # Contract exercise, not physical measurement.
    runtime.registration.configure(RegistrationConfig.model_validate(config))
    now = time.monotonic()
    for i in range(3):
        runtime.registration.observe(runtime.camera.pixels,
            {"session_id": "dry", "sequence": i, "received_mono_s": now - 1 + i * .5})
    return runtime.registration.status()


def approve(client, state):
    response = client.post(BASE + "/approve", headers=AUTH, json={"proposal_id": state["proposal_id"],
        "water_surface_and_scale_confirmed": True, "confirmed_layers": ["filter_border"]})
    assert response.status_code == 200, response.text
    return response.json()


def test_operator_local_only_no_camera_start_or_synthetic_admission(env):
    client, runtime, app = env
    config = synthetic_config().model_dump()
    assert client.post(BASE + "/configure", json=config).status_code == 401
    result = client.post(BASE + "/configure", json=config, headers=AUTH)
    assert result.status_code == 200
    assert result.headers["Cache-Control"] == "no-store"
    state = configure_stable(runtime, "SYNTHETIC")
    response = client.post(BASE + "/approve", headers=AUTH, json={"proposal_id": state["proposal_id"],
                          "water_surface_and_scale_confirmed": True})
    assert response.status_code == 409 and "Synthetic" in response.text
    assert runtime.store.list("calibration") == []
    app.state.deployment_profile = "cloud_software_demo"
    assert client.get(BASE + "/status", headers=AUTH).status_code == 503
    assert runtime.photon_task is None


def test_managed_mapping_immutable_records_and_stale_recording_gate(env):
    client, runtime, _ = env
    state = approve(client, configure_stable(runtime))
    cid = state["calibration_id"]
    original = copy.deepcopy(runtime.store.get("calibration", cid))
    runtime.registration.assert_current(cid)
    runtime.camera.pixels = np.full_like(runtime.camera.pixels, 235)
    runtime.registration.monitor.last_t -= .5  # Reach the declared sampling gate without sleeping.
    response = client.get(BASE + "/status", headers=AUTH)
    assert response.status_code == 200 and response.json()["state"] == "MOVED_STALE"
    result = client.post("/api/v1/camera/record", headers=AUTH,
                         json={"calibration_id": cid, "duration_s": 1})
    assert result.status_code == 409 and "stale" in result.text
    assert runtime.store.list("recording") == []
    assert len(runtime.store.list("rig_change")) == 1
    assert runtime.store.get("calibration", cid) == original
    assert runtime.registration.status()["proposal"] is None


def test_shift_mid_recording_discards_scientific_record_and_keeps_old_map(env):
    client, runtime, _ = env
    state = approve(client, configure_stable(runtime))
    cid = state["calibration_id"]
    runtime.camera.moved_after = time.monotonic() + .2
    response = client.post("/api/v1/camera/record", headers=AUTH,
                           json={"calibration_id": cid, "duration_s": 1})
    assert response.status_code == 409 and "stale" in response.text
    assert runtime.store.list("recording") == []
    assert runtime.store.get("calibration", cid)["approved"] is True  # Historical fact unchanged.
    assert runtime.registration.status()["mapping_current"] is False


def test_process_restart_cannot_reuse_managed_map_and_detached_reuse_is_blocked(env):
    client, runtime, _ = env
    state = approve(client, configure_stable(runtime))
    cid = state["calibration_id"]
    source = client.get("/api/v1/vision/calibrations/" + cid, headers=AUTH).json()
    response = client.post("/api/v1/vision/calibrations/revalidate", headers=AUTH,
        json={"source": source, "camera_session_id": "dry", "image_size_px": [1040, 840],
              "check_pixels": [[300, 300], [500, 300], [400, 500]],
              "check_world_cm": [[9, 9], [19, 9], [14, 19]], "water_plane_unchanged": True})
    assert response.status_code == 409 and "Marker-managed" in response.text
    runtime.registration = RegistrationService(runtime)
    with pytest.raises(ValueError, match="restart"):
        runtime.registration.assert_current(cid)
    assert client.post("/api/v1/camera/record", headers=AUTH,
        json={"calibration_id": cid, "duration_s": 1}).status_code == 409


def test_explicit_context_change_invalidates_flow_and_cannot_replace_during_recording(env):
    client, runtime, _ = env
    state = approve(client, configure_stable(runtime))
    body = synthetic_config().context.model_dump()
    body["waterline_id"] = "changed-level"
    response = client.post(BASE + "/context", headers=AUTH, json=body)
    assert response.json()["state"] == "MOVED_STALE"
    assert runtime.store.list("rig_change")
    with pytest.raises(ValueError):
        runtime.registration.assert_current(state["calibration_id"])

    async def attempt_while_recording():
        async with runtime.record_lock:
            with pytest.raises(ValueError, match="Stop the recording"):
                runtime.registration.configure(synthetic_config())
    asyncio.run(attempt_while_recording())


def test_support_clipping_frame_age_and_current_proposal_identity(env):
    client, runtime, _ = env
    state = configure_stable(runtime)
    wrong = client.post(BASE + "/approve", headers=AUTH, json={"proposal_id": "0" * 64,
                        "water_surface_and_scale_confirmed": True})
    assert wrong.status_code == 409
    state = approve(client, state)
    cid = state["calibration_id"]
    assert runtime.registration.supported_detections(cid, [{"pixel_x": 200, "pixel_y": 200}])
    assert runtime.registration.supported_detections(cid, [{"pixel_x": 0, "pixel_y": 0}]) == []
    two = [{"pixel_x": 0, "pixel_y": 0}, {"pixel_x": 200, "pixel_y": 200}]
    assert runtime.registration.supported_detections(cid, two) == two
    runtime.registration.observe(runtime.camera.pixels, {"session_id": "dry", "sequence": 50,
                                  "received_mono_s": time.monotonic() - 2})
    with pytest.raises(ValueError, match="stale"):
        runtime.registration.assert_current(cid)


def test_config_and_approval_failure_do_not_leave_current_mapping(env, monkeypatch):
    _client, runtime, _ = env
    state = configure_stable(runtime)
    put = runtime.store.put
    def fail_calibration(kind, payload, record_id=None):
        if kind == "calibration":
            raise OSError("Synthetic write failure")
        return put(kind, payload, record_id)
    monkeypatch.setattr(runtime.store, "put", fail_calibration)
    with pytest.raises(OSError, match="write failure"):
        runtime.registration.approve(state["proposal_id"], [])
    cid = state["proposal"]["calibration"]["calibration_id"]
    assert runtime.registration.is_managed(cid)
    assert runtime.registration.status()["mapping_current"] is False
    with pytest.raises(ValueError, match="stale"):
        runtime.registration.assert_current(cid)


def test_retried_approval_is_idempotent_and_new_recording_binds_exact_approval(env):
    client, runtime, _ = env
    state = configure_stable(runtime)
    approved = approve(client, state)
    assert approve(client, state)["calibration_id"] == approved["calibration_id"]
    response = client.post("/api/v1/camera/record", headers=AUTH,
                           json={"calibration_id": approved["calibration_id"], "duration_s": 1})
    assert response.status_code == 200, response.text
    recording = response.json()
    assert recording["marker_approval_id"] == state["proposal_id"]
    for fid in recording["evidence_frame_ids"]:
        assert runtime.store.get("frame", fid)["marker_approval_id"] == state["proposal_id"]
    assert len(runtime.store.list("marker_approval")) == 1
