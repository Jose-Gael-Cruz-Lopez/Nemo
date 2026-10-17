"""Frozen real-data replay plus explicitly synthetic policy/physics regressions."""

from __future__ import annotations

import copy
import csv
import io
import itertools
import json
import shutil
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import httpx
import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import benchmark, multidrifter
from apps.ocean.reeftrace_ocean.ablation import ABLATION_MODEL_IDS, run_motion_ablation
from apps.ocean.reeftrace_ocean.data import DrifterRecord
from apps.ocean.reeftrace_ocean.diagnostics import run_training_diagnostic
from scripts import fetch_multidrifter_study as acquisition


def synthetic_group():
    return {"drifter_id": "900000001", "block_id": "synthetic-policy-fixture",
            "start_utc": "2001-01-01T00:00:00Z", "end_utc": "2001-01-01T23:00:00Z"}


def synthetic_records():
    start = datetime(2001, 1, 1, tzinfo=UTC)
    return [DrifterRecord("900000001", start + timedelta(hours=i), 10 + i * 0.001, 20 + i * 0.002,
                          0.0, 0.0, 0.0, 0.0) for i in range(24)]


def test_pinned_report_preserves_partial_sampling_coverage_and_complete_acquired_matrix():
    report = multidrifter.run_multidrifter_study()
    assert report == multidrifter.run_multidrifter_study()
    assert report["kind"] == "MULTI_DRIFTER_RETROSPECTIVE_STUDY"
    assert report["status"] == "PARTIAL_COVERAGE"
    assert report["data_origin"] == "REAL_HISTORICAL_NOAA_DRIFTERS"
    assert report["test_data_used"] is True
    for flag in ("physical_validation", "automatic_model_promotion", "model_selection_performed",
                 "calibrated_probability", "statistical_independence", "independent_replication_verified"):
        assert report[flag] is False
    coverage = report["coverage"]
    assert coverage["target_groups"] == 6 and coverage["declared_groups"] == 4
    assert coverage["target_outcomes"] == 144 and coverage["attempted_outcomes"] == 96
    assert coverage["missing_selection_slots"] == 2
    assert coverage["selection_complete"] is False
    assert coverage["sampling_coverage_fraction"] == 4 / 6
    assert coverage["scored_outcomes"] + coverage["failed_outcomes"] == 96
    ids = [group["drifter_id"] for group in report["groups"]]
    assert "8707978" not in ids and len(set(ids)) == 4
    observed = [(row["drifter_id"], row["model_id"], row["horizon_hours"]) for row in report["outcomes"]]
    assert len(observed) == len(set(observed)) == 96
    assert set(observed) == set(itertools.product(ids, ABLATION_MODEL_IDS, range(1, 7)))
    assert report["selection_failures"][0]["block_id"] == "indian-2010"
    assert report["selection_failures"][0]["selected_count"] == 0
    assert report["provenance"]["integrity_verified"] is True
    json.dumps(report, allow_nan=False)


def test_acquired_trajectory_means_macro_and_paired_counts_reconstruct_from_every_outcome():
    report = multidrifter.run_multidrifter_study()
    for summary in report["trajectory_summaries"]:
        outcomes = [row for row in report["outcomes"] if row["drifter_id"] == summary["drifter_id"]
                    and row["model_id"] == summary["model_id"]]
        assert len(outcomes) == 6
        errors = [row["error_m"] for row in outcomes]
        assert summary["scored_horizons"] == 6
        assert summary["mean_error_m"] == pytest.approx(np.mean(errors))
        assert summary["rmse_error_m"] == pytest.approx(np.sqrt(np.mean(np.square(errors))))
    for model in report["models"]:
        means = [row["mean_error_m"] for row in report["trajectory_summaries"] if row["model_id"] == model["id"]]
        assert model["macro"]["mean_trajectory_error_m"] == pytest.approx(np.mean(means))
        assert model["macro"]["scope"] == "ACQUIRED_DECLARED_COHORT_NOT_FULL_PLANNED_TARGET"
    for pair in report["paired_comparisons"]:
        candidate, baseline = [], []
        for group in report["groups"]:
            rows = {row["model_id"]: row for row in report["trajectory_summaries"]
                    if row["drifter_id"] == group["drifter_id"]}
            candidate.append(rows["ridge_ar1"]["mean_error_m"])
            baseline.append(rows[pair["baseline_id"]]["mean_error_m"])
        delta = np.array(candidate) - baseline
        summary = pair["summary"]
        assert summary["count"] == 4
        assert summary["mean_delta_m"] == pytest.approx(np.mean(delta))
        assert summary["median_delta_m"] == pytest.approx(np.median(delta))
        assert summary["min_delta_m"] == pytest.approx(min(delta))
        assert summary["max_delta_m"] == pytest.approx(max(delta))
        assert summary["candidate_lower_error_count"] == int(np.sum(delta < 0))
        assert summary["equal_error_count"] == int(np.sum(delta == 0))
        assert summary["candidate_higher_error_count"] == int(np.sum(delta > 0))
        assert summary["skill_vs_baseline"] == pytest.approx(1 - sum(candidate) / sum(baseline))


def test_future_truth_changes_errors_but_never_prefix_parameters_or_predictions_and_is_not_radius_filtered():
    group, records = synthetic_group(), synthetic_records()
    eligible, before, params = multidrifter.evaluate_trajectory(group, records)
    changed = [replace(record, latitude_deg=record.latitude_deg + 5) if i >= 18 else record
               for i, record in enumerate(records)]
    after_eligible, after, after_params = multidrifter.evaluate_trajectory(group, changed)
    assert eligible is after_eligible is True and params == after_params
    assert all(row["status"] == "SCORED" and row["error_m"] > 100_000 for row in after)
    for a, b in zip(before, after, strict=True):
        assert (a["latitude_deg"], a["longitude_deg"]) == (b["latitude_deg"], b["longitude_deg"])
    assert [row["error_m"] for row in before] != [row["error_m"] for row in after]
    summaries, models, pairs, complete = multidrifter.aggregate_outcomes([group], after)
    assert complete == [group["drifter_id"]]
    assert len(summaries) == len(models) == 4 and len(pairs) == 3


def test_all_fixed_model_predictions_exist_before_any_later_position_is_read(monkeypatch):
    group, original = synthetic_group(), synthetic_records()
    seen = set()
    legacy, mean = multidrifter._forecast, multidrifter.mean_drift_forecast

    def forecast(*args):
        seen.add(args[3])
        return legacy(*args)

    def mean_forecast(*args):
        if args[1] == 6:
            seen.add("mean_drift")
        return mean(*args)

    class GuardedTruth:
        def __init__(self, record):
            self.record = record

        def __getattr__(self, name):
            if name in {"latitude_deg", "longitude_deg"}:
                assert seen == set(ABLATION_MODEL_IDS)
            return getattr(self.record, name)

    guarded = original[:18] + [GuardedTruth(record) for record in original[18:]]
    monkeypatch.setattr(multidrifter, "_forecast", forecast)
    monkeypatch.setattr(multidrifter, "mean_drift_forecast", mean_forecast)
    eligible, outcomes, _ = multidrifter.evaluate_trajectory(group, guarded)
    assert eligible and len(outcomes) == 24


def test_position_predictor_ignores_future_ancillary_fields_while_shared_csv_ingestion_is_strict():
    group, records = synthetic_group(), synthetic_records()
    changed = [replace(record, eastward_m_s=float("nan"), northward_uncertainty_m_s=-1)
               if i >= 18 else record for i, record in enumerate(records)]
    assert multidrifter.evaluate_trajectory(group, records) == multidrifter.evaluate_trajectory(group, changed)
    # This is a disclosed ingestion limitation, not a claim that such rows are
    # admitted as physical input. No frozen payload or evaluator is modified.
    raw = (multidrifter.DIRECTORY / "raw/drifter-12730-2000-06-01.csv").read_text()
    rows = list(csv.reader(io.StringIO(raw)))
    rows[20][4] = "NaN"
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows(rows)
    with pytest.raises(ValueError, match="missing/non-finite"):
        multidrifter.parse_drifter_csv(out.getvalue())


def test_prefix_out_of_domain_remains_twenty_four_failures_in_all_denominators():
    group, records = synthetic_group(), synthetic_records()
    records[12] = replace(records[12], latitude_deg=15.0)
    eligible, outcomes, _ = multidrifter.evaluate_trajectory(group, records)
    assert eligible is False
    assert len(outcomes) == 24 and all(row["error_m"] is None for row in outcomes)
    assert all(row["reason_codes"] == ["PREFIX_OUT_OF_DOMAIN"] for row in outcomes)
    summaries, models, pairs, complete = multidrifter.aggregate_outcomes([group], outcomes)
    assert complete == []
    assert all(summary["failed_horizons"] == 6 and summary["mean_error_m"] is None for summary in summaries)
    assert all(model["macro"]["attempted_groups"] == 1 and model["macro"]["mean_trajectory_error_m"] is None for model in models)
    assert all(pair["failed_groups"] == 1 and pair["summary"] is None for pair in pairs)


def test_one_model_one_horizon_failure_withholds_common_macro_without_dropping_easy_models(monkeypatch):
    group, records = synthetic_group(), synthetic_records()
    original = multidrifter._forecast

    def far_forecast(xy, horizons, step_s, model_id):
        values, params = original(xy, horizons, step_s, model_id)
        if model_id == "ridge_ar1":
            values[-1] = [100_000, 0]
        return values, params

    monkeypatch.setattr(multidrifter, "_forecast", far_forecast)
    eligible, outcomes, params = multidrifter.evaluate_trajectory(group, records)
    assert eligible
    assert sum(row["status"] == "SCORED" for row in outcomes) == 23
    failed = next(row for row in outcomes if row["status"] == "FAILED")
    assert failed["model_id"] == "ridge_ar1" and failed["horizon_hours"] == 6
    assert failed["reason_codes"] == ["FORECAST_OUT_OF_DOMAIN"]
    summaries, models, pairs, complete = multidrifter.aggregate_outcomes([group], outcomes,
        {group["drifter_id"]: params})
    assert complete == [] and len(summaries) == 4
    assert all(model["macro"]["mean_trajectory_error_m"] is None for model in models)
    assert all(row["mean_error_m"] is None for model in models for row in model["per_horizon"])
    assert all(pair["summary"] is None and pair["failed_groups"] == 1 for pair in pairs)


@pytest.mark.parametrize("tamper", ["missing", "duplicate", "extra", "false_failure", "nonfinite"])
def test_aggregate_requires_exact_cartesian_identity_and_honest_failures(tamper):
    group = synthetic_group()
    _, outcomes, _ = multidrifter.evaluate_trajectory(group, synthetic_records())
    if tamper == "missing":
        outcomes.pop()
    elif tamper == "duplicate":
        outcomes.append(copy.deepcopy(outcomes[0]))
    elif tamper == "extra":
        outcomes[0]["horizon_hours"] = 7
    elif tamper == "false_failure":
        outcomes[0]["status"] = "FAILED"
    else:
        outcomes[0]["error_m"] = float("nan")
    with pytest.raises(ValueError):
        multidrifter.aggregate_outcomes([group], outcomes)


def test_zero_error_pairs_stay_null_skill_and_a_losing_candidate_is_kept():
    group = synthetic_group()
    _, outcomes, _ = multidrifter.evaluate_trajectory(group, synthetic_records())
    for row in outcomes:
        row["error_m"] = 0.0
    _, _, pairs, _ = multidrifter.aggregate_outcomes([group], outcomes)
    assert all(pair["summary"]["skill_vs_baseline"] is None
               and pair["summary"]["reason_codes"] == ["ZERO_BASELINE_ERROR"] for pair in pairs)
    for row in outcomes:
        row["error_m"] = 10.0 if row["model_id"] == "ridge_ar1" else 1.0
    _, _, pairs, _ = multidrifter.aggregate_outcomes([group], outcomes)
    assert all(pair["summary"]["mean_delta_m"] == 9.0
               and pair["summary"]["candidate_higher_error_count"] == 1
               and pair["summary"]["skill_vs_baseline"] == -9.0 for pair in pairs)


@pytest.mark.parametrize("tamper", ["reserved", "duplicate", "alpha", "radius", "origin"])
def test_development_overlap_or_frozen_model_preprocessing_origin_changes_are_rejected(tamper):
    protocol, selection, manifest, _, _ = multidrifter.load_multidrifter_inputs()
    if tamper == "reserved":
        selection["groups"][0]["drifter_id"] = "8707978"
    elif tamper == "duplicate":
        selection["groups"][1]["drifter_id"] = selection["groups"][0]["drifter_id"]
    elif tamper == "alpha":
        protocol["models"]["ridge_alpha"] = 2.0
    elif tamper == "radius":
        protocol["preprocessing"]["maximum_local_distance_m"] = 100_000
    else:
        protocol["origin"]["training_count"] = 19
    with pytest.raises(ValueError):
        multidrifter._identity(protocol, selection, manifest)
    with pytest.raises(ValueError, match="Development-only"):
        multidrifter.evaluate_trajectory({**synthetic_group(), "drifter_id": "8707978"}, synthetic_records())


@pytest.mark.parametrize("file", ["protocol.json", "selection.json", "manifest.json", "implementation-receipt.json",
                                "raw/drifter-12730-2000-06-01.csv"])
def test_changed_pinned_file_fails_closed_even_if_an_adjacent_receipt_is_recomputed(tmp_path, file):
    import hashlib

    target = tmp_path / "study"
    shutil.copytree(multidrifter.DIRECTORY, target)
    path = target / file
    path.write_bytes(path.read_bytes() + b" ")
    sidecar = path.with_suffix(".sha256")
    if sidecar.exists():
        sidecar.write_text(hashlib.sha256(path.read_bytes()).hexdigest() + "\n")
    # The implementation receipt is a local guard, not an authenticated signature;
    # modifying its content plus detached digest can only pass if its bound
    # protocol/selection/manifest/evaluator identities still match.
    if file == "implementation-receipt.json":
        altered = json.loads(path.read_text())
        altered["evaluator_sha256"] = "0" * 64
        path.write_text(json.dumps(altered))
        sidecar.write_text(hashlib.sha256(path.read_bytes()).hexdigest() + "\n")
    with pytest.raises(ValueError):
        multidrifter.load_multidrifter_inputs(target)


def _metadata_csv(protocol, block, index):
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(protocol["selection"]["metadata_columns"])
    writer.writerow(["", "UTC", "degrees_north", "degrees_east", "count", ""])
    lat = (block["latitude_min"] + block["latitude_max"]) / 2
    lon = (block["longitude_min"] + block["longitude_max"]) / 2
    for drifter_id in (str(index * 1000 + 3), str(index * 1000 + 1), "8707978", str(index * 1000 + 2)):
        writer.writerow([drifter_id, block["start_utc"], lat, lon, index, "Argos"])
    return output.getvalue().encode()


def test_acquisition_freezes_metadata_only_assignment_before_trajectory_fetch_and_never_replaces_failure(tmp_path, monkeypatch):
    folder = tmp_path / "study"
    folder.mkdir()
    for name in ("protocol.json", "protocol.sha256"):
        shutil.copy(multidrifter.DIRECTORY / name, folder / name)
    protocol = json.loads((folder / "protocol.json").read_text())
    metadata_bytes = (multidrifter.DIRECTORY / "raw/dataset-info.json").read_bytes()
    requests = []

    def handler(request):
        requests.append(str(request.url))
        if request.url.path.endswith("index.json"):
            return httpx.Response(200, content=metadata_bytes)
        query = str(request.url.query)
        if "expno" in query:
            if "2010" in query:
                return httpx.Response(503, content=b"Explicit synthetic metadata service failure")
            index = 1 if "2000" in query else 3
            block = protocol["selection"]["blocks"][index - 1]
            return httpx.Response(200, content=_metadata_csv(protocol, block, index))
        # Crucial chronology: no trajectory bytes may be requested before all
        # group assignment and a detached pre-outcome receipt have been saved.
        selection = json.loads((folder / "selection.json").read_text())
        assert selection["evaluation_outcomes_computed"] is False
        assert selection["trajectory_payloads_fetched"] is False
        assert (tmp_path / "work/multidrifter-selection-freeze.json").exists()
        assert not (folder / "manifest.json").exists()
        return httpx.Response(200, content=b"Explicit original-response-byte policy fixture; not real trajectory data")

    monkeypatch.setattr(acquisition, "ROOT", tmp_path)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        receipt = acquisition.acquire_study(folder, client=client)
    assert receipt["selected_ids"] == ["1001", "1002", "3001", "3002"]
    assert receipt["downloaded"] == 4 and receipt["evaluation_outcomes_computed"] is False
    assert len(requests) == 8
    selection = json.loads((folder / "selection.json").read_text())
    assert selection["blocks"][1]["status"] == "FETCH_FAILED"
    assert selection["blocks"][1]["selected_ids"] == []
    assert all("8707978" not in block["selected_ids"] for block in selection["blocks"])
    with pytest.raises(ValueError, match="never overwrite"):
        acquisition.acquire_study(folder)


def test_legacy_fixtures_and_reports_are_unchanged_by_new_cohort_replay():
    baseline = json.dumps(benchmark.run_real_data_example(), sort_keys=True, allow_nan=False)
    diagnostic = json.dumps(run_training_diagnostic(), sort_keys=True, allow_nan=False)
    ablation = json.dumps(run_motion_ablation(), sort_keys=True, allow_nan=False)
    multidrifter.run_multidrifter_study()
    assert json.dumps(benchmark.run_real_data_example(), sort_keys=True, allow_nan=False) == baseline
    assert json.dumps(run_training_diagnostic(), sort_keys=True, allow_nan=False) == diagnostic
    assert json.dumps(run_motion_ablation(), sort_keys=True, allow_nan=False) == ablation
