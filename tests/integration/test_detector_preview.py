"""Live display HTTP flow over a synthetic pre-existing camera buffer, no devices."""
from __future__ import annotations

import base64
import copy
import json
import time
from datetime import UTC, datetime
from types import SimpleNamespace

import cv2
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.api.reeftrace_api.services import detector_preview
from apps.vision.reeftrace_vision.calibration import fit_homography
from apps.vision.reeftrace_vision.foreground import EmptyTankReference
from apps.vision.reeftrace_vision.surface_token import surface_policy

TOKEN = "live-preview-synthetic-only"
AUTH = {"Authorization": "Bearer " + TOKEN}
BASE = "/api/v1/camera/detector-preview"
WIDTH, HEIGHT = 320, 240
POLYGON = [[20, 20], [300, 20], [300, 220], [20, 220]]
GREEN = (30, 180, 40)


class ExistingBuffer:
    """A prepared buffer, not a camera that the endpoint can start or capture."""

    stale_s = 2.0

    def __init__(self, image):
        self.session_id = "usb-current-synthetic"
        self.running = True
        self.sequence = 0
        self.on_read = None
        self.set_frame(image)

    def set_frame(self, image):
        ok, encoded = cv2.imencode(".jpg", image)
        assert ok
        self.sequence += 1
        self.frame = {"jpeg": encoded.tobytes(), "session_id": self.session_id,
                      "sequence": self.sequence, "received_mono_s": time.monotonic(),
                      "received_utc": datetime.now(UTC).isoformat(),
                      "width": image.shape[1], "height": image.shape[0],
                      "backend": "SYNTHETIC_EXISTING_BUFFER"}

    def status(self):
        age = time.monotonic() - self.frame["received_mono_s"]
        return {"running": self.running, "fresh": self.running and 0 <= age <= self.stale_s,
                "session_id": self.session_id, "width": self.frame["width"],
                "height": self.frame["height"], "age_s": age, "sequence": self.sequence}

    def image(self):
        frame = dict(self.frame)
        image = cv2.imdecode(np.frombuffer(frame["jpeg"], np.uint8), cv2.IMREAD_COLOR)
        if self.on_read is not None:
            self.on_read()
        return image, frame

    def start(self, *_args, **_kwargs):
        raise AssertionError("Detector display must not open or start a camera")

    def stop(self):
        raise AssertionError("Detector display must not stop a camera")


@pytest.fixture
def env(tmp_path, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("No actual device or provider is authorized in these tests")

    monkeypatch.setattr(cv2, "VideoCapture", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    app = create_app(Settings(data_dir=tmp_path, local_token=TOKEN))
    runtime = app.state.runtime
    gray = np.random.default_rng(774).integers(80, 150, (HEIGHT, WIDTH), np.uint8)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    floor = np.repeat(gray[:, :, None], 3, axis=2)
    reference = EmptyTankReference([floor.copy() for _ in range(5)])
    reference_id = reference.fingerprint + "-old-pose"
    folder = tmp_path / "token_references"
    folder.mkdir()
    np.savez_compressed(folder / (reference_id + ".npz"), **reference.to_arrays())
    runtime.store.put("token_reference", {**reference.describe(), "reference_id": reference_id,
        "content_id": reference.fingerprint, "camera_session_id": "usb-historical-background",
        "captured_at": 1.0, "rig_change_at_capture": None}, reference_id)
    fit = [[0, 0], [319, 0], [319, 239], [0, 239]]
    checks = [[30, 30], [270, 40], [120, 200]]
    cm = lambda pairs: [[x / 10, y / 10] for x, y in pairs]
    source = fit_homography(fit, cm(fit), checks, cm(checks), max_error_cm=0.5,
        image_size_px=[WIDTH, HEIGHT], camera_session_id="usb-original-measurements")
    source["id"] = source["calibration_id"]
    bundle = {"schema_version": "nemo_saved_calibration_v1", "calibration": source,
              "calibration_json": json.dumps(source, sort_keys=True, allow_nan=False)}
    camera = ExistingBuffer(floor)
    runtime.camera = camera
    body = {"source": bundle, "reference_id": reference_id, "detection_polygon_px": POLYGON}
    client = TestClient(app)  # No lifespan: no background worker is started.
    yield SimpleNamespace(client=client, runtime=runtime, app=app, camera=camera,
        floor=floor, reference=reference, reference_id=reference_id, body=body, tmp_path=tmp_path)
    client.close()


def configure(env):
    response = env.client.post(BASE + "/config", headers=AUTH, json=env.body)
    assert response.status_code == 200, response.text
    return response.json()


def configure_marker(env):
    env.runtime.store.put("detector_replay", {
        "report_id": "saved-green-development", "data_origin": "LOCAL_SAVED_FOOTAGE_REPLAY",
        "purpose": "DEVELOPMENT_REGRESSION", "validation_status": "UNVALIDATED",
        "measured_flow_eligible": False, "policy": {"id": surface_policy()["policy_id"],
                                                   "sha256": surface_policy()["policy_sha256"]},
        "clips": [{"id": "synthetic-development", "image_size_px": [WIDTH, HEIGHT],
                   "points": [{"observed": True, "area_px": 600.0}]}],
    }, "saved-green-development")
    env.body["detector_mode"] = "saved_green_marker_preview_v2"
    return configure(env)


def poll(env, config, status=200):
    response = env.client.get(BASE + "/" + config["preview_id"], headers=AUTH)
    assert response.status_code == status, response.text
    return response


def assert_no_admission(env):
    for kind in ("recording", "frame", "calibration", "profile", "flow", "field_session",
                 "estimated_rehearsal", "estimated_rehearsal_frame", "token_size", "rig_change"):
        assert env.runtime.store.list(kind) == []
    assert env.runtime.store.cases() == []
    assert not (env.tmp_path / "estimated_rehearsals").exists()
    assert len(list((env.tmp_path / "token_references").iterdir())) == 1


def cap_frame(env, centers=((140, 110),), shift=(0, 0)):
    image = env.floor.copy()
    for center in centers:
        cv2.circle(image, center, 14, GREEN, -1)
    if shift != (0, 0):
        image = cv2.warpAffine(image, np.float32([[1, 0, shift[0]], [0, 1, shift[1]]]),
                               (WIDTH, HEIGHT), borderMode=cv2.BORDER_REFLECT)
    env.camera.set_frame(image)


def test_actual_router_uses_historical_setup_and_exact_live_buffer_without_approval(env):
    config = configure(env)
    assert config["camera_session_id"] == env.camera.session_id
    assert config["source_camera_session_id"] == "usb-original-measurements"
    assert config["reference_camera_session_id"] == "usb-historical-background"
    assert config["validation_status"] == "UNVALIDATED"
    assert config["calibration_id"] is config["profile_id"] is config["case_id"] is None
    assert config["current_alignment_verified"] is config["approved_for_inference"] is False
    assert config["measured_flow_eligible"] is False
    assert config["policy"]["policy_id"] == "foreground_green_cap_v1"
    cap_frame(env)
    response = poll(env, config)
    result = response.json()
    assert response.headers["Cache-Control"] == "no-store"
    assert result["observed"] and result["reason"] is None
    assert result["sequence"] == env.camera.frame["sequence"]
    assert result["received_utc"] == env.camera.frame["received_utc"]
    assert base64.b64decode(result["jpeg_data_url"].split(",", 1)[1]) == env.camera.frame["jpeg"]
    assert result["point"]["pixel_x"] == pytest.approx(140, abs=1)
    assert result["point"]["estimated_x_cm"] == pytest.approx(14, abs=.1)
    assert result["point"]["estimated_y_cm"] == pytest.approx(11, abs=.1)
    assert "x_cm" not in result["point"] and "y_cm" not in result["point"]
    assert env.camera.running
    assert_no_admission(env)


def test_raw_jpeg_overlay_undoes_permitted_alignment_but_estimates_use_reference_pixels(env):
    config = configure(env)
    cap_frame(env, shift=(4, 2))
    result = poll(env, config).json()
    assert result["alignment"]["applied"]
    point = result["point"]
    assert point["pixel_x"] == pytest.approx(144, abs=1)
    assert point["pixel_y"] == pytest.approx(112, abs=1)
    assert point["reference_pixel_x"] == pytest.approx(140, abs=1)
    assert point["estimated_x_cm"] == pytest.approx(14, abs=.1)
    assert point["pixel_x"] - point["reference_pixel_x"] == result["alignment"]["dx_px"]
    x, y, width, height = point["bbox_px"]
    assert x <= 144 <= x + width and y <= 112 <= y + height


@pytest.mark.parametrize("centers,reason", [((), "NO_TOKEN"), (((90, 100), (220, 120)), "MULTIPLE_TOKENS")])
def test_missing_and_multiple_caps_remain_gaps_without_estimated_position(env, centers, reason):
    config = configure(env)
    cap_frame(env, centers)
    result = poll(env, config).json()
    assert result["observed"] is False and result["point"] is None and result["reason"] == reason
    assert all("estimated_x_cm" not in point for point in result["detections"])
    assert_no_admission(env)


@pytest.mark.parametrize("scene", ["brightness", "camera_move", "obstruction"])
def test_scene_limits_remain_gaps_and_never_bypass_the_frozen_policy(env, scene):
    config = configure(env)
    image = env.floor.copy()
    if scene == "brightness":
        image = (image.astype(float) * .65).astype(np.uint8)
    elif scene == "camera_move":
        image = cv2.warpAffine(image, np.float32([[1, 0, 16], [0, 1, 0]]), (WIDTH, HEIGHT),
                               borderMode=cv2.BORDER_REFLECT)
    else:
        cv2.rectangle(image, (80, 50), (240, 190), (0, 0, 0), -1)
    env.camera.set_frame(image)
    result = poll(env, config).json()
    assert not result["observed"] and result["point"] is None and result["detections"] == []
    assert result["reason"] in {"SCENE_CHANGED", "VIEW_OBSTRUCTED"}
    assert result["scene_rejection"]
    assert_no_admission(env)


@pytest.mark.parametrize("path,method", [("/references", "get"), ("/config", "post"), ("/unknown", "get")])
def test_all_preview_endpoints_require_operator_and_are_disabled_in_cloud(env, path, method):
    request = getattr(env.client, method)
    kwargs = {"json": env.body} if method == "post" else {}
    assert request(BASE + path, **kwargs).status_code == 401
    env.app.state.deployment_profile = "cloud_software_demo"
    rejected = request(BASE + path, headers=AUTH, **kwargs)
    assert rejected.status_code == 503 and rejected.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("change", ["stopped", "stale", "session", "size", "frame_session", "timestamp", "jpeg"])
def test_no_stale_or_mismatched_frame_can_be_presented_as_live(env, change):
    config = configure(env)
    cap_frame(env)
    if change == "stopped":
        env.camera.running = False
    elif change == "stale":
        env.camera.frame["received_mono_s"] -= 30
    elif change == "session":
        env.camera.session_id = "usb-restarted"
    elif change == "size":
        env.camera.frame["width"] += 1
    elif change == "frame_session":
        env.camera.frame["session_id"] = "usb-previous"
    elif change == "timestamp":
        env.camera.frame["received_mono_s"] = float("nan")
    else:
        env.camera.frame["jpeg"] = b"not a jpeg"
    # Invalid JPEG cannot decode, so provide a correctly sized synthetic BGR
    # image while preserving the deliberately invalid buffered bytes.
    if change == "jpeg":
        env.camera.image = lambda: (env.floor.copy(), dict(env.camera.frame))
    assert "jpeg_data_url" not in poll(env, config, 409).json()
    assert_no_admission(env)


def test_camera_restart_during_detection_and_active_recording_are_rejected(env):
    config = configure(env)
    cap_frame(env)
    env.camera.on_read = lambda: setattr(env.camera, "session_id", "usb-restarted-during-read")
    poll(env, config, 409)
    env.camera.on_read = None
    env.camera.session_id = config["camera_session_id"]
    env.runtime.record_lock._locked = True
    try:
        assert "paused" in poll(env, config, 409).json()["detail"]
    finally:
        env.runtime.record_lock._locked = False
    assert_no_admission(env)


def test_repeated_buffer_sequence_is_cached_but_not_relabelled_new_observation(env, monkeypatch):
    config = configure(env)
    cap_frame(env)
    first = poll(env, config).json()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Repeated sequence should not rerun detection")

    monkeypatch.setattr(detector_preview, "surface_token_diagnostic", forbidden)
    repeated = poll(env, config).json()
    assert repeated["sequence"] == first["sequence"]
    assert repeated["point"] == first["point"]
    assert repeated["age_s"] >= first["age_s"]
    env.camera.frame["received_mono_s"] += .001
    poll(env, config, 409)


def test_reference_listing_is_image_free_and_configuration_does_not_read_camera_buffer(env, monkeypatch):
    def forbidden():
        raise AssertionError("Configuration must not read a camera frame")

    monkeypatch.setattr(env.camera, "image", forbidden)
    response = env.client.get(BASE + "/references", headers=AUTH)
    assert response.status_code == 200
    refs = response.json()["references"]
    assert refs[0]["reference_id"] == env.reference_id and refs[0]["full_frame"]
    assert "path" not in json.dumps(refs) and "jpeg" not in json.dumps(refs)
    configure(env)
    assert_no_admission(env)


@pytest.mark.parametrize("kind", ["tampered", "missing_raw", "dimensions", "polygon"])
def test_invalid_historical_source_or_declared_region_cannot_configure_preview(env, kind):
    body = copy.deepcopy(env.body)
    if kind == "tampered":
        body["source"]["calibration"]["homography_image_to_cm"][0][0] += .01
    elif kind == "missing_raw":
        del body["source"]["calibration_json"]
    elif kind == "dimensions":
        env.camera.frame["width"] = 640
    else:
        body["detection_polygon_px"][0][0] = -1
    response = env.client.post(BASE + "/config", headers=AUTH, json=body)
    assert response.status_code in {409, 422}
    assert_no_admission(env)


def test_preview_id_cannot_be_promoted_into_recording_or_source_evidence(env):
    config = configure(env)
    for path, body in (("/camera/record", {"calibration_id": config["preview_id"], "duration_s": 1}),
                       (f"/recordings/{config['preview_id']}/case", {})):
        response = env.client.post("/api/v1" + path, headers=AUTH, json=body)
        assert response.status_code in {404, 409, 422}
    assert_no_admission(env)


def test_marker_mode_is_explicit_and_discloses_incompatible_foreground_without_approving_size(env):
    config = configure_marker(env)
    assert config["detector_mode"] == "saved_green_marker_preview_v2"
    assert config["policy"]["segmentation"] == "direct_green_hsv_without_background_subtraction"
    assert config["marker_area_source"]["area_px_range"] == [210, 1800]
    image = (env.floor.astype(float) * .65).astype(np.uint8)
    cv2.circle(image, (140, 110), 14, GREEN, -1)
    cv2.circle(image, (80, 80), 4, GREEN, -1)  # Too small under saved development area.
    cv2.rectangle(image, (30, 170), (250, 177), GREEN, -1)  # Static green border is elongated.
    env.camera.set_frame(image)
    result = poll(env, config).json()
    assert result["observed"] and result["reason"] is None
    assert result["saved_foreground_status"] == "SCENE_CHANGED"
    assert result["saved_foreground_rejection"]
    assert result["scene_rejection"] is None
    assert len(result["detections"]) == 1
    assert result["point"]["pixel_x"] == pytest.approx(140, abs=1)
    assert result["validation_status"] == "UNVALIDATED"
    assert result["calibration_id"] is result["profile_id"] is result["case_id"] is None
    assert result["approved_for_inference"] is result["measured_flow_eligible"] is False
    assert_no_admission(env)


def test_marker_translation_can_exceed_foreground_eight_pixel_gate_but_is_only_estimated(env):
    config = configure_marker(env)
    cap_frame(env, shift=(4, 18))
    result = poll(env, config).json()
    assert result["saved_foreground_status"] == "SCENE_CHANGED"
    assert result["alignment"]["method"] == "orb_translation_estimate_v1"
    assert result["alignment"]["inlier_count"] >= 15
    assert result["point"]["pixel_x"] == pytest.approx(144, abs=1)
    assert result["point"]["pixel_y"] == pytest.approx(128, abs=1)
    assert result["point"]["estimated_x_cm"] == pytest.approx(14, abs=.2)
    assert result["point"]["estimated_y_cm"] == pytest.approx(11, abs=.2)


def test_marker_registration_failure_keeps_only_raw_pixels_and_never_invents_cm(env, monkeypatch):
    config = configure_marker(env)
    cap_frame(env)
    monkeypatch.setattr(detector_preview.DetectorPreviewService, "_marker_alignment",
                        lambda *_args: (None, "Synthetic rejected registration"))
    result = poll(env, config).json()
    assert result["observed"] and result["alignment"] is None
    assert result["alignment_rejection"] == "Synthetic rejected registration"
    assert result["point"]["pixel_x"] == pytest.approx(140, abs=1)
    for field in ("reference_pixel_x", "reference_pixel_y", "estimated_x_cm", "estimated_y_cm"):
        assert result["point"][field] is None
    assert_no_admission(env)


def test_marker_mode_refuses_absent_or_retired_development_area_source(env):
    env.body["detector_mode"] = "saved_green_marker_preview_v2"
    missing = env.client.post(BASE + "/config", headers=AUTH, json=env.body)
    assert missing.status_code == 404
    configure_marker(env)
    old = env.runtime.store.get("detector_replay", "saved-green-development")
    old["report_id"] = "obsolete-policy-report"
    old["policy"]["sha256"] = "0" * 64
    env.runtime.store.put("detector_replay", old, old["report_id"])
    rejected = env.client.post(BASE + "/config", headers=AUTH, json=env.body)
    assert rejected.status_code == 409 and "predates" in rejected.json()["detail"]
    assert_no_admission(env)


def test_marker_mode_refuses_retired_policy_id_even_when_hash_echoes_current_policy(env):
    configure_marker(env)
    old = env.runtime.store.get("detector_replay", "saved-green-development")
    old["report_id"] = "obsolete-policy-name"
    old["policy"]["id"] = "compact_cap_v1"
    env.runtime.store.put("detector_replay", old, old["report_id"])
    rejected = env.client.post(BASE + "/config", headers=AUTH, json=env.body)
    assert rejected.status_code == 409 and "current-policy" in rejected.json()["detail"]
    assert_no_admission(env)


def test_marker_v2_keeps_dim_green_cap_but_rejects_dim_elongated_filter_and_tiny_fleck(env):
    config = configure_marker(env)
    assert config["policy"]["policy_id"] == "saved_green_marker_preview_v2"
    assert config["policy"]["green_hsv_lower"] == [35, 80, 20]
    assert surface_policy()["green_hsv_lower"] == [35, 80, 40]  # Strict detector stays unchanged.
    image = env.floor.copy()
    dim_green = (12, 35, 10)  # HSV value 35: below v1 display threshold, above v2's fixed 20.
    cv2.circle(image, (140, 110), 14, dim_green, -1)
    cv2.rectangle(image, (30, 170), (250, 177), dim_green, -1)
    cv2.circle(image, (80, 80), 4, dim_green, -1)
    env.camera.set_frame(image)
    result = poll(env, config).json()
    assert result["detector_mode"] == "saved_green_marker_preview_v2"
    assert result["observed"] and result["point"]["pixel_x"] == pytest.approx(140, abs=1)
    assert len(result["detections"]) == 1
    assert result["diagnostics"]["rejection_counts"]["ELONGATED_COMPONENT"] >= 1
    assert result["diagnostics"]["rejection_counts"]["AREA_OUT_OF_RANGE"] >= 1
    assert result["validation_status"] == "UNVALIDATED"
    assert result["approved_for_inference"] is False
    assert_no_admission(env)


def test_marker_v2_still_rejects_a_green_blob_below_fixed_value_twenty(env):
    config = configure_marker(env)
    image = env.floor.copy()
    cv2.circle(image, (140, 110), 14, (3, 12, 3), -1)
    env.camera.set_frame(image)
    result = poll(env, config).json()
    assert result["observed"] is False and result["reason"] == "NO_TOKEN"
    assert result["point"] is None
    assert_no_admission(env)


def test_retired_marker_v1_cannot_be_requested_as_the_current_display_policy(env):
    env.body["detector_mode"] = "saved_green_marker_preview_v1"
    response = env.client.post(BASE + "/config", headers=AUTH, json=env.body)
    assert response.status_code == 422
    assert_no_admission(env)
