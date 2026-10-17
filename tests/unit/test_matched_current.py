"""Synthetic math, failure accounting and reserved-position isolation contracts."""

import copy
import json
import math
from datetime import timedelta

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import matched_current as matched
from apps.ocean.reeftrace_ocean.benchmark import EARTH_MEAN_RADIUS_M, great_circle_distance_m
from apps.ocean.reeftrace_ocean.field import OceanField, _wgs84_metres_per_degree

ORIGIN_LONGITUDE = -79.9


def context(group_id, *, delta_s=3600, penultimate_east_m=-1800):
    rows = [{
        "drifter_id": group_id,
        "time_utc": (matched.ORIGIN - timedelta(hours=24 - index)).isoformat(),
        "latitude_deg": "0", "longitude_deg": str(ORIGIN_LONGITUDE),
    } for index in range(25)]
    rows[-2] = {
        "drifter_id": group_id,
        "time_utc": (matched.ORIGIN - timedelta(seconds=delta_s)).isoformat(),
        "latitude_deg": "0",
        "longitude_deg": str(ORIGIN_LONGITUDE + math.degrees(penultimate_east_m / EARTH_MEAN_RADIUS_M)),
    }
    return rows


def contexts(**kwargs):
    return {group_id: context(group_id, **kwargs) for group_id in matched.GROUP_IDS}


def targets(group_id, *, longitude=ORIGIN_LONGITUDE):
    return [{
        "drifter_id": group_id,
        "time_utc": (matched.ORIGIN + timedelta(seconds=horizon)).isoformat(),
        "latitude_deg": "0", "longitude_deg": str(longitude),
    } for horizon in matched.HORIZONS_S]


def all_targets(**kwargs):
    return {group_id: targets(group_id, **kwargs) for group_id in matched.GROUP_IDS}


def field(*, times=(0, 3, 6), masked_hour=None, east_m_s=0.5):
    times = np.array(times, dtype=float)
    shape = (len(times), 2, 2)
    mask = np.ones(shape, dtype=bool)
    if masked_hour is not None:
        mask[times == masked_hour] = False
    return OceanField(
        time_utc=np.datetime64("2022-06-01T00:00:00", "us")
        + np.rint(times * 3_600_000_000).astype("timedelta64[us]"),
        longitude_deg=np.array([-80.0, -79.0]), latitude_deg=np.array([-1.0, 1.0]),
        eastward_m_s=np.full(shape, east_m_s), northward_m_s=np.zeros(shape),
        valid_mask=mask, selected_depth_m=15,
        metadata={"velocity_units": "m/s", "data_kind": "SYNTHETIC_TEST"},
    )


def fields(source=None):
    source = field() if source is None else source
    return dict.fromkeys(matched.GROUP_IDS, source)


def candidate(report, model_id, group_index=0):
    return report["groups"][group_index]["candidates"][matched.MODEL_IDS.index(model_id)]


def score_candidate(report, model_id, group_index=0):
    return candidate(report, model_id, group_index)


def test_fixed_plan_and_unfitted_context_contract_are_explicit():
    result = matched.build_matched_current_forecasts(contexts(), fields())
    assert matched.GROUP_IDS == ("300234066836710", "300534061292930")
    assert matched.MODEL_IDS == ("stationary", "last_drift", "current_only")
    assert result["planned_cell_count"] == 36
    assert result["planned_distinct_target_count"] == 12
    assert sum(len(item["cells"]) for group in result["groups"]
               for item in group["candidates"]) == 36
    assert all(item["status"] == "COMPLETED" for group in result["groups"]
               for item in group["candidates"])
    assert [item["context_rows_used"] for item in result["groups"][0]["candidates"]] == [1, 2, 1]
    assert all(item["learned_parameters"] == 0 and item["future_positions_used"] is False
               for group in result["groups"] for item in group["candidates"])
    assert result["forecast_sha256"] == matched.forecast_sha256(result)
    json.dumps(result, allow_nan=False)


def test_origin_anchored_last_drift_uses_actual_positive_delta_and_spherical_exp():
    forecasts = matched.build_matched_current_forecasts(contexts(), fields())
    drift = candidate(forecasts, "last_drift")
    assert drift["last_observed_delta_s"] == 3600
    assert drift["last_observed_velocity_m_s"] == pytest.approx([0.5, 0], abs=1e-12)
    for point in drift["cells"]:
        expected_lon = ORIGIN_LONGITUDE + math.degrees(point["elapsed_s"] * 0.5 / EARTH_MEAN_RADIUS_M)
        assert point["longitude_deg"] == pytest.approx(expected_lon, abs=1e-12)
        assert point["latitude_deg"] == pytest.approx(0, abs=1e-12)


def test_current_hourly_points_follow_wgs84_metric_not_spherical_last_drift_geometry():
    forecasts = matched.build_matched_current_forecasts(contexts(), fields())
    current = candidate(forecasts, "current_only")
    metres_lon, _ = _wgs84_metres_per_degree(0)
    for cell in current["cells"]:
        assert cell["longitude_deg"] == pytest.approx(
            ORIGIN_LONGITUDE + 0.5 * cell["elapsed_s"] / metres_lon, abs=2e-12,
        )
    assert current["advection"]["solver"]["maximum_step_s"] == 300
    assert current["advection"]["solver"]["output_step_s"] == 3600
    assert current["advection"]["heldout_buoy_positions_used"] is False


def test_current_candidate_integrates_changing_time_forcing_instead_of_last_observed_drift():
    source = field()
    source.eastward_m_s[:] = np.array([0.2, 0.8, 0.4])[:, None, None]
    forecasts = matched.build_matched_current_forecasts(contexts(), fields(source))
    current = candidate(forecasts, "current_only")
    metres_lon, _ = _wgs84_metres_per_degree(0)
    for cell in current["cells"]:
        t = cell["elapsed_s"]
        first_t = min(t, 10800)
        second_t = max(0, t - 10800)
        # Independent exact antiderivatives for the two linear forcing pieces.
        expected_east_m = (
            0.2 * first_t + 0.6 * first_t**2 / (2 * 10800)
            + 0.8 * second_t - 0.4 * second_t**2 / (2 * 10800)
        )
        assert (cell["longitude_deg"] - ORIGIN_LONGITUDE) * metres_lon == pytest.approx(
            expected_east_m, abs=3e-8,
        )
    assert current["cells"][-1]["longitude_deg"] != candidate(forecasts, "last_drift")["cells"][-1]["longitude_deg"]


def test_first23_context_rows_cannot_change_any_model_or_frozen_hash():
    supplied = contexts()
    original = matched.build_matched_current_forecasts(supplied, fields())
    for rows in supplied.values():
        rows[:23] = [{"deliberately_not_a_valid_position": object()} for _ in range(23)]
    changed = matched.build_matched_current_forecasts(supplied, fields())
    assert changed == original


def test_changing_penultimate_changes_only_last_drift():
    original = matched.build_matched_current_forecasts(contexts(), fields())
    changed = matched.build_matched_current_forecasts(contexts(penultimate_east_m=-900), fields())
    for group_index in range(2):
        for model_id in ("stationary", "current_only"):
            assert candidate(changed, model_id, group_index) == candidate(original, model_id, group_index)
        assert candidate(changed, "last_drift", group_index) != candidate(original, "last_drift", group_index)


@pytest.mark.parametrize("delta_s", [0, -3600])
def test_bad_penultimate_time_fails_last_drift_only(delta_s):
    result = matched.build_matched_current_forecasts(contexts(delta_s=delta_s), fields())
    for index in range(2):
        assert candidate(result, "last_drift", index)["reason_code"] == "NONPOSITIVE_CONTEXT_DELTA"
        assert candidate(result, "stationary", index)["status"] == "COMPLETED"
        assert candidate(result, "current_only", index)["status"] == "COMPLETED"


@pytest.mark.parametrize("delta_s", [7200, 3599.5])
def test_positive_irregular_context_gap_is_not_implicitly_substituted_for_hourly_cadence(delta_s):
    result = matched.build_matched_current_forecasts(contexts(delta_s=delta_s), fields())
    for index in range(2):
        drift = candidate(result, "last_drift", index)
        assert drift["reason_code"] == "CONTEXT_CADENCE_MISMATCH"
        assert drift["available_count"] == 0
        assert candidate(result, "stationary", index)["status"] == "COMPLETED"
        assert candidate(result, "current_only", index)["status"] == "COMPLETED"


def test_bad_penultimate_coordinate_fails_last_drift_only():
    supplied = contexts()
    supplied[matched.GROUP_IDS[0]][-2]["latitude_deg"] = "NaN"
    result = matched.build_matched_current_forecasts(supplied, fields())
    assert candidate(result, "last_drift")["reason_code"] == "INVALID_COORDINATE"
    assert candidate(result, "stationary")["status"] == "COMPLETED"
    assert candidate(result, "current_only")["status"] == "COMPLETED"
    assert candidate(result, "last_drift", 1)["status"] == "COMPLETED"


def test_fifty_kilometre_limit_is_not_clamped_and_failures_are_candidate_specific():
    forecasts = matched.build_matched_current_forecasts(
        contexts(penultimate_east_m=-36_000), fields(),
    )
    drift = candidate(forecasts, "last_drift")
    assert drift["status"] == "PARTIAL"
    assert drift["available_count"] == 1
    assert drift["completed_horizon_s"] == 3600
    assert drift["reason_code"] == "LOCAL_GEOMETRY_BUDGET_EXCEEDED"
    assert all(cell["latitude_deg"] is None for cell in drift["cells"][1:])
    assert candidate(forecasts, "stationary")["status"] == "COMPLETED"
    assert candidate(forecasts, "current_only")["status"] == "COMPLETED"
    too_far = matched.build_matched_current_forecasts(contexts(penultimate_east_m=-51_000), fields())
    assert candidate(too_far, "last_drift")["status"] == "FAILED"
    assert candidate(too_far, "last_drift")["available_count"] == 0


def test_current_can_travel_seventy_kilometres_and_score_far_truth_without_local_frame_limit():
    forecasts = matched.build_matched_current_forecasts(
        contexts(penultimate_east_m=-60_000), fields(field(east_m_s=70_000 / 21600)),
    )
    future = {}
    for index, group_id in enumerate(matched.GROUP_IDS):
        current = candidate(forecasts, "current_only", index)
        assert current["status"] == "COMPLETED"
        assert candidate(forecasts, "stationary", index)["status"] == "COMPLETED"
        assert candidate(forecasts, "last_drift", index)["reason_code"] == "LOCAL_GEOMETRY_BUDGET_EXCEEDED"
        assert great_circle_distance_m(
            (0, ORIGIN_LONGITUDE),
            (current["cells"][-1]["latitude_deg"], current["cells"][-1]["longitude_deg"]),
        ) > 50_000
        future[group_id] = [{
            "time_utc": cell["time_utc"], "latitude_deg": cell["latitude_deg"],
            "longitude_deg": cell["longitude_deg"],
        } for cell in current["cells"]]
    result = matched.score_matched_current_forecasts(forecasts, future)
    assert result["scored_cell_count"] == 24
    assert score_candidate(result, "current_only")["metrics"]["full_horizon_ade_m"] == 0
    assert score_candidate(result, "current_only")["metrics"]["endpoint_fde_m"] == 0
    assert result["primary_equal_id_macro_results"] is None


def test_missing_currents_leave_both_baselines_and_all36_cells():
    forecasts = matched.build_matched_current_forecasts(
        contexts(), current_failures_by_group=dict.fromkeys(matched.GROUP_IDS, "TRANSPORT_FAILED"),
    )
    result = matched.score_matched_current_forecasts(forecasts, all_targets())
    assert result["planned_cell_count"] == 36
    assert result["scored_cell_count"] == 24
    assert all(candidate(forecasts, "current_only", index)["reason_code"] == "TRANSPORT_FAILED"
               for index in range(2))
    assert result["primary_common_cohort_complete"] is False
    assert result["primary_equal_id_macro_results"] is None
    assert result["primary_paired_comparisons"] is None
    assert result["models"][0]["metrics"]["full_horizon_ade_m"] == 0
    assert result["models"][2]["metrics"]["full_horizon_ade_m"] is None


@pytest.mark.parametrize("masked_hour,status,available,completed", [
    (3, "UNSUPPORTED", 0, 0), (6, "PARTIAL", 3, 10800),
])
def test_masked_forcing_preserves_actual_status_prefix_and_denominator(
    masked_hour, status, available, completed,
):
    forecasts = matched.build_matched_current_forecasts(contexts(), fields(field(masked_hour=masked_hour)))
    current = candidate(forecasts, "current_only")
    assert current["status"] == status
    assert current["reason_code"] == "MASKED_CURRENT_CELL"
    assert current["available_count"] == available
    assert current["completed_horizon_s"] == completed
    result = matched.score_matched_current_forecasts(forecasts, all_targets())
    assert result["planned_cell_count"] == 36
    assert result["scored_cell_count"] == 24 + 2 * available
    metrics = score_candidate(result, "current_only")["metrics"]
    assert metrics["scored_count"] == available
    assert metrics["full_horizon_ade_m"] is None
    assert metrics["endpoint_fde_m"] is None
    assert metrics["scored_prefix_count"] == available
    assert metrics["prefix_is_full_horizon"] is False
    assert result["primary_equal_id_macro_results"] is None


def test_nonhourly_partial_tail_is_not_relabelled_as_hourly_prediction():
    result = matched.build_matched_current_forecasts(contexts(), fields(field(times=(0, 3, 3.5))))
    current = candidate(result, "current_only")
    assert current["status"] == "PARTIAL"
    assert current["reason_code"] == "OUTSIDE_FORCING_TIME"
    assert current["completed_horizon_s"] == 12600
    assert current["advection"]["track"][-1]["elapsed_s"] == 12600
    assert current["available_count"] == 3
    assert current["cells"][3]["latitude_deg"] is None


def test_invalid_current_configuration_is_recorded_without_blocking_baselines():
    source = field()
    source.eastward_m_s[:] = 99
    result = matched.build_matched_current_forecasts(contexts(), fields(source))
    assert candidate(result, "current_only")["reason_code"] == "CURRENT_CONFIGURATION_INVALID"
    assert candidate(result, "stationary")["status"] == "COMPLETED"
    assert candidate(result, "last_drift")["status"] == "COMPLETED"


def test_all36_cells_survive_absent_or_bad_context_and_targets():
    result = matched.evaluate_matched_current(
        {}, {}, failures_by_group={matched.GROUP_IDS[0]: "TRAJECTORY_DOWNLOAD_FAILED"},
    )
    assert result["planned_cell_count"] == 36
    assert result["scored_cell_count"] == 0
    assert candidate(result["forecast_report"], "stationary")["reason_code"] == "TRAJECTORY_DOWNLOAD_FAILED"
    assert candidate(result["forecast_report"], "stationary", 1)["reason_code"] == "CONTEXT_COUNT_INVALID"
    assert all(model["metrics"]["missing_count"] == 12 for model in result["models"])
    assert all(pair["common_scored_count"] == 0 and pair["mean_error_a_m"] is None
               for pair in result["paired_comparisons"])
    json.dumps(result, allow_nan=False)


def test_all_six_model_forecasts_exist_and_are_hashed_before_first_future_numeric_read(monkeypatch):
    finished = []
    real_advect = matched.advect_current

    def traced_advect(*args, **kwargs):
        result = real_advect(*args, **kwargs)
        finished.append(result["status"])
        return result

    monkeypatch.setattr(matched, "advect_current", traced_advect)
    ready = []
    real_score = matched.score_matched_current_forecasts

    def traced_score(forecasts, reserved):
        assert finished == ["COMPLETED", "COMPLETED"]
        assert len(forecasts["groups"]) == 2
        assert sum(len(item["cells"]) for group in forecasts["groups"]
                   for item in group["candidates"]) == 36
        assert forecasts["forecast_sha256"] == matched.forecast_sha256(forecasts)
        ready.append(True)
        return real_score(forecasts, reserved)

    monkeypatch.setattr(matched, "score_matched_current_forecasts", traced_score)

    class ReservedRow(dict):
        def get(self, key, default=None):
            if key in ("latitude_deg", "longitude_deg"):
                assert ready == [True]
                assert len(finished) == 2
            return super().get(key, default)

    future = {group_id: [ReservedRow(row) for row in targets(group_id)]
              for group_id in matched.GROUP_IDS}
    result = matched.evaluate_matched_current(contexts(), future, fields())
    assert result["scored_cell_count"] == 36


def test_every_planned_cell_is_allocated_before_any_current_candidate_attempt(monkeypatch):
    allocated = []
    real_candidate = matched._candidate
    real_current = matched._current

    def tracked_candidate(model_id):
        result = real_candidate(model_id)
        allocated.append(result)
        return result

    def tracked_current(*args, **kwargs):
        assert len(allocated) == 6
        assert sum(len(item["cells"]) for item in allocated) == 36
        return real_current(*args, **kwargs)

    monkeypatch.setattr(matched, "_candidate", tracked_candidate)
    monkeypatch.setattr(matched, "_current", tracked_current)
    matched.build_matched_current_forecasts(contexts(), fields())


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "", "91", True, None])
def test_bad_future_latitude_never_changes_prior_forecasts_or_becomes_zero_error(bad):
    forecasts = matched.build_matched_current_forecasts(contexts(), fields())
    before = copy.deepcopy(forecasts)
    future = all_targets()
    future[matched.GROUP_IDS[0]][2]["latitude_deg"] = bad
    result = matched.score_matched_current_forecasts(forecasts, future)
    assert forecasts == before == result["forecast_report"]
    assert result["scored_cell_count"] == 33
    assert result["primary_equal_id_macro_results"] is None
    for model_id in matched.MODEL_IDS:
        item = score_candidate(result, model_id)
        assert item["cells"][2]["error_m"] is None
        assert item["cells"][2]["score_status"] == "TARGET_UNAVAILABLE"
        assert item["cells"][2]["target_reason_code"] == "TARGET_INVALID_COORDINATE"
        assert item["metrics"]["full_horizon_ade_m"] is None
        assert item["metrics"]["scored_prefix_count"] == 2
        assert item["metrics"]["endpoint_scored"] is True


def test_scoring_never_radius_or_tile_filters_future_truth():
    forecasts = matched.build_matched_current_forecasts(contexts(), fields())
    result = matched.score_matched_current_forecasts(forecasts, all_targets(longitude=-70))
    assert result["scored_cell_count"] == 36
    expected = great_circle_distance_m((0, ORIGIN_LONGITUDE), (0, -70))
    assert expected > 50_000
    assert score_candidate(result, "stationary")["metrics"]["endpoint_fde_m"] == expected
    assert score_candidate(result, "stationary")["metrics"]["full_horizon_ade_m"] == expected
    assert result["primary_common_cohort_complete"] is True


def test_missing_interior_target_retains_available_endpoint_without_claiming_full_ade():
    forecasts = matched.build_matched_current_forecasts(contexts(), fields())
    future = all_targets()
    del future[matched.GROUP_IDS[0]][1]
    result = matched.score_matched_current_forecasts(forecasts, future)
    item = score_candidate(result, "stationary")
    assert item["metrics"]["scored_count"] == 5
    assert item["metrics"]["full_horizon_ade_m"] is None
    assert item["metrics"]["endpoint_fde_m"] == 0
    assert item["metrics"]["scored_prefix_count"] == 1
    assert item["cells"][1]["target_reason_code"] == "MISSING_TARGET"
    assert result["primary_paired_comparisons"] is None


@pytest.mark.parametrize("change,reason", [
    ({"longitude_deg": "-181"}, "TARGET_INVALID_COORDINATE"),
    ({"drifter_id": "another"}, "TARGET_ID_MISMATCH"),
    ({"time_utc": "invalid"}, "MISSING_TARGET"),
    ({"time_utc": "2022-06-01T01:00:00"}, "MISSING_TARGET"),
])
def test_bad_future_identity_time_or_longitude_is_a_missing_score_not_a_prediction_failure(change, reason):
    forecasts = matched.build_matched_current_forecasts(contexts(), fields())
    future = all_targets()
    future[matched.GROUP_IDS[0]][0].update(change)
    result = matched.score_matched_current_forecasts(forecasts, future)
    assert result["scored_cell_count"] == 33
    assert score_candidate(result, "stationary")["prediction_status"] == "COMPLETED"
    cell = score_candidate(result, "stationary")["cells"][0]
    assert cell["target_reason_code"] == reason
    assert cell["error_m"] is None
    assert result["groups"][0]["target_issues"]


def test_duplicate_target_time_is_not_arbitrarily_chosen_and_pair_cells_are_explicit():
    forecasts = matched.build_matched_current_forecasts(contexts(), fields())
    future = all_targets()
    future[matched.GROUP_IDS[0]].append(copy.deepcopy(future[matched.GROUP_IDS[0]][0]))
    result = matched.score_matched_current_forecasts(forecasts, future)
    assert result["scored_cell_count"] == 33
    cell = score_candidate(result, "stationary")["cells"][0]
    assert cell["target_reason_code"] == "DUPLICATE_TARGET_TIME"
    for pair in result["paired_comparisons"]:
        assert pair["common_scored_count"] == 11
        assert pair["planned_common_cell_count"] == 12
        assert pair["coverage_complete"] is False
        assert all(cell["group_id"] in matched.GROUP_IDS and cell["time_utc"]
                   and 1 <= cell["horizon_hours"] <= 6 for cell in pair["cells"])
        assert not any(cell["group_id"] == matched.GROUP_IDS[0] and cell["horizon_hours"] == 1
                       for cell in pair["cells"])


def test_primary_equal_id_results_require_every_model_cell_and_keep_secondary_stats():
    forecasts = matched.build_matched_current_forecasts(contexts(), fields())
    full = matched.score_matched_current_forecasts(forecasts, all_targets())
    assert full["primary_common_cohort_complete"] is True
    assert len(full["primary_equal_id_macro_results"]) == 3
    assert len(full["primary_paired_comparisons"]) == 3
    for model in full["primary_equal_id_macro_results"]:
        index = matched.MODEL_IDS.index(model["model_id"])
        expected = sum(group["candidates"][index]["metrics"]["full_horizon_ade_m"]
                       for group in full["groups"]) / 2
        assert model["equal_id_macro_ade_m"] == expected
        assert len(model["per_horizon_mean_error_m"]) == 6
    assert full["automatic_winner_selected"] is False
    assert full["statistical_independence"] is False


def test_a_missing_forecast_hash_or_tampered_prior_forecast_fails_before_reserved_reads():
    forecasts = matched.build_matched_current_forecasts(contexts(), fields())

    class NeverDecode(dict):
        def get(self, *args):
            raise AssertionError("Reserved data read before forecast validation")

    future = {group_id: [NeverDecode()] for group_id in matched.GROUP_IDS}
    del forecasts["forecast_sha256"]
    with pytest.raises(ValueError, match="hash"):
        matched.score_matched_current_forecasts(forecasts, future)
    forecasts["forecast_sha256"] = matched.forecast_sha256(forecasts)
    forecasts["groups"][0]["candidates"][0]["cells"][0]["longitude_deg"] = -79
    with pytest.raises(ValueError, match="hash"):
        matched.score_matched_current_forecasts(forecasts, future)


def test_rehashed_invalid_forecast_coordinate_is_rejected_before_target_decode():
    forecasts = matched.build_matched_current_forecasts(contexts(), fields())
    forecasts["groups"][0]["candidates"][0]["cells"][0]["latitude_deg"] = 91
    forecasts["forecast_sha256"] = matched.forecast_sha256(forecasts)
    with pytest.raises(ValueError, match="INVALID_COORDINATE"):
        matched.score_matched_current_forecasts(forecasts, {})


@pytest.mark.parametrize("bad_group", ["other", "300234066836711"])
def test_outside_cohort_is_rejected_rather_than_expanding_or_replacing_fixed_slots(bad_group):
    with pytest.raises(ValueError, match="fixed group IDs"):
        matched.build_matched_current_forecasts({bad_group: context(bad_group)})
    forecasts = matched.build_matched_current_forecasts(contexts(), fields())
    with pytest.raises(ValueError, match="fixed group IDs"):
        matched.score_matched_current_forecasts(forecasts, {bad_group: targets(bad_group)})
