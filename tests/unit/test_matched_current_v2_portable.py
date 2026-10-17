"""Portability permits numerical roundoff only; frozen evidence stays exact."""

import copy
import hashlib
import json
import shutil

import pytest

from apps.ocean.reeftrace_ocean.matched_current import forecast_sha256
from scripts import verify_matched_current_v2_portable as portable


@pytest.mark.parametrize(("path", "delta", "units"), [
    ("$.forecasts.groups[0].candidates[1].cells[0].latitude_deg", 1e-14, "degrees"),
    ("$.scores.forecast_report.groups[1].candidates[2].advection.track[0].longitude_deg", 1e-14, "degrees"),
    ("$.forecasts.groups[0].candidates[1].last_observed_velocity_m_s[1]", 1e-13, "m/s"),
    ("$.forecasts.groups[0].candidates[2].advection.track[0].speed_m_s", 1e-13, "m/s"),
    ("$.scores.groups[0].candidates[1].cells[0].error_m", 1e-8, "metres"),
    ("$.scores.primary_equal_id_macro_results[1].equal_id_macro_ade_m", 1e-8, "metres"),
])
def test_only_explicit_computed_float_paths_allow_bounded_roundoff(path, delta, units):
    differences = portable.compare_numeric_trees(1.0, 1.0 + delta, path=path)
    assert len(differences) == 1
    assert differences[0]["units"] == units
    assert differences[0]["absolute_difference"] <= portable.ABSOLUTE_TOLERANCES[units]


@pytest.mark.parametrize("path", [
    "$.forecasts.groups[0].origin_position.latitude_deg",
    "$.scores.groups[0].candidates[0].cells[0].target_latitude_deg",
    "$.forecasts.groups[0].candidates[0].advection.solver.maximum_step_s",
    "$.forecasts.groups[0].candidates[0].completed_horizon_s",
    "$.source_receipts[0].elapsed_wall_s",
    "$.arbitrary.new_field_m",
])
def test_input_values_configuration_clocks_and_unknown_quantities_are_exact(path):
    with pytest.raises(ValueError, match="numeric difference"):
        portable.compare_numeric_trees(1.0, 1.0 + 1e-14, path=path)


@pytest.mark.parametrize(("saved", "current"), [
    (True, 1), (1, 1.0), (1, 2), ("COMPLETED", "UNSUPPORTED"),
    ({"x": 1}, {"x": 1, "y": 2}), ([1], [1, 2]),
    (float("nan"), float("nan")), (float("inf"), float("inf")),
])
def test_types_nonfinite_shapes_counts_statuses_and_strings_never_get_tolerance(saved, current):
    with pytest.raises(ValueError):
        portable.compare_numeric_trees(saved, current)


@pytest.mark.parametrize(("path", "delta"), [
    ("$.forecasts.groups[0].candidates[1].cells[0].latitude_deg", 2e-11),
    ("$.forecasts.groups[0].candidates[1].last_observed_velocity_m_s[1]", 2e-12),
    ("$.scores.primary_equal_id_macro_results[0].equal_id_macro_ade_m", 2e-6),
])
def test_above_bound_changes_fail_and_no_relative_tolerance_is_used(path, delta):
    with pytest.raises(ValueError, match="numeric difference"):
        portable.compare_numeric_trees(1.0, 1.0 + delta, path=path)
    with pytest.raises(ValueError, match="numeric difference"):
        portable.compare_numeric_trees(100_000.0, 100_000.0 + 1e-4, path=path)


def _snapshot():
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in portable.frozen.DIRECTORY.rglob("*") if path.is_file()}


def test_real_frozen_v2_portable_replay_never_rewrites_any_archived_bytes():
    pytest.importorskip("netCDF4")
    before = _snapshot()
    report = portable.verify_portable()
    assert report["verified"] is True
    assert report["artifact_identity"]["result_pin_verified"] is True
    assert report["frozen_exact_evaluator_changed"] is False
    assert report["frozen_artifacts_written"] is False
    assert report["new_first_score"] is False
    assert report["network_acquisition"] is False
    assert _snapshot() == before


@pytest.mark.parametrize("change", ["roundoff", "physical_shift", "stale_digest", "status"])
def test_real_replay_distinguishes_roundoff_from_changed_motion_and_contract(monkeypatch, change):
    pytest.importorskip("netCDF4")
    inputs = list(portable.frozen._inputs(portable.frozen.DIRECTORY))
    forecasts = copy.deepcopy(inputs[5])
    candidate = forecasts["groups"][0]["candidates"][1]
    if change == "status":
        candidate["status"] = "UNSUPPORTED"
    else:
        candidate["cells"][0]["latitude_deg"] += 1e-14 if change == "roundoff" else 2e-11
    if change != "stale_digest":
        forecasts["forecast_sha256"] = forecast_sha256(forecasts)
    inputs[5] = forecasts
    monkeypatch.setattr(portable.frozen, "_inputs", lambda directory: tuple(inputs))
    before = _snapshot()
    if change == "roundoff":
        result = portable.verify_portable()
        assert result["bit_exact_forecasts"] is False
        assert result["accepted_roundoff_differences"]
    else:
        with pytest.raises(ValueError):
            portable.verify_portable()
    assert _snapshot() == before


def test_recomputed_score_perturbation_exceeding_one_micrometre_fails(monkeypatch):
    pytest.importorskip("netCDF4")
    original = portable.frozen.score_matched_current_forecasts

    def wrong_score(*args, **kwargs):
        result = original(*args, **kwargs)
        result["primary_equal_id_macro_results"][0]["equal_id_macro_ade_m"] += 1e-4
        return result

    monkeypatch.setattr(portable.frozen, "score_matched_current_forecasts", wrong_score)
    with pytest.raises(ValueError, match="numeric difference"):
        portable.verify_portable()


def test_rehashed_saved_forecast_tampering_fails_even_within_float_tolerance(tmp_path):
    pytest.importorskip("netCDF4")
    directory = tmp_path / "study"
    shutil.copytree(portable.frozen.DIRECTORY, directory)
    path = directory / "forecasts.json"
    document = json.loads(path.read_text())
    forecasts = document["forecasts"]
    forecasts["groups"][0]["candidates"][1]["cells"][0]["latitude_deg"] += 1e-14
    forecasts["forecast_sha256"] = forecast_sha256(forecasts)
    raw = portable.frozen.canonical_json(document)
    path.write_bytes(raw)
    path.with_suffix(".sha256").write_text(hashlib.sha256(raw).hexdigest() + "\n")
    with pytest.raises(ValueError, match="trusted artifact hash changed"):
        portable.verify_portable(directory)
