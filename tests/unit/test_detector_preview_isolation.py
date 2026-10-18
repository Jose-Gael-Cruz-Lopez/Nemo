"""Display-only marker fallback cannot write scientific or detector-size evidence."""
from __future__ import annotations

import copy
import json
import threading
import time
from datetime import UTC, datetime
from types import SimpleNamespace

import cv2
import httpx
import numpy as np
import pytest

from apps.api.reeftrace_api.schemas.saved_calibrations import SavedCalibrationBundle
from apps.api.reeftrace_api.services.detector_preview import DetectorPreviewService
from apps.vision.reeftrace_vision.calibration import fit_homography
from apps.vision.reeftrace_vision.foreground import EmptyTankReference, SceneChanged
from apps.vision.reeftrace_vision.surface_token import surface_policy, surface_token_diagnostic

WIDTH, HEIGHT = 320, 240
POLYGON = [[20, 20], [300, 20], [300, 220], [20, 220]]


class ReadOnlyPreviewStore:
    def __init__(self):
        self.writes = []
        policy = surface_policy()
        self.replay = {"report_id": "surface-replay-synthetic-isolation",
                       "data_origin": "LOCAL_SAVED_FOOTAGE_REPLAY", "purpose": "DEVELOPMENT_REGRESSION",
                       "validation_status": "UNVALIDATED", "measured_flow_eligible": False,
                       "policy": {"id": policy["policy_id"], "sha256": policy["policy_sha256"]},
                       "clips": [{"id": "synthetic-isolation-clip", "image_size_px": [WIDTH, HEIGHT],
                                  "points": [{"observed": True, "area_px": 620.0}]}]}

    def list(self, kind, limit=100):
        return [copy.deepcopy(self.replay)] if kind == "detector_replay" else []

    def put(self, kind, *_args, **_kwargs):
        self.writes.append(kind)
        raise AssertionError("A display-only preview cannot persist evidence of any kind")


class ExistingSyntheticBuffer:
    stale_s = 2.0

    def __init__(self, image):
        self.session_id = "usb-current-isolation-fixture"
        self.running = True
        self.reads = 0
        self.image_bgr = image
        ok, encoded = cv2.imencode(".jpg", image)
        assert ok
        self.frame = {"session_id": self.session_id, "width": WIDTH, "height": HEIGHT,
                      "sequence": 1, "received_mono_s": time.monotonic(),
                      "received_utc": datetime.now(UTC).isoformat(), "jpeg": encoded.tobytes()}

    def status(self):
        return {"running": self.running, "fresh": True, "session_id": self.session_id,
                "width": WIDTH, "height": HEIGHT}

    def image(self):
        self.reads += 1
        return self.image_bgr.copy(), dict(self.frame)


@pytest.fixture
def env(tmp_path, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Preview may not open hardware, call providers or admit evidence")

    monkeypatch.setattr(cv2, "VideoCapture", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    gray = np.random.default_rng(520).integers(80, 160, (HEIGHT, WIDTH), dtype=np.uint8)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    floor = np.repeat(gray[:, :, None], 3, axis=2)
    reference = EmptyTankReference([floor.copy() for _ in range(5)])
    reference_id = reference.fingerprint + "-historical"
    record = {**reference.describe(), "reference_id": reference_id,
              "camera_session_id": "usb-old-background-fixture", "captured_at": 1.0}
    fit = [[0, 0], [319, 0], [319, 239], [0, 239]]
    checks = [[30, 30], [270, 40], [120, 200]]
    cm = lambda points: [[x / 10, y / 10] for x, y in points]
    source = fit_homography(fit, cm(fit), checks, cm(checks), max_error_cm=.5,
        image_size_px=[WIDTH, HEIGHT], camera_session_id="usb-original-survey-fixture")
    source["id"] = source["calibration_id"]
    bundle = SavedCalibrationBundle.model_validate({
        "schema_version": "nemo_saved_calibration_v1", "calibration": source,
        "calibration_json": json.dumps(source, sort_keys=True, allow_nan=False)})
    # The changed brightness must remain invalid for the measured foreground
    # pipeline. The explicitly chosen color-only preview is a separate display.
    image = (floor.astype(float) * .65).astype(np.uint8)
    cv2.circle(image, (145, 110), 14, (30, 180, 40), -1)
    camera = ExistingSyntheticBuffer(image)
    camera.start = camera.stop = forbidden
    runtime = SimpleNamespace(
        settings=SimpleNamespace(data_dir=tmp_path), store=ReadOnlyPreviewStore(), camera=camera,
        record_lock=threading.Lock(), register_profile=forbidden, fit_recorded_flow=forbidden,
        record=forbidden, add_case=forbidden,
        token_detection=SimpleNamespace(_reference=lambda _id: (record, reference),
                                        measure_token=forbidden, capture_reference=forbidden,
                                        detector=forbidden))
    body = SimpleNamespace(source=bundle, reference_id=reference_id,
                           detection_polygon_px=POLYGON, detector_mode="saved_green_marker_preview_v2")
    service = DetectorPreviewService(runtime)
    return SimpleNamespace(service=service, runtime=runtime, body=body, source=source,
                           reference_record=record, reference=reference, path=tmp_path)


def assert_no_admission(env):
    assert env.runtime.store.writes == []
    assert list(env.path.iterdir()) == []


def test_explicit_marker_preview_keeps_historical_map_and_never_mints_measured_artifacts(env):
    source_before, reference_before = copy.deepcopy(env.source), copy.deepcopy(env.reference_record)
    config = env.service.configure(env.body)
    assert config["detector_mode"] == "saved_green_marker_preview_v2"
    assert config["validation_status"] == "UNVALIDATED"
    assert config["approved_for_inference"] is config["measured_flow_eligible"] is False
    assert config["current_alignment_verified"] is False
    assert config["calibration_id"] is config["profile_id"] is config["case_id"] is None
    assert config["homography_image_to_cm"] == source_before["homography_image_to_cm"]
    assert config["camera_session_id"] != config["source_camera_session_id"]
    result = env.service.get(config["preview_id"])
    assert result["detector_mode"] == "saved_green_marker_preview_v2"
    assert result["validation_status"] == "UNVALIDATED"
    assert result["approved_for_inference"] is result["measured_flow_eligible"] is False
    assert result["calibration_id"] is result["profile_id"] is result["case_id"] is None
    assert result["jpeg_data_url"].startswith("data:image/jpeg;base64,")
    assert result["observed"] is True
    assert "x_cm" not in result["point"] and "y_cm" not in result["point"]
    assert env.source == source_before and env.reference_record == reference_before
    assert_no_admission(env)


def test_registration_failure_shows_only_pixels_and_cannot_invent_centimetres(env, monkeypatch):
    monkeypatch.setattr(env.service, "_marker_alignment",
                        lambda *_args: (None, "Synthetic insufficient-inliers fixture"))
    config = env.service.configure(env.body)
    result = env.service.get(config["preview_id"])
    assert result["observed"] is True and result["alignment"] is None
    assert result["point"]["pixel_x"] == pytest.approx(145, abs=1)
    assert result["point"]["reference_pixel_x"] is result["point"]["reference_pixel_y"] is None
    assert result["point"]["estimated_x_cm"] is result["point"]["estimated_y_cm"] is None
    assert result["alignment_rejection"] == "Synthetic insufficient-inliers fixture"
    assert result["validation_status"] == "UNVALIDATED"
    assert result["approved_for_inference"] is result["measured_flow_eligible"] is False
    assert_no_admission(env)


def test_current_policy_area_is_an_estimate_not_a_saved_token_size_or_calibration(env):
    config = env.service.configure(env.body)
    size = config["marker_area_source"]
    assert size["area_px"] == 620
    assert size["report_id"] == env.runtime.store.replay["report_id"]
    assert size["source_policy_sha256"] == surface_policy()["policy_sha256"]
    assert config["calibration_id"] is None and config["current_alignment_verified"] is False
    assert_no_admission(env)


def test_color_only_display_does_not_relax_the_measured_foreground_scene_gate(env):
    with pytest.raises(SceneChanged):
        surface_token_diagnostic(env.runtime.camera.image_bgr, env.reference, POLYGON)
    strict = copy.deepcopy(env.body)
    strict.detector_mode = "foreground_surface_v2"
    strict_config = env.service.configure(strict)
    strict_frame = env.service.get(strict_config["preview_id"])
    assert strict_frame["observed"] is False and strict_frame["reason"] == "SCENE_CHANGED"
    approximate = env.service.configure(env.body)
    marker_frame = env.service.get(approximate["preview_id"])
    assert marker_frame["observed"] is True
    assert marker_frame["saved_foreground_status"] == "SCENE_CHANGED"
    assert marker_frame["validation_status"] == "UNVALIDATED"
    assert marker_frame["approved_for_inference"] is False
    assert_no_admission(env)


def test_retired_replay_policy_cannot_supply_a_size_estimate_for_the_live_preview(env):
    env.runtime.store.replay["policy"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="predates the current detector policy"):
        env.service.configure(env.body)
    assert env.runtime.camera.reads == 0
    assert_no_admission(env)


def test_display_does_not_rebind_an_old_preview_to_a_new_camera_session(env):
    config = env.service.configure(env.body)
    env.runtime.camera.session_id = "usb-new-session-fixture"
    with pytest.raises(ValueError, match="session changed"):
        env.service.get(config["preview_id"])
    assert env.runtime.camera.reads == 0
    assert_no_admission(env)
