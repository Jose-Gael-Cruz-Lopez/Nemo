"""Bounded deterministic lookback, not a reverse-time probability or polluter claim.

Only the endpoint and (for one baseline) its immediately preceding fix enter
inference. Evaluation truth belongs to the separate scorer after all forecasts.
No network, devices, fitting, randomness or mutable application state is used.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from numbers import Real

import numpy as np

from .advection import CurrentSampler, advect_current
from .benchmark import SphericalLocalFrame, great_circle_distance_m
from .field import OceanField

STUDY_ID = "ocean-source-gdp-hycom-15m-v1"
GROUP_IDS = ("300234066836710", "300534061292930")
MODEL_IDS = ("stationary", "last_drift", "reverse_current")
OBSERVATION_TIME = datetime(2022, 6, 1, 6, tzinfo=UTC)
OBSERVATION_TIME_UTC = "2022-06-01T06:00:00Z"
EARLIER_TIME_UTC = "2022-06-01T00:00:00Z"
LOOKBACK_HOURS = (1, 3, 6)
HORIZON_S = 21600
STEP_S = 300
OFFSETS = (("center", 0., 0.), ("east", 100., 0.), ("west", -100., 0.),
           ("north", 0., 100.), ("south", 0., -100.))
BIASES = (("zero", 0., 0.), ("east", .05, 0.), ("west", -.05, 0.),
          ("north", 0., .05), ("south", 0., -.05))
LIMITATIONS = [
    "Retrospective post-outcome development on two already-viewed processed GDP groups, not a new blind test.",
    "A computed earlier position is not a verified pollution release, unique origin or polluter identity.",
    "The twenty-five fixed endpoint/current perturbations are a sensitivity grid, not probabilities or calibrated uncertainty.",
    "HYCOM fifteen-metre model analysis does not establish surface-plastic behavior or issue-time availability.",
    "No diffusion reversal, windage, waves, beaching, retention, object change or coastline source search is modeled.",
    "Numerical forward closure is solver consistency, not observed earlier-position accuracy.",
    "Missing masks, times and geography stop supported integration; no hull bridges unsupported regions.",
    "Ocean geography is separate from tank centimetres; no physical tank or reef benefit is validated.",
]


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def forecast_sha256(value):
    return canonical_sha256({key: item for key, item in value.items() if key != "forecast_sha256"})


def _utc(value):
    try:
        when = datetime.fromisoformat(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        raise ValueError("INVALID_UTC_TIME") from None
    if (not isinstance(when, datetime) or when.utcoffset() != timedelta(0)
            or not 1900 <= when.year <= 2100):
        raise ValueError("INVALID_UTC_TIME")
    return when.astimezone(UTC)


def _iso(when):
    return when.isoformat().replace("+00:00", "Z")


def _number(value):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (Real, str)):
        raise ValueError("INVALID_GEOGRAPHIC_POSITION")  # noqa: TRY004 - domain validation contract
    try:
        value = float(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("INVALID_GEOGRAPHIC_POSITION") from None
    if not math.isfinite(value):
        raise ValueError("INVALID_GEOGRAPHIC_POSITION")
    return value


def _position(row, group_id=None):
    if (not isinstance(row, Mapping) or set(row) - {
            "drifter_id", "time_utc", "latitude_deg", "longitude_deg"}):
        raise ValueError("POSITION_FIELDS_NOT_ALLOWED")
    if group_id is not None and row.get("drifter_id", group_id) != group_id:
        raise ValueError("GROUP_ID_MISMATCH")
    time = _utc(row.get("time_utc"))
    latitude, longitude = (_number(row.get(key)) for key in ("latitude_deg", "longitude_deg"))
    if abs(latitude) > 85 or not -180 <= longitude <= 180:
        raise ValueError("UNSUPPORTED_GEOGRAPHY")
    return {"time_utc": _iso(time), "latitude_deg": latitude, "longitude_deg": longitude}


def _vector(value, maximum):
    if (not isinstance(value, (tuple, list, np.ndarray))
            or np.shape(value) != (2,)
            or any(isinstance(x, (bool, np.bool_)) or not isinstance(x, Real)
                   or not math.isfinite(x) for x in value)):
        raise ValueError("FINITE_TWO_COMPONENT_VECTOR_REQUIRED")
    vector = np.array(value, dtype=float)
    if np.linalg.norm(vector) > maximum:
        raise ValueError("VECTOR_BUDGET_EXCEEDED")
    return vector


def reverse_current_field(field, observed_time_utc, current_bias_east_north_m_s=(0., 0.)):
    """Reparameterize time AND negate u+b; never merely negate chronological u.

    Pseudo time s=T+tau maps to actual t=T-tau. All source axes/masks stay
    unchanged apart from time reversal, with independent read-only copies.
    """
    CurrentSampler(field)
    when = _utc(observed_time_utc)
    bias = _vector(current_bias_east_north_m_s, .05)
    endpoint = np.datetime64(when.replace(tzinfo=None), "us")
    original_times = np.asarray(field.time_utc).astype("datetime64[us]")
    times = endpoint + (endpoint - original_times[::-1])
    u = -(np.array(field.eastward_m_s[::-1], dtype=float, copy=True) + bias[0])
    v = -(np.array(field.northward_m_s[::-1], dtype=float, copy=True) + bias[1])
    mask = np.array(field.valid_mask[::-1], copy=True)
    lon, lat = np.array(field.longitude_deg, copy=True), np.array(field.latitude_deg, copy=True)
    metadata = copy.deepcopy(field.metadata)
    digest = hashlib.sha256()
    for array in (times, lon, lat, u, v, mask):
        digest.update(array.tobytes())
    digest.update(json.dumps({"observation_time_utc": _iso(when), "forward_bias_m_s": bias.tolist()},
                             sort_keys=True).encode())
    metadata.update({"sha256": digest.hexdigest(), "data_kind": "DERIVED_REVERSED_TIME_SENSITIVITY_FIELD",
                     "source_field_sha256": field.metadata.get("sha256"),
                     "actual_time": "t_observed-minus-lookback", "velocity_units": "m/s"})
    for array in (times, lon, lat, u, v, mask):
        array.setflags(write=False)
    result = OceanField(times, lon, lat, u, v, mask, field.selected_depth_m, metadata)
    CurrentSampler(result)
    return result


def backtrack_current(field, observation, *, endpoint_offset_east_north_m=(0., 0.),
                      current_bias_east_north_m_s=(0., 0.), horizon_s=HORIZON_S):
    """One bounded deterministic path; return actual descending UTC."""
    if (isinstance(horizon_s, bool) or not isinstance(horizon_s, Real)
            or not math.isfinite(horizon_s) or not 0 < horizon_s <= HORIZON_S):
        raise ValueError("LOOKBACK_HORIZON_OUTSIDE_BUDGET")
    endpoint = _position(observation)
    offset = _vector(endpoint_offset_east_north_m, 100)
    latitude, longitude = SphericalLocalFrame(endpoint["latitude_deg"], endpoint["longitude_deg"]).to_latlon(offset)
    transformed = reverse_current_field(field, endpoint["time_utc"], current_bias_east_north_m_s)
    raw = advect_current(transformed, latitude_deg=latitude, longitude_deg=longitude,
        start_time_utc=endpoint["time_utc"], horizon_s=horizon_s, step_s=STEP_S,
        output_step_s=STEP_S)
    observed_time = _utc(endpoint["time_utc"])
    track = [{"lookback_s": point["elapsed_s"],
              "time_utc": _iso(observed_time - timedelta(seconds=point["elapsed_s"])),
              "latitude_deg": point["latitude_deg"], "longitude_deg": point["longitude_deg"]}
             for point in raw["track"]]
    return {"status": raw["status"], "reason_code": raw["reason_code"],
            "completed_lookback_s": raw["completed_horizon_s"], "track": track,
            "accepted_steps": raw["accepted_steps"], "solver": raw["solver"],
            "derived_field_sha256": transformed.metadata["sha256"]}


def _candidate(model, reason=None):
    return {"model_id": model, "status": "UNSUPPORTED", "reason_code": reason,
            "earlier_time_utc": EARLIER_TIME_UTC, "latitude_deg": None, "longitude_deg": None}


def _closure(field, endpoint, nominal):
    result = {"status": "UNSUPPORTED", "reason_code": "NOMINAL_LOOKBACK_INCOMPLETE",
              "endpoint_distance_m": None, "forward_track": [], "comparison_kind": "NUMERICAL_CLOSURE_NOT_REAL_ACCURACY"}
    if nominal["status"] != "COMPLETED":
        return result
    earlier = nominal["track"][-1]
    try:
        forward = advect_current(field, latitude_deg=earlier["latitude_deg"],
            longitude_deg=earlier["longitude_deg"], start_time_utc=earlier["time_utc"],
            horizon_s=HORIZON_S, step_s=STEP_S, output_step_s=STEP_S)
    except (ValueError, TypeError):
        result["reason_code"] = "FORWARD_CLOSURE_INPUT_UNSUPPORTED"
        return result
    result.update(status=forward["status"], reason_code=forward["reason_code"],
                  forward_track=forward["track"])
    if forward["status"] == "COMPLETED":
        final = forward["track"][-1]
        result["endpoint_distance_m"] = great_circle_distance_m(
            (endpoint["latitude_deg"], endpoint["longitude_deg"]),
            (final["latitude_deg"], final["longitude_deg"]))
    return result


def _group(group_id, observations, field, field_failure):
    candidates = [_candidate(model) for model in MODEL_IDS]
    scenarios = []
    group = {"group_id": group_id, "observed_endpoint": None, "penultimate_observation": None,
             "candidates": candidates, "numerical_closure": {
                 "status": "UNSUPPORTED", "reason_code": "ENDPOINT_UNAVAILABLE",
                 "endpoint_distance_m": None, "forward_track": [],
                 "comparison_kind": "NUMERICAL_CLOSURE_NOT_REAL_ACCURACY"}}
    endpoint = penultimate = None
    try:
        if (not isinstance(observations, Sequence) or isinstance(observations, (str, bytes))
                or not 1 <= len(observations) <= 2):
            raise ValueError("ONLY_FINAL_AND_PENULTIMATE_POSITIONS_ALLOWED")
        endpoint = _position(observations[-1], group_id)
        if _utc(endpoint["time_utc"]) != OBSERVATION_TIME:
            raise ValueError("FINAL_OBSERVATION_TIME_MISMATCH")
        group["observed_endpoint"] = endpoint
        candidates[0].update(status="COMPLETED", latitude_deg=endpoint["latitude_deg"],
                             longitude_deg=endpoint["longitude_deg"])
        if len(observations) == 2:
            penultimate = _position(observations[0], group_id)
            if _utc(penultimate["time_utc"]) != OBSERVATION_TIME - timedelta(hours=1):
                raise ValueError("PENULTIMATE_OBSERVATION_TIME_MISMATCH")
            group["penultimate_observation"] = penultimate
        if penultimate is None:
            candidates[1]["reason_code"] = "PENULTIMATE_OBSERVATION_UNAVAILABLE"
        else:
            frame = SphericalLocalFrame(endpoint["latitude_deg"], endpoint["longitude_deg"])
            previous_xy = frame.to_xy(penultimate["latitude_deg"], penultimate["longitude_deg"])
            inferred_xy = previous_xy * 6  # Last forward displacement is -previous_xy per hour.
            latitude, longitude = frame.to_latlon(inferred_xy)
            candidates[1].update(status="COMPLETED", latitude_deg=latitude, longitude_deg=longitude)
    except (ValueError, TypeError, KeyError) as error:
        reason = str(error) if isinstance(error, ValueError) else "INVALID_OBSERVATION"
        for candidate in candidates:
            if candidate["status"] != "COMPLETED":
                candidate["reason_code"] = reason
        if endpoint is not None and group["observed_endpoint"] is None:
            endpoint = None
    for offset_name, east, north in OFFSETS:
        for bias_name, u, v in BIASES:
            path = {"status": "UNSUPPORTED", "reason_code": field_failure or "CURRENT_FIELD_UNAVAILABLE",
                    "completed_lookback_s": 0., "track": [], "accepted_steps": 0, "solver": None,
                    "derived_field_sha256": None}
            if endpoint is not None and field is not None:
                try:
                    path = backtrack_current(field, endpoint, endpoint_offset_east_north_m=(east, north),
                                             current_bias_east_north_m_s=(u, v))
                except (ValueError, TypeError, OverflowError):
                    path["reason_code"] = "CURRENT_OR_GEOMETRY_CONTRACT_UNSUPPORTED"
            elif endpoint is None:
                path["reason_code"] = candidates[2]["reason_code"] or "ENDPOINT_UNAVAILABLE"
            scenarios.append({"scenario_id": offset_name + "|" + bias_name,
                "endpoint_offset_east_north_m": [east, north],
                "current_bias_east_north_m_s": [u, v], **path})
    nominal = scenarios[0]
    candidates[2].update(status=nominal["status"], reason_code=nominal["reason_code"])
    if nominal["status"] == "COMPLETED":
        candidates[2].update(latitude_deg=nominal["track"][-1]["latitude_deg"],
                             longitude_deg=nominal["track"][-1]["longitude_deg"])
    earlier_candidates = []
    for hour in LOOKBACK_HOURS:
        points = [{"scenario_id": scenario["scenario_id"], "latitude_deg": point["latitude_deg"],
                   "longitude_deg": point["longitude_deg"]} for scenario in scenarios
                  for point in scenario["track"] if point["lookback_s"] == hour * 3600]
        earlier_candidates.append({"lookback_hours": hour,
            "time_utc": _iso(OBSERVATION_TIME - timedelta(hours=hour)), "planned_scenarios": 25,
            "available_count": len(points), "points": points})
    group["reverse_current"] = {"nominal_scenario_id": "center|zero", "scenarios": scenarios,
        "earlier_candidates": earlier_candidates,
        "coverage": {"planned_scenarios": 25, **{key: sum(path["status"] == status for path in scenarios)
            for key, status in (("completed_scenarios", "COMPLETED"), ("partial_scenarios", "PARTIAL"),
                                ("unsupported_scenarios", "UNSUPPORTED"))}}}
    if endpoint is not None and field is not None:
        group["numerical_closure"] = _closure(field, endpoint, nominal)
    return group


def build_ocean_source_forecasts(observations_by_group, field, *, field_failure=None):
    """Only up to two permitted position rows per fixed group; no evaluator truth."""
    if not isinstance(observations_by_group, Mapping) or set(observations_by_group) - set(GROUP_IDS):
        raise ValueError("FIXED_GROUP_INPUTS_REQUIRED")
    result = {"schema_version": 1, "kind": "OCEAN_SOURCE_BACKTRACKING_FORECASTS", "study_id": STUDY_ID,
        "observation_time_utc": OBSERVATION_TIME_UTC, "earlier_time_utc": EARLIER_TIME_UTC,
        "group_ids": list(GROUP_IDS), "model_ids": list(MODEL_IDS), "lookback_hours": list(LOOKBACK_HOURS),
        "planned_model_rows": 6, "planned_distinct_earlier_positions": 2, "scenarios_per_group": 25,
        "analysis_scope": "POST_OUTCOME_EXPLORATORY", "previously_viewed_earlier_positions": True,
        "inference_uses_only_last_two_positions": True, "earlier_truth_used": False,
        "source_attribution_validated": False, "physical_validation": False,
        "automatic_model_promotion": False, "limitations": list(LIMITATIONS),
        "groups": [_group(group, observations_by_group.get(group), field, field_failure) for group in GROUP_IDS]}
    result["forecast_sha256"] = forecast_sha256(result)
    return result


def score_ocean_source_forecasts(forecasts, earlier_truth_by_group):
    """Decode separately reserved earlier truth only after a complete forecast exists."""
    if (not isinstance(forecasts, dict) or forecasts.get("forecast_sha256") != forecast_sha256(forecasts)
            or forecasts.get("study_id") != STUDY_ID or forecasts.get("model_ids") != list(MODEL_IDS)
            or forecasts.get("group_ids") != list(GROUP_IDS) or len(forecasts.get("groups", [])) != 2
            or [group.get("group_id") for group in forecasts["groups"]] != list(GROUP_IDS)
            or any([row.get("model_id") for row in group.get("candidates", [])] != list(MODEL_IDS)
                   for group in forecasts["groups"])):
        raise ValueError("FORECAST_IDENTITY_INVALID")
    if not isinstance(earlier_truth_by_group, Mapping) or set(earlier_truth_by_group) - set(GROUP_IDS):
        raise ValueError("FIXED_EARLIER_TRUTH_GROUPS_REQUIRED")
    rows = []
    for group in forecasts["groups"]:
        target, truth_reason = None, None
        try:
            target = _position(earlier_truth_by_group.get(group["group_id"]), group["group_id"])
            if target["time_utc"] != EARLIER_TIME_UTC:
                raise ValueError("EARLIER_TARGET_TIME_MISMATCH")
        except (ValueError, TypeError, KeyError):
            target, truth_reason = None, "EARLIER_TRUTH_UNAVAILABLE"
        for candidate in group["candidates"]:
            predicted = ({"time_utc": EARLIER_TIME_UTC, "latitude_deg": candidate["latitude_deg"],
                          "longitude_deg": candidate["longitude_deg"]}
                         if candidate["status"] == "COMPLETED" else None)
            status = "FORECAST_UNAVAILABLE" if predicted is None else "TRUTH_UNAVAILABLE" if target is None else "SCORED"
            rows.append({"group_id": group["group_id"], "model_id": candidate["model_id"], "status": status,
                "reason_code": candidate["reason_code"] if predicted is None else truth_reason,
                "earlier_target": target, "predicted_earlier": predicted,
                "error_m": great_circle_distance_m((target["latitude_deg"], target["longitude_deg"]),
                    (predicted["latitude_deg"], predicted["longitude_deg"])) if status == "SCORED" else None})
    scored = sum(row["status"] == "SCORED" for row in rows)
    primary = [{"model_id": model, "group_count": 2,
                "mean_error_m": math.fsum(row["error_m"] for row in rows if row["model_id"] == model) / 2}
               for model in MODEL_IDS] if scored == 6 else None
    return {"schema_version": 1, "kind": "OCEAN_SOURCE_EARLIER_POSITION_VALIDATION",
        "planned_model_rows": 6, "scored_model_rows": scored, "planned_distinct_earlier_positions": 2,
        "primary_complete": scored == 6, "primary_mean_earlier_position_error_m": primary, "rows": rows,
        "analysis_scope": "POST_OUTCOME_EXPLORATORY", "previously_viewed_earlier_positions": True,
        "source_attribution_validated": False, "physical_validation": False,
        "statistical_independence": False, "automatic_model_promotion": False}
