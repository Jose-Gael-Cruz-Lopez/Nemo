"""Repeated recordings/frames cannot reweight a frozen validation experiment.

All records are synthetic contracts in temporary stores. No device, provider or
physical measurement is involved, even when exercising MEASURED_TANK admission.
"""

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app

AUTH = {"Authorization": "Bearer evidence-identity-test"}
BOUNDS = {"x_min_cm": 0, "x_max_cm": 20, "y_min_cm": 0, "y_max_cm": 20}


@pytest.fixture
def rig(tmp_path):
    app = create_app(Settings(data_dir=tmp_path, local_token="evidence-identity-test"))
    runtime = app.state.runtime
    for name, speed in (("training", 1), ("good", 1), ("bad", 5)):
        frame_ids = [f"{name}-frame-{index}" for index in range(4)]
        points = [{"observed": True, "track_id": name, "t_s": index * .2,
                   "x_cm": 1 + speed * index * .2, "y_cm": 1, "frame_id": frame_id}
                  for index, frame_id in enumerate(frame_ids)]
        runtime.store.put("recording", {"calibration_id": "test-calibration",
            "camera_session_id": "test-session", "data_origin": "MEASURED_TANK",
            "test_fixture_origin": "SYNTHETIC_CONTRACT_TEST", "physical_validation": False,
            "points": points, "evidence_frame_ids": frame_ids}, name)
    body = {"training_recording_ids": ["training"], "validation_recording_ids": ["good", "bad"],
            "bounds": BOUNDS, "coverage_radius_cm": 100}
    return TestClient(app), runtime, body


def forbid_fit_and_write(monkeypatch, runtime):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Invalid evidence reached fitting or a database write")
    monkeypatch.setattr("apps.transport.reeftrace_transport.fit_flow", forbidden)
    monkeypatch.setattr(runtime.store, "put", forbidden)


def test_unique_validation_runs_keep_the_real_denominator_and_error(rig):
    client, runtime, body = rig
    response = client.post("/api/v1/flow/fit-recordings", json=body, headers=AUTH)
    assert response.status_code == 200, response.text
    flow = response.json()
    assert flow["diagnostics"]["validation_coverage_fraction"] == 1
    assert flow["diagnostics"]["validation_rmse_cm_s"] == pytest.approx(8 ** .5)
    assert flow["provenance"]["validation_recording_ids"] == ["good", "bad"]
    assert runtime.store.get("flow", flow["id"]) == flow


@pytest.mark.parametrize("split", ["training", "validation"])
def test_duplicate_ids_rejected_before_any_read_fit_or_write(rig, monkeypatch, split):
    client, runtime, body = rig
    body[f"{split}_recording_ids"] = ["training"] * 2 if split == "training" else ["good"] * 9 + ["bad"]
    forbid_fit_and_write(monkeypatch, runtime)
    def forbidden_get(*_args, **_kwargs):
        raise AssertionError("Duplicate identity reached the artifact store")
    monkeypatch.setattr(runtime.store, "get", forbidden_get)
    response = client.post("/api/v1/flow/fit-recordings", json=body, headers=AUTH)
    assert response.status_code == 409
    assert "distinct within each split" in response.text


@pytest.mark.parametrize("split", ["training", "validation"])
def test_new_recording_id_cannot_disguise_reused_frames_in_same_split(rig, monkeypatch, split):
    client, runtime, body = rig
    original = "training" if split == "training" else "good"
    duplicate = runtime.store.put("recording", runtime.store.get("recording", original), "copied-footage")
    body[f"{split}_recording_ids"].append(duplicate["id"])
    forbid_fit_and_write(monkeypatch, runtime)
    response = client.post("/api/v1/flow/fit-recordings", json=body, headers=AUTH)
    assert response.status_code == 409 and "frames" in response.text


def test_new_validation_recording_id_cannot_copy_training_frames(rig, monkeypatch):
    client, runtime, body = rig
    duplicate = runtime.store.put("recording", runtime.store.get("recording", "training"), "copied-footage")
    body["validation_recording_ids"] = [duplicate["id"]]
    forbid_fit_and_write(monkeypatch, runtime)
    response = client.post("/api/v1/flow/fit-recordings", json=body, headers=AUTH)
    assert response.status_code == 409 and "disjoint" in response.text


@pytest.mark.parametrize("split", ["training", "validation"])
def test_repeated_frame_within_one_recording_is_not_an_additional_measurement(rig, monkeypatch, split):
    client, runtime, body = rig
    original = "training" if split == "training" else "good"
    recording = runtime.store.get("recording", original)
    recording["evidence_frame_ids"][1] = recording["evidence_frame_ids"][0]
    replacement = runtime.store.put("recording", recording, "repeated-frame")
    body[f"{split}_recording_ids"] = [replacement["id"]]
    forbid_fit_and_write(monkeypatch, runtime)
    response = client.post("/api/v1/flow/fit-recordings", json=body, headers=AUTH)
    assert response.status_code == 409 and "frames" in response.text


@pytest.mark.parametrize("bad_id", [None, True, 17, [], {}, "", " ", "bad/id", "x" * 101])
def test_malformed_recording_ids_fail_cleanly_before_set_lookup(rig, monkeypatch, bad_id):
    client, runtime, body = rig
    body["validation_recording_ids"] = [bad_id]
    forbid_fit_and_write(monkeypatch, runtime)
    response = client.post("/api/v1/flow/fit-recordings", json=body, headers=AUTH)
    assert response.status_code == 409 and "artifact identifiers" in response.text


@pytest.mark.parametrize("bad_frames", [[], [True], [[]], ["bad/frame"], "frame"])
def test_malformed_frame_identity_cannot_reach_fit(rig, monkeypatch, bad_frames):
    client, runtime, body = rig
    recording = runtime.store.get("recording", "good")
    recording["evidence_frame_ids"] = bad_frames
    replacement = runtime.store.put("recording", recording, "invalid-frames")
    body["validation_recording_ids"] = [replacement["id"]]
    forbid_fit_and_write(monkeypatch, runtime)
    response = client.post("/api/v1/flow/fit-recordings", json=body, headers=AUTH)
    assert response.status_code == 409 and "frames" in response.text


def test_recording_payload_identity_cannot_alias_another_reference(rig, monkeypatch):
    client, runtime, body = rig
    original_get = runtime.store.get
    def aliased_get(kind, identifier):
        document = deepcopy(original_get(kind, identifier))
        if kind == "recording" and identifier == "good":
            document["id"] = "another-recording"
        return document
    monkeypatch.setattr(runtime.store, "get", aliased_get)
    forbid_fit_and_write(monkeypatch, runtime)
    response = client.post("/api/v1/flow/fit-recordings", json=body, headers=AUTH)
    assert response.status_code == 409 and "identity" in response.text
