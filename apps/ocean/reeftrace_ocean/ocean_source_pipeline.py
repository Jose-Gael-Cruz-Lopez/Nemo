"""Three-fix causal-filter walkthrough, separate from the frozen Kalman study.

Only 01/02/03Z enter inference. Earlier 00Z and later 04/05/06Z belong to
post-readback evaluation. Nothing here is a calibrated pollution-source model.
"""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Mapping, Sequence

import numpy as np

from .advection import CurrentSampler, advect_current
from .benchmark import SphericalLocalFrame, great_circle_distance_m
from .field import OceanField
from .kalman import (
    ACCELERATION_SPECTRAL_DENSITY_M2_S3,
    MAX_LOCAL_M,
    POSITION_STD_M,
    _check_cov,
    _check_state,
    _initialize,
    transition_and_noise,
)
from .ocean_source import GROUP_IDS, STEP_S, _position, _vector, backtrack_current, forecast_sha256

OBSERVATION_TIMES = tuple(f"2022-06-01T0{hour}:00:00Z" for hour in (1, 2, 3))
ANCHOR_TIME = OBSERVATION_TIMES[-1]
BRANCH_HORIZON_S = 10800
TRUTH_TIMES = ("2022-06-01T00:00:00Z", "2022-06-01T04:00:00Z",
               "2022-06-01T05:00:00Z", "2022-06-01T06:00:00Z")
STAGES = [
    {"id": "raw", "title": "Three recorded positions", "formula": "z_k = [east_k, north_k] metres; k=01,02,03 UTC"},
    {"id": "connected", "title": "Connect the observations", "formula": "join z_01 -> z_02 -> z_03; no additional measurements"},
    {"id": "filtered", "title": "Causal Kalman filter", "formula": "x=[E,N,vE,vN]; F=[[I,dt I],[0,I]]; Q=q[[dt^3/3 I,dt^2/2 I],[dt^2/2 I,dt I]]; H=[I,0]; R=100^2 I; Joseph covariance update"},
    {"id": "formula", "title": "Combine movement and changing currents", "formula": "b = v_filtered(03Z) - u(X_filtered(03Z),03Z); dX/dt = u(X,t) + b"},
    {"id": "branches", "title": "Look backward and forward", "formula": "forward: dX/dt=u(X,t)+b; backward: dY/dtau=-(u(Y,03Z-tau)+b); 0<=tau<=3h"},
]
LIMITATIONS = [
    "Separate three-fix research walkthrough; not the frozen eight-or-more-fix Kalman benchmark.",
    "100 m position error and q=1e-6 m^2/s^3 are declared assumptions, not fitted or calibrated uncertainties.",
    "01Z is position-only; 02Z initializes velocity; only 03Z receives a causal measurement update. No RTS smoothing.",
    "ENU state is in an 01Z-anchored mean-sphere frame; its velocity components approximate local east/north forcing.",
    "One constant residual bias persists on each three-hour branch; no windage, retention or coastline process is learned.",
    "All recorded validation positions have been viewed previously; this is retrospective, not independent source validation.",
    "A possible earlier position is not a confirmed release; a forward path is not an interception or reef-protection result.",
]


def filter_three_positions(observations, group_id):
    """Causal states at each fix; never use a later fix to backfill the first."""
    if (not isinstance(observations, Sequence) or isinstance(observations, (str, bytes))
            or len(observations) != 3):
        raise ValueError("EXACTLY_THREE_ALLOWED_OBSERVATIONS_REQUIRED")
    raw = [_position(row, group_id) for row in observations]
    if tuple(row["time_utc"] for row in raw) != OBSERVATION_TIMES:
        raise ValueError("THREE_FIX_CADENCE_OR_TIME_MISMATCH")
    frame = SphericalLocalFrame(raw[0]["latitude_deg"], raw[0]["longitude_deg"])
    xy = np.asarray([frame.to_xy(row["latitude_deg"], row["longitude_deg"]) for row in raw])
    if (not np.isfinite(xy).all() or np.max(np.linalg.norm(xy, axis=1)) > MAX_LOCAL_M):
        raise ValueError("THREE_FIX_POSITION_OUTSIDE_LOCAL_DOMAIN")
    variance = POSITION_STD_M**2
    states = [{**raw[0], "east_m": float(xy[0, 0]), "north_m": float(xy[0, 1]),
               "eastward_m_s": None, "northward_m_s": None, "status": "POSITION_ONLY", "covariance": None}]
    state, covariance = _initialize(xy[:2], 3600., variance)
    for index in (1, 2):
        if index == 2:
            transition, process = transition_and_noise(3600., ACCELERATION_SPECTRAL_DENSITY_M2_S3)
            state = transition @ state
            _check_state(state)
            covariance = _check_cov(transition @ covariance @ transition.T + process, 4, "predicted")
            measurement, noise = np.eye(4)[:2], variance * np.eye(2)
            innovation = _check_cov(measurement @ covariance @ measurement.T + noise, 2, "innovation")
            if float(np.linalg.eigvalsh(innovation).min()) <= 0:
                raise ValueError("INNOVATION_NOT_POSITIVE_DEFINITE")
            gain = np.linalg.solve(innovation, measurement @ covariance).T
            state = state + gain @ (xy[index] - measurement @ state)
            _check_state(state)
            complement = np.eye(4) - gain @ measurement
            covariance = _check_cov(complement @ covariance @ complement.T + gain @ noise @ gain.T, 4, "corrected")
        _vector(state[2:], 10.)
        latitude, longitude = frame.to_latlon(state[:2])
        states.append({"time_utc": raw[index]["time_utc"], "latitude_deg": latitude, "longitude_deg": longitude,
            "east_m": float(state[0]), "north_m": float(state[1]), "eastward_m_s": float(state[2]),
            "northward_m_s": float(state[3]), "status": "INITIALIZED" if index == 1 else "UPDATED",
            "covariance": covariance.tolist()})
    return raw, states


def corrected_current_field(field, bias_east_north_m_s):
    """Independent immutable field copy; enforce the unchanged sampler's limits."""
    CurrentSampler(field)
    bias = _vector(bias_east_north_m_s, 10.)
    arrays = [np.array(value, copy=True) for value in (field.time_utc, field.longitude_deg,
              field.latitude_deg, field.eastward_m_s, field.northward_m_s, field.valid_mask)]
    arrays[3] = arrays[3].astype(float) + bias[0]
    arrays[4] = arrays[4].astype(float) + bias[1]
    metadata = copy.deepcopy(field.metadata)
    digest = hashlib.sha256()
    for array in arrays:
        digest.update(array.tobytes())
        array.setflags(write=False)
    metadata.update(sha256=digest.hexdigest(), source_field_sha256=field.metadata.get("sha256"),
                    data_kind="THREE_FIX_CONSTANT_RESIDUAL_FIELD", velocity_units="m/s",
                    residual_bias_east_north_m_s=bias.tolist())
    result = OceanField(*arrays, field.selected_depth_m, metadata)
    CurrentSampler(result)
    return result


def _empty_branch(backward, reason):
    return {"status": "UNSUPPORTED", "reason_code": reason, "track": [],
            "completed_lookback_s" if backward else "completed_horizon_s": 0.}


def _group(group_id, observations, field, field_failure):
    group = {"group_id": group_id, "status": "UNSUPPORTED", "reason_code": None,
        "raw_observations": [], "connected_path": [], "filtered_states": [],
        "filtered_anchor": None, "formula": None,
        "backward": _empty_branch(True, "FILTER_INPUT_UNSUPPORTED"),
        "forward": _empty_branch(False, "FILTER_INPUT_UNSUPPORTED")}
    try:
        raw, states = filter_three_positions(observations, group_id)
        anchor = {key: states[-1][key] for key in ("time_utc", "latitude_deg", "longitude_deg")}
        group.update(raw_observations=raw, connected_path=copy.deepcopy(raw), filtered_states=states,
                     filtered_anchor=anchor, status="PARTIAL")
    except (ValueError, TypeError, KeyError, OverflowError, np.linalg.LinAlgError) as error:
        group["reason_code"] = str(error) if isinstance(error, ValueError) else "FILTER_INPUT_UNSUPPORTED"
        return group
    if field is None:
        reason = field_failure or "CURRENT_FIELD_UNAVAILABLE"
        group.update(reason_code=reason, backward=_empty_branch(True, reason), forward=_empty_branch(False, reason))
        return group
    try:
        sampler = CurrentSampler(field, time_origin=np.datetime64(ANCHOR_TIME.removesuffix("Z"), "us"))
        current = np.asarray(sampler.sample(anchor["latitude_deg"], anchor["longitude_deg"], 0.))
        velocity = np.asarray([states[-1]["eastward_m_s"], states[-1]["northward_m_s"]])
        bias = _vector(velocity - current, 10.)
        corrected = corrected_current_field(field, bias)
        group["formula"] = {"equation": "dX/dt = u(X,t) + b", "current_east_north_m_s": current.tolist(),
            "filtered_velocity_east_north_m_s": velocity.tolist(), "residual_bias_east_north_m_s": bias.tolist()}
    except (ValueError, TypeError, KeyError, OverflowError, np.linalg.LinAlgError) as error:
        reason = str(error) if isinstance(error, ValueError) else "CURRENT_OR_FILTER_CONTRACT_UNSUPPORTED"
        group.update(reason_code=reason, backward=_empty_branch(True, reason), forward=_empty_branch(False, reason))
        return group
    # A failed past integration does not invalidate a supported future, or vice
    # versa. Both use the same frozen anchor/bias; neither borrows from the other.
    for direction in ("backward", "forward"):
        try:
            if direction == "backward":
                group[direction] = backtrack_current(corrected, anchor, horizon_s=BRANCH_HORIZON_S)
            else:
                forward = advect_current(corrected, latitude_deg=anchor["latitude_deg"],
                    longitude_deg=anchor["longitude_deg"], start_time_utc=ANCHOR_TIME,
                    horizon_s=BRANCH_HORIZON_S, step_s=STEP_S, output_step_s=STEP_S)
                group[direction] = {key: forward[key] for key in
                    ("status", "reason_code", "track", "completed_horizon_s")}
        except (ValueError, TypeError, KeyError, OverflowError, np.linalg.LinAlgError) as error:
            reason = str(error) if isinstance(error, ValueError) else "BRANCH_CONTRACT_UNSUPPORTED"
            group[direction] = _empty_branch(direction == "backward", reason)
    statuses = [group[key]["status"] for key in ("backward", "forward")]
    group["status"] = "COMPLETED" if statuses == ["COMPLETED", "COMPLETED"] else "PARTIAL"
    group["reason_code"] = next((group[key]["reason_code"] for key in ("backward", "forward")
                                 if group[key]["status"] != "COMPLETED"), None)
    return group


def build_pipeline_forecasts(observations_by_group, field, *, field_failure=None):
    if not isinstance(observations_by_group, Mapping) or set(observations_by_group) - set(GROUP_IDS):
        raise ValueError("ONLY_THE_TWO_FIXED_GROUPS_ALLOWED")
    result = {"schema_version": 1, "kind": "THREE_FIX_BIDIRECTIONAL_FORECASTS", "group_ids": list(GROUP_IDS),
        "observation_times_utc": list(OBSERVATION_TIMES), "anchor_time_utc": ANCHOR_TIME,
        "earlier_truth_used": False, "later_truth_used": False, "position_std_m": POSITION_STD_M,
        "acceleration_spectral_density_m2_s3": ACCELERATION_SPECTRAL_DENSITY_M2_S3,
        "analysis_scope": "POST_OUTCOME_EXPLORATORY", "previously_viewed_validation_positions": True,
        "physical_validation": False, "source_attribution_validated": False,
        "stages": copy.deepcopy(STAGES), "groups": [_group(group, observations_by_group.get(group), field,
           field_failure) for group in GROUP_IDS], "limitations": list(LIMITATIONS)}
    result["forecast_sha256"] = forecast_sha256(result)
    return result


def score_pipeline_forecasts(forecasts, truth_by_group):
    """Evaluate saved branches against four separate, previously viewed fixes."""
    if (forecasts.get("forecast_sha256") != forecast_sha256(forecasts)
            or forecasts.get("group_ids") != list(GROUP_IDS) or len(forecasts.get("groups", [])) != 2
            or [group.get("group_id") for group in forecasts["groups"]] != list(GROUP_IDS)):
        raise ValueError("SAVED_PIPELINE_FORECAST_IDENTITY_MISMATCH")
    if not isinstance(truth_by_group, Mapping) or set(truth_by_group) - set(GROUP_IDS):
        raise ValueError("ONLY_THE_TWO_FIXED_GROUPS_ALLOWED")
    rows = []
    for group in forecasts["groups"]:
        reserved = truth_by_group.get(group["group_id"], {})
        for time in TRUTH_TIMES:
            backward = time == TRUTH_TIMES[0]
            direction = "backward" if backward else "forward"
            row = {"group_id": group["group_id"], "direction": direction, "time_utc": time,
                "status": "FORECAST_UNAVAILABLE", "reason_code": "SUPPORTED_FORECAST_TIME_UNAVAILABLE",
                "observed": None, "predicted": None, "error_m": None}
            try:
                target = _position(reserved.get(time), group["group_id"])
                if target["time_utc"] != time:
                    raise ValueError("VALIDATION_TIME_MISMATCH")
                row["observed"] = target
            except (ValueError, TypeError, AttributeError):
                row.update(status="TRUTH_UNAVAILABLE", reason_code="VALIDATION_POSITION_UNAVAILABLE")
                rows.append(row)
                continue
            path = group[direction]["track"]
            matching = next((point for point in path if point["time_utc"] == time), None)
            if matching is not None:
                predicted = _position({key: matching[key] for key in ("time_utc", "latitude_deg", "longitude_deg")})
                row.update(status="SCORED", reason_code=None, predicted=predicted,
                    error_m=great_circle_distance_m((target["latitude_deg"], target["longitude_deg"]),
                                                   (predicted["latitude_deg"], predicted["longitude_deg"])))
            rows.append(row)
    return {"schema_version": 1, "kind": "THREE_FIX_BIDIRECTIONAL_VALIDATION", "planned_rows": 8,
        "scored_rows": sum(row["status"] == "SCORED" for row in rows), "rows": rows,
        "analysis_scope": "POST_OUTCOME_EXPLORATORY", "previously_viewed_validation_positions": True,
        "physical_validation": False, "statistical_independence": False,
        "source_attribution_validated": False}
