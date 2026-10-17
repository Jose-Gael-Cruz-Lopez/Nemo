"""Frozen, acquired-cohort retrospective forecasts on previously unscored IDs.

Grok provided static design assistance, not execution. The complete declared
group/model/horizon matrix is retained, including failures. No tuning, source
inference, provider, network, application writes or model promotion occurs here.
"""

from __future__ import annotations

import csv
import hashlib
import io
import itertools
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from .ablation import ABLATION_MODEL_IDS, BASELINE_IDS, mean_drift_forecast
from .benchmark import (
    EARTH_MEAN_RADIUS_M,
    MAX_AR_SPECTRAL_RADIUS,
    MAX_LOCAL_DISTANCE_M,
    RIDGE_ALPHA,
    ROOT,
    SphericalLocalFrame,
    _forecast,
    great_circle_distance_m,
)
from .data import parse_drifter_csv

STUDY_ID = "noaa-multidrifter-retrospective-v1"
DIRECTORY = ROOT / "data/public/noaa-multidrifter-v1"
PROTOCOL_SHA256 = "e8ad0cec2b48fa0e516a03b0bc14c42ba2f055439e534878f3db55def4d25845"
SELECTION_SHA256 = "18533ebefa4a766b368f28316eb5c883482acd0c5862eb56cd25b6b2531c7079"
MANIFEST_SHA256 = "6b6f5bc13aaf3f370b5e2ce90fcfbde0a4f7a18f3aa1ff76bd533b09856d9f2f"
DEVELOPMENT_ONLY = {"8707978"}
TRAINING_COUNT = 18
HORIZONS = (1, 2, 3, 4, 5, 6)
STEP_S = 3600
TARGET_GROUPS = 6
METRIC_SCOPE = "ACQUIRED_DECLARED_COHORT_NOT_FULL_PLANNED_TARGET"


def _digest(payload):
    return hashlib.sha256(payload).hexdigest()


def _read(path, maximum):
    with Path(path).open("rb") as stream:
        payload = stream.read(maximum + 1)
    if len(payload) > maximum:
        raise ValueError("Pinned study file exceeds its byte budget")
    return payload


def _pinned_json(directory, name, expected):
    payload = _read(directory / (name + ".json"), 100_000)
    receipt = _read(directory / (name + ".sha256"), 80).decode().strip()
    if _digest(payload) != expected or receipt != expected:
        raise ValueError(f"Pinned {name} manifest hash does not match its detached receipt")
    document = json.loads(payload)
    if not isinstance(document, dict):
        raise TypeError("Pinned study manifests must be JSON objects")
    return document


def _safe_raw(directory, entry):
    relative = entry["raw_path"]
    if not isinstance(relative, str) or not relative.startswith("raw/"):
        raise ValueError("Raw study payload must stay inside the public study directory")
    path = (directory / relative).resolve()
    if not path.is_relative_to((directory / "raw").resolve()):
        raise ValueError("Raw study payload path escapes its public directory")
    payload = _read(path, 1_000_000)
    if _digest(payload) != entry["sha256"] or len(payload) != entry["bytes"]:
        raise ValueError("Pinned NOAA raw payload hash or byte count changed")
    return payload


def _identity(protocol, selection, manifest):
    if any(document.get("study_id") != STUDY_ID or document.get("schema_version") != 1
           for document in (protocol, selection, manifest)):
        raise ValueError("Study manifest identity or schema is not supported")
    if (selection["protocol_sha256"] != PROTOCOL_SHA256
            or manifest["protocol_sha256"] != PROTOCOL_SHA256
            or manifest["selection_sha256"] != SELECTION_SHA256
            or selection["evaluation_outcomes_computed"] is not False
            or selection["trajectory_payloads_fetched"] is not False
            or manifest["evaluation_outcomes_computed"] is not False):
        raise ValueError("Model, selection and acquisition lineage is not the frozen pre-outcome study")
    if (protocol["models"]["ids"] != list(ABLATION_MODEL_IDS)
            or protocol["models"]["ridge_alpha"] != RIDGE_ALPHA
            or protocol["models"]["maximum_ar_spectral_radius"] != MAX_AR_SPECTRAL_RADIUS
            or protocol["origin"]["training_count"] != TRAINING_COUNT
            or protocol["origin"]["forecast_hours"] != list(HORIZONS)
            or protocol["preprocessing"]["maximum_local_distance_m"] != MAX_LOCAL_DISTANCE_M
            or protocol["assignment"]["development_only"] != sorted(DEVELOPMENT_ONLY)):
        raise ValueError("Frozen model, preprocessing, origin or group-assignment rule changed")
    groups = selection["groups"]
    ids = [group["drifter_id"] for group in groups]
    if (not 1 <= len(ids) <= TARGET_GROUPS or len(set(ids)) != len(ids)
            or any(not isinstance(value, str) or not value.isascii() or not value.isdigit() for value in ids)
            or DEVELOPMENT_ONLY & set(ids)):
        raise ValueError("Evaluation IDs must be unique, unseen whole-drifter groups; 8707978 is development-only")
    entries = manifest["trajectories"]
    if [entry["drifter_id"] for entry in entries] != ids:
        raise ValueError("Acquisition does not match the entire frozen evaluation group assignment")
    for group, entry in zip(groups, entries, strict=True):
        if (group["split_label"] != "evaluation"
                or any(entry[key] != group[key] for key in ("drifter_id", "block_id", "split_label", "start_utc", "end_utc"))):
            raise ValueError("Acquired trajectory changed its frozen group identity or window")


def load_multidrifter_inputs(directory=None):
    """Read each content-pinned payload once; corrupted files fail closed."""
    directory = Path(directory or DIRECTORY)
    protocol = _pinned_json(directory, "protocol", PROTOCOL_SHA256)
    selection = _pinned_json(directory, "selection", SELECTION_SHA256)
    manifest = _pinned_json(directory, "manifest", MANIFEST_SHA256)
    _identity(protocol, selection, manifest)
    for relative, expected in protocol["models"]["implementation_sha256"].items():
        if _digest(_read(ROOT / relative, 100_000)) != expected:
            raise ValueError("Frozen forecast/preprocessing implementation changed after preregistration")
    # The detached implementation receipt is created before the first evaluation,
    # with no self-referential digest inside the evaluator's own source bytes.
    receipt_path = directory / "implementation-receipt.json"
    receipt_bytes = _read(receipt_path, 10_000)
    receipt_sha = _read(directory / "implementation-receipt.sha256", 80).decode().strip()
    if _digest(receipt_bytes) != receipt_sha:
        raise ValueError("Detached evaluator implementation receipt is corrupt")
    receipt = json.loads(receipt_bytes)
    if (receipt["protocol_sha256"] != PROTOCOL_SHA256 or receipt["selection_sha256"] != SELECTION_SHA256
            or receipt["manifest_sha256"] != MANIFEST_SHA256
            or receipt["evaluation_outcomes_computed"] is not False
            or receipt["evaluator_sha256"] != _digest(_read(Path(__file__), 100_000))):
        raise ValueError("Evaluator implementation no longer matches its frozen pre-evaluation receipt")
    raw = {}
    entries = [selection["dataset_metadata"], *selection["blocks"], *manifest["trajectories"]]
    for entry in entries:
        if "sha256" in entry:
            raw[entry["raw_path"]] = _safe_raw(directory, entry)
        elif entry["status"] == "DOWNLOADED":
            raise ValueError("A downloaded payload is missing its content digest")
    for block, frozen_block in zip(protocol["selection"]["blocks"], selection["blocks"], strict=True):
        if block["id"] != frozen_block["block_id"]:
            raise ValueError("Selection blocks differ from their preregistered order")
        if frozen_block["status"] != "DOWNLOADED":
            if frozen_block["selected_ids"]:
                raise ValueError("Failed metadata acquisition cannot invent selected group IDs")
            continue
        rows = list(csv.reader(io.StringIO(raw[frozen_block["raw_path"]].decode())))
        if rows[0] != protocol["selection"]["metadata_columns"]:
            raise ValueError("Selection metadata columns differ from the frozen protocol")
        candidates = {row[0]: dict(zip(rows[0], row, strict=True)) for row in rows[2:]}
        eligible = sorted(set(candidates) - DEVELOPMENT_ONLY, key=int)
        expected_ids = eligible[:protocol["selection"]["target_per_block"]]
        selected_groups = [group for group in selection["groups"] if group["block_id"] == block["id"]]
        if (frozen_block["selected_ids"] != expected_ids
                or [group["drifter_id"] for group in selected_groups] != expected_ids
                or any(group["selection_metadata"] != candidates[group["drifter_id"]] for group in selected_groups)):
            raise ValueError("Group assignment no longer matches the nonadaptive metadata-selection rule")
    return protocol, selection, manifest, raw, {"sha256": receipt_sha, **receipt}


def _failed_outcomes(group, reason):
    start = datetime.fromisoformat(group["start_utc"])
    return [{"drifter_id": group["drifter_id"], "block_id": group["block_id"], "model_id": model_id,
        "horizon_hours": h, "time_utc": (start + timedelta(hours=17 + h)).isoformat().replace("+00:00", "Z"),
        "status": "FAILED", "error_m": None, "latitude_deg": None, "longitude_deg": None,
        "reason_codes": [reason]} for model_id in ABLATION_MODEL_IDS for h in HORIZONS]


def evaluate_trajectory(group, records):
    """Forecast every fixed model from its allowed prefix, then score later truth.

    UTC/ID/cadence checks can read metadata of all 24 records. Fitting reads only
    records 0..17. Future position errors cannot alter the group or model choice.
    """
    drifter_id = group["drifter_id"]
    if drifter_id in DEVELOPMENT_ONLY:
        raise ValueError("Development-only drifter cannot be an unseen evaluation group")
    start = datetime.fromisoformat(group["start_utc"])
    if (len(records) != 24 or any(record.drifter_id != drifter_id for record in records)
            or any(record.time_utc.tzinfo is None or record.time_utc.utcoffset() != timedelta(0)
                   or record.time_utc != start + timedelta(hours=i) for i, record in enumerate(records))):
        return False, _failed_outcomes(group, "INPUT_ID_OR_HOURLY_WINDOW_INVALID"), {}
    prefix = records[:TRAINING_COUNT]
    frame = SphericalLocalFrame(prefix[0].latitude_deg, prefix[0].longitude_deg)
    try:
        xy = np.asarray([frame.to_xy(record.latitude_deg, record.longitude_deg) for record in prefix])
    except (ValueError, OverflowError):
        return False, _failed_outcomes(group, "PREFIX_OUT_OF_DOMAIN"), {}
    predicted, parameters = {}, {}
    # Build every model/horizon prediction before accessing future positions.
    for model_id in ABLATION_MODEL_IDS:
        if model_id == "mean_drift":
            values = []
            for horizon in HORIZONS:
                try:
                    values.append(mean_drift_forecast(xy, horizon, STEP_S)[-1])
                except (ValueError, FloatingPointError, OverflowError):
                    values.append(None)
            predicted[model_id] = values
            parameters[model_id] = {"learned_parameters": 2,
                "mean_velocity_m_s": ((xy[-1] - xy[0]) / ((len(xy) - 1) * STEP_S)).tolist()}
        else:
            try:
                values, params = _forecast(xy, len(HORIZONS), STEP_S, model_id)
                json.dumps(params, allow_nan=False)
                predicted[model_id], parameters[model_id] = list(values), params
            except (ValueError, FloatingPointError, OverflowError, np.linalg.LinAlgError):
                predicted[model_id], parameters[model_id] = [None] * 6, {}
    outcomes = []
    for model_id in ABLATION_MODEL_IDS:
        for horizon, value in zip(HORIZONS, predicted[model_id], strict=True):
            truth = records[TRAINING_COUNT + horizon - 1]
            row = {"drifter_id": drifter_id, "block_id": group["block_id"], "model_id": model_id,
                "horizon_hours": horizon, "time_utc": truth.time_utc.isoformat().replace("+00:00", "Z"),
                "status": "FAILED", "error_m": None, "latitude_deg": None, "longitude_deg": None,
                "reason_codes": ["MODEL_FORECAST_FAILED"]}
            if value is not None:
                try:
                    latitude, longitude = frame.to_latlon(value)
                    row.update(latitude_deg=latitude, longitude_deg=longitude)
                    # Future truth has no 50 km distance filter. Large misses stay
                    # actual errors rather than eligibility exclusions.
                    if (not all(math.isfinite(v) for v in (truth.latitude_deg, truth.longitude_deg))
                            or not -90 <= truth.latitude_deg <= 90 or not -180 <= truth.longitude_deg <= 180):
                        row["reason_codes"] = ["TRUTH_UNAVAILABLE"]
                    else:
                        error = great_circle_distance_m((latitude, longitude), (truth.latitude_deg, truth.longitude_deg))
                        row.update(status="SCORED", error_m=error, reason_codes=[])
                except (ValueError, FloatingPointError, OverflowError):
                    row["reason_codes"] = ["FORECAST_OUT_OF_DOMAIN"]
            outcomes.append(row)
    return True, outcomes, parameters


def _paired(candidate, baseline):
    delta = np.asarray(candidate) - np.asarray(baseline)
    baseline_sum = float(sum(baseline))
    skill = 1 - sum(candidate) / baseline_sum if baseline_sum else None
    if skill is not None and not math.isfinite(skill):
        raise ValueError("Paired acquired-cohort skill exceeds its finite arithmetic budget")
    return {"count": len(candidate), "mean_delta_m": float(delta.mean()),
        "median_delta_m": float(np.median(delta)), "min_delta_m": float(delta.min()),
        "max_delta_m": float(delta.max()), "candidate_lower_error_count": int(np.sum(delta < 0)),
        "equal_error_count": int(np.sum(delta == 0)), "candidate_higher_error_count": int(np.sum(delta > 0)),
        "skill_vs_baseline": skill,
        "reason_codes": [] if baseline_sum else ["ZERO_BASELINE_ERROR"]}


def aggregate_outcomes(groups, outcomes, parameters=None):
    """Require the exact declared Cartesian matrix; never drop failed forecasts."""
    parameters = parameters or {}
    ids = [group["drifter_id"] for group in groups]
    if not 1 <= len(ids) <= TARGET_GROUPS or len(set(ids)) != len(ids) or DEVELOPMENT_ONLY & set(ids):
        raise ValueError("Declare unique unseen evaluation groups before scoring")
    expected = set(itertools.product(ids, ABLATION_MODEL_IDS, HORIZONS))
    rows = {}
    for row in outcomes:
        key = row["drifter_id"], row["model_id"], row["horizon_hours"]
        if key not in expected or key in rows or type(row["horizon_hours"]) is not int:
            raise ValueError("Outcome Cartesian matrix has an extra, repeated or invalid identity")
        error = row["error_m"]
        if row["status"] == "SCORED":
            if (isinstance(error, bool) or not isinstance(error, (int, float)) or not math.isfinite(error)
                    or not 0 <= error <= math.pi * EARTH_MEAN_RADIUS_M or row["reason_codes"]):
                raise ValueError("Scored outcome requires a finite great-circle error and no failure reasons")
        elif row["status"] != "FAILED" or error is not None or not row["reason_codes"]:
            raise ValueError("Failed outcome must retain null error and an explicit reason")
        rows[key] = row
    if set(rows) != expected:
        raise ValueError("Outcome Cartesian matrix is incomplete; failures must remain explicit")
    summaries = []
    for drifter_id, model_id in itertools.product(ids, ABLATION_MODEL_IDS):
        model_rows = [rows[drifter_id, model_id, h] for h in HORIZONS]
        errors = [row["error_m"] for row in model_rows if row["status"] == "SCORED"]
        complete = len(errors) == len(HORIZONS)
        summaries.append({"drifter_id": drifter_id, "model_id": model_id, "attempted_horizons": 6,
            "scored_horizons": len(errors), "failed_horizons": 6 - len(errors),
            "mean_error_m": float(np.mean(errors)) if complete else None,
            "rmse_error_m": float(np.sqrt(np.mean(np.square(errors)))) if complete else None,
            "endpoint_error_m": model_rows[-1]["error_m"],
            "parameters": parameters.get(drifter_id, {}).get(model_id, {})})
    complete_ids = [drifter_id for drifter_id in ids if all(rows[drifter_id, model_id, h]["status"] == "SCORED"
                    for model_id, h in itertools.product(ABLATION_MODEL_IDS, HORIZONS))]
    ready = len(complete_ids) == len(ids)
    models = []
    for model_id in ABLATION_MODEL_IDS:
        model_summaries = [row for row in summaries if row["model_id"] == model_id]
        complete_count = sum(row["mean_error_m"] is not None for row in model_summaries)
        per_horizon = []
        for horizon in HORIZONS:
            values = [rows[drifter_id, model_id, horizon]["error_m"] for drifter_id in ids]
            scored = sum(value is not None for value in values)
            per_horizon.append({"horizon_hours": horizon, "attempted_groups": len(ids), "scored_groups": scored,
                "failed_groups": len(ids) - scored, "mean_error_m": float(np.mean(values)) if ready else None,
                "rmse_error_m": float(np.sqrt(np.mean(np.square(values)))) if ready else None})
        models.append({"id": model_id, "macro": {"scope": METRIC_SCOPE, "attempted_groups": len(ids),
            "complete_groups": complete_count, "failed_groups": len(ids) - complete_count,
            "mean_trajectory_error_m": float(np.mean([row["mean_error_m"] for row in model_summaries])) if ready else None},
            "per_horizon": per_horizon})
    pairs = []
    for baseline_id in BASELINE_IDS:
        candidate, baseline = [], []
        if ready:
            for drifter_id in ids:
                candidate.append(next(row["mean_error_m"] for row in summaries
                                      if row["drifter_id"] == drifter_id and row["model_id"] == "ridge_ar1"))
                baseline.append(next(row["mean_error_m"] for row in summaries
                                     if row["drifter_id"] == drifter_id and row["model_id"] == baseline_id))
        pairs.append({"candidate_id": "ridge_ar1", "baseline_id": baseline_id,
            "delta_definition": "candidate_minus_baseline_error_m", "attempted_groups": len(ids),
            "scored_groups": len(complete_ids), "failed_groups": len(ids) - len(complete_ids),
            "summary": _paired(candidate, baseline) if ready else None,
            "reason_codes": [] if ready else ["INCOMPLETE_COMMON_COHORT_COVERAGE"]})
    return summaries, models, pairs, complete_ids


def run_multidrifter_study() -> dict:
    """Offline deterministic replay of the frozen pre-evaluation acquired cohort."""
    protocol, selection, manifest, raw, implementation = load_multidrifter_inputs()
    outcomes, groups, parameters = [], [], {}
    for entry in manifest["trajectories"]:
        group = {key: entry[key] for key in ("drifter_id", "block_id", "split_label", "start_utc", "end_utc", "source_url")}
        eligible, values, params = False, [], {}
        if entry["status"] != "DOWNLOADED":
            values = _failed_outcomes(group, "ACQUISITION_FAILED")
        else:
            try:
                records = parse_drifter_csv(raw[entry["raw_path"]].decode("utf-8"))
                eligible, values, params = evaluate_trajectory(group, records)
            except (ValueError, UnicodeError, KeyError):
                values = _failed_outcomes(group, "INPUT_DATA_INVALID")
        outcomes.extend(values)
        parameters[group["drifter_id"]] = params
        reasons = sorted({reason for row in values for reason in row["reason_codes"]})
        group.update(eligible=eligible, status="SCORED" if not reasons else "FAILED", reason_codes=reasons)
        groups.append(group)
    summaries, models, pairs, complete_ids = aggregate_outcomes(groups, outcomes, parameters)
    declared = len(groups)
    scored = sum(row["status"] == "SCORED" for row in outcomes)
    selection_failures = [{"block_id": block["block_id"], "status": block["status"], "reason": block["reason"],
        "source_url": block["source_url"], "selected_count": len(block["selected_ids"]), "target_count": 2}
        for block in selection["blocks"] if len(block["selected_ids"]) != 2]
    report = {"schema_version": 1, "kind": "MULTI_DRIFTER_RETROSPECTIVE_STUDY", "study_id": STUDY_ID,
        "status": "COMPLETED" if declared == TARGET_GROUPS and len(complete_ids) == declared else "PARTIAL_COVERAGE",
        "data_origin": "REAL_HISTORICAL_NOAA_DRIFTERS", "metric_scope": METRIC_SCOPE,
        "test_data_used": True, "model_selection_performed": False, "calibrated_probability": False,
        "physical_validation": False, "automatic_model_promotion": False,
        "independent_replication_verified": False, "statistical_independence": False,
        "protocol": {"sha256": PROTOCOL_SHA256, "selection_sha256": SELECTION_SHA256,
            "manifest_sha256": MANIFEST_SHA256, "implementation_receipt_sha256": implementation["sha256"],
            "frozen_at_utc": protocol["frozen_at_utc"], "selection_frozen_at_utc": selection["frozen_at_utc"],
            "implementation_frozen_at_utc": implementation["frozen_at_utc"],
            "training_count": TRAINING_COUNT, "horizons_hours": list(HORIZONS),
            "model_ids": list(ABLATION_MODEL_IDS), "development_only_ids": sorted(DEVELOPMENT_ONLY),
            "selection_method": protocol["selection"]["method"]},
        "coverage": {"target_groups": TARGET_GROUPS, "declared_groups": declared,
            "eligible_groups": sum(group["eligible"] for group in groups), "complete_groups": len(complete_ids),
            "target_outcomes": TARGET_GROUPS * 24, "attempted_outcomes": len(outcomes),
            "scored_outcomes": scored, "failed_outcomes": len(outcomes) - scored,
            "missing_selection_slots": TARGET_GROUPS - declared, "selection_complete": declared == TARGET_GROUPS,
            "sampling_coverage_fraction": declared / TARGET_GROUPS,
            "model_prediction_coverage_fraction": scored / len(outcomes),
            "acquired_cohort_complete": len(complete_ids) == declared},
        "selection_failures": selection_failures, "groups": groups, "outcomes": outcomes,
        "trajectory_summaries": summaries, "models": models, "paired_comparisons": pairs,
        "provenance": {"provider": protocol["source"]["provider"], "metadata_url": protocol["source"]["metadata_url"],
            "product_doi": protocol["source"]["product_doi"], "license_name": protocol["source"]["license_name"],
            "license_url": protocol["source"]["license_url"], "integrity_verified": True,
            "sources": [{key: entry.get(key) for key in ("drifter_id", "block_id", "source_url", "sha256", "bytes",
                                                        "retrieved_at_utc", "status")} for entry in manifest["trajectories"]]},
        "limitations": [*protocol["limitations"],
            "Only four of six target metadata slots were acquired; Indian2010 metadata timed out. No replacement or score-based cohort repair occurred.",
            "Macro metrics describe all frozen acquired groups only, not the full planned six-group target. If any acquired outcome fails, all common-cohort macro errors and paired summaries are withheld.",
            "Per-group fitting on its permitted prefix is algorithm adaptation to unseen outcomes, not a globally trained model evaluated with no adaptation.",
            "The 50 km cap is a computational geometry domain, not a quality or ecological gate. Domain and forecast failures remain explicit in attempted coverage.",
            "Grok supplied static design assistance; local code and tests determine the results. No external assistant executed this study."]}
    json.dumps(report, allow_nan=False)
    return report
