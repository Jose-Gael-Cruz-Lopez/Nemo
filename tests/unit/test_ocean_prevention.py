"""First-passage and fair-counterfactual ocean prevention, without providers."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta

import httpx
import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import ocean_prevention as ocean
from apps.ocean.reeftrace_ocean.current_forecast import load_current_snapshot
from apps.ocean.reeftrace_ocean.field import OceanField, _wgs84_metres_per_degree

FRAME = ocean.frozen_scenario()["frame"]
SQUARE = [[100.0, -50.0], [200.0, -50.0], [200.0, 50.0], [100.0, 50.0]]


def point(x, y, elapsed):
    return {"elapsed_s": float(elapsed), "time_utc": (
        datetime.fromisoformat(ocean.START_UTC) + timedelta(seconds=elapsed)
    ).isoformat().replace("+00:00", "Z"), **ocean._geo(x, y, FRAME),
        "eastward_m_s": 1.0, "northward_m_s": 0.0, "speed_m_s": 1.0}


def path(points, *, status="COMPLETED", reason=None, horizon=300.0):
    return {"track": [point(*item) for item in points], "status": status,
            "reason_code": reason, "requested_horizon_s": horizon,
            "completed_horizon_s": points[-1][2] if points else 0.0}


def release(x=0.0, y=0.0):
    return {"id": "analytic-release", **ocean._geo(x, y, FRAME),
            "start_time_utc": ocean.START_UTC, "horizon_s": 300.0}


def barrier(x, y0=-100.0, y1=100.0, identity="line"):
    return {"id": identity, "start_xy_m": [float(x), float(y0)],
            "end_xy_m": [float(x), float(y1)]}


def evaluate(points, segments=None, **kwargs):
    return ocean.evaluate_path(path(points, **kwargs), release(),
                               segments or [], SQUARE, FRAME)


@pytest.mark.parametrize("a,b,c,d,expected", [
    ([0, 0], [300, 0], [100, -1], [100, 1], 1 / 3),
    ([300, 0], [0, 0], [100, -1], [100, 1], 2 / 3),
    ([0, 0], [300, 0], [100, 0], [200, 0], 1 / 3),
    ([0, 0], [300, 0], [200, 0], [100, 0], 1 / 3),
    ([0, 0], [300, 0], [-100, 0], [50, 0], 0),
    ([0, 0], [300, 0], [300, 0], [400, 0], 1),
    ([0, 0], [300, 0], [100, 1], [200, 1], None),
    ([0, 0], [300, 0], [301, -1], [301, 1], None),
    ([0, 0], [0, 0], [0, -1], [0, 1], 0),
    ([0, 0], [0, 0], [1, -1], [1, 1], None),
    ([0, 0], [300, 0], [100, 0], [100, 0], 1 / 3),
])
def test_closed_segment_first_contact_including_overlap_and_degenerate_cases(a, b, c, d, expected):
    actual = ocean._segment_crossing_fraction(a, b, c, d)
    assert actual == (None if expected is None else pytest.approx(expected, abs=1e-12))


def test_zone_crossing_detected_when_both_chord_endpoints_are_outside():
    result = evaluate([(0, 0, 0), (300, 0, 300)])
    assert result["status"] == "ENTERED_PROTECTED_ZONE"
    assert result["event"]["elapsed_s"] == pytest.approx(100, abs=1e-6)
    assert result["event"]["x_m"] == pytest.approx(100, abs=1e-6)
    assert result["event"]["y_m"] == pytest.approx(0, abs=1e-6)
    assert result["event"]["time_utc"] == "2026-10-17T18:01:40Z"
    assert len(result["track"]) == 2
    assert result["track"][-1]["elapsed_s"] == pytest.approx(100, abs=1e-6)
    assert result["integrated_horizon_s"] == 300


def test_first_barrier_contact_truncates_path_before_later_reef_entry():
    original = path([(0, 0, 0), (300, 0, 300)])
    saved = copy.deepcopy(original)
    result = ocean.evaluate_path(original, release(), [barrier(50)], SQUARE, FRAME)
    assert result["status"] == "IDEALIZED_INTERCEPTION"
    assert result["event"]["elapsed_s"] == pytest.approx(50, abs=1e-6)
    assert result["event"]["segment_id"] == "line"
    assert result["track"][-1]["x_m"] == pytest.approx(50, abs=1e-6)
    assert original == saved


def test_capture_after_entry_does_not_rewrite_an_exposed_particle_as_protected():
    result = evaluate([(0, 0, 0), (300, 0, 300)], [barrier(150)])
    assert result["status"] == "ENTERED_PROTECTED_ZONE"
    assert result["event"]["segment_id"] is None
    assert result["event"]["elapsed_s"] == pytest.approx(100, abs=1e-6)


@pytest.mark.parametrize("offset", [0.0, -0.0000005, 0.0000005])
def test_entry_wins_capture_at_simultaneous_boundary_with_conservative_tolerance(offset):
    result = evaluate([(0, 0, 0), (300, 0, 300)], [barrier(100 + offset)])
    assert result["status"] == "ENTERED_PROTECTED_ZONE"
    assert result["event"]["kind"] == "PROTECTED_ZONE_ENTRY"


def test_capture_significantly_before_entry_remains_capture():
    assert evaluate([(0, 0, 0), (300, 0, 300)], [barrier(99.99)])["status"] == (
        "IDEALIZED_INTERCEPTION"
    )


def test_multiple_crossings_use_first_event_independent_of_segment_order():
    points = [(0, 0, 0), (300, 0, 300), (0, 0, 600)]
    early, late = barrier(25, identity="early"), barrier(75, identity="late")
    a = evaluate(points, [late, early], horizon=600)
    b = evaluate(points, [early, late], horizon=600)
    assert a == b
    assert a["event"]["segment_id"] == "early"
    assert a["event"]["elapsed_s"] == pytest.approx(25, abs=1e-6)


@pytest.mark.parametrize("status,expected", [
    ("COMPLETED", "NO_ENTRY_WITHIN_HORIZON"), ("PARTIAL", "UNRESOLVED"),
    ("UNSUPPORTED", "UNRESOLVED"),
])
def test_no_contact_keeps_forcing_uncertainty_explicit(status, expected):
    points = [(0, 100, 0), (50, 100, 50)] if status != "UNSUPPORTED" else []
    result = evaluate(points, status=status, reason="MASKED_CURRENT_CELL")
    assert result["status"] == expected
    assert result["event"] is None
    assert result["forcing_status"] == status
    assert result["forcing_reason_code"] == "MASKED_CURRENT_CELL"
    if status == "UNSUPPORTED":
        assert result["track"] == []


def test_an_event_before_a_later_forcing_stop_is_still_known_under_the_ideal_model():
    result = evaluate([(0, 0, 0), (150, 0, 150)], [barrier(50)],
                      status="PARTIAL", reason="OUTSIDE_FORCING_TIME")
    assert result["status"] == "IDEALIZED_INTERCEPTION"
    assert result["forcing_status"] == "PARTIAL"
    assert result["event"]["elapsed_s"] == pytest.approx(50, abs=1e-6)


@pytest.mark.parametrize("unsupported", [False, True])
def test_release_already_inside_zone_is_immediate_entry_even_without_velocity(unsupported):
    source = path([] if unsupported else [(150, 0, 0), (300, 0, 300)],
                  status="UNSUPPORTED" if unsupported else "COMPLETED")
    result = ocean.evaluate_path(source, release(150, 0), [barrier(150)], SQUARE, FRAME)
    assert result["status"] == "ENTERED_PROTECTED_ZONE"
    assert result["event"]["elapsed_s"] == 0
    assert len(result["track"]) == 1
    if unsupported:
        assert result["track"][0]["eastward_m_s"] is None
        assert result["track"][0]["speed_m_s"] is None


def test_release_on_barrier_is_immediate_ideal_contact_without_forcing():
    result = ocean.evaluate_path(path([], status="UNSUPPORTED"), release(0, 0),
                                [barrier(0)], SQUARE, FRAME)
    assert result["status"] == "IDEALIZED_INTERCEPTION"
    assert result["event"]["elapsed_s"] == 0
    assert result["track"][0]["eastward_m_s"] is None


def test_zone_boundary_touch_is_conservative_entry_even_for_grazing_chord():
    result = evaluate([(0, 50, 0), (300, 50, 300)])
    assert result["status"] == "ENTERED_PROTECTED_ZONE"
    assert result["event"]["elapsed_s"] == pytest.approx(100, abs=1e-6)


def test_all_releases_remain_in_entry_bounds_not_just_supported_ones():
    summary = ocean.summarize_outcomes([
        {"status": "ENTERED_PROTECTED_ZONE"}, {"status": "IDEALIZED_INTERCEPTION"},
        {"status": "NO_ENTRY_WITHIN_HORIZON"}, {"status": "UNRESOLVED"},
        {"status": "UNRESOLVED"}, {"status": "UNRESOLVED"},
    ])
    assert summary["release_count"] == 6
    assert summary["protected_entry_count_bounds"] == [1, 4]
    assert summary["protected_entry_fraction_bounds"] == [1 / 6, 4 / 6]
    with pytest.raises(ValueError, match="Every release"):
        ocean.summarize_outcomes([])
    with pytest.raises(ValueError, match="Every release"):
        ocean.summarize_outcomes([{"status": "UNRECOGNIZED"}])


@pytest.mark.parametrize("left,right,status,best", [
    ([0, 1], [2, 3], "BEST_LAYOUT", "a"), ([3, 4], [0, 2], "BEST_LAYOUT", "b"),
    ([0, 2], [2, 4], "INDETERMINATE", None),
    ([0, 6], [0, 6], "INDETERMINATE", None),
    ([1, 1], [1, 1], "TIE", None), ([0, 0], [0, 0], "TIE", None),
])
def test_only_strict_nonoverlap_supports_best_layout(left, right, status, best):
    layouts = [{"id": identity, "label": identity,
                "summary": {"protected_entry_count_bounds": bounds}}
               for identity, bounds in (("a", left), ("b", right))]
    result = ocean.recommend_layout(layouts)
    assert result["status"] == status
    assert result["best_layout_id"] == best
    assert ocean.recommend_layout(layouts[::-1]) == result


def test_scenario_has_frozen_pre_outcome_geometry_and_equal_resources():
    scenario = ocean.frozen_scenario("initial-proxy-v1")
    assert scenario["design_status"] == "INITIAL_GEOMETRY_NEGATIVE_CONTROL"
    assert scenario["protected_zone"]["is_mapped_real_reef"] is False
    assert len(scenario["releases"]) == 6
    assert len({(r["x_m"], r["y_m"]) for r in scenario["releases"]}) == 6
    assert all(r["start_time_utc"] == ocean.START_UTC and r["horizon_s"] == 21600
               for r in scenario["releases"])
    for layout in scenario["layouts"]:
        length = sum(math_hypot_segment(segment) for segment in layout["segments"])
        assert length == layout["total_length_m"] == 2000
    assert scenario["event_model"]["event_chord_output_step_s"] == 300
    scenario["protected_zone"]["polygon_xy_m"][0][0] = 999
    assert ocean.frozen_scenario("initial-proxy-v1")["protected_zone"]["polygon_xy_m"][0][0] == -5000


def math_hypot_segment(segment):
    return float(np.linalg.norm(np.asarray(segment["end_xy_m"]) - segment["start_xy_m"]))


@pytest.fixture(scope="module")
def real_report():
    return ocean.run_ocean_prevention("initial-proxy-v1")


def test_real_report_uses_only_dynamic_paths_and_retains_honest_null_validation(real_report):
    report = real_report
    assert report["kind"] == "OCEAN_PREVENTION_COMPARISON"
    assert report["status"] == "COMPLETED"
    assert report["method"]["trajectory"] == "dynamic_current_advection_only"
    assert report["method"]["output_step_s"] == report["method"]["step_s"] == 300
    assert report["method"]["barriers_modify_flow"] is False
    assert report["validation"]["physical_validation"] is False
    assert report["validation"]["interception_benefit_established"] is False
    assert report["validation"]["measured_entry_count"] is None
    assert report["validation"]["measured_intercepted_count"] is None
    assert report["forcing"]["nominal_grid_spacing_m"] == 4000
    assert report["forcing"]["time_step_s"] == 10800
    assert report["forcing"]["model_issue_time_utc"] is None
    assert report["baseline"]["summary"]["release_count"] == 6
    assert report["recommendation"]["status"] == "TIE"
    assert report["recommendation"]["best_layout_id"] is None
    # This predeclared hypothesis has no baseline entry in six hours. Greater
    # idealized capture count must never be presented as proven reef protection.
    assert report["baseline"]["summary"]["entered_count"] == 0
    assert [layout["summary"]["intercepted_count"] for layout in report["layouts"]] == [4, 2]
    assert all(layout["summary"]["entry_reduction_count_bounds_vs_baseline"] == [0, 0]
               for layout in report["layouts"])
    json.dumps(report, allow_nan=False)


def test_report_identity_binds_exact_inputs_method_scenario_and_full_results(real_report):
    report = copy.deepcopy(real_report)
    identity = report.pop("report_sha256")
    assert ocean._sha256(report) == identity
    assert ocean._sha256(report["scenario"]) == report["scenario_sha256"]
    assert ocean._method_sha256() == report["method_sha256"]
    field, manifest = load_current_snapshot()
    assert report["snapshot_sha256"] == field.metadata["sha256"] == manifest["files"]["csv"]["sha256"]
    assert all(len(report[key]) == 64 for key in (
        "snapshot_sha256", "method_sha256", "scenario_sha256", "manifest_sha256",
    ))
    report["layouts"][0]["summary"]["entered_count"] += 1
    assert ocean._sha256(report) != identity
    assert len(json.dumps(real_report)) < 500_000


def test_identical_paths_are_integrated_once_per_release_and_never_mutate_the_field(monkeypatch):
    field, manifest = load_current_snapshot()
    before = [item.copy() for item in (field.eastward_m_s, field.northward_m_s, field.valid_mask)]
    metadata = copy.deepcopy(field.metadata)
    calls, real = [], ocean.advect_current

    def observed(source, **kwargs):
        assert source is field
        calls.append(kwargs)
        return real(source, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("The comparison must not request network data or providers")

    monkeypatch.setattr(ocean, "load_current_snapshot", lambda: (field, manifest))
    monkeypatch.setattr(ocean, "advect_current", observed)
    monkeypatch.setattr(httpx.Client, "send", forbidden)
    report = ocean.run_ocean_prevention()
    assert len(calls) == 6
    assert all(call["step_s"] == call["output_step_s"] == 300 for call in calls)
    for original, current in zip(before, (field.eastward_m_s, field.northward_m_s, field.valid_mask), strict=True):
        np.testing.assert_array_equal(original, current)
    assert metadata == field.metadata
    baseline = {o["release_id"]: o for o in report["baseline"]["outcomes"]}
    for layout in report["layouts"]:
        for outcome in layout["outcomes"]:
            assert outcome["track"][0] == baseline[outcome["release_id"]]["track"][0]
            if outcome["event"] is None:
                assert outcome["track"] == baseline[outcome["release_id"]]["track"]


def test_display_vectors_have_fixed_all_path_domain_and_finite_shared_scale(real_report):
    assert real_report["vector_sampling"] == "interpolated_display_samples_not_finer_observations"
    assert len(real_report["vector_frames"]) == 3
    assert all(len(frame["vectors"]) <= 9 for frame in real_report["vector_frames"])
    assert real_report["vector_speed_scale_m_s"] > 0
    for frame in real_report["vector_frames"]:
        for vector in frame["vectors"]:
            for axis in ("x_m", "y_m"):
                lower, upper = real_report["display_bounds_xy_m"][axis]
                assert lower <= vector[axis] <= upper
            speed = np.hypot(vector["eastward_m_s"], vector["northward_m_s"])
            assert speed <= real_report["vector_speed_scale_m_s"]


def synthetic_field(*, end_s=21600, masked=False):
    shape = (2, 2, 2)
    mask = np.ones(shape, bool)
    if masked:
        mask[:, 0, 0] = False
    return OceanField(
        np.array([np.datetime64("2026-10-17T18:00:00"),
                  np.datetime64("2026-10-17T18:00:00") + np.timedelta64(end_s, "s")]),
        np.array([-158.5, -157.5]), np.array([20.5, 21.5]),
        np.where(mask, np.full(shape, -0.25), np.nan),
        np.where(mask, np.zeros(shape), np.nan), mask, 0.25,
        {"velocity_units": "m/s", "license": "SYNTHETIC_NUMERICAL_TEST", "sha256": "a" * 64},
    )


def test_analytic_constant_west_flow_can_resolve_a_best_layout_without_geometry_tuning(monkeypatch):
    _, manifest = load_current_snapshot()
    monkeypatch.setattr(ocean, "load_current_snapshot", lambda: (synthetic_field(), manifest))
    report = ocean.run_ocean_prevention("initial-proxy-v1")
    assert report["baseline"]["summary"]["entered_count"] == 4
    central, flanking = report["layouts"]
    assert central["summary"]["protected_entry_count_bounds"] == [0, 0]
    assert flanking["summary"]["protected_entry_count_bounds"] == [4, 4]
    assert report["recommendation"]["status"] == "BEST_LAYOUT"
    assert report["recommendation"]["best_layout_id"] == "central"
    local_metres_lon, _ = _wgs84_metres_per_degree(report["releases"][1]["latitude_deg"])
    ratio = local_metres_lon / FRAME["east_metres_per_degree"]
    assert central["outcomes"][1]["event"]["elapsed_s"] == pytest.approx(6000 * ratio, abs=1e-5)
    assert report["baseline"]["outcomes"][1]["event"]["elapsed_s"] == pytest.approx(14000 * ratio, abs=1e-5)


def test_partial_future_forcing_retains_unknowns_in_denominator_and_no_false_winner(monkeypatch):
    _, manifest = load_current_snapshot()
    monkeypatch.setattr(ocean, "load_current_snapshot", lambda: (synthetic_field(end_s=10800), manifest))
    report = ocean.run_ocean_prevention("initial-proxy-v1")
    assert report["status"] == "PARTIAL"
    assert report["baseline"]["summary"]["protected_entry_count_bounds"] == [0, 6]
    assert [layout["summary"]["release_count"] for layout in report["layouts"]] == [6, 6]
    assert [layout["summary"]["unresolved_count"] for layout in report["layouts"]] == [2, 4]
    assert report["recommendation"]["status"] == "INDETERMINATE"
    assert report["recommendation"]["best_layout_id"] is None


def test_missing_start_current_does_not_become_zero_entries_or_success(monkeypatch):
    _, manifest = load_current_snapshot()
    monkeypatch.setattr(ocean, "load_current_snapshot", lambda: (synthetic_field(masked=True), manifest))
    report = ocean.run_ocean_prevention()
    assert report["status"] == "UNSUPPORTED"
    for layout in [report["baseline"], *report["layouts"]]:
        assert layout["summary"]["release_count"] == layout["summary"]["unresolved_count"] == 6
        assert layout["summary"]["protected_entry_count_bounds"] == [0, 6]
        assert all(outcome["track"] == [] for outcome in layout["outcomes"])
    assert report["recommendation"]["status"] == "INDETERMINATE"


def test_archival_display_state_is_part_of_report_identity_but_does_not_change_scenario(monkeypatch):
    class Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 19, tzinfo=tz)

    monkeypatch.setattr(ocean, "datetime", Later)
    report = ocean.run_ocean_prevention()
    assert report["mode"] == "archived_forecast_snapshot"
    assert any("not live conditions" in line for line in report["limitations"])
    assert report["scenario_sha256"] == ocean._sha256(ocean.frozen_scenario())


def test_post_preview_what_if_has_transparent_identity_and_keeps_initial_negative_control():
    initial = ocean.frozen_scenario("initial-proxy-v1")
    downstream = ocean.frozen_scenario("downstream-corridor-v2")
    assert ocean.SUPPORTED_SCENARIOS == ("initial-proxy-v1", "downstream-corridor-v2")
    assert ocean.DEFAULT_SCENARIO_ID == "downstream-corridor-v2"
    assert initial["releases"] == downstream["releases"]
    assert initial["layouts"] == downstream["layouts"]
    assert downstream["design_status"] == "ILLUSTRATIVE_WHAT_IF_AFTER_VIEWING_PREVIEW"
    assert "not independent performance evidence" in downstream["design_disclosure"]
    assert downstream["protected_zone"]["polygon_xy_m"] == [
        [-6000.0, -5000.0], [-3500.0, -5000.0], [-3500.0, 500.0], [-6000.0, 500.0],
    ]
    assert ocean._sha256(initial) == "a584d8f73d69cbcbfd3ef930800d4d0ef5d9f6cdb5d8e4f1723b46b629c1ef7b"
    assert ocean._sha256(downstream) == "0af5cfad8bf8c1f521af7c65fb3f51225793b758d8084c36b9782fab83e1db79"
    assert ocean._sha256(initial) != ocean._sha256(downstream)
    with pytest.raises(ValueError, match="supported frozen"):
        ocean.run_ocean_prevention("not-a-real-preset")


def test_default_real_what_if_compares_risk_without_equating_capture_to_measured_protection():
    report = ocean.run_ocean_prevention()
    assert report["scenario"]["id"] == "downstream-corridor-v2"
    assert report["scenario"]["design_status"] == "ILLUSTRATIVE_WHAT_IF_AFTER_VIEWING_PREVIEW"
    assert [item["id"] for item in report["available_scenarios"]] == list(ocean.SUPPORTED_SCENARIOS)
    assert report["baseline"]["summary"]["protected_entry_count_bounds"] == [6, 6]
    assert [layout["summary"]["protected_entry_count_bounds"] for layout in report["layouts"]] == [
        [2, 2], [4, 4],
    ]
    assert report["recommendation"]["best_layout_id"] == "central"
    assert report["validation"]["interception_benefit_established"] is False
    assert report["validation"]["real_reef_boundary_used"] is False
    assert any("not independent performance evidence" in line for line in report["limitations"])
