"""Field-session workflow through the actual API, recorder, tracker, flow fit and gates.

Only the capture DEVICE is replaced, by ``SyntheticFakeCapture``: it draws a red
disc on a synthetic image and reports backend ``SYNTHETIC_FAKE_CAPTURE``. Every
admission gate the workflow is meant to prove runs unmodified. Nothing here is a
physical tank measurement; the resulting manifests are labelled synthetic.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.api.v1.endpoints.field_sessions import create_field_sessions_router
from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.api.reeftrace_api.schemas.field_sessions import FieldSessionInput
from apps.api.reeftrace_api.services.field_sessions import (
    KIND,
    Blocked,
    FieldSessionService,
    verify_manifest,
)

TOKEN = "field-session-test-only"
AUTH = {"Authorization": "Bearer " + TOKEN}
PX_PER_CM = 20
WIDTH, HEIGHT = 640, 480
BOUNDS = {"x_min_cm": 0, "x_max_cm": 32, "y_min_cm": 0, "y_max_cm": 24}
ATTEST = {"waterline_unchanged": True, "pump_setting_unchanged": True,
          "hose_and_pocket_unchanged": True, "camera_and_light_unchanged": True,
          "coordinates_measured_in_cm": True}


class SyntheticFakeCapture:
    """Explicit synthetic capture device. Frames are drawn, never read from a camera."""

    backend = "SYNTHETIC_FAKE_CAPTURE"

    def __init__(self):
        self.lock = threading.RLock()
        self.session_id = self.device = None
        self.sequence = 0
        self.frozen = False
        self.script = (5.0, 10.0, 3.0, 0.0, time.monotonic())

    def start(self, device):
        with self.lock:
            self.session_id, self.device, self.frozen = "usb-fake-" + uuid.uuid4().hex[:12], device, False
            return self.status()

    def stop(self):
        with self.lock:
            self.session_id = self.device = None

    def drift(self, x_cm, y_cm, vx_cm_s=3.0, vy_cm_s=0.0):
        self.script = (x_cm, y_cm, vx_cm_s, vy_cm_s, time.monotonic())

    def status(self):
        running = self.session_id is not None
        return {"running": running, "session_id": self.session_id, "device_index": self.device,
                "fresh": running and not self.frozen, "age_s": 0.0 if running else None,
                "sequence": self.sequence or None, "width": WIDTH if running else None,
                "height": HEIGHT if running else None, "backend": self.backend if running else None}

    def image(self):
        if self.session_id is None or self.frozen:
            raise ValueError("Camera is stopped, unavailable or stale")
        now = time.monotonic()
        x0, y0, vx, vy, t0 = self.script
        x, y = x0 + vx * (now - t0), y0 + vy * (now - t0)
        image = np.full((HEIGHT, WIDTH, 3), (120, 110, 90), np.uint8)
        cv2.circle(image, (round(x * PX_PER_CM), round(y * PX_PER_CM)), 10, (0, 0, 255), -1)
        self.sequence += 1
        ok, jpeg = cv2.imencode(".jpg", image)
        assert ok
        return image, {"sequence": self.sequence, "received_mono_s": now,
                       "received_utc": datetime.now(UTC).isoformat(), "width": WIDTH, "height": HEIGHT,
                       "jpeg": jpeg.tobytes(), "backend": self.backend, "session_id": self.session_id}


@pytest.fixture
def env(tmp_path):
    app = create_app(Settings(data_dir=tmp_path, local_token=TOKEN, camera_sample_hz=20))
    runtime = app.state.runtime
    runtime.camera = SyntheticFakeCapture()
    with TestClient(app) as client:
        yield client, runtime, tmp_path


def post(client, path, body, status=200):
    response = client.post("/api/v1" + path, headers=AUTH, json=body)
    assert response.status_code == status, response.text
    return response.json()


def mapping(session_id, scale=1.0, check_scale=None):
    fit = [[0, 0], [639, 0], [639, 479], [0, 479]]
    check = [[100, 100], [500, 120], [300, 400]]
    check_scale = scale if check_scale is None else check_scale
    return {"pixel_points": fit, "world_cm_points": [[x / PX_PER_CM * scale, y / PX_PER_CM * scale] for x, y in fit],
            "check_pixels": check,
            "check_world_cm": [[x / PX_PER_CM * check_scale, y / PX_PER_CM * check_scale] for x, y in check],
            "max_error_cm": 0.5, "image_size_px": [WIDTH, HEIGHT], "camera_session_id": session_id}


def record(client, camera, *, at, **body):
    camera.drift(*at)
    return post(client, "/camera/record", {"duration_s": 1, **body})


def profile_body(calibration_id, flow):
    square = lambda x, y: [[x, y], [x + 2, y], [x + 2, y + 2], [x, y + 2]]
    return {"calibration_id": calibration_id, "data_origin": "MEASURED_TANK", "token_class": "red-foam-10mm",
            "bounds": BOUNDS, "flow": flow,
            "sources": [{"id": s, "polygon_cm": square(1, y)} for s, y in (("A", 3), ("B", 10), ("C", 18))],
            "traps": [{"id": "pocket", "validated": True, "polygon_cm": square(28, 10)}],
            "observation_polygon_cm": [[0, 0], [32, 0], [32, 24], [0, 24]],
            "transport": {"particles_per_source": 20, "dt_s": 0.1, "max_age_s": 5},
            "max_validation_rmse_cm_s": 1.0, "revalidation_max_rmse_cm_s": 1.0}


def commission(client, camera, *, validation_at=(5, 10), coverage_radius_cm=4):
    """The linear operator workflow, each step through an existing endpoint."""
    session = post(client, "/camera/start", {"device_index": 1})["session_id"]
    calibration = post(client, "/vision/calibrate", mapping(session))
    assert calibration["approved"] is True
    cal_id = calibration["calibration_id"]
    training = [record(client, camera, at=(4, y), calibration_id=cal_id)["id"] for y in (8, 12)]
    validation = [record(client, camera, at=validation_at, calibration_id=cal_id)["id"]]
    flow = post(client, "/flow/fit-recordings", {"training_recording_ids": training,
                "validation_recording_ids": validation, "bounds": BOUNDS,
                "coverage_radius_cm": coverage_radius_cm})
    return {"camera_session_id": session, "calibration_id": cal_id, "training_recording_ids": training,
            "validation_recording_ids": validation, "flow_id": flow["id"]}, flow


def admit_and_observe(client, camera, request, flow):
    profile = post(client, "/profiles", profile_body(request["calibration_id"], flow))
    source_recording = record(client, camera, at=(6, 9), profile_id=profile["id"])
    case = post(client, f"/recordings/{source_recording['id']}/case", {"observation_type": "trajectory"})
    return {**request, "profile_id": profile["id"], "first_case_id": case["id"], "attestations": ATTEST}


def steps(preflight):
    return {s["step"]: (s["status"], s["code"]) for s in preflight["steps"]}


def no_manifest(runtime):
    return runtime.store.list(KIND) == []


def test_missing_camera_blocks_every_capture_step_and_saves_nothing(env):
    client, runtime, _ = env
    request = {"camera_session_id": "usb-none", "calibration_id": "cal-none", "training_recording_ids": ["r1"],
               "validation_recording_ids": ["r2"], "flow_id": "flow-none", "profile_id": "profile-none"}
    preflight = post(client, "/field-sessions/preflight", request)
    assert preflight["status"] == "BLOCKED" and preflight["manifest_id"] is None
    assert steps(preflight)["camera_session"] == ("MISSING", "CAMERA_NOT_RUNNING")
    assert steps(preflight)["first_source_observation"] == ("MISSING", "NO_SOURCE_OBSERVATION")
    assert all(s["help"] for s in preflight["steps"] if s["status"] != "PASSED")
    assert client.post("/api/v1/camera/record", headers=AUTH,
                       json={"duration_s": 1, "calibration_id": "cal-none"}).status_code in {404, 409}
    assert client.post("/api/v1/field-sessions", headers=AUTH, json=request).status_code == 409
    assert runtime.camera.session_id is None, "the workflow must never open a camera itself"
    assert no_manifest(runtime)


def test_writes_require_the_shared_operator_dependency(env):
    client, runtime, _ = env
    body = {"camera_session_id": "s", "calibration_id": "c", "training_recording_ids": ["a"],
            "validation_recording_ids": ["b"], "flow_id": "f", "profile_id": "p"}
    for path in ("/api/v1/field-sessions", "/api/v1/field-sessions/preflight"):
        assert client.post(path, json=body).status_code == 401
        assert client.post(path, json=body, headers={"Authorization": "Bearer wrong"}).status_code == 401
    with pytest.raises(TypeError):
        create_field_sessions_router(runtime, None)


def test_caller_cannot_claim_gates_passed_or_inject_truth(env):
    client, runtime, _ = env
    body = {"camera_session_id": "s", "calibration_id": "c", "training_recording_ids": ["a"],
            "validation_recording_ids": ["b"], "flow_id": "f", "profile_id": "p"}
    for extra in ({"status": "READY"}, {"approved": True}, {"true_source": "A"}, {"checks": []}):
        assert client.post("/api/v1/field-sessions", headers=AUTH, json={**body, **extra}).status_code == 422
    assert no_manifest(runtime)


def test_successful_explicit_fake_capture_protocol_freezes_reproducible_receipt(env):
    client, runtime, tmp_path = env
    request, flow = commission(client, runtime.camera)
    partial = post(client, "/field-sessions/preflight", request)
    assert steps(partial)["measured_profile"][0] == "MISSING"
    assert client.post("/api/v1/field-sessions", headers=AUTH, json=request).status_code == 409
    request = admit_and_observe(client, runtime.camera, request, flow)

    unattested = {**request, "attestations": {**ATTEST, "pump_setting_unchanged": False}}
    assert steps(post(client, "/field-sessions/preflight", unattested))["operator_attestations"][0] == "BLOCKED"
    assert no_manifest(runtime)

    ready = post(client, "/field-sessions/preflight", request)
    assert ready["status"] == "READY", ready
    detail = post(client, "/field-sessions", request)
    manifest = detail["manifest"]
    assert detail["is_current"] is True and detail["stale_reasons"] == []
    assert manifest["manifest_id"] == ready["manifest_id"]
    assert manifest["content_hash"] == ready["content_hash"]
    assert verify_manifest(manifest).status == "READY"
    assert manifest["capture"]["capture_origin"] == "SYNTHETIC_FAKE_CAPTURE"
    assert "SYNTHETIC_FAKE_CAPTURE_NOT_PHYSICAL" in manifest["warnings"]
    assert manifest["provenance"]["hardware_independently_verified"] is False
    assert manifest["flow"]["flow_id"] == flow["id"]
    assert manifest["first_observation"]["case_id"] == request["first_case_id"]
    assert [c["status"] for c in manifest["checks"]] == ["PASSED"] * 8
    text = json.dumps(manifest)
    for forbidden in (str(tmp_path), TOKEN, "true_source", ".jpg", "release_time"):
        assert forbidden not in text

    again = post(client, "/field-sessions", request)
    assert again["manifest"] == manifest, "same artifacts give the same ID, hash and original receipt"
    assert len(runtime.store.list(KIND)) == 1
    assert client.get(f"/api/v1/field-sessions/{manifest['manifest_id']}").json() == detail
    assert client.get("/api/v1/field-sessions").json()[0]["manifest_id"] == manifest["manifest_id"]
    assert client.get("/api/v1/field-sessions/fm-0000000000000000").status_code == 404


def test_stored_receipt_tampering_is_detected_on_read(env):
    client, runtime, _ = env
    request, flow = commission(client, runtime.camera)
    manifest = post(client, "/field-sessions", admit_and_observe(client, runtime.camera, request, flow))["manifest"]
    tampered = {**manifest, "warnings": [w for w in manifest["warnings"] if "SYNTHETIC" not in w]}
    with pytest.raises(ValueError):
        verify_manifest(tampered)
    tampered = {**manifest, "flow": {**manifest["flow"], "validation_rmse_cm_s": 0.0}}
    with pytest.raises(ValueError, match="hash"):
        verify_manifest(tampered)


def test_stale_and_restarted_camera_sessions_block_and_mark_old_receipt(env):
    client, runtime, _ = env
    request, flow = commission(client, runtime.camera)
    request = admit_and_observe(client, runtime.camera, request, flow)
    manifest = post(client, "/field-sessions", request)["manifest"]

    runtime.camera.frozen = True
    stale = post(client, "/field-sessions/preflight", request)
    assert steps(stale)["camera_session"] == ("BLOCKED", "CAMERA_STALE")
    assert stale["status"] == "BLOCKED"
    stale_receipt = client.get(f"/api/v1/field-sessions/{manifest['manifest_id']}").json()
    assert stale_receipt["is_current"] is False
    assert "CAMERA_STALE_OR_UNAVAILABLE" in stale_receipt["stale_reasons"]

    post(client, "/camera/start", {"device_index": 1})  # operator restarts the device
    restarted = post(client, "/field-sessions/preflight", request)
    assert steps(restarted)["camera_session"] == ("BLOCKED", "CAMERA_SESSION_CHANGED")
    assert steps(restarted)["first_source_observation"][0] == "BLOCKED"
    assert client.post("/api/v1/field-sessions", headers=AUTH, json=request).status_code == 409
    old = client.get(f"/api/v1/field-sessions/{manifest['manifest_id']}").json()
    assert old["manifest"] == manifest and old["is_current"] is False
    assert "CAMERA_SESSION_ENDED" in old["stale_reasons"]
    # Old artifacts cannot be relabelled with the new session.
    moved = post(client, "/field-sessions/preflight", {**request, "camera_session_id": runtime.camera.session_id})
    assert steps(moved)["water_plane_mapping"] == ("BLOCKED", "CALIBRATION_OTHER_SESSION")
    assert len(runtime.store.list(KIND)) == 1


@pytest.mark.parametrize("scale,check_scale,code", [
    (10.0, 10.0, "MAPPING_SCALE_IMPLAUSIBLE"),  # everything entered in millimetres
    (10.0, 1.0, "MAPPING_NOT_APPROVED"),        # mapping in mm, check points in cm
])
def test_wrong_units_or_invalid_mapping_never_reach_ready(env, scale, check_scale, code):
    client, runtime, _ = env
    session = post(client, "/camera/start", {"device_index": 1})["session_id"]
    calibration = post(client, "/vision/calibrate", mapping(session, scale, check_scale))
    request = {"camera_session_id": session, "calibration_id": calibration["calibration_id"],
               "training_recording_ids": ["r1"], "validation_recording_ids": ["r2"],
               "flow_id": "f", "profile_id": "p"}
    assert steps(post(client, "/field-sessions/preflight", request))["water_plane_mapping"] == ("BLOCKED", code)
    if not calibration["approved"]:
        assert client.post("/api/v1/camera/record", headers=AUTH, json={
            "duration_s": 1, "calibration_id": calibration["calibration_id"]}).status_code == 409
    collinear = mapping(session)
    collinear["world_cm_points"] = [[0, 0], [1, 1], [2, 2], [3, 3]]
    assert client.post("/api/v1/vision/calibrate", headers=AUTH, json=collinear).status_code == 409
    assert no_manifest(runtime)


def test_overlapping_training_and_validation_recordings_are_refused(env):
    client, runtime, _ = env
    request, _ = commission(client, runtime.camera)
    shared = request["training_recording_ids"][0]
    overlap = {"training_recording_ids": request["training_recording_ids"],
               "validation_recording_ids": [shared], "bounds": BOUNDS}
    assert client.post("/api/v1/flow/fit-recordings", headers=AUTH, json=overlap).status_code == 409
    body = {**request, "validation_recording_ids": [shared], "profile_id": "p"}
    for path in ("/api/v1/field-sessions/preflight", "/api/v1/field-sessions"):
        assert client.post(path, headers=AUTH, json=body).status_code == 422
    # The real flow named with a swapped split does not match its frozen provenance.
    swapped = {**request, "training_recording_ids": request["validation_recording_ids"],
               "validation_recording_ids": request["training_recording_ids"], "profile_id": "p"}
    assert steps(post(client, "/field-sessions/preflight", swapped))["recorded_flow"] == ("BLOCKED", "FLOW_SPLIT_MISMATCH")
    assert no_manifest(runtime)


def test_unsupported_flow_cannot_become_a_measured_profile(env):
    client, runtime, _ = env
    request, flow = commission(client, runtime.camera, validation_at=(5, 20), coverage_radius_cm=2)
    assert flow["diagnostics"]["validation_coverage_fraction"] < 0.9
    refused = client.post("/api/v1/profiles", headers=AUTH, json=profile_body(request["calibration_id"], flow))
    assert refused.status_code == 409
    preflight = post(client, "/field-sessions/preflight", {**request, "profile_id": "never-admitted"})
    assert steps(preflight)["recorded_flow"] == ("BLOCKED", "FLOW_UNSUPPORTED")
    assert steps(preflight)["measured_profile"][0] == "MISSING"
    assert no_manifest(runtime)


def test_rig_disturbance_then_revalidation_requires_a_fresh_case(env):
    client, runtime, _ = env
    request, flow = commission(client, runtime.camera)
    request = admit_and_observe(client, runtime.camera, request, flow)
    first = post(client, "/field-sessions", request)["manifest"]

    post(client, "/rig/disturbed", {})
    disturbed = post(client, "/field-sessions/preflight", request)
    assert steps(disturbed)["rig_state"] == ("BLOCKED", "RIG_REVALIDATION_REQUIRED")
    assert steps(disturbed)["first_source_observation"][0] == "BLOCKED"
    assert client.post("/api/v1/field-sessions", headers=AUTH, json=request).status_code == 409
    old = client.get(f"/api/v1/field-sessions/{first['manifest_id']}").json()
    assert old["is_current"] is False and "RIG_CHANGED_AFTER_RECEIPT" in old["stale_reasons"]

    drift = record(client, runtime.camera, at=(5, 10), profile_id=request["profile_id"])
    check = post(client, "/rig/revalidate", {"profile_id": request["profile_id"], "recording_id": drift["id"],
                 "checks": {k: True for k in ATTEST if k != "coordinates_measured_in_cm"}})
    revalidated_old_case = post(client, "/field-sessions/preflight", {**request, "rig_check_id": check["id"]})
    assert steps(revalidated_old_case)["rig_state"][0] == "PASSED"
    assert steps(revalidated_old_case)["first_source_observation"] == ("BLOCKED", "OBSERVATION_NOT_CURRENT")

    fresh = record(client, runtime.camera, at=(6, 11), profile_id=request["profile_id"])
    case = post(client, f"/recordings/{fresh['id']}/case", {"observation_type": "trajectory"})
    renewed = post(client, "/field-sessions", {**request, "first_case_id": case["id"], "rig_check_id": check["id"]})
    assert renewed["is_current"] is True
    assert renewed["manifest"]["rig_check_id"] == check["id"]
    assert renewed["manifest"]["manifest_id"] != first["manifest_id"]
    assert client.get(f"/api/v1/field-sessions/{first['manifest_id']}").json()["is_current"] is False


@pytest.mark.parametrize("change", ["rig", "stop", "camera"])
def test_freeze_rechecks_state_after_initial_readiness_before_saving(env, monkeypatch, change):
    client, runtime, _ = env
    request, flow = commission(client, runtime.camera)
    request = FieldSessionInput(**admit_and_observe(client, runtime.camera, request, flow))
    service = FieldSessionService(runtime)
    original = service.evaluate
    calls = 0

    def change_after_initial_check(body):
        nonlocal calls
        steps, manifest = original(body)
        calls += 1
        if calls == 1:
            assert manifest is not None
            if change == "rig":
                runtime.store.put("rig_change", {"changed_at": time.time(), "reason": "operator_reported"})
            elif change == "stop":
                runtime.store.stop_case(body.first_case_id)
            else:
                runtime.camera.start(1)
        return steps, manifest

    monkeypatch.setattr(service, "evaluate", change_after_initial_check)
    with pytest.raises(Blocked):
        service.create(request)
    assert calls == 2
    assert no_manifest(runtime)


def test_queued_backdated_rig_change_cannot_remain_current_after_commit(env, monkeypatch):
    import apps.api.reeftrace_api.services.field_sessions as field_service

    client, runtime, _ = env
    request, flow = commission(client, runtime.camera)
    request = FieldSessionInput(**admit_and_observe(client, runtime.camera, request, flow))
    service = FieldSessionService(runtime)
    sealed, release, writer_started = threading.Event(), threading.Event(), threading.Event()
    original = field_service.seal

    def pause_at_commit_boundary(body):
        result = original(body)
        sealed.set()
        assert release.wait(5)
        return result

    def queued_disturbance():
        # A route can create this timestamp before waiting for the write lock.
        changed_at = time.time() - 100
        writer_started.set()
        return runtime.store.put("rig_change", {"changed_at": changed_at, "reason": "operator_reported"})

    monkeypatch.setattr(field_service, "seal", pause_at_commit_boundary)
    with ThreadPoolExecutor(max_workers=2) as workers:
        freezing = workers.submit(service.create, request)
        try:
            assert sealed.wait(5)
            assert not runtime.camera.lock.acquire(blocking=False), "Camera lifecycle must be pinned during commit"
            changing = workers.submit(queued_disturbance)
            assert writer_started.wait(2)
            assert not changing.done(), "Rig writer must wait until the receipt commit completes"
        finally:
            release.set()
        receipt = freezing.result(timeout=5)
        change = changing.result(timeout=5)
    assert change["changed_at"] < receipt["manifest"]["created_at"]
    assert receipt["manifest"]["rig_change_id"] is None
    detail = service.detail(receipt["manifest"]["manifest_id"])
    assert detail["is_current"] is False
    assert "RIG_CHANGED_AFTER_RECEIPT" in detail["stale_reasons"]


@pytest.mark.parametrize("unsafe", ["contact@example.test", "+15555550123", "/private/frames",
                                    "ck-FAKE-NOT-A-REAL-KEY"])
def test_unsafe_artifact_references_are_blocked_without_echo_or_capture(env, monkeypatch, unsafe):
    client, runtime, _ = env
    def forbidden_capture():
        raise AssertionError("Identifier validation must not capture a frame")
    monkeypatch.setattr(runtime.camera, "image", forbidden_capture)
    request = {"camera_session_id": unsafe}
    preflight = post(client, "/field-sessions/preflight", request)
    assert preflight["status"] == "BLOCKED"
    assert all(step["code"] == "UNSAFE_IDENTIFIER" for step in preflight["steps"])
    assert unsafe not in json.dumps(preflight)
    response = client.post("/api/v1/field-sessions", headers=AUTH, json=request)
    assert response.status_code == 409 and unsafe not in response.text
    assert no_manifest(runtime)


def test_freeform_profile_source_is_withheld_before_it_can_enter_a_receipt(env):
    _, runtime, _ = env
    unsafe = "ck-FAKE-NOT-A-REAL-KEY"
    flow = {"diagnostics": {"validation_rmse_cm_s": 0.01}}
    profile = runtime.store.put("profile", {"data_origin": "MEASURED_TANK", "calibration_id": "cal-policy",
        "flow": flow, "max_validation_rmse_cm_s": 1, "revalidation_max_rmse_cm_s": 1,
        "sources": [{"id": "A"}, {"id": unsafe}], "observation_polygon_cm": [[0, 0], [1, 0], [1, 1]]})
    service = FieldSessionService(runtime)
    step, value = service._profile(FieldSessionInput(camera_session_id="usb-policy",
        calibration_id="cal-policy", profile_id=profile["id"]), flow)
    assert value is None and step["code"] == "UNSAFE_SOURCE_IDENTIFIERS"
    assert unsafe not in json.dumps(step)
    assert no_manifest(runtime)


def test_public_receipt_reads_sanitize_invalid_stored_identifier_errors(env):
    from pathlib import Path

    client, runtime, _ = env
    source = Path(__file__).parents[1] / "fixtures/team_handoff/field_manifest_v1.json"
    manifest = json.loads(source.read_text())
    unsafe = "ck-FAKE-NOT-A-REAL-KEY"
    manifest["profile"]["source_ids"] = ["A", unsafe]
    runtime.store.put(KIND, manifest, manifest["manifest_id"])
    for path in ("/api/v1/field-sessions", "/api/v1/field-sessions/" + manifest["manifest_id"]):
        response = client.get(path)
        assert response.status_code == 409
        assert unsafe not in response.text
        assert response.json()["detail"] == "Field receipt has invalid public fields; source values were withheld"
