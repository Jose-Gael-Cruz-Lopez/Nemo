"""Post-hoc vector scoring of the existing pinned NOAA position forecasts.

No current field, new predictor, tuning, acquisition or model promotion is added.
Predicted intervals are free-running: later starts are previous predictions,
never observed future positions. Metres/second stay separate from tank cm/second.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime

import numpy as np

from .ablation import ABLATION_MODEL_IDS
from .benchmark import (
    MODEL_IDS,
    SphericalLocalFrame,
    great_circle_distance_m,
    run_real_data_example,
)
from .data import parse_drifter_csv
from .multidrifter import load_multidrifter_inputs, run_multidrifter_study

MIN_HEADING_SPEED_M_S = 0.005
HORIZONS = 6


def _timestamp(value):
    if not isinstance(value, str):
        raise TypeError("Explicit UTC timestamp required")
    when = datetime.fromisoformat(value)
    if when.tzinfo is None or when.utcoffset() != UTC.utcoffset(when):
        raise ValueError("Timezone-aware UTC timestamp required")
    return when


def _coordinate(point):
    values = [point["latitude_deg"], point["longitude_deg"]]
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
        raise ValueError("Finite numeric geographic coordinates required")
    return values


def _vector(value):
    east, north = map(float, value)
    speed = math.hypot(east, north)
    return {"eastward_m_s": east, "northward_m_s": north, "speed_m_s": speed,
            "heading_deg_clockwise_from_north": (
                math.degrees(math.atan2(east, north)) % 360
                if speed >= MIN_HEADING_SPEED_M_S else None)}


def vector_diagnostic_from_benchmark(report: dict, *, _model_ids=MODEL_IDS) -> dict:
    """Score one existing 18/6 benchmark without calling any fitting function.

    All three complete forecast tracks are validated/projected before held-out
    coordinates are accessed. Deriving velocities from future observations is
    scoring only, and does not update any predicted interval or parameter.
    """
    if (report.get("data_origin") != "REAL_HISTORICAL_NOAA_DRIFTER"
            or report["split"]["training_count"] != 18
            or report["split"]["heldout_count"] != HORIZONS
            or len(report["training_track"]) != 18
            or len(report["heldout_track"]) != HORIZONS
            or [model["id"] for model in report["models"]] != list(_model_ids)):
        raise ValueError("Require the fixed three-model 18/6 NOAA benchmark")
    frame = SphericalLocalFrame(report["coordinate_system"]["origin_latitude_deg"],
                               report["coordinate_system"]["origin_longitude_deg"])
    anchor = report["training_track"][-1]
    anchor_time = _timestamp(anchor["time_utc"])
    anchor_xy = frame.to_xy(*_coordinate(anchor))
    forecasts = []
    for model in report["models"]:
        if len(model["predictions"]) != HORIZONS:
            raise ValueError("Every declared model requires six matched predictions")
        points = model["predictions"]
        times = [_timestamp(point["time_utc"]) for point in points]
        if any((when - anchor_time).total_seconds() != (index + 1) * 3600
               for index, when in enumerate(times)):
            raise ValueError("Forecast intervals must be strictly increasing hourly UTC")
        xy = [anchor_xy, *[frame.to_xy(*_coordinate(point)) for point in points]]
        forecasts.append((model, points, times, xy))

    # Only now derive the observed held-out track and its velocity intervals.
    truth = report["heldout_track"]
    truth_times = [_timestamp(point["time_utc"]) for point in truth]
    if any((when - anchor_time).total_seconds() != (index + 1) * 3600
           for index, when in enumerate(truth_times)):
        raise ValueError("Observed intervals must match strictly increasing hourly UTC")
    truth_xy = [anchor_xy, *[frame.to_xy(*_coordinate(point)) for point in truth]]
    observed_velocities = [np.subtract(truth_xy[i + 1], truth_xy[i]) / 3600
                           for i in range(HORIZONS)]
    models = []
    for model, points, times, xy in forecasts:
        intervals, angular_errors, errors = [], [], []
        for index, (point, when, observed) in enumerate(
                zip(points, times, observed_velocities, strict=True)):
            start_time = anchor_time if index == 0 else times[index - 1]
            step_s = (when - start_time).total_seconds()
            predicted = np.subtract(xy[index + 1], xy[index]) / step_s
            residual = predicted - observed
            observed_vector, predicted_vector = _vector(observed), _vector(predicted)
            angular = None
            if min(observed_vector["speed_m_s"], predicted_vector["speed_m_s"]) >= MIN_HEADING_SPEED_M_S:
                angular = abs((predicted_vector["heading_deg_clockwise_from_north"]
                               - observed_vector["heading_deg_clockwise_from_north"] + 180) % 360 - 180)
                angular_errors.append(angular)
            error = great_circle_distance_m(tuple(_coordinate(point)),
                                            tuple(_coordinate(truth[index])))
            errors.append(error)
            intervals.append({
                "horizon_hours": index + 1,
                "start_utc": start_time.isoformat().replace("+00:00", "Z"),
                "end_utc": when.isoformat().replace("+00:00", "Z"),
                "interval_seconds": step_s,
                "observed_start": anchor if index == 0 else truth[index - 1],
                "observed_end": truth[index],
                "predicted_start": anchor if index == 0 else points[index - 1],
                "predicted_end": point,
                "observed_velocity": observed_vector,
                "predicted_velocity": predicted_vector,
                "residual_predicted_minus_observed": _vector(residual),
                "angular_error_deg": angular,
                "position_error_m": error,
                "status": "SCORED",
            })
        models.append({"id": model["id"], "label": model["label"], "intervals": intervals,
            "metrics": {
                "vector_rmse_m_s": math.sqrt(sum(row["residual_predicted_minus_observed"]["speed_m_s"] ** 2
                                                 for row in intervals) / HORIZONS),
                "speed_bias_predicted_minus_observed_m_s": sum(
                    row["predicted_velocity"]["speed_m_s"] - row["observed_velocity"]["speed_m_s"]
                    for row in intervals) / HORIZONS,
                "angular_mae_deg": sum(angular_errors) / len(angular_errors) if angular_errors else None,
                "angular_scored_count": len(angular_errors),
                "angular_withheld_count": HORIZONS - len(angular_errors),
                "ade_m": sum(errors) / HORIZONS, "fde_m": errors[-1],
            }})
    result = {
        "schema_version": 1, "kind": "NOAA_VECTOR_MOTION_DIAGNOSTIC", "status": "COMPLETED",
        "data_origin": "REAL_HISTORICAL_NOAA_DRIFTER",
        "design_status": "POST_HOC_ALREADY_VIEWED_FORECASTS_NOT_INDEPENDENT_TEST",
        "experiment_id": report["experiment_id"], "provenance": report.get("provenance", {}),
        "coordinate_system": report["coordinate_system"], "velocity_units": "m/s",
        "vector_basis": "fixed_spherical_local_frame_east_north_metres",
        "minimum_heading_speed_m_s": MIN_HEADING_SPEED_M_S,
        "residual_definition": "predicted_minus_observed_velocity_not_current_forcing_residual",
        "coverage": {"physical_drifters": 1, "models": len(_model_ids), "intervals_per_model": HORIZONS,
                     "attempted_model_intervals": HORIZONS * len(_model_ids),
                     "scored_model_intervals": HORIZONS * len(_model_ids),
                     "failed_model_intervals": 0, "unique_observed_intervals": HORIZONS},
        "models": models,
        "field_forcing_available": False, "debris_survey_context_available": False,
        "independent_evaluation": False, "model_selection_performed": False,
        "automatic_model_promotion": False, "physical_validation": False,
        "calibrated_probability": False, "plastic_source_attribution_supported": False,
        "new_trajectory_acquisition": False,
        "limitations": [
            "Six observed intervals are reused across three models; 18 scores are not 18 independent measurements.",
            "This scores existing forecasts on an already viewed historical buoy-day; it is not new model training or independent evaluation.",
            "NOAA hourly locations are QC/interpolated; upstream processing may use later fixes, so this does not establish raw real-time skill.",
            "Vectors are finite differences in the fixed local spherical metric frame, not direct current measurements or instantaneous velocity.",
            "No matched Copernicus/IOOS current field or MDMAP debris survey is connected; this residual is forecast minus observed motion.",
            "Buoy response/depth differs from floating plastic. No polluter, source probability, interception benefit or reef impact is inferred.",
        ],
    }
    json.dumps(result, allow_nan=False)
    return result


def run_noaa_vector_diagnostic() -> dict:
    """Replay the unchanged pinned benchmark, then score its frozen algorithms."""
    return vector_diagnostic_from_benchmark(run_real_data_example())


_LABELS = {"stationary": "Stationary position persistence",
           "last_drift": "Last observed displacement", "mean_drift": "Mean observed drift",
           "ridge_ar1": "Learned ridge velocity autoregression"}


def _public_point(record):
    return {"time_utc": record.time_utc.isoformat().replace("+00:00", "Z"),
            "latitude_deg": record.latitude_deg, "longitude_deg": record.longitude_deg}


def cohort_vector_diagnostic_from_inputs(study: dict, records_by_id: dict) -> dict:
    """Score the frozen acquired cohort; whole incomplete tracks stay withheld.

    All model coordinates are checked before deriving ANY held-out displacement.
    Raw buoy-day prefixes are not used to tune, refit or choose algorithms here.
    An incomplete source track withholds its six vector intervals rather than
    bridging a missing prediction. Common-cohort aggregate metrics then withhold.
    """
    groups = study["groups"]
    ids = [group["drifter_id"] for group in groups]
    model_ids = tuple(ABLATION_MODEL_IDS)
    if (study.get("kind") != "MULTI_DRIFTER_RETROSPECTIVE_STUDY"
            or study.get("data_origin") != "REAL_HISTORICAL_NOAA_DRIFTERS"
            or study["coverage"]["target_groups"] != 6 or len(ids) != 4
            or len(set(ids)) != 4 or set(ids) != set(records_by_id)
            or study["protocol"]["model_ids"] != list(model_ids)):
        raise ValueError("Require the frozen four-acquired/six-target NOAA cohort")
    expected = {(value, model_id, horizon) for value in ids
                for model_id in model_ids for horizon in range(1, 7)}
    rows = {}
    for row in study["outcomes"]:
        key = row["drifter_id"], row["model_id"], row["horizon_hours"]
        if key not in expected or key in rows or type(row["horizon_hours"]) is not int:
            raise ValueError("Require exact unique cohort/model/horizon identities")
        if row["status"] not in ("SCORED", "FAILED"):
            raise ValueError("Explicit scored/failed outcome required")
        rows[key] = row
    if set(rows) != expected:
        raise ValueError("Missing outcome slots must remain explicit failures")
    prepared = []
    for group in groups:
        value, records = group["drifter_id"], records_by_id[group["drifter_id"]]
        if (len(records) != 24 or any(row.drifter_id != value for row in records)
                or any(_timestamp(row.time_utc.isoformat()) !=
                       _timestamp(group["start_utc"]) + (row.time_utc - records[0].time_utc)
                       for row in records)
                or any((row.time_utc - records[0].time_utc).total_seconds() != index * 3600
                       for index, row in enumerate(records))):
            raise ValueError("Cohort raw records require exact hourly ID and UTC windows")
        # Read prefix coordinates only. Future coordinates stay unread below.
        frame = SphericalLocalFrame(records[0].latitude_deg, records[0].longitude_deg)
        anchor = _public_point(records[17])
        frame.to_xy(*_coordinate(anchor))
        tracks = []
        for model_id in model_ids:
            track = [rows[value, model_id, horizon] for horizon in range(1, 7)]
            for index, point in enumerate(track):
                if (point["block_id"] != group["block_id"]
                        or (_timestamp(point["time_utc"]) - _timestamp(anchor["time_utc"])).total_seconds()
                        != (index + 1) * 3600):
                    raise ValueError("Cohort predictions must match declared block and hourly window")
                if point["status"] == "SCORED":
                    frame.to_xy(*_coordinate(point))
            tracks.append((model_id, track))
        prepared.append((group, records, frame, tracks))

    reports, scored = [], 0
    for group, records, frame, tracks in prepared:
        group_models = []
        for model_id, track in tracks:
            reasons = sorted({reason for point in track for reason in point["reason_codes"]})
            if any(point["status"] != "SCORED" for point in track):
                group_models.append({"id": model_id, "label": _LABELS[model_id],
                    "status": "WITHHELD", "reason_codes": ["INCOMPLETE_FORECAST_TRACK", *reasons],
                    "intervals": [{"horizon_hours": index + 1, "end_utc": point["time_utc"],
                                   "status": "FAILED", "reason_codes": ["INCOMPLETE_FORECAST_TRACK"]}
                                  for index, point in enumerate(track)], "metrics": None})
                continue
            legacy = {"data_origin": "REAL_HISTORICAL_NOAA_DRIFTER",
                "split": {"training_count": 18, "heldout_count": 6},
                "training_track": [_public_point(record) for record in records[:18]],
                "heldout_track": [_public_point(record) for record in records[18:]],
                "coordinate_system": {"origin_latitude_deg": frame.latitude_deg,
                    "origin_longitude_deg": frame.longitude_deg,
                    "fit": "spherical_azimuthal_equidistant_east_north_metres"},
                "models": [{"id": model_id, "label": _LABELS[model_id], "predictions": track}],
                "experiment_id": study["study_id"] + ":" + group["drifter_id"]}
            result = vector_diagnostic_from_benchmark(legacy, _model_ids=(model_id,))
            group_models.append({**result["models"][0], "status": "SCORED", "reason_codes": []})
            scored += 6
        reports.append({"drifter_id": group["drifter_id"], "block_id": group["block_id"],
                        "start_utc": group["start_utc"], "end_utc": group["end_utc"],
                        "coordinate_system": {"origin_latitude_deg": frame.latitude_deg,
                            "origin_longitude_deg": frame.longitude_deg}, "models": group_models})
    complete = scored == len(expected)
    aggregates = []
    for model_id in model_ids:
        tracks = [next(model for model in group["models"] if model["id"] == model_id)
                  for group in reports]
        valid = [track for track in tracks if track["status"] == "SCORED"]
        metrics = None
        if complete:
            # Equal drifter weight, then equal six-hour interval weight within it.
            angles = [row["angular_error_deg"] for track in valid for row in track["intervals"]
                      if row["angular_error_deg"] is not None]
            metrics = {
                "vector_rmse_m_s": math.sqrt(sum(track["metrics"]["vector_rmse_m_s"] ** 2
                                                 for track in valid) / len(valid)),
                "speed_bias_predicted_minus_observed_m_s": sum(
                    track["metrics"]["speed_bias_predicted_minus_observed_m_s"]
                    for track in valid) / len(valid),
                "angular_mae_deg": sum(angles) / len(angles) if angles else None,
                "angular_scored_count": len(angles), "angular_withheld_count": 24 - len(angles),
                "ade_m": sum(track["metrics"]["ade_m"] for track in valid) / len(valid),
                "fde_m": sum(track["metrics"]["fde_m"] for track in valid) / len(valid),
            }
        aggregates.append({"id": model_id, "label": _LABELS[model_id], "metrics": metrics,
            "complete_drifters": len(valid), "attempted_drifters": 4,
            "reason_codes": [] if complete else ["INCOMPLETE_COMMON_ACQUIRED_COHORT"]})
    report = {"schema_version": 1, "kind": "NOAA_COHORT_VECTOR_MOTION_DIAGNOSTIC",
        "status": "PARTIAL_COVERAGE", "study_id": study["study_id"],
        "data_origin": "REAL_HISTORICAL_NOAA_DRIFTERS",
        "design_status": "POST_HOC_ALREADY_VIEWED_COHORT_NOT_INDEPENDENT_TEST",
        "metric_scope": "ACQUIRED_FOUR_DRIFTERS_NOT_SIX_TARGET_GROUPS",
        "aggregation": {
            "vector_rmse": "square_root_of_equal_drifter_mean_squared_interval_errors",
            "speed_bias_ade_fde": "equal_drifter_mean_of_each_complete_track_metric",
            "angular_mae": "all_eligible_intervals_with_explicit_scored_and_withheld_counts",
        },
        "velocity_units": "m/s", "vector_basis": "per_drifter_fixed_local_spherical_east_north_metres",
        "minimum_heading_speed_m_s": MIN_HEADING_SPEED_M_S,
        "residual_definition": "predicted_minus_observed_velocity_not_current_forcing_residual",
        "coverage": {"target_drifters": 6, "acquired_drifters": 4, "missing_drifters": 2,
            "models": 4, "model_tracks": 16, "intervals_per_track": 6,
            "planned_model_intervals": 144, "attempted_model_intervals": 96,
            "scored_model_intervals": scored, "failed_model_intervals": 96 - scored,
            "unique_observed_intervals": 24, "common_acquired_cohort_complete": complete},
        "groups": reports, "models": aggregates,
        "selection_failures": study["selection_failures"], "provenance": study["provenance"],
        "protocol": study["protocol"], "field_forcing_available": False,
        "physical_alias_resolution_verified": False,
        "debris_survey_context_available": False, "independent_evaluation": False,
        "model_selection_performed": False, "automatic_model_promotion": False,
        "physical_validation": False, "calibrated_probability": False,
        "plastic_source_attribution_supported": False, "new_trajectory_acquisition": False,
        "limitations": [
            "Four acquired historical drifters and 24 reused observed intervals yield 96 model scores, not 96 independent measurements.",
            "Two target metadata slots remain missing; acquired-cohort averages do not describe the unacquired six-group target.",
            "These drifters and forecasts were already viewed; post-hoc vector analysis is not a fresh unseen evaluation or model promotion.",
            "Hourly NOAA positions are QC/interpolated and may have upstream future-fix support; no operational real-time skill is established.",
            "Vectors are finite differences in per-drifter local frames, not direct water-current or plastic measurements.",
            "No independent current forcing, debris survey, known plastic source or intervention outcome is connected.",
            "Incomplete tracks withhold all their velocity intervals; no velocity bridges a missing prediction and common-cohort aggregate metrics withhold.",
        ]}
    json.dumps(report, allow_nan=False)
    return report


def run_noaa_cohort_vector_diagnostic() -> dict:
    """Replay the unchanged pinned cohort, then score its actual motion vectors."""
    study = run_multidrifter_study()
    _, _, manifest, raw, _ = load_multidrifter_inputs()
    records = {entry["drifter_id"]: parse_drifter_csv(raw[entry["raw_path"]].decode("utf-8"))
               for entry in manifest["trajectories"]}
    return cohort_vector_diagnostic_from_inputs(study, records)
