"""Mean-drift ablation arithmetic, cutoff isolation and legacy-output protection."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import ablation, benchmark
from apps.ocean.reeftrace_ocean.benchmark import ROOT, SAMPLE_NAME, SphericalLocalFrame
from apps.ocean.reeftrace_ocean.data import load_drifter_csv
from apps.ocean.reeftrace_ocean.diagnostics import run_training_diagnostic


def records():
    return load_drifter_csv(ROOT / "data/public" / SAMPLE_NAME)


def test_pinned_report_has_exact_fixed_contract_and_does_not_select_or_promote():
    report = ablation.run_motion_ablation()
    assert report == ablation.run_motion_ablation()
    assert report["schema_version"] == 1 and report["kind"] == "TRAINING_ONLY_MOTION_ABLATION"
    assert report["data_origin"] == "REAL_HISTORICAL_NOAA_DRIFTER"
    assert report["status"] == "COMPLETED"
    assert all(report[key] is False for key in ablation.FLAGS)
    assert report["split"]["training_count"] == 18
    assert report["split"]["prefix_counts"] == [8, 9, 10, 11, 12]
    assert report["split"]["origin_count"] == 5 and report["split"]["horizons"] == 6
    assert report["provenance"]["sha256"] == benchmark.SAMPLE_SHA256
    assert report["provenance"]["manifest_sha256"] == ablation.MANIFEST_SHA256
    assert report["provenance"]["integrity_verified"] is True
    assert report["provenance"]["row_count"] == 24
    assert [row["id"] for row in report["aggregates"]] == list(ablation.ABLATION_MODEL_IDS)
    assert [row["baseline_id"] for row in report["paired_comparisons"]] == list(ablation.BASELINE_IDS)
    for origin in report["origins"]:
        assert [model["id"] for model in origin["models"]] == list(ablation.ABLATION_MODEL_IDS)
        mean_model = origin["models"][2]
        assert mean_model["parameters"]["learned_parameters"] == 2
        assert len(mean_model["predictions"]) == 6
        assert mean_model["parameters"]["training_displacement_count"] == origin["prefix_count"] - 1
    assert "selected_model" not in report
    assert len(json.dumps(report, allow_nan=False).encode()) < 100_000


def test_mean_drift_forecasts_constant_velocity_and_stationary_prefix_without_mutation():
    moving = np.array([[0.0, 0.0], [2.0, 4.0], [4.0, 8.0]])
    before = moving.copy()
    forecast = ablation.mean_drift_forecast(moving, 3, 2.0)
    assert forecast == pytest.approx(np.array([[6.0, 12.0], [8.0, 16.0], [10.0, 20.0]]))
    assert np.array_equal(moving, before)
    stationary = np.repeat([[4.0, -3.0]], 8, axis=0)
    assert np.array_equal(ablation.mean_drift_forecast(stationary, 6, 3600), np.repeat([[4.0, -3.0]], 6, axis=0))
    # Average every prefix displacement, rather than repeating only the last one.
    uneven = [[0, 0], [1, 3], [6, 2]]
    assert ablation.mean_drift_forecast(uneven, 2, 3600) == pytest.approx(np.array([[9, 3], [12, 4]]))


@pytest.mark.parametrize("xy,steps,step_s", [
    ([[0, 0], [1, 1]], True, 1), ([[0, 0], [1, 1]], 1.0, 1),
    ([[0, 0], [1, 1]], 0, 1), ([[0, 0], [1, 1]], 7, 1),
    ([[0, 0], [1, 1]], 1, True), ([[0, 0], [1, 1]], 1, "1"),
    ([[0, 0], [1, 1]], 1, 0), ([[0, 0], [1, 1]], 1, float("inf")),
    ([[0, 0], [1, 1]], 1, float("nan")), ([[0, 0], [1, 1]], 1, 1 + 0j),
    ([[0, 0], [1, 1]], 1, 86401), ([[0, 0], [1, 1]], 1, 1e-320),
    ([], 1, 1), ([0, 1], 1, 1), ([[0, 0]], 1, 1), ([[0, 0, 0], [1, 1, 1]], 1, 1),
    ([[0, 0]] * 19, 1, 1), ([[0, 0], [True, 1]], 1, 1),
    ([[0, 0], ["1", 1]], 1, 1), ([[0, 0], [1 + 0j, 1]], 1, 1),
    ([[0, 0], [float("nan"), 1]], 1, 1), ([[0, 0], [1e308, 1]], 1, 1),
    ([[0, 0], [40000, 40000]], 1, 1), ([[0, 0], [30000, 0]], 1, 1),
])
def test_mean_drift_rejects_nonphysical_shapes_coercions_controls_and_overflow(xy, steps, step_s):
    with pytest.raises(ValueError):
        ablation.mean_drift_forecast(xy, steps, step_s)


def test_paired_summary_preserves_signed_arithmetic_losses_ties_and_zero_denominator():
    report = ablation.paired_error_summary([1, 4, 10], [1, 2, 3])
    assert report == {"count": 3, "mean_delta_m": 3.0, "median_delta_m": 2.0,
        "min_delta_m": 0.0, "max_delta_m": 7.0, "candidate_lower_error_count": 0,
        "equal_error_count": 1, "candidate_higher_error_count": 2,
        "skill_vs_baseline": -1.5, "reason_codes": []}
    mixed = ablation.paired_error_summary([1, 3, 5], [2, 3, 4])
    assert mixed["candidate_lower_error_count"] == mixed["equal_error_count"] == mixed["candidate_higher_error_count"] == 1
    assert mixed["mean_delta_m"] == mixed["skill_vs_baseline"] == 0
    for candidate in ([0, 0], [1, 2]):
        zero = ablation.paired_error_summary(candidate, [0, 0])
        assert zero["skill_vs_baseline"] is None
        assert zero["reason_codes"] == ["ZERO_BASELINE_ERROR"]
        json.dumps(zero, allow_nan=False)


@pytest.mark.parametrize("candidate,baseline", [
    ([], []), ([1], [1, 2]), ([[1]], [[1]]), ([True, 1], [1, 1]),
    (["1"], [1]), ([1 + 0j], [1]), ([-1], [1]), ([1], [-1]),
    ([float("nan")], [1]), ([1], [float("inf")]), ([1e308], [1]),
    ([1] * 101, [1] * 101), ([1], [1e-320]),
])
def test_paired_summary_rejects_invalid_shapes_coercions_and_nonfinite_arithmetic(candidate, baseline):
    with pytest.raises(ValueError):
        ablation.paired_error_summary(candidate, baseline)


def test_report_aggregates_and_pairs_reconstruct_exactly_from_aligned_origin_errors():
    report = ablation.training_motion_ablation(records())
    errors = {(model["id"], horizon): [next(m for m in origin["models"] if m["id"] == model["id"])
        ["predictions"][horizon - 1]["error_m"] for origin in report["origins"]]
        for model in report["aggregates"] for horizon in range(1, 7)}
    for model in report["aggregates"]:
        for row in model["per_horizon"]:
            values = np.array(errors[model["id"], row["horizon_hours"]])
            assert row["count"] == 5
            assert row["mean_error_m"] == pytest.approx(np.mean(values))
            assert row["median_error_m"] == pytest.approx(np.median(values))
            assert row["min_error_m"] == pytest.approx(np.min(values))
            assert row["max_error_m"] == pytest.approx(np.max(values))
            assert row["rmse_error_m"] == pytest.approx(np.sqrt(np.mean(values ** 2)))
    for pair in report["paired_comparisons"]:
        assert pair["candidate_id"] == "ridge_ar1"
        assert pair["delta_definition"] == "candidate_minus_baseline_error_m"
        for row in pair["per_horizon"]:
            h = row["horizon_hours"]
            expected = ablation.paired_error_summary(errors["ridge_ar1", h], errors[pair["baseline_id"], h])
            assert row == {"horizon_hours": h, **expected}
    # Never make success conditional on the learned model winning.
    assert any(row["candidate_higher_error_count"] > 0
               for pair in report["paired_comparisons"] for row in pair["per_horizon"])


class _HeldoutSentinel:
    def __getattribute__(self, name):
        raise AssertionError("A record after training_count was accessed")


def test_cutoff_sentinels_prove_positions_and_metadata_after_eighteen_are_not_read():
    guarded = records()[:18] + [_HeldoutSentinel() for _ in range(6)]
    report = ablation.training_motion_ablation(guarded)
    assert report["split"]["training_count"] == 18
    assert report["origins"][-1]["models"][-1]["predictions"][-1]["time_utc"] == "1987-10-03T17:00:00Z"


def test_all_four_forecasts_precede_later_truth_projection_for_every_origin(monkeypatch):
    original = records()
    events = []
    to_xy = SphericalLocalFrame.to_xy
    legacy = ablation._forecast
    mean = ablation.mean_drift_forecast

    def observed_xy(self, lat, lon):
        events.append(("xy", lat, lon))
        return to_xy(self, lat, lon)

    def observed_legacy(xy, steps, step_s, model_id):
        events.append(("forecast", model_id, len(xy)))
        return legacy(xy, steps, step_s, model_id)

    def observed_mean(xy, steps, step_s):
        events.append(("forecast", "mean_drift", len(xy)))
        return mean(xy, steps, step_s)

    monkeypatch.setattr(SphericalLocalFrame, "to_xy", observed_xy)
    monkeypatch.setattr(ablation, "_forecast", observed_legacy)
    monkeypatch.setattr(ablation, "mean_drift_forecast", observed_mean)
    ablation.training_motion_ablation(original)
    for prefix in range(8, 13):
        indices = [i for i, event in enumerate(events) if event[0] == "forecast" and event[2] == prefix]
        assert [events[i][1] for i in indices] == list(ablation.ABLATION_MODEL_IDS)
        assert indices == list(range(indices[0], indices[0] + 4))
        expected_truth = original[prefix]
        assert events[indices[-1] + 1] == ("xy", expected_truth.latitude_deg, expected_truth.longitude_deg)
    first = next(i for i, event in enumerate(events) if event[0] == "forecast")
    assert events[:first] == [("xy", row.latitude_deg, row.longitude_deg) for row in original[:8]]


def test_later_training_truth_changes_scores_without_changing_earlier_predictions():
    original = records()
    changed = original.copy()
    changed[16] = replace(changed[16], latitude_deg=changed[16].latitude_deg + 0.03)
    first = ablation.training_motion_ablation(original)
    second = ablation.training_motion_ablation(changed)
    for a, b in zip(first["origins"], second["origins"], strict=True):
        for model_a, model_b in zip(a["models"], b["models"], strict=True):
            assert model_a["parameters"] == model_b["parameters"]
            for point_a, point_b in zip(model_a["predictions"], model_b["predictions"], strict=True):
                assert point_a["latitude_deg"] == point_b["latitude_deg"]
                assert point_a["longitude_deg"] == point_b["longitude_deg"]
    assert first["aggregates"] != second["aggregates"]
    assert first["paired_comparisons"] != second["paired_comparisons"]


def test_unused_noaa_velocities_do_not_change_predictions_or_pairs():
    original = records()
    changed = [replace(row, eastward_m_s=100, northward_m_s=-100,
                       eastward_uncertainty_m_s=50, northward_uncertainty_m_s=50) for row in original]
    assert ablation.training_motion_ablation(original) == ablation.training_motion_ablation(changed)


@pytest.mark.parametrize("kwargs", [
    {"horizons": True}, {"horizons": 6.0}, {"horizons": 0}, {"horizons": 7},
    {"training_count": False}, {"training_count": 18.0}, {"training_count": 19},
    {"training_count": 13}, {"min_prefix": 7}, {"min_prefix": True}, {"min_prefix": 8.0},
])
def test_training_controls_are_strict_and_bounded(kwargs):
    with pytest.raises(ValueError):
        ablation.training_motion_ablation(records(), **kwargs)


def _copy_pinned_public_files(tmp_path):
    destination = tmp_path / "data/public"
    destination.mkdir(parents=True)
    source = ROOT / "data/public" / SAMPLE_NAME
    target = destination / SAMPLE_NAME
    target.write_bytes(source.read_bytes())
    target.with_suffix(".provenance.json").write_bytes(source.with_suffix(".provenance.json").read_bytes())
    return target


@pytest.mark.parametrize("tamper", ["csv", "manifest"])
def test_runner_rejects_changed_csv_or_provenance_even_with_matching_recomputed_local_hash(tmp_path, monkeypatch, tamper):
    import hashlib

    target = _copy_pinned_public_files(tmp_path)
    manifest_path = target.with_suffix(".provenance.json")
    manifest = json.loads(manifest_path.read_text())
    if tamper == "csv":
        data = target.read_bytes().replace(b"-0.0736", b"-0.0735", 1)
        assert data != target.read_bytes()
        target.write_bytes(data)
        manifest["sha256"] = hashlib.sha256(data).hexdigest()
    else:
        manifest["attribution"] = "Changed public fixture metadata"
    manifest_path.write_text(json.dumps(manifest))
    monkeypatch.setattr(ablation, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="hash"):
        ablation.run_motion_ablation()


def test_runner_uses_the_single_verified_payload_and_never_runs_heldout_benchmark(tmp_path, monkeypatch):
    expected = ablation.run_motion_ablation()
    target = _copy_pinned_public_files(tmp_path)
    original_parse, original_open = ablation.parse_drifter_csv, Path.open
    reads = []

    def tracked_open(path, mode="r", *args, **kwargs):
        if path == target and mode == "rb":
            reads.append(path)
        return original_open(path, mode, *args, **kwargs)

    def replace_after_verified_read(text):
        target.write_bytes(b"changed after the pinned payload was read")
        return original_parse(text)

    def forbidden(*args, **kwargs):
        raise AssertionError("Ablation attempted to run the heldout benchmark")

    monkeypatch.setattr(ablation, "ROOT", tmp_path)
    monkeypatch.setattr(Path, "open", tracked_open)
    monkeypatch.setattr(ablation, "parse_drifter_csv", replace_after_verified_read)
    monkeypatch.setattr(benchmark, "run_real_data_example", forbidden)
    assert ablation.run_motion_ablation() == expected
    assert len(reads) == 1


def test_legacy_three_model_diagnostic_and_eighteen_six_benchmark_remain_byte_identical():
    benchmark_before = json.dumps(benchmark.run_real_data_example(), sort_keys=True, allow_nan=False)
    diagnostic_before = json.dumps(run_training_diagnostic(), sort_keys=True, allow_nan=False)
    ablation.run_motion_ablation()
    assert json.dumps(benchmark.run_real_data_example(), sort_keys=True, allow_nan=False) == benchmark_before
    assert json.dumps(run_training_diagnostic(), sort_keys=True, allow_nan=False) == diagnostic_before
    assert benchmark.MODEL_IDS == ("stationary", "last_drift", "ridge_ar1")
