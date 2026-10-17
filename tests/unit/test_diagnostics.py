"""Training-origin diagnostic: schema, leakage isolation, validation and frozen 18/6 output."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import benchmark as benchmark_module
from apps.ocean.reeftrace_ocean import diagnostics as diagnostics_module
from apps.ocean.reeftrace_ocean.benchmark import (
    ROOT,
    SAMPLE_NAME,
    SphericalLocalFrame,
    benchmark_drifter_records,
    run_real_data_example,
)
from apps.ocean.reeftrace_ocean.data import load_drifter_csv
from apps.ocean.reeftrace_ocean.diagnostics import (
    run_training_diagnostic,
    training_origin_diagnostic,
)


def records():
    return load_drifter_csv(ROOT / "data/public" / SAMPLE_NAME)


class _HeldoutSentinel:
    def __getattribute__(self, name):
        raise AssertionError("record after training_count was accessed")


def test_default_schema_and_origin_count():
    report = run_training_diagnostic()
    assert report["kind"] == "TRAINING_ONLY_RETROSPECTIVE_DIAGNOSTIC"
    assert report["test_data_used"] is False
    assert report["model_selection_performed"] is False
    assert report["split"]["test_data_used"] is False
    assert report["split"]["model_selection_performed"] is False
    assert report["split"]["prefix_counts"] == [8, 9, 10, 11, 12]
    assert report["split"]["origin_count"] == 5
    assert report["split"]["training_count"] == 18
    assert report["split"]["horizons"] == 6
    assert [origin["prefix_count"] for origin in report["origins"]] == [8, 9, 10, 11, 12]
    assert len(report["origins"]) == 5
    assert {model["id"] for model in report["origins"][0]["models"]} == {
        "stationary",
        "last_drift",
        "ridge_ar1",
    }
    for origin in report["origins"]:
        assert origin["models"][0]["predictions"][0]["horizon_hours"] == 1
        assert origin["models"][0]["predictions"][-1]["horizon_hours"] == 6
        assert len(origin["models"]) == 3
        for model in origin["models"]:
            assert len(model["predictions"]) == 6
    assert report["provenance"]["integrity_verified"] is True
    assert "selected_model" not in report
    json.dumps(report, allow_nan=False)


def test_reconstruct_aggregate_metrics_from_origin_errors():
    report = training_origin_diagnostic(records())
    for model in report["aggregates"]:
        for row in model["per_horizon"]:
            errors = []
            stationary = []
            for origin in report["origins"]:
                predicted = next(item for item in origin["models"] if item["id"] == model["id"])
                baseline = next(item for item in origin["models"] if item["id"] == "stationary")
                errors.append(
                    next(
                        point["error_m"]
                        for point in predicted["predictions"]
                        if point["horizon_hours"] == row["horizon_hours"]
                    )
                )
                stationary.append(
                    next(
                        point["error_m"]
                        for point in baseline["predictions"]
                        if point["horizon_hours"] == row["horizon_hours"]
                    )
                )
            assert row["count"] == 5
            assert row["mean_error_m"] == pytest.approx(float(np.mean(errors)))
            assert row["rmse_error_m"] == pytest.approx(
                float(np.sqrt(np.mean(np.square(errors))))
            )
            assert row["max_error_m"] == pytest.approx(float(np.max(errors)))
            assert row["per_horizon_error_lower_than_stationary_count"] == sum(
                error < base for error, base in zip(errors, stationary, strict=True)
            )
    stationary_counts = next(
        model for model in report["aggregates"] if model["id"] == "stationary"
    )
    assert all(
        row["per_horizon_error_lower_than_stationary_count"] == 0
        for row in stationary_counts["per_horizon"]
    )


def test_later_training_positions_are_not_projected_before_prefix_forecasts(monkeypatch):
    original = records()
    prefix_coords = {(row.latitude_deg, row.longitude_deg) for row in original[:8]}
    later_coords = {(row.latitude_deg, row.longitude_deg) for row in original[8:18]}
    events = []
    original_to_xy = SphericalLocalFrame.to_xy
    original_forecast = diagnostics_module._forecast

    def to_xy(self, latitude_deg, longitude_deg):
        events.append(("xy", latitude_deg, longitude_deg))
        return original_to_xy(self, latitude_deg, longitude_deg)

    def forecast(training_xy, steps, step_s, model):
        events.append(("forecast", model, len(training_xy)))
        return original_forecast(training_xy, steps, step_s, model)

    monkeypatch.setattr(SphericalLocalFrame, "to_xy", to_xy)
    monkeypatch.setattr(diagnostics_module, "_forecast", forecast)
    training_origin_diagnostic(original)
    first_forecast = next(index for index, event in enumerate(events) if event[0] == "forecast")
    for event in events[:first_forecast]:
        assert event[0] == "xy"
        assert (event[1], event[2]) in prefix_coords
        assert (event[1], event[2]) not in later_coords
    first_later = next(
        index
        for index, event in enumerate(events)
        if event[0] == "xy" and (event[1], event[2]) in later_coords
    )
    assert [
        event[1] for event in events[:first_later] if event[0] == "forecast"
    ] == ["stationary", "last_drift", "ridge_ar1"]
    assert events[first_forecast][2] == 8


def test_entrypoint_rejects_tampered_csv_even_with_changed_manifest(tmp_path, monkeypatch):
    import hashlib
    target = tmp_path / "data/public"
    target.mkdir(parents=True)
    original = ROOT / "data/public" / SAMPLE_NAME
    csv_path = target / SAMPLE_NAME
    payload = original.read_bytes().replace(b"-0.0736", b"-0.0735", 1)
    csv_path.write_bytes(payload)
    manifest = json.loads(original.with_suffix(".provenance.json").read_text(encoding="utf-8"))
    manifest["sha256"] = hashlib.sha256(payload).hexdigest()
    csv_path.with_suffix(".provenance.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(diagnostics_module, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="hash"):
        run_training_diagnostic()


def test_entrypoint_does_not_run_the_heldout_benchmark(monkeypatch):
    def forbidden():
        raise AssertionError("The training-only entrypoint ran the full heldout benchmark")

    monkeypatch.setattr(benchmark_module, "run_real_data_example", forbidden)
    original_forecast = diagnostics_module._forecast
    prefix_lengths = []

    def prefix_only(training_xy, steps, step_s, model):
        prefix_lengths.append(len(training_xy))
        assert len(training_xy) <= 12
        return original_forecast(training_xy, steps, step_s, model)

    monkeypatch.setattr(diagnostics_module, "_forecast", prefix_only)
    result = run_training_diagnostic()
    assert prefix_lengths == [n for n in range(8, 13) for _ in range(3)]
    assert result["split"]["test_data_used"] is False


def test_sentinel_heldout_objects_are_never_accessed_after_training_count():
    guarded = records()[:18] + [_HeldoutSentinel() for _ in range(6)]
    report = training_origin_diagnostic(guarded)
    assert report["split"]["training_count"] == 18
    last_truth = report["origins"][-1]["models"][0]["predictions"][-1]["time_utc"]
    assert last_truth == "1987-10-03T17:00:00Z"


def test_later_training_truth_does_not_change_earlier_predictions():
    original = records()
    mutated = original.copy()
    mutated[16] = replace(
        mutated[16],
        latitude_deg=mutated[16].latitude_deg + 0.04,
        longitude_deg=mutated[16].longitude_deg - 0.03,
    )
    baseline = training_origin_diagnostic(original)
    alternative = training_origin_diagnostic(mutated)
    for first, second in zip(baseline["origins"], alternative["origins"], strict=True):
        assert first["prefix_count"] == second["prefix_count"]
        for model_a, model_b in zip(first["models"], second["models"], strict=True):
            for point_a, point_b in zip(model_a["predictions"], model_b["predictions"], strict=True):
                assert point_a["latitude_deg"] == point_b["latitude_deg"]
                assert point_a["longitude_deg"] == point_b["longitude_deg"]
    assert alternative["aggregates"] != baseline["aggregates"]


def test_published_velocity_columns_are_irrelevant_to_the_diagnostic():
    original = records()
    changed = [
        replace(
            row,
            eastward_m_s=1000 + index,
            northward_m_s=-999 - index,
            eastward_uncertainty_m_s=500,
            northward_uncertainty_m_s=500,
        )
        for index, row in enumerate(original)
    ]
    baseline = training_origin_diagnostic(original)
    alternative = training_origin_diagnostic(changed)
    assert alternative["origins"] == baseline["origins"]
    assert alternative["aggregates"] == baseline["aggregates"]


def test_rejects_bool_float_bounds_nonfinite_non_utc_cadence_and_multiple_drifters():
    original = records()
    with pytest.raises(ValueError, match="explicit Python int"):
        training_origin_diagnostic(original, horizons=True)
    with pytest.raises(ValueError, match="explicit Python int"):
        training_origin_diagnostic(original, training_count=18.0)
    with pytest.raises(ValueError, match="explicit Python int"):
        training_origin_diagnostic(original, min_prefix=False)
    with pytest.raises(ValueError, match="horizons"):
        training_origin_diagnostic(original, horizons=0)
    with pytest.raises(ValueError, match="horizons"):
        training_origin_diagnostic(original, horizons=7)
    with pytest.raises(ValueError, match="min_prefix"):
        training_origin_diagnostic(original, min_prefix=7)
    with pytest.raises(ValueError, match="training_count"):
        training_origin_diagnostic(original, training_count=13, min_prefix=8, horizons=6)
    with pytest.raises(ValueError, match="training_count"):
        training_origin_diagnostic(original, training_count=19)
    with pytest.raises(ValueError, match="enough records"):
        training_origin_diagnostic(original[:17])
    with pytest.raises(ValueError, match="<=100"):
        training_origin_diagnostic(original * 5)
    nonfinite = original.copy()
    nonfinite[3] = replace(nonfinite[3], latitude_deg=float("nan"))
    with pytest.raises(ValueError, match="Finite"):
        training_origin_diagnostic(nonfinite)
    naive = original.copy()
    naive[2] = replace(naive[2], time_utc=naive[2].time_utc.replace(tzinfo=None))
    with pytest.raises(ValueError, match="UTC"):
        training_origin_diagnostic(naive)
    offset = original.copy()
    offset[2] = replace(
        offset[2],
        time_utc=datetime(1987, 10, 3, 2, tzinfo=timezone(timedelta(hours=-8))),
    )
    with pytest.raises(ValueError, match="UTC"):
        training_origin_diagnostic(offset)
    irregular = original.copy()
    irregular[4] = replace(irregular[4], time_utc=irregular[4].time_utc + timedelta(minutes=1))
    with pytest.raises(ValueError, match="hourly"):
        training_origin_diagnostic(irregular)
    two_ids = original.copy()
    two_ids[5] = replace(two_ids[5], drifter_id="another-buoy")
    with pytest.raises(ValueError, match="one drifter"):
        training_origin_diagnostic(two_ids)


def test_existing_eighteen_six_benchmark_output_is_unchanged():
    before = run_real_data_example()
    before_json = json.dumps(before, allow_nan=False, sort_keys=True)
    before_split = benchmark_drifter_records(records())
    training_origin_diagnostic(records())
    run_training_diagnostic()
    after = run_real_data_example()
    after_split = benchmark_drifter_records(records())
    assert json.dumps(after, allow_nan=False, sort_keys=True) == before_json
    assert json.dumps(after_split, allow_nan=False, sort_keys=True) == json.dumps(
        before_split, allow_nan=False, sort_keys=True
    )
    persistence, last_drift, learned = after["models"]
    assert persistence["metrics"]["mean_error_m"] == pytest.approx(3855.003585, abs=0.01)
    assert last_drift["metrics"]["mae_skill_vs_stationary"] < 0
    assert learned["metrics"]["endpoint_error_m"] > persistence["metrics"]["endpoint_error_m"]
    assert after["split"]["training_count"] == 18
    assert after["split"]["heldout_count"] == 6
