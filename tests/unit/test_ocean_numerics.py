"""Separate solver sensitivity from contact-chord sensitivity, without providers."""

from __future__ import annotations

import copy
from datetime import datetime, timedelta

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import ocean_numerics as numerics
from apps.ocean.reeftrace_ocean import ocean_prevention as ocean
from apps.ocean.reeftrace_ocean.field import OceanField


def scenario(horizon=600.0):
    result = ocean.frozen_scenario()
    result["horizon_s"] = horizon
    for release in result["releases"]:
        release["horizon_s"] = horizon
    return result


def field(end_s=600, masked=False):
    shape = (2, 2, 2)
    valid = np.ones(shape, bool)
    if masked:
        valid[:, 0, 0] = False
    return OceanField(
        np.array([np.datetime64("2026-10-17T18:00:00"),
                  np.datetime64("2026-10-17T18:00:00") + np.timedelta64(end_s, "s")]),
        np.array([-158.5, -157.5]), np.array([20.5, 21.5]),
        np.where(valid, np.full(shape, -0.25), np.nan),
        np.where(valid, np.zeros(shape), np.nan), valid, 0.25,
        {"velocity_units": "m/s", "license": "SYNTHETIC_ANALYTIC_TEST"},
    )


def point(x, y, elapsed, frame):
    return {"elapsed_s": float(elapsed), **ocean._geo(x, y, frame),
            "time_utc": (datetime.fromisoformat(ocean.START_UTC)
                         + timedelta(seconds=elapsed)).isoformat().replace("+00:00", "Z"),
            "eastward_m_s": 1.0, "northward_m_s": 0.0, "speed_m_s": 1.0}


def path(points, frame, *, status="COMPLETED", horizon=600, reason=None):
    return {"status": status, "reason_code": reason, "requested_horizon_s": horizon,
            "completed_horizon_s": points[-1][2] if points else 0.0,
            "track": [point(*item, frame) for item in points]}


def test_constant_flow_common_time_check_is_numerical_separation_not_truth():
    result = numerics.run_numerical_sensitivity(field(), scenario())
    assert result["release_count"] == 6
    assert result["diagnostic_advection_runs_per_release"] == 4
    assert result["physical_validation"] is result["independent_truth_used"] is False
    assert result["model_parameters_tuned"] is False
    assert result["summary"]["all_integrations_completed"] is True
    assert result["summary"]["integration_max_separation_m"] < 1e-6
    assert "no physical accuracy or ML skill" in result["summary"]["meaning"]
    for level in result["integration"]["levels"]:
        assert level["output_step_s"] == 300
        assert level["comparable_release_count"] == 6
        assert level["forcing_status_counts"] == {"COMPLETED": 6, "PARTIAL": 0, "UNSUPPORTED": 0}
        for row in level["releases"]:
            comparison = row["comparison"]
            assert comparison["common_positive_time_count"] == 2  # t=0 is excluded
            assert comparison["last_common_elapsed_s"] == 600
            assert comparison["both_completed"] is True
    assert result["events"]["same_fine_tracks_downsampled"] is True
    assert result["events"]["terminal_accepted_partial_point_retained"] is True


def test_missing_start_does_not_become_zero_difference_or_an_omitted_release():
    result = numerics.run_numerical_sensitivity(field(masked=True), scenario())
    assert result["summary"]["all_integrations_completed"] is False
    assert result["summary"]["integration_max_separation_m"] is None
    for level in result["integration"]["levels"]:
        assert level["release_count"] == 6
        assert level["comparable_release_count"] == 0
        assert level["max_separation_m"] is None
        assert level["forcing_status_counts"]["UNSUPPORTED"] == 6
        for row in level["releases"]:
            assert row["forcing_reason_code"] == "MASKED_CURRENT_CELL"
            assert row["comparison"]["status"] == "NO_COMMON_POSITIVE_TIME"
            assert row["comparison"]["common_positive_time_count"] == 0
            assert row["comparison"]["max_separation_m"] is None
    for level in result["events"]["levels"]:
        assert level["recommendation"]["status"] == "INDETERMINATE"
        assert level["comparison_to_finest"]["unresolved_comparison_count"] == 18
        assert level["comparison_to_finest"]["max_matched_event_time_difference_s"] is None
        for row in [level["baseline"], *level["layouts"]]:
            assert row["summary"]["release_count"] == row["summary"]["unresolved_count"] == 6
            assert row["summary"]["protected_entry_count_bounds"] == [0, 6]
            assert all(outcome["event_time_difference_s"] is None for outcome in row["outcomes"])


def test_terminal_partial_coverage_and_comparison_are_explicit():
    result = numerics.run_numerical_sensitivity(field(end_s=425), scenario())
    assert result["summary"]["all_integrations_completed"] is False
    for level in result["integration"]["levels"]:
        assert level["forcing_status_counts"]["PARTIAL"] == 6
        for row in level["releases"]:
            assert row["completed_horizon_s"] == 425
            assert row["requested_horizon_s"] == 600
            assert row["forcing_reason_code"] == "OUTSIDE_FORCING_TIME"
            assert row["comparison"]["last_common_elapsed_s"] == 425
            assert row["comparison"]["common_positive_time_count"] == 2
            assert row["comparison"]["both_completed"] is False
    for level in result["events"]["levels"]:
        for row in [level["baseline"], *level["layouts"]]:
            assert all(outcome["track_end_elapsed_s"] == 425 for outcome in row["outcomes"])
            assert row["summary"]["unresolved_count"] == 6


def test_solver_and_chord_experiments_are_separate_and_keep_actual_partial_endpoint(monkeypatch):
    experiment = scenario()
    frame = experiment["frame"]
    experiment["protected_zone"]["polygon_xy_m"] = [[1000, -1000], [1200, -1000],
                                                     [1200, 1000], [1000, 1000]]
    experiment["layouts"][0]["segments"] = [{
        "id": "high-contact", "start_xy_m": [75, 90], "end_xy_m": [75, 110]}]
    experiment["layouts"][1]["segments"] = [{
        "id": "low-contact", "start_xy_m": [250, -80], "end_xy_m": [250, -50]}]
    integration = path([(0, 0, 0), (300, 0, 300), (425, 0, 425)], frame,
                       status="PARTIAL", reason="OUTSIDE_FORCING_TIME")
    fine = path([(0, 0, 0), (75, 100, 75), (150, 0, 150), (225, -100, 225),
                 (300, 0, 300), (375, 100, 375), (425, 100, 425)], frame,
                status="PARTIAL", reason="OUTSIDE_FORCING_TIME")
    calls = []

    def analytic_fixture(source, **kwargs):
        calls.append((kwargs["step_s"], kwargs["output_step_s"]))
        return copy.deepcopy(fine if kwargs["output_step_s"] == 75 else integration)

    monkeypatch.setattr(numerics, "advect_current", analytic_fixture)
    result = numerics.run_numerical_sensitivity(object(), experiment)
    assert calls == ([(300, 300)] * 6 + [(150, 300)] * 6
                     + [(75, 300)] * 6 + [(75, 75)] * 6)
    coarse, medium, finest = result["events"]["levels"]
    assert coarse["layouts"][0]["summary"]["intercepted_count"] == 0
    assert medium["layouts"][0]["summary"]["intercepted_count"] == 0
    assert finest["layouts"][0]["summary"]["intercepted_count"] == 6
    assert coarse["layouts"][0]["outcomes"][0]["comparison_status"] == "UNRESOLVED"
    assert finest["layouts"][0]["outcomes"][0]["event_kind"] == "IDEALIZED_CAPTURE"
    assert finest["layouts"][0]["outcomes"][0]["segment_id"] == "high-contact"
    assert finest["layouts"][0]["outcomes"][0]["event_elapsed_s"] == pytest.approx(75, abs=1e-6)
    # An earlier event is resolved under the ideal model, but all integrations
    # still declare partial forcing; no successful full-horizon check is claimed.
    assert result["summary"]["all_integrations_completed"] is False
    assert finest["layouts"][0]["outcomes"][0]["forcing_status"] == "PARTIAL"
    assert all(row["track_end_elapsed_s"] == 425 for row in coarse["baseline"]["outcomes"])
    assert fine["track"][-1]["elapsed_s"] == 425


def test_event_time_difference_needs_matching_resolved_event_kind_and_segment_identity():
    base = {"release_id": "r", "status": "IDEALIZED_INTERCEPTION",
            "event": {"kind": "IDEALIZED_CAPTURE", "segment_id": "north", "elapsed_s": 100},
            "forcing_status": "PARTIAL", "forcing_reason_code": "OUTSIDE_FORCING_TIME",
            "requested_horizon_s": 600, "integrated_horizon_s": 300, "track_end_elapsed_s": 100}
    later = copy.deepcopy(base)
    later["event"]["elapsed_s"] = 103
    assert numerics._compact_outcome(later, base)["event_time_difference_s"] == 3
    later["event"]["segment_id"] = "south"
    different = numerics._compact_outcome(later, base)
    assert different["comparison_status"] == "CHANGED_OUTCOME"
    assert different["event_time_difference_s"] is None
    later["event"] = None
    later["status"] = "UNRESOLVED"
    assert numerics._compact_outcome(later, base)["comparison_status"] == "UNRESOLVED"
    assert numerics._compact_outcome(later, base)["event_time_difference_s"] is None


def test_separation_does_not_interpolate_partial_times_or_use_t0_as_comparison_coverage():
    frame = scenario()["frame"]
    left = path([(0, 0, 0), (100, 0, 100)], frame, status="PARTIAL")
    right = path([(0, 0, 0), (200, 0, 200)], frame, status="PARTIAL")
    result = numerics._separation(left, right, frame)
    assert result["status"] == "NO_COMMON_POSITIVE_TIME"
    assert result["common_positive_time_count"] == 0
    assert result["last_common_elapsed_s"] is None
    assert result["max_separation_m"] is None


def test_same_path_downsampling_never_invents_points_and_retains_terminal_partial():
    frame = scenario()["frame"]
    source = path([(0, 0, 0), (75, 1, 75), (150, 2, 150), (225, 1, 225),
                   (300, 0, 300), (317, -1, 317)], frame, status="PARTIAL")
    saved = copy.deepcopy(source)
    sampled = numerics._downsample(source, 300)
    assert [row["elapsed_s"] for row in sampled["track"]] == [0, 300, 317]
    assert all(row in source["track"] for row in sampled["track"])
    assert sampled["status"] == "PARTIAL"
    assert source == saved
