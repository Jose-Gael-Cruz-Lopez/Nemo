"""Bounded, irregular-time constant-velocity Kalman prediction in SI units.

Grok supplied a static draft; local review corrected its gain solve and added
strict numerical boundaries. The first two independent isotropic position
errors initialize a correlated state at t1, assuming constant first-interval
velocity. Those assumptions are not established for NOAA's interpolated fixes.
No fitting, smoothing, future measurement updates or source inference occurs.
"""

from __future__ import annotations

import math
from numbers import Real

import numpy as np

MAX_LOCAL_M = 50_000.0
MIN_DT_S = 1e-6
MAX_PREFIX_S = 7 * 86400.0
MAX_HORIZON_S = 24 * 3600.0
POSITION_STD_M = 100.0
ACCELERATION_SPECTRAL_DENSITY_M2_S3 = 1e-6
COV_ABS_TOL = 1e-8
COV_REL_TOL = 1e-10


def _array(value, name, ndim, maximum):
    try:
        raw = np.asarray(value, dtype=object)
    except (ValueError, TypeError) as error:
        raise ValueError(f"{name} needs a rectangular numeric array") from error
    if raw.ndim != ndim or not 1 <= raw.size <= maximum:
        raise ValueError(f"{name} has an invalid shape or bounded count")
    if any(isinstance(item, (bool, np.bool_)) or not isinstance(item, Real)
           for item in raw.flat):
        raise ValueError(f"{name} requires real numbers, not booleans or strings")
    try:
        result = raw.astype(float)
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError(f"{name} requires bounded finite real numbers") from error
    if not np.isfinite(result).all():
        raise ValueError(f"{name} requires finite values")
    return result


def _positive(value, name, maximum):
    if (isinstance(value, (bool, np.bool_)) or not isinstance(value, Real)
            or not math.isfinite(value) or not 1e-15 <= value <= maximum):
        raise ValueError(f"{name} must be positive finite within its numerical budget")
    return float(value)


def _check_cov(value, dimension, name):
    covariance = np.asarray(value, dtype=float)
    if covariance.shape != (dimension, dimension) or not np.isfinite(covariance).all():
        raise ValueError(f"{name} requires a finite square covariance")
    scale = max(1.0, float(np.abs(covariance).max()))
    tolerance = COV_ABS_TOL + COV_REL_TOL * scale
    if float(np.abs(covariance - covariance.T).max()) > tolerance:
        raise ValueError(f"{name} covariance is not symmetric")
    covariance = (covariance + covariance.T) / 2
    if float(np.linalg.eigvalsh(covariance).min()) < -tolerance:
        raise ValueError(f"{name} covariance is not positive semidefinite")
    return covariance


def _check_state(value):
    if (value.shape != (4,) or not np.isfinite(value).all() or float(np.abs(value[:2]).max()) > MAX_LOCAL_M
            or float(np.linalg.norm(value[:2])) > MAX_LOCAL_M):
        raise ValueError("State position exceeds its finite 50 km local domain")


def transition_and_noise(dt, spectral_density):
    """Continuous white acceleration: q has units m²/s³, not m²/s⁴."""
    if not math.isfinite(dt) or not MIN_DT_S <= dt <= MAX_PREFIX_S:
        raise ValueError("Every transition requires dt >=1e-6 s within the duration budget")
    transition = np.eye(4)
    transition[0, 2] = transition[1, 3] = dt
    noise = spectral_density * np.block([
        [dt**3 / 3 * np.eye(2), dt**2 / 2 * np.eye(2)],
        [dt**2 / 2 * np.eye(2), dt * np.eye(2)],
    ])
    return transition, _check_cov(noise, 4, "process")


def _initialize(first_positions, dt, variance):
    state = np.r_[first_positions[1], (first_positions[1] - first_positions[0]) / dt]
    covariance = np.block([
        [variance * np.eye(2), variance / dt * np.eye(2)],
        [variance / dt * np.eye(2), 2 * variance / dt**2 * np.eye(2)],
    ])
    _check_state(state)
    return state, _check_cov(covariance, 4, "initial")


def _fit_and_forecast(prefix_times_s, prefix_xy_m, forecast_times_s, *,
                      position_std_m=POSITION_STD_M,
                      acceleration_spectral_density_m2_s3=ACCELERATION_SPECTRAL_DENSITY_M2_S3):
    times = _array(prefix_times_s, "prefix_times_s", 1, 100)
    positions = _array(prefix_xy_m, "prefix_xy_m", 2, 200)
    future = _array(forecast_times_s, "forecast_times_s", 1, 12)
    if not 8 <= len(times) <= 100 or positions.shape != (len(times), 2):
        raise ValueError("Require 8..100 prefix times and matching (n,2) positions")
    if np.abs(times).max() > 1e12 or np.abs(future).max() > 1e12:
        raise ValueError("Time offsets exceed the finite representation budget")
    intervals = np.r_[np.diff(times), future[0] - times[-1], np.diff(future)]
    if not np.isfinite(intervals).all() or np.any(intervals < MIN_DT_S):
        raise ValueError("All prefix and forecast transitions, including the first, require dt >=1e-6 s")
    if times[0] < 0 or times[-1] - times[0] > MAX_PREFIX_S or future[-1] - times[-1] > MAX_HORIZON_S:
        raise ValueError("Require nonnegative times, <=7-day prefix and <=24-hour future horizon")
    if float(np.abs(positions).max()) > MAX_LOCAL_M or float(np.linalg.norm(positions, axis=1).max()) > MAX_LOCAL_M:
        raise ValueError("Prefix positions exceed the 50 km local domain")
    sigma = _positive(position_std_m, "position_std_m", MAX_LOCAL_M)
    q = _positive(acceleration_spectral_density_m2_s3, "acceleration spectral density", 1e6)
    variance = sigma**2
    state, covariance = _initialize(positions[:2], times[1] - times[0], variance)
    measurement = np.eye(4)[:2]
    noise = variance * np.eye(2)
    for index in range(2, len(times)):
        transition, process = transition_and_noise(times[index] - times[index - 1], q)
        state = transition @ state
        _check_state(state)
        covariance = _check_cov(transition @ covariance @ transition.T + process, 4, "predicted")
        innovation_covariance = _check_cov(measurement @ covariance @ measurement.T + noise, 2, "innovation")
        if float(np.linalg.eigvalsh(innovation_covariance).min()) <= 0:
            raise ValueError("Innovation covariance must be positive definite")
        # S is 2x2 and H@P is 2x4. Do not transpose the solve's RHS to 4x2.
        gain = np.linalg.solve(innovation_covariance, measurement @ covariance).T
        state = state + gain @ (positions[index] - measurement @ state)
        _check_state(state)
        complement = np.eye(4) - gain @ measurement
        covariance = _check_cov(complement @ covariance @ complement.T + gain @ noise @ gain.T,
                                4, "corrected")
    anchor_state, anchor_covariance = state.copy(), covariance.copy()
    means, covariances, previous = [], [], times[-1]
    for timestamp in future:
        transition, process = transition_and_noise(timestamp - previous, q)
        state = transition @ state
        _check_state(state)
        covariance = _check_cov(transition @ covariance @ transition.T + process, 4, "forecast")
        means.append(state[:2].copy())
        covariances.append(_check_cov(covariance[:2, :2], 2, "position"))
        previous = timestamp
    return np.asarray(means), np.asarray(covariances), anchor_state, anchor_covariance


def kalman_cv_forecast(prefix_times_s, prefix_xy_m, forecast_times_s, *,
                       position_std_m=POSITION_STD_M,
                       acceleration_spectral_density_m2_s3=ACCELERATION_SPECTRAL_DENSITY_M2_S3):
    """Return free-running means(h,2), position covariances(h,2,2), never confidence.

    Prefix: 8..100 finite points; future: 1..12 times; every dt >=1e-6 s,
    prefix <=7 days, horizon <=24 hours, positions/mean states <=50 km. Frozen
    application defaults are arbitrary assumptions, not fitted NOAA uncertainties.
    """
    means, covariance, _, _ = _fit_and_forecast(prefix_times_s, prefix_xy_m, forecast_times_s,
        position_std_m=position_std_m,
        acceleration_spectral_density_m2_s3=acceleration_spectral_density_m2_s3)
    return means, covariance
