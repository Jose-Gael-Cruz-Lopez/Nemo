"""Local footage with explicitly estimated coordinates, outside measured evidence."""
from __future__ import annotations

import asyncio
import math
import shutil
import time

from apps.vision.reeftrace_vision.foreground import ViewObstructed
from apps.vision.reeftrace_vision.tracking import SingleTokenTracker

from .field_sessions import digest
from .saved_calibrations import validate_saved_record
from .store import uid

KIND = "estimated_rehearsal"
FRAME_KIND = "estimated_rehearsal_frame"
WARNING = (
    "Rehearsal only: real local camera capture with approximate coordinates from a historical map. "
    "Current camera-to-water-plane alignment is unvalidated. The historical centimetre tolerance "
    "is not current accuracy. This is not measured drift, source evidence or a validated tank trial."
)


class EstimatedRehearsalService:
    def __init__(self, runtime):
        self.runtime = runtime

    def _current_camera(self, body):
        status = self.runtime.camera.status()
        if not status.get("running") or not status.get("fresh"):
            raise ValueError("Start the local camera and wait for fresh frames before a rehearsal")
        if status.get("session_id") != body.camera_session_id:
            raise ValueError("Camera session changed; the rehearsal was not accepted")
        if [status.get("width"), status.get("height")] != list(body.image_size_px):
            raise ValueError("Camera dimensions changed; the rehearsal was not accepted")
        return status

    async def capture(self, body):
        if self.runtime.record_lock.locked():
            raise ValueError("A camera capture is active; finish it before a rehearsal")
        async with self.runtime.record_lock:
            source = validate_saved_record(body.source.source_record)
            if not source["approved"]:
                raise ValueError("The historical mapping was not approved; no estimated rehearsal created")
            status = self._current_camera(body)
            if list(source["image_size_px"]) != list(body.image_size_px):
                raise ValueError("Historical and current image dimensions differ; no scaling is assumed")
            detect, detection = self.runtime.token_detection.detector(
                body.detector, body.reference_id, body.camera_session_id, list(body.image_size_px))
            tracker = SingleTokenTracker()  # Existing association limits remain unchanged.
            rehearsal_id = uid("rehearsal")
            folder = self.runtime.settings.data_dir / "estimated_rehearsals" / rehearsal_id
            folder.mkdir(parents=True)
            points, frames, frame_ids = [], [], []
            start, previous, previous_time = time.monotonic(), None, None
            saved = False
            try:
                while time.monotonic() - start < body.duration_s:
                    self._current_camera(body)
                    image, frame = self.runtime.camera.image()
                    if (frame["session_id"] != body.camera_session_id
                            or self.runtime.camera.session_id != body.camera_session_id):
                        raise ValueError("Camera session changed during rehearsal; capture discarded")
                    if [frame["width"], frame["height"]] != list(body.image_size_px):
                        raise ValueError("Camera dimensions changed during rehearsal; capture discarded")
                    if frame["sequence"] != previous:
                        previous = frame["sequence"]
                        received = frame["received_mono_s"]
                        if not math.isfinite(received):
                            raise ValueError("Camera timestamp is not finite; capture discarded")
                        if received < start:
                            await asyncio.sleep(1 / self.runtime.settings.camera_sample_hz)
                            continue
                        if previous_time is not None and received <= previous_time:
                            raise ValueError("Camera timestamps are not increasing; capture discarded")
                        previous_time = received
                        try:
                            found = detect(image)
                        except ViewObstructed:
                            found = None
                        # SceneChanged and other detector errors discard this rehearsal;
                        # hands/occlusions remain explicit gaps instead of invented points.
                        # Rename only the output copy: tracker.previous retains its
                        # internal centimetre fields for unchanged association logic.
                        tracked = dict(tracker.update(found if found is not None else [],
                                                      received - start, source))
                        if found is None:
                            tracked["reason"] = "VIEW_OBSTRUCTED"
                        estimated_x = tracked.pop("x_cm", None)
                        estimated_y = tracked.pop("y_cm", None)
                        frame_id = uid("rehearsal-frame")
                        path = folder / (frame_id + ".jpg")
                        path.write_bytes(frame["jpeg"])
                        point = {**tracked, "frame_id": frame_id}
                        if tracked["observed"]:
                            point.update(estimated_x_cm=estimated_x, estimated_y_cm=estimated_y)
                        points.append(point)
                        frames.append({"id": frame_id, "rehearsal_id": rehearsal_id,
                                       "camera_session_id": body.camera_session_id,
                                       "path": str(path), "sequence": frame["sequence"],
                                       "received_mono_s": received,
                                       "received_utc": frame["received_utc"]})
                        frame_ids.append(frame_id)
                    await asyncio.sleep(1 / self.runtime.settings.camera_sample_hz)
                self._current_camera(body)
                if not frames:
                    raise ValueError("Camera produced no new timestamped rehearsal frames")
                result = {
                    "id": rehearsal_id, "schema_version": "nemo_estimated_rehearsal_v1",
                    "data_origin": "LOCAL_CAPTURE_ESTIMATED_COORDINATES",
                    "validation_status": "UNVALIDATED", "validation_warning": WARNING,
                    "warnings": [WARNING],
                    "calibration_id": None, "profile_id": None, "case_id": None,
                    "source_calibration_id": source["calibration_id"],
                    "source_content_sha256": digest(source),
                    "source_camera_session_id": source["camera_session_id"],
                    "historical_max_error_cm": source["max_error_cm"],
                    "historical_tolerance_cm": source["max_allowed_error_cm"],
                    "current_alignment_verified": False, "approved_for_inference": False,
                    "camera_session_id": body.camera_session_id,
                    "image_size_px": list(body.image_size_px),
                    "capture_backend": status.get("backend"),
                    "timestamp_kind": "host_receipt_not_exposure",
                    "duration_s": body.duration_s, "recorded_at": time.time(),
                    "detection": detection, "points": points, "evidence_frame_ids": frame_ids,
                    "frames": len(frames), "observed": sum(p["observed"] for p in points),
                }
                for frame in frames:
                    self.runtime.store.put(FRAME_KIND, frame, frame["id"])
                result = self.runtime.store.put(KIND, result, rehearsal_id)
                saved = True
                return result
            finally:
                if not saved:
                    shutil.rmtree(folder)

    def get(self, rehearsal_id):
        # Only the summary and estimated points are public to the authenticated
        # local operator; private frame paths live in a different record kind.
        return self.runtime.store.get(KIND, rehearsal_id)
