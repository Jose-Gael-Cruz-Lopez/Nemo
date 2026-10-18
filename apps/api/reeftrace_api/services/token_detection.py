"""Empty-tank reference capture and token-size measurement for colour-independent tracking.

The operator explicitly captures a reference from the *current* camera session
(pump running, no token, hands out of view), then measures one token. Recording
can then ask for a detector bound to that reference. The reference arrays stay
private under the local data directory; only IDs and small metadata are returned.
A rig disturbance after capture makes the reference stale.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import OrderedDict

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
from apps.vision.reeftrace_vision.surface_token import (
    SURFACE_DETECTOR_ID,
    SURFACE_POLICY_ID,
    SURFACE_POLICY_SHA256,
    detect_surface_token,
    measure_surface_token_area,
    validate_detection_polygon,
)

REFERENCE_KIND = "token_reference"
TOKEN_SIZE_KIND = "token_size"
RED_DETECTOR = "red_hsv"
DETECTORS = (RED_DETECTOR, DETECTOR_ID, SURFACE_DETECTOR_ID)
REFERENCE_CACHE_SIZE = 2


class TokenDetectionService:
    def __init__(self, runtime):
        self.runtime = runtime
        self._cache = OrderedDict()

    def _remember_reference(self, reference_id, reference):
        self._cache[reference_id] = reference
        self._cache.move_to_end(reference_id)
        while len(self._cache) > REFERENCE_CACHE_SIZE:
            self._cache.popitem(last=False)

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

    async def capture_reference(self, frame_count=10, roi_polygon_px=None, token_size_from=None,
                                *, detector=DETECTOR_ID, detection_polygon_px=None):
        """Capture the empty tank; optionally carry a token size measured with an earlier reference.

        Within the same detector policy, a calm-water pixel size may be reused for
        a running-water reference: same camera session, image size and allowed
        camera creep. Generic foreground area and green-only area are different
        measurements and cannot be transferred between policies.
        """
        if self.runtime.record_lock.locked():
            raise ValueError("A camera capture is active; finish it before capturing a reference")
        if detector not in {DETECTOR_ID, SURFACE_DETECTOR_ID}:
            raise ValueError("Unsupported empty-tank detector")
        if detector == SURFACE_DETECTOR_ID:
            if roi_polygon_px is not None:
                raise ValueError("V2 uses a full-frame background and a separate detection polygon")
            status = self._fresh_session()
            validate_detection_polygon([status.get("width"), status.get("height")],
                                       detection_polygon_px)
        elif detection_polygon_px is not None:
            raise ValueError("A detection polygon requires the explicit foreground_surface_v2 detector")
        # asyncio.Lock acquires immediately while free: with no intervening await
        # after the check, another capture is rejected rather than queued.
        async with self.runtime.record_lock:
            result = await self._capture_reference(frame_count, roi_polygon_px, token_size_from,
                                                   source_detector=detector)
            if detector == SURFACE_DETECTOR_ID:
                surface = self.derive_surface_reference(result["reference_id"], detection_polygon_px)
                if token_size_from and self._token_size(surface["reference_id"]) is None:
                    self._carry_size(surface["reference_id"], surface["camera_session_id"],
                                     token_size_from, self._token_size(token_size_from), surface=True)
                return {**surface, "token_size": self._token_size(surface["reference_id"])}
            return result

    async def _capture_reference(self, frame_count, roi_polygon_px, token_size_from,
                                 *, source_detector=DETECTOR_ID):
        status = self._fresh_session()
        source = source_size = None
        if token_size_from:
            source, source_reference = self._reference(token_size_from)
            if source.get("detector", DETECTOR_ID) != source_detector:
                raise ValueError("Token pixel area cannot be carried between detector policies")
            self._check_current(source, status["session_id"])
            source_size = self._token_size(token_size_from)
            if source_size is None:
                raise ValueError("Measure one token with the earlier reference before carrying its size over")
            if source_detector == SURFACE_DETECTOR_ID:
                self._check_surface_size(source_size)
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
        self._remember_reference(reference_id, reference)
        record = {**reference.describe(), "reference_id": reference_id,
                  "content_id": reference.fingerprint, "camera_session_id": status["session_id"],
                  "captured_at": time.time(), "rig_change_at_capture": self._latest_rig_change()}
        try:
            saved = self.runtime.store.put(REFERENCE_KIND, record, reference_id)
        except ValueError:  # Identical content from the same session: reuse the saved record.
            saved = self.runtime.store.get(REFERENCE_KIND, reference_id)
        if (source_size is not None and source_detector == DETECTOR_ID
                and self._token_size(reference_id) is None):
            self._carry_size(reference_id, status["session_id"], token_size_from, source_size)
        size = self._token_size(reference_id)
        return {**saved, "token_size": size}

    def _reference(self, reference_id):
        record = self.runtime.store.get(REFERENCE_KIND, reference_id)
        if reference_id not in self._cache:
            path = self._folder / f"{reference_id}.npz"
            if not path.exists():
                raise ValueError("Saved empty-tank reference data is missing; capture a new one")
            with np.load(path) as arrays:
                self._remember_reference(reference_id, EmptyTankReference.from_arrays(
                    arrays, expected_id=record["content_id"]))
        else:
            self._cache.move_to_end(reference_id)
        reference = self._cache[reference_id]
        if record.get("detector") == SURFACE_DETECTOR_ID:
            polygon = validate_detection_polygon(reference.shape[::-1], record.get("detection_polygon_px"))
            if (record.get("policy_id") != SURFACE_POLICY_ID
                    or record.get("policy_sha256") != SURFACE_POLICY_SHA256
                    or reference.fingerprint != record.get("content_id")
                    or not reference.roi.all()
                    or record.get("image_size_px") != list(reference.shape[::-1])
                    or self._surface_reference_id(record["content_id"], record["camera_session_id"],
                                                 record.get("derived_from_reference_id"), polygon)
                    != reference_id):
                raise ValueError("Saved surface reference no longer matches its frozen policy and polygon")
        return record, reference

    @staticmethod
    def _surface_reference_id(content_id, session_id, source_id, polygon):
        body = {"content_id": content_id, "camera_session_id": session_id,
                "derived_from_reference_id": source_id, "detection_polygon_px": polygon,
                "policy_id": SURFACE_POLICY_ID, "policy_sha256": SURFACE_POLICY_SHA256}
        return "refsurf-" + hashlib.sha256(json.dumps(
            body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()[:16]

    def derive_surface_reference(self, reference_id, detection_polygon_px):
        """Derive immutable candidate admission from SAVED arrays; no camera access.

        Session, capture time and background stay historical. A later detector
        call must independently pass normal current-session/reference gates.
        """
        source, reference = self._reference(reference_id)
        if (reference.fingerprint != source.get("content_id")
                or source.get("image_size_px") != list(reference.shape[::-1])):
            raise ValueError("Saved background metadata does not match its immutable arrays")
        polygon = validate_detection_polygon(reference.shape[::-1], detection_polygon_px)
        if not reference.roi.all():
            raise ValueError("V2 requires an existing full-frame background; its gain ROI cannot be changed")
        new_id = self._surface_reference_id(source["content_id"], source["camera_session_id"],
                                           reference_id, polygon)
        try:
            saved, _ = self._reference(new_id)
            return {**saved, "token_size": self._token_size(new_id)}
        except KeyError:
            pass
        record = {key: value for key, value in source.items() if key != "id"}
        record.update(detector=SURFACE_DETECTOR_ID, reference_id=new_id,
                      detection_polygon_px=polygon, policy_id=SURFACE_POLICY_ID,
                      policy_sha256=SURFACE_POLICY_SHA256,
                      derived_from_reference_id=reference_id, derived_at=time.time())
        np.savez_compressed(self._folder / f"{new_id}.npz", **reference.to_arrays())
        self._remember_reference(new_id, reference)
        saved = self.runtime.store.put(REFERENCE_KIND, record, new_id)
        size = self._token_size(reference_id)
        # Green-only segmented area and generic foreground area are different
        # measurements. A v1 size must never approve the new colour policy.
        if size is not None and source.get("detector") == SURFACE_DETECTOR_ID:
            self._check_surface_size(size)
            self._carry_size(new_id, source["camera_session_id"], reference_id, size, surface=True)
        return {**saved, "token_size": self._token_size(new_id)}

    @staticmethod
    def _check_surface_size(size):
        if (size.get("policy_id") != SURFACE_POLICY_ID
                or size.get("policy_sha256") != SURFACE_POLICY_SHA256):
            raise ValueError("Green-cap pixel area belongs to another detector policy; measure it again")

    def _carry_size(self, reference_id, session_id, source_id, size, *, surface=False):
        record = {"reference_id": reference_id, "camera_session_id": session_id,
                  "token_area_px": size["token_area_px"],
                  "token_area_px_range": size["token_area_px_range"],
                  "measured_at": size["measured_at"], "carried_from_reference_id": source_id}
        if surface:
            record.update(policy_id=SURFACE_POLICY_ID, policy_sha256=SURFACE_POLICY_SHA256)
        return self.runtime.store.put(TOKEN_SIZE_KIND, record)

    def _check_current(self, record, session_id):
        if record["camera_session_id"] != session_id:
            raise ValueError("The empty-tank reference belongs to another camera session; capture a new one")
        changed = self._latest_rig_change()
        if changed is not None and changed > record["captured_at"]:
            raise ValueError("The rig changed after the empty-tank reference; capture a new one")

    async def measure_token(self, reference_id):
        if self.runtime.record_lock.locked():
            raise ValueError("A camera capture is active; finish it before measuring a token")
        async with self.runtime.record_lock:
            return await self._measure_token(reference_id)

    async def _measure_token(self, reference_id):
        status = self._fresh_session()
        record, reference = self._reference(reference_id)
        self._check_current(record, status["session_id"])
        frame = (await self._frames(1, status["session_id"]))[0]
        area = (measure_surface_token_area(frame, reference, record["detection_polygon_px"])
                if record.get("detector") == SURFACE_DETECTOR_ID
                else measure_token_area(frame, reference))
        low, high = token_area_range(area)
        size = {
            "reference_id": reference_id, "camera_session_id": status["session_id"],
            "token_area_px": round(float(area), 1),
            "token_area_px_range": [round(low, 1), round(high, 1)], "measured_at": time.time()}
        if record.get("detector") == SURFACE_DETECTOR_ID:
            size.update(policy_id=SURFACE_POLICY_ID, policy_sha256=SURFACE_POLICY_SHA256)
        return self.runtime.store.put(TOKEN_SIZE_KIND, size)

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
        if name not in {DETECTOR_ID, SURFACE_DETECTOR_ID}:
            raise ValueError("Unsupported token detector")
        if not reference_id:
            raise ValueError("Capture an empty-tank reference and pass its reference_id")
        record, reference = self._reference(reference_id)
        if record.get("detector", DETECTOR_ID) != name:
            raise ValueError("Detector does not match the frozen reference version")
        self._check_current(record, session_id)
        if list(record["image_size_px"]) != list(image_size_px or []):
            raise ValueError("The empty-tank reference and the mapping use different image sizes")
        size = self._token_size(reference_id)
        if size is None:
            raise ValueError("Measure one token with this reference before recording")
        area_range = tuple(size["token_area_px_range"])
        if name == SURFACE_DETECTOR_ID:
            self._check_surface_size(size)
            metadata = {"detector": SURFACE_DETECTOR_ID, "reference_id": reference_id,
                        "token_area_px_range": list(area_range),
                        "detection_polygon_px": record["detection_polygon_px"],
                        "policy_id": SURFACE_POLICY_ID, "policy_sha256": SURFACE_POLICY_SHA256}
            return (lambda image: detect_surface_token(
                image, reference, record["detection_polygon_px"], area_px_range=area_range), metadata)
        return (lambda image: detect_foreground(image, reference, area_px_range=area_range),
                {"detector": DETECTOR_ID, "reference_id": reference_id,
                 "token_area_px_range": list(area_range)})
