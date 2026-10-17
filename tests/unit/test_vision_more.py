"""Geometry/measurement contracts, using synthetic records and no physical camera.

The mocked MEASURED_TANK records below exercise admission rules, not physical validation.
They live only in pytest temporary directories and are labeled SYNTHETIC_CONTRACT_TEST.
"""

import asyncio
import copy
import threading
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.vision.reeftrace_vision.calibration import fit_homography, project
from apps.vision.reeftrace_vision.tracking import SingleTokenTracker, flow_samples


def _calibration(camera_session_id=None):
    return fit_homography(
        [[0, 0], [300, 0], [300, 200], [0, 200]],
        [[0, 0], [30, 0], [30, 20], [0, 20]],
        [[50, 40], [140, 130], [250, 140]],
        [[5, 4], [14, 13], [25, 14]],
        image_size_px=[301, 201], max_error_cm=0.1,
        camera_session_id=camera_session_id,
    )


def test_projective_horizon_cannot_become_a_valid_tank_origin():
    matrix = [[1, 0, 0], [0, 1, 0], [0.1, 0, -1]]
    with pytest.raises(ValueError, match="horizon|denominator|projection"):
        project(matrix, [[10, 5]])


def test_equivalent_homography_scales_produce_the_same_coordinates():
    # Multiplying all nine homogeneous coefficients changes no projective map.
    matrix = np.array([[0.1, 0, 1], [0, 0.2, 2], [0, 0, 1.0]])
    pixels = [[10, 20], [100, 50]]
    expected = np.array([[2, 6], [11, 12]])
    np.testing.assert_allclose(project(matrix, pixels), expected)
    np.testing.assert_allclose(project(matrix * 1e-14, pixels), expected)


def test_three_copies_of_one_validation_point_are_not_three_checks():
    with pytest.raises(ValueError, match="distinct|repeat|independent|unique"):
        fit_homography(
            [[0, 0], [300, 0], [300, 200], [0, 200]],
            [[0, 0], [30, 0], [30, 20], [0, 20]],
            [[50, 50], [50, 50], [50, 50]],
            [[5, 5], [5, 5], [5, 5]],
            image_size_px=[301, 201],
        )


def test_exactly_mapped_validation_locations_stay_within_error_budget():
    calibration = _calibration()
    assert calibration["approved"]
    assert calibration["max_error_cm"] < 1e-8
    assert calibration["validation_count"] == 3
    np.testing.assert_allclose(project(calibration["homography_image_to_cm"],
                                       [[150, 100], [0, 0], [300, 200]]),
                               [[15, 10], [0, 0], [30, 20]], atol=1e-8)


def test_speed_violation_starts_a_new_track_instead_of_a_large_drift_sample():
    tracker = SingleTokenTracker(max_gap_s=0.5, max_speed_cm_s=10)
    calibration = _calibration()
    first = tracker.update([{"pixel_x": 10, "pixel_y": 10}], 0, calibration)
    jumped = tracker.update([{"pixel_x": 250, "pixel_y": 10}], 0.1, calibration)
    follow = tracker.update([{"pixel_x": 252, "pixel_y": 10}], 0.2, calibration)
    assert first["track_id"] != jumped["track_id"]
    assert jumped["association_break"] and jumped["reason"] == "ASSOCIATION_GAP"
    assert jumped["track_id"] == follow["track_id"]
    samples = flow_samples([first, jumped, follow])
    assert len(samples) == 1
    assert samples[0]["vx_cm_s"] == pytest.approx(2)


def test_camera_gap_cannot_generate_a_bridged_velocity_even_with_same_track_id():
    # A malformed/replayed same ID is still unable to bypass the elapsed-time gate.
    points = [
        {"t_s": 0, "x_cm": 0, "y_cm": 0, "observed": True, "track_id": "one"},
        {"t_s": 1, "x_cm": 10, "y_cm": 0, "observed": True, "track_id": "one"},
        {"t_s": 1.1, "x_cm": 10.1, "y_cm": 0, "observed": True, "track_id": "one"},
    ]
    samples = flow_samples(points, max_dt_s=0.5)
    assert len(samples) == 1
    assert samples[0]["vx_cm_s"] == pytest.approx(1)


def test_a_missing_detection_is_never_interpolated_into_a_flow_measurement():
    points = [
        {"t_s": 0, "x_cm": 0, "y_cm": 0, "observed": True, "track_id": "one"},
        {"t_s": 0.1, "x_cm": 1, "y_cm": 0, "observed": False, "track_id": "one"},
        {"t_s": 0.2, "x_cm": 2, "y_cm": 0, "observed": True, "track_id": "one"},
    ]
    assert flow_samples(points) == []


AUTH = {"Authorization": "Bearer audit-test"}


def _record(runtime, recording_id, calibration_id, *, profile_id=None, speed=1.0,
            x=5.0, y=5.0, age_s=0.1):
    """Fabricate an acquisition record only for policy testing; never camera evidence."""
    mono, utc = time.monotonic() - age_s, time.time() - age_s
    points, frame_ids = [], []
    for i in range(8):
        t = i * 0.2
        frame_id = f"{recording_id}-frame-{i}"
        runtime.store.put("frame", {
            "profile_id": profile_id, "camera_session_id": "audit-camera",
            "sequence": i, "received_mono_s": mono - 1.4 + t,
            "saved_at": utc - 1.4 + t,
            "test_fixture_origin": "SYNTHETIC_CONTRACT_TEST", "physical_validation": False,
        }, frame_id)
        frame_ids.append(frame_id)
        points.append({"t_s": t, "x_cm": x + speed * t, "y_cm": y,
                       "observed": True, "quality": 1.0, "track_id": recording_id + "-track",
                       "frame_id": frame_id})
    return runtime.store.put("recording", {
        "profile_id": profile_id, "camera_session_id": "audit-camera",
        "calibration_id": calibration_id, "points": points, "evidence_frame_ids": frame_ids,
        "recorded_at": utc, "data_origin": "MEASURED_TANK",
        "test_fixture_origin": "SYNTHETIC_CONTRACT_TEST", "physical_validation": False,
    }, recording_id)


@pytest.fixture
def measured_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("CHALK_ENABLED", "false")
    monkeypatch.setenv("PHOTON_ENABLED", "false")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "[]")
    app = create_app(Settings(data_dir=tmp_path, local_token="audit-test"))
    runtime = app.state.runtime
    runtime.camera.session_id = "audit-camera"
    monkeypatch.setattr(runtime.camera, "status", lambda: {
        "fresh": True, "running": True, "session_id": "audit-camera",
        "width": 301, "height": 201,
    })
    calibration = _calibration("audit-camera")
    runtime.store.put("calibration", calibration, calibration["calibration_id"])
    training = _record(runtime, "audit-training", calibration["calibration_id"])
    validation = _record(runtime, "audit-validation", calibration["calibration_id"], y=10)
    body = {"training_recording_ids": [training["id"]],
            "validation_recording_ids": [validation["id"]],
            "bounds": {"x_min_cm": 0, "x_max_cm": 30, "y_min_cm": 0, "y_max_cm": 20},
            "cell_size_cm": 1, "coverage_radius_cm": 30}
    flow = runtime.fit_recorded_flow(body)
    profile = runtime.register_profile({
        "id": "audit-measured-profile", "calibration_id": calibration["calibration_id"],
        "valid": True, "data_origin": "MEASURED_TANK", "token_class": "audit-float",
        "test_fixture_origin": "SYNTHETIC_CONTRACT_TEST", "physical_validation": False,
        "bounds": body["bounds"], "flow": flow,
        "max_validation_rmse_cm_s": 0.1, "revalidation_max_rmse_cm_s": 0.2,
        "observation_polygon_cm": [[0, 0], [30, 0], [30, 20], [0, 20]],
        "sources": [
            {"id": "A", "polygon_cm": [[0, 4], [1, 4], [1, 6], [0, 6]]},
            {"id": "B", "polygon_cm": [[0, 14], [1, 14], [1, 16], [0, 16]]},
        ],
        "traps": [],
        "transport": {"particles_per_source": 20, "dt_s": 0.1, "max_age_s": 5},
    })
    recording = _record(runtime, "audit-case-recording", calibration["calibration_id"],
                        profile_id=profile["id"], x=10, y=10)
    with TestClient(app) as client:
        yield client, runtime, profile, recording, body


def test_live_coordinates_require_the_immutable_recording_route(measured_contract):
    client, _, profile, recording, _ = measured_contract
    direct = client.post("/api/v1/cases", headers=AUTH, json={
        "profile_id": profile["id"], "calibration_id": profile["calibration_id"],
        "mode": "LIVE", "token_class": profile["token_class"], "camera_session_id": "audit-camera",
        "points": [{k: p[k] for k in ("t_s", "x_cm", "y_cm", "quality", "observed", "frame_id")}
                   for p in recording["points"]],
        "evidence_frame_ids": recording["evidence_frame_ids"],
    })
    assert direct.status_code == 409
    assert "immutable recording" in direct.text
    derived = client.post(f"/api/v1/recordings/{recording['id']}/case", json={}, headers=AUTH)
    assert derived.status_code == 200, derived.text
    assert derived.json()["recording_id"] == recording["id"]
    assert derived.json()["points"][0]["frame_id"] == recording["points"][0]["frame_id"]


def test_recording_splits_must_not_reuse_captures_or_frames(measured_contract):
    client, runtime, _, _, body = measured_contract
    same_recording = {**body, "validation_recording_ids": body["training_recording_ids"]}
    response = client.post("/api/v1/flow/fit-recordings", json=same_recording, headers=AUTH)
    assert response.status_code == 409 and "disjoint" in response.text
    duplicate = runtime.store.get("recording", body["training_recording_ids"][0])
    duplicate = runtime.store.put("recording", duplicate, "audit-duplicate-footage")
    response = client.post("/api/v1/flow/fit-recordings", headers=AUTH, json={
        **body, "validation_recording_ids": [duplicate["id"]],
    })
    assert response.status_code == 409 and "frames" in response.text


def test_frozen_flow_cannot_be_edited_inside_a_new_profile(measured_contract):
    client, _, profile, _, _ = measured_contract
    changed = copy.deepcopy(profile)
    changed["id"] = "audit-tampered-profile"
    changed["flow"]["nodes"][0]["vx_cm_s"] += 0.1
    response = client.post("/api/v1/profiles", json=changed, headers=AUTH)
    assert response.status_code == 409 and "changed after fitting" in response.text


def test_real_holdout_error_must_pass_the_frozen_profile_tolerance(measured_contract):
    client, runtime, profile, _, body = measured_contract
    validation = _record(runtime, "audit-incompatible-validation", profile["calibration_id"],
                         speed=3.0, y=10)
    flow = runtime.fit_recorded_flow({**body, "validation_recording_ids": [validation["id"]]})
    assert flow["diagnostics"]["validation_rmse_cm_s"] == pytest.approx(2.0)
    changed = {**profile, "id": "audit-high-error-profile", "flow": flow}
    response = client.post("/api/v1/profiles", json=changed, headers=AUTH)
    assert response.status_code == 409 and "max_validation_rmse_cm_s" in response.text


def test_fresh_preview_does_not_refresh_old_target_observations(measured_contract):
    client, runtime, profile, _, _ = measured_contract
    recording = _record(runtime, "audit-old-target", profile["calibration_id"],
                        profile_id=profile["id"], x=10, y=10, age_s=60)
    response = client.post(f"/api/v1/recordings/{recording['id']}/case", json={}, headers=AUTH)
    assert response.status_code == 200, response.text
    with pytest.raises(ValueError, match="Target observation is stale"):
        runtime.validate_live(response.json(), profile, require_target_fresh=True)


def test_post_disturbance_revalidation_does_not_revive_an_old_case(measured_contract):
    client, runtime, profile, recording, _ = measured_contract
    response = client.post(f"/api/v1/recordings/{recording['id']}/case", json={}, headers=AUTH)
    assert response.status_code == 200, response.text
    changed_at = time.time()
    runtime.store.put("rig_change", {"changed_at": changed_at})
    runtime.store.put("rig_check", {"checked_at": changed_at + 0.01, "profile_id": profile["id"]})
    with pytest.raises(ValueError, match="predates the latest rig disturbance"):
        runtime.validate_live(response.json(), profile)


def test_retained_endpoint_is_derived_from_a_stable_recording_inside_a_validated_trap(measured_contract):
    client, runtime, profile, _, _ = measured_contract
    retained_profile = runtime.register_profile({
        **profile, "id": "audit-retained-profile",
        "traps": [{"id": "pocket", "polygon_cm": [[10, 9], [12, 9], [12, 11], [10, 11]],
                   "retention": "absorbing", "validated": True}],
    })
    recording = _record(runtime, "audit-stationary", retained_profile["calibration_id"],
                        profile_id=retained_profile["id"], x=11, y=10, speed=0)
    response = client.post(f"/api/v1/recordings/{recording['id']}/case", headers=AUTH,
                           json={"observation_type": "retained_endpoint"})
    assert response.status_code == 200, response.text
    case = response.json()
    assert case["points"] == [] and case["endpoint"]["retained"] is True
    assert case["endpoint"]["x_cm"] == pytest.approx(11)
    assert case["recording_id"] == recording["id"]
    # The underlying observed history is preserved, despite endpoint-only inference.
    assert len(runtime.store.get("recording", recording["id"])["points"]) == 8


def test_retained_endpoint_cannot_bypass_the_permitted_observation_region(measured_contract):
    client, runtime, profile, _, _ = measured_contract
    retained_profile = runtime.register_profile({
        **profile, "id": "audit-excluded-pocket-profile",
        "observation_polygon_cm": [[15, 0], [30, 0], [30, 20], [15, 20]],
        "traps": [{"id": "excluded-pocket", "polygon_cm": [[10, 9], [12, 9], [12, 11], [10, 11]],
                   "retention": "absorbing", "validated": True}],
    })
    recording = _record(runtime, "audit-outside-observation-region", retained_profile["calibration_id"],
                        profile_id=retained_profile["id"], x=11, y=10, speed=0)
    response = client.post(f"/api/v1/recordings/{recording['id']}/case", headers=AUTH,
                           json={"observation_type": "retained_endpoint"})
    assert response.status_code == 409, response.text


def test_compute_and_sensitivity_share_one_cpu_budget(measured_contract, monkeypatch):
    """Mock numerical work to test admission, without claiming an estimate was computed."""
    _, runtime, profile, _, _ = measured_contract
    from apps.estimation import reeftrace_estimation

    counter_lock, overlap = threading.Lock(), threading.Event()
    active = maximum = 0

    def fake_estimate(_profile, _observation):
        nonlocal active, maximum
        with counter_lock:
            active += 1
            maximum = max(maximum, active)
            if active > 1:
                overlap.set()
        # Without the shared limit, a second worker overlaps and releases both.
        overlap.wait(0.1)
        with counter_lock:
            active -= 1
        return {"status": "unknown", "ranked_source": None, "relative_support": {},
                "reason_codes": ["MOCKED_FOR_CONCURRENCY_TEST"], "sensitivity_results": [],
                "physical_validation": False}

    monkeypatch.setattr(reeftrace_estimation, "estimate", fake_estimate)
    cases = [runtime.store.add_case({"profile_id": profile["id"], "mode": "REPLAY",
                                    "points": [], "evidence_frame_ids": []}) for _ in range(2)]
    evidence = runtime.store.put("estimate", {"case_id": cases[1]["id"], "status": "unknown"})
    runtime.store.update_case(cases[1]["id"], 1, {"evidence_id": evidence["id"]})

    async def together():
        return await asyncio.gather(runtime.compute(cases[0]["id"]),
                                    runtime.sensitivity(cases[1]["id"]))

    results = asyncio.run(together())
    assert maximum == 1 and active == 0
    assert results[0]["reason_codes"] == ["MOCKED_FOR_CONCURRENCY_TEST"]
    assert results[1]["combined_report"]["reason_codes"] == ["MOCKED_FOR_CONCURRENCY_TEST"]
