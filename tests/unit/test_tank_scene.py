"""Read-only scene contracts against SQLite policy fixtures, never a real tank.

The measured-shaped fixtures below test provenance rejection only. They are not
measurements, and no camera, model provider, message or actuator is opened.
"""

import copy
import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.api.reeftrace_api.schemas.prevention import TrialInput
from apps.api.reeftrace_api.services.prevention import COMPARISON_KIND, digest
from apps.api.reeftrace_api.services.tank_scene import build_tank_scene
from apps.transport.reeftrace_transport import fit_flow

AUTH = {"Authorization": "Bearer scene-test-only"}
ROOT = "/api/v1/prevention/comparisons"


@pytest.fixture
def app(tmp_path):
    return create_app(Settings(data_dir=tmp_path, local_token="scene-test-only"))


def seed(client, app, origin="SYNTHETIC"):
    runtime = app.state.runtime
    bounds = {"x_min_cm": 0, "x_max_cm": 10, "y_min_cm": 0, "y_max_cm": 10}
    samples = [{"x_cm": x, "y_cm": y, "vx_cm_s": 1, "vy_cm_s": 0}
               for x in (0, 5, 10) for y in (0, 5, 10)]
    sources = [{"id": sid, "polygon_cm": [[1, y], [2, y], [2, y + 1], [1, y + 1]]}
               for sid, y in (("A", 2), ("B", 7))]
    profiles = []
    for layout in ("baseline", "intervention"):
        flow = fit_flow(samples, bounds, validation_samples=copy.deepcopy(samples),
                        coverage_radius_cm=20, data_origin=origin)
        if origin == "MEASURED_TANK":
            flow["provenance"] = {"training_recording_ids": [layout + "-train"],
                                  "validation_recording_ids": [layout + "-validation"]}
            flow = runtime.store.put("flow", flow)
        profiles.append(runtime.store.put("profile", {
            "valid": True, "data_origin": origin, "bounds": bounds, "flow": flow,
            "sources": sources, "token_class": "scene-policy-fixture", "calibration_id": "scene-map",
            "max_validation_rmse_cm_s": 0.1, "revalidation_max_rmse_cm_s": 0.1,
            "transport": {"dt_s": 0.2, "max_age_s": 20, "diffusivity_cm2_s": 0.01},
            "traps": [] if layout == "baseline" else [{"id": "mesh", "validated": True,
                "retention": "absorbing", "polygon_cm": [[5, 1], [6, 1], [6, 9], [5, 9]]}]}))
    case = runtime.store.add_case({"profile_id": profiles[0]["id"], "mode": "REPLAY",
                                   "points": [], "evidence_frame_ids": []})
    runtime.store.put_case_result("estimate", {"case_id": case["id"], "status": "unknown",
        "data_origin": origin, "confidence_kind": "relative_support_not_probability"},
        case["id"], case["revision"], changes={"state": "INVESTIGATE"})
    response = client.post(ROOT, headers=AUTH, json={"case_id": case["id"],
        "baseline_profile_id": profiles[0]["id"], "intervention_profile_id": profiles[1]["id"],
        "protected_zone_cm": [[8, 1], [9, 1], [9, 9], [8, 9]],
        "name": "Scene policy fixture", "horizon_s": 10, "particles": 20, "trials_per_source": 2})
    assert response.status_code == 200, response.text
    return response.json()


def url(detail):
    return (ROOT + "/" + detail["comparison"]["id"] + "/scene?evaluation_snapshot_hash="
            + detail["evaluation"]["snapshot_hash"])


def replace(runtime, kind, record):
    """Explicit test-only corruptor for adversarial immutable-artifact tests."""
    with runtime.store.connection() as db:
        db.execute("UPDATE records SET payload=? WHERE kind=? AND id=?",
                   (json.dumps(record, allow_nan=False), kind, record["id"]))


def trial(**changes):
    return TrialInput(**{"trial_key": "scene-release", "layout": "baseline", "source_id": "A",
        "data_origin": "SYNTHETIC_DEMO", "outcome": "zone_entry", "entry_time_s": 7,
        "interception_time_s": None, "token_accounted": True, "physical_confirmed": False,
        "horizon_completed": True, "note": "Policy fixture, not actual physical evidence.",
        "recording_id": None, **changes})


def recorded_fixture(runtime, detail, *, gap_only=False):
    """Prospective recorder-shaped fixture with deliberately missing detections."""
    comparison = detail["comparison"]
    profile_id = comparison["baseline_profile_id"]
    runtime.store.put("calibration", {"approved": True, "units": "cm",
        "plane": "measured_water_surface", "camera_session_id": "scene-camera"}, "scene-map")
    start = comparison["created_at"] + 1
    raw = [
        {"t_s": 0.1, "x_cm": 1, "y_cm": 2, "track_id": "track-1", "observed": True},
        {"t_s": 0.3, "x_cm": 1.2, "y_cm": 2, "track_id": "track-1", "observed": True},
        {"t_s": 0.4, "observed": False, "reason": "NO_DETECTION"},
        {"t_s": 0.6, "x_cm": 1.5, "y_cm": 2, "track_id": "track-1", "observed": True},
        {"t_s": 0.7, "x_cm": 1.6, "y_cm": 2, "track_id": "track-1", "observed": True},
        {"t_s": 1.5, "x_cm": 2, "y_cm": 2, "track_id": "track-1", "observed": True},
        {"t_s": 1.6, "x_cm": 2.1, "y_cm": 2, "observed": True},
        {"t_s": 1.7, "x_cm": 11, "y_cm": 2, "track_id": "track-1", "observed": True},
        {"t_s": 1.9, "x_cm": 2.3, "y_cm": 2, "track_id": "track-2", "observed": True},
    ]
    if gap_only:
        raw = [{"t_s": point["t_s"], "observed": False, "reason": "NO_DETECTION"} for point in raw]
    frame_ids, points = [], []
    for index, point in enumerate(raw):
        frame = runtime.store.put("frame", {"profile_id": profile_id,
            "camera_session_id": "scene-camera",
            "sequence": 1 + 3 * index, "received_mono_s": 1000 + point["t_s"],
            "received_utc": datetime.fromtimestamp(start + point["t_s"], UTC).isoformat(),
            "path": "/private/camera/image.jpg", "private_secret": "do-not-export"})
        frame_ids.append(frame["id"])
        points.append({**point, "frame_id": frame["id"], "pixel_x": 500, "pixel_y": 250})
    recording = runtime.store.put("recording", {"profile_id": profile_id,
        "data_origin": "MEASURED_TANK", "calibration_id": "scene-map",
        "camera_session_id": "scene-camera", "recorded_at": start + 10,
        "points": points, "evidence_frame_ids": frame_ids,
        "timestamp_kind": "host_receipt_not_exposure", "private_secret": "do-not-export"})
    detail = runtime.prevention.add_trial(comparison["id"], trial(
        data_origin="OPERATOR_REPORTED_PHYSICAL", physical_confirmed=True, recording_id=recording["id"]))
    return detail, recording


def test_synthetic_scene_preserves_full_ensemble_and_plan_counts_without_rerunning(app, monkeypatch):
    with TestClient(app) as client:
        detail = seed(client, app)
        runtime = app.state.runtime
        before = {kind: runtime.store.list(kind) for kind in (COMPARISON_KIND, "prevention_trial", "recording", "frame")}

        def forbidden(*args, **kwargs):
            raise AssertionError("A read-only scene must not simulate, capture, invoke a provider or write")

        import apps.estimation.reeftrace_estimation.prevention as numerical
        monkeypatch.setattr(numerical, "compare_layouts", forbidden)
        monkeypatch.setattr(runtime.store, "put", forbidden)
        monkeypatch.setattr(runtime, "record", forbidden)
        response = client.get(url(detail))
        assert response.status_code == 200, response.text
        scene = response.json()
        assert response.headers["cache-control"] == "no-store"
        assert scene["kind"] == "TANK_RIG_SCENE" and scene["schema_version"] == 1
        assert scene["units"] == {"position": "cm", "time": "s", "velocity": "cm/s"}
        assert scene["vertical"] == {"mode": "SCHEMATIC_SURFACE_ONLY", "surface_z_cm": 0,
                                    "measured_depth_cm": None, "physical_geometry_verified": False}
        assert scene["physical_validation"] is False
        assert scene["actual"]["status"] == "NOT_CAPTURED" and scene["actual"]["recordings"] == []
        assert scene["actual"]["positional_error_metrics"] is None
        assert scene["results"]["by_origin"] == detail["evaluation"]["by_origin"]
        for row, original in zip(scene["results"]["rows"], detail["comparison"]["numerical_report"]["results"], strict=True):
            for layout in ("baseline", "intervention"):
                assert row[layout] == original[layout]
                assert row[layout]["particles"] == 20
        assert scene["results"]["by_origin"]["OPERATOR_REPORTED_PHYSICAL"]["layouts"]["baseline"]["planned"] == 4
        assert scene["results"]["by_origin"]["OPERATOR_REPORTED_PHYSICAL"]["layouts"]["baseline"]["missing_planned"] == 4
        assert len(scene["simulation"]["paths"]) == 24
        assert all(len(path["points"]) <= 80 for path in scene["simulation"]["paths"])
        assert all(node["supported"] is True and node["vx_cm_s"] == 1 for field in scene["vectors"] for node in field["nodes"])
        assert all(field["time_varying"] is False for field in scene["vectors"])
        expected_hash = scene.pop("scene_sha256")
        assert expected_hash == digest(scene)
        # View-only query flags cannot silently change authoritative denominators.
        filtered = client.get(url(detail) + "&layout=baseline&source=A").json()
        assert filtered["results"] == scene["results"]
        assert filtered["simulation"]["paths"] == scene["simulation"]["paths"]
        assert before == {kind: runtime.store.list(kind) for kind in before}


def test_legacy_paths_are_clipped_without_inventing_event_positions_or_support(app):
    with TestClient(app) as client:
        detail = seed(client, app)
        comparison = detail["comparison"]
        comparison["numerical_report"]["nominal_paths"] = [{"layout": "baseline", "source_id": "A", "paths": [
            {"particle_index": 0, "zone_entry_s": 0.9, "capture_s": 2.0, "supported": True,
             "points": [{"t_s": t, "x_cm": 1 + t, "y_cm": 2} for t in (0, 0.5, 1, 2)]},
            {"particle_index": 1, "zone_entry_s": None, "capture_s": None, "supported": False,
             "points": [{"t_s": t, "x_cm": 1 + t, "y_cm": 2} for t in (0, 0.5, 1)]}]}]
        replace(app.state.runtime, COMPARISON_KIND, comparison)
        detail = app.state.runtime.prevention.comparison_detail(comparison["id"])
        scene = client.get(url(detail)).json()
        visible, unsupported = scene["simulation"]["paths"]
        assert visible["display_stop_s"] == 0.9
        assert [point["t_s"] for point in visible["points"]] == [0, 0.5]
        assert visible["sampling"] == "LEGACY_DECIMATED_REPRESENTATIVE"
        assert visible["counts_derived_from_path"] is False
        assert unsupported["points"] == [] and unsupported["support_status"] == "UNSUPPORTED_PATH_WITHHELD"
        assert scene["results"]["rows"][0]["baseline"]["particles"] == 20


def test_measured_scene_is_authenticated_and_retains_unaligned_segments_and_gaps(app):
    with TestClient(app) as client:
        detail = seed(client, app, "MEASURED_TANK")
        detail, recording = recorded_fixture(app.state.runtime, detail)
        assert client.get(url(detail)).status_code == 401
        response = client.get(url(detail), headers=AUTH)
        assert response.status_code == 200, response.text
        scene = response.json()
        actual = scene["actual"]
        assert actual["status"] == "RECORDED_TRACKS_AVAILABLE"
        assert actual["clock"] == "CAPTURE_START_UNALIGNED" and actual["release_alignment"] == "MISSING"
        assert actual["positional_error_metrics"] is None and scene["physical_validation"] is False
        record = actual["recordings"][0]
        assert record["recording_content_hash"] == digest(recording)
        assert record["outcome_automatically_verified"] is False
        assert [[p["t_s"] for p in segment["points"]] for segment in record["segments"]] == [
            [0.1, 0.3], [0.6, 0.7], [1.5], [1.9]]
        assert record["reason_codes"] == ["ASSOCIATION_GAP", "INVALID_OR_OUTSIDE_TANK_POINT", "MISSING_TRACK_ID", "NO_DETECTION"]
        assert actual["reported_physical_trial_count"] == 1
        assert scene["results"]["by_origin"] == detail["evaluation"]["by_origin"]
        encoded = json.dumps(scene)
        assert "do-not-export" not in encoded and "/private" not in encoded
        assert "pixel_x" not in encoded and "evidence_frame_ids" not in encoded


def test_gap_only_recording_is_retained_without_claiming_a_visible_track(app):
    with TestClient(app) as client:
        detail = seed(client, app, "MEASURED_TANK")
        detail, _ = recorded_fixture(app.state.runtime, detail, gap_only=True)
        scene = client.get(url(detail), headers=AUTH).json()
        assert scene["actual"]["status"] == "REPORTED_COUNTS_ONLY"
        assert scene["actual"]["recordings"][0]["segments"] == []
        assert len(scene["actual"]["recordings"][0]["gaps"]) == 9


@pytest.mark.parametrize("change", [
    "two-second-receipts", "utc-origin-drift", "monotonic-origin-drift",
    "duplicate-sequence", "backward-sequence", "backward-mono", "duplicate-mono",
    "backward-utc", "missing-sequence", "missing-mono", "nonfinite-mono", "boolean-sequence",
])
def test_actual_tracks_require_one_consistent_recording_clock(app, change):
    with TestClient(app) as client:
        detail = seed(client, app, "MEASURED_TANK")
        detail, recording = recorded_fixture(app.state.runtime, detail)
        runtime = app.state.runtime
        frames = [runtime.store.get("frame", fid) for fid in recording["evidence_frame_ids"]]
        first, second = frames[:2]
        first_utc = datetime.fromisoformat(first["received_utc"]).timestamp()
        if change == "two-second-receipts":
            # A .2s token displacement cannot be replayed as though two seconds
            # of frame receipts were a continuous .2s capture interval.
            second["received_mono_s"] = first["received_mono_s"] + 2
            second["received_utc"] = datetime.fromtimestamp(first_utc + 2, UTC).isoformat()
        elif change == "utc-origin-drift":
            second["received_utc"] = datetime.fromtimestamp(first_utc + 0.21, UTC).isoformat()
        elif change == "monotonic-origin-drift":
            second["received_mono_s"] += 0.0001
        elif change == "duplicate-sequence":
            second["sequence"] = first["sequence"]
        elif change == "backward-sequence":
            first["sequence"], second["sequence"] = 5, 4
        elif change == "backward-mono":
            second["received_mono_s"] = first["received_mono_s"] - 0.1
        elif change == "duplicate-mono":
            second["received_mono_s"] = first["received_mono_s"]
        elif change == "backward-utc":
            second["received_utc"] = datetime.fromtimestamp(first_utc - 0.1, UTC).isoformat()
        elif change == "missing-sequence":
            del second["sequence"]
        elif change == "missing-mono":
            del second["received_mono_s"]
        elif change == "nonfinite-mono":
            # SQLite's stored JSON rejects NaN; nonnumeric legacy metadata is
            # also a nonfinite/non-measured monotonic clock and fails closed.
            second["received_mono_s"] = "NaN"
        else:
            second["sequence"] = True
        for frame in (first, second):
            replace(runtime, "frame", frame)
        response = client.get(url(detail), headers=AUTH)
        assert response.status_code == 409, response.text
        assert "Scene recording" in response.json()["detail"]


def test_clock_admission_tolerances_accept_only_small_read_pair_jitter_without_resampling(app):
    from apps.api.reeftrace_api.services.tank_scene import (
        MONOTONIC_ORIGIN_TOLERANCE_S,
        UTC_ORIGIN_TOLERANCE_S,
    )

    assert MONOTONIC_ORIGIN_TOLERANCE_S == 1e-6 and UTC_ORIGIN_TOLERANCE_S == 1e-3
    with TestClient(app) as client:
        detail = seed(client, app, "MEASURED_TANK")
        detail, recording = recorded_fixture(app.state.runtime, detail)
        runtime = app.state.runtime
        frame = runtime.store.get("frame", recording["evidence_frame_ids"][1])
        frame["received_mono_s"] += 0.25e-6
        receipt = datetime.fromisoformat(frame["received_utc"]).timestamp() + 0.0005
        frame["received_utc"] = datetime.fromtimestamp(receipt, UTC).isoformat()
        replace(runtime, "frame", frame)
        response = client.get(url(detail), headers=AUTH)
        assert response.status_code == 200, response.text
        points = response.json()["actual"]["recordings"][0]["segments"][0]["points"]
        assert [point["t_s"] for point in points] == [0.1, 0.3]
        assert response.json()["actual"]["positional_error_metrics"] is None


def test_operator_counts_without_recording_remain_counts_only(app):
    with TestClient(app) as client:
        detail = seed(client, app, "MEASURED_TANK")
        detail = app.state.runtime.prevention.add_trial(detail["comparison"]["id"], trial(
            data_origin="OPERATOR_REPORTED_PHYSICAL", physical_confirmed=True))
        scene = client.get(url(detail), headers=AUTH).json()
        assert scene["actual"]["status"] == "REPORTED_COUNTS_ONLY"
        assert scene["actual"]["recordings"] == []
        assert scene["actual"]["reported_physical_trial_count"] == 1
        assert scene["results"]["by_origin"] == detail["evaluation"]["by_origin"]


def test_recording_budget_is_checked_before_expensive_frame_provenance_reads(app, monkeypatch):
    with TestClient(app) as client:
        detail = seed(client, app, "MEASURED_TANK")
        detail, recording = recorded_fixture(app.state.runtime, detail)
        recording["points"] = [copy.deepcopy(recording["points"][0])] * 2001
        replace(app.state.runtime, "recording", recording)

        def forbidden(*args):
            raise AssertionError("Oversized recording must be rejected before frame reads")

        monkeypatch.setattr(app.state.runtime.prevention, "_validate_recording", forbidden)
        response = client.get(url(detail), headers=AUTH)
        assert response.status_code == 409 and "budget" in response.text


def test_payload_budget_and_legacy_absent_representatives_are_explicit(app, monkeypatch):
    import apps.api.reeftrace_api.services.tank_scene as service

    with TestClient(app) as client:
        detail = seed(client, app)
        comparison = detail["comparison"]
        del comparison["numerical_report"]["nominal_paths"]
        replace(app.state.runtime, COMPARISON_KIND, comparison)
        detail = app.state.runtime.prevention.comparison_detail(comparison["id"])
        scene = client.get(url(detail)).json()
        assert scene["simulation"]["paths"] == []
        assert scene["results"]["rows"][0]["baseline"]["particles"] == 20
        monkeypatch.setattr(service, "MAX_SCENE_BYTES", 1)
        response = client.get(url(detail))
        assert response.status_code == 409 and "byte budget" in response.text


@pytest.mark.parametrize("change", ["profile", "calibration", "session", "frame-session", "frame-profile", "predates", "clock"])
def test_wrong_recording_binding_never_exports_as_actual(app, change):
    with TestClient(app) as client:
        detail = seed(client, app, "MEASURED_TANK")
        detail, record = recorded_fixture(app.state.runtime, detail)
        kind = "recording"
        if change == "profile":
            record["profile_id"] = detail["comparison"]["intervention_profile_id"]
        elif change == "calibration":
            record["calibration_id"] = "another-map"
        elif change == "session":
            record["camera_session_id"] = "another-camera"
        elif change.startswith("frame-"):
            kind = "frame"
            record = app.state.runtime.store.get(kind, record["evidence_frame_ids"][0])
            record["camera_session_id" if change == "frame-session" else "profile_id"] = "wrong"
        elif change == "predates":
            record["recorded_at"] = detail["comparison"]["created_at"] - 1
        else:
            record["timestamp_kind"] = "unverified_exposure_clock"
        replace(app.state.runtime, kind, record)
        response = client.get(url(detail), headers=AUTH)
        assert response.status_code == 409, response.text
        assert "recordings" not in response.json()


def test_hash_required_mismatch_and_missing_comparison_fail_closed(app):
    with TestClient(app) as client:
        detail = seed(client, app)
        path = ROOT + "/" + detail["comparison"]["id"] + "/scene"
        assert client.get(path).status_code == 422
        assert client.get(path + "?evaluation_snapshot_hash=not-a-hash").status_code == 422
        assert client.get(path + "?evaluation_snapshot_hash=" + "0" * 64).status_code == 409
        assert client.get(ROOT + "/missing/scene?evaluation_snapshot_hash=" + "0" * 64).status_code == 404


def test_stale_trial_hash_rejected_but_updated_hash_keeps_all_missing_denominators(app):
    with TestClient(app) as client:
        old = seed(client, app)
        new = app.state.runtime.prevention.add_trial(old["comparison"]["id"], trial())
        assert client.get(url(old)).status_code == 409
        scene = client.get(url(new)).json()
        assert scene["results"]["by_origin"] == new["evaluation"]["by_origin"]
        assert scene["results"]["by_origin"]["SYNTHETIC_DEMO"]["layouts"]["baseline"]["missing_planned"] == 3


def test_archived_comparison_remains_explicitly_archival(app):
    with TestClient(app) as client:
        detail = seed(client, app)
        app.state.runtime.store.stop_case(detail["comparison"]["case_id"])
        scene = client.get(url(detail)).json()
        assert scene["is_current"] is False and scene["archive_reason"] == "CASE_CHANGED_OR_STOPPED"


@pytest.mark.parametrize("mutation", ["new-trial", "stop", "profile", "late-trial", "late-stop"])
def test_concurrent_evidence_change_is_not_returned_as_a_fresh_scene(app, monkeypatch, mutation):
    with TestClient(app) as client:
        detail = seed(client, app)
        runtime = app.state.runtime
        original = runtime.prevention.comparison_detail
        called = False

        def changed(identity, **kwargs):
            nonlocal called
            if not called:
                called = True
                latest = original(identity, **kwargs)
                if mutation == "new-trial":
                    runtime.prevention.add_trial(identity, trial())
                elif mutation == "stop":
                    runtime.store.stop_case(detail["comparison"]["case_id"])
                elif mutation == "profile":
                    profile = runtime.store.get("profile", detail["comparison"]["baseline_profile_id"])
                    profile["token_class"] = "mutated"
                    replace(runtime, "profile", profile)
                elif mutation == "late-trial":
                    runtime.prevention.add_trial(identity, trial())
                    return latest
                else:
                    runtime.store.stop_case(detail["comparison"]["case_id"])
                    return latest
            return original(identity, **kwargs)

        monkeypatch.setattr(runtime.prevention, "comparison_detail", changed)
        response = client.get(url(detail))
        assert response.status_code == 409, response.text


@pytest.mark.parametrize("corruption", ["profile-hash", "source-origin", "particle-denominator", "duplicated-group", "time-order"])
def test_mutated_frozen_scientific_contracts_are_rejected(app, corruption):
    with TestClient(app) as client:
        detail = seed(client, app)
        runtime, comparison = app.state.runtime, detail["comparison"]
        if corruption == "source-origin":
            source = runtime.store.get("estimate", comparison["source_evidence_id"])
            source["data_origin"] = "MEASURED_TANK"
            replace(runtime, "estimate", source)
        else:
            report = comparison["numerical_report"]
            if corruption == "profile-hash":
                report["layouts"]["baseline"]["profile_hash"] = "0" * 64
            elif corruption == "particle-denominator":
                report["results"][0]["baseline"]["particles"] = 1
            elif corruption == "duplicated-group":
                report["nominal_paths"].append(copy.deepcopy(report["nominal_paths"][0]))
            else:
                points = report["nominal_paths"][0]["paths"][0]["points"]
                points[1]["t_s"] = points[0]["t_s"]
            replace(runtime, COMPARISON_KIND, comparison)
            detail = runtime.prevention.comparison_detail(comparison["id"])
        with pytest.raises(ValueError):
            build_tank_scene(runtime, comparison["id"], detail["evaluation"]["snapshot_hash"])
