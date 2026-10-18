"""Session-bound live display using historical setup, never measured evidence."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
import threading
import time
from collections import OrderedDict

import cv2
import numpy as np

from apps.vision.reeftrace_vision.calibration import project
from apps.vision.reeftrace_vision.foreground import (
    MIN_SHIFT_CONFIDENCE,
    SceneChanged,
    ViewObstructed,
)
from apps.vision.reeftrace_vision.surface_token import (
    surface_policy,
    surface_token_diagnostic,
    validate_detection_polygon,
)

from .detector_replay import DetectorReplayService
from .field_sessions import digest
from .saved_calibrations import validate_saved_record
from .store import uid

WARNING = (
    "Live display only: saved background and historical mapping may belong to another camera pose. "
    "Green-cap pixels are observed; centimetres are approximate. Historical calibration error "
    "is not current accuracy. No token-size, calibration, recording, flow, source or trial "
    "evidence is approved or saved."
)
MAX_PREVIEWS = 2
PREVIEW_LIFETIME_S = 1800
MAX_JPEG_BYTES = 640_000
MARKER_MODE = "saved_green_marker_preview_v1"
_MARKER_POLICY = {
    "policy_id": MARKER_MODE, "detector": MARKER_MODE,
    "segmentation": "direct_green_hsv_without_background_subtraction",
    "green_hsv_lower": [35, 80, 40], "green_hsv_upper": [85, 255, 255],
    "maximum_aspect_ratio": 2.0, "minimum_circularity": 0.45, "minimum_solidity": 0.75,
    "open_kernel_px": 3, "close_kernel_px": 5,
    "area_lower_multiplier": 0.35, "area_upper_multiplier": 3.0,
    "orb_features": 1500, "match_ratio": 0.75, "minimum_inliers": 15,
    "minimum_inlier_fraction": 0.5, "maximum_residual_px": 3.0,
    "maximum_translation_px": 64.0,
    "registration": "bounded_translation_image_estimate_not_water_plane_validation",
}


def marker_policy():
    policy = copy.deepcopy(_MARKER_POLICY)
    policy["policy_sha256"] = hashlib.sha256(json.dumps(
        policy, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return policy


class DetectorPreviewService:
    def __init__(self, runtime):
        self.runtime = runtime
        self._previews = OrderedDict()
        self._state_lock = threading.Lock()
        self._processing_lock = threading.Lock()

    def references(self):
        summaries = []
        for record in self.runtime.store.list("token_reference", 100):
            try:
                saved, reference = self.runtime.token_detection._reference(record["id"])
            except (KeyError, ValueError, FileNotFoundError):
                continue
            if not reference.roi.all():
                continue
            item = {"reference_id": saved["reference_id"],
                    "camera_session_id": saved["camera_session_id"],
                    "image_size_px": saved["image_size_px"], "captured_at": saved["captured_at"],
                    "detector": saved["detector"], "full_frame": True}
            for key in ("policy_id", "policy_sha256"):
                if key in saved:
                    item[key] = saved[key]
            summaries.append(item)
            if len(summaries) >= 20:
                break
        return {"references": summaries}

    def _current(self, session_id=None, dimensions=None):
        status = self.runtime.camera.status()
        if not status.get("running") or not status.get("fresh") or not status.get("session_id"):
            raise ValueError("The local camera is stopped, unavailable or stale; preview has no fresh frame")
        if session_id is not None and status["session_id"] != session_id:
            raise ValueError("Camera session changed; enable a new display-only preview")
        if dimensions is not None and [status.get("width"), status.get("height")] != dimensions:
            raise ValueError("Camera dimensions changed; preview was not accepted")
        return status

    def configure(self, body):
        source = copy.deepcopy(validate_saved_record(body.source.source_record))
        if not source["approved"]:
            raise ValueError("The historical mapping was not approved; it cannot seed this preview")
        saved, reference = self.runtime.token_detection._reference(body.reference_id)
        dimensions = list(source["image_size_px"])
        if list(saved["image_size_px"]) != dimensions or list(reference.shape[::-1]) != dimensions:
            raise ValueError("Saved mapping and background dimensions differ; no scaling is assumed")
        if not reference.roi.all():
            raise ValueError("Live green preview requires a saved full-frame background")
        polygon = validate_detection_polygon(dimensions, body.detection_polygon_px)
        status = self._current(dimensions=dimensions)
        mode = getattr(body, "detector_mode", "foreground_surface_v2")
        marker_area = self._marker_area_source(dimensions) if mode == MARKER_MODE else None
        config = {
            "schema_version": "nemo_detector_preview_config_v1", "preview_id": uid("detector-preview"),
            "camera_session_id": status["session_id"], "image_size_px": dimensions,
            "reference_id": body.reference_id, "reference_camera_session_id": saved["camera_session_id"],
            "source_calibration_id": source["calibration_id"], "source_content_sha256": digest(source),
            "source_camera_session_id": source["camera_session_id"],
            "homography_image_to_cm": source["homography_image_to_cm"],
            "detection_polygon_px": polygon, "detector_mode": mode,
            "policy": marker_policy() if mode == MARKER_MODE else surface_policy(),
            "marker_area_source": marker_area,
            "data_origin": "LOCAL_LIVE_DISPLAY_ESTIMATED_COORDINATES",
            "validation_status": "UNVALIDATED", "current_alignment_verified": False,
            "approved_for_inference": False, "measured_flow_eligible": False,
            "calibration_id": None, "profile_id": None, "case_id": None, "warnings": [WARNING],
        }
        if mode == MARKER_MODE:
            config["warnings"].append(
                "Marker preview uses green colour and shape, without foreground subtraction. "
                "Its area bounds come from saved development footage, not a new physical size check. "
                "Image registration is approximate and cannot validate the historical water-plane map."
            )
        self._current(status["session_id"], dimensions)
        with self._state_lock:
            self._previews[config["preview_id"]] = {
                "config": config, "reference": reference, "created_at": time.monotonic(),
                "latest": None, "latest_jpeg": None,
            }
            while len(self._previews) > MAX_PREVIEWS:
                self._previews.popitem(last=False)
        return copy.deepcopy(config)

    def _marker_area_source(self, dimensions):
        report = DetectorReplayService(self.runtime).latest()
        if (report.get("data_origin") != "LOCAL_SAVED_FOOTAGE_REPLAY"
                or report.get("purpose") != "DEVELOPMENT_REGRESSION"
                or report.get("validation_status") != "UNVALIDATED"
                or report.get("measured_flow_eligible") is not False):
            raise ValueError("Marker preview requires a current-policy saved development replay")
        for clip in report.get("clips", [])[:10]:
            if clip.get("image_size_px") != dimensions:
                continue
            for index, point in enumerate(clip.get("points", [])[:300]):
                area = point.get("area_px")
                if (point.get("observed") is True and type(area) in (int, float)
                        and math.isfinite(area) and 25 <= area <= np.prod(dimensions) * .2):
                    return {"report_id": report["report_id"], "clip_id": clip["id"],
                            "point_index": index, "area_px": area,
                            "area_px_range": [.35 * area, 3.0 * area],
                            "source_policy_sha256": report["policy"]["sha256"]}
        raise ValueError("No same-size green marker observation exists in the current saved replay")

    def get(self, preview_id):
        if not self._processing_lock.acquire(blocking=False):
            raise ValueError("A detector preview is already processing; wait for its current frame")
        try:
            return self._get(preview_id)
        finally:
            self._processing_lock.release()

    def _get(self, preview_id):
        with self._state_lock:
            state = self._previews[preview_id]
            if time.monotonic() - state["created_at"] > PREVIEW_LIFETIME_S:
                del self._previews[preview_id]
                raise ValueError("Display-only preview expired; enable it again")
            config = state["config"]
        if self.runtime.record_lock.locked():
            raise ValueError("A camera recording is active; live detector display is paused")
        self._current(config["camera_session_id"], config["image_size_px"])
        # Reads only the already running camera's latest buffer; never starts a
        # device, waits for a new capture, writes an image or changes rig state.
        image, frame = self.runtime.camera.image()
        self._validate_frame(config, image, frame)
        previous = state["latest"]
        if previous is not None and (frame["sequence"] < previous["sequence"]
                or frame["received_mono_s"] < previous["received_mono_s"]):
            raise ValueError("Camera preview sequence or timestamp moved backwards")
        if previous is not None and frame["sequence"] == previous["sequence"]:
            if (frame["received_mono_s"] != previous["received_mono_s"]
                    or frame["jpeg"] != state["latest_jpeg"]):
                raise ValueError("A repeated camera sequence changed its timestamp or image")
            result = copy.deepcopy(state["latest"])
            result["age_s"] = time.monotonic() - frame["received_mono_s"]
            self._current(config["camera_session_id"], config["image_size_px"])
            return result
        found, diagnostics, alignment = [], None, None
        reason = rejection = None
        foreground_status, foreground_rejection, alignment_rejection = "OK", None, None
        try:
            report = surface_token_diagnostic(image, state["reference"], config["detection_polygon_px"])
        except ViewObstructed as error:
            foreground_status, foreground_rejection = "VIEW_OBSTRUCTED", str(error)[:240]
        except SceneChanged as error:
            foreground_status, foreground_rejection = "SCENE_CHANGED", str(error)[:240]
        if config["detector_mode"] == MARKER_MODE:
            alignment, alignment_rejection = self._marker_alignment(image, state["reference"])
            found, diagnostics = self._marker_detections(image, config, alignment)
        elif foreground_status == "OK":
            alignment = self._alignment(image, state["reference"])
            found = [self._display_detection(detection, alignment) for detection in report["detections"]]
            diagnostics = {key: report["diagnostics"][key] for key in (
                "candidate_count", "accepted_count", "rejected_count", "rejection_counts")}
        else:
            reason, rejection = foreground_status, foreground_rejection
        if reason is None:
            reason = "NO_TOKEN" if not found else "MULTIPLE_TOKENS" if len(found) > 1 else None
        point = None
        if len(found) == 1:
            candidate = found[0]
            if alignment is not None:
                x_cm, y_cm = project(config["homography_image_to_cm"], [[
                    candidate["reference_pixel_x"], candidate["reference_pixel_y"]]])[0]
                point = {**candidate, "estimated_x_cm": float(x_cm), "estimated_y_cm": float(y_cm)}
            else:
                point = {**candidate, "estimated_x_cm": None, "estimated_y_cm": None}
        self._current(config["camera_session_id"], config["image_size_px"])
        self._validate_frame(config, image, frame)
        result = {
            "schema_version": "nemo_detector_preview_frame_v1", "preview_id": preview_id,
            "camera_session_id": config["camera_session_id"], "image_size_px": config["image_size_px"],
            "sequence": frame["sequence"], "received_utc": frame["received_utc"],
            "received_mono_s": frame["received_mono_s"],
            "age_s": time.monotonic() - frame["received_mono_s"],
            "timestamp_kind": "host_receipt_not_exposure",
            "jpeg_data_url": "data:image/jpeg;base64," + base64.b64encode(frame["jpeg"]).decode(),
            "observed": point is not None, "reason": reason, "scene_rejection": rejection,
            "detector_mode": config["detector_mode"],
            "saved_foreground_status": foreground_status,
            "saved_foreground_rejection": foreground_rejection,
            "alignment_rejection": alignment_rejection,
            "alignment": alignment, "point": point, "detections": found, "diagnostics": diagnostics,
            "data_origin": config["data_origin"], "validation_status": "UNVALIDATED",
            "approved_for_inference": False, "measured_flow_eligible": False,
            "calibration_id": None, "profile_id": None, "case_id": None,
        }
        state["latest"] = result
        state["latest_jpeg"] = frame["jpeg"]
        return copy.deepcopy(result)

    def _validate_frame(self, config, image, frame):
        if (frame.get("session_id") != config["camera_session_id"]
                or self.runtime.camera.session_id != config["camera_session_id"]):
            raise ValueError("Camera session changed during detector display")
        if ([frame.get("width"), frame.get("height")] != config["image_size_px"]
                or list(image.shape[1::-1]) != config["image_size_px"]):
            raise ValueError("Camera frame dimensions changed during detector display")
        received, sequence = frame.get("received_mono_s"), frame.get("sequence")
        if (type(received) not in (int, float) or not math.isfinite(received)
                or type(sequence) is not int or sequence < 1):
            raise ValueError("Camera frame needs a finite timestamp and positive sequence")
        age = time.monotonic() - received
        if not 0 <= age <= min(getattr(self.runtime.camera, "stale_s", 2.0), 2.0):
            raise ValueError("The exact preview frame is stale; no detector position is shown")
        jpeg = frame.get("jpeg")
        if (not isinstance(jpeg, bytes) or not 4 <= len(jpeg) <= MAX_JPEG_BYTES
                or not jpeg.startswith(b"\xff\xd8") or not jpeg.endswith(b"\xff\xd9")):
            raise ValueError("The exact preview JPEG is invalid or exceeds its display bound")

    @staticmethod
    def _alignment(image, reference):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
        (dx, dy), confidence = cv2.phaseCorrelate(reference.gray.copy(), gray.copy(), reference._window)
        shift = float(np.hypot(dx, dy)) if confidence >= MIN_SHIFT_CONFIDENCE else 0.0
        applied = math.isfinite(shift) and shift > 0.5
        return {"method": "foreground_phase_translation_v1",
                "applied": applied, "dx_px": float(dx) if applied else 0.0,
                "dy_px": float(dy) if applied else 0.0,
                "confidence": float(confidence) if math.isfinite(confidence) else 0.0}

    @staticmethod
    def _marker_alignment(image, reference):
        """A bounded global image translation; never a physical calibration check."""
        orb = cv2.ORB_create(nfeatures=1500)
        saved = np.clip(reference.gray, 0, 255).astype(np.uint8)
        current = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        key_a, descriptors_a = orb.detectAndCompute(saved, None)
        key_b, descriptors_b = orb.detectAndCompute(current, None)
        if descriptors_a is None or descriptors_b is None or len(descriptors_b) < 2:
            return None, "Not enough image features for an estimated translation"
        matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(descriptors_a, descriptors_b, k=2)
        good = [pair[0] for pair in matches if len(pair) == 2 and pair[0].distance < .75 * pair[1].distance]
        if len(good) < 15:
            return None, "Fewer than 15 matched image features; centimetres and grid withheld"
        delta = np.asarray([np.subtract(key_b[match.trainIdx].pt, key_a[match.queryIdx].pt)
                            for match in good], float)
        translation = np.median(delta, axis=0)
        for _ in range(2):
            inliers = np.linalg.norm(delta - translation, axis=1) <= 3.0
            if inliers.sum() < 15:
                return None, "Fewer than 15 translation inliers; centimetres and grid withheld"
            translation = np.median(delta[inliers], axis=0)
        residuals = np.linalg.norm(delta - translation, axis=1)
        inliers = residuals <= 3.0
        fraction = float(inliers.mean())
        if inliers.sum() < 15 or fraction < .5:
            return None, "Image matches do not support one translation; centimetres and grid withheld"
        residual = float(np.sqrt(np.mean(residuals[inliers] ** 2)))
        if not np.isfinite(translation).all() or np.linalg.norm(translation) > 64 or residual > 3:
            return None, "Estimated translation exceeds its fixed display-only bound"
        applied = bool(np.linalg.norm(translation) > .5)
        return {"method": "orb_translation_estimate_v1", "applied": applied,
                "dx_px": float(translation[0]) if applied else 0.0,
                "dy_px": float(translation[1]) if applied else 0.0, "confidence": fraction,
                "match_count": len(good), "inlier_count": int(inliers.sum()),
                "residual_px": residual}, None

    @staticmethod
    def _marker_detections(image, config, alignment):
        from collections import Counter

        green = cv2.inRange(cv2.cvtColor(image, cv2.COLOR_BGR2HSV),
                           np.array([35, 80, 40], np.uint8), np.array([85, 255, 255], np.uint8))
        green = cv2.morphologyEx(green, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        green = cv2.morphologyEx(green, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        dx, dy = (alignment["dx_px"], alignment["dy_px"]) if alignment else (0.0, 0.0)
        domain = np.zeros(image.shape[:2], np.uint8)
        polygon = np.asarray(config["detection_polygon_px"], float) + [dx, dy]
        # Internally translated historical geometry may extend off the frame;
        # rasterization clips only the display domain, never candidate contours.
        cv2.fillPoly(domain, [np.round(polygon).astype(np.int32)], 1)
        contours, _ = cv2.findContours(green, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        low, high = config["marker_area_source"]["area_px_range"]
        found, reasons, candidates = [], Counter(), 0
        for contour in contours:
            area = float(cv2.contourArea(contour))
            moments = cv2.moments(contour)
            if area <= 0 or moments["m00"] <= 0:
                continue
            candidates += 1
            x, y, width, height = cv2.boundingRect(contour)
            perimeter = float(cv2.arcLength(contour, True))
            hull = float(cv2.contourArea(cv2.convexHull(contour)))
            rejected = []
            if not domain[y:y + height, x:x + width].all():
                rejected.append("OUTSIDE_DETECTION_POLYGON")
            if not low <= area <= high:
                rejected.append("AREA_OUT_OF_RANGE")
            if max(width, height) / min(width, height) > 2:
                rejected.append("ELONGATED_COMPONENT")
            if not perimeter or 4 * np.pi * area / perimeter ** 2 < .45:
                rejected.append("WEAK_CIRCULARITY")
            if not hull or area / hull < .75:
                rejected.append("LOW_SOLIDITY")
            reasons.update(rejected)
            if rejected:
                continue
            pixel_x, pixel_y = float(moments["m10"] / moments["m00"]), float(moments["m01"] / moments["m00"])
            found.append({"pixel_x": pixel_x, "pixel_y": pixel_y,
                          "reference_pixel_x": pixel_x - dx if alignment else None,
                          "reference_pixel_y": pixel_y - dy if alignment else None,
                          "area_px": area, "bbox_px": [x, y, width, height]})
        return found, {"candidate_count": candidates, "accepted_count": len(found),
                       "rejected_count": candidates - len(found), "rejection_counts": dict(reasons)}

    @staticmethod
    def _display_detection(detection, alignment):
        dx, dy = alignment["dx_px"], alignment["dy_px"]
        x, y, width, height = detection["bbox_px"]
        return {"pixel_x": detection["pixel_x"] + dx, "pixel_y": detection["pixel_y"] + dy,
                "reference_pixel_x": detection["pixel_x"], "reference_pixel_y": detection["pixel_y"],
                "area_px": detection["area_px"], "bbox_px": [x + dx, y + dy, width, height]}
