"""Pure, bounded public reader of an already scored matched-current study.

This module never forecasts, scores, acquires, freezes or imports the first-score
wrapper. Hash/shape/clock validation is not an independent numerical replay.
The default requires a separately trusted result identity; an explicit caller
pin may be supplied while that identity is being prepared. Unpinned reads require
an explicit local-only opt-in and must never be used by a public/API handler.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import itertools
import json
import math
import re
from datetime import datetime, timedelta
from pathlib import Path

from . import matched_current_protocol as protocol_io

RESULT_IDENTITY_RELATIVE = "apps/ocean/reeftrace_ocean/matched_current_result_identity.py"
MAX_RESULT_BYTES = 4_194_304
GROUP_IDS = tuple(row[0] for row in protocol_io.GROUPS)
MODEL_IDS = tuple(protocol_io.MODEL_IDS)
HORIZONS = tuple(range(3600, 21601, 3600))
ORIGIN = datetime.fromisoformat(protocol_io.ORIGIN)
FALSE_FLAGS = {
    "physical_validation", "operational_causality", "assimilation_independence_verified",
    "physical_alias_resolution_verified", "statistical_independence", "global_training",
    "heldout_tuning", "automatic_model_promotion", "provider_calls", "camera_started",
    "store_written",
}
REPORT_KEYS = {
    "schema_version", "kind", "study_id", "lineage", "forecast_file_sha256",
    "forecast_frozen_at_utc", "forecasts_saved_before_target_coordinate_decode",
    "source_receipts", "context_qc", "current_field", "current_field_failure", "scores",
    "scored_at_utc", *FALSE_FLAGS,
}
FORECAST_KEYS = {
    "schema_version", "kind", "origin_time_utc", "group_ids", "model_ids", "horizons_s",
    "planned_group_count", "planned_cell_count", "planned_distinct_target_count",
    "all_forecasts_built_before_target_decode", "future_positions_used", "coordinate_method",
    "score_method", "statistical_independence", "operational_forecast_skill_verified",
    "physical_validation", "groups", "forecast_sha256",
}
CELL_KEYS = {
    "horizon_hours", "elapsed_s", "time_utc", "forecast_status", "forecast_reason_code",
    "latitude_deg", "longitude_deg",
}
SCORED_CELL_KEYS = CELL_KEYS | {
    "group_id", "model_id", "target_status", "target_reason_code", "target_latitude_deg",
    "target_longitude_deg", "error_m", "score_status",
}
SCORE_KEYS = {
    "schema_version", "kind", "origin_time_utc", "planned_group_count", "planned_cell_count",
    "scored_cell_count", "planned_distinct_target_count", "forecast_report", "groups",
    "models", "paired_comparisons", "primary_common_cohort_complete",
    "primary_equal_id_macro_results", "primary_paired_comparisons", "statistical_independence",
    "automatic_winner_selected", "operational_forecast_skill_verified", "physical_validation",
    "limitations",
}


def _require(condition, message: str) -> None:
    if not condition:
        raise ValueError("Frozen matched-current result: " + message)


def _hash(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _number(value, *, nonnegative=False) -> bool:
    return (type(value) in {int, float} and math.isfinite(value)
            and (not nonnegative or value >= 0))


def _keys(value, expected) -> None:
    _require(isinstance(value, dict) and set(value) == set(expected), "object schema changed")


def _clock(value) -> datetime:
    try:
        result = datetime.fromisoformat(value) if isinstance(value, str) else None
        if result is None or result.utcoffset() != timedelta(0):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Frozen matched-current result: invalid UTC receipt clock") from None
    return result


def _equal(value, expected) -> None:
    """Compare stored aggregate arithmetic, never compute new scientific errors."""
    if type(expected) is float:
        _require(_number(value) and math.isclose(value, expected, rel_tol=1e-12, abs_tol=1e-9),
                 "stored aggregate arithmetic changed")
    elif isinstance(expected, dict):
        _keys(value, expected)
        for key, child in expected.items():
            _equal(value[key], child)
    elif isinstance(expected, list):
        _require(isinstance(value, list) and len(value) == len(expected), "list shape changed")
        for child, reference in zip(value, expected, strict=True):
            _equal(child, reference)
    else:
        _require(type(value) is type(expected) and value == expected, "fixed value changed")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _no_constant(_value):
    raise ValueError("Frozen matched-current result: nonfinite JSON constant")


def _bounded(value, depth=0, budget=None) -> None:
    budget = [0] if budget is None else budget
    budget[0] += 1
    _require(depth <= 24 and budget[0] <= 100_000, "structure exceeds its budget")
    if isinstance(value, dict):
        _require(len(value) <= 300 and all(isinstance(key, str) for key in value),
                 "object exceeds its budget")
        for child in value.values():
            _bounded(child, depth + 1, budget)
    elif isinstance(value, list):
        _require(len(value) <= 2048, "array exceeds its budget")
        for child in value:
            _bounded(child, depth + 1, budget)
    elif isinstance(value, str):
        _require(len(value) <= 12_000, "string exceeds its budget")
    else:
        _require(value is None or type(value) is bool or _number(value), "invalid JSON value")


def _pinned(directory: Path, name: str, expected=None) -> tuple[dict, str]:
    path = protocol_io._safe_path(directory, name + ".json")
    raw = protocol_io.read_bytes(path, MAX_RESULT_BYTES)
    digest = hashlib.sha256(raw).hexdigest()
    sidecar = protocol_io.read_bytes(protocol_io._safe_path(directory, name + ".sha256"), 80)
    try:
        detached = sidecar.decode("ascii").strip()
    except UnicodeError:
        raise ValueError("Frozen matched-current result: invalid detached hash") from None
    _require(_hash(detached) and detached == digest, "detached artifact hash changed")
    _require(expected is None or expected == digest, "trusted artifact hash changed")
    try:
        value = json.loads(raw, object_pairs_hook=_unique, parse_constant=_no_constant)
        _bounded(value)
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError):
        raise ValueError("Frozen matched-current result: invalid bounded JSON") from None
    _require(isinstance(value, dict), "artifact must be an object")
    return value, digest


def _version_contract(study_version: str):
    """Two explicit historical namespaces; never accept a caller module/path."""
    if study_version == "v1":
        return protocol_io, RESULT_IDENTITY_RELATIVE, "data/research/matched-current-v1"
    if study_version == "v2":
        from . import matched_current_v2_protocol

        return (matched_current_v2_protocol,
                "apps/ocean/reeftrace_ocean/matched_current_v2_result_identity.py",
                "data/research/matched-current-v2")
    raise ValueError("Unknown frozen matched-current study version")


def _result_pin(root: Path, expected, allow_unpinned: bool, *, study_version="v1") -> tuple[dict, str, str | None]:
    selected_protocol, identity_relative, _ = _version_contract(study_version)
    if expected is not None:
        _require(_hash(expected), "expected report hash must be lowercase SHA-256")
        return {"REPORT_SHA256": expected}, "EXPLICIT_CALLER_PIN", None
    path = root / identity_relative
    if not path.is_file():
        if allow_unpinned:
            return {}, "UNPINNED_LOCAL_ONLY", None
        raise FileNotFoundError("Trusted matched-current result identity is not available")
    _require(not path.is_symlink(), "symlinked result identity is not accepted")
    raw = protocol_io.read_bytes(path, 1024)
    try:
        tree = ast.parse(raw.decode("utf-8"))
    except (SyntaxError, UnicodeError):
        raise ValueError("Frozen matched-current result: invalid trusted identity syntax") from None
    values = {}
    for node in tree.body:
        _require(isinstance(node, ast.Assign) and len(node.targets) == 1
                 and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Constant)
                 and isinstance(node.value.value, str) and node.targets[0].id not in values,
                 "result identity permits literal string assignments only")
        values[node.targets[0].id] = node.value.value
    _keys(values, {"STUDY_ID", "REPORT_SHA256", "FORECAST_SHA256", "MANIFEST_SHA256"})
    _require(values["STUDY_ID"] == selected_protocol.STUDY_ID
             and all(_hash(values[key]) for key in values if key != "STUDY_ID"),
             "trusted result identity changed")
    return values, "TRUSTED_RESULT_IDENTITY", hashlib.sha256(raw).hexdigest()


def _position(latitude, longitude) -> None:
    _require(_number(latitude) and -90 <= latitude <= 90
             and _number(longitude) and -180 <= longitude <= 180, "invalid geographic position")


def _reason(value, *, required=False) -> None:
    _require((value is None and not required)
             or isinstance(value, str) and 0 < len(value) <= 300, "invalid reason code")


def _strings(value) -> None:
    _require(isinstance(value, list) and value
             and all(isinstance(item, str) and item for item in value), "text list changed")


def _field_shape(value, receipt) -> None:
    """Whitelist the saved reader summary, never decode the underlying grid."""
    _keys(value, {"coordinate_space", "velocity_units", "array_dimensions", "shape",
        "time_start_utc", "time_end_utc", "longitude_range_deg", "latitude_range_deg",
        "selected_depth_m", "valid_sample_count", "invalid_sample_count",
        "longitude_spacing_degrees_min_max", "latitude_spacing_degrees_min_max",
        "approx_east_west_grid_spacing_m_at_midlatitude", "approx_north_south_grid_spacing_m",
        "limitations", "provenance"})
    _require(value["coordinate_space"] == "geographic_lonlat_degrees"
             and value["velocity_units"] == "m/s" and value["selected_depth_m"] == 15
             and value["array_dimensions"] == ["time", "latitude", "longitude"],
             "current units/depth changed")
    shape = value["shape"]
    _require(isinstance(shape, list) and len(shape) == 3 and type(shape[0]) is int and shape[0] == 3
             and all(type(n) is int and n >= 2 for n in shape[1:])
             and math.prod(shape) <= 250_000, "current summary exceeds fixed grid budget")
    _require(_clock(value["time_start_utc"]) == ORIGIN
             and _clock(value["time_end_utc"]) == ORIGIN + timedelta(hours=6),
             "current summary time range changed")
    valid, invalid = value["valid_sample_count"], value["invalid_sample_count"]
    _require(type(valid) is type(invalid) is int and min(valid, invalid) >= 0
             and valid + invalid == math.prod(shape), "current support accounting changed")
    for key, bounds in (("longitude_range_deg", (-80, -65)), ("latitude_range_deg", (25, 35))):
        axis = value[key]
        _require(isinstance(axis, list) and len(axis) == 2 and all(_number(x) for x in axis)
                 and bounds[0] <= axis[0] < axis[1] <= bounds[1], "current summary domain changed")
    for key in ("longitude_spacing_degrees_min_max", "latitude_spacing_degrees_min_max",
                "approx_east_west_grid_spacing_m_at_midlatitude", "approx_north_south_grid_spacing_m"):
        _require(isinstance(value[key], list) and len(value[key]) == 2
                 and all(_number(n) and n > 0 for n in value[key]), "current grid spacing changed")
    metadata = value["provenance"]
    _keys(metadata, {"product", "contract_metadata_url", "sha256", "source_bytes", "u_variable",
        "v_variable", "velocity_units", "data_kind", "source_origin_verified", "issue_time_verified",
        "calendar", "time_units", "longitude_normalization", "raw_encoding", "limitations"})
    _require(metadata["sha256"] == receipt["sha256"]
             and metadata["source_bytes"] == receipt["bytes"]
             and metadata["u_variable"] == "water_u" and metadata["v_variable"] == "water_v"
             and metadata["velocity_units"] == "m/s" and metadata["source_origin_verified"] is False
             and metadata["issue_time_verified"] is False, "current provenance/claim boundary changed")
    _equal(metadata["raw_encoding"], {"dtype": "signed_int16", "fill_and_missing": -30000,
        "scale_factor_encoding": "exact_pinned_float32", "applied_decimal_scale": 0.001,
        "add_offset": 0, "mask_before_scaling": True, "decode_count": 1})
    _strings(value["limitations"])
    _strings(metadata["limitations"])


def _advection_shape(value, candidate, origin) -> None:
    _keys(value, {"schema_version", "kind", "status", "reason_code", "requested_horizon_s",
        "completed_horizon_s", "track", "accepted_steps", "solver", "forcing", "physical_validation",
        "plastic_motion_validated", "tank_flow_used", "heldout_buoy_positions_used", "limitations"})
    _require(value["schema_version"] == 1 and value["kind"] == "CURRENT_FORCED_PASSIVE_TRACER"
             and all(value[key] is False for key in ("physical_validation", "plastic_motion_validated",
                 "tank_flow_used", "heldout_buoy_positions_used")), "advection claim boundary changed")
    _equal(value["schema_version"], 1)
    _strings(value["limitations"])
    for key in ("status", "reason_code", "requested_horizon_s", "completed_horizon_s"):
        _equal(value[key], float(candidate[key]) if key.endswith("_s") else candidate[key])
    _keys(value["solver"], {"method", "maximum_step_s", "output_step_s", "spatial_interpolation",
        "temporal_interpolation", "velocity_units", "forcing_time_knots_aligned", "position_units",
        "maximum_steps"})
    _equal(value["solver"], {"method": "RK4_WGS84_METRIC_DERIVATIVES", "maximum_step_s": 300.0,
        "output_step_s": 3600.0, "spatial_interpolation": "bilinear", "temporal_interpolation": "linear",
        "velocity_units": "m/s", "forcing_time_knots_aligned": True,
        "position_units": "geographic_degrees", "maximum_steps": 2048})
    forcing = value["forcing"]
    _keys(forcing, {"time_start_utc", "time_end_utc", "selected_depth_m", "shape", "provenance"})
    _require(forcing["selected_depth_m"] == 15 and _clock(forcing["time_start_utc"]) == ORIGIN
             and _clock(forcing["time_end_utc"]) == ORIGIN + timedelta(hours=6)
             and isinstance(forcing["provenance"], dict)
             and set(forcing["provenance"]) <= {"product", "dataset", "title", "u_variable", "v_variable",
                "sha256", "source_url", "issued_at_utc", "retrieved_at_utc", "license", "data_kind"},
             "advection forcing summary changed")
    _require(isinstance(value["track"], list) and len(value["track"]) <= 8
             and type(value["accepted_steps"]) is int and 0 <= value["accepted_steps"] <= 2048,
             "advection trace budget changed")
    previous = -1
    for point in value["track"]:
        _keys(point, {"time_utc", "elapsed_s", "latitude_deg", "longitude_deg", "eastward_m_s",
                      "northward_m_s", "speed_m_s"})
        elapsed = point["elapsed_s"]
        _require(_number(elapsed) and previous < elapsed <= candidate["completed_horizon_s"]
                 and _clock(point["time_utc"]) == ORIGIN + timedelta(seconds=elapsed),
                 "advection trace clock changed")
        _position(point["latitude_deg"], point["longitude_deg"])
        _require(all(_number(point[key]) for key in ("eastward_m_s", "northward_m_s", "speed_m_s"))
                 and 0 <= point["speed_m_s"] <= 10, "invalid saved velocity")
        previous = elapsed
    if value["track"]:
        first = value["track"][0]
        _require(first["elapsed_s"] == 0 and origin is not None
                 and all(first[key] == origin[key] for key in ("latitude_deg", "longitude_deg")),
                 "advection origin changed")
    points = {point["elapsed_s"]: point for point in value["track"]}
    for cell in candidate["cells"]:
        if cell["forecast_status"] == "AVAILABLE":
            point = points.get(cell["elapsed_s"])
            _require(point is not None and all(point[key] == cell[key] for key in (
                "time_utc", "latitude_deg", "longitude_deg")), "hourly cell lacks its saved solver output")


def _forecast_shape(forecasts: dict) -> None:
    _keys(forecasts, FORECAST_KEYS)
    constants = {"schema_version": 1, "kind": "MATCHED_CURRENT_FORECASTS",
        "origin_time_utc": protocol_io.ORIGIN, "group_ids": list(GROUP_IDS),
        "model_ids": list(MODEL_IDS), "horizons_s": list(HORIZONS), "planned_group_count": 2,
        "planned_cell_count": 36, "planned_distinct_target_count": 12,
        "all_forecasts_built_before_target_decode": True, "future_positions_used": False,
        "coordinate_method": "origin_anchored_mean_sphere_log_exp_50km_last_drift",
        "score_method": "mean_radius_sphere_great_circle_metres", "statistical_independence": False,
        "operational_forecast_skill_verified": False, "physical_validation": False}
    for key, expected in constants.items():
        _equal(forecasts[key], expected)
    canonical = {key: value for key, value in forecasts.items() if key != "forecast_sha256"}
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()
    _require(forecasts["forecast_sha256"] == digest, "inner forecast hash changed")
    _require(isinstance(forecasts["groups"], list) and len(forecasts["groups"]) == 2,
             "both planned forecast groups are required")
    for group_id, group in zip(GROUP_IDS, forecasts["groups"], strict=True):
        _keys(group, {"group_id", "context_count", "origin_position", "candidates"})
        _require(group["group_id"] == group_id and type(group["context_count"]) is int
                 and 0 <= group["context_count"] <= 25, "group identity/count changed")
        if group["origin_position"] is not None:
            origin = group["origin_position"]
            _keys(origin, {"time_utc", "latitude_deg", "longitude_deg"})
            _require(origin["time_utc"] == protocol_io.ORIGIN, "origin time changed")
            _position(origin["latitude_deg"], origin["longitude_deg"])
        _require(isinstance(group["candidates"], list) and len(group["candidates"]) == 3,
                 "all three planned candidates are required")
        for model_id, candidate in zip(MODEL_IDS, group["candidates"], strict=True):
            base = {"model_id", "status", "reason_code", "requested_horizon_s",
                    "completed_horizon_s", "planned_count", "available_count", "context_rows_used",
                    "learned_parameters", "future_positions_used", "cells"}
            optional = {"last_observed_delta_s", "last_observed_velocity_m_s"} if model_id == "last_drift" else {"advection"} if model_id == "current_only" else set()
            _require(isinstance(candidate, dict) and base <= set(candidate)
                     and set(candidate) <= base | optional, "candidate schema changed")
            _require(candidate["model_id"] == model_id and candidate["status"] in {
                "COMPLETED", "PARTIAL", "UNSUPPORTED", "FAILED"}, "candidate identity/status changed")
            for key, expected in {"requested_horizon_s": 21600, "planned_count": 6,
                    "context_rows_used": 2 if model_id == "last_drift" else 1,
                    "learned_parameters": 0, "future_positions_used": False}.items():
                _equal(candidate[key], expected)
            _require(_number(candidate["completed_horizon_s"], nonnegative=True)
                     and candidate["completed_horizon_s"] <= 21600, "invalid supported horizon")
            _reason(candidate["reason_code"], required=candidate["status"] != "COMPLETED")
            _require(isinstance(candidate["cells"], list) and len(candidate["cells"]) == 6,
                     "all six forecast horizons are required")
            available = 0
            for elapsed, cell in zip(HORIZONS, candidate["cells"], strict=True):
                _keys(cell, CELL_KEYS)
                for key, expected in {"elapsed_s": elapsed, "horizon_hours": elapsed // 3600,
                        "time_utc": (ORIGIN + timedelta(seconds=elapsed)).isoformat().replace(
                            "+00:00", "Z")}.items():
                    _equal(cell[key], expected)
                if cell["forecast_status"] == "AVAILABLE":
                    _position(cell["latitude_deg"], cell["longitude_deg"])
                    _require(cell["forecast_reason_code"] is None and group["origin_position"] is not None
                             and elapsed <= candidate["completed_horizon_s"], "unsupported forecast cell")
                    available += 1
                else:
                    _require(cell["forecast_status"] == "UNAVAILABLE"
                             and cell["latitude_deg"] is cell["longitude_deg"] is None,
                             "unavailable forecast contains positions")
                    _reason(cell["forecast_reason_code"], required=True)
            _equal(candidate["available_count"], available)
            if candidate["status"] == "COMPLETED":
                _require(available == 6 and candidate["completed_horizon_s"] == 21600
                         and candidate["reason_code"] is None, "complete forecast is incomplete")
            elif candidate["status"] in {"FAILED", "UNSUPPORTED"}:
                _require(available == 0 and candidate["completed_horizon_s"] == 0,
                         "failed forecast contains available cells")
            else:
                _require(0 < candidate["completed_horizon_s"] < 21600,
                         "partial forecast has no partial supported horizon")
            if "last_observed_delta_s" in candidate or "last_observed_velocity_m_s" in candidate:
                velocity = candidate.get("last_observed_velocity_m_s")
                _require(candidate.get("last_observed_delta_s") == 3600
                         and isinstance(velocity, list) and len(velocity) == 2
                         and all(_number(component) for component in velocity),
                         "last-drift input summary changed")
            if "advection" in candidate:
                _advection_shape(candidate["advection"], candidate, group["origin_position"])


def _metrics(cells: list[dict], planned: int) -> dict:
    errors = [cell["error_m"] for cell in cells if cell["score_status"] == "SCORED"]
    return {"planned_count": planned, "scored_count": len(errors),
        "missing_count": planned - len(errors), "coverage_complete": len(errors) == planned,
        "available_cell_mean_error_m": math.fsum(errors) / len(errors) if errors else None,
        "full_horizon_ade_m": math.fsum(errors) / planned if len(errors) == planned else None,
        "available_cell_summary_is_full_horizon_ade": len(errors) == planned}


def _score_shape(scores: dict, forecasts: dict) -> None:
    _keys(scores, SCORE_KEYS)
    for key, expected in {"schema_version": 1, "kind": "MATCHED_CURRENT_SCORES",
            "origin_time_utc": protocol_io.ORIGIN, "planned_group_count": 2,
            "planned_cell_count": 36, "planned_distinct_target_count": 12,
            "statistical_independence": False, "automatic_winner_selected": False,
            "operational_forecast_skill_verified": False, "physical_validation": False}.items():
        _equal(scores[key], expected)
    _require(scores["forecast_report"] == forecasts, "scoring changed frozen forecasts")
    _strings(scores["limitations"])
    _require(isinstance(scores["groups"], list) and len(scores["groups"]) == 2,
             "both score groups are required")
    all_cells = {model: [] for model in MODEL_IDS}
    for group_id, group, prior in zip(GROUP_IDS, scores["groups"], forecasts["groups"], strict=True):
        _keys(group, {"group_id", "target_issues", "candidates"})
        _require(group["group_id"] == group_id and isinstance(group["target_issues"], list)
                 and isinstance(group["candidates"], list) and len(group["candidates"]) == 3,
                 "score group identity/schema changed")
        for issue in group["target_issues"]:
            _require(isinstance(issue, dict) and "reason_code" in issue
                     and set(issue) <= {"reason_code", "row_index", "time_utc"},
                     "target issue schema changed")
            _reason(issue["reason_code"], required=True)
            if "row_index" in issue:
                _require(type(issue["row_index"]) is int and 0 <= issue["row_index"] < 6,
                         "target issue index changed")
            if "time_utc" in issue:
                _clock(issue["time_utc"])
        target_reference = None
        for model_id, candidate, predicted in zip(MODEL_IDS, group["candidates"], prior["candidates"], strict=True):
            _keys(candidate, {"model_id", "prediction_status", "prediction_reason_code", "metrics", "cells"})
            _require(candidate["model_id"] == model_id
                     and candidate["prediction_status"] == predicted["status"]
                     and candidate["prediction_reason_code"] == predicted["reason_code"]
                     and isinstance(candidate["cells"], list) and len(candidate["cells"]) == 6,
                     "scored candidate disagrees with forecast")
            targets = []
            for cell, old in zip(candidate["cells"], predicted["cells"], strict=True):
                _keys(cell, SCORED_CELL_KEYS)
                _require({key: cell[key] for key in CELL_KEYS} == old
                         and cell["group_id"] == group_id and cell["model_id"] == model_id,
                         "scored cell changed forecast identity")
                if cell["target_status"] == "AVAILABLE":
                    _position(cell["target_latitude_deg"], cell["target_longitude_deg"])
                    _require(cell["target_reason_code"] is None, "available target has failure reason")
                else:
                    _require(cell["target_status"] == "UNAVAILABLE"
                             and cell["target_latitude_deg"] is cell["target_longitude_deg"] is None,
                             "unavailable target contains positions")
                    _reason(cell["target_reason_code"], required=True)
                targets.append({key: cell[key] for key in (
                    "target_status", "target_reason_code", "target_latitude_deg", "target_longitude_deg")})
                expected = ("FORECAST_UNAVAILABLE" if cell["forecast_status"] != "AVAILABLE" else
                            "TARGET_UNAVAILABLE" if cell["target_status"] != "AVAILABLE" else "SCORED")
                _require(cell["score_status"] == expected, "score availability disagrees with cell")
                _require(_number(cell["error_m"], nonnegative=True) if expected == "SCORED"
                         else cell["error_m"] is None, "missing score became zero or invalid error")
            _require(target_reference is None or targets == target_reference,
                     "models disagree about shared future targets")
            target_reference = targets
            cells = candidate["cells"]
            prefix = list(itertools.takewhile(lambda cell: cell["score_status"] == "SCORED", cells))
            metrics = {**_metrics(cells, 6), "endpoint_fde_m": cells[-1]["error_m"],
                "endpoint_scored": cells[-1]["score_status"] == "SCORED",
                "scored_prefix_count": len(prefix),
                "scored_prefix_hours": [cell["horizon_hours"] for cell in prefix],
                "scored_prefix_mean_error_m": math.fsum(cell["error_m"] for cell in prefix) / len(prefix)
                if prefix else None, "prefix_is_full_horizon": len(prefix) == 6}
            _equal(candidate["metrics"], metrics)
            all_cells[model_id].extend(cells)
    _require(isinstance(scores["models"], list) and len(scores["models"]) == 3,
             "three aggregate models are required")
    for model_id, model in zip(MODEL_IDS, scores["models"], strict=True):
        cells = all_cells[model_id]
        horizons = []
        for elapsed in HORIZONS:
            metrics = _metrics([cell for cell in cells if cell["elapsed_s"] == elapsed], 2)
            horizons.append({"horizon_hours": elapsed // 3600, "planned_group_count": 2,
                "scored_group_count": metrics["scored_count"], "coverage_complete": metrics["coverage_complete"],
                "available_group_mean_error_m": metrics["available_cell_mean_error_m"],
                "complete_group_mean_error_m": metrics["full_horizon_ade_m"]})
        _equal(model, {"model_id": model_id, "metrics": _metrics(cells, 12), "per_horizon": horizons})
    paired = []
    for a, b in itertools.combinations(MODEL_IDS, 2):
        common = [{"group_id": left["group_id"], "time_utc": left["time_utc"],
                   "horizon_hours": left["horizon_hours"], "error_a_m": left["error_m"],
                   "error_b_m": right["error_m"]}
                  for left, right in zip(all_cells[a], all_cells[b], strict=True)
                  if left["score_status"] == right["score_status"] == "SCORED"]
        paired.append({"model_a": a, "model_b": b, "planned_common_cell_count": 12,
            "common_scored_count": len(common), "coverage_complete": len(common) == 12,
            "analysis_scope": "SECONDARY_COMMON_AVAILABLE_CELLS",
            "mean_error_a_m": math.fsum(cell["error_a_m"] for cell in common) / len(common) if common else None,
            "mean_error_b_m": math.fsum(cell["error_b_m"] for cell in common) / len(common) if common else None,
            "mean_delta_a_minus_b_m": math.fsum(cell["error_a_m"] - cell["error_b_m"] for cell in common) / len(common) if common else None,
            "cells": common})
    _equal(scores["paired_comparisons"], paired)
    count = sum(cell["score_status"] == "SCORED" for cells in all_cells.values() for cell in cells)
    _equal(scores["scored_cell_count"], count)
    complete = count == 36
    _equal(scores["primary_common_cohort_complete"], complete)
    if not complete:
        _require(scores["primary_equal_id_macro_results"] is scores["primary_paired_comparisons"] is None,
                 "incomplete common cohort cannot have primary results")
    else:
        primary = []
        for index, model_id in enumerate(MODEL_IDS):
            groups = [group["candidates"][index] for group in scores["groups"]]
            primary.append({"model_id": model_id, "group_count": 2,
                "equal_id_macro_ade_m": math.fsum(group["metrics"]["full_horizon_ade_m"] for group in groups) / 2,
                "equal_id_macro_fde_m": math.fsum(group["metrics"]["endpoint_fde_m"] for group in groups) / 2,
                "per_horizon_mean_error_m": [{"horizon_hours": index + 1,
                    "error_m": math.fsum(group["cells"][index]["error_m"] for group in groups) / 2}
                    for index in range(6)]})
        _equal(scores["primary_equal_id_macro_results"], primary)
        _equal(scores["primary_paired_comparisons"], [
            {**pair, "analysis_scope": "PRIMARY_COMPLETE_COMMON_COHORT"} for pair in paired])


def _load_result(
    directory=None, *, root=None, expected_report_sha256=None, allow_unpinned_local=False,
    study_version="v1",
) -> dict:
    """Read one pinned result without executing any forecast or first-score path.

    Missing artifacts/identity raise FileNotFoundError; corrupt lineage, shapes or
    clocks raise ValueError. FORECAST_SHA256 in the trusted result identity is the
    outer forecasts.json file hash, not its inner forecast-content digest.
    """
    _require(type(allow_unpinned_local) is bool, "local-only opt-in must be boolean")
    selected_protocol, _, default_directory = _version_contract(study_version)
    root = Path(root or selected_protocol.ROOT)
    directory = Path(directory or root / default_directory)
    _require(not directory.is_symlink(), "symlinked study directory is not accepted")
    pins, pin_source, result_identity_hash = _result_pin(
        root, expected_report_sha256, allow_unpinned_local, study_version=study_version)
    protocol, manifest, hashes, _sources = selected_protocol.load_acquisition(directory, root=root)
    if manifest is None:
        raise FileNotFoundError("Matched-current acquisition is not available")
    lineage = {key: value for key, value in hashes.items() if key.endswith("sha256")}
    forecast, forecast_file_hash = _pinned(directory, "forecasts", pins.get("FORECAST_SHA256"))
    report, report_hash = _pinned(directory, "evaluation", pins.get("REPORT_SHA256"))
    _keys(forecast, {"schema_version", "kind", "study_id", "lineage", "forecasts",
                     "future_coordinates_decoded", "frozen_at_utc"})
    _keys(report, REPORT_KEYS)
    _require(forecast["schema_version"] == report["schema_version"] == 1
             and forecast["kind"] == "FROZEN_MATCHED_CURRENT_FORECASTS"
             and report["kind"] == "MATCHED_CURRENT_RETROSPECTIVE_DIAGNOSTIC"
             and forecast["study_id"] == report["study_id"] == selected_protocol.STUDY_ID,
             "study kind/identity changed")
    _equal(forecast["schema_version"], 1)
    _equal(report["schema_version"], 1)
    _require(forecast["lineage"] == report["lineage"] == lineage
             and all(_hash(value) for value in lineage.values())
             and {"protocol_sha256", "trusted_identity_sha256", "manifest_sha256",
                  "acquisition_start_sha256"} <= set(lineage), "artifact lineage changed")
    _require(pins.get("MANIFEST_SHA256", hashes["manifest_sha256"]) == hashes["manifest_sha256"],
             "trusted acquisition manifest changed")
    _require(forecast["future_coordinates_decoded"] is False
             and report["forecasts_saved_before_target_coordinate_decode"] is True,
             "forecast/target isolation declaration changed")
    _require(report["forecast_file_sha256"] == forecast_file_hash
             and report["forecast_frozen_at_utc"] == forecast["frozen_at_utc"],
             "evaluation does not bind its frozen forecasts")
    frozen = _clock(forecast["frozen_at_utc"])
    _require(_clock(protocol["frozen_at_utc"]) <= _clock(manifest["finished_at_utc"]) <= frozen
             <= _clock(report["scored_at_utc"])
             and all(_clock(receipt["finished_at_utc"]) <= frozen
                     for receipt in manifest["source_receipts"]), "acquisition/forecast/score chronology changed")
    _require(report["source_receipts"] == manifest["source_receipts"]
             and all(report[flag] is False for flag in FALSE_FLAGS), "evidence or claim boundaries changed")
    receipt_keys = {"role", "status", "reason", "source_url", "raw_path", "sha256", "bytes",
        "received_bytes", "retained_bytes", "request_attempted", "http_status", "response_complete",
        "content_type", "content_encoding", "started_at_utc", "finished_at_utc", "elapsed_wall_s"}
    for receipt in report["source_receipts"]:
        _keys(receipt, receipt_keys)
    _forecast_shape(forecast["forecasts"])
    _score_shape(report["scores"], forecast["forecasts"])
    _require(isinstance(report["context_qc"], dict) and set(report["context_qc"]) == set(GROUP_IDS),
             "both descriptive context QC groups are required")
    for qc in report["context_qc"].values():
        _keys(qc, {"planned_context_rows", "received_context_rows", "invalid_coordinate_indices",
                   "used_as_whole_group_admission_gate", "first_23_positions_used_by_models"})
        _require(qc["planned_context_rows"] == 25 and type(qc["received_context_rows"]) is int
                 and 0 <= qc["received_context_rows"] <= 25
                 and qc["used_as_whole_group_admission_gate"] is False
                 and qc["first_23_positions_used_by_models"] is False
                 and isinstance(qc["invalid_coordinate_indices"], list)
                 and all(type(index) is int and 0 <= index < qc["received_context_rows"]
                         for index in qc["invalid_coordinate_indices"])
                 and qc["invalid_coordinate_indices"] == sorted(set(qc["invalid_coordinate_indices"])),
                 "descriptive context QC changed")
    for group in forecast["forecasts"]["groups"]:
        _require(report["context_qc"][group["group_id"]]["received_context_rows"]
                 == group["context_count"], "context QC disagrees with frozen context count")
    _require(report["current_field"] is None or isinstance(report["current_field"], dict),
             "current field summary changed")
    _reason(report["current_field_failure"], required=report["current_field"] is None)
    if report["current_field"] is not None:
        receipt = next(row for row in manifest["source_receipts"] if row["role"] == "hycom_currents")
        _require(receipt["status"] == "DOWNLOADED" and report["current_field_failure"] is None,
                 "current summary contradicts acquisition/failure evidence")
        _field_shape(report["current_field"], receipt)
        for group in forecast["forecasts"]["groups"]:
            advection = group["candidates"][2].get("advection")
            if advection is not None:
                _require(advection["forcing"]["shape"] == report["current_field"]["shape"]
                         and advection["forcing"]["provenance"].get("sha256") == receipt["sha256"],
                         "advection forcing differs from the acquired field")
    # Re-read frozen identity/files after validation so a concurrent replacement
    # is rejected, rather than returning mixed artifact generations.
    _, latest_manifest, latest_hashes, _ = selected_protocol.load_acquisition(directory, root=root)
    _require(latest_hashes == hashes and latest_manifest == manifest
             and _pinned(directory, "forecasts", forecast_file_hash)[0] == forecast
             and _pinned(directory, "evaluation", report_hash)[0] == report,
             "frozen artifacts changed while being read")
    _require(_result_pin(root, expected_report_sha256, allow_unpinned_local, study_version=study_version)
             == (pins, pin_source, result_identity_hash), "trusted result pin changed while being read")
    return {"report": copy.deepcopy({key: report[key] for key in REPORT_KEYS}),
        "artifact_identity": {"schema_version": 1, "study_id": selected_protocol.STUDY_ID,
            "report_sha256": report_hash, "forecast_file_sha256": forecast_file_hash,
            "forecast_sha256": forecast["forecasts"]["forecast_sha256"],
            "protocol_sha256": hashes["protocol_sha256"],
            "trusted_protocol_identity_sha256": hashes["trusted_identity_sha256"],
            "manifest_sha256": hashes["manifest_sha256"],
            "acquisition_start_sha256": hashes["acquisition_start_sha256"],
            "integrity_verified": True, "numeric_replay_verified": False,
            "verification_scope": "FROZEN_ARTIFACT_LINEAGE_AND_STRUCTURE_NOT_NUMERIC_REPLAY",
            "result_pin_verified": bool(pins), "pin_source": pin_source,
            "result_identity_file_sha256": result_identity_hash}}


def load_frozen_matched_current_result(
    directory=None, *, root=None, expected_report_sha256=None, allow_unpinned_local=False,
    study_version="v1",
) -> dict:
    """Read pinned, already scored evidence; never execute acquisition or scoring.

    FileNotFoundError means missing saved evidence/identity. Invalid scientific
    structure or lineage raises ValueError, including malformed nested types.
    Defaults require the trusted result identity; local-only unpinned reads are
    explicitly marked and are not suitable for a public/API handler.
    """
    try:
        return _load_result(directory, root=root, expected_report_sha256=expected_report_sha256,
                            allow_unpinned_local=allow_unpinned_local, study_version=study_version)
    except (KeyError, TypeError, IndexError, OverflowError, RecursionError) as error:
        raise ValueError("Frozen matched-current result: malformed artifact structure") from error
