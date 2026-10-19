"""One standardized red floating token; ambiguity/misses are explicit gaps."""
import uuid

import cv2
import numpy as np

from .calibration import project


def detect_red(frame, *, min_area_px=25, max_area_fraction=0.05):
    if frame is None or frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("Expected a BGR camera image")
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 100, 70), (10, 255, 255))
    mask |= cv2.inRange(hsv, (170, 100, 70), (179, 255, 255))
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    detections = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if not min_area_px <= area <= frame.shape[0] * frame.shape[1] * max_area_fraction:
            continue
        moments = cv2.moments(contour)
        if moments["m00"] <= 0:
            continue
        x, y = moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]
        detections.append({"pixel_x": float(x), "pixel_y": float(y),
                           "area_px": float(area), "bbox_px": list(cv2.boundingRect(contour))})
    return detections


def in_polygon(point, polygon):
    return cv2.pointPolygonTest(np.asarray(polygon, np.float32), tuple(map(float, point)), False) >= 0


class SingleTokenTracker:
    def __init__(self, *, max_gap_s=0.5, max_speed_cm_s=20):
        self.max_gap_s = max_gap_s
        self.max_speed = max_speed_cm_s
        self.previous = None
        self.track_id = None
        self.calibration_id = None

    def update(self, detections, t_s, calibration):
        # A mapping version break is a track break, never a relabelled old point.
        identity = calibration.get("calibration_id")
        if identity != self.calibration_id:
            self.previous = None
            self.track_id = None
            self.calibration_id = identity
        if len(detections) != 1:
            self.previous = None
            self.track_id = None
            return {"observed": False, "t_s": t_s,
                    "reason": "NO_DETECTION" if not detections else "MULTIPLE_TOKENS"}
        d = detections[0]
        xy = project(calibration["homography_image_to_cm"], [[d["pixel_x"], d["pixel_y"]]])[0]
        point = {**d, "t_s": t_s, "x_cm": xy[0], "y_cm": xy[1], "observed": True,
                 "quality": 1.0}
        broken = self.previous is None
        reason = None
        if self.previous is not None:
            dt = t_s - self.previous["t_s"]
            distance = np.hypot(xy[0] - self.previous["x_cm"], xy[1] - self.previous["y_cm"])
            if dt <= 0 or dt > self.max_gap_s or distance > self.max_speed * dt:
                broken, reason = True, "ASSOCIATION_GAP"
        if broken:
            self.track_id = "track-" + uuid.uuid4().hex[:12]
        point.update(track_id=self.track_id, association_break=broken, reason=reason)
        self.previous = point
        return point


def flow_samples(track, *, min_dt_s=0.1, max_dt_s=0.5):
    """Nonoverlapping position differences, not velocity as extra inference evidence."""
    samples, start = [], None
    for p in track:
        if not p.get("observed"):
            start = None
            continue
        if start is None:
            start = p
            continue
        dt = p["t_s"] - start["t_s"]
        if p.get("track_id") != start.get("track_id") or dt > max_dt_s or dt <= 0:
            start = p
            continue
        if dt < min_dt_s:
            continue
        samples.append({"x_cm": (p["x_cm"] + start["x_cm"]) / 2,
                        "y_cm": (p["y_cm"] + start["y_cm"]) / 2,
                        "vx_cm_s": (p["x_cm"] - start["x_cm"]) / dt,
                        "vy_cm_s": (p["y_cm"] - start["y_cm"]) / dt})
        start = None
    return samples
