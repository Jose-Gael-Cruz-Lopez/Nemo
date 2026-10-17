"""Numerical regressions for irregular forcing times, never new field evidence."""

from datetime import UTC, datetime, timedelta
from fractions import Fraction

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import advection
from apps.ocean.reeftrace_ocean.field import OceanField, _wgs84_metres_per_degree

EPOCH = datetime(2026, 10, 17, tzinfo=UTC)
METRES_LON, _ = _wgs84_metres_per_degree(0)


def forcing(times=(0, 650, 1400), speeds=(0, 1, 0)):
    seconds = np.asarray(times, dtype=float)
    shape = (len(times), 2, 2)
    return OceanField(
        np.datetime64("2026-10-17T00:00:00", "ns")
        + np.rint(seconds * 1_000_000_000).astype("timedelta64[ns]"),
        np.array([-1.0, 1.0]), np.array([-1.0, 1.0]),
        np.broadcast_to(np.asarray(speeds, dtype=float)[:, None, None], shape).copy(),
        np.zeros(shape), np.ones(shape, dtype=bool), 0.25,
        {"velocity_units": "m/s", "product": "SYNTHETIC_TIME_KNOT_REGRESSION"},
    )


def exact_integral(times, speeds, start, end):
    """Exact trapezoid areas of the declared piecewise-linear time function."""
    start, end = Fraction(str(start)), Fraction(str(end))
    area = Fraction(0)
    for a, b, u0, u1 in zip(times[:-1], times[1:], speeds[:-1], speeds[1:], strict=True):
        a, b, u0, u1 = (Fraction(str(value)) for value in (a, b, u0, u1))
        left, right = max(a, start), min(b, end)
        if right > left:
            slope = (u1 - u0) / (b - a)
            left_u, right_u = u0 + slope * (left - a), u0 + slope * (right - a)
            area += (right - left) * (left_u + right_u) / 2
    return area


def integrate(source=None, *, start=0, horizon=1000, step=300, output=1000):
    return advection.advect_current(
        source or forcing(), latitude_deg=0, longitude_deg=0,
        start_time_utc=EPOCH + timedelta(seconds=start),
        horizon_s=horizon, step_s=step, output_step_s=output,
    )


@pytest.mark.parametrize("start,horizon,area", [
    (0, 1000, Fraction(1780, 3)),
    (100, 900, Fraction(22840, 39)),
    (100, 1000, Fraction(8220, 13)),
    (650, 450, Fraction(315)),
])
def test_rk4_integrates_each_linear_time_piece_with_arbitrary_start(start, horizon, area):
    # These exact areas independently verify both the equation and horizon meaning:
    # a 900-second horizon from t=100 ends at t=1000, not t=900 or t=1100.
    assert exact_integral((0, 650, 1400), (0, 1, 0), start, start + horizon) == area
    result = integrate(start=start, horizon=horizon)
    assert result["status"] == "COMPLETED"
    assert result["completed_horizon_s"] == horizon
    assert result["track"][-1]["longitude_deg"] * METRES_LON == pytest.approx(
        float(area), abs=1e-9,
    )
    assert result["solver"]["forcing_time_knots_aligned"] is True
    assert result["solver"]["method"] == "RK4_WGS84_METRIC_DERIVATIVES"


def test_several_irregular_knots_and_output_boundaries_preserve_exact_time_integral():
    times, speeds = (0, 650, 1400, 1800), (0.2, 1, 0.1, 0.8)
    result = integrate(forcing(times, speeds), start=123, horizon=1500, output=479)
    assert result["status"] == "COMPLETED"
    assert [point["elapsed_s"] for point in result["track"]] == [0, 479, 958, 1437, 1500]
    for point in result["track"]:
        area = exact_integral(times, speeds, 123, 123 + point["elapsed_s"])
        assert point["longitude_deg"] * METRES_LON == pytest.approx(float(area), abs=1e-9)


@pytest.mark.parametrize("start,horizon,completed", [(0, 1800, 1400), (100, 1800, 1300)])
def test_unaligned_forcing_end_retains_the_entire_supported_prefix(start, horizon, completed):
    result = integrate(start=start, horizon=horizon, output=900)
    assert result["status"] == "PARTIAL"
    assert result["reason_code"] == "OUTSIDE_FORCING_TIME"
    assert result["completed_horizon_s"] == completed
    assert result["track"][-1]["elapsed_s"] == completed
    assert result["track"][-1]["time_utc"] == "2026-10-17T00:23:20Z"
    assert result["track"][-1]["longitude_deg"] * METRES_LON == pytest.approx(
        float(exact_integral((0, 650, 1400), (0, 1, 0), start, 1400)), abs=1e-9,
    )


def test_request_ending_exactly_at_last_forcing_time_is_completed():
    result = integrate(horizon=1400, output=900)
    assert result["status"] == "COMPLETED"
    assert result["reason_code"] is None
    assert result["completed_horizon_s"] == 1400
    assert result["track"][-1]["longitude_deg"] * METRES_LON == pytest.approx(700)


def test_request_starting_at_forcing_end_has_no_invented_future():
    result = integrate(start=1400, horizon=100)
    assert result["status"] == "UNSUPPORTED"
    assert result["reason_code"] == "OUTSIDE_FORCING_TIME"
    assert result["completed_horizon_s"] == result["accepted_steps"] == 0
    assert len(result["track"]) == 1
    assert result["track"][0]["elapsed_s"] == result["track"][0]["longitude_deg"] == 0


def test_exact_valid_knot_is_allowed_but_does_not_bridge_a_masked_future_interval():
    source = forcing()
    source.valid_mask[-1] = False
    source.eastward_m_s[-1] = np.nan
    at_knot = integrate(source, horizon=650)
    after_knot = integrate(source, horizon=1000)
    assert at_knot["status"] == "COMPLETED"
    assert at_knot["completed_horizon_s"] == 650
    assert after_knot["status"] == "PARTIAL"
    assert after_knot["reason_code"] == "MASKED_CURRENT_CELL"
    assert after_knot["completed_horizon_s"] == 650
    assert after_knot["track"][-1] == at_knot["track"][-1]


def test_masked_arrival_knot_never_accepts_the_future_position():
    source = forcing()
    source.valid_mask[1] = False
    source.eastward_m_s[1] = np.nan
    result = integrate(source, horizon=650)
    # Every t>0 interpolation needs the masked t=650 sample, even before arrival.
    assert result["status"] == "UNSUPPORTED"
    assert result["reason_code"] == "MASKED_CURRENT_CELL"
    assert result["completed_horizon_s"] == result["accepted_steps"] == 0
    assert len(result["track"]) == 1


def test_positive_submicrosecond_steps_integrate_position_instead_of_skipping_time():
    result = integrate(forcing((0, 0.000001, 0.000002), (1, 1, 1)),
                       horizon=0.000002, output=0.000002)
    assert result["status"] == "COMPLETED"
    assert result["completed_horizon_s"] == 0.000002
    assert result["accepted_steps"] == 4
    assert result["track"][-1]["longitude_deg"] * METRES_LON == pytest.approx(
        0.000002, abs=1e-18,
    )


def test_local_time_progress_integrates_even_when_distant_epoch_cannot_resolve_the_increment():
    source = forcing((0, 1), (1, 1))
    # Float seconds from a distant epoch cannot distinguish a nanosecond increment
    # at this start. Sampling and integration instead share a local elapsed axis;
    # the positive duration must still advance position, not be skipped or censored.
    source = OceanField(
        np.array(["1900-01-01", "2090-01-01"], dtype="datetime64[ns]"),
        source.longitude_deg, source.latitude_deg, source.eastward_m_s,
        source.northward_m_s, source.valid_mask, source.selected_depth_m, source.metadata,
    )
    result = integrate(source, horizon=1e-9, output=1e-9)
    assert result["status"] == "COMPLETED"
    assert result["reason_code"] is None
    assert result["completed_horizon_s"] == 1e-9
    assert result["accepted_steps"] == 1
    assert len(result["track"]) == 2
    assert result["track"][-1]["longitude_deg"] * METRES_LON == pytest.approx(1e-9, abs=1e-22)


def test_forcing_knot_splits_are_included_in_conservative_preflight_budget(monkeypatch):
    # Four max-size intervals plus one output bound alone would fit this limit;
    # the additional forcing-knot split must be accounted for before integration.
    monkeypatch.setattr(advection, "MAX_STEPS", 5)
    with pytest.raises(ValueError, match="bounded step budget"):
        integrate()


@pytest.mark.parametrize("origin", ["1600-01-01", "1800-01-01", "2201-01-01", "2500-01-01"])
def test_direct_sampler_rejects_origins_outside_its_bounded_calendar(origin):
    # A direct caller does not pass through advect_current's _start validation.
    # Reject before subtracting dates that could exceed the timedelta64 range.
    with pytest.raises(ValueError, match="calendar"):
        advection.CurrentSampler(forcing(), time_origin=np.datetime64(origin))


MICROSECOND_KNOTS = (0, 347304243, 374526192, 412218073, 895964114)


def microsecond_forcing(speeds=(0.5, 0.5, 0.5, 0.5, 0.5)):
    """Integer UTC coordinates, independent of the solver's floating time axis."""
    when = (np.datetime64("2026-10-17T00:00:00", "us")
            + np.asarray(MICROSECOND_KNOTS).astype("timedelta64[us]"))
    shape = (len(when), 2, 2)
    return OceanField(
        when, np.array([-1.0, 1.0]), np.array([-1.0, 1.0]),
        np.broadcast_to(np.asarray(speeds)[:, None, None], shape).copy(),
        np.zeros(shape), np.ones(shape, dtype=bool), 0.25,
        {"velocity_units": "m/s", "product": "SYNTHETIC_FRACTIONAL_START_REGRESSION"},
    )


def test_fractional_start_reaches_supported_last_microsecond_knot_without_false_censoring():
    # Previously offset + elapsed rounded one ULP past the last forcing knot.
    # The supported final interval was then discarded at elapsed=559.3726975.
    result = integrate(microsecond_forcing(), start=329.229483,
                       horizon=566.734631, step=200, output=566.734631)
    assert result["status"] == "COMPLETED"
    assert result["reason_code"] is None
    assert result["completed_horizon_s"] == 566.734631
    assert result["track"][-1]["elapsed_s"] == 566.734631
    assert result["track"][-1]["time_utc"] == "2026-10-17T00:14:55.964114Z"
    assert result["track"][-1]["longitude_deg"] * METRES_LON == pytest.approx(
        283.3673155, abs=1e-9,
    )


def test_every_output_point_matches_constant_speed_integral_with_fractional_time_origin():
    result = integrate(microsecond_forcing(), start=329.229483,
                       horizon=566.734631, step=200, output=100)
    assert result["status"] == "COMPLETED"
    assert [p["elapsed_s"] for p in result["track"]] == [0, 100, 200, 300, 400, 500, 566.734631]
    for point in result["track"]:
        assert point["longitude_deg"] * METRES_LON == pytest.approx(
            point["elapsed_s"] * 0.5, abs=1e-9,
        )


@pytest.mark.parametrize("start_us,end_us,expected", [
    (329229483, 895964114, Fraction(1024621662902407, 19135220000000)),
    (329229483, 412218073, Fraction(280896158484603, 9567610000000)),
    (374526192, 895964114, Fraction(149205421, 5000000)),
])
def test_fractional_signed_velocity_knots_have_independently_verified_exact_integrals(
    start_us, end_us, expected,
):
    speeds = (Fraction(1, 5), Fraction(4, 5), Fraction(-1, 10), Fraction(2, 5), Fraction(-3, 10))
    exact = exact_integral([Fraction(knot, 1_000_000) for knot in MICROSECOND_KNOTS], speeds,
                          Fraction(start_us, 1_000_000), Fraction(end_us, 1_000_000))
    assert exact == expected  # Verify proposed values independently before using them.
    duration = (end_us - start_us) / 1_000_000
    result = integrate(microsecond_forcing(tuple(map(float, speeds))),
                       start=start_us / 1_000_000, horizon=duration, step=200, output=100)
    assert result["status"] == "COMPLETED"
    assert result["completed_horizon_s"] == duration
    assert result["track"][-1]["longitude_deg"] * METRES_LON == pytest.approx(float(exact), abs=1e-9)


def test_signed_velocity_partial_run_retains_the_exact_supported_integral():
    speeds = (0.2, 0.8, -0.1, 0.4, -0.3)
    result = integrate(microsecond_forcing(speeds), start=329.229483,
                       horizon=600, step=200, output=100)
    exact = exact_integral([Fraction(knot, 1_000_000) for knot in MICROSECOND_KNOTS], speeds,
                          Fraction(329229483, 1_000_000), Fraction(895964114, 1_000_000))
    assert result["status"] == "PARTIAL"
    assert result["reason_code"] == "OUTSIDE_FORCING_TIME"
    assert result["completed_horizon_s"] == 566.734631
    assert result["track"][-1]["longitude_deg"] * METRES_LON == pytest.approx(float(exact), abs=1e-9)


@pytest.mark.parametrize("start_us", [329229483, 347304243, 374526193, 412218072, 895964113])
def test_fractional_starts_match_independent_piecewise_linear_time_integral(start_us):
    speeds = (0.2, 1.0, 0.1, 0.8, 0.5)
    duration_us = MICROSECOND_KNOTS[-1] - start_us
    start, end = Fraction(start_us, 1_000_000), Fraction(MICROSECOND_KNOTS[-1], 1_000_000)
    area = exact_integral([Fraction(knot, 1_000_000) for knot in MICROSECOND_KNOTS],
                          speeds, start, end)
    result = integrate(microsecond_forcing(speeds), start=float(start),
                       horizon=duration_us / 1_000_000, step=200,
                       output=duration_us / 1_000_000)
    assert result["status"] == "COMPLETED"
    assert result["completed_horizon_s"] == duration_us / 1_000_000
    assert result["track"][-1]["longitude_deg"] * METRES_LON == pytest.approx(
        float(area), abs=1e-9,
    )


def test_rebased_sampler_keeps_default_epoch_and_strict_last_time_boundary():
    source = microsecond_forcing()
    default = advection.CurrentSampler(source)
    start64 = np.datetime64("2026-10-17T00:05:29.229483", "us")
    rebased = advection.CurrentSampler(source, time_origin=start64)
    assert default.epoch == source.time_utc[0]
    assert default.times[0] == 0
    assert rebased.epoch == start64
    assert rebased.times[-1] == 566.734631
    for sampler in (default, rebased):
        assert sampler.sample(0, 0, sampler.times[-1]) == (0.5, 0)
        with pytest.raises(advection._Unsupported, match="OUTSIDE_FORCING_TIME"):
            sampler.sample(0, 0, float(np.nextafter(sampler.times[-1], np.inf)))


def test_fractional_request_beyond_last_knot_retains_the_full_supported_prefix_only():
    result = integrate(microsecond_forcing(), start=329.229483,
                       horizon=566.734632, step=200, output=566.734632)
    assert result["status"] == "PARTIAL"
    assert result["reason_code"] == "OUTSIDE_FORCING_TIME"
    assert result["completed_horizon_s"] == 566.734631
    assert result["track"][-1]["longitude_deg"] * METRES_LON == pytest.approx(
        283.3673155, abs=1e-9,
    )


def test_fractional_rebased_exact_knot_still_requires_only_its_valid_time_slice():
    source = microsecond_forcing()
    source.valid_mask[-1] = False
    source.eastward_m_s[-1] = np.nan
    start_us = 329229483
    duration = (MICROSECOND_KNOTS[-2] - start_us) / 1_000_000
    at_knot = integrate(source, start=start_us / 1_000_000,
                        horizon=duration, step=200, output=duration)
    past_knot = integrate(source, start=start_us / 1_000_000,
                          horizon=duration + 0.000001, step=200, output=duration + 0.000001)
    assert at_knot["status"] == "COMPLETED"
    assert past_knot["status"] == "PARTIAL"
    assert past_knot["reason_code"] == "MASKED_CURRENT_CELL"
    assert past_knot["completed_horizon_s"] == duration
    assert past_knot["track"][-1] == at_knot["track"][-1]
    unsupported = integrate(source, start=MICROSECOND_KNOTS[-2] / 1_000_000,
                            horizon=10, step=200, output=10)
    assert unsupported["status"] == "UNSUPPORTED"
    assert unsupported["reason_code"] == "MASKED_CURRENT_CELL"
    assert unsupported["completed_horizon_s"] == unsupported["accepted_steps"] == 0
    assert len(unsupported["track"]) == 1
    assert unsupported["track"][0]["longitude_deg"] == 0
