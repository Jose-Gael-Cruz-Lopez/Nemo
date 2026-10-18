"""Post-outcome, unfitted origin-residual development diagnostic.

The original matched-current experiment is immutable. This distinct candidate
adds a constant local east/north discrepancy to a copied, supported current
field. The two already-viewed GDP groups are development data, not a new test.
Candidate construction has no reserved-target argument or future access.
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

import numpy as np

from . import matched_current as original
from .advection import CurrentSampler, advect_current
from .benchmark import SphericalLocalFrame, great_circle_distance_m
from .field import OceanField

GROUP_IDS = original.GROUP_IDS
MODEL_IDS = (*original.MODEL_IDS, "origin_residual_current")
HORIZONS_S = original.HORIZONS_S
ORIGIN = original.ORIGIN
ORIGIN_TIME_UTC = original.ORIGIN_TIME_UTC
STUDY_ID = "origin-residual-gdp-hycom-15m-exploratory-v1"
PLANNED_CELLS = len(GROUP_IDS) * len(MODEL_IDS) * len(HORIZONS_S)
PLANNED_DISTINCT_TARGETS = len(GROUP_IDS) * len(HORIZONS_S)


class _PositionInputError(ValueError):
    """Scientific input type failures remain explicit candidate/target failures."""


def canonical_sha256(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def forecast_sha256(value: dict) -> str:
    return canonical_sha256({key: item for key, item in value.items()
                             if key != "forecast_sha256"})


def _fix(row, group_id):
    if not isinstance(row, Mapping):
        raise _PositionInputError("INVALID_POSITION_ROW")
    if row.get("drifter_id", group_id) != group_id:
        raise ValueError("ID_MISMATCH")
    when = row.get("time_utc")
    try:
        when = datetime.fromisoformat(when) if isinstance(when, str) else when
    except ValueError:
        raise ValueError("INVALID_TIME") from None
    if (not isinstance(when, datetime) or when.utcoffset() != timedelta(0)):
        raise ValueError("INVALID_TIME")
    coordinates = []
    for key, lower, upper in (("latitude_deg", -90, 90), ("longitude_deg", -180, 180)):
        value = row.get(key)
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (Real, str)):
            raise _PositionInputError("INVALID_COORDINATE")
        try:
            number = float(value)
        except (ValueError, TypeError, OverflowError):
            raise ValueError("INVALID_COORDINATE") from None
        if not math.isfinite(number) or not lower <= number <= upper:
            raise ValueError("INVALID_COORDINATE")
        coordinates.append(number)
    return when.astimezone(UTC), *coordinates


def _blank_candidate():
    return {"model_id": MODEL_IDS[-1], "status": "UNSUPPORTED", "reason_code": None,
        "requested_horizon_s": HORIZONS_S[-1], "completed_horizon_s": 0.0,
        "planned_count": len(HORIZONS_S), "available_count": 0, "context_rows_used": 2,
        "learned_parameters": 0, "future_positions_used": False,
        "residual_definition": "last_observed_origin_tangent_velocity_minus_origin_current",
        "residual_units": "m/s", "residual_transport": "constant_local_east_north_components",
        "residual_east_north_m_s": None, "last_observed_velocity_m_s": None,
        "origin_current_east_north_m_s": None,
        "cells": [{"horizon_hours": h // 3600, "elapsed_s": h,
            "time_utc": (ORIGIN + timedelta(seconds=h)).isoformat().replace("+00:00", "Z"),
            "forecast_status": "UNAVAILABLE", "forecast_reason_code": None,
            "latitude_deg": None, "longitude_deg": None} for h in HORIZONS_S]}


def _failure(candidate, reason):
    candidate["reason_code"] = reason
    for cell in candidate["cells"]:
        if cell["forecast_status"] != "AVAILABLE":
            cell["forecast_reason_code"] = reason
    return candidate


def corrected_field(field: OceanField, residual_east_north_m_s) -> OceanField:
    """Copy actual axes/masks and add the declared local residual without clipping.

    This is a derived model field, not a change to the source NetCDF. Existing
    CurrentSampler/advect_current validate the corrected whole supported grid,
    including its unchanged 10 m/s bound. Missing cells remain missing.
    """
    if not isinstance(field, OceanField):
        raise TypeError("An OceanField is required")
    raw_residual = np.asarray(residual_east_north_m_s, dtype=object)
    if (raw_residual.shape != (2,)
            or any(isinstance(value, (bool, np.bool_)) or not isinstance(value, Real)
                   for value in raw_residual)):
        raise ValueError("A finite numeric east/north residual pair in m/s is required")
    residual = raw_residual.astype(float)
    if not np.isfinite(residual).all():
        raise ValueError("A finite east/north residual pair in m/s is required")
    arrays = {key: np.array(getattr(field, key), copy=True) for key in (
        "time_utc", "longitude_deg", "latitude_deg", "eastward_m_s",
        "northward_m_s", "valid_mask")}
    arrays["eastward_m_s"] = arrays["eastward_m_s"].astype(float) + residual[0]
    arrays["northward_m_s"] = arrays["northward_m_s"].astype(float) + residual[1]
    metadata = copy.deepcopy(field.metadata)
    source = copy.deepcopy(metadata)
    digest = hashlib.sha256()
    for key in ("time_utc", "longitude_deg", "latitude_deg", "eastward_m_s",
                "northward_m_s", "valid_mask"):
        value = arrays[key]
        raw = (value.astype("datetime64[us]").astype("<i8") if key == "time_utc"
               else value.astype("u1") if key == "valid_mask" else value.astype("<f8"))
        digest.update(key.encode() + str(raw.shape).encode() + raw.tobytes(order="C"))
    digest.update(json.dumps({"source": source, "residual_m_s": residual.tolist()},
                             sort_keys=True, allow_nan=False).encode())
    metadata.update({"sha256": digest.hexdigest(), "data_kind": "DERIVED_EXPLORATORY_FIELD",
        "source_field_provenance": source, "residual_east_north_m_s": residual.tolist(),
        "velocity_units": "m/s", "source_bytes_modified": False,
        "residual_transport": "constant_local_east_north_components"})
    return OceanField(**arrays, selected_depth_m=field.selected_depth_m, metadata=metadata)


def build_origin_residual_candidate(context, field, *, group_id: str, failure: str | None = None,
                                    context_failure: str | None = None):
    """Use only a permitted prefix, never a future position or fitted coefficient."""
    if group_id not in GROUP_IDS:
        raise ValueError("Only the two fixed development groups are accepted")
    candidate = _blank_candidate()
    if (not isinstance(context, Sequence) or isinstance(context, (str, bytes))
            or len(context) != original.CONTEXT_COUNT):
        return _failure(candidate, context_failure or "CONTEXT_COUNT_INVALID")
    try:
        now, latitude, longitude = _fix(context[-1], group_id)
        if now != ORIGIN:
            raise ValueError("ORIGIN_TIME_MISMATCH")
        before, previous_latitude, previous_longitude = _fix(context[-2], group_id)
        if (now - before).total_seconds() != original.CONTEXT_STEP_S:
            raise ValueError("CONTEXT_CADENCE_MISMATCH")
        frame = SphericalLocalFrame(latitude, longitude)
        velocity = -frame.to_xy(previous_latitude, previous_longitude) / original.CONTEXT_STEP_S
    except ValueError as error:
        return _failure(candidate, "LOCAL_GEOMETRY_BUDGET_EXCEEDED" if "50 km" in str(error)
                        else str(error))
    candidate["last_observed_velocity_m_s"] = velocity.tolist()
    if field is None:
        return _failure(candidate, failure or "CURRENT_FIELD_UNAVAILABLE")
    try:
        sampler = CurrentSampler(field, time_origin=np.datetime64(ORIGIN.replace(tzinfo=None), "us"))
        initial = np.asarray(sampler.sample(latitude, longitude, 0.0))
        residual = velocity - initial
        candidate["origin_current_east_north_m_s"] = initial.tolist()
        candidate["residual_east_north_m_s"] = residual.tolist()
        derived = corrected_field(field, residual)
        result = advect_current(derived, latitude_deg=latitude, longitude_deg=longitude,
            start_time_utc=ORIGIN, horizon_s=HORIZONS_S[-1], step_s=300, output_step_s=3600)
    except (ValueError, TypeError, OverflowError) as error:
        reason = getattr(error, "reason", None)
        if reason is None:
            if isinstance(field, OceanField) and np.asarray(field.valid_mask).dtype == np.dtype(bool) and not np.asarray(field.valid_mask).any():
                reason = "CURRENT_FIELD_ALL_MASKED"
            else:
                reason = ("CORRECTED_FIELD_SPEED_BUDGET_EXCEEDED" if "speed exceeds" in str(error)
                          else "CURRENT_CONFIGURATION_INVALID")
        return _failure(candidate, reason)
    candidate.update({"advection": result, "derived_field_sha256": derived.metadata["sha256"],
        "source_field_sha256": field.metadata.get("sha256"), "status": result["status"],
        "reason_code": result["reason_code"], "completed_horizon_s": result["completed_horizon_s"]})
    accepted = {point["elapsed_s"]: point for point in result["track"]}
    for cell in candidate["cells"]:
        point = accepted.get(cell["elapsed_s"])
        if point is None:
            cell["forecast_reason_code"] = result["reason_code"] or "HOURLY_OUTPUT_UNAVAILABLE"
        else:
            cell.update({"latitude_deg": point["latitude_deg"], "longitude_deg": point["longitude_deg"],
                         "forecast_status": "AVAILABLE", "forecast_reason_code": None})
            candidate["available_count"] += 1
    return candidate


def build_forecasts(context_by_group, fields_by_group=None, *, failures_by_group=None,
                    current_failures_by_group=None) -> dict:
    """Allocate all 48 cells and build all four candidates before target access."""
    fields_by_group = {} if fields_by_group is None else fields_by_group
    for values in (context_by_group, fields_by_group, failures_by_group or {},
                   current_failures_by_group or {}):
        if not isinstance(values, Mapping) or set(values) - set(GROUP_IDS):
            raise ValueError("Only the two fixed development groups are accepted")
    groups = [{"group_id": group, "context_count": 0, "origin_position": None,
               "candidates": [None, None, None, _blank_candidate()]} for group in GROUP_IDS]
    baseline = original.build_matched_current_forecasts(context_by_group, fields_by_group,
        failures_by_group=failures_by_group, current_failures_by_group=current_failures_by_group)
    for group, old in zip(groups, baseline["groups"], strict=True):
        group.update({"context_count": old["context_count"],
                      "origin_position": copy.deepcopy(old["origin_position"])})
        group["candidates"][:3] = copy.deepcopy(old["candidates"])
        group["candidates"][3] = build_origin_residual_candidate(
            context_by_group.get(group["group_id"]), fields_by_group.get(group["group_id"]),
            group_id=group["group_id"],
            failure=(current_failures_by_group or {}).get(group["group_id"]),
            context_failure=(failures_by_group or {}).get(group["group_id"]))
    report = {"schema_version": 1, "kind": "ORIGIN_RESIDUAL_EXPLORATORY_FORECASTS",
        "study_id": STUDY_ID, "group_ids": list(GROUP_IDS), "model_ids": list(MODEL_IDS),
        "origin_time_utc": ORIGIN_TIME_UTC, "horizons_s": list(HORIZONS_S),
        "planned_group_count": len(GROUP_IDS), "planned_cell_count": PLANNED_CELLS,
        "planned_distinct_target_count": PLANNED_DISTINCT_TARGETS,
        "all_forecasts_built_before_target_decode": True, "future_positions_used": False,
        "previously_viewed_target_outcomes": True, "analysis_scope": "POST_OUTCOME_EXPLORATORY",
        "learned_parameters": 0, "automatic_model_promotion": False,
        "groups": groups}
    report["forecast_sha256"] = forecast_sha256(report)
    return report


def _validate_forecasts(report):
    if (not isinstance(report, dict) or report.get("forecast_sha256") != forecast_sha256(report)
            or type(report.get("schema_version")) is not int or report.get("schema_version") != 1
            or report.get("kind") != "ORIGIN_RESIDUAL_EXPLORATORY_FORECASTS"
            or report.get("study_id") != STUDY_ID or report.get("model_ids") != list(MODEL_IDS)
            or report.get("group_ids") != list(GROUP_IDS)
            or report.get("horizons_s") != list(HORIZONS_S)
            or report.get("planned_cell_count") != PLANNED_CELLS
            or report.get("all_forecasts_built_before_target_decode") is not True
            or report.get("future_positions_used") is not False
            or report.get("previously_viewed_target_outcomes") is not True
            or report.get("analysis_scope") != "POST_OUTCOME_EXPLORATORY"
            or report.get("automatic_model_promotion") is not False):
        raise ValueError("Complete frozen four-candidate forecasts are required before target decoding")
    if len(report["groups"]) != len(GROUP_IDS):
        raise ValueError("Every fixed development group is required")
    for group, identity in zip(report["groups"], GROUP_IDS, strict=True):
        if group["group_id"] != identity or len(group["candidates"]) != len(MODEL_IDS):
            raise ValueError("Fixed forecast groups/candidates changed")
        for candidate, model in zip(group["candidates"], MODEL_IDS, strict=True):
            if (candidate["model_id"] != model or len(candidate["cells"]) != len(HORIZONS_S)
                    or candidate["future_positions_used"] is not False
                    or type(candidate["learned_parameters"]) is not int
                    or candidate["learned_parameters"] != 0):
                raise ValueError("Every planned candidate/hour cell is required")
            for cell, h in zip(candidate["cells"], HORIZONS_S, strict=True):
                if (cell["elapsed_s"] != h or cell["horizon_hours"] != h // 3600
                        or cell["time_utc"] != (ORIGIN + timedelta(seconds=h)).isoformat().replace("+00:00", "Z")):
                    raise ValueError("Fixed forecast times changed")
                if cell["forecast_status"] == "AVAILABLE":
                    _fix(cell, identity)
                elif (cell["forecast_status"] != "UNAVAILABLE" or cell["latitude_deg"] is not None
                      or cell["longitude_deg"] is not None):
                    raise ValueError("Unavailable forecast must retain null coordinates")


def _targets(rows, identity):
    values, issues, seen, duplicates = {}, [], set(), set()
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return values, ["TARGETS_UNAVAILABLE"]
    if len(rows) > 64:
        return values, ["TARGET_ROW_BUDGET_EXCEEDED"]
    allowed = {ORIGIN + timedelta(seconds=h) for h in HORIZONS_S}
    for row in rows:
        try:
            if not isinstance(row, Mapping):
                raise _PositionInputError("INVALID_POSITION_ROW")
            raw_time = row.get("time_utc")
            when = datetime.fromisoformat(raw_time) if isinstance(raw_time, str) else raw_time
            if (not isinstance(when, datetime) or when.utcoffset() != timedelta(0)):
                raise ValueError("INVALID_TIME")
            if when in seen:
                values.pop(when, None)
                duplicates.add(when)
                issues.append("DUPLICATE_TARGET_TIME")
                continue
            seen.add(when)
            when, latitude, longitude = _fix(row, identity)
            if when not in allowed:
                raise ValueError("UNPLANNED_TARGET_TIME")
            values[when] = latitude, longitude
        except ValueError as error:
            issues.append(str(error))
    return {when: value for when, value in values.items() if when not in duplicates}, sorted(set(issues))


def _metrics(cells, planned):
    errors = [cell["error_m"] for cell in cells if cell["score_status"] == "SCORED"]
    return {"planned_count": planned, "scored_count": len(errors),
        "coverage_complete": len(errors) == planned,
        "available_cell_mean_error_m": math.fsum(errors) / len(errors) if errors else None,
        "full_horizon_ade_m": math.fsum(errors) / planned if len(errors) == planned else None}


def score_forecasts(forecasts: dict, reserved_targets_by_group: Mapping) -> dict:
    """Score only after all four forecast candidates have a valid content digest."""
    _validate_forecasts(forecasts)
    if not isinstance(reserved_targets_by_group, Mapping) or set(reserved_targets_by_group) - set(GROUP_IDS):
        raise ValueError("Reserved targets must use the two fixed development identities")
    groups, all_cells = [], {model: [] for model in MODEL_IDS}
    for group in forecasts["groups"]:
        identity = group["group_id"]
        targets, issues = _targets(reserved_targets_by_group.get(identity), identity)
        candidates = []
        for candidate in group["candidates"]:
            cells = []
            for prediction in candidate["cells"]:
                cell = copy.deepcopy(prediction)
                target = targets.get(ORIGIN + timedelta(seconds=cell["elapsed_s"]))
                status = ("FORECAST_UNAVAILABLE" if cell["forecast_status"] != "AVAILABLE" else
                          "TARGET_UNAVAILABLE" if target is None else "SCORED")
                cell.update({"group_id": identity, "model_id": candidate["model_id"],
                    "target_latitude_deg": target[0] if target else None,
                    "target_longitude_deg": target[1] if target else None,
                    "score_status": status, "error_m": great_circle_distance_m(
                        (cell["latitude_deg"], cell["longitude_deg"]), target) if status == "SCORED" else None})
                cells.append(cell)
            metrics = _metrics(cells, len(HORIZONS_S))
            metrics["endpoint_fde_m"] = cells[-1]["error_m"]
            candidates.append({"model_id": candidate["model_id"], "prediction_status": candidate["status"],
                "prediction_reason_code": candidate["reason_code"], "metrics": metrics, "cells": cells})
            all_cells[candidate["model_id"]].extend(cells)
        groups.append({"group_id": identity, "target_issues": issues, "candidates": candidates})
    models = [{"model_id": model, "metrics": _metrics(cells, PLANNED_DISTINCT_TARGETS)}
              for model, cells in all_cells.items()]
    complete = sum(row["metrics"]["scored_count"] for row in models) == PLANNED_CELLS
    primary = None
    if complete:
        primary = [{"model_id": model, "group_count": len(GROUP_IDS),
            "equal_id_macro_ade_m": math.fsum(group["candidates"][i]["metrics"]["full_horizon_ade_m"]
                for group in groups) / len(GROUP_IDS),
            "equal_id_macro_fde_m": math.fsum(group["candidates"][i]["metrics"]["endpoint_fde_m"]
                for group in groups) / len(GROUP_IDS)} for i, model in enumerate(MODEL_IDS)]
    paired = []
    for a, b in itertools.combinations(MODEL_IDS, 2):
        common = [{"group_id": x["group_id"], "horizon_hours": x["horizon_hours"],
                   "error_a_m": x["error_m"], "error_b_m": y["error_m"]}
                  for x, y in zip(all_cells[a], all_cells[b], strict=True)
                  if x["score_status"] == y["score_status"] == "SCORED"]
        paired.append({"model_a": a, "model_b": b, "planned_common_cell_count": PLANNED_DISTINCT_TARGETS,
            "common_scored_count": len(common), "coverage_complete": len(common) == PLANNED_DISTINCT_TARGETS,
            "analysis_scope": "PRIMARY_COMPLETE_DEVELOPMENT_COHORT" if complete else "SECONDARY_COMMON_AVAILABLE_CELLS",
            "mean_delta_a_minus_b_m": math.fsum(row["error_a_m"] - row["error_b_m"]
                for row in common) / len(common) if common else None, "cells": common})
    return {"schema_version": 1, "kind": "ORIGIN_RESIDUAL_EXPLORATORY_SCORES",
        "study_id": STUDY_ID, "planned_group_count": len(GROUP_IDS),
        "planned_cell_count": PLANNED_CELLS, "planned_distinct_target_count": PLANNED_DISTINCT_TARGETS,
        "scored_cell_count": sum(row["metrics"]["scored_count"] for row in models),
        "groups": groups, "models": models, "paired_comparisons": paired,
        "primary_common_cohort_complete": complete, "primary_equal_id_macro_results": primary,
        "analysis_scope": "POST_OUTCOME_EXPLORATORY", "previously_viewed_target_outcomes": True,
        "statistical_independence": False, "automatic_winner_selected": False,
        "automatic_model_promotion": False, "operational_forecast_skill_verified": False,
        "physical_validation": False, "heldout_tuning": False, "global_training": False,
        "limitations": ["These 48 model/hour cells reuse only 12 already-viewed processed GDP targets.",
            "The residual is constant local east/north discrepancy, not an identified physical coefficient.",
            "Mean-sphere context velocity and WGS84 RK4 are distinct coordinate constructions.",
            "Lower descriptive error is not confirmatory skill, statistical significance or model promotion.",
            "Issue-time availability, assimilation independence, plastic, tank and reef accuracy remain unverified."]}
