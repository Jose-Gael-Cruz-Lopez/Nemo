"""Frozen compact-cap policy on synthetic images; no saved physical footage or devices."""
from __future__ import annotations

import cv2
import numpy as np
import pytest

from apps.vision.reeftrace_vision.foreground import (
    EmptyTankReference,
    SceneChanged,
    detect_foreground,
)
from apps.vision.reeftrace_vision.surface_token import (
    SURFACE_POLICY_SHA256,
    detect_surface_token,
    measure_surface_token_area,
    surface_policy,
    surface_token_diagnostic,
    validate_detection_polygon,
)

WIDTH, HEIGHT = 320, 240
DOMAIN = [[20, 20], [300, 20], [300, 220], [20, 220]]
GREEN = (30, 180, 40)


@pytest.fixture
def scene():
    image = np.random.default_rng(91).integers(80, 140, (HEIGHT, WIDTH, 3), np.uint8)
    return image, EmptyTankReference([image.copy() for _ in range(5)])


def test_compact_cap_admitted_while_rim_and_wall_components_are_explained(scene):
    empty, reference = scene
    frame = empty.copy()
    cv2.circle(frame, (140, 110), 14, GREEN, -1)
    cv2.rectangle(frame, (30, 170), (230, 177), GREEN, -1)  # Elongated rim inside domain.
    cv2.circle(frame, (15, 80), 10, GREEN, -1)  # A component crossing the declared boundary.
    report = surface_token_diagnostic(frame, reference, DOMAIN, max_area_fraction=0.2)
    assert len(report["detections"]) == 1
    cap = report["detections"][0]
    assert cap["pixel_x"] == pytest.approx(140, abs=1)
    assert cap["pixel_y"] == pytest.approx(110, abs=1)
    assert report["diagnostics"]["accepted_count"] == 1
    assert report["diagnostics"]["rejection_counts"]["ELONGATED_COMPONENT"] >= 1
    assert report["diagnostics"]["rejection_counts"]["OUTSIDE_DETECTION_POLYGON"] >= 1
    assert report["policy_sha256"] == SURFACE_POLICY_SHA256
    assert measure_surface_token_area(frame, reference, DOMAIN) == cap["area_px"]


def test_polygon_does_not_crop_or_modify_background_gain_or_component_shape(scene):
    empty, reference = scene
    before_roi, before_median = reference.roi.copy(), reference.median_gray
    frame = empty.copy()
    cv2.circle(frame, (140, 110), 14, GREEN, -1)
    original = detect_foreground(frame, reference, max_area_fraction=0.2)
    surface = detect_surface_token(frame, reference, DOMAIN, max_area_fraction=0.2)
    assert len(original) == len(surface) == 1
    assert surface == original  # No ROI-induced gain change, clipping, merging or new centroid.
    np.testing.assert_array_equal(reference.roi, before_roi)
    assert reference.median_gray == before_median
    cropped_reference = EmptyTankReference([empty.copy() for _ in range(5)], roi_polygon_px=DOMAIN)
    with pytest.raises(ValueError, match="full-frame background"):
        detect_surface_token(frame, cropped_reference, DOMAIN)


def test_zero_and_two_similar_caps_remain_missing_or_ambiguous(scene):
    empty, reference = scene
    assert detect_surface_token(empty, reference, DOMAIN) == []
    with pytest.raises(ValueError, match="found 0"):
        measure_surface_token_area(empty, reference, DOMAIN)
    frame = empty.copy()
    for center in ((90, 100), (220, 120)):
        cv2.circle(frame, center, 12, GREEN, -1)
    assert len(detect_surface_token(frame, reference, DOMAIN)) == 2
    with pytest.raises(ValueError, match="found 2"):
        measure_surface_token_area(frame, reference, DOMAIN)


def test_cap_crossing_domain_is_rejected_not_clipped_into_compact_fake_blob(scene):
    empty, reference = scene
    frame = empty.copy()
    cv2.circle(frame, (22, 120), 14, GREEN, -1)
    report = surface_token_diagnostic(frame, reference, DOMAIN)
    assert report["detections"] == []
    assert report["diagnostics"]["rejection_counts"]["OUTSIDE_DETECTION_POLYGON"] == 1
    component = report["diagnostics"]["candidates"][0]
    assert component["bbox_px"][0] < 20
    assert component["area_px"] > 400  # Full component retained; no silhouette cropping.


def test_concave_weak_shape_is_rejected_with_diagnostics(scene):
    empty, reference = scene
    frame = empty.copy()
    points = np.array([[150 + (27 if i % 2 == 0 else 9) * np.cos(i * np.pi / 6),
                        110 + (27 if i % 2 == 0 else 9) * np.sin(i * np.pi / 6)]
                       for i in range(12)], np.int32)
    cv2.fillPoly(frame, [points], GREEN)
    report = surface_token_diagnostic(frame, reference, DOMAIN, max_area_fraction=0.2)
    assert report["detections"] == []
    codes = report["diagnostics"]["rejection_counts"]
    assert codes.get("LOW_SOLIDITY", 0) or codes.get("WEAK_CIRCULARITY", 0)


@pytest.mark.parametrize("change", ["brightness", "camera", "dimensions"])
def test_global_scene_and_camera_limits_are_not_relaxed_by_surface_domain(scene, change):
    empty, reference = scene
    if change == "brightness":
        frame = (empty.astype(float) * 0.7).astype(np.uint8)
    elif change == "camera":
        frame = cv2.warpAffine(empty, np.float32([[1, 0, 15], [0, 1, 0]]), (WIDTH, HEIGHT),
                               borderMode=cv2.BORDER_REFLECT)
    else:
        frame = empty[:100, :100]
    with pytest.raises(SceneChanged):
        detect_surface_token(frame, reference, DOMAIN)


@pytest.mark.parametrize("polygon", [None, [[0, 0], [10, 0]], [[0, 0], [30, 0], [0, 0]],
                                    [[0, 0], [20, 20], [40, 40]],
                                    [[-1, 20], [100, 20], [100, 100], [20, 100]],
                                    [[20, 20], [100, 20], [50, 50], [100, 100], [20, 100]]])
def test_invalid_detection_domains_are_explicit_errors(polygon):
    with pytest.raises(ValueError):
        validate_detection_polygon([WIDTH, HEIGHT], polygon)


def test_policy_is_versioned_and_callers_cannot_change_shape_or_dominance(scene):
    _, reference = scene
    original = surface_policy()
    changed = surface_policy()
    changed["minimum_circularity"] = 0
    assert surface_policy() == original
    assert original["maximum_aspect_ratio"] == 2.0
    assert original["minimum_circularity"] == 0.45
    assert original["minimum_solidity"] == 0.75
    assert original["measurement_dominance"] == 4.0
    with pytest.raises(ValueError, match="fixed fourfold"):
        measure_surface_token_area(np.zeros((HEIGHT, WIDTH, 3), np.uint8), reference, DOMAIN,
                                   dominance=1)
