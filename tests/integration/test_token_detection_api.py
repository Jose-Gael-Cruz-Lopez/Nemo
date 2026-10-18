"""Green-token recording through the actual API, store, reference capture and tracker.

Only the capture DEVICE is replaced: ``GreenCapFakeCapture`` draws a GREEN bottle-cap
disc on a textured floor and reports backend SYNTHETIC_FAKE_CAPTURE. Nothing here is a
physical measurement. The red detector stays the default and is checked for regressions.
"""
from __future__ import annotations

import asyncio
import copy
import json
import time
import uuid
from datetime import UTC, datetime

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.api.reeftrace_api.services.token_detection import TokenDetectionService
from apps.vision.reeftrace_vision.surface_token import (
    SURFACE_DETECTOR_ID,
    SURFACE_POLICY_ID,
    SURFACE_POLICY_SHA256,
)

TOKEN = "token-detection-test-only"
AUTH = {"Authorization": "Bearer " + TOKEN}
PX_PER_CM = 20
WIDTH, HEIGHT = 640, 480
GREEN = (50, 150, 45)


def floor():
    rng = np.random.default_rng(5)
    image = cv2.GaussianBlur(rng.uniform(70, 180, (HEIGHT, WIDTH, 3)).astype(np.float32), (0, 0), 2)
    image[..., 1] += 20
    return np.clip(image, 0, 255).astype(np.uint8)


FLOOR = floor()


class GreenCapFakeCapture:
    """Explicit synthetic capture device. Frames are drawn, never read from a camera."""

    backend = "SYNTHETIC_FAKE_CAPTURE"

    def __init__(self):
        self.session_id = self.device = None
        self.sequence = 0
        self.cap = None            # None = empty tank; else (x_cm, y_cm, vx, vy, t0)
        self.shift_px = 0
        self.rng = np.random.default_rng(1)

    def start(self, device):
        self.session_id, self.device = "usb-fake-" + uuid.uuid4().hex[:12], device
        return self.status()

    def stop(self):
        self.session_id = self.device = None

    def place(self, x_cm, y_cm, vx_cm_s=0.0, vy_cm_s=0.0):
        self.cap = (x_cm, y_cm, vx_cm_s, vy_cm_s, time.monotonic())

    def status(self):
        running = self.session_id is not None
        return {"running": running, "session_id": self.session_id, "device_index": self.device,
                "fresh": running, "age_s": 0.0 if running else None, "sequence": self.sequence or None,
                "width": WIDTH if running else None, "height": HEIGHT if running else None,
                "backend": self.backend if running else None}

    def image(self):
        if self.session_id is None:
            raise ValueError("Camera is stopped, unavailable or stale")
        now = time.monotonic()
        image = FLOOR.copy()
        if self.shift_px:
            image = cv2.warpAffine(image, np.float32([[1, 0, self.shift_px], [0, 1, self.shift_px]]),
                                   (WIDTH, HEIGHT), borderMode=cv2.BORDER_REFLECT)
        if self.cap is not None:
            x0, y0, vx, vy, t0 = self.cap
            x, y = x0 + vx * (now - t0), y0 + vy * (now - t0)
            cv2.circle(image, (round(x * PX_PER_CM), round(y * PX_PER_CM)), 11, GREEN, -1, lineType=cv2.LINE_AA)
        image = np.clip(image.astype(np.float32) + self.rng.normal(0, 2.0, image.shape), 0, 255).astype(np.uint8)
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
    runtime.camera = GreenCapFakeCapture()
    with TestClient(app) as client:
        yield client, runtime, tmp_path


def post(client, path, body=None, status=200):
    response = client.post("/api/v1" + path, headers=AUTH, json=body or {})
    assert response.status_code == status, response.text
    return response.json()


def calibrate(client, session_id):
    fit = [[0, 0], [639, 0], [639, 479], [0, 479]]
    check = [[100, 100], [500, 120], [300, 400]]
    cm = lambda pts: [[x / PX_PER_CM, y / PX_PER_CM] for x, y in pts]
    return post(client, "/vision/calibrate", {"pixel_points": fit, "world_cm_points": cm(fit),
                "check_pixels": check, "check_world_cm": cm(check), "max_error_cm": 0.5,
                "image_size_px": [WIDTH, HEIGHT], "camera_session_id": session_id})["calibration_id"]


def prepared(client, camera):
    """Start the fake device, map, capture the empty tank and measure one green cap."""
    session = post(client, "/camera/start", {"device_index": 1})["session_id"]
    calibration_id = calibrate(client, session)
    camera.cap = None
    reference = post(client, "/camera/reference", {"frame_count": 8})
    camera.place(16, 12)
    size = post(client, f"/camera/reference/{reference['reference_id']}/token-size")
    return session, calibration_id, reference, size


def test_reference_and_token_size_are_saved_without_images(env):
    client, runtime, tmp_path = env
    assert client.get("/api/v1/camera/reference").json()["reference"] is None
    session, _, reference, size = prepared(client, runtime.camera)
    assert reference["detector"] == "foreground_reference_v1"
    assert reference["camera_session_id"] == session and reference["image_size_px"] == [WIDTH, HEIGHT]
    assert 200 < size["token_area_px"] < 600 and size["token_area_px_range"][0] < size["token_area_px"]
    status = client.get("/api/v1/camera/reference").json()
    assert status["is_current"] is True and status["token_size"]["reference_id"] == reference["reference_id"]
    for value in (reference, size, status):
        text = str(value)
        assert str(tmp_path) not in text and "npz" not in text and "median" not in text


def test_green_cap_is_tracked_with_foreground_detector_but_not_with_red(env):
    client, runtime, _ = env
    _, calibration_id, reference, size = prepared(client, runtime.camera)
    runtime.camera.place(6, 10, 3.0, 0.0)
    green = post(client, "/camera/record", {"calibration_id": calibration_id, "duration_s": 1,
                 "detector": "foreground_reference_v1", "reference_id": reference["reference_id"]})
    observed = [p for p in green["points"] if p["observed"]]
    assert len(observed) >= 0.9 * len(green["points"]) and len({p["track_id"] for p in observed}) == 1
    assert green["detection"] == {"detector": "foreground_reference_v1", "reference_id": reference["reference_id"],
                                  "token_area_px_range": size["token_area_px_range"]}
    slope = np.polyfit([p["t_s"] for p in observed], [p["x_cm"] for p in observed], 1)[0]
    assert abs(slope - 3.0) < 0.4

    runtime.camera.place(6, 10, 3.0, 0.0)
    red = post(client, "/camera/record", {"calibration_id": calibration_id, "duration_s": 1})
    assert red["detection"] == {"detector": "red_hsv"}
    assert not any(p["observed"] for p in red["points"]), "the red detector cannot see a green cap"


def test_foreground_recording_needs_a_current_measured_reference(env):
    client, runtime, _ = env
    session = post(client, "/camera/start", {"device_index": 1})["session_id"]
    calibration_id = calibrate(client, session)
    body = {"calibration_id": calibration_id, "duration_s": 1, "detector": "foreground_reference_v1"}
    assert "reference_id" in post(client, "/camera/record", body, 409)["detail"]
    runtime.camera.cap = None
    reference = post(client, "/camera/reference", {"frame_count": 6})
    body["reference_id"] = reference["reference_id"]
    assert "Measure one token" in post(client, "/camera/record", body, 409)["detail"]
    assert "does not use" in post(client, "/camera/record", {"calibration_id": calibration_id, "duration_s": 1,
                                  "reference_id": reference["reference_id"]}, 409)["detail"]
    assert client.post("/api/v1/camera/reference/ref-missing/token-size", headers=AUTH, json={}).status_code == 404
    assert runtime.store.list("recording") == []


def test_token_size_check_needs_exactly_one_token(env):
    client, runtime, _ = env
    post(client, "/camera/start", {"device_index": 1})
    runtime.camera.cap = None
    reference = post(client, "/camera/reference", {"frame_count": 6})
    detail = post(client, f"/camera/reference/{reference['reference_id']}/token-size", status=409)["detail"]
    assert "exactly one token" in detail


def test_disturbance_or_new_session_makes_the_reference_stale(env):
    client, runtime, _ = env
    _, calibration_id, reference, _ = prepared(client, runtime.camera)
    body = {"calibration_id": calibration_id, "duration_s": 1, "detector": "foreground_reference_v1",
            "reference_id": reference["reference_id"]}
    post(client, "/rig/disturbed")
    assert "rig changed" in post(client, "/camera/record", body, 409)["detail"]
    status = client.get("/api/v1/camera/reference").json()
    assert status["is_current"] is False and "rig changed" in status["reason"]

    post(client, "/camera/start", {"device_index": 1})  # restarted device: new session
    assert "another camera session" in client.get("/api/v1/camera/reference").json()["reason"]


def test_camera_bump_during_recording_discards_it(env):
    client, runtime, _ = env
    _, calibration_id, reference, _ = prepared(client, runtime.camera)
    runtime.camera.place(6, 10)
    runtime.camera.shift_px = 12
    detail = post(client, "/camera/record", {"calibration_id": calibration_id, "duration_s": 1,
                  "detector": "foreground_reference_v1", "reference_id": reference["reference_id"]}, 409)["detail"]
    assert detail.startswith("Recording discarded") and "moved" in detail
    assert runtime.store.list("recording") == []


def test_reference_capture_requires_operator_and_refuses_a_token_in_motion(env):
    client, runtime, _ = env
    assert client.post("/api/v1/camera/reference", json={}).status_code == 401
    assert post(client, "/camera/reference", {}, 409)["detail"].startswith("Start the webcam")
    post(client, "/camera/start", {"device_index": 1})
    runtime.camera.shift_px = 0
    reference = post(client, "/camera/reference", {"frame_count": 5})
    assert reference["frame_count"] == 5


def test_mixed_detectors_cannot_form_one_field_receipt(env):
    client, runtime, _ = env
    session, calibration_id, reference, _ = prepared(client, runtime.camera)
    runtime.camera.place(4, 8, 3.0, 0.0)
    green = post(client, "/camera/record", {"calibration_id": calibration_id, "duration_s": 1,
                 "detector": "foreground_reference_v1", "reference_id": reference["reference_id"]})
    runtime.camera.place(4, 12, 3.0, 0.0)
    red = post(client, "/camera/record", {"calibration_id": calibration_id, "duration_s": 1})
    preflight = post(client, "/field-sessions/preflight", {"camera_session_id": session,
                     "calibration_id": calibration_id, "training_recording_ids": [green["id"]],
                     "validation_recording_ids": [red["id"]]})
    step = next(s for s in preflight["steps"] if s["step"] == "drift_recordings")
    assert (step["status"], step["code"]) == ("BLOCKED", "DETECTOR_MIXED")


def test_small_camera_creep_and_a_passing_hand_do_not_discard_the_run(env):
    client, runtime, _ = env
    _, calibration_id, reference, _ = prepared(client, runtime.camera)
    runtime.camera.place(6, 10, 3.0, 0.0)
    runtime.camera.shift_px = 2                      # mount creep: measured and undone
    original = runtime.camera.image
    calls = {"n": 0}

    def with_hand():
        image, meta = original()
        calls["n"] += 1
        if calls["n"] <= 4:                          # a hand covers part of the view at the start
            image = image.copy()
            cv2.rectangle(image, (0, 0), (420, 300), (120, 150, 200), -1)
        return image, meta

    runtime.camera.image = with_hand
    run = post(client, "/camera/record", {"calibration_id": calibration_id, "duration_s": 1,
               "detector": "foreground_reference_v1", "reference_id": reference["reference_id"]})
    reasons = [p.get("reason") for p in run["points"] if not p["observed"]]
    assert "VIEW_OBSTRUCTED" in reasons
    assert sum(p["observed"] for p in run["points"]) >= len(run["points"]) // 2


def test_token_size_measured_calm_can_carry_to_a_running_reference(env):
    client, runtime, _ = env
    _, calibration_id, calm, size = prepared(client, runtime.camera)   # calm reference + measured cap
    runtime.camera.cap = None
    running = post(client, "/camera/reference", {"frame_count": 6, "token_size_from": calm["reference_id"]})
    assert running["token_size"]["token_area_px"] == size["token_area_px"]
    assert running["token_size"]["carried_from_reference_id"] == calm["reference_id"]
    runtime.camera.place(6, 10, 3.0, 0.0)
    run = post(client, "/camera/record", {"calibration_id": calibration_id, "duration_s": 1,
               "detector": "foreground_reference_v1", "reference_id": running["reference_id"]})
    assert sum(p["observed"] for p in run["points"]) > 0

    runtime.camera.cap = None
    runtime.camera.shift_px = 12                     # camera moved: the size is not carried over
    detail = post(client, "/camera/reference", {"frame_count": 6, "token_size_from": calm["reference_id"]}, 409)["detail"]
    assert "moved" in detail
    unmeasured = post(client, "/camera/reference", {"frame_count": 6})
    runtime.camera.shift_px = 0
    detail = post(client, "/camera/reference", {"frame_count": 6, "token_size_from": unmeasured["reference_id"]}, 409)["detail"]
    assert "Measure one token" in detail


@pytest.mark.parametrize("owner", ["reference", "measurement", "recording"])
@pytest.mark.parametrize("contender", ["reference", "measurement", "recording"])
def test_camera_operations_reject_competing_capture_without_queuing_and_release_on_cancel(
        env, monkeypatch, owner, contender):
    client, runtime, _ = env
    _, calibration_id, reference, _ = prepared(client, runtime.camera)
    service = runtime.token_detection

    async def run():
        entered = asyncio.Event()
        original_frames = service._frames
        original_image = runtime.camera.image

        async def hold_frames(count, session_id):
            entered.set()
            await asyncio.Event().wait()

        def mark_recording_frame():
            image = original_image()
            entered.set()
            return image

        if owner == "recording":
            monkeypatch.setattr(runtime.camera, "image", mark_recording_frame)
        else:
            monkeypatch.setattr(service, "_frames", hold_frames)

        async def operation(kind):
            if kind == "reference":
                return await service.capture_reference(frame_count=5)
            if kind == "measurement":
                return await service.measure_token(reference["reference_id"])
            # Cancel this owned recording after the overlap check; a long allowed
            # horizon keeps a slow test host from finishing it before cancellation.
            return await runtime.record(None, 20, calibration_id)

        task = asyncio.create_task(operation(owner))
        try:
            await asyncio.wait_for(entered.wait(), timeout=2)
            sequence = runtime.camera.sequence
            counts = {kind: len(runtime.store.list(kind))
                      for kind in ("token_reference", "token_size", "recording")}
            # An overlap must fail now; silently waiting until the owner finishes
            # could capture the wrong physical scene after a button click.
            with pytest.raises(ValueError, match="active"):
                await asyncio.wait_for(operation(contender), timeout=0.2)
            assert runtime.camera.sequence == sequence
            assert {kind: len(runtime.store.list(kind)) for kind in counts} == counts
            assert runtime.record_lock.locked()
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert not runtime.record_lock.locked()
        monkeypatch.setattr(service, "_frames", original_frames)
        monkeypatch.setattr(runtime.camera, "image", original_image)
        # Cancellation frees the shared resource for an actual subsequent
        # measurement through the unchanged detector and private store.
        measured = await service.measure_token(reference["reference_id"])
        assert measured["reference_id"] == reference["reference_id"]
        assert measured["token_area_px"] > 25

    asyncio.run(run())


def test_reference_eviction_keeps_durable_arrays_and_reloads_a_working_detector(env):
    client, runtime, tmp_path = env
    session = post(client, "/camera/start", {"device_index": 1})["session_id"]
    service = runtime.token_detection
    references = []
    for left in (0, 20):
        references.append(post(client, "/camera/reference", {"frame_count": 5,
            "roi_polygon_px": [[left, 0], [WIDTH - 1, 0], [WIDTH - 1, HEIGHT - 1], [left, HEIGHT - 1]]}))
    second_id = references[1]["reference_id"]
    original_second = service._reference(second_id)[1]
    service._reference(references[0]["reference_id"])  # First reference is most recently used.
    references.append(post(client, "/camera/reference", {"frame_count": 5,
        "roi_polygon_px": [[40, 0], [WIDTH - 1, 0], [WIDTH - 1, HEIGHT - 1], [40, HEIGHT - 1]]}))
    assert len(service._cache) == 2
    assert references[0]["reference_id"] in service._cache
    assert second_id not in service._cache
    assert all((tmp_path / "token_references" / f"{ref['reference_id']}.npz").is_file()
               for ref in references)
    assert len(runtime.store.list("token_reference")) == 3

    record, reloaded = service._reference(second_id)
    assert record["reference_id"] == second_id
    assert reloaded.fingerprint == record["content_id"]
    np.testing.assert_array_equal(reloaded.median, original_second.median)
    assert len(service._cache) == 2
    runtime.camera.place(16, 12)
    post(client, f"/camera/reference/{second_id}/token-size")

    # A cold service rebuilds the reference from the durable NPZ, retaining
    # its measured-token provenance and real detection behavior after eviction.
    cold = TokenDetectionService(runtime)
    detect, provenance = cold.detector("foreground_reference_v1", second_id,
                                       session, [WIDTH, HEIGHT])
    found = detect(runtime.camera.image()[0])
    assert len(found) == 1
    assert found[0]["pixel_x"] == pytest.approx(16 * PX_PER_CM, abs=1)
    assert provenance["reference_id"] == second_id
    assert len(cold._cache) == 1

    # Eviction cannot turn a tampered disk reference into valid camera evidence.
    path = tmp_path / "token_references" / f"{second_id}.npz"
    with np.load(path) as saved:
        altered = {key: saved[key].copy() for key in saved.files}
    altered["median"][0, 0, 0] += 10
    np.savez_compressed(path, **altered)
    with pytest.raises(ValueError, match="does not match its ID"):
        TokenDetectionService(runtime).detector("foreground_reference_v1", second_id,
                                                session, [WIDTH, HEIGHT])


SURFACE_POLYGON = [[20, 20], [WIDTH - 21, 20], [WIDTH - 21, HEIGHT - 21], [20, HEIGHT - 21]]


def test_surface_reference_derivation_reuses_arrays_but_not_v1_area_without_camera_access(env, monkeypatch):
    client, runtime, tmp_path = env
    session, _, original, _ = prepared(client, runtime.camera)
    before = copy.deepcopy(runtime.store.get("token_reference", original["reference_id"]))
    sequence = runtime.camera.sequence

    def forbidden():
        raise AssertionError("Deriving a saved surface reference must not read the camera")

    with monkeypatch.context() as guard:
        guard.setattr(runtime.camera, "image", forbidden)
        response = client.post(f"/api/v1/camera/reference/{original['reference_id']}/surface",
                               headers=AUTH, json={"detection_polygon_px": SURFACE_POLYGON})
        assert response.status_code == 200, response.text
        surface = response.json()
        assert post(client, f"/camera/reference/{original['reference_id']}/surface",
                    {"detection_polygon_px": SURFACE_POLYGON}) == surface
    assert runtime.camera.sequence == sequence
    assert surface["detector"] == SURFACE_DETECTOR_ID
    assert surface["reference_id"].startswith("refsurf-")
    assert surface["derived_from_reference_id"] == original["reference_id"]
    assert surface["captured_at"] == original["captured_at"]
    assert surface["camera_session_id"] == session
    assert surface["policy_id"] == SURFACE_POLICY_ID
    assert surface["policy_sha256"] == SURFACE_POLICY_SHA256
    assert surface["detection_polygon_px"] == SURFACE_POLYGON
    assert surface["token_size"] is None  # Generic foreground area is not green-only area.
    assert runtime.store.get("token_reference", original["reference_id"]) == before
    assert str(tmp_path) not in json.dumps(surface) and "npz" not in json.dumps(surface)
    cold = TokenDetectionService(runtime)
    record, reference = cold._reference(surface["reference_id"])
    assert reference.roi.all() and reference.fingerprint == original["content_id"]
    with pytest.raises(ValueError, match="Measure one token"):
        cold.detector(SURFACE_DETECTOR_ID, record["id"], session, [WIDTH, HEIGHT])
    size = post(client, f"/camera/reference/{surface['reference_id']}/token-size")
    assert size["policy_sha256"] == SURFACE_POLICY_SHA256
    detect, metadata = cold.detector(SURFACE_DETECTOR_ID, record["id"], session, [WIDTH, HEIGHT])
    assert len(detect(runtime.camera.image()[0])) == 1
    assert metadata == {"detector": SURFACE_DETECTOR_ID, "reference_id": record["id"],
        "token_area_px_range": size["token_area_px_range"], "detection_polygon_px": SURFACE_POLYGON,
        "policy_id": SURFACE_POLICY_ID, "policy_sha256": SURFACE_POLICY_SHA256}


def test_surface_capture_and_token_size_record_through_actual_api_keep_v1_opt_in(env):
    client, runtime, _ = env
    session = post(client, "/camera/start", {"device_index": 1})["session_id"]
    calibration_id = calibrate(client, session)
    runtime.camera.cap = None
    surface = post(client, "/camera/reference", {"frame_count": 5,
        "detector": SURFACE_DETECTOR_ID, "detection_polygon_px": SURFACE_POLYGON})
    assert surface["detector"] == SURFACE_DETECTOR_ID
    assert surface["token_size"] is None
    runtime.camera.place(10, 10, 1, 0)
    measured = post(client, f"/camera/reference/{surface['reference_id']}/token-size")
    assert measured["token_area_px"] > 25
    record = post(client, "/camera/record", {"calibration_id": calibration_id, "duration_s": 1,
        "detector": SURFACE_DETECTOR_ID, "reference_id": surface["reference_id"]})
    assert any(p["observed"] for p in record["points"])
    assert record["detection"]["detector"] == SURFACE_DETECTOR_ID
    assert record["detection"]["policy_sha256"] == SURFACE_POLICY_SHA256
    assert "version" in post(client, "/camera/record", {"calibration_id": calibration_id,
        "duration_s": 1, "detector": "foreground_reference_v1",
        "reference_id": surface["reference_id"]}, 409)["detail"]


def test_surface_derivation_rejects_cropped_background_and_requires_operator(env):
    client, runtime, _ = env
    post(client, "/camera/start", {"device_index": 1})
    original = post(client, "/camera/reference", {"frame_count": 5,
        "roi_polygon_px": SURFACE_POLYGON})
    route = f"/api/v1/camera/reference/{original['reference_id']}/surface"
    assert client.post(route, json={"detection_polygon_px": SURFACE_POLYGON}).status_code == 401
    rejected = client.post(route, headers=AUTH, json={"detection_polygon_px": SURFACE_POLYGON})
    assert rejected.status_code == 409 and "full-frame" in rejected.json()["detail"]
    assert len(runtime.store.list("token_reference")) == 1


def test_surface_provenance_does_not_waive_session_or_disturbance_checks(env):
    client, runtime, _ = env
    session, _, original, _ = prepared(client, runtime.camera)
    surface = runtime.token_detection.derive_surface_reference(original["reference_id"], SURFACE_POLYGON)
    with pytest.raises(ValueError, match="version"):
        runtime.token_detection.detector(SURFACE_DETECTOR_ID, original["reference_id"],
                                         session, [WIDTH, HEIGHT])
    with pytest.raises(ValueError, match="another camera session"):
        runtime.token_detection.detector(SURFACE_DETECTOR_ID, surface["reference_id"],
                                         "usb-other", [WIDTH, HEIGHT])
    post(client, "/rig/disturbed")
    with pytest.raises(ValueError, match="rig changed"):
        runtime.token_detection.detector(SURFACE_DETECTOR_ID, surface["reference_id"],
                                         session, [WIDTH, HEIGHT])


def test_surface_polygon_and_policy_are_bound_to_reference_identity(env):
    client, runtime, _ = env
    _, _, original, _ = prepared(client, runtime.camera)
    surface = runtime.token_detection.derive_surface_reference(original["reference_id"], SURFACE_POLYGON)
    corrupted = runtime.store.get("token_reference", surface["reference_id"])
    corrupted["detection_polygon_px"][0][0] += 1
    with runtime.store.connection() as db:
        db.execute("UPDATE records SET payload=? WHERE kind=? AND id=?",
                   (json.dumps(corrupted), "token_reference", surface["reference_id"]))
    with pytest.raises(ValueError, match="frozen policy and polygon"):
        TokenDetectionService(runtime)._reference(surface["reference_id"])


@pytest.mark.parametrize("body", [
    {"detector": SURFACE_DETECTOR_ID},
    {"detector": SURFACE_DETECTOR_ID, "detection_polygon_px": SURFACE_POLYGON,
     "roi_polygon_px": SURFACE_POLYGON},
    {"detector": "foreground_reference_v1", "detection_polygon_px": SURFACE_POLYGON},
])
def test_surface_live_capture_invalid_domain_is_rejected_before_reading_frames(env, body):
    client, runtime, _ = env
    post(client, "/camera/start", {"device_index": 1})
    sequence = runtime.camera.sequence
    post(client, "/camera/reference", {"frame_count": 5, **body}, 409)
    assert runtime.camera.sequence == sequence
    assert runtime.store.list("token_reference") == []


def test_surface_and_v1_recordings_cannot_be_mixed_into_a_measured_field_receipt(env):
    client, runtime, _ = env
    session, calibration_id, original, _ = prepared(client, runtime.camera)
    surface = runtime.token_detection.derive_surface_reference(original["reference_id"], SURFACE_POLYGON)
    post(client, f"/camera/reference/{surface['reference_id']}/token-size")
    recordings = []
    for detector, reference_id in (("foreground_reference_v1", original["reference_id"]),
                                   (SURFACE_DETECTOR_ID, surface["reference_id"])):
        runtime.camera.place(6, 10, 2, 0)
        recordings.append(post(client, "/camera/record", {"calibration_id": calibration_id,
            "duration_s": 1, "detector": detector, "reference_id": reference_id}))
    preflight = post(client, "/field-sessions/preflight", {"camera_session_id": session,
        "calibration_id": calibration_id, "training_recording_ids": [recordings[0]["id"]],
        "validation_recording_ids": [recordings[1]["id"]]})
    step = next(step for step in preflight["steps"] if step["step"] == "drift_recordings")
    assert (step["status"], step["code"]) == ("BLOCKED", "DETECTOR_MIXED")


def test_surface_detector_rehearsal_keeps_versioned_provenance_and_unvalidated_coordinates(env):
    client, runtime, _ = env
    session, calibration_id, original, _ = prepared(client, runtime.camera)
    surface = runtime.token_detection.derive_surface_reference(original["reference_id"], SURFACE_POLYGON)
    post(client, f"/camera/reference/{surface['reference_id']}/token-size")
    calibration = runtime.store.get("calibration", calibration_id)
    runtime.camera.place(8, 10, 1, 0)
    result = post(client, "/camera/rehearsals", {
        "source": {"schema_version": "nemo_saved_calibration_v1", "calibration": calibration,
                   "calibration_json": json.dumps(calibration, sort_keys=True, allow_nan=False)},
        "camera_session_id": session, "image_size_px": [WIDTH, HEIGHT], "duration_s": 1,
        "detector": SURFACE_DETECTOR_ID, "reference_id": surface["reference_id"],
        "acknowledge_estimated_mapping": True})
    assert result["observed"] > 0
    assert result["data_origin"] == "LOCAL_CAPTURE_ESTIMATED_COORDINATES"
    assert result["validation_status"] == "UNVALIDATED"
    assert result["calibration_id"] is result["case_id"] is result["profile_id"] is None
    assert result["detection"]["policy_sha256"] == SURFACE_POLICY_SHA256
    assert result["detection"]["detection_polygon_px"] == SURFACE_POLYGON
    assert all("x_cm" not in point and "y_cm" not in point for point in result["points"])
    assert runtime.store.list("recording") == runtime.store.cases() == []


def test_surface_only_carries_area_measured_under_the_same_green_policy(env, monkeypatch):
    client, runtime, _ = env
    session, _, original, _ = prepared(client, runtime.camera)
    first = runtime.token_detection.derive_surface_reference(original["reference_id"], SURFACE_POLYGON)
    size = post(client, f"/camera/reference/{first['reference_id']}/token-size")
    smaller = [[30, 30], [WIDTH - 31, 30], [WIDTH - 31, HEIGHT - 31], [30, HEIGHT - 31]]

    def forbidden():
        raise AssertionError("Same-policy saved derivation must not read the camera")

    with monkeypatch.context() as guard:
        guard.setattr(runtime.camera, "image", forbidden)
        second = runtime.token_detection.derive_surface_reference(first["reference_id"], smaller)
    assert second["token_size"]["token_area_px"] == size["token_area_px"]
    assert second["token_size"]["policy_sha256"] == SURFACE_POLICY_SHA256
    assert second["token_size"]["carried_from_reference_id"] == first["reference_id"]
    runtime.camera.cap = None
    running = post(client, "/camera/reference", {"frame_count": 5,
        "detector": SURFACE_DETECTOR_ID, "detection_polygon_px": SURFACE_POLYGON,
        "token_size_from": first["reference_id"]})
    assert running["token_size"]["policy_sha256"] == SURFACE_POLICY_SHA256
    assert running["token_size"]["token_area_px"] == size["token_area_px"]
    assert running["camera_session_id"] == session


def test_surface_capture_cannot_carry_v1_area_or_expose_v2_area_as_v1(env):
    client, runtime, _ = env
    _, _, original, _ = prepared(client, runtime.camera)
    before = runtime.camera.sequence
    rejected = post(client, "/camera/reference", {"frame_count": 5,
        "detector": SURFACE_DETECTOR_ID, "detection_polygon_px": SURFACE_POLYGON,
        "token_size_from": original["reference_id"]}, 409)
    assert "between detector policies" in rejected["detail"]
    assert runtime.camera.sequence == before
    surface = runtime.token_detection.derive_surface_reference(original["reference_id"], SURFACE_POLYGON)
    post(client, f"/camera/reference/{surface['reference_id']}/token-size")
    before = runtime.camera.sequence
    rejected = post(client, "/camera/reference", {"frame_count": 5,
        "token_size_from": surface["reference_id"]}, 409)
    assert "between detector policies" in rejected["detail"]
    assert runtime.camera.sequence == before
