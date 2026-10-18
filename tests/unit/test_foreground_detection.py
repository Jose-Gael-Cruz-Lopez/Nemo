"""Colour-independent foreground token detection on SYNTHETIC images only.

No camera is opened and no real rig photo is used. The textured background
imitates a clear bin over a patterned floor; the caps are drawn discs.
"""
import cv2
import numpy as np
import pytest

from apps.vision.reeftrace_vision.calibration import fit_homography
from apps.vision.reeftrace_vision.foreground import (
    DETECTOR_ID,
    EmptyTankReference,
    SceneChanged,
    detect_foreground,
    measure_token_area,
    token_area_range,
)
from apps.vision.reeftrace_vision.tracking import SingleTokenTracker, detect_red

W, H = 640, 360
ROI = [(40, 30), (600, 30), (600, 330), (40, 330)]
GREEN, DARK_GREEN, WHITE, BLACK = (50, 150, 45), (40, 100, 30), (235, 235, 235), (25, 25, 25)


def background(seed=3):
    rng = np.random.default_rng(seed)
    speckle = cv2.GaussianBlur(rng.uniform(60, 190, (H, W, 3)).astype(np.float32), (0, 0), 2)
    speckle[..., 1] += 25  # greenish patterned floor seen through the bin
    image = np.clip(speckle, 0, 255).astype(np.uint8)
    cv2.rectangle(image, (250, 60), (380, 200), (60, 200, 70), 4)   # green mesh frame
    cv2.rectangle(image, (300, 60), (320, 330), (20, 20, 20), -1)   # black tape strip
    cv2.circle(image, (520, 80), 6, (255, 255, 255), -1)            # saturated glare spot
    return image


BASE = background()


def camera(image, seed, noise=2.5):
    rng = np.random.default_rng(seed)
    return np.clip(image.astype(np.float32) + rng.normal(0, noise, image.shape), 0, 255).astype(np.uint8)


def cap(image, x, y, colour=GREEN, radius=11):
    out = image.copy()
    cv2.circle(out, (round(x), round(y)), radius, colour, -1, lineType=cv2.LINE_AA)
    return out


@pytest.fixture(scope="module")
def reference():
    return EmptyTankReference([camera(BASE, s) for s in range(8)], roi_polygon_px=ROI)


@pytest.fixture(scope="module")
def area_range(reference):
    return token_area_range(measure_token_area(camera(cap(BASE, 450, 250), 99), reference))


def test_green_cap_is_invisible_to_red_detector_but_found_by_foreground(reference):
    frame = camera(cap(BASE, 150, 120), 10)
    assert detect_red(frame) == []
    found = detect_foreground(frame, reference)
    assert len(found) == 1
    assert abs(found[0]["pixel_x"] - 150) < 1 and abs(found[0]["pixel_y"] - 120) < 1


@pytest.mark.parametrize("colour", [GREEN, DARK_GREEN, WHITE, BLACK])
@pytest.mark.parametrize("where", [(150, 250), (315, 150), (260, 130)])  # open, on tape, on mesh
def test_any_colour_cap_is_found_anywhere_in_the_tank(reference, area_range, colour, where):
    if colour == BLACK and where == (315, 150):
        pytest.skip("covered by test_a_token_matching_what_is_under_it_is_not_seen")
    found = detect_foreground(camera(cap(BASE, *where, colour=colour), 11), reference, area_px_range=area_range)
    assert len(found) == 1
    assert np.hypot(found[0]["pixel_x"] - where[0], found[0]["pixel_y"] - where[1]) < 2


def test_a_token_matching_what_is_under_it_is_not_seen(reference, area_range):
    # Known limitation: a black cap over black tape has no contrast for any camera method.
    # It must be a gap, never a misplaced detection.
    assert detect_foreground(camera(cap(BASE, 310, 150, colour=BLACK, radius=8), 19),
                             reference, area_px_range=area_range) == []


def test_moving_token_does_not_look_like_camera_motion(reference, area_range):
    for x in (100, 300, 500):
        assert len(detect_foreground(camera(cap(BASE, x, 250), 20 + x), reference, area_px_range=area_range)) == 1


def test_empty_frames_with_fresh_noise_report_nothing(reference, area_range):
    for seed in range(20, 30):
        assert detect_foreground(camera(BASE, seed), reference, area_px_range=area_range) == []


def test_two_caps_become_a_tracker_gap_not_a_guess(reference, area_range, calibration):
    found = detect_foreground(camera(cap(cap(BASE, 150, 120), 450, 250), 12), reference, area_px_range=area_range)
    assert len(found) == 2
    point = SingleTokenTracker().update(found, 0.0, calibration)
    assert point["observed"] is False and point["reason"] == "MULTIPLE_TOKENS"


def test_hand_sized_object_is_rejected_by_measured_token_size(reference, area_range):
    hand = BASE.copy()
    cv2.ellipse(hand, (120, 300), (70, 40), 15, 0, 360, (120, 150, 200), -1)
    assert detect_foreground(camera(hand, 13), reference, area_px_range=area_range) == []


def test_small_lamp_change_including_saturated_glare_reports_nothing(reference, area_range):
    for gain in (0.9, 1.1):
        brighter = np.clip(BASE.astype(np.float32) * gain, 0, 255).astype(np.uint8)
        assert detect_foreground(camera(brighter, 14), reference, area_px_range=area_range) == []


def test_large_lamp_change_bumped_camera_or_resized_frame_require_new_reference(reference):
    with pytest.raises(SceneChanged, match="brightness"):
        detect_foreground(camera(np.clip(BASE * 1.4, 0, 255).astype(np.uint8), 15), reference)
    shifted = cv2.warpAffine(BASE, np.float32([[1, 0, 9], [0, 1, 7]]), (W, H), borderMode=cv2.BORDER_REFLECT)
    with pytest.raises(SceneChanged, match="moved"):
        detect_foreground(camera(shifted, 16), reference)
    with pytest.raises(SceneChanged, match="size"):
        detect_foreground(cv2.resize(BASE, (320, 180)), reference)


def test_reference_refuses_a_moving_camera_and_bad_inputs():
    shaky = [camera(cv2.warpAffine(BASE, np.float32([[1, 0, dx], [0, 1, 0]]), (W, H),
                                   borderMode=cv2.BORDER_REFLECT), 40 + dx) for dx in range(-4, 5)]
    with pytest.raises(SceneChanged, match="moved while capturing"):
        EmptyTankReference(shaky, roi_polygon_px=ROI)
    with pytest.raises(ValueError, match="5-60"):
        EmptyTankReference([BASE] * 3)
    with pytest.raises(ValueError, match="same size"):
        EmptyTankReference([BASE] * 4 + [cv2.resize(BASE, (320, 180))])
    with pytest.raises(ValueError, match="outside"):
        EmptyTankReference([BASE] * 5, roi_polygon_px=[(0, 0), (W + 10, 0), (0, H - 1)])


def test_token_measurement_needs_exactly_one_token(reference):
    with pytest.raises(ValueError, match="exactly one"):
        measure_token_area(camera(BASE, 17), reference)
    with pytest.raises(ValueError, match="exactly one"):
        measure_token_area(camera(cap(cap(BASE, 150, 120), 450, 250), 18), reference)
    low, high = token_area_range(400)
    assert low < 400 < high


def test_reference_provenance_is_small_stable_and_image_free(reference):
    again = EmptyTankReference([camera(BASE, s) for s in range(8)], roi_polygon_px=ROI)
    described = reference.describe()
    assert described == again.describe()
    assert described["detector"] == DETECTOR_ID and described["image_size_px"] == [W, H]
    assert set(described) == {"detector", "reference_id", "image_size_px", "frame_count", "roi_fraction"}


@pytest.fixture(scope="module")
def calibration():
    scale = 30 / 560  # synthetic: ROI spans 30 cm; not a measured rig
    px = [[40, 30], [600, 30], [600, 330], [40, 330]]
    check = [[200, 100], [500, 120], [350, 300]]
    to_cm = lambda p: [[(x - 40) * scale, (y - 30) * scale] for x, y in p]
    return fit_homography(px, to_cm(px), check, to_cm(check), image_size_px=(W, H),
                          camera_session_id="synthetic")


def test_moving_green_cap_forms_one_continuous_track_at_the_true_speed(reference, area_range, calibration):
    scale = 30 / 560
    tracker, points = SingleTokenTracker(), []
    for i in range(31):
        t = i * 0.1
        x_cm = 4 + 3.0 * t
        frame = camera(cap(BASE, 40 + x_cm / scale, 30 + 8 / scale), 100 + i)
        points.append(tracker.update(detect_foreground(frame, reference, area_px_range=area_range), t, calibration))
    observed = [p for p in points if p["observed"]]
    assert len(observed) == 31 and len({p["track_id"] for p in observed}) == 1
    slope = np.polyfit([p["t_s"] for p in observed], [p["x_cm"] for p in observed], 1)[0]
    assert abs(slope - 3.0) < 0.05


def test_token_measurement_ignores_small_ripple_sparkles(reference):
    sparkly = cap(BASE, 450, 250)
    for x, y in [(100, 80), (180, 300), (560, 60), (520, 300)]:
        cv2.circle(sparkly, (x, y), 4, (255, 255, 255), -1)   # small specular sparkles
    area = measure_token_area(camera(sparkly, 21), reference)
    assert 250 < area < 600
    with pytest.raises(ValueError, match="exactly one"):
        measure_token_area(camera(cap(cap(BASE, 150, 120), 450, 250), 22), reference)


def test_token_measurement_refuses_sparkles_alone():
    calm = [camera(BASE, s) for s in range(30, 38)]
    ref = EmptyTankReference(calm, roi_polygon_px=ROI)
    sparkly = BASE.copy()
    for x, y in [(100, 80), (180, 300), (560, 60)]:
        cv2.circle(sparkly, (x, y), 4, (255, 255, 255), -1)
    with pytest.raises(ValueError, match="exactly one"):
        measure_token_area(camera(sparkly, 23), ref)


@pytest.mark.parametrize("dx,dy", [(2, 1), (-3, 2), (5, -4)])
def test_small_camera_creep_is_undone_and_positions_stay_in_the_reference_pose(reference, area_range, dx, dy):
    moved = lambda img: cv2.warpAffine(img, np.float32([[1, 0, dx], [0, 1, dy]]), (W, H),
                                      borderMode=cv2.BORDER_REFLECT)
    assert detect_foreground(camera(moved(BASE), 40), reference, area_px_range=area_range) == []
    found = detect_foreground(camera(moved(cap(BASE, 300, 220)), 41), reference, area_px_range=area_range)
    assert len(found) == 1
    assert abs(found[0]["pixel_x"] - 300) < 1.5 and abs(found[0]["pixel_y"] - 220) < 1.5
