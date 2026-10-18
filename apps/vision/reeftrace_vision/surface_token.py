"""Opt-in declared green-cap admission after unchanged global foreground checks.

This revised engineering hypothesis was informed by development footage; it is
not plastic recognition or independent physical validation. It requires a green
marker, not an arbitrary cap. Polygon and morphology failures remain gaps.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from types import MappingProxyType

import cv2
import numpy as np

from .foreground import _roi_mask, foreground_change_mask_and_frame

SURFACE_DETECTOR_ID = "foreground_surface_v2"
SURFACE_POLICY_ID = "foreground_green_cap_v1"
_POLICY = MappingProxyType({
    "policy_id": SURFACE_POLICY_ID,
    "detector": SURFACE_DETECTOR_ID,
    "maximum_aspect_ratio": 2.0,
    "minimum_circularity": 0.45,
    "minimum_solidity": 0.75,
    "green_hsv_lower": (35, 80, 40),
    "green_hsv_upper": (85, 255, 255),
    "green_mask_open_kernel_px": 3,
    "green_mask_close_kernel_px": 5,
    "segmentation": "aligned_green_hsv_intersect_unchanged_foreground_mask",
    "minimum_area_px": 25.0,
    "default_max_area_fraction": 0.02,
    "measurement_max_area_fraction": 0.2,
    "measurement_dominance": 4.0,
    "candidate_domain": "entire_component_bbox_inside_declared_convex_polygon",
    "background_gain_domain": "unchanged_full_frame_reference",
    "diagnostic_candidate_limit": 200,
})
SURFACE_POLICY_SHA256 = hashlib.sha256(
    json.dumps(dict(_POLICY), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
).hexdigest()


def surface_policy():
    return {**{key: list(value) if isinstance(value, tuple) else value
               for key, value in _POLICY.items()}, "policy_sha256": SURFACE_POLICY_SHA256}


def validate_detection_polygon(image_size_px, polygon):
    dimensions = np.asarray(image_size_px, dtype=float)
    if (dimensions.shape != (2,) or not np.isfinite(dimensions).all()
            or np.any(dimensions < 2) or np.any(dimensions != np.floor(dimensions))):
        raise ValueError("Image dimensions must be two integer pixel counts")
    points = np.asarray(polygon, dtype=float)
    if (points.ndim != 2 or points.shape[1] != 2 or not 3 <= len(points) <= 32
            or not np.isfinite(points).all() or len(np.unique(points, axis=0)) != len(points)
            or not cv2.isContourConvex(points.astype(np.float32))):
        raise ValueError("Detection polygon must have 3-32 distinct convex pixel vertices")
    _roi_mask((int(dimensions[1]), int(dimensions[0])), points)
    return points.tolist()


def surface_token_diagnostic(frame, reference, detection_polygon_px, *, area_px_range=None,
                             max_area_fraction=0.02):
    polygon = validate_detection_polygon(reference.shape[::-1], detection_polygon_px)
    if not reference.roi.all():
        raise ValueError("V2 requires a full-frame background; candidate ROI must not change global gain")
    if not np.isfinite(max_area_fraction) or not 0 < max_area_fraction < 1:
        raise ValueError("Area fraction must be finite and between zero and one")
    low, high = _POLICY["minimum_area_px"], float(np.prod(reference.shape)) * max_area_fraction
    if area_px_range is not None:
        if len(area_px_range) != 2:
            raise ValueError("Token area bounds need two values")
        low, high = map(float, area_px_range)
        if not np.isfinite([low, high]).all() or not 0 < low < high:
            raise ValueError("Token area bounds must be increasing positive finite values")
    # No polygon or colour mask changes gain estimation or the global scene gates.
    mask, aligned = foreground_change_mask_and_frame(frame, reference)
    green = cv2.inRange(cv2.cvtColor(aligned, cv2.COLOR_BGR2HSV),
                        np.array(_POLICY["green_hsv_lower"], np.uint8),
                        np.array(_POLICY["green_hsv_upper"], np.uint8))
    mask = cv2.bitwise_and(mask, green)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    domain = _roi_mask(reference.shape, polygon)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates, detections, reasons = [], [], Counter()
    for contour in contours:
        area = float(cv2.contourArea(contour))
        moments = cv2.moments(contour)
        if area <= 0 or moments["m00"] <= 0:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        perimeter = float(cv2.arcLength(contour, True))
        hull_area = float(cv2.contourArea(cv2.convexHull(contour)))
        aspect = max(width, height) / min(width, height)
        circularity = 4 * np.pi * area / perimeter ** 2 if perimeter else 0.0
        solidity = area / hull_area if hull_area else 0.0
        rejected = []
        if not domain[y:y + height, x:x + width].all():
            rejected.append("OUTSIDE_DETECTION_POLYGON")
        if not low <= area <= high:
            rejected.append("AREA_OUT_OF_RANGE")
        if aspect > _POLICY["maximum_aspect_ratio"]:
            rejected.append("ELONGATED_COMPONENT")
        if circularity < _POLICY["minimum_circularity"]:
            rejected.append("WEAK_CIRCULARITY")
        if solidity < _POLICY["minimum_solidity"]:
            rejected.append("LOW_SOLIDITY")
        detection = {"pixel_x": float(moments["m10"] / moments["m00"]),
                     "pixel_y": float(moments["m01"] / moments["m00"]),
                     "area_px": area, "bbox_px": [x, y, width, height]}
        candidates.append({**detection, "aspect_ratio": float(aspect),
                           "circularity": float(circularity), "solidity": float(solidity),
                           "accepted": not rejected, "rejection_codes": rejected})
        reasons.update(rejected)
        if not rejected:
            detections.append(detection)
    candidates.sort(key=lambda candidate: candidate["area_px"], reverse=True)
    return {"detector": SURFACE_DETECTOR_ID, "policy_id": SURFACE_POLICY_ID,
            "policy_sha256": SURFACE_POLICY_SHA256, "detection_polygon_px": polygon,
            "detections": detections, "diagnostics": {
                "candidate_count": len(candidates), "accepted_count": len(detections),
                "rejected_count": len(candidates) - len(detections),
                "rejection_counts": dict(sorted(reasons.items())),
                "candidates": candidates[:_POLICY["diagnostic_candidate_limit"]],
                "diagnostics_truncated": len(candidates) > _POLICY["diagnostic_candidate_limit"]}}


def detect_surface_token(frame, reference, detection_polygon_px, *, area_px_range=None,
                         max_area_fraction=0.02):
    return surface_token_diagnostic(frame, reference, detection_polygon_px,
                                    area_px_range=area_px_range,
                                    max_area_fraction=max_area_fraction)["detections"]


def measure_surface_token_area(frame, reference, detection_polygon_px, *, dominance=4.0):
    if dominance != _POLICY["measurement_dominance"]:
        raise ValueError("The versioned surface policy has a fixed fourfold size dominance")
    found = sorted((d["area_px"] for d in detect_surface_token(
        frame, reference, detection_polygon_px,
        max_area_fraction=_POLICY["measurement_max_area_fraction"])), reverse=True)
    if not found or (len(found) > 1 and found[0] < dominance * found[1]):
        raise ValueError("Expected one dominant green compact token inside the detection polygon; "
                         f"found {len(found)} admitted components")
    return found[0]
