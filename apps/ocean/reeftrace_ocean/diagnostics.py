"""Training-only expanding-origin diagnostic for the existing NOAA motion models.

This is a retrospective check on overlapping training prefixes. It is not model
selection, hyperparameter search, generalization evidence or source attribution.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from datetime import UTC

import numpy as np

from .benchmark import (
    EARTH_MEAN_RADIUS_M,
    EXPECTED_PROVENANCE,
    MAX_LOCAL_DISTANCE_M,
    MIN_FIT_COUNT,
    MODEL_IDS,
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

DEFAULT_HORIZONS = 6
MAX_RECORDS = 100


def _require_int(name: str, value: object) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be an explicit Python int, not bool or float")
    return value


def _validate_training_window(records, horizons: int, training_count: int, min_prefix: int):
    horizons = _require_int("horizons", horizons)
    training_count = _require_int("training_count", training_count)
    min_prefix = _require_int("min_prefix", min_prefix)
    if not 1 <= horizons <= DEFAULT_HORIZONS:
        raise ValueError("horizons must be in 1..6")
    if min_prefix < MIN_FIT_COUNT:
        raise ValueError("min_prefix must be >= MIN_FIT_COUNT")
    if not min_prefix + horizons <= training_count <= TRAIN_COUNT:
        raise ValueError("training_count must satisfy min_prefix+horizons .. 18")
    n_records = len(records)
    if n_records > MAX_RECORDS:
        raise ValueError("Require <=100 records")
    if n_records < training_count:
        raise ValueError("Not enough records for the requested training_count")
    training = records[:training_count]
    if len({row.drifter_id for row in training}) != 1:
        raise ValueError("Require one drifter")
    if any(
        row.time_utc.tzinfo is None or row.time_utc.utcoffset() != UTC.utcoffset(row.time_utc)
        for row in training
    ):
        raise ValueError("This diagnostic requires timezone-aware UTC records")
    step_s = (training[1].time_utc - training[0].time_utc).total_seconds()
    if step_s != 3600 or any(
        (later.time_utc - earlier.time_utc).total_seconds() != step_s
        for earlier, later in itertools.pairwise(training)
    ):
        raise ValueError("This bounded diagnostic requires regular hourly UTC records")
    return training, horizons, training_count, min_prefix, step_s


def _errors_for(origins: list[dict], model_id: str, horizon: int) -> list[float]:
    errors = []
    for origin in origins:
        model = next(item for item in origin["models"] if item["id"] == model_id)
        point = next(item for item in model["predictions"] if item["horizon_hours"] == horizon)
        errors.append(point["error_m"])
    return errors


def _aggregates(origins: list[dict], horizons: int) -> list[dict]:
    by_model = []
    for model_id in MODEL_IDS:
        per_horizon = []
        for horizon in range(1, horizons + 1):
            errors = _errors_for(origins, model_id, horizon)
            stationary_errors = _errors_for(origins, "stationary", horizon)
            array = np.asarray(errors, dtype=float)
            per_horizon.append(
                {
                    "horizon_hours": horizon,
                    "count": len(errors),
                    "mean_error_m": float(np.mean(array)),
                    "rmse_error_m": float(np.sqrt(np.mean(np.square(array)))),
                    "max_error_m": float(np.max(array)),
                    "per_horizon_error_lower_than_stationary_count": int(
                        sum(
                            error < baseline
                            for error, baseline in zip(errors, stationary_errors, strict=True)
                        )
                    ),
                }
            )
        by_model.append({"id": model_id, "per_horizon": per_horizon})
    return by_model


def training_origin_diagnostic(
    records,
    horizons: int = DEFAULT_HORIZONS,
    training_count: int = TRAIN_COUNT,
    min_prefix: int = MIN_FIT_COUNT,
) -> dict:
    """Fit each training prefix alone, then score later training positions only.

    Records after ``training_count`` are never read. Cadence checks may inspect
    training timestamps. Prefix lat/lon are projected only as ``training[:prefix_count]``
    immediately before that origin's three forecasts. That origin's later positions
    are validated/projected and scored only after those forecasts exist. Remaining
    training positions receive finite/50 km checks after all origin forecasts.
    Overlapping windows are dependent; NOAA hourly positions may already be interpolated.
    """
    training, horizons, training_count, min_prefix, step_s = _validate_training_window(
        records, horizons, training_count, min_prefix
    )
    frame = SphericalLocalFrame(training[0].latitude_deg, training[0].longitude_deg)
    prefix_counts = list(range(min_prefix, training_count - horizons + 1))
    origins = []
    for prefix_count in prefix_counts:
        prefix = training[:prefix_count]
        prefix_xy = np.asarray(
            [frame.to_xy(row.latitude_deg, row.longitude_deg) for row in prefix]
        )
        forecasts = {
            model_id: _forecast(prefix_xy, horizons, step_s, model_id)[0] for model_id in MODEL_IDS
        }
        truth = training[prefix_count : prefix_count + horizons]
        for observed in truth:
            frame.to_xy(observed.latitude_deg, observed.longitude_deg)
        models = []
        for model_id in MODEL_IDS:
            predictions = []
            for index, (predicted, observed) in enumerate(
                zip(forecasts[model_id], truth, strict=True), 1
            ):
                latitude_deg, longitude_deg = frame.to_latlon(predicted)
                predictions.append(
                    {
                        "time_utc": _point(observed)["time_utc"],
                        "horizon_hours": index,
                        "latitude_deg": float(latitude_deg),
                        "longitude_deg": float(longitude_deg),
                        "error_m": float(
                            great_circle_distance_m(
                                (latitude_deg, longitude_deg),
                                (observed.latitude_deg, observed.longitude_deg),
                            )
                        ),
                    }
                )
            models.append({"id": model_id, "predictions": predictions})
        origins.append(
            {
                "prefix_count": prefix_count,
                "fit_end_utc": _point(training[prefix_count - 1])["time_utc"],
                "models": models,
            }
        )
    for row in training:
        frame.to_xy(row.latitude_deg, row.longitude_deg)
    report = {
        "schema_version": 1,
        "kind": "TRAINING_ONLY_RETROSPECTIVE_DIAGNOSTIC",
        "status": "COMPLETED",
        "split": {
            "method": "training_only_expanding_origin_no_heldout",
            "training_count": training_count,
            "min_prefix": min_prefix,
            "horizons": horizons,
            "prefix_counts": prefix_counts,
            "origin_count": len(prefix_counts),
            "step_seconds": step_s,
            "test_data_used": False,
            "model_selection_performed": False,
        },
        "coordinate_system": {
            "input": "geographic_latitude_longitude_degrees",
            "fit": "spherical_azimuthal_equidistant_east_north_metres",
            "error": "spherical_great_circle_metres",
            "earth_mean_radius_m": EARTH_MEAN_RADIUS_M,
            "origin_latitude_deg": frame.latitude_deg,
            "origin_longitude_deg": frame.longitude_deg,
            "maximum_local_distance_m": MAX_LOCAL_DISTANCE_M,
            "sphere_not_wgs84_ellipsoid": True,
        },
        "origins": origins,
        "aggregates": _aggregates(origins, horizons),
        "limitations": [
            "Default prefixes 8..12 yield five overlapping six-hour origins on one drifter-day; those windows share positions and are statistically dependent.",
            "Hourly NOAA locations are quality-controlled/interpolated; upstream processing may use later raw fixes. Code-level isolation of records after training_count cannot undo that product interpolation or prove raw real-time skill.",
            "Each prefix is fit from its own earlier positions only, then scored on later positions still inside the training window. Held-out hours after training_count are not used.",
            "No hyperparameter search, model selection, promotion or generalization claim is performed.",
            "Buoy drift is not floating-plastic behavior. This diagnostic does not infer a plastic source, polluter or ecological impact.",
        ],
    }
    json.dumps(report, allow_nan=False)
    return report


def run_training_diagnostic() -> dict:
    """Offline entry: verify the pinned NOAA sample, then diagnose training prefixes only."""
    source = ROOT / "data/public" / SAMPLE_NAME
    payload = source.read_bytes()
    if len(payload) > 100_000:
        raise ValueError("Public example exceeds its 100 KB budget")
    digest = hashlib.sha256(payload).hexdigest()
    manifest = json.loads(source.with_suffix(".provenance.json").read_text(encoding="utf-8"))
    if digest != SAMPLE_SHA256 or digest != manifest.get("sha256"):
        raise ValueError("Public NOAA sample hash does not match pinned provenance")
    if any(manifest.get(key) != value for key, value in EXPECTED_PROVENANCE.items()):
        raise ValueError("Public NOAA provenance differs from the reviewed official-source record")
    # Parse and identify the entire immutable artifact, without forecasting or
    # scoring the held-out observations. The diagnostic receives its prefix only.
    records = parse_drifter_csv(payload.decode("utf-8"))
    if (len(records) != 24 or manifest.get("row_count") != 24
            or manifest.get("bytes") != len(payload)
            or {row.drifter_id for row in records} != {"8707978"}
            or _point(records[0])["time_utc"] != "1987-10-03T00:00:00Z"
            or _point(records[-1])["time_utc"] != "1987-10-03T23:00:00Z"):
        raise ValueError("Public NOAA sample identity/count/time differs from pinned experiment")
    report = training_origin_diagnostic(records[:TRAIN_COUNT])
    report["data_origin"] = "REAL_HISTORICAL_NOAA_DRIFTER"
    report["provenance"] = {
        "provider": manifest["provider"], "source_url": manifest["source_url"],
        "metadata_url": manifest["metadata_url"], "product_doi": manifest["product_doi"],
        "license": manifest["license_from_endpoint_metadata"],
        "license_url": manifest["license_url"], "attribution": manifest["attribution"],
        "retrieved_at_utc": manifest["retrieved_at_utc"], "sha256": digest,
        "bytes": len(payload), "row_count": len(records), "drifter_id": records[0].drifter_id,
        "integrity_verified": True,
        "benchmark_scope": "training_only_diagnostic_without_heldout_forecast_or_scoring",
    }
    report["test_data_used"] = False
    report["model_selection_performed"] = False
    json.dumps(report, allow_nan=False)
    return report
