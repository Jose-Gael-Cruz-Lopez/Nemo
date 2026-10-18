"""Colour-independent token detection by comparison with an empty-tank reference.

The red HSV detector in ``tracking.py`` only sees red markers. This module finds
*any* new object on a fixed scene: the operator first captures several frames of
the empty tank (pump running, lamp on, hands out of view). Each later frame is
compared with that reference, and a pixel counts as foreground only when it
differs by more than that pixel's own natural flicker allows.

It locates an unexpected object; it does not recognise plastic. The output uses
the same detection dictionaries as ``detect_red``, so ``SingleTokenTracker`` keeps
its gap rules: zero or several blobs are a gap, never a guess. A large change
across the scene raises ``SceneChanged`` instead of reporting detections, because
a moved camera, moved lamp or a hand invalidates the reference.
"""
from __future__ import annotations

import hashlib

import cv2
import numpy as np

DETECTOR_ID = "foreground_reference_v1"
MIN_REFERENCE_FRAMES = 5
MAX_REFERENCE_FRAMES = 60
# A pixel whose own variation across the empty-tank frames exceeds this (Lab units)
# is "busy"; too many busy pixels means the reference was not captured from a still rig.
BUSY_PIXEL_DELTA = 12.0
MAX_BUSY_FRACTION = 0.10
# Global brightness may drift a little between reference and frame (lamp warm-up,
# auto exposure). Larger changes are treated as a changed scene, not compensated.
MAX_GAIN_CHANGE = 0.20
# A fixed overhead camera must not move. A whole-image shift larger than this
# (measured by phase correlation against the reference) invalidates the mapping.
MAX_CAMERA_SHIFT_PX = 1.5
MIN_SHIFT_CONFIDENCE = 0.05


class SceneChanged(ValueError):
    """The frame no longer matches the empty-tank reference; capture a new one."""


def _bgr(frame, label):
    if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3
            or frame.shape[2] != 3 or min(frame.shape[:2]) < 2):
        raise ValueError(f"{label} must be a uint8 BGR image")
    return frame


def _lab(frame):
    return cv2.cvtColor(frame, cv2.COLOR_BGR2LAB).astype(np.float32)


def _roi_mask(shape, roi_polygon_px):
    h, w = shape
    if roi_polygon_px is None:
        return np.ones((h, w), bool)
    polygon = np.asarray(roi_polygon_px, dtype=np.float64)
    if (polygon.ndim != 2 or polygon.shape[1] != 2 or len(polygon) < 3
            or not np.isfinite(polygon).all()):
        raise ValueError("Region of interest must be 3 or more finite [x, y] pixel points")
    if np.any(polygon < 0) or np.any(polygon[:, 0] > w - 1) or np.any(polygon[:, 1] > h - 1):
        raise ValueError("Region of interest lies outside the image")
    mask = np.zeros((h, w), np.uint8)
    cv2.fillPoly(mask, [np.round(polygon).astype(np.int32)], 1)
    if mask.sum() < 100:
        raise ValueError("Region of interest is too small")
    return mask.astype(bool)


class EmptyTankReference:
    """Per-pixel median appearance and natural variation of the empty, running tank."""

    def __init__(self, frames, *, roi_polygon_px=None):
        if not MIN_REFERENCE_FRAMES <= len(frames) <= MAX_REFERENCE_FRAMES:
            raise ValueError(f"Capture {MIN_REFERENCE_FRAMES}-{MAX_REFERENCE_FRAMES} empty-tank frames")
        frames = [_bgr(f, "Reference frame") for f in frames]
        if len({f.shape for f in frames}) != 1:
            raise ValueError("Reference frames must all have the same size")
        self.shape = frames[0].shape[:2]
        grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in frames]
        window = cv2.createHanningWindow(self.shape[::-1], cv2.CV_32F)
        for other in grays[1:]:
            (dx, dy), confidence = cv2.phaseCorrelate(grays[0].copy(), other.copy(), window)
            if confidence >= MIN_SHIFT_CONFIDENCE and np.hypot(dx, dy) > MAX_CAMERA_SHIFT_PX:
                raise SceneChanged("The camera moved while capturing the empty tank; "
                                   "fix the mount and retake it")
        stack = np.stack([_lab(f) for f in frames])
        self.median = np.median(stack, axis=0)
        self.median_bgr = np.median(np.stack(frames), axis=0).astype(np.float32)
        # Robust per-pixel spread (MAD scaled to a standard deviation), lightly smoothed
        # so isolated sensor noise does not leave single-pixel holes in the threshold.
        delta = np.sqrt(((stack - self.median) ** 2).sum(axis=3))
        self.noise = cv2.GaussianBlur(1.4826 * np.median(delta, axis=0), (5, 5), 0)
        self.roi = _roi_mask(self.shape, roi_polygon_px)
        busy = float((self.noise[self.roi] > BUSY_PIXEL_DELTA).mean())
        if busy > MAX_BUSY_FRACTION:
            raise SceneChanged(f"{busy:.0%} of the view varied while capturing the empty tank; "
                               "keep hands, tokens and the camera still and retake it")
        self.gray = np.median(np.stack(grays), axis=0).astype(np.float32)
        self.median_gray = float(np.median(self.gray[self.roi]))
        self._window = window
        self.frame_count = len(frames)
        roi_bytes = np.packbits(self.roi).tobytes()
        self.fingerprint = "ref-" + hashlib.sha256(
            np.round(self.median).astype(np.uint8).tobytes() + roi_bytes
            + repr(self.shape).encode()).hexdigest()[:16]

    _ARRAYS = ("median", "median_bgr", "noise", "roi", "gray")

    def to_arrays(self):
        """Private arrays for local storage (``numpy.savez``); never sent to clients."""
        return {**{name: getattr(self, name) for name in self._ARRAYS},
                "meta": np.array([self.frame_count, self.median_gray], dtype=np.float64)}

    @classmethod
    def from_arrays(cls, arrays, *, expected_id):
        """Rebuild a saved reference and refuse it if its content no longer matches its ID."""
        reference = cls.__new__(cls)
        for name in cls._ARRAYS:
            setattr(reference, name, np.asarray(arrays[name]))
        reference.roi = reference.roi.astype(bool)
        reference.shape = reference.gray.shape
        reference.frame_count = int(arrays["meta"][0])
        reference.median_gray = float(arrays["meta"][1])
        reference._window = cv2.createHanningWindow(reference.shape[::-1], cv2.CV_32F)
        reference.fingerprint = "ref-" + hashlib.sha256(
            np.round(reference.median).astype(np.uint8).tobytes() + np.packbits(reference.roi).tobytes()
            + repr(tuple(reference.shape)).encode()).hexdigest()[:16]
        if reference.fingerprint != expected_id:
            raise ValueError("Saved empty-tank reference does not match its ID; capture a new one")
        return reference

    def describe(self):
        """Small provenance record; never the images themselves."""
        return {"detector": DETECTOR_ID, "reference_id": self.fingerprint,
                "image_size_px": [self.shape[1], self.shape[0]],
                "frame_count": self.frame_count,
                "roi_fraction": round(float(self.roi.mean()), 4)}


def token_area_range(measured_area_px):
    """Accepted blob areas around one measured token; hands and fragments fall outside."""
    if not np.isfinite(measured_area_px) or measured_area_px < 25:
        raise ValueError("Measure one token of at least 25 pixels first")
    return (0.35 * measured_area_px, 3.0 * measured_area_px)


def measure_token_area(frame, reference, *, dominance=4.0):
    """One-token check on the rig: one blob must clearly dominate; returns its area in px.

    Running water leaves small ripple sparkles that differ from the reference. The
    token must be at least ``dominance`` times larger than any other changed blob,
    so sparkles neither hide it nor pass as a token when the tank is empty.
    """
    found = sorted((d["area_px"] for d in detect_foreground(frame, reference, max_area_fraction=0.2)),
                   reverse=True)
    if not found or (len(found) > 1 and found[0] < dominance * found[1]):
        raise ValueError("Expected exactly one token in view, found "
                         f"{0 if not found else sum(a >= found[0] / dominance for a in found)}")
    return found[0]


def detect_foreground(frame, reference, *, min_area_px=25, max_area_fraction=0.02,
                      area_px_range=None, k_sigma=6.0, min_delta=18.0, max_changed_fraction=0.15):
    """Return blobs that differ from the empty-tank reference, in ``detect_red``'s format.

    Without ``area_px_range`` the size limits are generic (25 px up to 2% of the frame).
    On the rig, pass ``token_area_range(measure_token_area(...))`` so only blobs about
    the size of one measured token count; a hand or a fragment then becomes a gap.
    """
    frame = _bgr(frame, "Frame")
    if frame.shape[:2] != reference.shape:
        raise SceneChanged("Frame size differs from the empty-tank reference; retake it")
    if not (np.isfinite([k_sigma, min_delta, max_changed_fraction, max_area_fraction]).all()
            and k_sigma > 0 and min_delta > 0 and 0 < max_changed_fraction < 1
            and 0 < max_area_fraction < 1 and 0 < min_area_px):
        raise ValueError("Detector thresholds must be finite and positive")
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    # phaseCorrelate windows its inputs in place, so give it copies.
    (dx, dy), confidence = cv2.phaseCorrelate(reference.gray.copy(), frame_gray.copy(), reference._window)
    if confidence >= MIN_SHIFT_CONFIDENCE and np.hypot(dx, dy) > MAX_CAMERA_SHIFT_PX:
        raise SceneChanged(f"The camera view moved by about {np.hypot(dx, dy):.1f} px; "
                           "fix the mount, then retake the mapping and the empty-tank reference")
    gray = float(np.median(frame_gray[reference.roi]))
    gain = gray / max(reference.median_gray, 1.0)
    if abs(gain - 1) > MAX_GAIN_CHANGE:
        raise SceneChanged(f"Overall brightness changed by {gain - 1:+.0%}; retake the empty-tank reference")
    # Apply a small global exposure/lamp change to the *reference* and clip it, so glare
    # that was already saturated stays saturated instead of appearing as a change.
    expected = _lab(np.clip(reference.median_bgr * gain, 0, 255).astype(np.uint8))
    delta = np.sqrt(((_lab(frame) - expected) ** 2).sum(axis=2))
    threshold = np.maximum(min_delta, k_sigma * reference.noise)
    mask = ((delta > threshold) & reference.roi).astype(np.uint8) * 255
    changed = float((mask[reference.roi] > 0).mean())
    if changed > max_changed_fraction:
        raise SceneChanged(f"{changed:.0%} of the view changed; the camera, lamp or scene moved, "
                           "or something large entered the frame. Retake the empty-tank reference")
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    max_area = frame.shape[0] * frame.shape[1] * max_area_fraction
    if area_px_range is not None:
        low, high = (float(v) for v in area_px_range)
        if not (np.isfinite([low, high]).all() and 0 < low < high):
            raise ValueError("area_px_range must be two increasing positive areas")
        min_area_px, max_area = low, high
    detections = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if not min_area_px <= area <= max_area:
            continue
        moments = cv2.moments(contour)
        if moments["m00"] <= 0:
            continue
        x, y = moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]
        detections.append({"pixel_x": float(x), "pixel_y": float(y), "area_px": float(area),
                           "bbox_px": list(cv2.boundingRect(contour))})
    return detections
