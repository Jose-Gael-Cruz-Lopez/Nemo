"""Fit water-plane references and report errors on separate validation points."""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--references", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    data = json.loads(Path(args.references).read_text())
    pixels = np.asarray(data["pixel_points"], np.float32)
    world = np.asarray(data["world_cm_points"], np.float32)
    check_px = np.asarray(data["check_pixel_points"], np.float32)
    check_world = np.asarray(data["check_world_cm_points"], np.float32)
    if pixels.shape != world.shape or pixels.ndim != 2 or pixels.shape[1] != 2 or len(pixels) < 4:
        raise ValueError("At least four paired non-collinear reference points required")
    if (
        check_px.shape != check_world.shape
        or check_px.ndim != 2
        or check_px.shape[1] != 2
        or len(check_px) < 3
    ):
        raise ValueError("At least three independent check points required")
    if not all(np.isfinite(a).all() for a in [pixels, world, check_px, check_world]):
        raise ValueError("Coordinates must be finite")
    if any(np.linalg.norm(p - q) < 1e-5 for p in pixels for q in check_px):
        raise ValueError("Check points must be independent of fitted references")
    matrix, _ = cv2.findHomography(pixels, world, method=0)
    if matrix is None or not np.isfinite(matrix).all() or abs(np.linalg.det(matrix)) < 1e-12:
        raise ValueError("Degenerate camera mapping")
    mapped = cv2.perspectiveTransform(check_px[None], matrix)[0]
    errors = np.linalg.norm(mapped - check_world, axis=1)
    result = {
        **data,
        "homography": matrix.tolist(),
        "mean_error_cm": float(errors.mean()),
        "max_error_cm": float(errors.max()),
        "measurement_plane": "water_surface",
        "validity": "development",
        "note": "Accept tolerances using development measurements before validation",
    }
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False))
    print(f"Mean error {errors.mean():.3f} cm; maximum {errors.max():.3f} cm")


if __name__ == "__main__":
    main()
