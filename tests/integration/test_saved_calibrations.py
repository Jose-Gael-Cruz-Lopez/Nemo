"""Checked map reuse through HTTP and real recording gates; all frames are synthetic."""
from __future__ import annotations

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

from apps.api.reeftrace_api.api.v1.endpoints.saved_calibrations import (
    create_saved_calibrations_router,
)
from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.api.reeftrace_api.services.field_sessions import calibration_intact, digest
from apps.vision.reeftrace_vision.calibration import fit_homography

TOKEN = "saved-calibration-synthetic-test-only"
AUTH = {"Authorization": "Bearer " + TOKEN}
BASE = "/api/v1/vision/calibrations"
WIDTH, HEIGHT = 160, 120
FIT = [[0, 0], [159, 0], [159, 119], [0, 119]]
CHECK = [[20, 20], [130, 30], [70, 100]]


class SyntheticCamera:
    backend = "SYNTHETIC_FAKE_CAPTURE"

    def __init__(self):
        self.session_id = "usb-new-synthetic"
        self.running = self.fresh = True
        self.width, self.height, self.sequence = WIDTH, HEIGHT, 0

    def status(self):
        return {"running": self.running, "fresh": self.fresh, "session_id": self.session_id,
                "width": self.width, "height": self.height, "device_index": 1,
                "backend": self.backend}

    def stop(self):
        self.running = False
        self.session_id = None

    def image(self):
        self.sequence += 1
        image = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        cv2.circle(image, (60 + self.sequence % 8, 55), 7, (0, 0, 255), -1)
        ok, jpeg = cv2.imencode(".jpg", image)
        assert ok
        return image, {"session_id": self.session_id, "sequence": self.sequence,
                       "width": WIDTH, "height": HEIGHT, "received_mono_s": time.monotonic(),
                       "received_utc": datetime.now(UTC).isoformat(), "jpeg": jpeg.tobytes()}


def cm(points):
    return [[x / 10, y / 10] for x, y in points]


def rehash(record):
    result = copy.deepcopy(record)
    report = {key: value for key, value in result.items() if key not in {"id", "calibration_id"}}
    identity = "cal-" + hashlib.sha256(
        json.dumps(report, sort_keys=True, allow_nan=False).encode()).hexdigest()[:16]
    result.update(id=identity, calibration_id=identity)
    return result


@pytest.fixture
def env(tmp_path):
    app = create_app(Settings(_env_file=None, data_dir=tmp_path, local_token=TOKEN,
                              camera_sample_hz=20))
    runtime = app.state.runtime
    runtime.camera = SyntheticCamera()

    def operator(request: Request):
        if request.headers.get("Authorization") != AUTH["Authorization"]:
            raise HTTPException(401, "Operator token required")

    # Root mounts this same factory with its existing shared operator dependency.
    # Keep this isolated test runnable before that unrelated main.py wiring lands.
    if BASE not in app.openapi()["paths"]:
        app.include_router(create_saved_calibrations_router(runtime, operator), prefix="/api/v1")
    report = fit_homography(FIT, cm(FIT), CHECK, cm(CHECK), max_error_cm=0.5,
                            image_size_px=[WIDTH, HEIGHT], camera_session_id="usb-old-synthetic")
    source = runtime.store.put("calibration", report, report["calibration_id"])
    with TestClient(app) as client:
        yield client, runtime, source, app


def request_body(source):
    return {"source": {"schema_version": "nemo_saved_calibration_v1", "calibration": source,
                       "calibration_json": json.dumps(source, sort_keys=True, allow_nan=False)},
            "camera_session_id": "usb-new-synthetic", "image_size_px": [WIDTH, HEIGHT],
            "check_pixels": CHECK, "check_world_cm": cm(CHECK), "water_plane_unchanged": True}


def post(client, body, expected=200):
    response = client.post(BASE + "/revalidate", json=body, headers=AUTH)
    assert response.status_code == expected, response.text
    return response.json()


def test_export_is_exact_private_operator_only_and_has_no_images_or_settings(env):
    client, runtime, source, _ = env
    assert client.get(BASE).status_code == 401
    assert client.get(BASE + "/" + source["id"]).status_code == 401
    summary = client.get(BASE, headers=AUTH)
    assert summary.status_code == 200 and summary.headers["Cache-Control"] == "no-store"
    assert summary.json() == {"calibrations": [{key: source[key] for key in (
        "calibration_id", "camera_session_id", "image_size_px", "approved", "max_error_cm",
        "max_allowed_error_cm", "mean_error_cm", "validation_count")} ]}
    bundle = client.get(BASE + "/" + source["id"], headers=AUTH)
    assert bundle.status_code == 200
    assert bundle.json() == {"schema_version": "nemo_saved_calibration_v1", "calibration": source,
                            "calibration_json": json.dumps(source, sort_keys=True, allow_nan=False)}
    assert str(runtime.settings.data_dir) not in bundle.text
    assert "frame" not in bundle.text and "token" not in bundle.text
    assert client.get(BASE + "/cal-not-found", headers=AUTH).status_code == 404


def test_fixed_map_current_checks_create_new_immutable_calibration_then_record(env):
    client, runtime, source, _ = env
    source_before = copy.deepcopy(source)
    # The old map remains readable, but cannot authorize this new capture session.
    recording_body = {"calibration_id": source["id"], "duration_s": 1}
    rejected = client.post("/api/v1/camera/record", headers=AUTH, json=recording_body)
    assert rejected.status_code == 409 and "session" in rejected.json()["detail"]
    result = post(client, request_body(source))
    assert result["approved"] is True and calibration_intact(result)
    assert result["id"] != source["id"]
    assert result["camera_session_id"] == runtime.camera.session_id
    assert result["homography_image_to_cm"] == source["homography_image_to_cm"]
    assert result["max_allowed_error_cm"] == source["max_allowed_error_cm"]
    assert result["reuse"] == {"method": "fixed_homography_current_checks_v1",
        "source_calibration_id": source["id"], "source_content_sha256": digest(source),
        "check_pixels": CHECK, "check_world_cm": cm(CHECK), "water_plane_unchanged": True}
    assert runtime.store.get("calibration", source["id"]) == source_before
    assert len(runtime.store.list("calibration")) == 2
    assert post(client, request_body(source)) == result  # Idempotent fixed evidence.
    assert len(runtime.store.list("calibration")) == 2
    assert client.post("/api/v1/camera/record", json={**recording_body,
                       "calibration_id": result["id"]}).status_code == 401
    recorded = client.post("/api/v1/camera/record", headers=AUTH,
                           json={**recording_body, "calibration_id": result["id"]})
    assert recorded.status_code == 200, recorded.text
    assert recorded.json()["data_origin"] == "MEASURED_TANK"
    assert recorded.json()["calibration_id"] == result["id"]
    assert recorded.json()["evidence_frame_ids"]
    assert any(point["observed"] for point in recorded.json()["points"])
    assert runtime.photon_task is None


def test_failed_fresh_checks_are_saved_unapproved_and_cannot_authorize_recording(env):
    client, runtime, source, _ = env
    body = request_body(source)
    body["check_world_cm"] = [[x + 2, y] for x, y in cm(CHECK)]
    result = post(client, body)
    assert result["approved"] is False and result["max_error_cm"] > 0.5
    assert calibration_intact(result) and result["max_allowed_error_cm"] == 0.5
    rejected = client.post("/api/v1/camera/record", headers=AUTH,
                           json={"calibration_id": result["id"], "duration_s": 1})
    assert rejected.status_code == 409 and "approved" in rejected.json()["detail"]
    assert runtime.store.list("recording") == []
    assert post(client, request_body(result), 409)["detail"].startswith("Only an originally approved")


@pytest.mark.parametrize("change", ["stopped", "stale", "session", "dimensions"])
def test_current_capture_identity_and_freshness_are_required(env, change):
    client, runtime, source, _ = env
    if change == "stopped":
        runtime.camera.running = False
    elif change == "stale":
        runtime.camera.fresh = False
    elif change == "session":
        runtime.camera.session_id = "usb-another"
    else:
        runtime.camera.width = WIDTH + 1
    post(client, request_body(source), 409)
    assert len(runtime.store.list("calibration")) == 1


@pytest.mark.parametrize("change", ["tamper", "singular", "horizon", "source_dimensions",
                                   "unapproved", "mean_error", "tabletop_scale"])
def test_corrupt_or_inapplicable_source_never_becomes_a_current_map(env, change):
    client, runtime, source, _ = env
    record = copy.deepcopy(source)
    if change == "tamper":
        record["homography_image_to_cm"][0][2] += 1
    else:
        if change == "singular":
            record["homography_image_to_cm"] = [[1, 0, 0], [0, 0, 0], [0, 0, 1]]
        elif change == "horizon":
            record["homography_image_to_cm"] = [[1, 0, 0], [0, 1, 0], [0.02, 0, -1]]
        elif change == "source_dimensions":
            record["image_size_px"][0] += 1
        elif change == "unapproved":
            record["approved"] = False
        elif change == "tabletop_scale":
            record["homography_image_to_cm"] = [[100, 0, 0], [0, 100, 0], [0, 0, 1]]
        else:
            record["mean_error_cm"] = record["max_error_cm"] + 1
        record = rehash(record)
    post(client, request_body(record), 409)
    assert len(runtime.store.list("calibration")) == 1


@pytest.mark.parametrize("change", ["repeated_pixel", "repeated_world", "collinear_pixel",
                                   "collinear_world", "outside", "mismatched"])
def test_current_checks_are_independent_in_bounds_and_corresponding(env, change):
    client, runtime, source, _ = env
    body = request_body(source)
    if change == "repeated_pixel":
        body["check_pixels"] = [CHECK[0], CHECK[0], CHECK[2]]
    elif change == "repeated_world":
        body["check_world_cm"] = [cm(CHECK)[0], cm(CHECK)[0], cm(CHECK)[2]]
    elif change == "collinear_pixel":
        body["check_pixels"] = [[10, 10], [20, 20], [30, 30]]
    elif change == "collinear_world":
        body["check_world_cm"] = [[1, 1], [2, 2], [3, 3]]
    elif change == "outside":
        body["check_pixels"] = [[-1, 20], CHECK[1], CHECK[2]]
    else:
        body["check_world_cm"] = cm(CHECK) + [[1, 2]]
    post(client, body, 409)
    assert len(runtime.store.list("calibration")) == 1


@pytest.mark.parametrize("change", ["tolerance_override", "excess_tolerance", "unknown_private",
                                   "water_plane", "too_few", "infinity", "oversized",
                                   "numeric_string", "boolean_coordinate", "extreme_coordinate"])
def test_schema_forbids_tolerance_changes_and_nonportable_fields(env, change):
    client, runtime, source, _ = env
    body = request_body(copy.deepcopy(source))
    if change == "tolerance_override":
        body["max_error_cm"] = 5
    elif change == "excess_tolerance":
        body["source"]["calibration"]["max_allowed_error_cm"] = 6
    elif change == "unknown_private":
        body["source"]["calibration"]["private_frame_path"] = "/private/not-exported.jpg"
    elif change == "water_plane":
        body["water_plane_unchanged"] = False
    elif change == "too_few":
        body["check_pixels"] = CHECK[:2]
    elif change == "infinity":
        body["check_pixels"] = [["inf", 20], CHECK[1], CHECK[2]]
    elif change == "numeric_string":
        body["source"]["calibration"]["mean_error_cm"] = "0.01"
    elif change == "boolean_coordinate":
        body["check_pixels"] = [[True, 20], CHECK[1], CHECK[2]]
    elif change == "extreme_coordinate":
        body["check_world_cm"] = [[1e308, 20], CHECK[1], CHECK[2]]
    else:
        body["check_pixels"] = CHECK * 34
    post(client, body, 422)
    assert len(runtime.store.list("calibration")) == 1


def test_private_export_and_revalidation_are_disabled_in_cloud_even_if_mounted(env):
    client, runtime, source, app = env
    app.state.deployment_profile = "cloud_software_demo"
    for path, method, body in ((BASE, "get", None), (BASE + "/" + source["id"], "get", None),
                               (BASE + "/revalidate", "post", request_body(source))):
        kwargs = {"headers": AUTH}
        if body is not None:
            kwargs["json"] = body
        response = getattr(client, method)(path, **kwargs)
        assert response.status_code == 503
        assert response.headers["Cache-Control"] == "no-store"
    assert len(runtime.store.list("calibration")) == 1


def test_revalidation_requires_operator_and_does_not_export_unexpected_saved_fields(env):
    client, runtime, source, _ = env
    assert client.post(BASE + "/revalidate", json=request_body(source)).status_code == 401
    bad = {**source, "private_frame_path": "/private/not-exported.jpg"}
    bad["id"] = bad["calibration_id"] = "cal-0000000000000000"
    runtime.store.put("calibration", bad, bad["id"])
    response = client.get(BASE + "/" + bad["id"], headers=AUTH)
    assert response.status_code == 409
    assert "private_frame_path" not in response.text and "/private/" not in response.text


def test_browser_number_roundtrip_preserves_legacy_identity_through_exact_json(env):
    client, runtime, source, _ = env
    exported = client.get(BASE + "/" + source["id"], headers=AUTH).json()

    def browser_numbers(value):
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, list):
            return [browser_numbers(item) for item in value]
        if isinstance(value, dict):
            return {key: browser_numbers(item) for key, item in value.items()}
        return value

    body = browser_numbers(request_body(source))
    body["source"] = browser_numbers(exported)
    assert not calibration_intact(body["source"]["calibration"]), "fixture must exercise legacy float hash"
    assert body["source"]["calibration_json"] == exported["calibration_json"]
    result = post(client, body)
    assert result["approved"] is True and calibration_intact(result)
    assert result["homography_image_to_cm"] == source["homography_image_to_cm"]
    assert result["reuse"]["source_content_sha256"] == digest(source)
    assert runtime.store.get("calibration", source["id"]) == source


@pytest.mark.parametrize("change", ["missing", "mirror_mismatch", "duplicate_key", "nonfinite",
                                   "invalid_json", "raw_oversized"])
def test_exact_json_is_required_bounded_unambiguous_and_matches_mirror(env, change):
    client, runtime, source, _ = env
    body = request_body(copy.deepcopy(source))
    if change == "missing":
        del body["source"]["calibration_json"]
    elif change == "mirror_mismatch":
        body["source"]["calibration"]["mean_error_cm"] += 0.1
    elif change == "duplicate_key":
        original = body["source"]["calibration_json"]
        body["source"]["calibration_json"] = original[:-1] + ', "id": "' + source["id"] + '"}'
    elif change == "nonfinite":
        body["source"]["calibration_json"] = '{"max_error_cm": NaN}'
    elif change == "invalid_json":
        body["source"]["calibration_json"] = '{"unfinished":'
    else:
        body["source"]["calibration_json"] += " " * 32_000
    post(client, body, 422)
    assert len(runtime.store.list("calibration")) == 1
