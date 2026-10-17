"""Read-only deterministic forward replay of frozen recorded drift validation runs.

Only each run's initial position enters prediction. Later observed coordinates
are read after every run's forecasts exist. This is a mean-field diagnostic,
not the stochastic source estimator, a retention model or independent validation.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math

import numpy as np

from apps.transport.reeftrace_transport.flow import FlowField
from apps.transport.reeftrace_transport.geometry import advance_reflecting

from .field_vector_diagnostic import _digest, _fake, _identifier, _load

MAX_POINTS = 20000
MAX_STEPS_PER_RUN = 2000
MAX_TOTAL_STEPS = 20000
MAX_HORIZON_S = 20.0
MAX_STEP_S = 0.05
MAX_GAP_S = 0.5


def _xy(point):
    values = [point.get("x_cm"), point.get("y_cm")]
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
        raise ValueError("Observed drift coordinates must be finite numbers")
    return np.asarray(values, dtype=float)


def _segment_supported(field, start, end):
    """Require complete coverage by the union of measured-node support disks.

    Each disk contributes an analytically calculated interval along this straight
    segment. Their union must cover [0, 1] without filling any gap by tolerance.
    Roundoff may conservatively withhold a tangential/near-touching case; endpoint
    coverage alone never establishes support between endpoints.
    """
    if not field.bounds.contains(np.asarray([start, end])).all():
        return False
    delta = np.asarray(end) - start
    length = float(np.linalg.norm(delta))
    if length == 0:
        return bool(field.evaluate([start])[1][0])
    direction = delta / length
    relative = field.xy - start
    projection = relative @ direction
    perpendicular = relative - projection[:, None] * direction
    distance = np.linalg.norm(perpendicular, axis=1)
    eligible = distance <= field.radius
    # (r-d)*(r+d) avoids cancellation from subtracting squared near-equal radii.
    half = np.sqrt(np.maximum(0, (field.radius - distance[eligible])
                              * (field.radius + distance[eligible])))
    starts = (projection[eligible] - half) / length
    ends = (projection[eligible] + half) / length
    intervals = sorted((max(0.0, float(low)), min(1.0, float(high)))
                       for low, high in zip(starts, ends, strict=True)
                       if high >= 0 and low <= 1)
    covered = 0.0
    for low, high in intervals:
        if low > covered:
            return False
        covered = max(covered, high)
        if covered >= 1:
            return True
    return False


def _reflected_path_supported(field, start, delta):
    """Check each actual reflected subsegment, not a chord between final nodes.

    Wall timing and simultaneous-axis reflection mirror advance_reflecting with
    no traps. The same finite collision budget is retained. A zero final chord
    can therefore still be unsupported when a path went out to a wall and back.
    """
    position, remaining = np.array(start, dtype=float), np.array(delta, dtype=float)
    for _ in range(12):
        wall_times = np.full(2, np.inf)
        for axis, low, high in ((0, field.bounds.x_min_cm, field.bounds.x_max_cm),
                                (1, field.bounds.y_min_cm, field.bounds.y_max_cm)):
            if abs(remaining[axis]) > 1e-14:
                target = high if remaining[axis] > 0 else low
                value = (target - position[axis]) / remaining[axis]
                if -1e-10 <= value <= 1:
                    wall_times[axis] = max(value, 0)
        wall_time = float(wall_times.min())
        end = position + remaining * (wall_time if math.isfinite(wall_time) else 1)
        if not _segment_supported(field, position, end):
            return False
        if not math.isfinite(wall_time):
            return True
        position = end
        remaining *= 1 - wall_time
        remaining[np.isclose(wall_times, wall_time, atol=1e-10)] *= -1
    return False


def _forecast(field, points, remaining_steps=MAX_TOTAL_STEPS):
    """Preflight metadata, then advance from the initial coordinate only."""
    times = [point.get("t_s") for point in points]
    if (any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in times)
            or any(later <= earlier for earlier, later in itertools.pairwise(times))):
        raise ValueError("Saved offsets must be finite, nonnegative and strictly increasing")
    horizon = times[-1] - times[0]
    if horizon > MAX_HORIZON_S:
        return None, ["HORIZON_BUDGET_EXCEEDED"], 0
    first_track = points[0].get("track_id")
    if (not isinstance(first_track, str) or not first_track
            or any(point.get("observed") is not True or point.get("track_id") != first_track
                   or point.get("association_break") is True and index > 0
                   for index, point in enumerate(points))
            or any(later - earlier > MAX_GAP_S for earlier, later in itertools.pairwise(times))):
        return None, ["MISSING_OR_BROKEN_TRACK"], 0
    position = _xy(points[0])[None, :]
    if not field.bounds.contains(position).all():
        return None, ["INITIAL_POSITION_OUTSIDE_TANK"], 0
    maximum_speed = float(np.linalg.norm(field.velocity, axis=1).max())
    if maximum_speed > 100:
        return None, ["DRIFT_SPEED_BUDGET_EXCEEDED"], 0
    step_limit = min(MAX_STEP_S, float(field.bounds.size.min()) / (2 * maximum_speed)) if maximum_speed else MAX_STEP_S
    counts = [max(1, math.ceil((later - earlier) / step_limit))
              for earlier, later in itertools.pairwise(times)]
    if sum(counts) > MAX_STEPS_PER_RUN:
        return None, ["INTEGRATION_BUDGET_EXCEEDED"], 0
    if sum(counts) > remaining_steps:
        return None, ["TOTAL_INTEGRATION_BUDGET_EXCEEDED"], 0
    predictions, steps = [], 0
    for earlier, later, count in zip(times, times[1:], counts, strict=False):
        dt = (later - earlier) / count
        for _ in range(count):
            velocity, supported = field.evaluate(position)
            if not supported.all():
                return None, ["UNSUPPORTED_FORECAST_PATH"], steps
            if not _reflected_path_supported(field, position[0], velocity[0] * dt):
                return None, ["UNSUPPORTED_FORECAST_PATH"], steps
            position, _ = advance_reflecting(position, velocity * dt, field.bounds, [])
            steps += 1
            if not field.evaluate(position)[1].all():
                return None, ["UNSUPPORTED_FORECAST_PATH"], steps
        predictions.append({"t_s": float(later), "x_cm": float(position[0, 0]),
                            "y_cm": float(position[0, 1])})
    return predictions, [], steps


def inspect_recorded_flow_trajectories(store, flow_id):
    """Verify artifact bindings; forecast all runs, then score future coordinates."""
    flow = _load(store, "flow", flow_id)
    provenance = flow.get("provenance") or {}
    if flow.get("data_origin") != "MEASURED_TANK" or provenance.get("frame_splits_disjoint") is not True:
        raise ValueError("Select a recorded flow with explicit disjoint recording provenance")
    calibration_id = _identifier(provenance.get("calibration_id"))
    session_id = _identifier(provenance.get("camera_session_id"))
    calibration = _load(store, "calibration", calibration_id)
    body = {key: value for key, value in calibration.items() if key not in {"id", "calibration_id"}}
    expected = "cal-" + hashlib.sha256(json.dumps(body, sort_keys=True, allow_nan=False).encode()).hexdigest()[:16]
    if (not calibration.get("approved") or calibration.get("calibration_id") != expected
            or expected != calibration_id or calibration.get("camera_session_id") != session_id):
        raise ValueError("Frozen mapping integrity or camera-session binding failed")
    splits = {}
    for split in ("training", "validation"):
        ids = provenance.get(f"{split}_recording_ids")
        if not isinstance(ids, list) or not 1 <= len(ids) <= 100:
            raise ValueError("Both splits must name 1..100 complete recordings")
        ids = [_identifier(value) for value in ids]
        if len(set(ids)) != len(ids):
            raise ValueError("Recording references must be distinct")
        splits[split] = ids
    if set(splits["training"]) & set(splits["validation"]):
        raise ValueError("Recording splits overlap")
    field = FlowField(flow)
    total_points, seen_frames, validation = 0, set(), []
    synthetic = _fake(flow) or _fake(calibration)
    for split, ids in splits.items():
        for identifier in ids:
            recording = _load(store, "recording", identifier)
            if (recording.get("data_origin") != "MEASURED_TANK"
                    or recording.get("calibration_id") != calibration_id
                    or recording.get("camera_session_id") != session_id
                    or recording.get("timestamp_kind") != "host_receipt_not_exposure"):
                raise ValueError("Recording mapping, origin, session or time-kind mismatch")
            points, frames = recording.get("points"), recording.get("evidence_frame_ids")
            if (not isinstance(points, list) or len(points) < 2 or not isinstance(frames, list)
                    or len(points) != len(frames)):
                raise ValueError("Saved drift recordings require matching points and frame references")
            total_points += len(points)
            if total_points > MAX_POINTS:
                raise ValueError("Saved drift point budget exceeded")
            frames = [_identifier(value) for value in frames]
            if len(set(frames)) != len(frames) or seen_frames & set(frames):
                raise ValueError("Saved recording frames are reused")
            for point, frame_id in zip(points, frames, strict=True):
                if not isinstance(point, dict) or point.get("frame_id") != frame_id:
                    raise ValueError("Recorded points and frames do not match")
                frame = _load(store, "frame", frame_id)
                if frame.get("camera_session_id") != session_id:
                    raise ValueError("Saved frame belongs to another camera session")
                synthetic = synthetic or _fake(frame) or _fake(point)
            seen_frames.update(frames)
            synthetic = synthetic or _fake(recording)
            if split == "validation":
                validation.append(recording)

    # All mean-field trajectories exist before reading any later observed XY.
    prepared, total_steps = [], 0
    for recording in validation:
        predictions, reasons, steps = _forecast(field, recording["points"], MAX_TOTAL_STEPS - total_steps)
        total_steps += steps
        prepared.append((recording, predictions, reasons, steps))
    origin = "SYNTHETIC_CAPTURE_REPLAY" if synthetic else "RECORDED_TANK_CAPTURE_UNVERIFIED"
    runs, errors = [], []
    for recording, predictions, reasons, steps in prepared:
        points, comparisons = recording["points"], []
        if predictions is not None:
            for prediction, observed in zip(predictions, points[1:], strict=True):
                actual = _xy(observed)
                if not field.bounds.contains(actual[None, :]).all():
                    raise ValueError("Saved observed position is outside declared tank bounds")
                error = float(np.linalg.norm(_xy(prediction) - actual))
                comparisons.append({"t_s": prediction["t_s"], "predicted_x_cm": prediction["x_cm"],
                    "predicted_y_cm": prediction["y_cm"], "observed_x_cm": float(actual[0]),
                    "observed_y_cm": float(actual[1]), "position_error_cm": error})
        values = [row["position_error_cm"] for row in comparisons]
        metrics = {"ade_cm": float(np.mean(values)), "fde_cm": values[-1],
                   "position_rmse_cm": float(np.sqrt(np.mean(np.square(values))))} if values else None
        errors.extend(values)
        runs.append({"recording_id": recording["id"], "recording_content_hash": _digest(recording),
            "status": "SCORED" if predictions is not None else "WITHHELD", "reason_codes": reasons,
            "data_origin": origin, "physical_validation": False,
            "planned_forecast_points": len(points) - 1, "scored_forecast_points": len(comparisons),
            "integration_steps": steps, "horizon_s": float(points[-1]["t_s"] - points[0]["t_s"]),
            "time_origin_s": float(points[0]["t_s"]),
            "initial_position": {"t_s": points[0]["t_s"], "x_cm": points[0].get("x_cm"),
                                 "y_cm": points[0].get("y_cm")},
            "comparisons": comparisons, "metrics": metrics})
    complete = all(run["status"] == "SCORED" for run in runs)
    metrics = None
    if complete:
        metrics = {"equal_recording_ade_cm": float(np.mean([run["metrics"]["ade_cm"] for run in runs])),
                   "equal_recording_fde_cm": float(np.mean([run["metrics"]["fde_cm"] for run in runs])),
                   "pooled_position_rmse_cm": float(np.sqrt(np.mean(np.square(errors))))}
    planned = sum(run["planned_forecast_points"] for run in runs)
    report = {"schema_version": 1, "kind": "RECORDED_FIELD_TRAJECTORY_DIAGNOSTIC",
        "status": "COMPLETED" if complete else "WITHHELD_INCOMPLETE_RUNS",
        "scope": "ALREADY_REVIEWED_RECORDINGS_DETERMINISTIC_MEAN_FIELD_NOT_INDEPENDENT_TEST",
        "flow_id": flow_id, "flow_content_hash": _digest(flow), "calibration_id": calibration_id,
        "camera_session_id": session_id, "data_origin": origin, "physical_validation": False,
        "capture_independently_verified": False, "bounds": field.bounds.to_dict(),
        "position_units": "cm", "time_units": "s", "timestamp_kind": "host_receipt_not_exposure",
        "model": {"kind": "DETERMINISTIC_FROZEN_MEAN_FIELD", "maximum_step_s": MAX_STEP_S,
                  "boundary": "reflecting_rectangle", "traps": "NONE", "diffusivity_cm2_s": 0,
                  "initial_observation_only": True, "observed_position_updates": False},
        "integration": {"total_steps": total_steps, "maximum_total_steps": MAX_TOTAL_STEPS,
                        "maximum_steps_per_run": MAX_STEPS_PER_RUN,
                        "maximum_horizon_s": MAX_HORIZON_S, "maximum_observation_gap_s": MAX_GAP_S},
        "coverage": {"validation_recordings": len(runs), "complete_recordings": sum(
            run["status"] == "SCORED" for run in runs), "planned_forecast_points": planned,
            "scored_forecast_points": len(errors), "withheld_forecast_points": planned - len(errors)},
        "provenance": {"training_recording_ids": splits["training"],
                       "validation_recording_ids": splits["validation"], "frame_splits_disjoint": True},
        "recordings": runs, "metrics": metrics, "camera_started": False,
        "hardware_actuation": False, "store_written": False, "refit_performed": False,
        "model_selection_performed": False, "independent_evaluation": False,
        "provider_calls": False, "calibrated_probability": False,
        "limitations": [
            "Already reviewed validation recordings; this is not a fresh independent test or proof of physical capture.",
            "Frozen mean drift only, with reflecting walls and no traps or dispersion; not the stochastic source or prevention simulator.",
            "Only the initial observed position initializes forecasts; later positions are used for scoring after every forecast exists.",
            "Any missing/broken track, long gap or unsupported predicted path withholds the full run and common aggregate metrics.",
            "Every reflected integration subsegment must be continuously covered by the union of node-support disks; covered endpoints alone are insufficient.",
            "Positions within a recording are dependent; pooled position counts are not independent trial counts.",
            "Actual saved host-receipt offsets are used, not exposure times; no protected-zone entry, retention or intervention benefit is evaluated.",
        ]}
    json.dumps(report, allow_nan=False)
    return report
