"""Read-only inspection of a previously frozen recorded-drift field.

This conditions on observed validation midpoints. It is neither a free-running
forecast nor a new independent experiment. Stored capture declarations are not
independent verification that any physical tank or camera was used.
"""

from __future__ import annotations

import hashlib
import json
import math
import re

import numpy as np

from apps.transport.reeftrace_transport.flow import FlowField

from .tracking import flow_samples
from .vector_diagnostic import _compare_vectors

MAX_POINTS = 20000
MAX_SAMPLES = 10000


def _identifier(value):
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", value) is None:
        raise ValueError("A bounded stored-artifact identifier is required")
    return value


def _load(store, kind, identifier):
    identifier = _identifier(identifier)
    document = store.get(kind, identifier)
    if not isinstance(document, dict) or document.get("id") != identifier:
        raise ValueError("Stored artifact identity does not match its reference")
    return document


def _fake(document):
    # Test artifacts can deliberately carry MEASURED_TANK to exercise admission.
    # A recorded label must never suppress their explicit fake/test provenance.
    keys = ("test_fixture_origin", "capture_origin", "backend", "data_origin")
    return any(isinstance(document.get(key), str)
               and any(marker in document[key].upper() for marker in ("SYNTHETIC", "FAKE", "TEST"))
               for key in keys)


def _digest(document):
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def inspect_recorded_flow_vectors(store, flow_id) -> dict:
    """Re-read exact frozen fit/recordings; never acquire, fit, write or promote."""
    flow = _load(store, "flow", flow_id)
    if flow.get("data_origin") != "MEASURED_TANK":
        raise ValueError("Select an immutable recorded-flow fit, not a synthetic or unverified fit")
    provenance = flow.get("provenance") or {}
    if provenance.get("frame_splits_disjoint") is not True:
        raise ValueError("Recorded flow requires disjoint frame-split provenance")
    calibration_id = _identifier(provenance.get("calibration_id"))
    session_id = _identifier(provenance.get("camera_session_id"))
    split_ids = {}
    for split in ("training", "validation"):
        values = provenance.get(f"{split}_recording_ids")
        if not isinstance(values, list) or not 1 <= len(values) <= 100:
            raise ValueError("Frozen flow must name 1..100 recordings in both splits")
        values = [_identifier(value) for value in values]
        if len(set(values)) != len(values):
            raise ValueError("Frozen recording references must be distinct")
        split_ids[split] = values
    if set(split_ids["training"]) & set(split_ids["validation"]):
        raise ValueError("Training and validation recordings overlap")
    calibration = _load(store, "calibration", calibration_id)
    body = {key: value for key, value in calibration.items() if key not in {"id", "calibration_id"}}
    expected = "cal-" + hashlib.sha256(
        json.dumps(body, sort_keys=True, allow_nan=False).encode()).hexdigest()[:16]
    if (not calibration.get("approved") or calibration.get("calibration_id") != expected
            or expected != calibration_id or calibration.get("camera_session_id") != session_id):
        raise ValueError("Frozen calibration identity, approval or camera-session binding failed")
    field, total_points = FlowField(flow), 0
    split_frames, loaded = {"training": set(), "validation": set()}, {}
    synthetic = _fake(flow) or _fake(calibration)
    for split, ids in split_ids.items():
        loaded[split] = []
        for recording_id in ids:
            recording = _load(store, "recording", recording_id)
            if (recording.get("data_origin") != "MEASURED_TANK"
                    or recording.get("calibration_id") != calibration_id
                    or recording.get("camera_session_id") != session_id
                    or recording.get("timestamp_kind") != "host_receipt_not_exposure"):
                raise ValueError("Recording origin, mapping, session or timestamp binding failed")
            points, frames = recording.get("points"), recording.get("evidence_frame_ids")
            if not isinstance(points, list) or not points or not isinstance(frames, list) or not frames:
                raise ValueError("Recordings require saved points and evidence frames")
            total_points += len(points)
            if total_points > MAX_POINTS or len(points) != len(frames):
                raise ValueError("Recorded point/frame identity or 20000-point budget failed")
            frames = [_identifier(value) for value in frames]
            if len(set(frames)) != len(frames) or split_frames[split] & set(frames):
                raise ValueError("Recording evidence frames are duplicated or reused")
            previous = -1.0
            for point, frame_id in zip(points, frames, strict=True):
                if not isinstance(point, dict) or point.get("frame_id") != frame_id:
                    raise ValueError("Point/frame evidence references do not match")
                t_s = point.get("t_s")
                if type(t_s) not in (int, float) or not math.isfinite(t_s) or t_s <= previous:
                    raise ValueError("Recorded time offsets must be finite and strictly increasing")
                previous = t_s
                if point.get("observed") is True:
                    values = [point.get("x_cm"), point.get("y_cm")]
                    if (any(type(value) not in (int, float) or not math.isfinite(value) for value in values)
                            or not isinstance(point.get("track_id"), str) or not point["track_id"]):
                        raise ValueError("Observed recorded positions require finite coordinates and track identity")
                elif point.get("observed") is not False:
                    raise ValueError("Recorded observation presence must be explicit")
                frame = _load(store, "frame", frame_id)
                if frame.get("camera_session_id") != session_id:
                    raise ValueError("Evidence frame belongs to another camera session")
                synthetic = synthetic or _fake(frame) or _fake(point)
            split_frames[split].update(frames)
            synthetic = synthetic or _fake(recording)
            loaded[split].append((recording, flow_samples(points)))
    if split_frames["training"] & split_frames["validation"]:
        raise ValueError("Training and validation evidence frames overlap")
    counts = {split: sum(len(samples) for _, samples in rows) for split, rows in loaded.items()}
    if not all(counts.values()) or sum(counts.values()) > MAX_SAMPLES:
        raise ValueError("Require supported extraction in both splits within the 10000-sample budget")
    origin = "SYNTHETIC_CAPTURE_REPLAY" if synthetic else "RECORDED_TANK_CAPTURE_UNVERIFIED"
    recordings, supported_samples, supported_predictions = [], [], []
    supported_total, unsupported_total, run_rmses = 0, 0, []
    for recording, samples in loaded["validation"]:
        vectors, selected_samples, selected_predictions = [], [], []
        if samples:
            predictions, supported = field.evaluate([[s["x_cm"], s["y_cm"]] for s in samples])
            for index, (sample, prediction, ok) in enumerate(zip(samples, predictions, supported, strict=True)):
                if ok:
                    vector = _compare_vectors([sample], [prediction])[0][0]
                    selected_samples.append(sample)
                    selected_predictions.append(prediction)
                else:
                    vector = {"x_cm": sample["x_cm"], "y_cm": sample["y_cm"],
                              "observed_vx_cm_s": sample["vx_cm_s"], "observed_vy_cm_s": sample["vy_cm_s"],
                              **{key: None for key in ("predicted_vx_cm_s", "predicted_vy_cm_s",
                                  "residual_vx_cm_s", "residual_vy_cm_s", "vector_error_cm_s",
                                  "speed_bias_cm_s", "absolute_speed_error_cm_s", "direction_error_deg")}}
                vectors.append({**vector, "sample_index": index, "supported": bool(ok),
                                "data_origin": origin, "physical_validation": False})
        _, metrics = _compare_vectors(selected_samples, selected_predictions)
        supported_samples.extend(selected_samples)
        supported_predictions.extend(selected_predictions)
        supported_total += len(selected_samples)
        unsupported_total += len(samples) - len(selected_samples)
        if metrics["vector_rmse_cm_s"] is not None:
            run_rmses.append(metrics["vector_rmse_cm_s"])
        points = recording["points"]
        recordings.append({"recording_id": recording["id"], "data_origin": origin,
            "physical_validation": False, "recording_content_hash": _digest(recording),
            "counts": {"point_count": len(points), "frame_count": len(recording["evidence_frame_ids"]),
                       "observed_point_count": sum(p["observed"] is True for p in points),
                       "missing_point_count": sum(p["observed"] is False for p in points),
                       "ambiguous_point_count": sum(p.get("reason") == "MULTIPLE_TOKENS" for p in points),
                       "no_detection_point_count": sum(p.get("reason") == "NO_DETECTION" for p in points),
                       "association_gap_count": sum(p.get("reason") == "ASSOCIATION_GAP" for p in points),
                       "track_count": len({p["track_id"] for p in points if p["observed"]}),
                       "extracted_sample_count": len(samples), "supported_sample_count": len(selected_samples),
                       "unsupported_sample_count": len(samples) - len(selected_samples)},
            "metrics": metrics, "vectors": vectors})
    _, metrics = _compare_vectors(supported_samples, supported_predictions)
    metrics["equal_recording_mean_rmse_cm_s"] = float(np.mean(run_rmses)) if run_rmses else None
    metrics["recordings_with_supported_samples"] = len(run_rmses)
    report = {"schema_version": 1, "kind": "RECORDED_FIELD_VECTOR_DIAGNOSTIC", "status": "COMPLETED",
        "scope": "CONDITIONAL_HELDOUT_FIELD_INTERPOLATION_ALREADY_REVIEWED_NOT_INDEPENDENT_TEST",
        "flow_id": flow_id, "flow_content_hash": _digest(flow), "calibration_id": calibration_id,
        "camera_session_id": session_id, "data_origin": origin, "recorded_data_origin": "MEASURED_TANK",
        "capture_origin": "SYNTHETIC_CAPTURE_REPLAY" if synthetic else "UNVERIFIED_STORED_CAPTURE",
        "capture_independently_verified": False, "physical_validation": False,
        "camera_started": False, "hardware_actuation": False, "provider_calls": False,
        "store_written": False, "refit_performed": False, "model_selection_performed": False,
        "position_units": "cm", "velocity_units": "cm/s", "timestamp_kind": "host_receipt_not_exposure",
        "provenance": {"training_recording_ids": split_ids["training"],
                       "validation_recording_ids": split_ids["validation"], "frame_splits_disjoint": True},
        "coverage": {"training_recording_count": len(loaded["training"]),
                     "validation_recording_count": len(loaded["validation"]),
                     "training_sample_count": counts["training"], "validation_sample_count": counts["validation"],
                     "supported_sample_count": supported_total, "unsupported_sample_count": unsupported_total,
                     "supported_fraction": supported_total / counts["validation"]},
        "metrics": metrics, "recordings": recordings,
        "limitations": [
            "Conditional field interpolation at observed validation midpoints, not a free-running trajectory forecast.",
            "These validation runs already contributed to the saved fit diagnostics; this is not a new independent experiment.",
            "Unsupported samples remain visible with predictions and scores withheld; supported error must be read with coverage.",
            "Vectors within a run share motion and are dependent; equal-recording summaries are descriptive only.",
            "Stored MEASURED_TANK labels are capture declarations, not independent proof of physical hardware or validation.",
            "Host receipt timestamps differ from exposure times; this is object drift, not direct water-current measurement.",
            "No source identity, calibrated probability, interception benefit or ecological impact is established.",
        ]}
    json.dumps(report, allow_nan=False)
    return report
