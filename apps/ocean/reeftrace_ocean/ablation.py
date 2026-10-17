"""Training-only test of learned velocity memory against three simple baselines.

Mean-drift and paired-summary formulas received static Grok code assistance;
numeric guards, the report contract and execution are reviewed locally. No model
is selected or promoted. Overlapping origins are dependent diagnostic examples.
"""

from __future__ import annotations

import hashlib
import json
import math
from numbers import Real

import numpy as np

from .benchmark import (
    EARTH_MEAN_RADIUS_M,
    EXPECTED_PROVENANCE,
    MAX_LOCAL_DISTANCE_M,
    MIN_FIT_COUNT,
    ROOT,
    SAMPLE_NAME,
    SAMPLE_SHA256,
    TRAIN_COUNT,
    SphericalLocalFrame,
    _forecast,
    _point,
    great_circle_distance_m,
)
from .data import parse_drifter_csv
from .diagnostics import DEFAULT_HORIZONS, _validate_training_window

ABLATION_MODEL_IDS = ("stationary", "last_drift", "mean_drift", "ridge_ar1")
BASELINE_IDS = ABLATION_MODEL_IDS[:-1]
MAX_PAIRED_ERRORS = 100
MAX_ERROR_M = 2 * MAX_LOCAL_DISTANCE_M
MANIFEST_SHA256 = "3379582bfe819fc995520cf9af9a86688f0fa0cba8f61dcf26935a41efbf9958"
FLAGS = {"test_data_used": False, "model_selection_performed": False,
         "calibrated_probability": False, "physical_validation": False,
         "automatic_model_promotion": False}


def _numeric_array(value, name, ndim, maximum_items):
    try:
        # Object dtype preserves booleans/strings in mixed Python lists so they
        # cannot silently become 1.0 or a parsed number during float coercion.
        raw = np.asarray(value, dtype=object)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} needs a rectangular numeric array") from error
    if raw.ndim != ndim or not 1 <= raw.size <= maximum_items:
        raise ValueError(f"{name} has an invalid shape or size")
    if any(isinstance(item, (bool, np.bool_)) or not isinstance(item, Real) for item in raw.flat):
        raise ValueError(f"{name} requires real numbers, not booleans, strings or complex values")
    try:
        result = raw.astype(float)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} requires finite real numbers") from error
    if not np.isfinite(result).all():
        raise ValueError(f"{name} requires finite real numbers")
    return result


def mean_drift_forecast(training_xy, steps: int, step_s: float) -> np.ndarray:
    """Free-run mean velocity from 2..18 prefix positions, returning (steps,2).

    This is the existing AR(1) predictor with its velocity-memory matrix zeroed.
    Position coordinates and predictions obey the same 50 km local-frame budget.
    """
    if type(steps) is not int or not 1 <= steps <= DEFAULT_HORIZONS:
        raise ValueError("steps must be an explicit Python int in 1..6")
    if (isinstance(step_s, (bool, np.bool_)) or not isinstance(step_s, Real)
            or not math.isfinite(step_s) or not 0 < step_s <= 86_400):
        raise ValueError("step_s must be a positive finite number no greater than 86400")
    xy = _numeric_array(training_xy, "training_xy", 2, TRAIN_COUNT * 2)
    if xy.shape[1] != 2 or not 2 <= len(xy) <= TRAIN_COUNT:
        raise ValueError("training_xy requires shape (n,2) with n in 2..18")
    if np.abs(xy).max() > MAX_LOCAL_DISTANCE_M or np.linalg.norm(xy, axis=1).max() > MAX_LOCAL_DISTANCE_M:
        raise ValueError("Mean-drift positions exceed the 50 km local-geometry budget")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            mean_velocity = (xy[-1] - xy[0]) / ((len(xy) - 1) * float(step_s))
            prediction = xy[-1] + np.arange(1, steps + 1)[:, None] * float(step_s) * mean_velocity
    except FloatingPointError as error:
        raise ValueError("Mean-drift arithmetic must remain finite") from error
    if not np.isfinite(prediction).all() or not np.isfinite(mean_velocity).all():
        raise ValueError("Mean-drift arithmetic must remain finite")
    if np.linalg.norm(prediction, axis=1).max() > MAX_LOCAL_DISTANCE_M:
        raise ValueError("Mean-drift forecast exceeds the 50 km local-geometry budget")
    return prediction


def paired_error_summary(candidate_errors, baseline_errors) -> dict:
    """Aligned descriptive error differences; negative delta favors candidate.

    Bounds on values/counts keep all aggregates finite. Equal means exact numeric
    equality, not a post-hoc tolerance. Zero baseline error has undefined skill.
    """
    candidate = _numeric_array(candidate_errors, "candidate_errors", 1, MAX_PAIRED_ERRORS)
    baseline = _numeric_array(baseline_errors, "baseline_errors", 1, MAX_PAIRED_ERRORS)
    if candidate.shape != baseline.shape:
        raise ValueError("Paired errors must have matching nonempty shapes")
    if min(candidate.min(), baseline.min()) < 0 or max(candidate.max(), baseline.max()) > MAX_ERROR_M:
        raise ValueError("Paired errors must be nonnegative and within the 100 km distance budget")
    delta = candidate - baseline
    baseline_sum = float(baseline.sum())
    if baseline_sum == 0:
        skill, reasons = None, ["ZERO_BASELINE_ERROR"]
    else:
        skill = 1 - float(candidate.sum()) / baseline_sum
        if not math.isfinite(skill):
            raise ValueError("Paired skill exceeds its finite arithmetic budget")
        reasons = []
    return {"count": len(candidate), "mean_delta_m": float(np.mean(delta)),
        "median_delta_m": float(np.median(delta)), "min_delta_m": float(delta.min()),
        "max_delta_m": float(delta.max()),
        "candidate_lower_error_count": int(np.sum(delta < 0)),
        "equal_error_count": int(np.sum(delta == 0)),
        "candidate_higher_error_count": int(np.sum(delta > 0)),
        "skill_vs_baseline": skill, "reason_codes": reasons}


def _model_errors(origins, model_id, horizon):
    return [next(model for model in origin["models"] if model["id"] == model_id)
            ["predictions"][horizon - 1]["error_m"] for origin in origins]


def training_motion_ablation(records, *, horizons=DEFAULT_HORIZONS,
                             training_count=TRAIN_COUNT, min_prefix=MIN_FIT_COUNT) -> dict:
    """Read only the declared training window; forecast all models before truth.

    Full-window timestamp checks precede fitting. Later latitude/longitude values
    are projected only after the four forecasts for that origin exist. None of
    the records after training_count is accessed, including its metadata.
    """
    training, horizons, training_count, min_prefix, step_s = _validate_training_window(
        records, horizons, training_count, min_prefix)
    frame = SphericalLocalFrame(training[0].latitude_deg, training[0].longitude_deg)
    prefixes = list(range(min_prefix, training_count - horizons + 1))
    origins = []
    for prefix_count in prefixes:
        prefix = np.asarray([frame.to_xy(row.latitude_deg, row.longitude_deg)
                             for row in training[:prefix_count]])
        forecasts = {}
        for model_id in ABLATION_MODEL_IDS:
            if model_id == "mean_drift":
                predicted = mean_drift_forecast(prefix, horizons, step_s)
                parameters = {"learned_parameters": 2,
                    "mean_velocity_m_s": ((prefix[-1] - prefix[0]) / ((prefix_count - 1) * step_s)).tolist(),
                    "training_displacement_count": prefix_count - 1,
                    "equivalent_to": "ridge_ar1_with_velocity_memory_matrix_zeroed"}
            else:
                predicted, parameters = _forecast(prefix, horizons, step_s, model_id)
            forecasts[model_id] = predicted, parameters
        truth = training[prefix_count:prefix_count + horizons]
        for record in truth:
            frame.to_xy(record.latitude_deg, record.longitude_deg)
        models = []
        for model_id, (predicted, parameters) in forecasts.items():
            predictions = []
            for horizon, (xy, record) in enumerate(zip(predicted, truth, strict=True), 1):
                lat, lon = frame.to_latlon(xy)
                predictions.append({"time_utc": _point(record)["time_utc"], "horizon_hours": horizon,
                    "latitude_deg": lat, "longitude_deg": lon,
                    "error_m": great_circle_distance_m((lat, lon), (record.latitude_deg, record.longitude_deg))})
            models.append({"id": model_id, "parameters": parameters, "predictions": predictions})
        origins.append({"prefix_count": prefix_count, "fit_end_utc": _point(training[prefix_count - 1])["time_utc"],
                        "models": models})
    # Validate any unused trailing training coordinates without exposing them to
    # earlier fits. This never iterates through held-out records.
    for record in training:
        frame.to_xy(record.latitude_deg, record.longitude_deg)
    aggregates, pairs = [], []
    for model_id in ABLATION_MODEL_IDS:
        rows = []
        for horizon in range(1, horizons + 1):
            errors = np.asarray(_model_errors(origins, model_id, horizon))
            rows.append({"horizon_hours": horizon, "count": len(errors),
                "mean_error_m": float(errors.mean()), "median_error_m": float(np.median(errors)),
                "min_error_m": float(errors.min()), "max_error_m": float(errors.max()),
                "rmse_error_m": float(np.sqrt(np.mean(errors ** 2)))})
        aggregates.append({"id": model_id, "per_horizon": rows})
    for baseline_id in BASELINE_IDS:
        pairs.append({"candidate_id": "ridge_ar1", "baseline_id": baseline_id,
            "delta_definition": "candidate_minus_baseline_error_m",
            "per_horizon": [{"horizon_hours": horizon, **paired_error_summary(
                _model_errors(origins, "ridge_ar1", horizon), _model_errors(origins, baseline_id, horizon))}
                for horizon in range(1, horizons + 1)]})
    report = {"schema_version": 1, "kind": "TRAINING_ONLY_MOTION_ABLATION", "status": "COMPLETED",
        "data_origin": "UNVERIFIED_TRAINING_RECORDS", **FLAGS,
        "split": {"method": "training_only_expanding_origin_no_heldout", "training_count": training_count,
            "min_prefix": min_prefix, "horizons": horizons, "prefix_counts": prefixes,
            "origin_count": len(prefixes), "step_seconds": step_s,
            "test_data_used": False, "model_selection_performed": False},
        "coordinate_system": {"input": "geographic_latitude_longitude_degrees",
            "fit": "spherical_azimuthal_equidistant_east_north_metres",
            "error": "spherical_great_circle_metres", "earth_mean_radius_m": EARTH_MEAN_RADIUS_M,
            "origin_latitude_deg": frame.latitude_deg, "origin_longitude_deg": frame.longitude_deg,
            "maximum_local_distance_m": MAX_LOCAL_DISTANCE_M, "sphere_not_wgs84_ellipsoid": True},
        "origins": origins, "aggregates": aggregates, "paired_comparisons": pairs,
        "limitations": [
            "Five default origins overlap on one drifter-day; errors are dependent, not independent validation trials.",
            "Hourly NOAA locations are interpolated; prefix-only code cannot undo upstream use of later raw fixes or establish raw operational forecasting skill.",
            "Only the first eighteen positions are available to this diagnostic; the frozen six-hour held-out benchmark is not evaluated or changed.",
            "Mean drift removes the learned velocity-memory matrix; it is a fitted two-component baseline, not a new physical ocean model.",
            "Negative paired error difference favors ridge at the named origin/horizon; no significance, winner selection or automatic model promotion is implied.",
            "No probability calibration, plastic-source attribution, tank validation, polluter identity or ecological impact is established."]}
    json.dumps(report, allow_nan=False)
    return report


def run_motion_ablation() -> dict:
    """Verify both pinned public files once, then use only eighteen positions."""
    source = ROOT / "data/public" / SAMPLE_NAME
    with source.open("rb") as stream:
        payload = stream.read(100_001)
    if len(payload) > 100_000 or hashlib.sha256(payload).hexdigest() != SAMPLE_SHA256:
        raise ValueError("Public NOAA sample exceeds its budget or does not match its pinned hash")
    with source.with_suffix(".provenance.json").open("rb") as stream:
        manifest_payload = stream.read(20_001)
    if len(manifest_payload) > 20_000 or hashlib.sha256(manifest_payload).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Public NOAA provenance does not match its pinned manifest hash")
    manifest = json.loads(manifest_payload.decode("utf-8"))
    if (not isinstance(manifest, dict)
            or any(manifest.get(key) != value for key, value in EXPECTED_PROVENANCE.items())
            or manifest.get("sha256") != SAMPLE_SHA256):
        raise ValueError("Public NOAA provenance differs from the reviewed official-source record")
    records = parse_drifter_csv(payload.decode("utf-8"))
    if (len(records) != 24 or manifest.get("row_count") != 24 or manifest.get("bytes") != len(payload)
            or {record.drifter_id for record in records} != {"8707978"}
            or _point(records[0])["time_utc"] != manifest.get("time_start_utc")
            or _point(records[-1])["time_utc"] != manifest.get("time_end_utc")):
        raise ValueError("Public NOAA sample identity/count/time differs from the pinned experiment")
    report = training_motion_ablation(records[:TRAIN_COUNT])
    report["data_origin"] = "REAL_HISTORICAL_NOAA_DRIFTER"
    report["provenance"] = {"provider": manifest["provider"], "source_url": manifest["source_url"],
        "metadata_url": manifest["metadata_url"], "product_doi": manifest["product_doi"],
        "license": manifest["license_from_endpoint_metadata"], "license_url": manifest["license_url"],
        "attribution": manifest["attribution"], "retrieved_at_utc": manifest["retrieved_at_utc"],
        "sha256": SAMPLE_SHA256, "manifest_sha256": MANIFEST_SHA256, "bytes": len(payload),
        "row_count": len(records), "drifter_id": "8707978", "integrity_verified": True,
        "benchmark_scope": "training_only_motion_ablation_without_heldout_forecast_or_scoring"}
    json.dumps(report, allow_nan=False)
    return report
