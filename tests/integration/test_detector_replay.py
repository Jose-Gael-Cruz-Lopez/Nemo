"""Saved-footage HTTP regression with synthetic files only; no devices or providers."""
from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import cv2
import httpx
import numpy as np
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.api.v1.endpoints.detector_replay import create_detector_replay_router
from apps.api.reeftrace_api.services.detector_replay import MANIFEST_SCHEMA
from apps.api.reeftrace_api.services.store import Store
from apps.vision.reeftrace_vision.calibration import fit_homography
from apps.vision.reeftrace_vision.foreground import EmptyTankReference

TOKEN = "synthetic-replay-test-only"
AUTH = {"Authorization": "Bearer " + TOKEN}
BASE = "/api/v1/camera/detector-replay"
WIDTH, HEIGHT = 160, 120


def file_entry(path, root, **fields):
    return {"path": str(path.relative_to(root)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), **fields}


@pytest.fixture
def env(tmp_path, monkeypatch):
    root = tmp_path / "local-data"
    folder = root / "detector_replay"
    folder.mkdir(parents=True)
    gray = np.random.default_rng(230).integers(95, 145, (HEIGHT, WIDTH), dtype=np.uint8)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    floor = np.repeat(gray[:, :, None], 3, axis=2)
    reference = EmptyTankReference([floor.copy() for _ in range(5)])
    reference_path = folder / "reference.npz"
    np.savez_compressed(reference_path, **reference.to_arrays())
    frames = []
    for index in range(5):
        image = floor.copy()
        if index != 3:
            cv2.circle(image, (70 + index, 50), 7, (0, 255, 0), -1)
        if index == 1:
            cv2.rectangle(image, (5, 35), (15, 70), (250, 250, 250), -1)
        if index == 2:
            cv2.rectangle(image, (105, 60), (135, 65), (250, 250, 250), -1)
        success, encoded = cv2.imencode(".jpg", image)
        assert success
        path = folder / f"frame-{index}.jpg"
        path.write_bytes(encoded.tobytes())
        frames.append(file_entry(path, root, sequence=index + 1, t_s=index * 0.2))
    fit = [[0, 0], [159, 0], [159, 119], [0, 119]]
    checks = [[20, 20], [130, 30], [70, 100]]
    cm = lambda pairs: [[x / 10, y / 10] for x, y in pairs]
    report = fit_homography(fit, cm(fit), checks, cm(checks), max_error_cm=0.5,
                            image_size_px=[WIDTH, HEIGHT], camera_session_id="usb-synthetic-history")
    source = {**report, "id": report["calibration_id"]}
    clip = {"id": "synthetic-clip", "label": "Synthetic cap and reflections",
            "source_kind": "estimated_rehearsal", "source_id": "rehearsal-synthetic",
            "image_size_px": [WIDTH, HEIGHT], "camera_session_id": "usb-saved-synthetic",
            "reference": file_entry(reference_path, root, content_id=reference.fingerprint,
                                    camera_session_id="usb-saved-synthetic"),
            "original_token_area_px_range": [35, 800], "frames": frames}
    manifest = {"schema_version": MANIFEST_SCHEMA,
                "source_calibration": {"schema_version": "nemo_saved_calibration_v1",
                                       "calibration": source,
                                       "calibration_json": json.dumps(source, sort_keys=True)},
                "detection_polygon_px": [[25, 15], [145, 15], [145, 110], [25, 110]],
                "clips": [clip]}
    path = folder / "manifest.json"
    path.write_text(json.dumps(manifest))
    calls = {"camera": 0, "provider": 0}

    def forbid_camera(*_args, **_kwargs):
        calls["camera"] += 1
        raise AssertionError("Replay must not access a camera")

    async def forbid_provider(*_args, **_kwargs):
        calls["provider"] += 1
        raise AssertionError("Replay must not contact providers")

    monkeypatch.setattr(cv2, "VideoCapture", forbid_camera)
    monkeypatch.setattr(httpx.AsyncClient, "request", forbid_provider)
    runtime = SimpleNamespace(settings=SimpleNamespace(data_dir=root), store=Store(root),
                              camera=SimpleNamespace(image=forbid_camera, status=forbid_camera,
                                                     start=forbid_camera))
    app = FastAPI()

    def operator(request: Request):
        if request.headers.get("Authorization") != AUTH["Authorization"]:
            raise HTTPException(401, "Operator token required", headers={"Cache-Control": "no-store"})

    @app.exception_handler(ValueError)
    async def invalid(_request, error):
        return JSONResponse(status_code=409, content={"detail": str(error)[:300]})

    @app.exception_handler(KeyError)
    async def missing(_request, _error):
        return JSONResponse(status_code=404, content={"detail": "Record not found"})

    app.include_router(create_detector_replay_router(runtime, operator), prefix="/api/v1")
    with TestClient(app, raise_server_exceptions=False) as client:
        yield SimpleNamespace(client=client, runtime=runtime, app=app, manifest=manifest,
                              manifest_path=path, root=root, calls=calls, source=source,
                              floor=floor, reference=reference)
    assert calls == {"camera": 0, "provider": 0}


def save_manifest(env):
    env.manifest_path.write_text(json.dumps(env.manifest))


def post(env, expected=200):
    response = env.client.post(BASE, headers=AUTH, json={})
    assert response.status_code == expected, f"HTTP {response.status_code}: {response.text[:240]}"
    return response


def assert_no_admission(env):
    for kind in ("recording", "frame", "flow", "profile", "calibration", "field_session",
                 "estimated_rehearsal", "estimated_rehearsal_frame"):
        assert env.runtime.store.list(kind) == []
    assert env.runtime.store.cases() == []
    with env.runtime.store.connection() as db:
        assert db.execute("SELECT count(*) FROM inbox").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM outbox").fetchone()[0] == 0


def test_replay_compares_actual_detectors_over_synthetic_saved_frames_without_admission(env):
    response = post(env)
    result = response.json()
    assert response.headers["Cache-Control"] == "no-store"
    assert result["data_origin"] == "LOCAL_SAVED_FOOTAGE_REPLAY"
    assert result["purpose"] == "DEVELOPMENT_REGRESSION"
    assert result["validation_status"] == "UNVALIDATED"
    assert result["measured_flow_eligible"] is result["camera_accessed"] is False
    assert result["photon_messages_sent"] is False
    assert result["manifest_sha256"] == hashlib.sha256(env.manifest_path.read_bytes()).hexdigest()
    assert result["policy"]["sha256"] == result["policy"]["parameters"]["policy_sha256"]
    assert result["totals"]["frames"] == 5
    assert result["totals"]["surface_accepted_frames"] == 4
    assert result["totals"]["baseline_ambiguous_frames"] >= 1
    assert result["totals"]["roi_rejected_candidates"] >= 1
    assert result["totals"]["shape_rejected_candidates"] >= 1
    clip = result["clips"][0]
    observed = [point for point in clip["points"] if point["observed"]]
    assert len(observed) == 4
    assert any(not point["observed"] for point in clip["points"])
    assert all("estimated_x_cm" in point and "estimated_y_cm" in point for point in observed)
    assert all("x_cm" not in point and "y_cm" not in point for point in clip["points"])
    assert clip["example"]["jpeg_data_url"].startswith("data:image/jpeg;base64,")
    assert str(env.root) not in json.dumps(result)
    assert_no_admission(env)
    latest = env.client.get(BASE, headers=AUTH)
    assert latest.status_code == 200 and latest.json() == result
    assert latest.headers["Cache-Control"] == "no-store"


def test_replay_requires_local_operator_and_get_does_not_run_a_replay(env):
    assert env.client.get(BASE).status_code == 401
    assert env.client.post(BASE, json={}).status_code == 401
    assert env.client.get(BASE, headers=AUTH).status_code == 404
    assert env.runtime.store.list("detector_replay") == []
    assert_no_admission(env)


@pytest.mark.parametrize("body", [{"path": "elsewhere.json"}, {"detector": "anything"},
                                  {"acknowledge": True}, [], None])
def test_replay_post_accepts_only_the_empty_strict_object(env, body):
    response = env.client.post(BASE, headers=AUTH, json=body)
    assert response.status_code == 422, response.text
    assert env.runtime.store.list("detector_replay") == []


def test_replay_is_disabled_in_cloud_even_when_router_is_mounted(env):
    env.app.state.deployment_profile = "cloud_software_demo"
    for response in (env.client.get(BASE, headers=AUTH),
                     env.client.post(BASE, headers=AUTH, json={})):
        assert response.status_code == 503
        assert response.headers.get("Cache-Control") == "no-store"
    assert env.runtime.store.list("detector_replay") == []


@pytest.mark.parametrize("where", ["reference", "frame"])
@pytest.mark.parametrize("escape", ["absolute", "traversal", "symlink"])
def test_private_replay_files_cannot_escape_the_local_data_root(env, tmp_path, where, escape):
    outside = tmp_path / "outside-private-file"
    outside.write_bytes(b"must not leave private root")
    target = env.manifest["clips"][0]["reference"] if where == "reference" else env.manifest["clips"][0]["frames"][0]
    if escape == "absolute":
        relative = str(outside)
    elif escape == "traversal":
        relative = "../outside-private-file"
    else:
        link = env.root / "detector_replay/escape-file"
        link.symlink_to(outside)
        relative = "detector_replay/escape-file"
    target.update(path=relative, sha256=hashlib.sha256(outside.read_bytes()).hexdigest())
    save_manifest(env)
    post(env, 409)
    assert env.runtime.store.list("detector_replay") == []
    assert_no_admission(env)


@pytest.mark.parametrize("corruption", ["reference_hash", "frame_hash", "reference_content_id",
                                       "clip_dimensions", "reference_session", "frame_dimensions",
                                       "frame_not_image", "duplicate_time", "negative_time", "nan_time",
                                       "duplicate_sequence", "bool_sequence", "bool_time", "text_time"])
def test_changed_replay_identity_dimensions_session_and_clock_fail_closed(env, corruption):
    clip = env.manifest["clips"][0]
    frame = clip["frames"][-1]
    if corruption == "reference_hash":
        clip["reference"]["sha256"] = "0" * 64
    elif corruption == "frame_hash":
        frame["sha256"] = "0" * 64
    elif corruption == "reference_content_id":
        clip["reference"]["content_id"] = "ref-" + "0" * 16
    elif corruption == "clip_dimensions":
        clip["image_size_px"] = [WIDTH - 1, HEIGHT]
    elif corruption == "reference_session":
        clip["reference"]["camera_session_id"] = "usb-other-saved-session"
    elif corruption in {"frame_dimensions", "frame_not_image"}:
        path = env.root / frame["path"]
        if corruption == "frame_dimensions":
            ok, encoded = cv2.imencode(".jpg", env.floor[:, :-1])
            assert ok
            payload = encoded.tobytes()
        else:
            payload = b"This is not an image"
        path.write_bytes(payload)
        frame["sha256"] = hashlib.sha256(payload).hexdigest()
    elif corruption == "duplicate_time":
        frame["t_s"] = clip["frames"][-2]["t_s"]
    elif corruption == "negative_time":
        clip["frames"][0]["t_s"] = -0.1
    elif corruption == "nan_time":
        frame["t_s"] = float("nan")
    elif corruption == "duplicate_sequence":
        frame["sequence"] = clip["frames"][-2]["sequence"]
    elif corruption == "bool_sequence":
        frame["sequence"] = True
    elif corruption == "bool_time":
        frame["t_s"] = True
    else:
        frame["t_s"] = "1.0"
    save_manifest(env)
    post(env, 409)
    assert env.runtime.store.list("detector_replay") == []
    assert_no_admission(env)


def test_wrong_manifest_shape_is_rejected_without_persisting_a_report(env):
    env.manifest_path.write_text("[]")
    post(env, 409)
    assert env.runtime.store.list("detector_replay") == []
