"""Numerical contracts on synthetic SI trajectories; no NOAA scoring or devices."""

from __future__ import annotations

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import kalman


def inputs():
    times = np.arange(8, dtype=float)
    positions = np.c_[times * .2, times * -.1]
    return times, positions, np.arange(8, 11, dtype=float)


def test_constant_velocity_means_covariances_and_inputs_are_preserved():
    times, positions, future = inputs()
    before = [value.copy() for value in (times, positions, future)]
    means, covariance = kalman.kalman_cv_forecast(times, positions, future)
    np.testing.assert_allclose(means, np.c_[future * .2, future * -.1], atol=1e-10)
    assert means.shape == (3, 2) and covariance.shape == (3, 2, 2)
    assert np.isfinite(covariance).all()
    for matrix in covariance:
        np.testing.assert_allclose(matrix, matrix.T, rtol=0, atol=1e-8)
        assert np.linalg.eigvalsh(matrix).min() >= -1e-8
    for current, old in zip((times, positions, future), before, strict=True):
        np.testing.assert_array_equal(current, old)


def test_irregular_actual_dt_and_integration_noise_convention():
    times = np.array([0, .11, .25, .39, .58, .72, .91, 1.2])
    future = np.array([1.31, 1.5, 1.93])
    means, covariance = kalman.kalman_cv_forecast(times, np.c_[times * .03, times * .02], future)
    np.testing.assert_allclose(means, np.c_[future * .03, future * .02], atol=1e-10)
    transition, noise = kalman.transition_and_noise(.2, 3.0)
    assert transition[0, 2] == transition[1, 3] == .2
    assert noise[0, 0] == pytest.approx(3 * .2**3 / 3)
    assert noise[0, 2] == pytest.approx(3 * .2**2 / 2)
    assert noise[2, 2] == pytest.approx(3 * .2)
    assert covariance[1, 0, 0] > covariance[0, 0, 0]


def test_initialization_at_second_observation_has_correlated_iid_error_covariance():
    points = np.array([[1., 2.], [5., 8.]])
    state, covariance = kalman._initialize(points, 2, 9)
    np.testing.assert_array_equal(state, [5, 8, 2, 3])
    np.testing.assert_array_equal(covariance[:2, :2], 9 * np.eye(2))
    np.testing.assert_array_equal(covariance[:2, 2:], 4.5 * np.eye(2))
    np.testing.assert_array_equal(covariance[2:, 2:], 4.5 * np.eye(2))


def test_each_prefix_measurement_is_used_once_and_gain_solve_has_correct_shapes(monkeypatch):
    original, shapes = np.linalg.solve, []
    def solve(matrix, rhs):
        shapes.append((matrix.shape, rhs.shape))
        return original(matrix, rhs)
    monkeypatch.setattr(np.linalg, "solve", solve)
    kalman.kalman_cv_forecast(*inputs())
    assert shapes == [((2, 2), (2, 4))] * 6  # Prefix indices 2..7, never future times.


def test_forecast_starts_from_filtered_state_and_later_prefix_points_affect_it():
    times, positions, future = inputs()
    positions[-1, 0] += .2
    means, _, state, _ = kalman._fit_and_forecast(times, positions, future)
    assert state[0] != positions[-1, 0]
    np.testing.assert_allclose(means[0], state[:2] + (future[0] - times[-1]) * state[2:])
    original, _ = kalman.kalman_cv_forecast(*inputs())
    assert not np.allclose(means, original)


@pytest.mark.parametrize("future", [[], [7], [7 + 5e-7], [8, 8], [9, 8], [8, float("nan")], [8] * 13])
def test_invalid_forecast_times_rejected_including_empty_and_first_tiny_dt(future):
    times, positions, _ = inputs()
    with pytest.raises(ValueError):
        kalman.kalman_cv_forecast(times, positions, future)


@pytest.mark.parametrize("change", ["short", "many", "duplicate", "tiny_dt", "long_prefix", "long_future",
    "nan", "infinity", "outside", "string", "bool", "negative_time", "huge_integer"])
def test_bad_prefix_shapes_types_time_budgets_and_domain_fail_before_forecasting(change):
    times, positions, future = inputs()
    if change == "short":
        times, positions = times[:7], positions[:7]
    elif change == "many":
        times, positions, future = np.arange(101), np.zeros((101, 2)), [101]
    elif change == "duplicate":
        times[3] = times[2]
    elif change == "tiny_dt":
        times[1] = 5e-7
    elif change == "long_prefix":
        times = times * 100_000
        future = [times[-1] + 1]
    elif change == "long_future":
        future = [times[-1] + 86401]
    elif change == "nan":
        positions[3, 0] = np.nan
    elif change == "infinity":
        times[3] = np.inf
    elif change == "outside":
        positions[3, 0] = 50001
    elif change == "string":
        times = [*times[:-1], "7"]
    elif change == "bool":
        times = [*times[:-1], True]
    elif change == "negative_time":
        times[0] = -1
    else:
        positions = positions.astype(object)
        positions[0, 0] = 10**1000
    with pytest.raises(ValueError):
        kalman.kalman_cv_forecast(times, positions, future)


@pytest.mark.parametrize("name,value", [("position_std_m", 0), ("position_std_m", True),
    ("position_std_m", "100"), ("position_std_m", float("nan")),
    ("acceleration_spectral_density_m2_s3", -1), ("acceleration_spectral_density_m2_s3", float("inf"))])
def test_noise_values_are_explicit_positive_finite_assumptions(name, value):
    with pytest.raises(ValueError):
        kalman.kalman_cv_forecast(*inputs(), **{name: value})


def test_out_of_domain_free_run_fails_instead_of_clipping_mean_or_shrinking_covariance():
    times = np.arange(8, dtype=float)
    positions = np.c_[49_990 + times, np.zeros(8)]
    with pytest.raises(ValueError, match="50 km"):
        kalman.kalman_cv_forecast(times, positions, [100])


@pytest.mark.parametrize("covariance", [np.full((4, 4), np.nan), np.diag([-1., 1, 1, 1]),
    np.array([[1, 1, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])])
def test_nonfinite_indefinite_and_asymmetric_covariance_are_rejected(covariance):
    with pytest.raises(ValueError):
        kalman._check_cov(covariance, 4, "test")
