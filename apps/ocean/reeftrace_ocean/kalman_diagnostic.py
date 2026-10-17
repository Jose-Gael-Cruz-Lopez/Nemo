"""Fixed-parameter post-hoc Kalman comparison on four already viewed buoy-days.

Twenty complete forecast tracks exist before any held-out coordinate is read.
Every declared outcome stays in coverage; one failed track withholds all common
model aggregates. Neither this study nor its Gaussian spread establishes skill
on unseen data, physical capture, calibrated probability or source attribution.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC

import numpy as np

from .ablation import ABLATION_MODEL_IDS, mean_drift_forecast
from .benchmark import (
    EARTH_MEAN_RADIUS_M,
    ROOT,
    SphericalLocalFrame,
    _forecast,
    great_circle_distance_m,
)
from .data import parse_drifter_csv
from .kalman import ACCELERATION_SPECTRAL_DENSITY_M2_S3, POSITION_STD_M, _fit_and_forecast
from .multidrifter import load_multidrifter_inputs

DIRECTORY = ROOT / "data/public/noaa-fixed-kalman-diagnostic-v1"
PROTOCOL_SHA256 = "a50881870c14d992a296fb29a524f5b5d833188f984846014cce67001bb729af"
MODEL_IDS = (*ABLATION_MODEL_IDS, "kalman_cv")
DRIFTER_IDS = ("12730", "12731", "300234063243480", "300234063472530")
LABELS = {"stationary": "Stationary position persistence", "last_drift": "Last observed drift",
          "mean_drift": "Mean observed drift", "ridge_ar1": "Own-prefix ridge velocity AR(1)",
          "kalman_cv": "Fixed-noise constant-velocity Kalman"}
CHI2 = {"nominal50": -2 * math.log(.5), "nominal90": -2 * math.log(.1)}
FLOAT_REL_TOL = 1e-10
FLOAT_ABS_TOL = 1e-8


def _time(value):
    return value.isoformat().replace("+00:00", "Z")


def _point(record, frame):
    xy = frame.to_xy(record.latitude_deg, record.longitude_deg)
    return {"time_utc": _time(record.time_utc), "latitude_deg": float(record.latitude_deg),
            "longitude_deg": float(record.longitude_deg), "x_m": float(xy[0]), "y_m": float(xy[1])}


def _one_forecast(model_id, prefix_xy, prefix_times, future_times):
    """Consume only one training prefix; return a complete free-running track."""
    covariances = None
    anchor = prefix_xy[-1].copy()
    if model_id == "kalman_cv":
        positions, covariances, state, _ = _fit_and_forecast(prefix_times, prefix_xy, future_times)
        anchor = state[:2]
        parameters = {"position_std_m": POSITION_STD_M, "measurement_variance_m2": POSITION_STD_M**2,
            "acceleration_spectral_density_m2_s3": ACCELERATION_SPECTRAL_DENSITY_M2_S3,
            "forecast_start": "FILTERED_LAST_TRAINING_STATE", "parameter_fitting_performed": False,
            "initialization": "SECOND_POSITION_AND_FIRST_DIFFERENCE_WITH_CORRELATED_COVARIANCE",
            "initialization_assumptions": "CONSTANT_FIRST_INTERVAL_VELOCITY_AND_INDEPENDENT_IID_ISOTROPIC_POSITION_ERRORS",
            "noaa_velocity_uncertainty_used": False}
    elif model_id == "mean_drift":
        positions = mean_drift_forecast(prefix_xy, 6, 3600)
        parameters = {"forecast_start": "RAW_LAST_TRAINING_POSITION", "learned_parameters": 2}
    else:
        positions, parameters = _forecast(prefix_xy, 6, 3600, model_id)
        parameters = {**parameters, "forecast_start": "RAW_LAST_TRAINING_POSITION"}
    return positions, covariances, np.asarray(anchor), parameters


def diagnostic_predictions(records_by_id):
    """Build all 4x5 tracks without inspecting ANY future latitude/longitude."""
    if tuple(sorted(records_by_id, key=int)) != DRIFTER_IDS:
        raise ValueError("Require the exact four already-viewed acquired drifter IDs")
    prepared = {}
    for identifier in DRIFTER_IDS:
        records = records_by_id[identifier]
        if (len(records) != 24 or any(row.drifter_id != identifier for row in records)
                or any(row.time_utc.tzinfo is None or row.time_utc.utcoffset() != UTC.utcoffset(row.time_utc)
                       for row in records)
                or any((row.time_utc - records[0].time_utc).total_seconds() != index * 3600
                       for index, row in enumerate(records))):
            raise ValueError("Require exact 24-row hourly UTC identities for each acquired drifter")
        frame = SphericalLocalFrame(records[0].latitude_deg, records[0].longitude_deg)
        training = [_point(row, frame) for row in records[:18]]
        prefix_xy = np.asarray([[row["x_m"], row["y_m"]] for row in training])
        times = np.arange(18, dtype=float) * 3600
        future = np.arange(18, 24, dtype=float) * 3600
        tracks = {}
        for model_id in MODEL_IDS:
            try:
                positions, covariance, anchor, parameters = _one_forecast(model_id, prefix_xy, times, future)
                # Convert every prediction before any future coordinates are read.
                predictions = []
                for index, xy in enumerate(positions):
                    latitude, longitude = frame.to_latlon(xy)
                    predictions.append({"horizon_hours": index + 1,
                        "time_utc": _time(records[18 + index].time_utc),
                        "latitude_deg": latitude, "longitude_deg": longitude,
                        "x_m": float(xy[0]), "y_m": float(xy[1]),
                        "position_covariance_m2": None if covariance is None else covariance[index].tolist(),
                        "observation_covariance_m2": None if covariance is None else (
                            covariance[index] + POSITION_STD_M**2 * np.eye(2)).tolist()})
                tracks[model_id] = {"predictions": predictions, "parameters": parameters,
                    "forecast_anchor": {"x_m": float(anchor[0]), "y_m": float(anchor[1]),
                                        "time_utc": _time(records[17].time_utc)}, "reason_codes": []}
            except (ValueError, OverflowError, FloatingPointError, np.linalg.LinAlgError):
                tracks[model_id] = {"predictions": None, "parameters": {}, "forecast_anchor": None,
                                    "reason_codes": ["NUMERICAL_OR_LOCAL_DOMAIN_FAILURE"]}
        prepared[identifier] = {"frame": frame, "training_track": training, "models": tracks}
    return prepared


def diagnostic_from_records(records_by_id, block_ids=None):
    """Numerical helper; caller-supplied records retain UNVERIFIED origin."""
    prepared = diagnostic_predictions(records_by_id)
    groups, scored, ellipse_rows = [], 0, []
    for identifier in DRIFTER_IDS:
        state = prepared[identifier]
        truth = [_point(row, state["frame"]) for row in records_by_id[identifier][18:]]
        models = []
        for model_id in MODEL_IDS:
            track = state["models"][model_id]
            rows, errors, vector_errors, hits = [], [], [], []
            observed_previous = np.array([state["training_track"][-1][key] for key in ("x_m", "y_m")])
            predicted_previous = None if track["forecast_anchor"] is None else np.array([
                track["forecast_anchor"][key] for key in ("x_m", "y_m")])
            for index, actual in enumerate(truth):
                row = {"horizon_hours": index + 1, "time_utc": actual["time_utc"],
                    "status": "FAILED", "reason_codes": track["reason_codes"],
                    **dict.fromkeys(("latitude_deg", "longitude_deg", "x_m", "y_m", "position_error_m",
                                     "position_covariance_m2", "observation_covariance_m2", "ellipse_hits"))}
                if track["predictions"] is not None:
                    prediction = track["predictions"][index]
                    error = great_circle_distance_m((prediction["latitude_deg"], prediction["longitude_deg"]),
                                                    (actual["latitude_deg"], actual["longitude_deg"]))
                    actual_xy = np.array([actual["x_m"], actual["y_m"]])
                    predicted_xy = np.array([prediction["x_m"], prediction["y_m"]])
                    residual_velocity = ((predicted_xy - predicted_previous)
                                         - (actual_xy - observed_previous)) / 3600
                    vector_errors.append(float(np.dot(residual_velocity, residual_velocity)))
                    ellipse = None
                    if prediction["observation_covariance_m2"] is not None:
                        residual = predicted_xy - actual_xy
                        squared = float(residual @ np.linalg.solve(
                            prediction["observation_covariance_m2"], residual))
                        if not math.isfinite(squared) or squared < -1e-8:
                            raise ValueError("Observed ellipse score must be finite and nonnegative")
                        ellipse = {key: squared <= threshold for key, threshold in CHI2.items()}
                        hits.append(ellipse)
                    row.update(**prediction, status="SCORED", reason_codes=[],
                               position_error_m=error, ellipse_hits=ellipse)
                    errors.append(error)
                    scored += 1
                    observed_previous, predicted_previous = actual_xy, predicted_xy
                rows.append(row)
            metrics = {"ade_m": float(np.mean(errors)), "fde_m": errors[-1],
                       "vector_rmse_m_s": math.sqrt(float(np.mean(vector_errors)))} if errors else None
            models.append({"id": model_id, "label": LABELS[model_id],
                "status": "SCORED" if errors else "FAILED", "reason_codes": track["reason_codes"],
                "forecast_anchor": track["forecast_anchor"], "parameters": track["parameters"],
                "predictions": rows, "metrics": metrics})
            if model_id == "kalman_cv":
                ellipse_rows.append({"drifter_id": identifier, "scored_count": len(hits),
                    **{key + "_hit_count": sum(hit[key] for hit in hits) if hits else None for key in CHI2},
                    **{key + "_hit_fraction": sum(hit[key] for hit in hits) / len(hits) if hits else None for key in CHI2}})
        groups.append({"drifter_id": identifier, "block_id": (block_ids or {}).get(identifier, "UNVERIFIED"),
            "coordinate_system": {"origin_latitude_deg": state["frame"].latitude_deg,
                                  "origin_longitude_deg": state["frame"].longitude_deg},
            "training_track": state["training_track"], "heldout_track": truth, "models": models})
    complete = scored == 120
    aggregates = []
    for index, model_id in enumerate(MODEL_IDS):
        tracks = [group["models"][index] for group in groups]
        successful = [track for track in tracks if track["status"] == "SCORED"]
        metrics = None
        if complete:
            metrics = {"ade_m": float(np.mean([track["metrics"]["ade_m"] for track in tracks])),
                "fde_m": float(np.mean([track["metrics"]["fde_m"] for track in tracks])),
                "vector_rmse_m_s": math.sqrt(float(np.mean([
                    track["metrics"]["vector_rmse_m_s"]**2 for track in tracks])))}
        aggregates.append({"id": model_id, "label": LABELS[model_id], "complete_groups": len(successful),
            "metrics": metrics, "reason_codes": [] if complete else ["INCOMPLETE_COMMON_ACQUIRED_COHORT"]})
    return {"schema_version": 1, "kind": "FIXED_KALMAN_MOTION_DIAGNOSTIC",
        "status": "COMPLETED" if complete else "INCOMPLETE_OUTCOMES", "data_origin": "UNVERIFIED_RECORDS",
        "design_status": "POST_HOC_ALREADY_VIEWED_FIXED_PARAMETER_COMPARISON",
        "coordinate_system": {"position_units": "m", "velocity_units": "m/s",
            "projection": "spherical_azimuthal_equidistant", "earth_mean_radius_m": EARTH_MEAN_RADIUS_M,
            "position_error": "great_circle_on_declared_mean_radius_sphere"},
        "coverage": {"target_groups": 6, "acquired_groups": 4, "missing_groups": 2, "models": 5,
            "horizons": 6, "planned_outcomes": 180, "attempted_outcomes": 120,
            "scored_outcomes": scored, "failed_outcomes": 120 - scored,
            "unique_observed_intervals": 24, "common_acquired_cohort_complete": complete},
        "groups": groups, "models": aggregates,
        "uncertainty": {"kind": "UNCALIBRATED_OBSERVATION_PREDICTIVE_ELLIPSE_HITS",
            "comparison_covariance": "position_covariance_plus_assumed_R", "chi2_thresholds": CHI2,
            "per_drifter": ellipse_rows, "fraction_ranges": {key: {
                "min": min(row[key + "_hit_fraction"] for row in ellipse_rows),
                "max": max(row[key + "_hit_fraction"] for row in ellipse_rows)} for key in CHI2} if complete else None},
        "test_data_used": True, "physical_validation": False, "calibrated_probability": False,
        "independent_evaluation": False, "automatic_model_promotion": False,
        "model_selection_performed": False, "parameter_fitting_performed": False,
        "parameter_fitting_scope": "KALMAN_NOISE_HYPERPARAMETERS_ONLY",
        "new_trajectory_acquisition": False, "physical_alias_resolution_verified": False,
        "camera_started": False, "provider_calls": False, "store_written": False,
        "limitations": [
            "Fixed q=1e-6 m²/s³ and assumed position standard deviation=100 m were declared before this new score, not tuned or fitted NOAA errors.",
            "The no-parameter-fitting flag applies only to Kalman noise hyperparameters; its state is estimated, and fixed baseline algorithms can adapt parameters on their allowed prefixes.",
            "This is a post-hoc comparison of already viewed drifters, not an independent unseen test or evidence of generalization.",
            "The four acquired buoy-days leave two original target slots missing; 120 scores reuse 24 observed intervals and are not independent trials.",
            "Initialization assumes constant first-interval velocity and independent IID isotropic position errors; NOAA interpolation can violate both assumptions.",
            "Kalman starts at the filtered last training state. Other models start at the raw last training position. No future measurement updates occur.",
            "Latent position covariance and future-observation covariance are distinct; ellipse hits compare observed positions against position covariance plus assumed R.",
            "Nominal ellipse levels are model assumptions, not calibrated confidence, source probabilities or independent coverage estimates.",
            "NOAA hourly positions are QC/interpolated and may use future fixes upstream; raw real-time operational skill is not established.",
            "The Kalman model has no current forcing, walls, retention, debris-source identity, physical tank validation or ecological benefit model.",
        ]}


def _pinned_json(name, expected=None):
    payload = (DIRECTORY / (name + ".json")).read_bytes()
    if len(payload) > 1_000_000:
        raise ValueError("Kalman diagnostic artifact exceeds its byte budget")
    actual = hashlib.sha256(payload).hexdigest()
    if (expected is not None and actual != expected) or (DIRECTORY / (name + ".sha256")).read_text().strip() != actual:
        raise ValueError("Kalman diagnostic artifact hash or detached receipt changed")
    return json.loads(payload), actual


def _verified_design():
    protocol, protocol_hash = _pinned_json("protocol", PROTOCOL_SHA256)
    receipt, receipt_hash = _pinned_json("implementation-receipt")
    if (protocol["model_ids"] != list(MODEL_IDS) or protocol["drifter_ids"] != list(DRIFTER_IDS)
            or protocol["position_std_m"] != POSITION_STD_M
            or protocol["acceleration_spectral_density_m2_s3"] != ACCELERATION_SPECTRAL_DENSITY_M2_S3
            or protocol["parameter_fitting_performed"] is not False
            or receipt["protocol_sha256"] != protocol_hash or receipt["real_kalman_outcomes_computed"] is not False):
        raise ValueError("Kalman fixed design or implementation freeze changed")
    for relative, expected in receipt["implementation_sha256"].items():
        if relative not in {"apps/ocean/reeftrace_ocean/kalman.py", "apps/ocean/reeftrace_ocean/kalman_diagnostic.py"}:
            raise ValueError("Unexpected Kalman implementation reference")
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError("Kalman implementation changed after first-score freeze")
    if len(receipt["implementation_sha256"]) != 2:
        raise ValueError("Both frozen Kalman implementations are required")
    return protocol, receipt, receipt_hash


def _compute_verified_report(protocol, receipt, receipt_hash):
    _, _, manifest, raw, original_implementation = load_multidrifter_inputs()
    records = {entry["drifter_id"]: parse_drifter_csv(raw[entry["raw_path"]].decode("utf-8"))
               for entry in manifest["trajectories"]}
    report = diagnostic_from_records(records, {entry["drifter_id"]: entry["block_id"] for entry in manifest["trajectories"]})
    report.update(data_origin="REAL_HISTORICAL_NOAA_DRIFTERS_ALREADY_VIEWED",
        protocol_sha256=PROTOCOL_SHA256, protocol=protocol,
        implementation_receipt=receipt, implementation_receipt_sha256=receipt_hash,
        original_implementation_receipt_sha256=original_implementation["sha256"],
        provenance={"integrity_verified": True, "provider": "NOAA AOML Global Drifter Program",
            "sources": [{key: entry[key] for key in ("drifter_id", "source_url", "sha256", "bytes")}
                        for entry in manifest["trajectories"]]})
    json.dumps(report, allow_nan=False)
    return report


def _same_reference(actual, expected):
    if type(actual) is not type(expected):
        raise ValueError("Kalman replay reference type changed")
    if isinstance(expected, float):
        if not math.isfinite(actual) or not math.isclose(actual, expected, rel_tol=FLOAT_REL_TOL, abs_tol=FLOAT_ABS_TOL):
            raise ValueError("Kalman replay reference numerical result changed")
    elif isinstance(expected, dict):
        if actual.keys() != expected.keys():
            raise ValueError("Kalman replay reference fields changed")
        for key in expected:
            _same_reference(actual[key], expected[key])
    elif isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError("Kalman replay reference denominator changed")
        for left, right in zip(actual, expected, strict=True):
            _same_reference(left, right)
    elif actual != expected:
        raise ValueError("Kalman replay reference identity, status or count changed")


def run_kalman_diagnostic():
    """Recompute the isolated frozen design; verify raw inputs and reference report."""
    protocol, receipt, receipt_hash = _verified_design()
    result = _compute_verified_report(protocol, receipt, receipt_hash)
    reference, report_hash = _pinned_json("report")
    _same_reference(result, reference)
    result["replay"] = {"reference_report_sha256": report_hash, "verified_numeric_replay": True,
        "float_relative_tolerance": FLOAT_REL_TOL, "float_absolute_tolerance": FLOAT_ABS_TOL}
    return result
