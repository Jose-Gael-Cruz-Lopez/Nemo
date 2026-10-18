"""Synthetic causal-filter and bidirectional walkthrough contracts."""

import copy

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import ocean_source_pipeline as model
from apps.ocean.reeftrace_ocean.benchmark import SphericalLocalFrame
from tests.unit.test_ocean_source import (
    LAT,
    LON,
    field,
    position,
    tutorial_observations,
    tutorial_truth,
)


def test_causal_initial_states_and_joseph_covariance_for_constant_local_velocity():
    group = model.GROUP_IDS[0]
    frame = SphericalLocalFrame(LAT, LON)
    raw = [position(group, hour, *frame.to_latlon(np.array([360. * (hour - 1), 0.]))) for hour in (1, 2, 3)]
    before = copy.deepcopy(raw)
    parsed, states = model.filter_three_positions(raw, group)
    assert raw == before
    assert [row["status"] for row in states] == ["POSITION_ONLY", "INITIALIZED", "UPDATED"]
    assert states[0]["eastward_m_s"] is states[0]["northward_m_s"] is states[0]["covariance"] is None
    assert states[0]["east_m"] == pytest.approx(0., abs=1e-6)
    assert states[-1]["eastward_m_s"] == pytest.approx(.1, abs=1e-12)
    assert states[-1]["east_m"] == pytest.approx(720., abs=1e-6)
    for state in states[1:]:
        covariance = np.asarray(state["covariance"])
        assert covariance == pytest.approx(covariance.T)
        assert np.linalg.eigvalsh(covariance).min() > 0
    changed = copy.deepcopy(raw)
    changed[-1]["longitude_deg"] = str(float(changed[-1]["longitude_deg"]) + .001)
    _, changed_states = model.filter_three_positions(changed, group)
    assert changed_states[:2] == states[:2]  # No future03 fix changes01/02 filtered states.
    assert parsed[0]["time_utc"] == model.OBSERVATION_TIMES[0]


@pytest.mark.parametrize("change", ["extra", "duplicate", "wrong_id", "boolean", "wrong_time", "huge_speed"])
def test_only_three_exact_hourly_permitted_fixes(change):
    group = model.GROUP_IDS[0]
    rows = tutorial_observations()[group]
    if change == "extra":
        rows.insert(0, position(group, 0))
    elif change == "duplicate":
        rows[1] = rows[0]
    elif change == "wrong_id":
        rows[0]["drifter_id"] = "different"
    elif change == "boolean":
        rows[0]["latitude_deg"] = True
    elif change == "wrong_time":
        rows[0]["time_utc"] = "2022-06-01T00:00:00Z"
    else:
        rows[1]["longitude_deg"] = "-79."
    with pytest.raises(ValueError):
        model.filter_three_positions(rows, group)


def test_bias_formula_and_two_correct_three_hour_branches():
    forecasts = model.build_pipeline_forecasts(tutorial_observations(), field())
    assert forecasts["earlier_truth_used"] is forecasts["later_truth_used"] is False
    for group in forecasts["groups"]:
        assert group["status"] == "COMPLETED"
        assert group["raw_observations"] == group["connected_path"]
        assert group["formula"]["current_east_north_m_s"] == pytest.approx([.6, 0.])
        assert group["formula"]["residual_bias_east_north_m_s"] == pytest.approx([-.6, 0.], abs=1e-12)
        assert group["forward"]["track"][0]["time_utc"] == group["backward"]["track"][0]["time_utc"] == model.ANCHOR_TIME
        assert group["forward"]["completed_horizon_s"] == group["backward"]["completed_lookback_s"] == 10800
        assert group["backward"]["track"][-1]["time_utc"] == "2022-06-01T00:00:00Z"
        assert group["forward"]["track"][-1]["time_utc"] == "2022-06-01T06:00:00Z"
        # Velocity is zero at03; changing forcing still curves displacement in time.
        assert group["backward"]["track"][-1]["longitude_deg"] > LON
        assert group["forward"]["track"][-1]["longitude_deg"] > LON
    unchanged = copy.deepcopy(forecasts)
    validation = model.score_pipeline_forecasts(forecasts, tutorial_truth())
    assert validation["planned_rows"] == validation["scored_rows"] == 8
    assert [row["direction"] for row in validation["rows"][:4]] == ["backward", "forward", "forward", "forward"]
    assert forecasts == unchanged
    changed = tutorial_truth()
    changed[model.GROUP_IDS[0]][model.TRUTH_TIMES[0]]["longitude_deg"] = "-79.4"
    assert model.score_pipeline_forecasts(forecasts, changed) != validation
    assert forecasts == unchanged


def test_corrected_field_preserves_original_axes_mask_and_deep_metadata():
    original = field()
    before = copy.deepcopy(original)
    corrected = model.corrected_current_field(original, [-.6, 0.])
    for name in ("time_utc", "latitude_deg", "longitude_deg", "valid_mask"):
        assert np.array_equal(getattr(corrected, name), getattr(original, name))
    for name in ("time_utc", "latitude_deg", "longitude_deg", "valid_mask", "eastward_m_s", "northward_m_s"):
        assert not np.shares_memory(getattr(corrected, name), getattr(original, name))
        assert not getattr(corrected, name).flags.writeable
        assert np.array_equal(getattr(original, name), getattr(before, name))
    corrected.metadata["nested"]["values"].append(2)
    assert original.metadata == before.metadata
    with pytest.raises(ValueError):
        model.corrected_current_field(original, ["0", 0.])
    with pytest.raises(ValueError):
        model.corrected_current_field(original, [10., 0.])  # Derived speed cannot exceed sampler cap.


def test_missing_flow_masks_and_missing_groups_stay_visible_without_fake_prediction():
    forecasts = model.build_pipeline_forecasts(tutorial_observations(), None, field_failure="UPSTREAM_REASON")
    for group in forecasts["groups"]:
        assert len(group["filtered_states"]) == 3 and group["status"] == "PARTIAL"
        assert group["reason_code"] == "UPSTREAM_REASON"
        assert group["forward"]["track"] == group["backward"]["track"] == []
    score = model.score_pipeline_forecasts(forecasts, tutorial_truth())
    assert len(score["rows"]) == 8 and score["scored_rows"] == 0
    masked = field()
    masked.valid_mask[1] = False
    result = model.build_pipeline_forecasts(tutorial_observations(), masked)
    assert all(group["reason_code"] == "MASKED_CURRENT_CELL" for group in result["groups"])
    missing = model.build_pipeline_forecasts({}, field())
    assert len(missing["groups"]) == 2 and all(not group["raw_observations"] for group in missing["groups"])
    assert model.score_pipeline_forecasts(missing, {})["scored_rows"] == 0


def test_forecast_identity_rejects_changed_stage_or_coordinate_before_scoring():
    forecasts = model.build_pipeline_forecasts(tutorial_observations(), None)
    forecasts["groups"][0]["filtered_anchor"]["longitude_deg"] += .1
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        model.score_pipeline_forecasts(forecasts, tutorial_truth())


def test_missing_earliest_forcing_and_later_masks_affect_only_supported_branches():
    early_missing = field()
    early_missing.valid_mask[0] = False
    result = model.build_pipeline_forecasts(tutorial_observations(), early_missing)
    for group in result["groups"]:
        assert group["backward"]["status"] != "COMPLETED"
        assert group["forward"]["status"] == "COMPLETED"
    late_missing = field()
    late_missing.valid_mask[2] = False
    result = model.build_pipeline_forecasts(tutorial_observations(), late_missing)
    for group in result["groups"]:
        assert group["backward"]["status"] == "COMPLETED"
        assert group["forward"]["status"] != "COMPLETED"
        assert group["forward"]["reason_code"] == "MASKED_CURRENT_CELL"


def test_heldout_validation_mutation_never_enters_inference_or_changes_forecast_hash():
    inputs, reserved = tutorial_observations(), tutorial_truth()
    first = model.build_pipeline_forecasts(inputs, field())
    first_score = model.score_pipeline_forecasts(first, reserved)
    for group in reserved.values():
        for row in group.values():
            row["longitude_deg"] = "-79.3"
    second = model.build_pipeline_forecasts(inputs, field())
    assert second == first and second["forecast_sha256"] == first["forecast_sha256"]
    assert model.score_pipeline_forecasts(second, reserved) != first_score


def test_duplicate_fixed_group_cannot_be_scored_even_if_digest_recomputed():
    forecasts = model.build_pipeline_forecasts(tutorial_observations(), None)
    forecasts["groups"][1] = copy.deepcopy(forecasts["groups"][0])
    forecasts["forecast_sha256"] = model.forecast_sha256(forecasts)
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        model.score_pipeline_forecasts(forecasts, tutorial_truth())


@pytest.mark.parametrize("failed_direction", ["backward", "forward"])
def test_branch_exception_does_not_erase_the_independent_supported_branch(monkeypatch, failed_direction):
    failing = "backtrack_current" if failed_direction == "backward" else "advect_current"

    def fail(*_args, **_kwargs):
        raise ValueError("BRANCH_STEP_BUDGET_EXCEEDED")

    monkeypatch.setattr(model, failing, fail)
    forecasts = model.build_pipeline_forecasts(tutorial_observations(), field())
    supported = "forward" if failed_direction == "backward" else "backward"
    for group in forecasts["groups"]:
        assert group["status"] == "PARTIAL"
        assert len(group["filtered_states"]) == 3 and group["formula"] is not None
        assert group[failed_direction]["status"] == "UNSUPPORTED"
        assert group[failed_direction]["reason_code"] == "BRANCH_STEP_BUDGET_EXCEEDED"
        assert group[failed_direction]["track"] == []
        assert group[supported]["status"] == "COMPLETED"
        assert len(group[supported]["track"]) == 37
    validation = model.score_pipeline_forecasts(forecasts, tutorial_truth())
    assert len(validation["rows"]) == 8
    assert validation["scored_rows"] == (6 if failed_direction == "backward" else 2)


def test_both_turning_current_branches_match_independent_negative_time_oracle():
    from scipy.integrate import solve_ivp

    forcing = field(east=(.2, .6, 1.), north=(.4, -.2, .1))
    group = model.build_pipeline_forecasts(tutorial_observations(), forcing)["groups"][0]
    assert group["status"] == "COMPLETED"
    bias = np.array(group["formula"]["residual_bias_east_north_m_s"])
    assert bias == pytest.approx([-.6, .2], abs=1e-12)

    def derivative(actual_time, state):
        u = np.interp(actual_time, [0, 10800, 21600], [.2, .6, 1.]) + bias[0]
        v = np.interp(actual_time, [0, 10800, 21600], [.4, -.2, .1]) + bias[1]
        latitude = np.deg2rad(state[0])
        eccentricity2 = 6.6943799901413165e-3
        denominator = 1 - eccentricity2 * np.sin(latitude)**2
        meridional = 6378137 * (1 - eccentricity2) / denominator**1.5
        prime = 6378137 / np.sqrt(denominator)
        return [v * 180 / (np.pi * meridional), u * 180 / (np.pi * prime * np.cos(latitude))]

    anchor = group["filtered_anchor"]
    start = [anchor["latitude_deg"], anchor["longitude_deg"]]
    for direction, final_time in (("backward", 0), ("forward", 21600)):
        reference = solve_ivp(derivative, [10800, final_time], start,
                              method="DOP853", rtol=1e-12, atol=1e-12)
        assert reference.success
        endpoint = group[direction]["track"][-1]
        assert [endpoint["latitude_deg"], endpoint["longitude_deg"]] == pytest.approx(
            reference.y[:, -1], abs=1e-10)


def test_single_causal_measurement_update_matches_declared_covariance_oracle():
    group = model.GROUP_IDS[0]
    frame = SphericalLocalFrame(LAT, LON)
    # First interval is 0.1 m/s east. The final fix is 100 m east of that
    # extrapolation. The scalar one-axis covariance values below are derived
    # from independent 100 m fix errors and integrated white acceleration.
    fixes = [position(group, hour, *frame.to_latlon(np.array([east, 0.])))
             for hour, east in ((1, 0.), (2, 360.), (3, 820.))]
    _, states = model.filter_three_positions(fixes, group)
    predicted_position_variance = 65552.
    predicted_position_velocity_covariance = 14.813333333333333
    predicted_velocity_variance = 2 * 10000. / 3600.**2 + .0036
    innovation_variance = predicted_position_variance + 10000.
    position_gain = predicted_position_variance / innovation_variance
    velocity_gain = predicted_position_velocity_covariance / innovation_variance
    assert states[-1]["east_m"] == pytest.approx(720. + 100. * position_gain, abs=1e-6)
    assert states[-1]["eastward_m_s"] == pytest.approx(.1 + 100. * velocity_gain, abs=1e-10)
    covariance = np.asarray(states[-1]["covariance"])
    assert covariance[0, 0] == pytest.approx(predicted_position_variance * 10000. / innovation_variance)
    assert covariance[0, 2] == pytest.approx(
        predicted_position_velocity_covariance * 10000. / innovation_variance)
    assert covariance[2, 2] == pytest.approx(predicted_velocity_variance
        - predicted_position_velocity_covariance**2 / innovation_variance)


def test_raw_fix_outside_local_domain_cannot_be_hidden_by_filter_correction():
    group = model.GROUP_IDS[0]
    frame = SphericalLocalFrame(LAT, LON)
    fixes = [position(group, 1), position(group, 2, *frame.to_latlon(np.array([10000., 0.]))),
             position(group, 3, lon=LON + .53)]
    # The shared geometry guard rejects the >50km measurement before a filter
    # correction could pull its state back inside the permitted local frame.
    with pytest.raises(ValueError, match="50 km local-geometry budget"):
        model.filter_three_positions(fixes, group)
