"""Reuse an immutable map only after current checks; never relabel old evidence."""
from __future__ import annotations

import copy
import hashlib
import json

import numpy as np

from apps.vision.reeftrace_vision.calibration import project

from ..schemas.saved_calibrations import CalibrationRecord
from .field_sessions import MAX_TABLETOP_SPAN_CM, calibration_intact, digest

SCHEMA_VERSION = "nemo_saved_calibration_v1"
SUMMARY_FIELDS = ("calibration_id", "camera_session_id", "image_size_px", "approved",
                  "max_error_cm", "max_allowed_error_cm", "mean_error_cm", "validation_count")


def validate_saved_record(record):
    CalibrationRecord.model_validate(record)
    if not calibration_intact(record):
        raise ValueError("Saved calibration content does not match its immutable ID")
    matrix = np.asarray(record["homography_image_to_cm"], dtype=float)
    width, height = record["image_size_px"]
    corners = np.asarray([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    mapped = np.asarray(project(matrix, corners))  # Rejects singularity or a corner at infinity.
    if np.ptp(mapped, axis=0).max() > MAX_TABLETOP_SPAN_CM:
        raise ValueError("Saved mapping exceeds the 200 cm tabletop scope; check centimetre units")
    matrix = matrix / np.max(np.abs(matrix))
    denominators = np.column_stack([corners, np.ones(4)]) @ matrix[2]
    if denominators.min() <= 0 <= denominators.max():
        raise ValueError("Saved calibration horizon crosses the camera image")
    if record["mean_error_cm"] > record["max_error_cm"]:
        raise ValueError("Saved calibration error summary is inconsistent")
    if record["approved"] and record["max_error_cm"] > record["max_allowed_error_cm"]:
        raise ValueError("Saved calibration approval contradicts its original tolerance")
    if record.get("reuse") is not None and not record["reuse"]["water_plane_unchanged"]:
        raise ValueError("Saved calibration reuse did not retain the original water plane")
    return record


class SavedCalibrationService:
    def __init__(self, runtime):
        self.runtime = runtime

    def list(self):
        summaries = []
        for record in self.runtime.store.list("calibration", 100):
            validate_saved_record(record)
            summaries.append({field: record[field] for field in SUMMARY_FIELDS})
        return {"calibrations": summaries}

    def export(self, calibration_id):
        record = self.runtime.store.get("calibration", calibration_id)
        validate_saved_record(record)
        return {"schema_version": SCHEMA_VERSION, "calibration": record,
                "calibration_json": json.dumps(record, sort_keys=True, allow_nan=False)}

    def _current_camera(self, body):
        status = self.runtime.camera.status()
        if not status.get("running") or not status.get("fresh"):
            raise ValueError("Start the local camera and wait for fresh frames before checking a saved map")
        if status.get("session_id") != body.camera_session_id:
            raise ValueError("The selected camera session is no longer current")
        if [status.get("width"), status.get("height")] != list(body.image_size_px):
            raise ValueError("Current camera dimensions do not match the check image")

    def revalidate(self, body):
        source = validate_saved_record(body.source.source_record)
        if self.runtime.registration.is_managed(source["calibration_id"]):
            raise ValueError("Marker-managed maps need a new monitored proposal, not detached reuse")
        if not source["approved"]:
            raise ValueError("Only an originally approved saved calibration can be reused")
        self._current_camera(body)
        if list(source["image_size_px"]) != list(body.image_size_px):
            raise ValueError("Saved and current camera dimensions differ; refit instead of scaling a map")
        pixels = np.asarray(body.check_pixels, dtype=float)
        world = np.asarray(body.check_world_cm, dtype=float)
        if len(pixels) != len(world):
            raise ValueError("Each current check pixel needs its corresponding surveyed world point")
        for points in (pixels, world):
            if len(np.unique(points, axis=0)) != len(points):
                raise ValueError("Current check points must be distinct")
            if np.linalg.matrix_rank(points - points.mean(axis=0)) < 2:
                raise ValueError("Current check points must span the plane, not lie on one line")
        if np.any(pixels < 0) or np.any(pixels > np.asarray(body.image_size_px) - 1):
            raise ValueError("Current check pixels lie outside the actual camera image")
        errors = np.linalg.norm(np.asarray(project(source["homography_image_to_cm"], pixels)) - world,
                                axis=1)
        report = {key: copy.deepcopy(value) for key, value in source.items()
                  if key not in {"id", "calibration_id", "reuse"}}
        report.update(camera_session_id=body.camera_session_id,
                      image_size_px=list(body.image_size_px), validation_count=len(pixels),
                      mean_error_cm=float(errors.mean()), max_error_cm=float(errors.max()),
                      approved=bool(errors.max() <= source["max_allowed_error_cm"]),
                      reuse={"method": "fixed_homography_current_checks_v1",
                             "source_calibration_id": source["calibration_id"],
                             "source_content_sha256": digest(source),
                             "check_pixels": pixels.tolist(), "check_world_cm": world.tolist(),
                             "water_plane_unchanged": True})
        # Keep the exact legacy content-addressing rule; old objects remain untouched.
        report["calibration_id"] = "cal-" + hashlib.sha256(
            json.dumps(report, sort_keys=True, allow_nan=False).encode()).hexdigest()[:16]
        self._current_camera(body)
        try:
            return self.runtime.store.put("calibration", report, report["calibration_id"])
        except ValueError:
            existing = self.runtime.store.get("calibration", report["calibration_id"])
            validate_saved_record(existing)
            if existing != {**report, "id": report["calibration_id"]}:
                raise ValueError("An existing calibration has different immutable content") from None
            return existing
