"""Offline, fixed-denominator GDP/HYCOM feasibility comparison primitives.

Frozen input/report interface, schema v1:
* The two GROUP_IDS, ORIGIN_TIME_UTC, MODEL_IDS and six HORIZONS_S are fixed.
* Context/target rows are mappings with ``time_utc``, ``latitude_deg`` and
  ``longitude_deg``; coordinates may be finite numbers or numeric CSV strings.
  An optional ``drifter_id`` must agree with the enclosing group.
* ``build_matched_current_forecasts`` accepts context and fields only. It never
  receives reserved positions. The first 23 context rows are not model inputs;
  full context QC belongs to the acquisition/orchestration layer.
* ``score_matched_current_forecasts`` consumes the completed forecast report and
  only then decodes reserved positions. It returns a separate score report and
  does not change forecasts. ``evaluate_matched_current`` enforces this order.
* All 2 groups x 3 candidates x 6 hourly cells survive failures. Full-six-hour
  ADE requires six scored cells; endpoint FDE requires the six-hour cell. Partial
  cell/prefix summaries and paired denominators are explicit, never substitutes.

These are retrospective forcing-supported diagnostics, not operational skill,
plastic/reef/tank validation, a fitted ML model, or independent observations.
There are no network calls, coefficient fitting, or learned/global state here.
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from numbers import Real
from typing import Any, TypedDict

import numpy as np

from .advection import advect_current
from .benchmark import SphericalLocalFrame, great_circle_distance_m
from .field import OceanField

SCHEMA_VERSION = 1
GROUP_IDS = ("300234066836710", "300534061292930")
MODEL_IDS = ("stationary", "last_drift", "current_only")
ORIGIN_TIME_UTC = "2022-06-01T00:00:00Z"
ORIGIN = datetime(2022, 6, 1, tzinfo=UTC)
CONTEXT_COUNT = 25
CONTEXT_STEP_S = 3600
HORIZONS_S = tuple(hour * 3600 for hour in range(1, 7))
PLANNED_CELLS = len(GROUP_IDS) * len(MODEL_IDS) * len(HORIZONS_S)
PLANNED_DISTINCT_TARGETS = len(GROUP_IDS) * len(HORIZONS_S)


class PositionInput(TypedDict):
    time_utc: str | datetime
    latitude_deg: float | str
    longitude_deg: float | str


class _PositionInputError(ValueError):
    """Malformed scientific rows are recorded as data-validation failures."""


def _iso(when: datetime) -> str:
    return when.isoformat().replace("+00:00", "Z")


def _when(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError("INVALID_TIME") from error
    if (not isinstance(value, datetime) or value.utcoffset() is None
            or value.utcoffset() != timedelta(0)):
        raise ValueError("INVALID_TIME")
    return value.astimezone(UTC)


def _number(value: Any) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (Real, str)):
        raise _PositionInputError("INVALID_COORDINATE")
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError("INVALID_COORDINATE") from error
    if not math.isfinite(result):
        raise ValueError("INVALID_COORDINATE")
    return result


def _position(row: Any, group_id: str) -> tuple[datetime, float, float]:
    if not isinstance(row, Mapping):
        raise _PositionInputError("INVALID_POSITION_ROW")
    if "drifter_id" in row and row["drifter_id"] != group_id:
        raise ValueError("ID_MISMATCH")
    when = _when(row.get("time_utc"))
    latitude = _number(row.get("latitude_deg"))
    longitude = _number(row.get("longitude_deg"))
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("INVALID_COORDINATE")
    return when, latitude, longitude


def _cell(horizon_s: int) -> dict:
    return {
        "horizon_hours": horizon_s // 3600,
        "elapsed_s": horizon_s,
        "time_utc": _iso(ORIGIN + timedelta(seconds=horizon_s)),
        "forecast_status": "UNAVAILABLE",
        "forecast_reason_code": None,
        "latitude_deg": None,
        "longitude_deg": None,
    }


def _candidate(model_id: str) -> dict:
    return {
        "model_id": model_id,
        "status": "UNSUPPORTED",
        "reason_code": None,
        "requested_horizon_s": HORIZONS_S[-1],
        "completed_horizon_s": 0.0,
        "planned_count": len(HORIZONS_S),
        "available_count": 0,
        "context_rows_used": 2 if model_id == "last_drift" else 1,
        "learned_parameters": 0,
        "future_positions_used": False,
        "cells": [_cell(horizon) for horizon in HORIZONS_S],
    }


def forecast_sha256(report: dict) -> str:
    """Canonical forecast identity, excluding only its own digest field."""
    content = {key: value for key, value in report.items() if key != "forecast_sha256"}
    return hashlib.sha256(json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _fail(candidate: dict, reason: str, *, status: str = "FAILED") -> None:
    candidate["status"] = status
    candidate["reason_code"] = reason
    for cell in candidate["cells"]:
        if cell["forecast_status"] != "AVAILABLE":
            cell["forecast_reason_code"] = reason


def _put(cell: dict, latitude: float, longitude: float) -> None:
    cell.update({
        "forecast_status": "AVAILABLE", "forecast_reason_code": None,
        "latitude_deg": float(latitude), "longitude_deg": float(longitude),
    })


def _last_drift(candidate: dict, context: Sequence, group_id: str,
                origin_position: tuple[float, float]) -> None:
    try:
        before_time, before_lat, before_lon = _position(context[-2], group_id)
        dt = (ORIGIN - before_time).total_seconds()
        if dt <= 0:
            raise ValueError("NONPOSITIVE_CONTEXT_DELTA")
        if dt != CONTEXT_STEP_S:
            raise ValueError("CONTEXT_CADENCE_MISMATCH")
        frame = SphericalLocalFrame(*origin_position)
        velocity = -frame.to_xy(before_lat, before_lon) / dt
        candidate["last_observed_delta_s"] = dt
        candidate["last_observed_velocity_m_s"] = velocity.tolist()
    except ValueError as error:
        reason = str(error)
        if "50 km" in reason:
            reason = "LOCAL_GEOMETRY_BUDGET_EXCEEDED"
        _fail(candidate, reason)
        return
    for cell in candidate["cells"]:
        try:
            latitude, longitude = frame.to_latlon(velocity * cell["elapsed_s"])
        except ValueError:
            _fail(candidate, "LOCAL_GEOMETRY_BUDGET_EXCEEDED",
                  status="PARTIAL" if candidate["available_count"] else "UNSUPPORTED")
            return
        _put(cell, latitude, longitude)
        candidate["available_count"] += 1
        candidate["completed_horizon_s"] = float(cell["elapsed_s"])
    candidate["status"] = "COMPLETED"


def _current(candidate: dict, field: OceanField | None,
             origin_position: tuple[float, float], failure: str | None) -> None:
    if field is None:
        _fail(candidate, failure or "CURRENT_FIELD_UNAVAILABLE", status="UNSUPPORTED")
        return
    try:
        result = advect_current(
            field, latitude_deg=origin_position[0], longitude_deg=origin_position[1],
            start_time_utc=ORIGIN, horizon_s=HORIZONS_S[-1], step_s=300,
            output_step_s=3600,
        )
    except (ValueError, TypeError, OverflowError):
        _fail(candidate, "CURRENT_CONFIGURATION_INVALID")
        return
    candidate["advection"] = result
    candidate["status"] = result["status"]
    candidate["reason_code"] = result["reason_code"]
    candidate["completed_horizon_s"] = result["completed_horizon_s"]
    # No nearest point, interpolation, clamping or projection of a partial tail
    # into an unobserved hourly output. The solver explicitly emits these times.
    accepted = {point["elapsed_s"]: point for point in result["track"]}
    for cell in candidate["cells"]:
        point = accepted.get(cell["elapsed_s"])
        if point is not None:
            _put(cell, point["latitude_deg"], point["longitude_deg"])
            candidate["available_count"] += 1
        else:
            cell["forecast_reason_code"] = result["reason_code"] or "HOURLY_OUTPUT_UNAVAILABLE"


def build_matched_current_forecasts(
    context_by_group: Mapping[str, Sequence[PositionInput]],
    current_fields_by_group: Mapping[str, OceanField] | None = None,
    *,
    failures_by_group: Mapping[str, str] | None = None,
    current_failures_by_group: Mapping[str, str] | None = None,
) -> dict:
    """Build all 36 forecast cells without receiving/decoding reserved targets.

    ``failures_by_group`` describes context transport/identity failures when a
    context is absent. ``current_failures_by_group`` describes current transport
    failures independently. Unused/extraneous group keys are rejected, not added
    to the planned cohort. Missing fixed groups remain six-cell candidate rows.
    """
    supplied = (context_by_group, current_fields_by_group or {}, failures_by_group or {},
                current_failures_by_group or {})
    if any(not isinstance(item, Mapping) for item in supplied):
        raise ValueError("Group inputs must be mappings")
    if any(set(item) - set(GROUP_IDS) for item in supplied):
        raise ValueError("Only the two fixed group IDs are allowed")
    # Allocate the entire Cartesian plan before even the first candidate attempt.
    groups = [{"group_id": group_id, "context_count": 0, "origin_position": None,
               "candidates": [_candidate(model_id) for model_id in MODEL_IDS]}
              for group_id in GROUP_IDS]
    for group in groups:
        group_id = group["group_id"]
        context = context_by_group.get(group_id)
        candidates = group["candidates"]
        if isinstance(context, Sequence) and not isinstance(context, (str, bytes)):
            group["context_count"] = len(context)
        if (not isinstance(context, Sequence) or isinstance(context, (str, bytes))
                or len(context) != CONTEXT_COUNT):
            reason = (failures_by_group or {}).get(group_id, "CONTEXT_COUNT_INVALID")
            for candidate in candidates:
                _fail(candidate, reason)
            continue
        try:
            when, latitude, longitude = _position(context[-1], group_id)
            if when != ORIGIN:
                raise ValueError("ORIGIN_TIME_MISMATCH")
        except ValueError as error:
            for candidate in candidates:
                _fail(candidate, f"ORIGIN_{error}")
            continue
        origin = (latitude, longitude)
        group["origin_position"] = {
            "time_utc": ORIGIN_TIME_UTC, "latitude_deg": latitude, "longitude_deg": longitude,
        }
        stationary, last_drift, current = candidates
        for cell in stationary["cells"]:
            _put(cell, latitude, longitude)
        stationary.update({"status": "COMPLETED", "completed_horizon_s": HORIZONS_S[-1],
                           "available_count": len(HORIZONS_S)})
        _last_drift(last_drift, context, group_id, origin)
        _current(current, (current_fields_by_group or {}).get(group_id), origin,
                 (current_failures_by_group or {}).get(group_id))
    report = {
        "schema_version": SCHEMA_VERSION, "kind": "MATCHED_CURRENT_FORECASTS",
        "origin_time_utc": ORIGIN_TIME_UTC,
        "group_ids": list(GROUP_IDS), "model_ids": list(MODEL_IDS),
        "horizons_s": list(HORIZONS_S), "planned_group_count": len(GROUP_IDS),
        "planned_cell_count": PLANNED_CELLS,
        "planned_distinct_target_count": PLANNED_DISTINCT_TARGETS,
        "all_forecasts_built_before_target_decode": True,
        "future_positions_used": False,
        "coordinate_method": "origin_anchored_mean_sphere_log_exp_50km_last_drift",
        "score_method": "mean_radius_sphere_great_circle_metres",
        "statistical_independence": False, "operational_forecast_skill_verified": False,
        "physical_validation": False, "groups": groups,
    }
    report["forecast_sha256"] = forecast_sha256(report)
    return report


def _validate_forecasts(report: dict) -> None:
    if (not isinstance(report, dict) or report.get("schema_version") != SCHEMA_VERSION
            or report.get("kind") != "MATCHED_CURRENT_FORECASTS"
            or report.get("origin_time_utc") != ORIGIN_TIME_UTC
            or report.get("group_ids") != list(GROUP_IDS)
            or report.get("model_ids") != list(MODEL_IDS)
            or report.get("horizons_s") != list(HORIZONS_S)
            or report.get("planned_cell_count") != PLANNED_CELLS
            or report.get("all_forecasts_built_before_target_decode") is not True):
        raise ValueError("A complete fixed-schema forecast report is required before scoring")
    if report.get("forecast_sha256") != forecast_sha256(report):
        raise ValueError("Forecast hash does not match the frozen prior forecasts")
    groups = report.get("groups", [])
    if len(groups) != len(GROUP_IDS):
        raise ValueError("Both fixed forecast groups must exist before scoring")
    for group_id, group in zip(GROUP_IDS, groups, strict=True):
        candidates = group.get("candidates", [])
        if group.get("group_id") != group_id or len(candidates) != len(MODEL_IDS):
            raise ValueError("All fixed candidate forecasts must exist before scoring")
        for model_id, candidate in zip(MODEL_IDS, candidates, strict=True):
            cells = candidate.get("cells", [])
            if candidate.get("model_id") != model_id or len(cells) != len(HORIZONS_S):
                raise ValueError("All six hourly forecast cells must exist before scoring")
            available = 0
            for horizon, cell in zip(HORIZONS_S, cells, strict=True):
                if (cell.get("elapsed_s") != horizon or cell.get("horizon_hours") != horizon // 3600
                        or cell.get("time_utc") != _iso(ORIGIN + timedelta(seconds=horizon))):
                    raise ValueError("Forecast cell coordinates must match the fixed schedule")
                if cell.get("forecast_status") == "AVAILABLE":
                    _position(cell, group_id)
                    available += 1
                elif (cell.get("forecast_status") != "UNAVAILABLE"
                      or cell.get("latitude_deg") is not None
                      or cell.get("longitude_deg") is not None):
                    raise ValueError("Unavailable forecast cells cannot contain invented positions")
            if candidate.get("available_count") != available:
                raise ValueError("Forecast available_count does not match its cells")


def _targets(rows: Any, group_id: str) -> tuple[dict[str, tuple | str], list[dict]]:
    """Decode reserved numbers only after the caller validated all forecasts."""
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return {}, [{"reason_code": "TARGET_ROWS_UNAVAILABLE"}]
    expected = {_iso(ORIGIN + timedelta(seconds=horizon)) for horizon in HORIZONS_S}
    indexed: dict[str, list] = {}
    issues = []
    for index, row in enumerate(rows):
        try:
            if not isinstance(row, Mapping):
                raise _PositionInputError("INVALID_POSITION_ROW")
            when = _iso(_when(row.get("time_utc")))
        except ValueError as error:
            issues.append({"row_index": index, "reason_code": f"TARGET_{error}"})
            continue
        if when not in expected:
            issues.append({"row_index": index, "time_utc": when,
                           "reason_code": "UNEXPECTED_TARGET_TIME"})
            continue
        indexed.setdefault(when, []).append(row)
    decoded = {}
    for when, matching in indexed.items():
        if len(matching) != 1:
            decoded[when] = "DUPLICATE_TARGET_TIME"
            issues.append({"time_utc": when, "reason_code": "DUPLICATE_TARGET_TIME"})
            continue
        try:
            _, latitude, longitude = _position(matching[0], group_id)
            decoded[when] = (latitude, longitude)
        except ValueError as error:
            decoded[when] = f"TARGET_{error}"
            issues.append({"time_utc": when, "reason_code": decoded[when]})
    return decoded, issues


def _metrics(cells: list[dict], planned: int) -> dict:
    scored = [cell for cell in cells if cell["score_status"] == "SCORED"]
    errors = [cell["error_m"] for cell in scored]
    return {
        "planned_count": planned, "scored_count": len(scored),
        "missing_count": planned - len(scored), "coverage_complete": len(scored) == planned,
        "available_cell_mean_error_m": math.fsum(errors) / len(errors) if errors else None,
        "full_horizon_ade_m": math.fsum(errors) / planned if len(scored) == planned else None,
        "available_cell_summary_is_full_horizon_ade": len(scored) == planned,
    }


def score_matched_current_forecasts(
    forecasts: dict, reserved_targets_by_group: Mapping[str, Sequence[PositionInput]],
) -> dict:
    """Score immutable prior forecasts; retain missing/bad targets and all cells."""
    _validate_forecasts(forecasts)
    if (not isinstance(reserved_targets_by_group, Mapping)
            or set(reserved_targets_by_group) - set(GROUP_IDS)):
        raise ValueError("Reserved targets must be keyed by the two fixed group IDs")
    groups = []
    all_cells: dict[str, list[dict]] = {model_id: [] for model_id in MODEL_IDS}
    for group in forecasts["groups"]:
        group_id = group["group_id"]
        targets, issues = _targets(reserved_targets_by_group.get(group_id), group_id)
        candidates = []
        for forecast in group["candidates"]:
            cells = []
            for predicted in forecast["cells"]:
                cell = copy.deepcopy(predicted)
                cell["group_id"] = group_id
                cell["model_id"] = forecast["model_id"]
                target = targets.get(cell["time_utc"], "MISSING_TARGET")
                cell["target_status"] = "AVAILABLE" if isinstance(target, tuple) else "UNAVAILABLE"
                cell["target_reason_code"] = None if isinstance(target, tuple) else target
                cell["target_latitude_deg"] = target[0] if isinstance(target, tuple) else None
                cell["target_longitude_deg"] = target[1] if isinstance(target, tuple) else None
                cell["error_m"] = None
                if cell["forecast_status"] != "AVAILABLE":
                    cell["score_status"] = "FORECAST_UNAVAILABLE"
                elif not isinstance(target, tuple):
                    cell["score_status"] = "TARGET_UNAVAILABLE"
                else:
                    cell["score_status"] = "SCORED"
                    cell["error_m"] = great_circle_distance_m(
                        (cell["latitude_deg"], cell["longitude_deg"]), target,
                    )
                cells.append(cell)
            metrics = _metrics(cells, len(HORIZONS_S))
            prefix = list(itertools.takewhile(lambda cell: cell["score_status"] == "SCORED", cells))
            metrics.update({
                "endpoint_fde_m": cells[-1]["error_m"],
                "endpoint_scored": cells[-1]["score_status"] == "SCORED",
                "scored_prefix_count": len(prefix),
                "scored_prefix_hours": [cell["horizon_hours"] for cell in prefix],
                "scored_prefix_mean_error_m": (
                    math.fsum(cell["error_m"] for cell in prefix) / len(prefix) if prefix else None
                ),
                "prefix_is_full_horizon": len(prefix) == len(HORIZONS_S),
            })
            candidates.append({"model_id": forecast["model_id"],
                               "prediction_status": forecast["status"],
                               "prediction_reason_code": forecast["reason_code"],
                               "metrics": metrics, "cells": cells})
            all_cells[forecast["model_id"]].extend(cells)
        groups.append({"group_id": group_id, "target_issues": issues, "candidates": candidates})
    models = []
    for model_id, cells in all_cells.items():
        horizons = []
        for horizon in HORIZONS_S:
            selected = [cell for cell in cells if cell["elapsed_s"] == horizon]
            metrics = _metrics(selected, len(GROUP_IDS))
            horizons.append({
                "horizon_hours": horizon // 3600,
                "planned_group_count": len(GROUP_IDS), "scored_group_count": metrics["scored_count"],
                "coverage_complete": metrics["coverage_complete"],
                "available_group_mean_error_m": metrics["available_cell_mean_error_m"],
                "complete_group_mean_error_m": metrics["full_horizon_ade_m"],
            })
        models.append({"model_id": model_id, "metrics": _metrics(cells, PLANNED_DISTINCT_TARGETS),
                       "per_horizon": horizons})
    paired = []
    for model_a, model_b in itertools.combinations(MODEL_IDS, 2):
        common = []
        for cell_a, cell_b in zip(all_cells[model_a], all_cells[model_b], strict=True):
            if cell_a["score_status"] == cell_b["score_status"] == "SCORED":
                common.append({"group_id": cell_a["group_id"], "time_utc": cell_a["time_utc"],
                               "horizon_hours": cell_a["horizon_hours"],
                               "error_a_m": cell_a["error_m"], "error_b_m": cell_b["error_m"]})
        paired.append({
            "model_a": model_a, "model_b": model_b,
            "planned_common_cell_count": PLANNED_DISTINCT_TARGETS,
            "common_scored_count": len(common),
            "coverage_complete": len(common) == PLANNED_DISTINCT_TARGETS,
            "analysis_scope": "SECONDARY_COMMON_AVAILABLE_CELLS",
            "mean_error_a_m": math.fsum(cell["error_a_m"] for cell in common) / len(common)
            if common else None,
            "mean_error_b_m": math.fsum(cell["error_b_m"] for cell in common) / len(common)
            if common else None,
            "mean_delta_a_minus_b_m": math.fsum(
                cell["error_a_m"] - cell["error_b_m"] for cell in common
            ) / len(common) if common else None,
            "cells": common,
        })
    complete = sum(model["metrics"]["scored_count"] for model in models) == PLANNED_CELLS
    primary = None
    if complete:
        primary = []
        for model_index, model_id in enumerate(MODEL_IDS):
            metrics = [group["candidates"][model_index]["metrics"] for group in groups]
            primary.append({
                "model_id": model_id, "group_count": len(GROUP_IDS),
                "equal_id_macro_ade_m": math.fsum(
                    metric["full_horizon_ade_m"] for metric in metrics
                ) / len(GROUP_IDS),
                "equal_id_macro_fde_m": math.fsum(
                    metric["endpoint_fde_m"] for metric in metrics
                ) / len(GROUP_IDS),
                "per_horizon_mean_error_m": [
                    {"horizon_hours": horizon // 3600,
                     "error_m": math.fsum(group["candidates"][model_index]["cells"][index]["error_m"]
                                          for group in groups) / len(GROUP_IDS)}
                    for index, horizon in enumerate(HORIZONS_S)
                ],
            })
    primary_paired = copy.deepcopy(paired) if complete else None
    if primary_paired is not None:
        for pair in primary_paired:
            pair["analysis_scope"] = "PRIMARY_COMPLETE_COMMON_COHORT"
    return {
        "schema_version": SCHEMA_VERSION, "kind": "MATCHED_CURRENT_SCORES",
        "origin_time_utc": ORIGIN_TIME_UTC,
        "planned_group_count": len(GROUP_IDS), "planned_cell_count": PLANNED_CELLS,
        "scored_cell_count": sum(model["metrics"]["scored_count"] for model in models),
        "planned_distinct_target_count": PLANNED_DISTINCT_TARGETS,
        "forecast_report": copy.deepcopy(forecasts), "groups": groups,
        "models": models, "paired_comparisons": paired,
        "primary_common_cohort_complete": complete,
        "primary_equal_id_macro_results": primary,
        "primary_paired_comparisons": primary_paired,
        "statistical_independence": False, "automatic_winner_selected": False,
        "operational_forecast_skill_verified": False, "physical_validation": False,
        "limitations": [
            "The 36 model/horizon cells reuse only 12 processed GDP position estimates.",
            "Paired errors describe only explicitly listed common available cells.",
            "Whole-group exclusion does not prove independence from HYCOM assimilation.",
            "Retrospective future-valid forcing lacks a verified historical issue-time cutoff.",
            "No plastic source, reef protection, tank accuracy or statistical significance is proved.",
        ],
    }


def evaluate_matched_current(
    context_by_group: Mapping[str, Sequence[PositionInput]],
    reserved_targets_by_group: Mapping[str, Sequence[PositionInput]],
    current_fields_by_group: Mapping[str, OceanField] | None = None,
    *,
    failures_by_group: Mapping[str, str] | None = None,
    current_failures_by_group: Mapping[str, str] | None = None,
) -> dict:
    """Convenience orchestration: all candidates exist before target decoding."""
    forecasts = build_matched_current_forecasts(
        context_by_group, current_fields_by_group, failures_by_group=failures_by_group,
        current_failures_by_group=current_failures_by_group,
    )
    return score_matched_current_forecasts(forecasts, reserved_targets_by_group)
