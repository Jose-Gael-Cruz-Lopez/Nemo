"""Vector units, free-running anchors, aligned scoring and provenance boundaries."""

from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import benchmark
from apps.ocean.reeftrace_ocean import vector_diagnostics as vectors


def fixture():
    return benchmark.run_real_data_example()


def test_pinned_report_keeps_exact_denominators_and_no_authority_escalation():
    report = vectors.run_noaa_vector_diagnostic()
    assert report == vectors.run_noaa_vector_diagnostic()
    assert report["coverage"] == {"physical_drifters": 1, "models": 3,
        "intervals_per_model": 6, "attempted_model_intervals": 18,
        "scored_model_intervals": 18, "failed_model_intervals": 0,
        "unique_observed_intervals": 6}
    for key in ("field_forcing_available", "debris_survey_context_available", "independent_evaluation",
                "model_selection_performed", "automatic_model_promotion", "physical_validation",
                "calibrated_probability", "plastic_source_attribution_supported", "new_trajectory_acquisition"):
        assert report[key] is False
    assert report["provenance"]["sha256"] == benchmark.SAMPLE_SHA256
    stationary = report["models"][0]
    assert stationary["metrics"]["angular_mae_deg"] is None
    assert stationary["metrics"]["angular_withheld_count"] == 6
    assert all(row["predicted_velocity"]["heading_deg_clockwise_from_north"] is None
               for row in stationary["intervals"])


def test_known_eastward_motion_uses_metres_per_second_and_previous_forecasts():
    source = fixture()
    frame = benchmark.SphericalLocalFrame(0, 0)
    source["coordinate_system"].update(origin_latitude_deg=0, origin_longitude_deg=0)
    anchor_lat, anchor_lon = frame.to_latlon([0, 0])
    source["training_track"][-1].update(latitude_deg=anchor_lat, longitude_deg=anchor_lon)
    for index in range(6):
        lat, lon = frame.to_latlon([3600 * (index + 1), 0])
        source["heldout_track"][index].update(latitude_deg=lat, longitude_deg=lon)
        for model in source["models"]:
            lat, lon = frame.to_latlon([1800 * (index + 1), 0])
            model["predictions"][index].update(latitude_deg=lat, longitude_deg=lon)
    report = vectors.vector_diagnostic_from_benchmark(source)
    for model in report["models"]:
        assert model["metrics"]["vector_rmse_m_s"] == pytest.approx(0.5)
        assert model["metrics"]["speed_bias_predicted_minus_observed_m_s"] == pytest.approx(-0.5)
        assert model["metrics"]["angular_mae_deg"] == pytest.approx(0)
        for row in model["intervals"]:
            assert row["observed_velocity"]["eastward_m_s"] == pytest.approx(1)
            assert row["predicted_velocity"]["eastward_m_s"] == pytest.approx(0.5)
            assert row["predicted_velocity"]["northward_m_s"] == pytest.approx(0)
            assert row["predicted_velocity"]["heading_deg_clockwise_from_north"] == pytest.approx(90)


def test_future_truth_changes_only_scoring_not_predicted_velocities_or_input():
    original = fixture()
    before = deepcopy(original)
    initial = vectors.vector_diagnostic_from_benchmark(original)
    assert original == before
    changed = deepcopy(original)
    for row in changed["heldout_track"]:
        row["latitude_deg"] += 0.005
    altered = vectors.vector_diagnostic_from_benchmark(changed)
    assert initial["models"][2]["metrics"] != altered["models"][2]["metrics"]
    for left, right in zip(initial["models"], altered["models"], strict=True):
        assert [row["predicted_velocity"] for row in left["intervals"]] == [
            row["predicted_velocity"] for row in right["intervals"]]


def test_all_forecasts_validated_before_future_coordinates(monkeypatch):
    source = fixture()
    events = []
    original = vectors._coordinate
    ids = {id(point): "prediction" for model in source["models"] for point in model["predictions"]}
    ids.update({id(point): "truth" for point in source["heldout_track"]})
    def spy(point):
        events.append(ids.get(id(point), "anchor"))
        return original(point)
    monkeypatch.setattr(vectors, "_coordinate", spy)
    vectors.vector_diagnostic_from_benchmark(source)
    assert events[:events.index("truth")].count("prediction") == 18


def test_position_metrics_match_same_benchmark_and_vector_rmse_reconstructs():
    source = fixture()
    report = vectors.vector_diagnostic_from_benchmark(source)
    for model, legacy in zip(report["models"], source["models"], strict=True):
        assert model["metrics"]["ade_m"] == pytest.approx(legacy["metrics"]["mean_error_m"])
        assert model["metrics"]["fde_m"] == pytest.approx(legacy["metrics"]["endpoint_error_m"])
        residuals = [[row["residual_predicted_minus_observed"][key] for key in
                      ("eastward_m_s", "northward_m_s")] for row in model["intervals"]]
        assert model["metrics"]["vector_rmse_m_s"] == pytest.approx(np.sqrt(np.mean(np.sum(np.square(residuals), axis=1))))


def test_heading_threshold_and_compass_convention_are_explicit():
    assert vectors._vector([0, 0])["heading_deg_clockwise_from_north"] is None
    assert vectors._vector([0.0049, 0])["heading_deg_clockwise_from_north"] is None
    assert vectors._vector([0.005, 0])["heading_deg_clockwise_from_north"] == 90
    assert vectors._vector([0, 1])["heading_deg_clockwise_from_north"] == 0
    assert vectors._vector([-1, 0])["heading_deg_clockwise_from_north"] == 270
    assert vectors._vector([0, -1])["heading_deg_clockwise_from_north"] == 180


@pytest.mark.parametrize("mutation", ["future_time", "naive_time", "nan_prediction", "missing_model"])
def test_misaligned_nonfinite_or_incomplete_inputs_fail_closed(mutation):
    source = fixture()
    if mutation == "future_time":
        source["heldout_track"][2]["time_utc"] = source["heldout_track"][1]["time_utc"]
    elif mutation == "naive_time":
        source["models"][0]["predictions"][0]["time_utc"] = "1987-10-03T18:00:00"
    elif mutation == "nan_prediction":
        source["models"][1]["predictions"][3]["latitude_deg"] = float("nan")
    else:
        source["models"].pop()
    with pytest.raises(ValueError):
        vectors.vector_diagnostic_from_benchmark(source)


def cohort_fixture():
    study = vectors.run_multidrifter_study()
    _, _, manifest, raw, _ = vectors.load_multidrifter_inputs()
    records = {entry["drifter_id"]: vectors.parse_drifter_csv(raw[entry["raw_path"]].decode())
               for entry in manifest["trajectories"]}
    return study, records


def test_real_cohort_retains_partial_acquisition_and_exact_vector_denominators():
    report = vectors.run_noaa_cohort_vector_diagnostic()
    assert report["status"] == "PARTIAL_COVERAGE"
    assert report["coverage"] == {"target_drifters": 6, "acquired_drifters": 4,
        "missing_drifters": 2, "models": 4, "model_tracks": 16, "intervals_per_track": 6,
        "planned_model_intervals": 144, "attempted_model_intervals": 96,
        "scored_model_intervals": 96, "failed_model_intervals": 0,
        "unique_observed_intervals": 24, "common_acquired_cohort_complete": True}
    assert len(report["selection_failures"]) == 1
    assert report["provenance"]["integrity_verified"] is True
    assert all(report[key] is False for key in ("new_trajectory_acquisition", "independent_evaluation",
        "model_selection_performed", "automatic_model_promotion", "field_forcing_available",
        "debris_survey_context_available", "plastic_source_attribution_supported", "physical_validation"))


def test_real_cohort_replay_is_deterministic_and_preserves_benchmark_position_metrics():
    study, records = cohort_fixture()
    report = vectors.cohort_vector_diagnostic_from_inputs(study, records)
    assert report == vectors.run_noaa_cohort_vector_diagnostic()
    for actual, legacy in zip(report["models"], study["models"], strict=True):
        assert actual["metrics"]["ade_m"] == pytest.approx(legacy["macro"]["mean_trajectory_error_m"])


def test_real_cohort_has_four_free_running_six_interval_tracks_per_drifter():
    report = vectors.run_noaa_cohort_vector_diagnostic()
    for group in report["groups"]:
        assert len(group["models"]) == 4
        for model in group["models"]:
            assert len(model["intervals"]) == 6
            for previous, row in zip(model["intervals"], model["intervals"][1:], strict=False):
                assert row["predicted_start"] == previous["predicted_end"]
                assert row["observed_start"] == previous["observed_end"]
                assert row["interval_seconds"] == 3600


def test_real_cohort_macro_rmse_uses_equal_drifter_squared_errors_and_heading_denominators():
    report = vectors.run_noaa_cohort_vector_diagnostic()
    for model in report["models"]:
        tracks = [next(row for row in group["models"] if row["id"] == model["id"])
                  for group in report["groups"]]
        expected = np.sqrt(np.mean([row["metrics"]["vector_rmse_m_s"] ** 2 for row in tracks]))
        assert model["metrics"]["vector_rmse_m_s"] == pytest.approx(expected)
        assert model["metrics"]["angular_scored_count"] + model["metrics"]["angular_withheld_count"] == 24


def test_cohort_future_truth_changes_scoring_without_changing_any_forecast_vector_or_input():
    study, records = cohort_fixture()
    before = deepcopy(study)
    initial = vectors.cohort_vector_diagnostic_from_inputs(study, records)
    altered = {value: rows[:18] + [replace(row, latitude_deg=row.latitude_deg + .002)
                                   for row in rows[18:]] for value, rows in records.items()}
    result = vectors.cohort_vector_diagnostic_from_inputs(study, altered)
    assert before == study
    assert initial["models"][3]["metrics"] != result["models"][3]["metrics"]
    for first, second in zip(initial["groups"], result["groups"], strict=True):
        for left, right in zip(first["models"], second["models"], strict=True):
            assert [row["predicted_velocity"] for row in left["intervals"]] == [
                row["predicted_velocity"] for row in right["intervals"]]


def test_all_ninety_six_forecasts_checked_before_any_heldout_coordinate_read(monkeypatch):
    study, records = cohort_fixture()
    forecasts, seen = {id(row) for row in study["outcomes"]}, set()
    truth = {id(row) for rows in records.values() for row in rows[18:]}
    coordinate, public = vectors._coordinate, vectors._public_point
    def coordinate_spy(row):
        if id(row) in forecasts:
            seen.add(id(row))
        return coordinate(row)
    def public_spy(row):
        if id(row) in truth:
            assert len(seen) == 96
        return public(row)
    monkeypatch.setattr(vectors, "_coordinate", coordinate_spy)
    monkeypatch.setattr(vectors, "_public_point", public_spy)
    vectors.cohort_vector_diagnostic_from_inputs(study, records)


def test_cohort_known_motion_exposes_metre_second_conversion_and_recomputes_errors():
    study, records = cohort_fixture()
    frame = benchmark.SphericalLocalFrame(0, 0)
    for value, rows in records.items():
        records[value] = [replace(row, latitude_deg=frame.to_latlon([index * 360, 0])[0],
                                 longitude_deg=frame.to_latlon([index * 360, 0])[1])
                          for index, row in enumerate(rows)]
    for row in study["outcomes"]:
        lat, lon = frame.to_latlon([17 * 360 + row["horizon_hours"] * 180, 0])
        row.update(latitude_deg=lat, longitude_deg=lon)
    report = vectors.cohort_vector_diagnostic_from_inputs(study, records)
    for model in report["models"]:
        assert model["metrics"]["vector_rmse_m_s"] == pytest.approx(.05)
        assert model["metrics"]["speed_bias_predicted_minus_observed_m_s"] == pytest.approx(-.05)
        assert model["metrics"]["ade_m"] == pytest.approx(630)
        assert model["metrics"]["fde_m"] == pytest.approx(1080)


def test_cohort_incomplete_forecast_track_stays_visible_and_withholds_common_metrics():
    study, records = cohort_fixture()
    study["outcomes"][1].update(status="FAILED", error_m=None, latitude_deg=None,
                                 longitude_deg=None, reason_codes=["MODEL_FORECAST_FAILED"])
    report = vectors.cohort_vector_diagnostic_from_inputs(study, records)
    assert report["coverage"]["scored_model_intervals"] == 90
    assert report["coverage"]["failed_model_intervals"] == 6
    assert report["coverage"]["common_acquired_cohort_complete"] is False
    assert all(model["metrics"] is None for model in report["models"])
    track = report["groups"][0]["models"][0]
    assert len(track["intervals"]) == 6 and track["metrics"] is None
    assert "INCOMPLETE_FORECAST_TRACK" in track["reason_codes"]


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "model", "time", "truth_time", "identity"])
def test_cohort_rejects_missing_duplicate_mismatched_or_out_of_order_inputs(mutation):
    study, records = cohort_fixture()
    if mutation == "missing":
        study["outcomes"].pop()
    elif mutation == "duplicate":
        study["outcomes"][-1] = study["outcomes"][0]
    elif mutation == "model":
        study["outcomes"][0]["model_id"] = "unregistered"
    elif mutation == "time":
        study["outcomes"][0]["time_utc"] = study["outcomes"][1]["time_utc"]
    elif mutation == "truth_time":
        value = next(iter(records))
        records[value][19] = replace(records[value][19], time_utc=records[value][18].time_utc)
    else:
        value = next(iter(records))
        records[value][23] = replace(records[value][23], drifter_id="unknown")
    with pytest.raises(ValueError):
        vectors.cohort_vector_diagnostic_from_inputs(study, records)
