"""Small reproducible geographic forecast experiment on an authentic NOAA drifter day.

This is a retrospective buoy-motion benchmark, never plastic-source attribution.
Only chronological training positions enter a model. NOAA's published velocities
and uncertainty columns are retained for inspection but never used as labels or
future forcing. All calculations run offline against a content-pinned CSV.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from .data import DrifterRecord, parse_drifter_csv

ROOT = Path(__file__).resolve().parents[3]
SAMPLE_NAME = "noaa-gdp-8707978-19871003.csv"
SAMPLE_SHA256 = "b503de924bbfe82fb18a705917e527faaf26e51688845adb4b57f0cb121c2fca"
EXPECTED_PROVENANCE = {
    "source_url": (
        "https://erddap.aoml.noaa.gov/gdp/erddap/tabledap/drifter_hourly_qc.csv?"
        "ID,time,latitude,longitude,ve,vn,err_ve,err_vn&ID=%228707978%22&"
        "time%3E=1987-10-03T00%3A00%3A00Z&time%3C=1987-10-03T23%3A00%3A00Z"
    ),
    "metadata_url": "https://erddap.aoml.noaa.gov/gdp/erddap/info/drifter_hourly_qc/index.html",
    "provider": "NOAA AOML Global Drifter Program",
    "dataset_id": "drifter_hourly_qc",
    "product_doi": "10.25921/x46c-3620",
    "license_from_endpoint_metadata": "CC-BY-4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "drifter_id": "8707978",
}
EARTH_MEAN_RADIUS_M = 6_371_008.8
MAX_LOCAL_DISTANCE_M = 50_000.0
TRAIN_COUNT = 18
MIN_FIT_COUNT = 8
RIDGE_ALPHA = 1.0  # Fixed dimensionless penalty; never selected on the holdout.
MAX_AR_SPECTRAL_RADIUS = 0.98  # Fixed stability constraint, not a post-test correction.
MODEL_IDS = ("stationary", "last_drift", "ridge_ar1")
ModelID = Literal["stationary", "last_drift", "ridge_ar1"]


@dataclass(frozen=True)
class SphericalLocalFrame:
    """Azimuthal equidistant log/exp map on a declared mean-radius sphere.

    East/north metres relative to the first training position. This is an exact
    spherical map, not WGS84 geodesy; the 50 km budget limits distortion. Distance
    errors are reported using great-circle separation on the same sphere. The
    ellipsoid-vs-sphere discrepancy can approach ~0.6%, which this example does
    not interpret as measured forecast uncertainty.
    """

    latitude_deg: float
    longitude_deg: float

    def to_xy(self, latitude_deg: float, longitude_deg: float) -> np.ndarray:
        if not all(math.isfinite(v) for v in (latitude_deg, longitude_deg)):
            raise ValueError("Finite geographic coordinates required")
        if not -90 <= latitude_deg <= 90 or not -180 <= longitude_deg <= 180:
            raise ValueError("Geographic coordinates outside latitude/longitude limits")
        lat0, lon0, lat, lon = map(
            math.radians,
            (self.latitude_deg, self.longitude_deg, latitude_deg, longitude_deg),
        )
        dlon = math.atan2(math.sin(lon - lon0), math.cos(lon - lon0))
        east = math.cos(lat) * math.sin(dlon)
        north = math.cos(lat0) * math.sin(lat) - math.sin(lat0) * math.cos(lat) * math.cos(dlon)
        dot = math.sin(lat0) * math.sin(lat) + math.cos(lat0) * math.cos(lat) * math.cos(dlon)
        angle = math.atan2(math.hypot(east, north), dot)
        distance = angle * EARTH_MEAN_RADIUS_M
        if distance > MAX_LOCAL_DISTANCE_M:
            raise ValueError("Drifter example exceeds its 50 km local-geometry budget")
        if distance < 1e-9:
            return np.zeros(2)
        return np.array([east, north]) * distance / math.hypot(east, north)

    def to_latlon(self, xy_m: np.ndarray) -> tuple[float, float]:
        east, north = np.asarray(xy_m, dtype=float)
        distance = math.hypot(east, north)
        if not math.isfinite(distance) or distance > MAX_LOCAL_DISTANCE_M:
            raise ValueError("Forecast exceeds its finite 50 km local-geometry budget")
        if distance < 1e-9:
            return self.latitude_deg, self.longitude_deg
        lat0, lon0 = map(math.radians, (self.latitude_deg, self.longitude_deg))
        angle = distance / EARTH_MEAN_RADIUS_M
        lat = math.asin(
            math.cos(angle) * math.sin(lat0) + north / distance * math.sin(angle) * math.cos(lat0)
        )
        lon = lon0 + math.atan2(
            east / distance * math.sin(angle),
            math.cos(lat0) * math.cos(angle) - north / distance * math.sin(lat0) * math.sin(angle),
        )
        return math.degrees(lat), (math.degrees(lon) + 180.0) % 360.0 - 180.0


def great_circle_distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Stable haversine separation for (latitude, longitude) tuples, in metres."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    sin2 = math.sin((lat2 - lat1) / 2) ** 2 + (
        math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_MEAN_RADIUS_M * math.asin(math.sqrt(min(1.0, max(0.0, sin2))))


def _forecast(training_xy: np.ndarray, steps: int, step_s: float, model: ModelID) -> tuple:
    """Free-run predictions anchored at the final TRAINING location only."""
    if len(training_xy) < MIN_FIT_COUNT or not 1 <= steps <= 12:
        raise ValueError("Forecast requires >=8 training points and 1..12 horizons")
    velocities = np.diff(training_xy, axis=0) / step_s
    anchor = training_xy[-1].copy()
    if model == "stationary":
        return np.repeat(anchor[None, :], steps, axis=0), {"learned_parameters": 0}
    if model == "last_drift":
        velocity = velocities[-1]
        return anchor + np.arange(1, steps + 1)[:, None] * step_s * velocity, {
            "last_observed_velocity_m_s": velocity.tolist(),
            "learned_parameters": 0,
        }
    if model != "ridge_ar1":
        raise ValueError("Unknown forecast model")
    mean_velocity = velocities.mean(axis=0)
    # A common scalar scale makes the regularizer dimensionless and isotropic.
    scale = float(np.sqrt(np.mean((velocities - mean_velocity) ** 2)))
    scale = max(scale, 1e-9)
    features = (velocities[:-1] - mean_velocity) / scale
    target = (velocities[1:] - mean_velocity) / scale
    matrix = np.linalg.solve(features.T @ features + RIDGE_ALPHA * np.eye(2), features.T @ target)
    radius_before = float(np.max(np.abs(np.linalg.eigvals(matrix))))
    if radius_before > MAX_AR_SPECTRAL_RADIUS:
        matrix *= MAX_AR_SPECTRAL_RADIUS / radius_before
    velocity = velocities[-1]
    predictions = []
    for _ in range(steps):
        velocity = mean_velocity + (velocity - mean_velocity) @ matrix
        anchor = anchor + step_s * velocity
        predictions.append(anchor.copy())
    return np.asarray(predictions), {
        "learned_parameters": 6,
        "training_velocity_pairs": len(features),
        "mean_velocity_m_s": mean_velocity.tolist(),
        "velocity_transition_matrix_row_vector_convention": matrix.tolist(),
        "ridge_alpha": RIDGE_ALPHA,
        "spectral_radius_before_constraint": radius_before,
        "maximum_spectral_radius": MAX_AR_SPECTRAL_RADIUS,
        "constraint_applied": radius_before > MAX_AR_SPECTRAL_RADIUS,
        "hyperparameters_selected_on_holdout": False,
    }


def _training_error_radii(
    training_xy: np.ndarray, horizons: int, step_s: float, model: ModelID
) -> list[dict]:
    """Training-only expanding-origin error radii, not calibrated probabilities.

    Each fit sees its prefix only; the later points used to score that prefix
    still precede the final train/test cutoff. Overlapping forecast errors are
    dependent, and this tiny sample does not establish nominal 90% coverage.
    """
    result = []
    for horizon in range(1, horizons + 1):
        errors = []
        for prefix_count in range(MIN_FIT_COUNT, len(training_xy) - horizon + 1):
            predicted, _ = _forecast(training_xy[:prefix_count], horizon, step_s, model)
            errors.append(
                float(np.linalg.norm(predicted[-1] - training_xy[prefix_count + horizon - 1]))
            )
        result.append(
            {
                "horizon_hours": horizon * step_s / 3600,
                "radius_m": float(np.quantile(errors, 0.9, method="higher")),
                "training_hindcast_count": len(errors),
                "nominal_quantile": 0.9,
                "calibrated_probability": False,
            }
        )
    return result


def _point(record: DrifterRecord) -> dict:
    return {
        "time_utc": record.time_utc.isoformat().replace("+00:00", "Z"),
        "latitude_deg": record.latitude_deg,
        "longitude_deg": record.longitude_deg,
    }


def benchmark_drifter_records(
    records: list[DrifterRecord], *, train_count: int = TRAIN_COUNT
) -> dict:
    """Chronological, deterministic retrospective experiment; no external calls.

    NOAA's hourly positions are already interpolated/smoothed. Splitting this
    published product avoids additional code-level future leakage, but cannot
    undo possible future support in NOAA's upstream interpolation. It therefore
    cannot establish raw real-time operational skill.
    """
    if not MIN_FIT_COUNT + 1 <= train_count < len(records) <= 100:
        raise ValueError("Require 9..99 training observations, <=100 total and heldout data")
    if len(records) - train_count > 12 or len({r.drifter_id for r in records}) != 1:
        raise ValueError("Require one drifter and <=12 heldout hours")
    step_s = (records[1].time_utc - records[0].time_utc).total_seconds()
    if step_s != 3600 or any(
        (b.time_utc - a.time_utc).total_seconds() != step_s for a, b in itertools.pairwise(records)
    ):
        raise ValueError("This bounded benchmark requires regular hourly UTC records")
    training = records[:train_count]
    heldout = records[train_count:]
    frame = SphericalLocalFrame(training[0].latitude_deg, training[0].longitude_deg)
    xy = np.asarray([frame.to_xy(r.latitude_deg, r.longitude_deg) for r in training])
    # Heldout positions are intentionally absent from fitting and error-radius calibration.
    models = []
    for model_id in MODEL_IDS:
        forecast, parameters = _forecast(xy, len(heldout), step_s, model_id)
        radius_rows = _training_error_radii(xy, len(heldout), step_s, model_id)
        predictions = []
        errors = []
        for index, (prediction, truth, radius) in enumerate(
            zip(forecast, heldout, radius_rows, strict=True), 1
        ):
            lat, lon = frame.to_latlon(prediction)
            error = great_circle_distance_m((lat, lon), (truth.latitude_deg, truth.longitude_deg))
            errors.append(error)
            predictions.append(
                {
                    "time_utc": _point(truth)["time_utc"],
                    "horizon_hours": index,
                    "latitude_deg": lat,
                    "longitude_deg": lon,
                    "error_m": error,
                    "training_error_radius_m": radius["radius_m"],
                    "training_hindcast_count": radius["training_hindcast_count"],
                    "within_training_error_radius": error <= radius["radius_m"],
                }
            )
        models.append(
            {
                "id": model_id,
                "label": {
                    "stationary": "Stationary position persistence",
                    "last_drift": "Last observed displacement",
                    "ridge_ar1": "Learned ridge velocity autoregression",
                }[model_id],
                "kind": "LEARNED_LINEAR_MODEL" if model_id == "ridge_ar1" else "NAIVE_BASELINE",
                "fit_uses": "training_positions_only",
                "free_run_without_heldout_updates": True,
                "parameters": parameters,
                "predictions": predictions,
                "metrics": {
                    "heldout_count": len(errors),
                    "mean_error_m": float(np.mean(errors)),
                    "rmse_error_m": float(np.sqrt(np.mean(np.square(errors)))),
                    "endpoint_error_m": errors[-1],
                    "max_error_m": max(errors),
                    "within_training_error_radius_count": sum(
                        point["within_training_error_radius"] for point in predictions
                    ),
                    "uncertainty_is_calibrated": False,
                },
                "training_error_radii": radius_rows,
            }
        )
    stationary_error = models[0]["metrics"]["mean_error_m"]
    for model in models:
        model["metrics"]["mae_skill_vs_stationary"] = (
            1 - model["metrics"]["mean_error_m"] / stationary_error
            if stationary_error > 0
            else None
        )
    return {
        "schema_version": 1,
        "experiment_id": "noaa-gdp-8707978-19871003-chronological-v1",
        "status": "COMPLETED",
        "data_origin": "REAL_HISTORICAL_NOAA_DRIFTER",
        "title": "Real NOAA drifter: six-hour heldout motion forecast",
        "split": {
            "method": "chronological_free_run_no_random_split",
            "training_count": len(training),
            "heldout_count": len(heldout),
            "training_end_utc": _point(training[-1])["time_utc"],
            "heldout_start_utc": _point(heldout[0])["time_utc"],
            "step_seconds": step_s,
            "test_values_used_for_model_selection": False,
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
            "approximate_maximum_ellipsoid_discrepancy_fraction": 0.006,
        },
        "training_track": [_point(r) for r in training],
        "heldout_track": [_point(r) for r in heldout],
        "models": models,
        "source_attribution": {
            "status": "NOT_SUPPORTED_BY_THIS_DATASET",
            "reason": "These are buoy locations, not plastic releases, coral health or polluter labels.",
        },
        "uncertainty_method": {
            "kind": "training_only_expanding_origin_90th_percentile_error_radius",
            "probability_claim": None,
            "note": "Few overlapping hindcasts; empirical radii are not calibrated 90% confidence regions.",
            "published_noaa_velocity_intervals_used_as_forecast_uncertainty": False,
        },
        "limitations": [
            "One historically selected drifter-day and six dependent heldout hours cannot establish general forecast skill.",
            "Hourly NOAA locations are quality-controlled/interpolated; upstream processing may use later raw fixes. This is retrospective product evaluation, not raw operational validation.",
            "Only positions before the split enter each fit; neither heldout positions nor published velocity columns enter prediction.",
            "The regression penalty and stability bound are fixed; no model is promoted on this tiny test.",
            "Training error radii use very few overlapping hindcasts and are not calibrated probabilities.",
            "A sphere approximates the Earth; geographic degrees never enter the tank-centimetre estimator.",
            "Buoy drift is not floating-plastic behavior. No plastic source, human actor or ecological impact is inferred.",
            "No Copernicus field is paired to this historical sample; this is not a physics-model-versus-buoy validation.",
        ],
    }


def run_real_data_example() -> dict:
    """API/CLI entrypoint. Verify pinned local bytes and provenance before fitting."""
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
    records = parse_drifter_csv(payload.decode("utf-8"))
    if (
        len(records) != 24
        or manifest.get("row_count") != 24
        or manifest.get("bytes") != len(payload)
        or {r.drifter_id for r in records} != {"8707978"}
        or _point(records[0])["time_utc"] != "1987-10-03T00:00:00Z"
        or _point(records[-1])["time_utc"] != "1987-10-03T23:00:00Z"
    ):
        raise ValueError("Public NOAA sample identity/count/time differs from pinned experiment")
    report = benchmark_drifter_records(records)
    report["provenance"] = {
        "provider": manifest["provider"],
        "source_url": manifest["source_url"],
        "metadata_url": manifest["metadata_url"],
        "product_doi": manifest["product_doi"],
        "license": manifest["license_from_endpoint_metadata"],
        "license_url": manifest["license_url"],
        "attribution": manifest["attribution"],
        "retrieved_at_utc": manifest["retrieved_at_utc"],
        "csv_relative_path": "data/public/" + SAMPLE_NAME,
        "sha256": digest,
        "integrity_verified": True,
        "bytes": len(payload),
        "row_count": len(records),
        "drifter_id": records[0].drifter_id,
        "upstream_manifest_purpose": manifest["purpose"],
        "benchmark_scope": "retrospective_tiny_heldout_forecast_extension_of_ingestion_fixture",
    }
    # Reject accidental numpy scalars/NaN before it reaches the API or exported report.
    json.dumps(report, allow_nan=False)
    return report
