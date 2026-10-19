"""Only constructed images; never camera/provider I/O or physical accuracy claims."""
import copy

import cv2
import numpy as np
import pytest
from pydantic import ValidationError

from apps.vision.reeftrace_vision.calibration import project
from apps.vision.reeftrace_vision.registration import (
    RegistrationConfig,
    RegistrationMonitor,
    contour_distance,
    detect_references,
    geometry_layers,
    propose,
)
from apps.vision.reeftrace_vision.tracking import SingleTokenTracker
from scripts.rehearse_tank_registration import constructed_frame, rehearse, synthetic_config


@pytest.fixture
def scene():
    config = synthetic_config()
    image, matrix = constructed_frame(config)
    return config, image, matrix


def stable(config, image):
    monitor = RegistrationMonitor(config)
    for i in range(3):
        monitor.observe(image, session_id="dry", sequence=i, t_s=i * .5,
                        context=config.context.model_dump())
    assert monitor.ready
    monitor.approve(monitor.snapshot()["proposal_id"])
    return monitor


def test_known_homography_and_independent_checks_grid_and_geometry(scene):
    config, image, matrix = scene
    proposal = propose(image, config, "dry")
    calibration = proposal["calibration"]
    assert calibration["validation_count"] == 12
    assert calibration["max_error_cm"] < .05  # Predeclared synthetic raster tolerance.
    sample_world = [[0, 0], [8, 9], [40, 30]]
    recovered = project(calibration["homography_image_to_cm"], project(matrix, sample_world))
    assert np.max(np.linalg.norm(np.asarray(recovered) - sample_world, axis=1)) < .05
    layers = geometry_layers(image, proposal, config)
    assert layers["tray_boundary"]["status"] == "CANDIDATE"
    assert layers["filter_border"]["status"] == "CANDIDATE"
    assert layers["filter_border"]["operator_confirmed"] is False
    assert layers["protected_zone"]["status"] == "NOT_ASSIGNED"
    assert layers["token_track"]["status"] == "NOT_ANALYZED"


@pytest.mark.parametrize("transform", [
    [[1., 0, 15], [0, 1, 10], [0, 0, 1]],
    [[.999, -.02, 20], [.02, .999, 2], [0, 0, 1]],
    [[1., .015, 22], [-.01, 1., 12], [.00001, -.00001, 1.]],
])
def test_shift_never_refits_away_stale_map_but_new_proposal_can_recover(scene, transform):
    config, image, _ = scene
    monitor = stable(config, image)
    moved = cv2.warpPerspective(image, np.asarray(transform), (1040, 840),
                                borderValue=(235, 235, 235))
    result = monitor.observe(moved, session_id="dry", sequence=3, t_s=1.5,
                             context=config.context.model_dump())
    assert result["state"] == "MOVED_STALE" and result["proposal"] is None
    with pytest.raises(ValueError, match="stable proposal"):
        monitor.approve(result["proposal_id"])
    assert monitor.observe(image, session_id="dry", sequence=4, t_s=2,
                           context=config.context.model_dump())["mapping_current"] is False
    fresh = RegistrationMonitor(config)
    result = fresh.observe(moved, session_id="dry", sequence=0, t_s=0,
                            context=config.context.model_dump())
    assert result["state"] in {"CANDIDATE_MAPPING", "VALIDATION_FAILED", "NO_REFERENCE"}
    assert result["mapping_current"] is False
    if result["proposal"]:
        assert result["proposal"]["calibration"]["max_error_cm"] < .05


@pytest.mark.parametrize("kind", ["missing", "occluded", "wrong_id", "duplicate", "blur", "glare"])
def test_missing_ambiguous_or_unreadable_references_are_honestly_withheld(scene, kind):
    config, image, _ = scene
    if kind in {"missing", "occluded", "glare"}:
        image[30:90, 30:90] = 255 if kind == "glare" else 235
    elif kind == "wrong_id":
        replacement = cv2.aruco.generateImageMarker(
            cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), 20, 40)
        image[40:80, 40:80] = cv2.cvtColor(replacement, cv2.COLOR_GRAY2BGR)
    elif kind == "duplicate":
        image[100:140, 40:80] = image[40:80, 40:80]
    else:
        image = cv2.GaussianBlur(image, (51, 51), 15)
    monitor = RegistrationMonitor(config)
    result = monitor.observe(image, session_id="dry", sequence=0, t_s=0,
                             context=config.context.model_dump())
    assert result["state"] in {"NO_REFERENCE", "VALIDATION_FAILED"}
    assert not result["mapping_current"] and result["proposal"] is None


def test_independent_check_errors_do_not_approve_or_change_declared_tolerance(scene):
    config, image, _ = scene
    data = config.model_dump()
    for marker in data["markers"]:
        if marker["role"] == "check":
            marker["corners_cm"] = [[x + 1., y] for x, y in marker["corners_cm"]]
    config = RegistrationConfig.model_validate(data)
    state = RegistrationMonitor(config).observe(image, session_id="dry", sequence=0, t_s=0,
                                                 context=config.context.model_dump())
    assert state["state"] == "VALIDATION_FAILED"
    assert "independent" in state["reason"]
    assert config.max_error_cm == .5


@pytest.mark.parametrize("change", ["unknown_scale", "wrong_plane", "duplicate_ids", "check_reuse",
                                    "unsupported_water", "nonsimple", "nan", "wider_tolerance"])
def test_bad_survey_contract_rejected_before_detection(change):
    data = synthetic_config().model_dump()
    if change == "unknown_scale":
        data["references_surveyed"] = False
    elif change == "wrong_plane":
        data["reference_plane"] = "tray_bottom"
    elif change == "duplicate_ids":
        data["markers"][1]["id"] = 0
    elif change == "check_reuse":
        data["markers"][4]["corners_cm"] = data["markers"][0]["corners_cm"]
    elif change == "unsupported_water":
        data["water_polygon_cm"][0] = [-10., 0.]
    elif change == "nonsimple":
        data["water_polygon_cm"] = [[0., 0.], [40., 30.], [0., 30.], [40., 0.]]
    elif change == "nan":
        data["markers"][0]["corners_cm"][0] = [float("nan"), 0.]
    else:
        data["max_error_cm"] = 1.
    with pytest.raises(ValidationError):
        RegistrationConfig.model_validate(data)


@pytest.mark.parametrize("change", ["session", "resolution", "waterline_id", "layout_id",
                                    "flow_configuration_id", "token_class_id", "gap", "backwards"])
def test_context_and_capture_changes_latch_stale(scene, change):
    config, image, _ = scene
    monitor = stable(config, image)
    kwargs = {"session_id": "dry", "sequence": 3, "t_s": 1.5,
              "context": config.context.model_dump()}
    if change == "session":
        kwargs["session_id"] = "new"
    elif change == "resolution":
        image = cv2.resize(image, (520, 420))
    elif change == "gap":
        kwargs["t_s"] = 3.
    elif change == "backwards":
        kwargs["sequence"] = 0
    else:
        kwargs["context"][change] = "changed"
    result = monitor.observe(image, **kwargs)
    assert result["state"] == "MOVED_STALE" and not result["mapping_current"]


def test_green_decoy_black_shadow_and_moved_filter_do_not_redefine_geometry(scene):
    config, image, _ = scene
    proposal = propose(image, config, "dry")
    cv2.circle(image, (300, 300), 20, (0, 180, 0), -1)  # Green non-filter.
    cv2.circle(image, (400, 300), 20, (0, 0, 0), -1)  # Black token shadow.
    layers = geometry_layers(image, proposal, config)
    assert layers["tray_boundary"]["status"] == "CANDIDATE"
    assert len(layers["filter_border"]["candidates"]) == 1
    monitor = stable(config, image)
    monitor.approve(monitor.snapshot()["proposal_id"], ["filter_border"])
    image[310:530, 590:650] = 235  # Erase declared filter.
    cv2.rectangle(image, (700, 320), (740, 520), (30, 170, 30), 3)
    state = monitor.observe(image, session_id="dry", sequence=3, t_s=1.5,
                             context=config.context.model_dump())
    assert state["state"] == "MOVED_STALE" and "filter_border" in state["reason"]


def test_real_outline_is_retained_and_not_rectangularized(scene):
    config, image, _ = scene
    data = config.model_dump()
    data["water_polygon_cm"] = [[0., 0.], [40., 0.], [40., 30.], [20., 30.],
                                [20., 25.], [0., 25.]]
    data["expected_filter_polygon_cm"] = None
    config = RegistrationConfig.model_validate(data)
    result = propose(image, config, "dry")
    assert len(result["water_polygon_px"]) == 6
    assert contour_distance(config.water_polygon_cm, [[0, 0], [40, 0], [40, 30], [0, 30]]) >= 5


def test_bounded_frame_work_no_repeated_frames_counted_and_no_early_approval(scene):
    config, image, _ = scene
    monitor = RegistrationMonitor(config)
    first = monitor.observe(image, session_id="dry", sequence=0, t_s=0,
                             context=config.context.model_dump())
    with pytest.raises(ValueError):
        monitor.approve(first["proposal_id"])
    for i in range(1, 5):
        monitor.observe(image, session_id="dry", sequence=i, t_s=i * .05,
                        context=config.context.model_dump())
    assert monitor.stable_frames == 1
    with pytest.raises(ValueError, match="bounded"):
        detect_references(np.zeros((1081, 1920, 3), np.uint8))


def test_mapping_version_breaks_track_without_changing_old_points():
    tracker = SingleTokenTracker()
    cal = {"homography_image_to_cm": [[.1, 0, 0], [0, .1, 0], [0, 0, 1]], "calibration_id": "one"}
    detection = [{"pixel_x": 10, "pixel_y": 20}]
    first = tracker.update(detection, 0, cal)
    original = copy.deepcopy(first)
    second = tracker.update(detection, .1, {**cal, "calibration_id": "two"})
    assert second["track_id"] != first["track_id"] and second["association_break"]
    assert first == original


def test_dry_rehearsal_is_deterministic_and_has_no_capture_or_provider(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("Dry rehearsal attempted capture/provider I/O")
    import httpx
    monkeypatch.setattr(cv2, "VideoCapture", forbidden)
    monkeypatch.setattr(httpx.Client, "request", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    a, b = rehearse(tmp_path / "a"), rehearse(tmp_path / "b")
    assert a == b and a["physical_accuracy_validated"] is False
    assert [s["status"]["state"] for s in a["steps"]] == [
        "STABLE_APPROVED", "MOVED_STALE", "CANDIDATE_MAPPING", "MOVED_STALE"]
