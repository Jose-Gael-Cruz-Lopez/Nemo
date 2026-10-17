"""Software-only image/vector contracts; never physical validation."""

import json

import cv2
import numpy as np
import pytest

from apps.vision.reeftrace_vision import vector_diagnostic as diagnostic


def _calibration():
    return diagnostic.fit_homography(
        [[0, 0], [99, 0], [99, 99], [0, 99]],
        [[0, 0], [9.9, 0], [9.9, 9.9], [0, 9.9]],
        [[10, 10], [50, 40], [80, 70]], [[1, 1], [5, 4], [8, 7]],
        image_size_px=[100, 100], camera_session_id=diagnostic.SESSION_ID,
    )


def _frame(*centers):
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    for center in centers:
        cv2.circle(image, center, 4, (0, 0, 255), -1)
    return image


def test_real_extractor_runs_and_known_velocity_discrepancy_is_preserved(monkeypatch):
    original, calls = diagnostic.detect_red, []

    def spy(frame):
        calls.append(frame.shape)
        return original(frame)

    monkeypatch.setattr(diagnostic, "detect_red", spy)
    report = diagnostic.run_synthetic_vector_diagnostic()
    assert calls == [(240, 400, 3)] * 8
    assert report["calibration"]["approved"]
    assert report["calibration"]["validation_count"] == 3
    assert report["metrics"]["sample_count"] == 4
    assert report["metrics"]["vector_rmse_cm_s"] == pytest.approx(1)
    assert report["metrics"]["mean_speed_bias_cm_s"] == pytest.approx(-1)
    assert report["metrics"]["mean_absolute_speed_error_cm_s"] == pytest.approx(1)
    assert report["metrics"]["mean_direction_error_deg"] == pytest.approx(0)
    for vector in report["vectors"]:
        assert vector["observed_vx_cm_s"] == pytest.approx(5)
        assert vector["predicted_vx_cm_s"] == 4
        assert vector["residual_vx_cm_s"] == pytest.approx(-1)
        assert vector["observed_vy_cm_s"] == pytest.approx(0, abs=1e-10)


def test_replay_is_deterministic_despite_production_tracker_uuid():
    first = json.dumps(diagnostic.run_synthetic_vector_diagnostic(), sort_keys=True, allow_nan=False)
    second = json.dumps(diagnostic.run_synthetic_vector_diagnostic(), sort_keys=True, allow_nan=False)
    assert first == second


def test_no_device_opened_and_all_artifacts_remain_synthetic(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("A synthetic replay must never open a capture device")

    monkeypatch.setattr(cv2, "VideoCapture", forbidden)
    report = diagnostic.run_synthetic_vector_diagnostic()
    assert report["data_origin"] == diagnostic.ORIGIN
    assert report["physical_validation"] is False
    assert report["camera_started"] is False
    assert report["hardware_actuation"] is False
    assert report["model"]["frozen_before_scoring"] is True
    assert report["model"]["trained"] is False
    assert report["model"]["promotion_performed"] is False
    assert report["admission"]["measured_profile_admitted"] is False
    assert report["admission"]["store_written"] is False
    for artifact in report["frames"] + report["observations"] + report["vectors"]:
        assert artifact["data_origin"] == diagnostic.ORIGIN
        assert artifact["physical_validation"] is False


@pytest.mark.parametrize("interruption,reason", [([], "NO_DETECTION"),
                                                ([(20, 20), (70, 70)], "MULTIPLE_TOKENS")])
def test_missing_or_ambiguous_image_never_creates_bridged_vector(interruption, reason):
    frames = [_frame((20, 20)), _frame(*interruption), _frame((30, 20)), _frame((40, 20))]
    observations, samples, _ = diagnostic._extract_sequence(frames, [0, 0.2, 0.4, 0.6], _calibration())
    assert observations[1]["observed"] is False
    assert observations[1]["reason"] == reason
    assert observations[0]["track_id"] != observations[2]["track_id"]
    assert len(samples) == 1
    assert samples[0]["vx_cm_s"] == pytest.approx(5)
    assert samples[0]["x_cm"] == pytest.approx(3.5)


def test_actual_time_difference_is_used_and_long_gap_not_interpolated():
    frames = [_frame((20, 20)), _frame((30, 20)), _frame((40, 20)), _frame((50, 20))]
    _, samples, _ = diagnostic._extract_sequence(frames, [0, 0.25, 1.0, 1.25], _calibration())
    assert len(samples) == 2
    assert [s["vx_cm_s"] for s in samples] == pytest.approx([4, 4])


@pytest.mark.parametrize("times", [[0, 0], [0.2, 0], [0, float("nan")], [-0.1, 0.2]])
def test_invalid_time_offsets_rejected(times):
    with pytest.raises(ValueError, match="monotonic"):
        diagnostic._extract_sequence([_frame((20, 20))] * 2, times, _calibration())


def test_frame_budget_and_image_bounds():
    with pytest.raises(ValueError, match="1..512"):
        diagnostic._extract_sequence([_frame()] * 513, np.arange(513) * 0.2, _calibration())
    with pytest.raises(ValueError, match="512 pixels"):
        diagnostic._extract_sequence([np.zeros((513, 2, 3), np.uint8)], [0], _calibration())


def test_direction_undefined_for_zero_speed_and_opposite_vectors_are_180_degrees():
    samples = [{"x_cm": 0, "y_cm": 0, "vx_cm_s": 0, "vy_cm_s": 0},
               {"x_cm": 1, "y_cm": 0, "vx_cm_s": 1, "vy_cm_s": 0}]
    vectors, metrics = diagnostic._compare_vectors(samples, [[1, 0], [-1, 0]])
    assert vectors[0]["direction_error_deg"] is None
    assert vectors[1]["direction_error_deg"] == pytest.approx(180)
    assert metrics["direction_defined_count"] == 1
    assert metrics["mean_direction_error_deg"] == pytest.approx(180)


def test_no_vectors_has_no_invented_score():
    vectors, metrics = diagnostic._compare_vectors([], np.empty((0, 2)))
    assert vectors == [] and metrics["sample_count"] == 0
    assert metrics["vector_rmse_cm_s"] is None
    assert metrics["mean_direction_error_deg"] is None


@pytest.mark.parametrize("field", ["x_cm", "y_cm", "vx_cm_s", "vy_cm_s"])
@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_observed_vectors_or_positions_are_rejected(field, invalid):
    sample = {"x_cm": 1, "y_cm": 2, "vx_cm_s": 3, "vy_cm_s": 4, field: invalid}
    with pytest.raises(ValueError, match="Observed velocities and sample coordinates must be finite"):
        diagnostic._compare_vectors([sample], [[3, 4]])


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_predictions_are_rejected(invalid):
    sample = {"x_cm": 1, "y_cm": 2, "vx_cm_s": 3, "vy_cm_s": 4}
    with pytest.raises(ValueError, match="finite two-component velocity"):
        diagnostic._compare_vectors([sample], [[invalid, 4]])
