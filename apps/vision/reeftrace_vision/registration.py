"""Bounded ArUco water-plane proposals; no capture, storage, training or actuation.

Reference height, scale and rig identity are surveyed declarations, never inferred
from marker pixels. All thresholds below are frozen development policy v1.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Annotated, Literal

import cv2
import numpy as np
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    StrictBool,
    StrictInt,
    model_validator,
)

from .calibration import fit_homography, project

POLICY = {"version": "tank_registration_v1", "interval_s": 0.5, "max_age_s": 1.5,
          "stable_frames": 3, "max_shift_cm": 0.2, "geometry_shift_cm": 0.3,
          "min_laplacian_variance": 20, "max_pixels": 1920 * 1080,
          "black_value_max": 65, "green_hsv_lower": [35, 80, 40],
          "green_hsv_upper": [85, 255, 255], "min_contour_area_px": 200,
          "max_contours": 64, "max_vertices": 32}
Number = Annotated[FiniteFloat, Field(strict=True, ge=-200, le=200)]
Pair = tuple[Number, Number]
Polygon = Annotated[list[Pair], Field(min_length=3, max_length=32)]
Reference = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Marker(Strict):
    id: Annotated[StrictInt, Field(ge=0, lt=50)]
    role: Literal["fit", "check"]
    # Clockwise in decoded marker orientation: TL, TR, BR, BL, measured in cm.
    corners_cm: Annotated[list[Pair], Field(min_length=4, max_length=4)]


class RigContext(Strict):
    waterline_id: Reference
    layout_id: Reference
    flow_configuration_id: Reference
    token_class_id: Reference


class RegistrationConfig(Strict):
    schema_version: Literal["tank_registration_config_v1"]
    data_origin: Literal["SYNTHETIC", "OPERATOR_SURVEYED"]
    dictionary: Literal["DICT_4X4_50"]
    reference_plane: Literal["measured_water_surface"]
    references_surveyed: StrictBool
    context: RigContext
    markers: Annotated[list[Marker], Field(min_length=7, max_length=20)]
    water_polygon_cm: Polygon
    # Declared position/shape gate only; never automatically trial geometry.
    expected_filter_polygon_cm: Polygon | None = None
    max_error_cm: Annotated[FiniteFloat, Field(strict=True, gt=0, le=0.5)] = 0.5

    @model_validator(mode="after")
    def survey(self):
        if not self.references_surveyed:
            raise ValueError("Unknown scale/plane: declare a surveyed water-surface reference")
        ids = [m.id for m in self.markers]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate reference IDs")
        if sum(m.role == "fit" for m in self.markers) < 4 or sum(
                m.role == "check" for m in self.markers) < 3:
            raise ValueError("Freeze at least four fit IDs and three separate check IDs")
        all_corners = [tuple(p) for m in self.markers for p in m.corners_cm]
        if len(set(all_corners)) != len(all_corners):
            raise ValueError("Reference corners must be distinct across fit/check IDs")
        for marker in self.markers:
            corners = np.asarray(marker.corners_cm, np.float32)
            if not cv2.isContourConvex(corners) or abs(cv2.contourArea(corners, oriented=True)) <= 0.01:
                raise ValueError("Marker corners must be distinct in decoded TL/TR/BR/BL order")
        for polygon in (self.water_polygon_cm, self.expected_filter_polygon_cm):
            if polygon is not None:
                validate_polygon(polygon)
        fit = np.asarray([p for m in self.markers if m.role == "fit" for p in m.corners_cm],
                         np.float32)
        hull = cv2.convexHull(fit)
        if any(cv2.pointPolygonTest(hull, p, False) < 0 for p in self.water_polygon_cm):
            raise ValueError("Water region must be inside surveyed fitting-reference support")
        if self.expected_filter_polygon_cm and any(cv2.pointPolygonTest(
                np.asarray(self.water_polygon_cm, np.float32), p, False) < 0
                for p in self.expected_filter_polygon_cm):
            raise ValueError("Expected filter must lie within the declared water polygon")
        return self


def validate_polygon(points):
    """Keep the actual simple outline, including concavities; never a bounding box."""
    a = np.asarray(points, dtype=np.float64)
    if (a.ndim != 2 or a.shape[1] != 2 or not 3 <= len(a) <= 32 or not np.isfinite(a).all()
            or len(np.unique(a, axis=0)) != len(a)
            or abs(cv2.contourArea(a.astype(np.float32))) < 0.01):
        raise ValueError("Polygon needs 3-32 distinct finite vertices and nonzero area")
    def orientation(p, q, r):
        u, v = q - p, r - p
        return float(u[0] * v[1] - u[1] * v[0])
    for i in range(len(a)):
        p, q = a[i], a[(i + 1) % len(a)]
        for j in range(i + 1, len(a)):
            if j in {i, (i + 1) % len(a)} or (j + 1) % len(a) == i:
                continue
            r, s = a[j], a[(j + 1) % len(a)]
            if (orientation(p, q, r) * orientation(p, q, s) <= 0
                    and orientation(r, s, p) * orientation(r, s, q) <= 0
                    and np.all(np.maximum(np.minimum(p, q), np.minimum(r, s))
                               <= np.minimum(np.maximum(p, q), np.maximum(r, s)))):
                raise ValueError("Polygon may not self-intersect")
    return a


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def detect_references(image):
    if (not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.ndim != 3
            or image.shape[2] != 3 or min(image.shape[:2]) < 32
            or image.shape[0] * image.shape[1] > POLICY["max_pixels"]):
        raise ValueError("Expected bounded uint8 BGR frame, at most 1920x1080 pixels")
    if not hasattr(cv2, "aruco"):
        raise ValueError("This OpenCV installation has no ArUco support")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if cv2.Laplacian(gray, cv2.CV_64F).var() < POLICY["min_laplacian_variance"]:
        raise ValueError("BLUR_OR_LOW_CONTRAST: references unavailable")
    parameters = cv2.aruco.DetectorParameters()
    parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    detector = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), parameters)
    corners, ids, _ = detector.detectMarkers(gray)
    if ids is None:
        raise ValueError("NO_REFERENCE: missing, occluded or unreadable IDs")
    values = ids.flatten().tolist()
    if len(set(values)) != len(values):
        raise ValueError("DUPLICATE_ID: ambiguous reference identities")
    return {i: c.reshape(4, 2).tolist() for i, c in zip(values, corners, strict=True)}


def propose(image, config: RegistrationConfig, session_id: str):
    found = detect_references(image)
    expected = {m.id for m in config.markers}
    if set(found) != expected:
        raise ValueError(f"REFERENCE_IDS: missing {sorted(expected - set(found))}; "
                         f"unexpected {sorted(set(found) - expected)}")
    pixels, world = {}, {}
    for role in ("fit", "check"):
        markers = [m for m in config.markers if m.role == role]
        pixels[role] = [p for m in markers for p in found[m.id]]
        world[role] = [p for m in markers for p in m.corners_cm]
        for points in (pixels[role], world[role]):
            a = np.asarray(points)
            if np.linalg.matrix_rank(a - a.mean(axis=0)) < 2:
                raise ValueError("Reference points must independently span the plane")
    report = fit_homography(pixels["fit"], world["fit"], pixels["check"], world["check"],
                            max_error_cm=config.max_error_cm,
                            image_size_px=[image.shape[1], image.shape[0]],
                            camera_session_id=session_id)
    if not report["approved"]:
        raise ValueError(f"VALIDATION_FAILED: independent max error {report['max_error_cm']:.4f} cm "
                         f"> frozen {config.max_error_cm} cm")
    water_pixels = project(np.linalg.inv(report["homography_image_to_cm"]),
                           config.water_polygon_cm)
    if any(x < 0 or y < 0 or x > image.shape[1] - 1 or y > image.shape[0] - 1
           for x, y in water_pixels):
        raise ValueError("Supported water region extends outside the image")
    return {"calibration": report, "fit_pixels": pixels["fit"],
            "water_polygon_px": water_pixels, "references": found,
            "config_sha256": digest(config.model_dump()), "policy_sha256": digest(POLICY),
            "opencv_version": cv2.__version__, "frame_pixels_sha256": hashlib.sha256(image.tobytes()).hexdigest()}


def contour_distance(a, b):
    """Symmetric vertex-to-edge distance; unlike bbox comparison preserves shape."""
    def one(points, edges):
        contour = np.asarray(edges, np.float32)
        return max(abs(cv2.pointPolygonTest(contour, tuple(map(float, p)), True)) for p in points)
    return max(one(a, b), one(b, a))


def geometry_layers(image, proposal, config):
    """Bounded contour candidates only; no colour-based scientific identity."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    water = np.zeros(image.shape[:2], np.uint8)
    cv2.fillPoly(water, [np.rint(proposal["water_polygon_px"]).astype(np.int32)], 255)
    matrix = proposal["calibration"]["homography_image_to_cm"]
    result = {}
    for label, lower, upper, expected in (
        ("tray_boundary", (0, 0, 0), (179, 255, POLICY["black_value_max"]),
         config.water_polygon_cm),
        ("filter_border", POLICY["green_hsv_lower"], POLICY["green_hsv_upper"],
         config.expected_filter_polygon_cm),
    ):
        mask = cv2.inRange(hsv, np.asarray(lower), np.asarray(upper)) & water
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        overflow = len(contours) > POLICY["max_contours"]
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:POLICY["max_contours"]]:
            if cv2.contourArea(contour) < POLICY["min_contour_area_px"]:
                continue
            polygon = cv2.approxPolyDP(contour, 0.005 * cv2.arcLength(contour, True), True)
            if not 3 <= len(polygon) <= POLICY["max_vertices"]:
                continue
            px = polygon.reshape(-1, 2).astype(float).tolist()
            cm = project(matrix, px)
            if expected is not None and contour_distance(cm, expected) <= POLICY["geometry_shift_cm"]:
                candidates.append({"polygon_px": px, "polygon_cm": cm})
        result[label] = {"status": "CANDIDATE" if len(candidates) == 1 and not overflow
                         else "AMBIGUOUS" if len(candidates) > 1 or overflow else "UNAVAILABLE",
                         "candidates": candidates[:8], "operator_confirmed": False}
    # Separate semantic layers; nothing detected here creates these scientific objects.
    result["protected_zone"] = {"status": "NOT_ASSIGNED"}
    result["token_track"] = {"status": "NOT_ANALYZED"}
    return result


class RegistrationMonitor:
    """Latched stale state. Recovery requires a new proposal and explicit approval."""
    def __init__(self, config: RegistrationConfig):
        self.config = config
        self.candidate = None
        self.approved = False
        self.stale = False
        self.last_t = None
        self.last_sequence = None
        self.stable_frames = 0
        self.layers = {}
        self.state, self.reason = "NO_REFERENCE", "No frame examined"

    def invalidate(self, reason):
        self.stale = True
        self.approved = False
        self.state, self.reason = "MOVED_STALE", reason
        return self.snapshot()

    def observe(self, image, *, session_id, sequence, t_s, context):
        if not np.isfinite(t_s) or not isinstance(sequence, int) or sequence < 0:
            return self.invalidate("Invalid frame identity/time")
        if context != self.config.context.model_dump():
            return self.invalidate("Rig context changed: re-survey plane/geometry and revalidate drift")
        if self.stale:
            return self.snapshot()
        if self.last_t is not None:
            if t_s < self.last_t or sequence < self.last_sequence:
                return self.invalidate("Frame identity/time moved backwards")
            if t_s - self.last_t > POLICY["max_age_s"]:
                return self.invalidate("Reference monitoring gap exceeded frozen maximum age")
            if self.candidate and (session_id != self.candidate["calibration"]["camera_session_id"]
                                  or [image.shape[1], image.shape[0]]
                                  != self.candidate["calibration"]["image_size_px"]):
                return self.invalidate("Camera session or resolution changed")
            if sequence == self.last_sequence and t_s != self.last_t:
                return self.invalidate("Repeated frame identity changed timestamp")
            if sequence == self.last_sequence or t_s - self.last_t < POLICY["interval_s"]:
                return self.snapshot()
        self.last_t, self.last_sequence = t_s, sequence
        try:
            proposal = propose(image, self.config, session_id)
            if self.candidate:
                # Do not refit-away a bump. Compare against the frozen candidate matrix.
                old = self.candidate["calibration"]["homography_image_to_cm"]
                shifts = [np.linalg.norm(np.asarray(project(old, proposal["references"][m.id]))
                                         - np.asarray(project(old, self.candidate["references"][m.id])),
                                         axis=1).max()
                          for m in self.config.markers]
                if max(shifts) > POLICY["max_shift_cm"]:
                    return self.invalidate("Reference displacement exceeds frozen 0.2 cm stability gate")
            else:
                self.candidate = proposal
                self.candidate["frame_identity"] = {"camera_session_id": session_id,
                    "sequence": sequence, "received_mono_s": t_s}
            layers = geometry_layers(image, self.candidate, self.config)
            if self.approved:
                for name, layer in self.layers.items():
                    if layer.get("operator_confirmed") and layers[name]["status"] != "CANDIDATE":
                        return self.invalidate(f"Confirmed {name} lost or moved; revalidate geometry/flow")
                    if layer.get("operator_confirmed"):
                        layers[name]["operator_confirmed"] = True
            self.layers = layers
            self.stable_frames += 1
            self.state = "STABLE_APPROVED" if self.approved else "CANDIDATE_MAPPING"
            self.reason = "Independent checks passed; explicit operator approval required" if not self.approved \
                else "References stable; flow admission remains separate"
        except (ValueError, cv2.error) as error:
            if self.candidate:
                return self.invalidate(str(error))
            self.state = "NO_REFERENCE" if "REFERENCE" in str(error) else "VALIDATION_FAILED"
            self.reason = str(error)
            self.stable_frames = 0
        return self.snapshot()

    def approve(self, proposal_id, confirmed_layers=()):
        if self.stale or not self.candidate or not self.ready or proposal_id != self.snapshot()["proposal_id"]:
            raise ValueError("Current stable proposal required; stale mappings cannot resume automatically")
        for name in confirmed_layers:
            if name not in {"tray_boundary", "filter_border"} or self.layers[name]["status"] != "CANDIDATE":
                raise ValueError("Only a unique surveyed-position geometry candidate may be confirmed")
        for name in confirmed_layers:
            self.layers[name]["operator_confirmed"] = True
        self.approved = True
        self.state, self.reason = "STABLE_APPROVED", "Operator approved mapping; drift admission is separate"
        return self.snapshot()

    @property
    def ready(self):
        return self.stable_frames >= POLICY["stable_frames"] and not self.stale

    def snapshot(self):
        proposal_id = digest({"proposal": self.candidate, "config": self.config.model_dump(),
                              "policy": POLICY}) if self.candidate else None
        return {"schema_version": "tank_registration_status_v1", "state": self.state,
                "reason": self.reason, "proposal_id": proposal_id, "ready_for_approval": self.ready,
                "mapping_current": self.approved and not self.stale,
                "data_origin": self.config.data_origin, "physical_accuracy_validated": False,
                "stable_frames": self.stable_frames, "policy": POLICY,
                "proposal": copy.deepcopy(self.candidate) if not self.stale else None,
                "geometry_layers": copy.deepcopy(self.layers) if not self.stale else {},
                "calibration_id": self.candidate["calibration"]["calibration_id"]
                if self.approved and self.candidate else None,
                "flow_admission": "SEPARATE_EXISTING_CONTRACT_REQUIRED"}
