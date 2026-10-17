"""Water-plane homography with genuinely separate validation coordinates."""
import hashlib
import json

import cv2
import numpy as np


def project(matrix, pixels):
    matrix = np.asarray(matrix, dtype=np.float64)
    if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
        raise ValueError("Homography must be a finite 3x3 matrix")
    scale = np.max(np.abs(matrix))
    if scale == 0 or np.linalg.matrix_rank(matrix / scale) < 3:
        raise ValueError("Singular homography")
    matrix = matrix / scale
    pts = np.asarray(pixels, dtype=np.float64)
    if pts.size == 0:
        return []
    if pts.ndim != 2 or pts.shape[1] != 2 or not np.isfinite(pts).all():
        raise ValueError("Coordinates must be finite Nx2 pairs")
    homogeneous = np.column_stack([pts, np.ones(len(pts))])
    denominator = homogeneous @ matrix[2]
    magnitude = np.abs(homogeneous) @ np.abs(matrix[2])
    if np.any(np.abs(denominator) <= 1e-10 * np.maximum(magnitude, 1e-300)):
        raise ValueError("Projection lies on the homography horizon")
    out = (homogeneous @ matrix[:2].T / denominator[:, None]).reshape(-1, 1, 2)
    if not np.isfinite(out).all():
        raise ValueError("Projection lies on an invalid homography horizon")
    return out.reshape(-1, 2).tolist()


def fit_homography(pixel_points, world_cm_points, check_pixels, check_world_cm,
                   *, max_error_cm=0.5, image_size_px=None, camera_session_id=None):
    a, b = np.asarray(pixel_points, float), np.asarray(world_cm_points, float)
    cp, cw = np.asarray(check_pixels, float), np.asarray(check_world_cm, float)
    if a.shape != b.shape or a.ndim != 2 or a.shape[1] != 2 or len(a) < 4:
        raise ValueError("Provide at least four matching pixel/cm calibration pairs")
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("Calibration coordinates must be finite")
    for pts in (a, b):
        if np.linalg.matrix_rank(pts - pts.mean(axis=0)) < 2:
            raise ValueError("Calibration coordinates are collinear")
    if cp.shape != cw.shape or cp.ndim != 2 or cp.shape[1] != 2 or len(cp) < 3:
        raise ValueError("Provide at least three independent validation pairs")
    if not np.isfinite(cp).all() or not np.isfinite(cw).all():
        raise ValueError("Validation coordinates must be finite")
    if len(np.unique(cp, axis=0)) != len(cp) or len(np.unique(cw, axis=0)) != len(cw):
        raise ValueError("Validation coordinates must be distinct")
    if np.linalg.matrix_rank(cp - cp.mean(axis=0)) < 2:
        raise ValueError("Validation coordinates must span the plane")
    if any(np.linalg.norm(a - x, axis=1).min() < 1e-6 for x in cp):
        raise ValueError("Validation points must not repeat fitting points")
    if max_error_cm <= 0 or not np.isfinite(max_error_cm):
        raise ValueError("Validation tolerance must be finite and positive")
    matrix, _ = cv2.findHomography(a, b, method=0)
    if matrix is None or abs(np.linalg.det(matrix)) < 1e-12:
        raise ValueError("Singular homography")
    region = np.concatenate([a, cp])
    if image_size_px is not None:
        dimensions = np.asarray(image_size_px, float)
        if (dimensions.shape != (2,) or not np.isfinite(dimensions).all()
                or np.any(dimensions < 2) or np.any(dimensions != np.floor(dimensions))):
            raise ValueError("Image dimensions must be two positive integer pixel counts")
        if np.any(region < 0) or np.any(region > dimensions - 1):
            raise ValueError("Pixel references lie outside the actual image")
        w, h = dimensions - 1
        region = np.array([[0, 0], [w, 0], [w, h], [0, h]])
    denominators = np.column_stack([region, np.ones(len(region))]) @ matrix[2]
    if denominators.min() <= 0 <= denominators.max():
        raise ValueError("Calibration horizon crosses the camera region")
    errors = np.linalg.norm(np.asarray(project(matrix, cp)) - cw, axis=1)
    report = {"homography_image_to_cm": matrix.tolist(),
              "mean_error_cm": float(errors.mean()), "max_error_cm": float(errors.max()),
              "validation_count": len(cp), "max_allowed_error_cm": max_error_cm,
              "approved": bool(errors.max() <= max_error_cm),
              "image_size_px": image_size_px, "camera_session_id": camera_session_id,
              "plane": "measured_water_surface", "units": "cm"}
    report["calibration_id"] = "cal-" + hashlib.sha256(
        json.dumps(report, sort_keys=True, allow_nan=False).encode()).hexdigest()[:16]
    return report
