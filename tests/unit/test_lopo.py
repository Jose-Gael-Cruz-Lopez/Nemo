"""Post-hoc real replay plus explicitly synthetic leakage and identity tests."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import replace

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import lopo
from apps.ocean.reeftrace_ocean.data import parse_drifter_csv
from apps.ocean.reeftrace_ocean.multidrifter import load_multidrifter_inputs, run_multidrifter_study


def inputs():
    _, _, manifest, raw, _ = load_multidrifter_inputs()
    return {row["drifter_id"]: parse_drifter_csv(raw[row["raw_path"]].decode())
            for row in manifest["trajectories"]}


def assert_frozen_report_matches(actual, expected, path="$body"):
    """Keep provenance/structure exact while allowing cross-platform float roundoff.

    Linux and macOS linear algebra differ at floating-point roundoff scale in this
    fixture. The explicit tolerance remains well below any meaningful reported
    positional precision; it is not applied to counts, IDs, flags or statuses.
    """
    assert type(actual) is type(expected), f"{path}: type changed"
    if isinstance(expected, float):
        assert math.isfinite(actual) and math.isfinite(expected), f"{path}: nonfinite value"
        assert actual == pytest.approx(expected, rel=1e-10, abs=1e-8), path
    elif isinstance(expected, dict):
        assert actual.keys() == expected.keys(), f"{path}: keys changed"
        for key in expected:
            assert_frozen_report_matches(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        assert len(actual) == len(expected), f"{path}: list length changed"
        for index, (value, frozen) in enumerate(zip(actual, expected, strict=True)):
            assert_frozen_report_matches(value, frozen, f"{path}[{index}]")
    else:
        assert actual == expected, path


def test_frozen_report_comparison_accepts_only_narrow_float_roundoff():
    frozen = {"models": [{"error_m": 2911.2980731059383, "spectral_radius": 0.9297275578838206}]}
    linux = {"models": [{"error_m": 2911.2980731060047, "spectral_radius": 0.9297275578838187}]}
    assert_frozen_report_matches(linux, frozen)


@pytest.mark.parametrize(("actual", "expected"), [
    ({"drifter_id": "12731"}, {"drifter_id": "12730"}),
    ({"coverage": {"scored_outcomes": 119}}, {"coverage": {"scored_outcomes": 120}}),
    ({"status": "INCOMPLETE_OUTCOMES"}, {"status": "COMPLETE"}),
    ({"independent_evaluation": True}, {"independent_evaluation": False}),
    ({"independent_evaluation": 0}, {"independent_evaluation": False}),
    ({"coverage": 120.0}, {"coverage": 120}),
    ({"errors_m": [1.0]}, {"errors_m": [1.0, 2.0]}),
    ({"error_m": 2911.2990731059383}, {"error_m": 2911.2980731059383}),
    ({"error_m": float("nan")}, {"error_m": 1.0}),
    ({"error_m": float("inf")}, {"error_m": 1.0}),
    ({"error_m": 1.0, "extra": None}, {"error_m": 1.0}),
])
def test_frozen_report_comparison_rejects_identity_accounting_and_material_changes(actual, expected):
    with pytest.raises(AssertionError):
        assert_frozen_report_matches(actual, expected)


def test_real_diagnostic_matches_frozen_report_and_preserves_all_120_outcomes_and_original_results():
    before = run_multidrifter_study()
    report = lopo.run_lopo_diagnostic()
    payload = (lopo.DIRECTORY / "report.json").read_bytes()
    assert hashlib.sha256(payload).hexdigest() == (lopo.DIRECTORY / "report.sha256").read_text().strip()
    assert_frozen_report_matches(report, json.loads(payload))
    # A second run in the same process must still reproduce every value exactly.
    assert report == lopo.run_lopo_diagnostic()
    assert run_multidrifter_study() == before
    assert report["design_status"] == "POST_HOC_ALREADY_VIEWED_DRIFTERS_NOT_INDEPENDENT_TEST"
    assert report["independent_evaluation"] is False
    assert report["physical_alias_resolution_verified"] is False
    assert report["automatic_model_promotion"] is False
    assert report["test_data_used"] is True
    assert report["coverage"]["attempted_outcomes"] == report["coverage"]["scored_outcomes"] == 120
    ids = [row["held_out_drifter_id"] for row in report["folds"]]
    matrix = [(row["drifter_id"], row["model_id"], row["horizon_hours"]) for row in report["outcomes"]]
    assert len(matrix) == len(set(matrix)) == 120
    assert set(matrix) == set(itertools.product(ids, lopo.MODEL_IDS, range(1, 7)))
    for fold in report["folds"]:
        assert fold["held_out_drifter_id"] not in fold["training_drifter_ids"]
        assert fold["parameters"]["training_velocity_pairs"] == 48
        assert fold["parameters"]["held_group_used_to_fit_shared_matrix"] is False
    for model in report["models"]:
        errors = [row["error_m"] for row in report["outcomes"] if row["model_id"] == model["id"]]
        assert model["mean_trajectory_error_m"] == pytest.approx(np.mean(errors))
    # Retain the unfavorable new-model outcome, rather than promoting or hiding it.
    means = {row["id"]: row["mean_trajectory_error_m"] for row in report["models"]}
    assert means["pooled_residual_ar1"] > means["ridge_ar1"]
    json.dumps(report, allow_nan=False)


def test_physical_alias_overlap_missing_mapping_and_duplicate_training_alias_fail_closed():
    with pytest.raises(ValueError, match="aliases overlap"):
        lopo.assert_disjoint_physical_groups(["gdp-a"], ["wmo-a"], {"gdp-a": "buoy-a", "wmo-a": "buoy-a"})
    with pytest.raises(ValueError, match="complete physical"):
        lopo.assert_disjoint_physical_groups(["a"], ["b"], {"a": "buoy-a"})
    with pytest.raises(ValueError, match="aliases overlap"):
        lopo.assert_disjoint_physical_groups(["a", "alias-a"], ["b"],
            {"a": "buoy-a", "alias-a": "buoy-a", "b": "buoy-b"})


def test_alias_overlap_rejected_before_shared_matrix_fit(monkeypatch):
    records = inputs()
    ids = list(records)
    aliases = dict(zip(ids, ids, strict=True))
    aliases[ids[1]] = aliases[ids[0]]

    def forbidden(*args):
        pytest.fail("Shared matrix fit ran despite held/training alias overlap")

    monkeypatch.setattr(lopo, "fit_pooled_transition", forbidden)
    with pytest.raises(ValueError, match="aliases overlap"):
        lopo.diagnostic_predictions(records, aliases)


def test_future_positions_cannot_be_read_during_any_fold_prediction():
    records = inputs()

    class FuturePosition:
        def __init__(self, row):
            self.drifter_id, self.time_utc = row.drifter_id, row.time_utc

        @property
        def latitude_deg(self):
            pytest.fail("Future truth was accessed before all predictions existed")

        @property
        def longitude_deg(self):
            pytest.fail("Future truth was accessed before all predictions existed")

    guarded = {key: [*rows[:18], *(FuturePosition(row) for row in rows[18:])]
               for key, rows in records.items()}
    predictions, folds = lopo.diagnostic_predictions(guarded, {key: key for key in records})
    assert len(predictions) == 20 and len(folds) == 4


def test_held_prefix_changes_conditioning_but_not_its_shared_matrix_or_training_scale():
    records = inputs()
    ids = list(records)
    held = ids[0]
    mapping = {key: key for key in records}
    before, old_folds = lopo.diagnostic_predictions(records, mapping)
    changed = {key: list(rows) for key, rows in records.items()}
    # Synthetic perturbation of one target prefix point; no real data are rewritten.
    changed[held][10] = replace(changed[held][10], latitude_deg=changed[held][10].latitude_deg + 0.001)
    after, new_folds = lopo.diagnostic_predictions(changed, mapping)
    old = next(row for row in old_folds if row["held_out_drifter_id"] == held)
    new = next(row for row in new_folds if row["held_out_drifter_id"] == held)
    assert old["parameters"] == new["parameters"]
    # A final-prefix perturbation changes target conditioning while leaving A fixed.
    changed[held][17] = replace(changed[held][17], latitude_deg=changed[held][17].latitude_deg + 0.001)
    after, new_folds = lopo.diagnostic_predictions(changed, mapping)
    assert next(row for row in new_folds if row["held_out_drifter_id"] == held)["parameters"] == old["parameters"]
    assert before[held, "pooled_residual_ar1"] != after[held, "pooled_residual_ar1"]


def test_any_pooled_forecast_failure_keeps_attempted_outcomes_and_withholds_all_macro(monkeypatch):
    original = lopo.diagnostic_predictions

    def failed(*args):
        forecasts, folds = original(*args)
        forecasts[next(iter(args[0])), "pooled_residual_ar1"] = [None] * 6
        return forecasts, folds

    monkeypatch.setattr(lopo, "diagnostic_predictions", failed)
    report = lopo.run_lopo_diagnostic()
    assert report["coverage"]["attempted_outcomes"] == 120
    assert report["coverage"]["failed_outcomes"] == 6
    assert report["status"] == "INCOMPLETE_OUTCOMES"
    assert all(row["mean_trajectory_error_m"] is None for row in report["models"])
