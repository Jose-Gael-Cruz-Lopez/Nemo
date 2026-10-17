"""Verify frozen v2 numbers across platforms without rewriting the first score.

The original byte/exact-float evaluator remains frozen and unchanged. This
separate software check permits only explicit, tiny absolute differences in
computed floating-point quantities. Input bytes, source hashes, chronology,
schema, statuses, counts, times, units and provenance still match exactly.
It performs no acquisition, model fitting, new first score or provider call.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import platform
import re
from pathlib import Path

from apps.ocean.reeftrace_ocean.matched_current import forecast_sha256
from apps.ocean.reeftrace_ocean.matched_current_result import load_frozen_matched_current_result
from scripts import evaluate_matched_current_v2_study as frozen

# These are numerical portability bounds, not measurement/model uncertainty.
# No relative tolerance: large values never receive proportionally larger slack.
ABSOLUTE_TOLERANCES = {"degrees": 1e-11, "m/s": 1e-12, "metres": 1e-6}
_CANDIDATE = "$.groups[].candidates[]"
_FORECAST_DEGREES = {
    _CANDIDATE + branch + "." + coordinate
    for branch in (".cells[]", ".advection.track[]")
    for coordinate in ("latitude_deg", "longitude_deg")
}
_FORECAST_VELOCITIES = {
    _CANDIDATE + ".last_observed_velocity_m_s[]",
    *(_CANDIDATE + ".advection.track[]." + key
      for key in ("eastward_m_s", "northward_m_s", "speed_m_s")),
}
_SCORE_METRES = {
    "$.scores.groups[].candidates[].cells[].error_m",
    *("$.scores.groups[].candidates[].metrics." + key for key in (
        "available_cell_mean_error_m", "endpoint_fde_m", "full_horizon_ade_m",
        "scored_prefix_mean_error_m")),
    *("$.scores.models[].metrics." + key for key in (
        "available_cell_mean_error_m", "full_horizon_ade_m")),
    *("$.scores.models[].per_horizon[]." + key for key in (
        "available_group_mean_error_m", "complete_group_mean_error_m")),
    *("$.scores." + comparison + "." + key
      for comparison in ("paired_comparisons[]", "primary_paired_comparisons[]")
      for key in ("mean_delta_a_minus_b_m", "mean_error_a_m", "mean_error_b_m",
                  "cells[].error_a_m", "cells[].error_b_m")),
    *("$.scores.primary_equal_id_macro_results[]." + key for key in (
        "equal_id_macro_ade_m", "equal_id_macro_fde_m",
        "per_horizon_mean_error_m[].error_m")),
}


def _units(path: str) -> str | None:
    normalized = re.sub(r"\[\d+\]", "[]", path)
    forecast_path = normalized
    for prefix in ("$.forecasts", "$.scores.forecast_report"):
        if normalized.startswith(prefix + "."):
            forecast_path = "$" + normalized[len(prefix):]
            break
    if forecast_path in _FORECAST_DEGREES:
        return "degrees"
    if forecast_path in _FORECAST_VELOCITIES:
        return "m/s"
    if normalized in {
        "$.scores.groups[].candidates[].cells[].latitude_deg",
        "$.scores.groups[].candidates[].cells[].longitude_deg",
    }:
        return "degrees"
    if normalized in _SCORE_METRES:
        return "metres"
    return None


def compare_numeric_trees(saved, recomputed, *, path="$", differences=None) -> list[dict]:
    """Strict recursive comparison, with only path-allowlisted float bounds.

    Integer/boolean identity is strict. Coordinates read directly from the CSV,
    origins, solver configuration and acquisition clocks receive no tolerance.
    Forecast digest verification is handled separately; this function never
    ignores hash strings or arbitrary metadata.
    """
    differences = [] if differences is None else differences
    if type(saved) is not type(recomputed):
        raise ValueError(f"Portable v2 type changed at {path}")
    if isinstance(saved, dict):
        if saved.keys() != recomputed.keys():
            raise ValueError(f"Portable v2 object keys changed at {path}")
        for key in sorted(saved):
            compare_numeric_trees(saved[key], recomputed[key],
                                  path=f"{path}.{key}", differences=differences)
    elif isinstance(saved, list):
        if len(saved) != len(recomputed):
            raise ValueError(f"Portable v2 list length changed at {path}")
        for index, (left, right) in enumerate(zip(saved, recomputed, strict=True)):
            compare_numeric_trees(left, right, path=f"{path}[{index}]", differences=differences)
    elif type(saved) is float:
        if not math.isfinite(saved) or not math.isfinite(recomputed):
            raise ValueError(f"Portable v2 nonfinite number at {path}")
        if saved != recomputed:
            units = _units(path)
            difference = abs(saved - recomputed)
            if units is None or difference > ABSOLUTE_TOLERANCES[units]:
                raise ValueError(f"Portable v2 numeric difference exceeds its explicit bound at {path}")
            differences.append({"path": path, "saved": saved, "recomputed": recomputed,
                                "absolute_difference": difference, "units": units,
                                "absolute_tolerance": ABSOLUTE_TOLERANCES[units]})
    elif saved != recomputed:
        raise ValueError(f"Portable v2 fixed value changed at {path}")
    return differences


def _without_validated_digest(forecasts: dict) -> dict:
    if forecasts.get("forecast_sha256") != forecast_sha256(forecasts):
        raise ValueError("Portable v2 forecast content digest does not match its own numbers")
    return {key: value for key, value in forecasts.items() if key != "forecast_sha256"}


def verify_portable(directory: Path = frozen.DIRECTORY) -> dict:
    directory = Path(directory)
    # The frozen implementation builds every forecast using context only before
    # we invoke the public saved-result validator or decode target coordinates.
    (protocol, manifest, hashes, contexts, targets, forecasts,
     forcing, current_failure) = frozen._inputs(directory)
    view = load_frozen_matched_current_result(directory, study_version="v2")
    saved_report = view["report"]
    saved_document, file_hash = frozen._pinned(directory / "forecasts.json")
    if file_hash != view["artifact_identity"]["forecast_file_sha256"]:
        raise ValueError("Portable v2 forecast file identity changed")
    frozen._forecast_chronology(saved_document, manifest)
    saved_forecasts = saved_document["forecasts"]
    lineage = {key: value for key, value in hashes.items() if key.endswith("sha256")}
    compare_numeric_trees(saved_document, {
        "schema_version": 1, "kind": "FROZEN_MATCHED_CURRENT_FORECASTS",
        "study_id": protocol["study_id"], "lineage": lineage,
        "forecasts": saved_forecasts, "future_coordinates_decoded": False,
        "frozen_at_utc": saved_document["frozen_at_utc"],
    })
    differences = compare_numeric_trees(
        _without_validated_digest(saved_forecasts), _without_validated_digest(forecasts),
        path="$.forecasts")
    # Both hash strings remain separately verified against their own complete
    # numbers. A different runtime hash is disclosed, never written over the pin.
    scores = frozen.score_matched_current_forecasts(forecasts, targets)
    bit_exact_scores = saved_report["scores"] == scores
    saved_scores = copy.deepcopy(saved_report["scores"])
    scores = copy.deepcopy(scores)
    saved_scores["forecast_report"] = _without_validated_digest(saved_scores["forecast_report"])
    scores["forecast_report"] = _without_validated_digest(scores["forecast_report"])
    compare_numeric_trees(saved_scores, scores, path="$.scores", differences=differences)
    compare_numeric_trees(saved_report["lineage"], lineage)
    compare_numeric_trees(saved_report["source_receipts"], manifest["source_receipts"])
    compare_numeric_trees(saved_report["context_qc"], {
        group: frozen._context_qc(contexts.get(group, [])) for group in frozen.GROUP_IDS})
    compare_numeric_trees(saved_report["current_field"], forcing.summary() if forcing else None)
    compare_numeric_trees(saved_report["current_field_failure"], current_failure)
    # Detect concurrent generation changes using the trusted reader and hashes.
    if load_frozen_matched_current_result(directory, study_version="v2") != view:
        raise ValueError("Portable v2 pinned artifacts changed during verification")
    return {
        "schema_version": 1, "kind": "MATCHED_CURRENT_V2_PORTABLE_NUMERIC_VERIFICATION",
        "verified": True, "study_id": protocol["study_id"],
        "verification_scope": "EXACT_FROZEN_INPUTS_AND_SCHEMA_WITH_EXPLICIT_FLOAT_ROUNDOFF_BOUNDS",
        "bit_exact_forecasts": saved_forecasts == forecasts,
        "bit_exact_scores": bit_exact_scores,
        "artifact_identity": view["artifact_identity"],
        "saved_forecast_content_sha256": saved_forecasts["forecast_sha256"],
        "runtime_forecast_content_sha256": forecasts["forecast_sha256"],
        "absolute_tolerances": ABSOLUTE_TOLERANCES, "relative_tolerance": 0,
        "accepted_roundoff_differences": differences,
        "runtime": {"python": platform.python_version(), "system": platform.system(),
                    "machine": platform.machine()},
        "frozen_exact_evaluator_changed": False, "frozen_artifacts_written": False,
        "new_first_score": False, "network_acquisition": False,
        "provider_calls": False, "physical_validation": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=frozen.DIRECTORY)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_portable(args.directory)
    raw = (json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    if args.output:
        with args.output.open("xb") as stream:
            stream.write(raw)
    else:
        print(raw.decode(), end="")


if __name__ == "__main__":
    main()
