"""Frozen deterministic free-runs on synthetic stored recording contracts."""

import copy
import runpy

import cv2
import numpy as np
import pytest

from apps.transport.reeftrace_transport.flow import FlowField
from apps.vision.reeftrace_vision import field_trajectory_diagnostic as diagnostic


@pytest.fixture
def stored():
    store = runpy.run_path("tests/unit/test_recorded_field_vectors.py")["stored"].__wrapped__()
    store.records["flow", "flow-test"]["provenance"]["validation_recording_ids"] = ["validation-near"]
    return store


def run(store):
    return diagnostic.inspect_recorded_flow_trajectories(store, "flow-test")


def test_mean_field_free_run_accumulates_error_without_observation_resets(stored):
    report = run(stored)
    assert report["status"] == "COMPLETED"
    assert report["data_origin"] == "SYNTHETIC_CAPTURE_REPLAY"
    assert report["coverage"] == {"validation_recordings": 1, "complete_recordings": 1,
        "planned_forecast_points": 5, "scored_forecast_points": 5, "withheld_forecast_points": 0}
    rows = report["recordings"][0]["comparisons"]
    assert [row["predicted_x_cm"] for row in rows] == pytest.approx([4.2, 4.4, 4.6, 4.8, 5])
    assert [row["position_error_cm"] for row in rows] == pytest.approx([.2, .4, .6, .8, 1])
    assert report["metrics"]["equal_recording_ade_cm"] == pytest.approx(.6)
    assert report["metrics"]["equal_recording_fde_cm"] == pytest.approx(1)
    assert report["metrics"]["pooled_position_rmse_cm"] == pytest.approx(np.sqrt(.44))
    assert report["model"]["observed_position_updates"] is False
    assert report["model"]["diffusivity_cm2_s"] == 0 and report["model"]["traps"] == "NONE"


def test_irregular_actual_saved_offsets_are_not_replaced_with_regular_timestamps(stored):
    points = stored.records["recording", "validation-near"]["points"]
    times = [5, 5.13, 5.3, 5.51, 5.79, 6]
    for point, timestamp in zip(points, times, strict=True):
        point.update(t_s=timestamp, x_cm=4 + 2 * (timestamp - 5))
    report = run(stored)
    result = report["recordings"][0]
    assert result["time_origin_s"] == 5
    assert [row["t_s"] for row in result["comparisons"]] == times[1:]
    assert [row["predicted_x_cm"] for row in result["comparisons"]] == pytest.approx(
        [4 + timestamp - 5 for timestamp in times[1:]])


def test_future_observed_coordinates_cannot_change_predicted_path_or_field_queries(stored, monkeypatch):
    original_evaluate = diagnostic.FlowField.evaluate
    queries = []
    def spy(field, points):
        queries.append(np.asarray(points).tolist())
        return original_evaluate(field, points)
    monkeypatch.setattr(diagnostic.FlowField, "evaluate", spy)
    first = run(stored)
    before = copy.deepcopy(queries)
    queries.clear()
    for point in stored.records["recording", "validation-near"]["points"][1:]:
        point["y_cm"] += 1
    changed = run(stored)
    assert queries == before
    assert first["metrics"] != changed["metrics"]
    assert [row["predicted_x_cm"] for row in first["recordings"][0]["comparisons"]] == [
        row["predicted_x_cm"] for row in changed["recordings"][0]["comparisons"]]


def test_all_recording_forecasts_exist_before_any_future_observation_is_scored(stored, monkeypatch):
    stored.records["flow", "flow-test"]["provenance"]["validation_recording_ids"].append("validation-far")
    stored.records["flow", "flow-test"]["coverage_radius_cm"] = 50
    forecast, coordinate = diagnostic._forecast, diagnostic._xy
    finished = []
    def forecast_spy(*args, **kwargs):
        result = forecast(*args, **kwargs)
        finished.append(True)
        return result
    def coordinate_spy(point):
        if point.get("observed") is True and point["t_s"] > 0:
            assert len(finished) == 2
        return coordinate(point)
    monkeypatch.setattr(diagnostic, "_forecast", forecast_spy)
    monkeypatch.setattr(diagnostic, "_xy", coordinate_spy)
    assert run(stored)["coverage"]["complete_recordings"] == 2


def test_wrong_direction_is_measured_as_a_larger_position_miss(stored):
    for node in stored.records["flow", "flow-test"]["nodes"]:
        node["vx_cm_s"] = -1
    report = run(stored)
    assert report["recordings"][0]["metrics"]["fde_cm"] == pytest.approx(3)


@pytest.mark.parametrize("change", ["missing", "track", "association", "long_gap"])
def test_gaps_withhold_the_whole_run_and_all_planned_denominators(stored, change):
    points = stored.records["recording", "validation-near"]["points"]
    if change == "missing":
        points[2]["observed"] = False
    elif change == "track":
        points[3]["track_id"] = "another-track"
    elif change == "association":
        points[3]["association_break"] = True
    else:
        for point in points[3:]:
            point["t_s"] += .4
    report = run(stored)
    assert report["status"] == "WITHHELD_INCOMPLETE_RUNS" and report["metrics"] is None
    assert report["coverage"]["planned_forecast_points"] == report["coverage"]["withheld_forecast_points"] == 5
    assert report["recordings"][0]["comparisons"] == []
    assert "MISSING_OR_BROKEN_TRACK" in report["recordings"][0]["reason_codes"]


def test_unsupported_future_forecast_withholds_whole_track_even_when_observed_points_are_supported(stored):
    field = stored.records["flow", "flow-test"]
    field["nodes"] = [{"x_cm": 4, "y_cm": 5, "vx_cm_s": 2, "vy_cm_s": 0}]
    field["coverage_radius_cm"] = .3
    for point in stored.records["recording", "validation-near"]["points"]:
        point["x_cm"] = 4
    report = run(stored)
    assert report["metrics"] is None
    assert "UNSUPPORTED_FORECAST_PATH" in report["recordings"][0]["reason_codes"]
    assert report["coverage"]["scored_forecast_points"] == 0


def test_unsupported_run_does_not_disappear_from_common_aggregate(stored):
    stored.records["flow", "flow-test"]["provenance"]["validation_recording_ids"].append("validation-far")
    report = run(stored)
    assert report["coverage"]["validation_recordings"] == 2
    assert report["coverage"]["complete_recordings"] == 1
    assert report["coverage"]["scored_forecast_points"] == 5
    assert report["coverage"]["withheld_forecast_points"] == 5
    assert report["metrics"] is None


def direct_field(nodes, radius):
    return FlowField({"kind": "idw", "bounds": {"x_min_cm": 0, "x_max_cm": 20,
        "y_min_cm": 0, "y_max_cm": 20}, "coverage_radius_cm": radius, "nodes": [
        {"x_cm": x, "y_cm": y, "vx_cm_s": vx, "vy_cm_s": vy}
        for x, y, vx, vy in nodes]})


def two_points(x, y, end_x=None):
    return [{"t_s": 0, "x_cm": x, "y_cm": y, "observed": True, "track_id": "one"},
            {"t_s": .05, "x_cm": x if end_x is None else end_x,
             "y_cm": y, "observed": True, "track_id": "one"}]


def test_supported_endpoints_cannot_hide_an_unsupported_segment_interior():
    field = direct_field([(1, 1, 100, 0), (6, 1, 100, 0)], .1)
    assert field.evaluate([[1, 1], [6, 1]])[1].all()
    assert not field.evaluate([[3.5, 1]])[1][0]
    predicted, reasons, _ = diagnostic._forecast(field, two_points(1, 1, 6))
    assert predicted is None and reasons == ["UNSUPPORTED_FORECAST_PATH"]


def test_zero_reflected_chord_cannot_hide_unsupported_out_and_back_wall_segments():
    field = direct_field([(19, 1, 40, 0)], .1)
    assert field.evaluate([[19, 1]])[1][0]
    assert diagnostic._segment_supported(field, [19, 1], [19, 1])
    predicted, reasons, _ = diagnostic._forecast(field, two_points(19, 1))
    assert predicted is None and reasons == ["UNSUPPORTED_FORECAST_PATH"]


def test_connected_overlapping_disks_support_the_whole_segment_without_a_single_covering_disk():
    field = direct_field([(1, 1, 6, 0), (1.15, 1, 6, 0), (1.3, 1, 6, 0)], .1)
    assert diagnostic._segment_supported(field, [1, 1], [1.3, 1])
    predicted, reasons, _ = diagnostic._forecast(field, two_points(1, 1, 1.3))
    assert not reasons and predicted[0]["x_cm"] == pytest.approx(1.3)


def test_continuously_supported_wall_reflection_remains_a_valid_mean_field_path():
    field = direct_field([(19, 1, 40, 0)], 1.1)
    predicted, reasons, _ = diagnostic._forecast(field, two_points(19, 1))
    assert not reasons and predicted[0]["x_cm"] == pytest.approx(19)


def test_diagonal_segment_and_narrow_support_gap_are_not_filled_by_tolerance():
    field = direct_field([(1, 1, 0, 0), (1.200001, 1, 0, 0)], .1)
    assert not diagnostic._segment_supported(field, [1, 1], [1.200001, 1])
    diagonal = direct_field([(1, 1, 0, 0), (1.2, 1.2, 0, 0)], .1)
    assert not diagnostic._segment_supported(diagonal, [1, 1], [1.2, 1.2])


def test_total_integration_budget_preserves_uncomputed_required_runs(stored, monkeypatch):
    stored.records["flow", "flow-test"]["provenance"]["validation_recording_ids"].append("validation-far")
    stored.records["flow", "flow-test"]["coverage_radius_cm"] = 50
    monkeypatch.setattr(diagnostic, "MAX_TOTAL_STEPS", 30)
    report = run(stored)
    assert report["integration"]["total_steps"] <= 30
    assert report["coverage"]["withheld_forecast_points"] == 5
    assert "TOTAL_INTEGRATION_BUDGET_EXCEEDED" in report["recordings"][1]["reason_codes"]


@pytest.mark.parametrize("change", ["missing_frame", "duplicate_id", "duplicate_frame", "mapping", "session", "time"])
def test_inconsistent_saved_provenance_is_rejected(stored, change):
    recording = stored.records["recording", "validation-near"]
    if change == "missing_frame":
        del stored.records["frame", "validation-near-frame-0"]
    elif change == "duplicate_id":
        stored.records["flow", "flow-test"]["provenance"]["validation_recording_ids"] *= 2
    elif change == "duplicate_frame":
        recording["evidence_frame_ids"][1] = recording["evidence_frame_ids"][0]
    elif change == "mapping":
        recording["calibration_id"] = "other-mapping"
    elif change == "session":
        recording["camera_session_id"] = "other-camera"
    else:
        recording["points"][2]["t_s"] = recording["points"][1]["t_s"]
    with pytest.raises((ValueError, KeyError)):
        run(stored)


def test_read_only_replay_is_deterministic_with_no_capture_refit_or_store_write(stored, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Read-only replay attempted camera, fitting or store write")
    monkeypatch.setattr(cv2, "VideoCapture", forbidden)
    monkeypatch.setattr("apps.transport.reeftrace_transport.flow.fit_flow", forbidden)
    stored.put = forbidden
    before = copy.deepcopy(stored.records)
    first = run(stored)
    assert first == run(stored) and stored.records == before
    for key in ("camera_started", "hardware_actuation", "provider_calls", "store_written",
                "refit_performed", "model_selection_performed", "independent_evaluation",
                "capture_independently_verified", "physical_validation", "calibrated_probability"):
        assert first[key] is False
