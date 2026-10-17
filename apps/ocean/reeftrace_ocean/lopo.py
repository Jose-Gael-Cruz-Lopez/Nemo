"""Post-hoc pooled motion diagnostic on four ALREADY VIEWED NOAA drifters.

This tests transfer of a shared residual-velocity matrix, not independent skill.
All folds predict before any later positions are scored. Original studies stay
unchanged. No network, provider, model promotion or application write occurs.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np

from .ablation import ABLATION_MODEL_IDS, mean_drift_forecast
from .benchmark import (
    MAX_LOCAL_DISTANCE_M,
    ROOT,
    SphericalLocalFrame,
    _forecast,
    great_circle_distance_m,
)
from .data import parse_drifter_csv
from .multidrifter import load_multidrifter_inputs

DIRECTORY = ROOT / "data/public/noaa-lopo-diagnostic-v1"
PROTOCOL_SHA256 = "198ebac9e216298cbd7d60ada7bcc18b1ac30bac837f4f7e94a1e402bef3a2e6"
MODEL_IDS = (*ABLATION_MODEL_IDS, "pooled_residual_ar1")


def assert_disjoint_physical_groups(training_ids, evaluation_ids, physical_mapping):
    """Fail closed on missing alias mappings or the same physical buoy in both."""
    ids = [*training_ids, *evaluation_ids]
    if (not training_ids or not evaluation_ids or len(set(ids)) != len(ids)
            or any(value not in physical_mapping or not isinstance(physical_mapping[value], str)
                   or not physical_mapping[value] for value in ids)):
        raise ValueError("Require distinct raw IDs and complete physical-buoy identity mapping")
    training = {physical_mapping[value] for value in training_ids}
    evaluation = {physical_mapping[value] for value in evaluation_ids}
    if (training & evaluation or len(training) != len(training_ids)
            or len(evaluation) != len(evaluation_ids)):
        raise ValueError("Physical drifter aliases overlap training and held-out groups")


def fit_pooled_transition(prefixes):
    """Learn only a 2x2 transition from three permitted 18-position prefixes."""
    if len(prefixes) != 3:
        raise ValueError("The frozen diagnostic requires exactly three training prefixes")
    centered = []
    for prefix in prefixes:
        xy = np.asarray(prefix, dtype=float)
        if (xy.shape != (18, 2) or not np.isfinite(xy).all()
                or np.linalg.norm(xy, axis=1).max() > MAX_LOCAL_DISTANCE_M):
            raise ValueError("Training prefix must be finite 18x2 within the local domain")
        velocity = np.diff(xy, axis=0) / 3600
        centered.append(velocity - velocity.mean(axis=0))
    scale = max(float(np.sqrt(np.mean(np.concatenate(centered) ** 2))), 1e-9)
    features = np.concatenate([value[:-1] for value in centered]) / scale
    target = np.concatenate([value[1:] for value in centered]) / scale
    matrix = np.linalg.solve(features.T @ features + np.eye(2), features.T @ target)
    radius = float(np.max(np.abs(np.linalg.eigvals(matrix))))
    if radius > 0.98:
        matrix *= 0.98 / radius
    return matrix, {"training_drifters": 3, "training_velocity_pairs": 48,
        "learned_transition_parameters": 4, "ridge_alpha": 1.0,
        "maximum_spectral_radius": 0.98, "spectral_radius_before_constraint": radius,
        "training_residual_scale_m_s": scale,
        "velocity_transition_matrix_row_vector_convention": matrix.tolist(),
        "held_group_used_to_fit_shared_matrix": False}


def pooled_forecast(prefix, matrix):
    xy = np.asarray(prefix, dtype=float)
    velocity = np.diff(xy, axis=0) / 3600
    mean, current, anchor = velocity.mean(axis=0), velocity[-1].copy(), xy[-1].copy()
    values = []
    for _ in range(6):
        current = mean + (current - mean) @ matrix
        anchor = anchor + 3600 * current
        values.append(anchor.copy())
    prediction = np.asarray(values)
    if (not np.isfinite(prediction).all()
            or np.linalg.norm(prediction, axis=1).max() > MAX_LOCAL_DISTANCE_M):
        raise ValueError("Pooled forecast outside finite local geometry domain")
    return prediction


def diagnostic_predictions(records_by_id, physical_mapping):
    """Return all predictions/parameters before accessing future positions."""
    ids = sorted(records_by_id, key=int)
    if len(ids) != 4:
        raise ValueError("This diagnostic requires exactly four declared drifter groups")
    frames, prefixes, forecasts, folds = {}, {}, {}, []
    for value in ids:
        records = records_by_id[value]
        if (len(records) != 24 or any(record.drifter_id != value for record in records)
                or any((records[i].time_utc - records[0].time_utc).total_seconds() != i * 3600
                       for i in range(24))):
            raise ValueError("Each group requires its declared 24 hourly identity/time rows")
        prefix = records[:18]
        frame = SphericalLocalFrame(prefix[0].latitude_deg, prefix[0].longitude_deg)
        frames[value] = frame
        prefixes[value] = np.asarray([frame.to_xy(row.latitude_deg, row.longitude_deg) for row in prefix])
    for held_id in ids:
        training_ids = [value for value in ids if value != held_id]
        assert_disjoint_physical_groups(training_ids, [held_id], physical_mapping)
        matrix, params = fit_pooled_transition([prefixes[value] for value in training_ids])
        folds.append({"held_out_drifter_id": held_id, "training_drifter_ids": training_ids,
                      "training_canonical_ids": [physical_mapping[value] for value in training_ids],
                      "held_out_canonical_id": physical_mapping[held_id], "parameters": params})
        for model_id in MODEL_IDS:
            try:
                if model_id == "pooled_residual_ar1":
                    values = pooled_forecast(prefixes[held_id], matrix)
                elif model_id == "mean_drift":
                    values = mean_drift_forecast(prefixes[held_id], 6, 3600)
                else:
                    values, _ = _forecast(prefixes[held_id], 6, 3600, model_id)
                forecasts[held_id, model_id] = [frames[held_id].to_latlon(value) for value in values]
            except (ValueError, OverflowError, FloatingPointError, np.linalg.LinAlgError):
                forecasts[held_id, model_id] = [None] * 6
    return forecasts, folds


def run_lopo_diagnostic():
    """Replay a frozen post-hoc design, clearly separated from the v1 study."""
    payload = (DIRECTORY / "protocol.json").read_bytes()
    if (hashlib.sha256(payload).hexdigest() != PROTOCOL_SHA256
            or (DIRECTORY / "protocol.sha256").read_text().strip() != PROTOCOL_SHA256):
        raise ValueError("LOPO diagnostic protocol is not the frozen design")
    protocol = json.loads(payload)
    receipt_bytes = (DIRECTORY / "implementation-receipt.json").read_bytes()
    if hashlib.sha256(receipt_bytes).hexdigest() != (DIRECTORY / "implementation-receipt.sha256").read_text().strip():
        raise ValueError("LOPO implementation receipt is corrupt")
    receipt = json.loads(receipt_bytes)
    if (receipt["protocol_sha256"] != PROTOCOL_SHA256
            or receipt["new_pooled_outcomes_computed"] is not False
            or receipt["evaluator_sha256"] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()):
        raise ValueError("LOPO evaluator changed after its first-score implementation freeze")
    _, _, manifest, raw, _ = load_multidrifter_inputs()
    records = {entry["drifter_id"]: parse_drifter_csv(raw[entry["raw_path"]].decode())
               for entry in manifest["trajectories"]}
    if sorted(records, key=int) != protocol["drifter_ids"]:
        raise ValueError("Post-hoc diagnostic group assignment changed")
    forecasts, folds = diagnostic_predictions(records, {value: value for value in records})
    # All 4 folds and all 5 models now exist; future positions are first used here.
    outcomes = []
    for drifter_id, model_id, horizon in itertools.product(records, MODEL_IDS, range(1, 7)):
        prediction = forecasts[drifter_id, model_id][horizon - 1]
        row = {"drifter_id": drifter_id, "model_id": model_id, "horizon_hours": horizon,
               "status": "FAILED", "error_m": None, "reason_codes": ["FORECAST_OUT_OF_DOMAIN"]}
        if prediction is not None:
            truth = records[drifter_id][17 + horizon]
            error = great_circle_distance_m(prediction, (truth.latitude_deg, truth.longitude_deg))
            if math.isfinite(error):
                row.update(status="SCORED", error_m=error, reason_codes=[])
        outcomes.append(row)
    complete = all(row["status"] == "SCORED" for row in outcomes)
    summaries = [{"drifter_id": value, "model_id": model_id,
        "mean_error_m": float(np.mean([row["error_m"] for row in outcomes
            if row["drifter_id"] == value and row["model_id"] == model_id])) if complete else None}
        for value, model_id in itertools.product(records, MODEL_IDS)]
    models = [{"id": model_id, "mean_trajectory_error_m": float(np.mean([
        row["mean_error_m"] for row in summaries if row["model_id"] == model_id])) if complete else None}
        for model_id in MODEL_IDS]
    return {"schema_version": 1, "kind": "LEAVE_ONE_DRIFTER_OUT_DIAGNOSTIC",
        "status": "COMPLETED" if complete else "INCOMPLETE_OUTCOMES",
        "design_status": "POST_HOC_ALREADY_VIEWED_DRIFTERS_NOT_INDEPENDENT_TEST",
        "protocol_sha256": PROTOCOL_SHA256, "implementation_receipt": receipt,
        "data_origin": "REAL_HISTORICAL_NOAA_DRIFTERS_ALREADY_VIEWED",
        "test_data_used": True, "model_selection_performed": False,
        "automatic_model_promotion": False, "physical_validation": False,
        "calibrated_probability": False,
        "independent_evaluation": False, "physical_alias_resolution_verified": False,
        "identity_scope": protocol["identity_scope"], "original_study_unchanged": True,
        "coverage": {"folds": 4, "models": 5, "horizons": 6, "attempted_outcomes": 120,
                     "scored_outcomes": sum(row["status"] == "SCORED" for row in outcomes),
                     "failed_outcomes": sum(row["status"] != "SCORED" for row in outcomes)},
        "folds": folds, "models": models, "trajectory_summaries": summaries,
        "outcomes": outcomes, "limitations": protocol["limitations"]}
