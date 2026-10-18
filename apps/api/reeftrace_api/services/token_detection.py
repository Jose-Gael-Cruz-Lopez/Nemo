"""Empty-tank reference capture and token-size measurement for colour-independent tracking.

The operator explicitly captures a reference from the *current* camera session
(pump running, no token, hands out of view), then measures one token. Recording
can then ask for a detector bound to that reference. The reference arrays stay
private under the local data directory; only IDs and small metadata are returned.
A rig disturbance after capture makes the reference stale.
"""
from __future__ import annotations

import asyncio
import time

import cv2
import numpy as np

from apps.vision.reeftrace_vision.foreground import (
    DETECTOR_ID,
    MAX_ALIGN_SHIFT_PX,
    MIN_SHIFT_CONFIDENCE,
    EmptyTankReference,
    detect_foreground,
    measure_token_area,
    token_area_range,
)

REFERENCE_KIND = "token_reference"
TOKEN_SIZE_KIND = "token_size"
RED_DETECTOR = "red_hsv"
DETECTORS = (RED_DETECTOR, DETECTOR_ID)


class TokenDetectionService:
    def __init__(self, runtime):
        self.runtime = runtime
        self._cache = {}

    @property
    def _folder(self):
        folder = self.runtime.settings.data_dir / "token_references"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _fresh_session(self):
        status = self.runtime.camera.status()
        if not status.get("fresh") or not status.get("session_id"):
            raise ValueError("Start the webcam and wait for fresh frames first")
        return status

    def _latest_rig_change(self):
        changes = self.runtime.store.list("rig_change", 1)
        return changes[0]["changed_at"] if changes else None

    async def _frames(self, count, session_id):
        """Distinct fresh frames from one unchanged session, at the recording sample rate."""
        frames, previous, deadline = [], None, time.monotonic() + 30
        while len(frames) < count:
            if time.monotonic() > deadline:
                raise ValueError("Camera did not deliver enough fresh frames")
            image, frame = self.runtime.camera.image()
            if frame["session_id"] != session_id or self.runtime.camera.session_id != session_id:
                raise ValueError("Camera restarted during capture; nothing was saved")
            if frame["sequence"] != previous:
                previous = frame["sequence"]
                frames.append(image)
            await asyncio.sleep(1 / self.runtime.settings.camera_sample_hz)
        return frames

    async def capture_reference(self, frame_count=10, roi_polygon_px=None, token_size_from=None):
        """Capture the empty tank; optionally carry a token size measured with an earlier reference.

        A token's apparent size depends on the camera, not on whether the water is moving,
        so a size measured with a calm (pump off) reference may be reused for a running
        (pump on) one: same camera session, same image size, and the two references must
        show the camera within the allowed creep of each other.
        """
        if self.runtime.record_lock.locked():
            raise ValueError("A recording is active; capture the reference before recording")
        status = self._fresh_session()
        source = source_size = None
        if token_size_from:
            source, source_reference = self._reference(token_size_from)
            self._check_current(source, status["session_id"])
            source_size = self._token_size(token_size_from)
            if source_size is None:
                raise ValueError("Measure one token with the earlier reference before carrying its size over")
        frames = await self._frames(frame_count, status["session_id"])
        reference = EmptyTankReference(frames, roi_polygon_px=roi_polygon_px)
        if source is not None:
            if list(source["image_size_px"]) != [reference.shape[1], reference.shape[0]]:
                raise ValueError("The earlier reference used a different image size")
            (dx, dy), confidence = cv2.phaseCorrelate(source_reference.gray.copy(), reference.gray.copy(),
                                                      source_reference._window)
            if confidence >= MIN_SHIFT_CONFIDENCE and np.hypot(dx, dy) > MAX_ALIGN_SHIFT_PX:
                raise ValueError("The camera moved between the two empty-tank captures; measure the token again")
        reference_id = reference.fingerprint + "-" + status["session_id"][-8:]
        path = self._folder / f"{reference_id}.npz"
        np.savez_compressed(path, **reference.to_arrays())
        self._cache[reference_id] = reference
        record = {**reference.describe(), "reference_id": reference_id,
                  "content_id": reference.fingerprint, "camera_session_id": status["session_id"],
                  "captured_at": time.time(), "rig_change_at_capture": self._latest_rig_change()}
        try:
            saved = self.runtime.store.put(REFERENCE_KIND, record, reference_id)
        except ValueError:  # Identical content from the same session: reuse the saved record.
            saved = self.runtime.store.get(REFERENCE_KIND, reference_id)
        if source_size is not None and self._token_size(reference_id) is None:
            self.runtime.store.put(TOKEN_SIZE_KIND, {
                "reference_id": reference_id, "camera_session_id": status["session_id"],
                "token_area_px": source_size["token_area_px"],
                "token_area_px_range": source_size["token_area_px_range"],
                "measured_at": source_size["measured_at"], "carried_from_reference_id": token_size_from})
        size = self._token_size(reference_id)
        return {**saved, "token_size": size}

    def _reference(self, reference_id):
        record = self.runtime.store.get(REFERENCE_KIND, reference_id)
        if reference_id not in self._cache:
            path = self._folder / f"{reference_id}.npz"
            if not path.exists():
                raise ValueError("Saved empty-tank reference data is missing; capture a new one")
            with np.load(path) as arrays:
                self._cache[reference_id] = EmptyTankReference.from_arrays(
                    arrays, expected_id=record["content_id"])
        return record, self._cache[reference_id]

    def _check_current(self, record, session_id):
        if record["camera_session_id"] != session_id:
            raise ValueError("The empty-tank reference belongs to another camera session; capture a new one")
        changed = self._latest_rig_change()
        if changed is not None and changed > record["captured_at"]:
            raise ValueError("The rig changed after the empty-tank reference; capture a new one")

    async def measure_token(self, reference_id):
        status = self._fresh_session()
        record, reference = self._reference(reference_id)
        self._check_current(record, status["session_id"])
        frame = (await self._frames(1, status["session_id"]))[0]
        area = measure_token_area(frame, reference)
        low, high = token_area_range(area)
        return self.runtime.store.put(TOKEN_SIZE_KIND, {
            "reference_id": reference_id, "camera_session_id": status["session_id"],
            "token_area_px": round(float(area), 1),
            "token_area_px_range": [round(low, 1), round(high, 1)], "measured_at": time.time()})

    def _token_size(self, reference_id):
        for item in self.runtime.store.list(TOKEN_SIZE_KIND, 100):
            if item["reference_id"] == reference_id:
                return item
        return None

    def status(self):
        references = self.runtime.store.list(REFERENCE_KIND, 1)
        if not references:
            return {"reference": None, "token_size": None, "is_current": False,
                    "reason": "No empty-tank reference captured yet"}
        record = references[0]
        reason = None
        try:
            self._check_current(record, self.runtime.camera.session_id)
        except ValueError as error:
            reason = str(error)
        size = self._token_size(record["reference_id"])
        if reason is None and size is None:
            reason = "Measure one token with this reference"
        return {"reference": record, "token_size": size, "is_current": reason is None, "reason": reason}

    def detector(self, name, reference_id, session_id, image_size_px):
        """Return ``(detect(image) -> detections, provenance)`` for a recording."""
        if name == RED_DETECTOR:
            if reference_id:
                raise ValueError("The red detector does not use an empty-tank reference")
            from apps.vision.reeftrace_vision.tracking import detect_red
            return detect_red, {"detector": RED_DETECTOR}
        if name != DETECTOR_ID:
            raise ValueError("Unsupported token detector")
        if not reference_id:
            raise ValueError("Capture an empty-tank reference and pass its reference_id")
        record, reference = self._reference(reference_id)
        self._check_current(record, session_id)
        if list(record["image_size_px"]) != list(image_size_px or []):
            raise ValueError("The empty-tank reference and the mapping use different image sizes")
        size = self._token_size(reference_id)
        if size is None:
            raise ValueError("Measure one token with this reference before recording")
        area_range = tuple(size["token_area_px_range"])
        return (lambda image: detect_foreground(image, reference, area_px_range=area_range),
                {"detector": DETECTOR_ID, "reference_id": reference_id,
                 "token_area_px_range": list(area_range)})
