"""Synthetic image-to-vector replay; no device, physical evidence or model fitting.

The moving images and reference field are declared demonstration fixtures. The
existing HSV detector, independent-check homography and gap-preserving tracker
extract their observations. A deliberately imperfect frozen reference illustrates
vector errors; it is not a trained current model or a physical validation result.
"""

from __future__ import annotations

import hashlib
import json

import cv2
import numpy as np

from .calibration import fit_homography
from .tracking import SingleTokenTracker, detect_red, flow_samples

ORIGIN = "SYNTHETIC_SOFTWARE_REPLAY"
MAX_FRAMES = 512
MAX_FRAME_SIDE_PX = 512
SESSION_ID = "SYNTHETIC-SOFTWARE-REPLAY-NO-CAMERA"
DIRECTION_MIN_SPEED_CM_S = 0.01


def _extract_sequence(frames, times_s, calibration):
    """Exercise the production extraction helpers on bounded in-memory images."""
    if not 1 <= len(frames) <= MAX_FRAMES or len(frames) != len(times_s):
        raise ValueError("Require 1..512 matching synthetic frames and time offsets")
    times = np.asarray(times_s, dtype=float)
    if (not np.isfinite(times).all() or np.any(times < 0)
            or np.any(np.diff(times) <= 0)):
        raise ValueError("Synthetic monotonic time offsets must be finite and increasing")
    tracker, observations, hashes = SingleTokenTracker(), [], []
    for index, (frame, offset) in enumerate(zip(frames, times, strict=True)):
        if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8
                or frame.ndim != 3 or frame.shape[2] != 3
                or not 1 <= min(frame.shape[:2]) <= max(frame.shape[:2]) <= MAX_FRAME_SIDE_PX):
            raise ValueError("Synthetic images must be uint8 BGR, at most 512 pixels per side")
        point = tracker.update(detect_red(frame), float(offset), calibration)
        observations.append({**point, "frame_id": f"synthetic-frame-{index:04d}",
                             "camera_session_id": SESSION_ID, "data_origin": ORIGIN,
                             "physical_validation": False})
        hashes.append(hashlib.sha256(frame.tobytes()).hexdigest())
    samples = flow_samples(observations)
    # Production identities use random UUIDs. Preserve their equality/breaks but
    # normalize labels for a byte-reproducible synthetic report, without changing
    # any detector coordinates, association decisions or finite differences.
    identities = {}
    for point in observations:
        if point.get("track_id") is not None:
            old_id = point["track_id"]
            if old_id not in identities:
                identities[old_id] = f"synthetic-track-{len(identities) + 1:04d}"
            point["track_id"] = identities[old_id]
    return observations, samples, hashes


def _compare_vectors(samples, predicted_velocity):
    """Vectorized, paired errors: predicted minus observed; undefined angles stay null."""
    if not samples:
        return [], {"sample_count": 0, "vector_rmse_cm_s": None,
                    "mean_speed_bias_cm_s": None, "mean_absolute_speed_error_cm_s": None,
                    "mean_direction_error_deg": None, "direction_defined_count": 0}
    observed = np.asarray([[s["vx_cm_s"], s["vy_cm_s"]] for s in samples], dtype=float)
    positions = np.asarray([[s["x_cm"], s["y_cm"]] for s in samples], dtype=float)
    if not np.isfinite(observed).all() or not np.isfinite(positions).all():
        raise ValueError("Observed velocities and sample coordinates must be finite")
    predicted = np.asarray(predicted_velocity, dtype=float)
    if predicted.shape != observed.shape or not np.isfinite(predicted).all():
        raise ValueError("Predictions must supply one finite two-component velocity per sample")
    residual = predicted - observed
    error = np.linalg.norm(residual, axis=1)
    observed_speed = np.linalg.norm(observed, axis=1)
    predicted_speed = np.linalg.norm(predicted, axis=1)
    speed_bias = predicted_speed - observed_speed
    defined = ((observed_speed >= DIRECTION_MIN_SPEED_CM_S)
               & (predicted_speed >= DIRECTION_MIN_SPEED_CM_S))
    angles = np.zeros(len(samples), dtype=float)
    cosine = (np.sum(predicted[defined] * observed[defined], axis=1)
              / (predicted_speed[defined] * observed_speed[defined]))
    angles[defined] = np.degrees(np.arccos(np.clip(cosine, -1, 1)))
    vectors = []
    for index, sample in enumerate(samples):
        vectors.append({
            "x_cm": sample["x_cm"], "y_cm": sample["y_cm"],
            "observed_vx_cm_s": float(observed[index, 0]),
            "observed_vy_cm_s": float(observed[index, 1]),
            "predicted_vx_cm_s": float(predicted[index, 0]),
            "predicted_vy_cm_s": float(predicted[index, 1]),
            "residual_vx_cm_s": float(residual[index, 0]),
            "residual_vy_cm_s": float(residual[index, 1]),
            "vector_error_cm_s": float(error[index]),
            "speed_bias_cm_s": float(speed_bias[index]),
            "absolute_speed_error_cm_s": float(abs(speed_bias[index])),
            "direction_error_deg": float(angles[index]) if defined[index] else None,
            "data_origin": ORIGIN, "physical_validation": False,
        })
    return vectors, {
        "sample_count": len(samples), "vector_rmse_cm_s": float(np.sqrt(np.mean(error ** 2))),
        "mean_speed_bias_cm_s": float(speed_bias.mean()),
        "mean_absolute_speed_error_cm_s": float(np.abs(speed_bias).mean()),
        "mean_direction_error_deg": float(angles[defined].mean()) if defined.any() else None,
        "direction_defined_count": int(defined.sum()),
    }


def run_synthetic_vector_diagnostic() -> dict:
    """Replay eight red-token images against a frozen 4 cm/s reference field.

    Image centroids advance 10 px every 0.2 synthetic seconds. The independently
    checked 0.1 cm/px mapping therefore extracts 5 cm/s; the reference intentionally
    underpredicts by 1 cm/s. Nothing is acquired from a camera or admitted as a
    measured flow/profile, and no model is fitted, selected or promoted.
    """
    # Define predictions before constructing/reading the target image sequence.
    frozen_velocity_cm_s = [4.0, 0.0]
    calibration = fit_homography(
        [[0, 0], [399, 0], [399, 239], [0, 239]],
        [[0, 0], [39.9, 0], [39.9, 23.9], [0, 23.9]],
        [[40, 40], [160, 120], [300, 200]],
        [[4, 4], [16, 12], [30, 20]],
        max_error_cm=0.001, image_size_px=[400, 240], camera_session_id=SESSION_ID,
    )
    frames, times_s = [], [index * 0.2 for index in range(8)]
    for index in range(8):
        image = np.zeros((240, 400, 3), dtype=np.uint8)
        cv2.circle(image, (50 + index * 10, 100), 6, (0, 0, 255), -1)
        frames.append(image)
    observations, samples, hashes = _extract_sequence(frames, times_s, calibration)
    predicted = np.broadcast_to(frozen_velocity_cm_s, (len(samples), 2))
    vectors, metrics = _compare_vectors(samples, predicted)
    report = {
        "schema_version": 1, "kind": "SYNTHETIC_VISION_VECTOR_DIAGNOSTIC",
        "status": "COMPLETED", "data_origin": ORIGIN, "physical_validation": False,
        "camera_started": False, "hardware_actuation": False,
        "camera_session_id": SESSION_ID,
        "coordinates": {"position_units": "cm", "velocity_units": "cm/s",
                        "image_size_px": [400, 240], "frame_count": len(frames),
                        "timestamp_kind": "SYNTHETIC_MONOTONIC_OFFSETS",
                        "direction_min_speed_cm_s": DIRECTION_MIN_SPEED_CM_S},
        "model": {"id": "synthetic-frozen-constant-reference-4cm-s",
                  "kind": "DECLARED_SYNTHETIC_REFERENCE_NOT_TRAINED",
                  "velocity_cm_s": frozen_velocity_cm_s,
                  "frozen_before_scoring": True, "trained": False,
                  "model_selection_performed": False, "promotion_performed": False},
        "calibration": {**calibration, "data_origin": ORIGIN, "physical_validation": False},
        "frames": [{"id": point["frame_id"], "t_s": point["t_s"], "sha256_bgr_bytes": digest,
                    "data_origin": ORIGIN, "physical_validation": False,
                    "camera_session_id": SESSION_ID}
                   for point, digest in zip(observations, hashes, strict=True)],
        "observations": observations, "vectors": vectors, "metrics": metrics,
        "admission": {"measured_profile_admitted": False, "store_written": False,
                      "data_origin": ORIGIN},
        "limitations": [
            "Synthetic software replay only: no physical tank, camera or ocean was observed.",
            "Four nonoverlapping differences from one synthetic track are dependent, not four independent trials.",
            "Accepted detector quality=1 is not calibrated probability or confidence.",
            "The deliberately imperfect frozen reference is not an ML model, water-current measurement or source prediction.",
            "Angles are undefined if either velocity is below the declared speed threshold.",
            "This fixture cannot validate NOAA forecasts, plastic origins, interception performance or ecological benefit.",
        ],
    }
    json.dumps(report, allow_nan=False)
    return report
