"""Synthetic-only reverse-current and artifact contracts; no real cohort execution."""

import copy
import json

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import ocean_source as model
from apps.ocean.reeftrace_ocean import ocean_source_pipeline as pipeline
from apps.ocean.reeftrace_ocean.advection import _wgs84_metres_per_degree
from apps.ocean.reeftrace_ocean.benchmark import SphericalLocalFrame
from apps.ocean.reeftrace_ocean.field import OceanField
from scripts import evaluate_ocean_source as runner

LAT, LON = 30., -79.5


def field(east=(.2, .6, 1.), north=(0., 0., 0.), mask=None):
    shape = (3, 2, 2)
    return OceanField(np.array(["2022-06-01T00", "2022-06-01T03", "2022-06-01T06"], dtype="datetime64[us]"),
        np.array([-80., -79.]), np.array([29., 31.]),
        np.broadcast_to(np.array(east)[:, None, None], shape).copy(),
        np.broadcast_to(np.array(north)[:, None, None], shape).copy(),
        np.ones(shape, dtype=bool) if mask is None else np.array(mask, copy=True),
        15., {"velocity_units": "m/s", "sha256": "a" * 64, "nested": {"values": [1]}})


def position(group, hour, lat=LAT, lon=LON):
    return {"drifter_id": group, "time_utc": f"2022-06-01T0{hour}:00:00Z",
            "latitude_deg": str(lat), "longitude_deg": str(lon)}


def observations():
    return {group: [position(group, 5), position(group, 6)] for group in model.GROUP_IDS}


def earlier_truth():
    return {group: position(group, 0) for group in model.GROUP_IDS}


def tutorial_observations():
    return {group: [position(group, hour) for hour in (1, 2, 3)] for group in model.GROUP_IDS}


def tutorial_truth():
    return {group: {time: position(group, int(time[12])) for time in pipeline.TRUTH_TIMES}
            for group in model.GROUP_IDS}


def test_reverse_time_field_is_correct_independent_immutable_copy():
    original = field()
    before = copy.deepcopy(original)
    transformed = model.reverse_current_field(original, model.OBSERVATION_TIME_UTC, (.05, 0.))
    assert np.array_equal(transformed.time_utc, np.array(
        ["2022-06-01T06", "2022-06-01T09", "2022-06-01T12"], dtype="datetime64[us]"))
    assert np.array_equal(transformed.eastward_m_s, -(original.eastward_m_s[::-1] + .05))
    for name in ("time_utc", "longitude_deg", "latitude_deg", "eastward_m_s", "northward_m_s", "valid_mask"):
        assert np.array_equal(getattr(original, name), getattr(before, name))
        assert not np.shares_memory(getattr(original, name), getattr(transformed, name))
        assert not getattr(transformed, name).flags.writeable
    transformed.metadata["nested"]["values"].append(2)
    assert original.metadata == before.metadata


def test_time_varying_east_only_analytic_oracle_catches_naive_negation():
    path = model.backtrack_current(field(), position(model.GROUP_IDS[0], 6))
    assert path["status"] == "COMPLETED"
    metres_lon, _ = _wgs84_metres_per_degree(LAT)
    # Fixed latitude makes the WGS84 longitude metric constant. The current is
    # linear in actual time: first backward hour averages .933333... m/s.
    first_hour = next(point for point in path["track"] if point["lookback_s"] == 3600)
    assert first_hour["longitude_deg"] == pytest.approx(LON - ((1 + (1 - .8 / 6)) / 2 * 3600) / metres_lon,
                                                     abs=2e-12)
    assert path["track"][-1]["longitude_deg"] == pytest.approx(LON - .6 * 21600 / metres_lon, abs=2e-12)
    assert path["track"][0]["time_utc"] == model.OBSERVATION_TIME_UTC
    assert path["track"][-1]["time_utc"] == model.EARLIER_TIME_UTC
    assert all(a["time_utc"] > b["time_utc"] for a, b in zip(path["track"], path["track"][1:]))


@pytest.mark.parametrize("kwargs", [
    {"endpoint_offset_east_north_m": [True, 0.]},
    {"endpoint_offset_east_north_m": [101., 0.]},
    {"endpoint_offset_east_north_m": np.array(1.)},
    {"current_bias_east_north_m_s": [.051, 0.]},
    {"current_bias_east_north_m_s": ["0", 0.]},
    {"horizon_s": True}, {"horizon_s": 21601}, {"horizon_s": float("nan")},
])
def test_strict_vector_and_duration_contract(kwargs):
    with pytest.raises(ValueError):
        model.backtrack_current(field(), position(model.GROUP_IDS[0], 6), **kwargs)


def test_mask_time_and_domain_failures_preserve_supported_prefix_only():
    masked = field()
    masked.valid_mask[0] = False
    result = model.backtrack_current(masked, position(model.GROUP_IDS[0], 6))
    assert result["status"] == "PARTIAL" and result["reason_code"] == "MASKED_CURRENT_CELL"
    assert 0 < result["completed_lookback_s"] <= 10800
    result = model.backtrack_current(field(), position(model.GROUP_IDS[0], 7))
    assert result["status"] == "UNSUPPORTED" and result["reason_code"] == "OUTSIDE_FORCING_TIME"
    result = model.backtrack_current(field(), position(model.GROUP_IDS[0], 6, lon=-78.))
    assert result["status"] == "UNSUPPORTED" and result["reason_code"] == "OUTSIDE_CURRENT_DOMAIN"


def test_fixed_plan_counts_sensitivity_not_probability_and_truth_separate():
    forecasts = model.build_ocean_source_forecasts(observations(), field())
    assert forecasts["planned_model_rows"] == 6 and forecasts["planned_distinct_earlier_positions"] == 2
    assert forecasts["earlier_truth_used"] is False
    assert forecasts["physical_validation"] is forecasts["source_attribution_validated"] is False
    for group in forecasts["groups"]:
        assert [row["model_id"] for row in group["candidates"]] == list(model.MODEL_IDS)
        reverse = group["reverse_current"]
        assert len(reverse["scenarios"]) == 25
        assert len({row["scenario_id"] for row in reverse["scenarios"]}) == 25
        assert reverse["coverage"] == {"planned_scenarios": 25, "completed_scenarios": 25,
                                        "partial_scenarios": 0, "unsupported_scenarios": 0}
        assert [row["available_count"] for row in reverse["earlier_candidates"]] == [25, 25, 25]
        assert group["numerical_closure"]["endpoint_distance_m"] < 1e-5
    unchanged = copy.deepcopy(forecasts)
    score = model.score_ocean_source_forecasts(forecasts, earlier_truth())
    assert score["scored_model_rows"] == 6 and score["primary_complete"] is True
    assert score["rows"][2]["error_m"] > 10000  # Good numerical closure does not establish actual accuracy.
    altered = earlier_truth()
    altered[model.GROUP_IDS[0]]["longitude_deg"] = "-79.4"
    assert model.score_ocean_source_forecasts(forecasts, altered) != score
    assert forecasts == unchanged


def test_missing_input_and_current_keep_every_planned_row_without_primary():
    forecasts = model.build_ocean_source_forecasts({}, None, field_failure="UPSTREAM_UNAVAILABLE")
    assert len(forecasts["groups"]) == 2
    for group in forecasts["groups"]:
        assert len(group["candidates"]) == 3
        assert group["reverse_current"]["coverage"]["unsupported_scenarios"] == 25
        assert all(not row["points"] for row in group["reverse_current"]["earlier_candidates"])
    score = model.score_ocean_source_forecasts(forecasts, earlier_truth())
    assert len(score["rows"]) == 6 and score["scored_model_rows"] == 0
    assert score["primary_mean_earlier_position_error_m"] is None
    upstream = model.build_ocean_source_forecasts(observations(), None, field_failure="UPSTREAM_UNAVAILABLE")
    assert upstream["groups"][0]["reverse_current"]["scenarios"][0]["reason_code"] == "UPSTREAM_UNAVAILABLE"


def test_inference_rejects_earlier_truth_extra_fields_and_nonfixed_ids():
    inputs = observations()
    inputs[model.GROUP_IDS[0]].insert(0, position(model.GROUP_IDS[0], 0))
    result = model.build_ocean_source_forecasts(inputs, field())
    assert result["groups"][0]["observed_endpoint"] is None
    assert all(row["status"] == "UNSUPPORTED" for row in result["groups"][0]["candidates"])
    with pytest.raises(ValueError):
        model.build_ocean_source_forecasts({"another": []}, field())
    with pytest.raises(ValueError):
        model._position({**position(model.GROUP_IDS[0], 6), "earlier_truth": "no"})


def test_last_drift_is_six_times_negative_final_forward_displacement():
    group = model.GROUP_IDS[0]
    previous = SphericalLocalFrame(LAT, LON).to_latlon(np.array([-360., 0.]))
    inputs = observations()
    inputs[group][0] = position(group, 5, *previous)
    forecast = model.build_ocean_source_forecasts(inputs, None)
    candidate = forecast["groups"][0]["candidates"][1]
    xy = SphericalLocalFrame(LAT, LON).to_xy(candidate["latitude_deg"], candidate["longitude_deg"])
    assert xy == pytest.approx([-2160., 0.], abs=1e-6)


def setup_synthetic_runner(tmp_path, monkeypatch):
    protocol = {"method_source_sha256": {"synthetic": "b" * 64}, "source_artifact_pins": {"synthetic": "c" * 64}}
    (tmp_path / "protocol.json").write_bytes(runner._canonical(protocol))
    monkeypatch.setattr(runner, "make_protocol", lambda: copy.deepcopy(protocol))
    monkeypatch.setattr(runner, "_committed_method", lambda: "f" * 40)
    lineage = {"synthetic": "d" * 64}
    monkeypatch.setattr(runner, "_source_inputs", lambda: (observations(), earlier_truth(), tutorial_observations(),
        tutorial_truth(), field(), None, lineage, {}))
    monkeypatch.setattr(runner, "load_acquisition", lambda _: ({}, {}, lineage, {}))


def test_synthetic_execution_saves_all_inference_before_any_truth_decode_and_reader_never_computes(tmp_path, monkeypatch):
    setup_synthetic_runner(tmp_path, monkeypatch)
    original_score, original_tutorial_score = model.score_ocean_source_forecasts, pipeline.score_pipeline_forecasts
    events = []
    original_load = runner._load

    def load(path):
        result = original_load(path)
        if path.name == "pipeline-forecasts.json":
            events.append("pipeline_readback")
        if path.name == "forecasts.json":
            events.append("readback")
        return result

    def score(forecasts, truth):
        assert events == ["pipeline_readback", "readback"]
        assert (tmp_path / "forecasts.sha256").exists()
        events.append("earlier_truth_decode")
        return original_score(forecasts, truth)

    def tutorial_score(forecasts, truth):
        assert events == ["pipeline_readback", "readback", "earlier_truth_decode"]
        events.append("tutorial_truth_decode")
        return original_tutorial_score(forecasts, truth)

    monkeypatch.setattr(runner, "_load", load)
    monkeypatch.setattr(model, "score_ocean_source_forecasts", score)
    monkeypatch.setattr(pipeline, "score_pipeline_forecasts", tutorial_score)
    result = runner.first_score(tmp_path)
    assert result["validation"]["scored_model_rows"] == 6
    assert result["pipeline_tutorial"]["validation"]["scored_rows"] == 8
    assert events == ["pipeline_readback", "readback", "earlier_truth_decode", "tutorial_truth_decode"]
    snapshot = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    for module, names in ((model, ("build_ocean_source_forecasts", "score_ocean_source_forecasts", "backtrack_current")),
                          (pipeline, ("build_pipeline_forecasts", "score_pipeline_forecasts"))):
        for name in names:
            monkeypatch.setattr(module, name, lambda *_a, **_k: pytest.fail("reader executed scientific code"))
    monkeypatch.setattr(runner, "_source_inputs", lambda: pytest.fail("reader decoded inference inputs"))
    envelope = runner.read_result(tmp_path)
    assert envelope["report"] == result
    assert envelope["artifact_identity"]["numeric_replay_verified"] is False
    identity = envelope["artifact_identity"]["identity_sha256"]
    assert runner.read_result(tmp_path, expected_identity_sha256=identity)["artifact_identity"]["external_result_pin_verified"]
    with pytest.raises(ValueError, match="externally pinned"):
        runner.read_result(tmp_path, expected_identity_sha256="0" * 64)
    with pytest.raises(ValueError, match="never overwrite"):
        runner.first_score(tmp_path)
    assert snapshot == {path.name: path.read_bytes() for path in tmp_path.iterdir()}


def test_synthetic_reader_rejects_changed_bytes_and_symlinks(tmp_path, monkeypatch):
    setup_synthetic_runner(tmp_path, monkeypatch)
    runner.first_score(tmp_path)
    path = tmp_path / "evaluation.json"
    report = json.loads(path.read_bytes())
    report["physical_validation"] = True
    path.write_bytes(runner._canonical(report))
    with pytest.raises(ValueError, match="detached hash"):
        runner.read_result(tmp_path)
    path.unlink()
    path.symlink_to(tmp_path / "forecasts.json")
    with pytest.raises(ValueError, match="symlinks"):
        runner._load(path)


def test_actual_first_score_guard_requires_committed_methods(monkeypatch):
    # Only asks Git for the method bytes; never loads or scores real trajectories.
    monkeypatch.setattr(runner, "METHOD_FILES", ("not-a-reviewed-source.py",))
    with pytest.raises(ValueError, match="Committed reviewed"):
        runner._committed_method()


def test_turning_time_varying_flow_against_independent_high_accuracy_geographic_reference():
    from scipy.integrate import solve_ivp

    forcing = field(east=(.2, .6, 1.), north=(.4, -.2, .1))
    result = model.backtrack_current(forcing, position(model.GROUP_IDS[0], 6))

    def derivative(lookback, state):
        actual = 21600 - lookback
        u = np.interp(actual, [0, 10800, 21600], [.2, .6, 1.])
        v = np.interp(actual, [0, 10800, 21600], [.4, -.2, .1])
        latitude = np.deg2rad(state[0])
        eccentricity2 = 6.6943799901413165e-3
        denominator = 1 - eccentricity2 * np.sin(latitude)**2
        meridional = 6378137 * (1 - eccentricity2) / denominator**1.5
        prime = 6378137 / np.sqrt(denominator)
        return [-v * 180 / (np.pi * meridional), -u * 180 / (np.pi * prime * np.cos(latitude))]

    first = solve_ivp(derivative, [0, 10800], [LAT, LON], method="DOP853", rtol=1e-12, atol=1e-12)
    second = solve_ivp(derivative, [10800, 21600], first.y[:, -1], method="DOP853", rtol=1e-12, atol=1e-12)
    point = result["track"][-1]
    assert [point["latitude_deg"], point["longitude_deg"]] == pytest.approx(second.y[:, -1], abs=1e-10)


def test_duplicate_group_and_candidate_missing_rows_rejected_even_after_digest_update():
    forecasts = model.build_ocean_source_forecasts(observations(), None)
    forecasts["groups"][1] = copy.deepcopy(forecasts["groups"][0])
    forecasts["forecast_sha256"] = model.forecast_sha256(forecasts)
    with pytest.raises(ValueError, match="IDENTITY_INVALID"):
        model.score_ocean_source_forecasts(forecasts, earlier_truth())
    forecasts = model.build_ocean_source_forecasts(observations(), None)
    forecasts["groups"][0]["candidates"].pop()
    forecasts["forecast_sha256"] = model.forecast_sha256(forecasts)
    with pytest.raises(ValueError, match="IDENTITY_INVALID"):
        model.score_ocean_source_forecasts(forecasts, earlier_truth())


def test_global_tutorial_future_numeric_firewall_precedes_independent_endpoint_study(tmp_path, monkeypatch):
    setup_synthetic_runner(tmp_path, monkeypatch)
    readback = False
    decoded_hours = []
    original_load = runner._load

    class GuardedCoordinate(str):
        def __new__(cls, value, hour):
            instance = str.__new__(cls, value)
            instance.hour = hour
            return instance

        def __float__(self):
            assert readback, "05/06 numeric decode preceded both tutorial groups' saved readback"
            decoded_hours.append(self.hour)
            return float(str(self))

    guarded_observations = observations()
    for rows in guarded_observations.values():
        for row in rows:
            row["latitude_deg"] = GuardedCoordinate(row["latitude_deg"], int(row["time_utc"][12]))
            row["longitude_deg"] = GuardedCoordinate(row["longitude_deg"], int(row["time_utc"][12]))

    def load(path):
        nonlocal readback
        result = original_load(path)
        if path.name == "pipeline-forecasts.json":
            assert all(len(group["filtered_states"]) == 3 for group in result[0]["forecasts"]["groups"])
            assert not decoded_hours
            readback = True
        return result

    monkeypatch.setattr(runner, "_source_inputs", lambda: (guarded_observations, earlier_truth(),
        tutorial_observations(), tutorial_truth(), field(), None, {"synthetic": "d" * 64}, {}))
    monkeypatch.setattr(runner, "_load", load)
    result = runner.first_score(tmp_path)
    assert set(decoded_hours) == {5, 6}
    assert result["pipeline_saved_before_any05_06_position_decode"] is True
    assert result["pipeline_forecast_file_sha256"] == runner._sha((tmp_path / "pipeline-forecasts.json").read_bytes())
