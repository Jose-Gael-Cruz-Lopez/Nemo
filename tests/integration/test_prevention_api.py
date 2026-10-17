"""Actual prevention API/SQLite behavior; fixture flows and all trials are policy test data.

No camera, model provider, messaging or physical experiment is used by these tests.
"""

import copy
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.api.reeftrace_api.services.prevention import COMPARISON_KIND, TRIAL_KIND
from apps.transport.reeftrace_transport import fit_flow

AUTH = {"Authorization": "Bearer prevention-test-only"}
ROOT = "/api/v1/prevention"


@pytest.fixture
def app(tmp_path, monkeypatch):
    for name in ("CHALK_ENABLED", "PHOTON_ENABLED", "GROK_VOICE_ENABLED"):
        monkeypatch.setenv(name, "false")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "[]")
    return create_app(Settings(data_dir=tmp_path, local_token="prevention-test-only"))


def seed(runtime, origin="SYNTHETIC", *, shared_flow=False, shared_recording=False):
    """Seed immutable policy fixtures, not a claim of an actual physical capture."""
    bounds = {"x_min_cm": 0, "x_max_cm": 10, "y_min_cm": 0, "y_max_cm": 10}
    samples = [{"x_cm": x, "y_cm": y, "vx_cm_s": 1, "vy_cm_s": 0}
               for x in (0, 5, 10) for y in (0, 5, 10)]
    flow = fit_flow(samples, bounds, validation_samples=copy.deepcopy(samples),
                    coverage_radius_cm=20, data_origin=origin)
    sources = [{"id": sid, "polygon_cm": [[1, y], [2, y], [2, y + 1], [1, y + 1]]}
               for sid, y in (("A", 2), ("B", 7))]
    profiles = []
    for layout in ("baseline", "intervention"):
        frozen_flow = copy.deepcopy(flow)
        if origin == "MEASURED_TANK":
            frozen_flow["provenance"] = {"training_recording_ids": ["shared" if shared_recording else layout + "-train"],
                                         "validation_recording_ids": [layout + "-validation"]}
            if shared_flow and profiles:
                frozen_flow = profiles[0]["flow"]
            else:
                frozen_flow = runtime.store.put("flow", frozen_flow)
        profile = {"valid": True, "data_origin": origin, "bounds": bounds, "flow": frozen_flow,
                   "sources": sources, "token_class": "policy-test-token", "calibration_id": "policy-map",
                   "max_validation_rmse_cm_s": 0.1, "revalidation_max_rmse_cm_s": 0.1,
                   "transport": {"dt_s": 0.2, "max_age_s": 20, "diffusivity_cm2_s": 0.01},
                   "traps": [] if layout == "baseline" else [{"id": "mesh", "validated": True,
                       "retention": "absorbing", "polygon_cm": [[5, 1], [6, 1], [6, 9], [5, 9]]}]}
        profiles.append(runtime.store.put("profile", profile))
    case = runtime.store.add_case({"profile_id": profiles[0]["id"], "mode": "REPLAY",
                                   "points": [], "evidence_frame_ids": []})
    runtime.store.put_case_result("estimate", {"case_id": case["id"], "status": "unknown",
        "data_origin": origin, "confidence_kind": "relative_support_not_probability"},
        case["id"], case["revision"], changes={"state": "INVESTIGATE"})
    return {"case_id": case["id"], "baseline_profile_id": profiles[0]["id"],
            "intervention_profile_id": profiles[1]["id"], "protected_zone_cm": [[8, 1], [9, 1], [9, 9], [8, 9]],
            "name": "Policy fixture comparison", "horizon_s": 10, "particles": 20, "trials_per_source": 2}


def create(client, app, **kwargs):
    body = seed(app.state.runtime, **kwargs)
    response = client.post(ROOT + "/comparisons", headers=AUTH, json=body)
    assert response.status_code == 200, response.text
    return response.json(), body


def trial(key="trial-one", **changes):
    return {"trial_key": key, "layout": "baseline", "source_id": "A",
            "data_origin": "SYNTHETIC_DEMO", "outcome": "zone_entry", "entry_time_s": 7,
            "interception_time_s": None, "token_accounted": True, "physical_confirmed": False,
            "horizon_completed": True, "note": "Explicit test fixture, not physical evidence.",
            "recording_id": None, **changes}


def capture_fixture(runtime, comparison, *, start_at=None, elapsed_s=(0.1, 9.9), **changes):
    """Recorder-shaped immutable policy fixture; never an actual camera capture."""
    start_at = comparison["created_at"] + 1 if start_at is None else start_at
    points, frame_ids = [], []
    for elapsed in elapsed_s:
        frame = runtime.store.put("frame", {
            "profile_id": comparison["baseline_profile_id"],
            "received_utc": datetime.fromtimestamp(start_at + elapsed, UTC).isoformat()})
        frame_ids.append(frame["id"])
        points.append({"t_s": elapsed, "frame_id": frame["id"], "observed": False})
    return runtime.store.put("recording", {
        "profile_id": comparison["baseline_profile_id"], "data_origin": "MEASURED_TANK",
        "recorded_at": start_at + 10, "points": points, "evidence_frame_ids": frame_ids,
        "timestamp_kind": "host_receipt_not_exposure", **changes})


def physical_trial(recording_id, key="physical-release", **changes):
    return trial(key, data_origin="OPERATOR_REPORTED_PHYSICAL", physical_confirmed=True,
                 recording_id=recording_id, **changes)


def test_unknown_source_can_anchor_a_conditional_comparison_without_changing_source_evidence(app):
    with TestClient(app) as client:
        detail, body = create(client, app)
        c = detail["comparison"]
        assert c["source_evidence_status"] == "unknown"
        assert c["physical_validation"] is False and c["data_origin"] == "SYNTHETIC"
        assert c["plan"]["frozen_before_trials"] is True
        assert c["plan"]["expected_total"] == 8
        assert c["numerical_report"]["physical_validation"] is False
        assert c["numerical_report"]["recommendation"] == "INTERVENTION"
        assert client.get(f"/api/v1/cases/{body['case_id']}/evidence").json()["id"] == c["source_evidence_id"]
        assert client.get(ROOT + "/comparisons").json()[0]["id"] == c["id"]
        assert client.get(ROOT + "/comparisons/" + c["id"]).json() == detail
        assert detail["is_current"] is True
        assert detail["evaluation"]["by_origin"]["OPERATOR_REPORTED_PHYSICAL"]["layouts"]["baseline"]["released"] == 0
        assert app.state.runtime.store.list("prevention_investigation") == []


def test_all_prevention_mutations_require_operator_and_never_actuate(app):
    with TestClient(app) as client:
        for path, body in (("/comparisons", {}), ("/demo", {}),
                           ("/comparisons/missing/trials", {}),
                           ("/comparisons/missing/investigate", {"text": "Explain"})):
            assert client.post(ROOT + path, json=body).status_code == 401
        assert app.state.runtime.store.list(COMPARISON_KIND) == []
        status = client.get("/api/v1/status").json()
        assert status["camera"]["running"] is False and status["hardware_actuation"] is False


def test_trial_retry_is_exactly_idempotent_and_different_replay_conflicts(app):
    with TestClient(app) as client:
        detail, _ = create(client, app)
        url = ROOT + "/comparisons/" + detail["comparison"]["id"] + "/trials"
        first = client.post(url, headers=AUTH, json=trial())
        again = client.post(url, headers=AUTH, json=trial())
        assert first.status_code == again.status_code == 200
        assert first.json() == again.json()
        assert len(first.json()["trials"]) == 1
        assert client.post(url, headers=AUTH, json=trial(note="Different immutable claim")).status_code == 409
        assert len(app.state.runtime.store.list(TRIAL_KIND)) == 1


def test_missing_and_unresolved_remain_in_plan_bounds_and_snapshot_is_content_addressed(app):
    with TestClient(app) as client:
        detail, _ = create(client, app)
        before = detail["evaluation"]["snapshot_hash"]
        cid = detail["comparison"]["id"]
        response = client.post(ROOT + f"/comparisons/{cid}/trials", headers=AUTH,
            json=trial(outcome="unresolved", entry_time_s=None, token_accounted=False,
                       horizon_completed=False))
        assert response.status_code == 200, response.text
        detail = response.json()
        group = detail["evaluation"]["by_origin"]["SYNTHETIC_DEMO"]
        baseline = group["layouts"]["baseline"]
        assert (baseline["released"], baseline["planned"], baseline["missing_planned"],
                baseline["unresolved"], baseline["unaccounted"]) == (1, 4, 3, 1, 1)
        assert baseline["entry_rate_bounds"]["lower"] == 0
        assert baseline["entry_rate_bounds"]["upper"] == 1
        assert baseline["observed_entry_rate_bounds"]["denominator"] == 1
        assert group["effect_bounds"]["lower"] == -1 and group["effect_bounds"]["upper"] == 1
        assert group["plan"]["complete"] is False and group["supports_causal_claim"] is False
        assert detail["evaluation"]["snapshot_hash"] != before
        assert client.get(ROOT + f"/comparisons/{cid}").json()["evaluation"] == detail["evaluation"]


@pytest.mark.parametrize("change", ["stop", "recompute"])
def test_source_change_rejects_new_trial_and_archives_readable_comparison(app, change):
    with TestClient(app) as client:
        detail, body = create(client, app)
        c = detail["comparison"]
        if change == "stop":
            app.state.runtime.store.stop_case(body["case_id"])
        else:
            case = app.state.runtime.store.case(body["case_id"])
            app.state.runtime.store.update_case(case["id"], case["revision"], {"state": "INVESTIGATE"})
        assert client.post(ROOT + f"/comparisons/{c['id']}/trials", headers=AUTH, json=trial()).status_code == 409
        assert client.post(ROOT + "/comparisons", headers=AUTH, json=body).status_code == (409 if change == "stop" else 200)
        archival = client.get(ROOT + f"/comparisons/{c['id']}").json()
        assert archival["is_current"] is False and archival["archive_reason"] == "CASE_CHANGED_OR_STOPPED"
        assert archival["trials"] == []


def test_source_stop_during_comparison_prevents_stale_commit(app, monkeypatch):
    import apps.estimation.reeftrace_estimation.prevention as numerical

    original = numerical.compare_layouts
    started, release = threading.Event(), threading.Event()

    def slow(*args, **kwargs):
        started.set()
        assert release.wait(2)
        return original(*args, **kwargs)

    monkeypatch.setattr(numerical, "compare_layouts", slow)
    with TestClient(app) as client, ThreadPoolExecutor() as executor:
        body = seed(app.state.runtime)
        future = executor.submit(client.post, ROOT + "/comparisons", headers=AUTH, json=body)
        assert started.wait(2)
        app.state.runtime.store.stop_case(body["case_id"])
        release.set()
        response = future.result(timeout=5)
        assert response.status_code == 409
        assert app.state.runtime.store.list(COMPARISON_KIND) == []


@pytest.mark.parametrize("changes", [
    {"outcome": "no_entry", "entry_time_s": None, "horizon_completed": False},
    {"outcome": "intercepted_before_entry", "entry_time_s": None, "interception_time_s": 3,
     "horizon_completed": False},
    {"entry_time_s": None}, {"entry_time_s": -1}, {"entry_time_s": float("inf")},
    {"interception_time_s": 2}, {"token_accounted": False}, {"physical_confirmed": True},
    {"data_origin": "OPERATOR_REPORTED_PHYSICAL", "physical_confirmed": False},
    {"unexpected_truth": "A"},
    {"entry_time_s": "7"}, {"horizon_completed": "true"},
])
def test_contradictory_partial_or_nonfinite_trial_claims_are_rejected(app, changes):
    with TestClient(app) as client:
        detail, _ = create(client, app)
        payload = trial(**changes)
        # Send a raw Infinity token to exercise server-side finite validation.
        import json
        response = client.post(ROOT + f"/comparisons/{detail['comparison']['id']}/trials", headers={
            **AUTH, "Content-Type": "application/json"}, content=json.dumps(payload))
        assert response.status_code == (409 if changes.get("entry_time_s") == float("inf") else 422)
        assert app.state.runtime.store.list(TRIAL_KIND) == []


def test_synthetic_layout_cannot_accept_physical_claim_and_quota_is_frozen(app):
    with TestClient(app) as client:
        detail, _ = create(client, app)
        url = ROOT + f"/comparisons/{detail['comparison']['id']}/trials"
        assert client.post(url, headers=AUTH, json=trial(data_origin="OPERATOR_REPORTED_PHYSICAL",
                                                      physical_confirmed=True)).status_code == 409
        assert client.post(url, headers=AUTH, json=trial()).status_code == 200
        assert client.post(url, headers=AUTH, json=trial("second")).status_code == 200
        assert client.post(url, headers=AUTH, json=trial("third")).status_code == 409


def test_invalid_anchor_mismatched_baseline_or_short_horizon_cannot_publish_claim(app):
    with TestClient(app) as client:
        body = seed(app.state.runtime)
        wrong = {**body, "baseline_profile_id": body["intervention_profile_id"],
                 "intervention_profile_id": body["baseline_profile_id"]}
        assert client.post(ROOT + "/comparisons", headers=AUTH, json=wrong).status_code == 409
        valid = client.post(ROOT + "/comparisons", headers=AUTH, json=body).json()
        cid = valid["comparison"]["id"]
        # The schema accepts this finite time, but the frozen plan's shorter horizon does not.
        assert client.post(ROOT + f"/comparisons/{cid}/trials", headers=AUTH,
                           json=trial(entry_time_s=11)).status_code == 409
        case = app.state.runtime.store.case(body["case_id"])
        app.state.runtime.store.put_case_result("estimate", {"case_id": case["id"], "status": "invalid"},
            case["id"], case["revision"], changes={"state": "INVESTIGATE"})
        assert client.post(ROOT + "/comparisons", headers=AUTH, json=body).status_code == 409


def test_concurrent_duplicate_trial_is_saved_once(app):
    with TestClient(app) as client, ThreadPoolExecutor() as pool:
        detail, _ = create(client, app)
        url = ROOT + f"/comparisons/{detail['comparison']['id']}/trials"
        calls = [pool.submit(client.post, url, headers=AUTH, json=trial()) for _ in range(2)]
        responses = [future.result(timeout=5) for future in calls]
        assert all(response.status_code == 200 for response in responses)
        assert responses[0].json()["trials"] == responses[1].json()["trials"]
        assert len(app.state.runtime.store.list(TRIAL_KIND)) == 1


def test_one_recording_cannot_be_counted_as_two_releases_or_sources_and_retry_is_idempotent(app):
    with TestClient(app) as client:
        detail, _ = create(client, app, origin="MEASURED_TANK")
        comparison = detail["comparison"]
        recording = capture_fixture(app.state.runtime, comparison)
        url = ROOT + f"/comparisons/{comparison['id']}/trials"
        payload = physical_trial(recording["id"])
        first = client.post(url, headers=AUTH, json=payload)
        assert first.status_code == 200, first.text
        assert client.post(url, headers=AUTH, json=payload).json() == first.json()
        for source_id in ("A", "B"):
            response = client.post(url, headers=AUTH, json=physical_trial(
                recording["id"], "duplicate-" + source_id, source_id=source_id))
            assert response.status_code == 409
            assert "fresh release" in response.json()["detail"]
        saved = client.get(ROOT + f"/comparisons/{comparison['id']}").json()
        assert len(saved["trials"]) == 1
        physical = saved["evaluation"]["by_origin"]["OPERATOR_REPORTED_PHYSICAL"]
        assert physical["layouts"]["baseline"]["released"] == 1
        assert physical["physical_outcomes_automatically_verified"] is False
        assert saved["trials"][0]["outcome_verification"] == "operator_reported_not_automatically_camera_verified"


def test_recording_reuse_conflicts_atomically_for_different_trial_keys(app):
    with TestClient(app) as client, ThreadPoolExecutor() as pool:
        detail, _ = create(client, app, origin="MEASURED_TANK")
        comparison = detail["comparison"]
        recording = capture_fixture(app.state.runtime, comparison)
        url = ROOT + f"/comparisons/{comparison['id']}/trials"
        calls = [pool.submit(client.post, url, headers=AUTH,
                            json=physical_trial(recording["id"], key))
                 for key in ("concurrent-one", "concurrent-two")]
        responses = [future.result(timeout=5) for future in calls]
        assert sorted(response.status_code for response in responses) == [200, 409]
        assert len(app.state.runtime.store.list(TRIAL_KIND)) == 1


def test_recording_is_one_release_even_across_two_prospectively_frozen_comparisons(app):
    with TestClient(app) as client:
        first, body = create(client, app, origin="MEASURED_TANK")
        second = client.post(ROOT + "/comparisons", headers=AUTH, json=body).json()
        recording = capture_fixture(app.state.runtime, second["comparison"])
        payload = physical_trial(recording["id"])
        for detail, status in ((first, 200), (second, 409)):
            url = ROOT + f"/comparisons/{detail['comparison']['id']}/trials"
            assert client.post(url, headers=AUTH, json=payload).status_code == status
        assert len(app.state.runtime.store.list(TRIAL_KIND)) == 1


@pytest.mark.parametrize("failure", ["completed_before_plan", "started_before_plan",
                                    "missing_completion", "missing_frames", "missing_elapsed",
                                    "naive_receipt", "wrong_origin", "wrong_layout"])
def test_linked_capture_requires_prospective_finite_recorder_lineage(app, failure):
    with TestClient(app) as client:
        detail, _ = create(client, app, origin="MEASURED_TANK")
        comparison = detail["comparison"]
        runtime = app.state.runtime
        changes = {}
        start_at = comparison["created_at"] - 1 if failure == "started_before_plan" else None
        if failure == "completed_before_plan":
            changes["recorded_at"] = comparison["created_at"] - 0.1
        elif failure == "missing_completion":
            changes["recorded_at"] = None
        elif failure == "missing_frames":
            changes.update(points=[], evidence_frame_ids=[])
        elif failure in {"missing_elapsed", "naive_receipt"}:
            received = datetime.fromtimestamp(comparison["created_at"] + 1, UTC)
            if failure == "naive_receipt":
                received = received.replace(tzinfo=None)
            frame = runtime.store.put("frame", {"received_utc": received.isoformat()})
            point = {"frame_id": frame["id"]}
            if failure != "missing_elapsed":
                point["t_s"] = 0.1
            changes.update(points=[point], evidence_frame_ids=[frame["id"]])
        elif failure == "wrong_origin":
            changes["data_origin"] = "SYNTHETIC"
        elif failure == "wrong_layout":
            changes["profile_id"] = comparison["intervention_profile_id"]
        recording = capture_fixture(runtime, comparison, start_at=start_at, **changes)
        url = ROOT + f"/comparisons/{comparison['id']}/trials"
        response = client.post(url, headers=AUTH, json=physical_trial(recording["id"]))
        assert response.status_code == 409, response.text
        assert runtime.store.list(TRIAL_KIND) == []


@pytest.mark.parametrize("shared_flow,shared_recording", [(True, False), (False, True)])
def test_measured_layouts_need_distinct_independent_flow_records(app, shared_flow, shared_recording):
    with TestClient(app) as client:
        body = seed(app.state.runtime, "MEASURED_TANK", shared_flow=shared_flow,
                    shared_recording=shared_recording)
        response = client.post(ROOT + "/comparisons", headers=AUTH, json=body)
        assert response.status_code == 409
        assert app.state.runtime.store.list(COMPARISON_KIND) == []


def test_reported_physical_and_synthetic_ledgers_never_share_rates(app):
    with TestClient(app) as client:
        detail, _ = create(client, app, origin="MEASURED_TANK")
        url = ROOT + f"/comparisons/{detail['comparison']['id']}/trials"
        assert client.post(url, headers=AUTH, json=trial()).status_code == 200
        response = client.post(url, headers=AUTH, json=trial("physical-one", layout="intervention",
            data_origin="OPERATOR_REPORTED_PHYSICAL", physical_confirmed=True,
            outcome="intercepted_before_entry", entry_time_s=None, interception_time_s=4))
        assert response.status_code == 200, response.text
        groups = response.json()["evaluation"]["by_origin"]
        assert groups["SYNTHETIC_DEMO"]["layouts"]["baseline"]["released"] == 1
        assert groups["SYNTHETIC_DEMO"]["layouts"]["intervention"]["released"] == 0
        physical = groups["OPERATOR_REPORTED_PHYSICAL"]
        assert physical["layouts"]["baseline"]["released"] == 0
        assert physical["layouts"]["intervention"]["captured_before_entry"] == 1
        assert physical["physical_outcomes_automatically_verified"] is False
        assert physical["supports_causal_claim"] is False


def test_trial_snapshot_compare_and_swap_rejects_stale_investigation_receipt(app):
    with TestClient(app) as client:
        detail, _ = create(client, app)
        comparison = detail["comparison"]
        old_hash = detail["evaluation"]["snapshot_hash"]
        client.post(ROOT + f"/comparisons/{comparison['id']}/trials", headers=AUTH, json=trial())
        service = app.state.runtime.prevention
        with pytest.raises(ValueError, match="evaluation changed"):
            service.commit_for_comparison("prevention_investigation", {"result": "stale"}, comparison,
                                          expected_evaluation_hash=old_hash)
        assert app.state.runtime.store.list("prevention_investigation") == []
        latest = service.comparison_detail(comparison["id"])["evaluation"]["snapshot_hash"]
        receipt = service.commit_for_comparison("prevention_investigation", {"evaluation_digest": latest},
                                                comparison, expected_evaluation_hash=latest)
        assert receipt["evaluation_digest"] == latest


def test_evaluation_content_address_is_independent_of_input_trial_list_order(app):
    with TestClient(app) as client:
        detail, _ = create(client, app)
        comparison = detail["comparison"]
        url = ROOT + f"/comparisons/{comparison['id']}/trials"
        client.post(url, headers=AUTH, json=trial())
        response = client.post(url, headers=AUTH, json=trial("second", layout="intervention"))
        detail = response.json()
        assert detail["evaluation"]["by_origin"]["SYNTHETIC_DEMO"]["plan"]["order_followed"] is True
        assert app.state.runtime.prevention.evaluate(comparison, list(reversed(detail["trials"]))) == detail["evaluation"]


def test_demo_is_idempotent_archival_and_explicitly_nonphysical(app):
    with TestClient(app) as client:
        first = client.post(ROOT + "/demo", headers=AUTH, json={})
        assert first.status_code == 200, first.text
        detail = first.json()
        cid = detail["comparison"]["id"]
        assert detail["comparison"]["data_origin"] == "SYNTHETIC"
        assert len(detail["trials"]) == 30
        assert all(t["data_origin"] == "SYNTHETIC_DEMO" and not t["physical_confirmed"] for t in detail["trials"])
        groups = detail["evaluation"]["by_origin"]
        assert groups["SYNTHETIC_DEMO"]["plan"]["complete"] is True
        assert groups["SYNTHETIC_DEMO"]["plan"]["balanced"] is True
        assert groups["OPERATOR_REPORTED_PHYSICAL"]["plan"]["recorded_total"] == 0
        assert client.post(ROOT + "/demo", headers=AUTH, json={}).json() == detail
        app.state.runtime.store.stop_case(detail["comparison"]["case_id"])
        replacement = client.post(ROOT + "/demo", headers=AUTH, json={})
        assert replacement.status_code == 200, replacement.text
        assert replacement.json()["comparison"]["id"] != cid
        assert client.get(ROOT + f"/comparisons/{cid}").json()["is_current"] is False
        assert app.state.runtime.camera.status()["running"] is False
