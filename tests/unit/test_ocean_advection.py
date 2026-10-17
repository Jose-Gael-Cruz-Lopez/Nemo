"""Current-forced paths follow supplied space/time physics, never cosmetic curves."""

import json
import math
from dataclasses import replace

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean.advection import CurrentSampler, advect_current
from apps.ocean.reeftrace_ocean.field import OceanField, _wgs84_metres_per_degree

START = "2026-10-17T00:00:00Z"
METRES_LON, METRES_LAT = _wgs84_metres_per_degree(0)


def field(*, longitude=(-1.0, 1.0), latitude=(-1.0, 1.0), times=(0, 3600, 7200),
          u=0.25, v=0.0):
    lon = np.asarray(longitude, float)
    lat = np.asarray(latitude, float)
    seconds = np.asarray(times, float)
    shape = (len(seconds), len(lat), len(lon))
    east = np.broadcast_to(u, shape).copy()
    north = np.broadcast_to(v, shape).copy()
    return OceanField(
        np.datetime64("2026-10-17T00:00:00", "us")
        + (seconds * 1_000_000).astype("timedelta64[us]"),
        lon, lat, east, north, np.ones(shape, bool), 0.5,
        {"product": "SYNTHETIC_NUMERICAL_TEST_NOT_REAL_CURRENT_DATA", "velocity_units": "m/s",
         "sha256": "a" * 64},
    )


def run(source, **kwargs):
    return advect_current(source, latitude_deg=0.0, longitude_deg=0.0,
                          start_time_utc=START, horizon_s=1800, **kwargs)


def test_constant_eastward_current_matches_wgs84_analytic_and_si_units():
    result = run(field(), output_step_s=600)
    assert result["status"] == "COMPLETED"
    assert result["completed_horizon_s"] == 1800
    assert [point["elapsed_s"] for point in result["track"]] == [0, 600, 1200, 1800]
    for point in result["track"]:
        assert point["latitude_deg"] == 0
        assert point["longitude_deg"] * METRES_LON == pytest.approx(0.25 * point["elapsed_s"])
        assert point["speed_m_s"] == pytest.approx(0.25)
    assert result["solver"]["position_units"] == "geographic_degrees"
    assert result["solver"]["velocity_units"] == "m/s"
    assert result["physical_validation"] is False
    assert result["heldout_buoy_positions_used"] is False
    json.dumps(result, allow_nan=False)


def test_time_varying_direction_produces_analytic_curved_path():
    source = field(times=(0, 1200), u=np.array([0.4, 0.0])[:, None, None],
                   v=np.array([0.0, 0.4])[:, None, None])
    result = advect_current(source, latitude_deg=0, longitude_deg=0,
                            start_time_utc=START, horizon_s=1200, step_s=60, output_step_s=300)
    assert result["status"] == "COMPLETED"
    for point in result["track"]:
        t = point["elapsed_s"]
        # Small equatorial domain: WGS84 latitude-dependent metric corrections
        # are much smaller than this one-centimetre check.
        assert point["longitude_deg"] * METRES_LON == pytest.approx(0.4 * t - t * t / 6000, abs=0.01)
        assert point["latitude_deg"] * METRES_LAT == pytest.approx(t * t / 6000, abs=0.01)
    early, late = result["track"][1], result["track"][-1]
    assert early["eastward_m_s"] > early["northward_m_s"]
    assert late["eastward_m_s"] == 0
    assert late["northward_m_s"] == pytest.approx(0.4)
    assert early["longitude_deg"] / early["latitude_deg"] > 4
    assert late["longitude_deg"] / late["latitude_deg"] == pytest.approx(METRES_LAT / METRES_LON)


def test_spatial_shear_changes_direction_without_time_variation():
    latitudes = np.array([-0.01, 0.01])
    u = (0.1 + 0.002 * latitudes * METRES_LAT)[None, :, None]
    source = field(latitude=latitudes, u=u, v=0.1)
    result = advect_current(source, latitude_deg=0, longitude_deg=0, start_time_utc=START,
                            horizon_s=1200, step_s=60, output_step_s=300)
    assert result["status"] == "COMPLETED"
    final = result["track"][-1]
    assert final["latitude_deg"] * METRES_LAT == pytest.approx(120, abs=0.01)
    assert final["longitude_deg"] * METRES_LON == pytest.approx(264, abs=0.01)
    assert final["eastward_m_s"] > result["track"][0]["eastward_m_s"]


def test_rk4_converges_against_nonlinear_spatial_analytic_solution():
    longitude = np.array([0.0, 0.1])
    rate = 0.0004
    source = field(longitude=longitude, u=(0.1 + rate * longitude * METRES_LON)[None, None, :])
    start_lon = 0.001
    initial_x = start_lon * METRES_LON
    exact = (initial_x + 0.1 / rate) * math.exp(rate * 1800) - 0.1 / rate
    errors = []
    for step in (600, 300):
        result = advect_current(source, latitude_deg=0, longitude_deg=start_lon,
                                start_time_utc=START, horizon_s=1800,
                                step_s=step, output_step_s=1800)
        assert result["status"] == "COMPLETED"
        errors.append(abs(result["track"][-1]["longitude_deg"] * METRES_LON - exact))
    assert errors[1] < errors[0] / 10
    assert errors[1] < 0.001


def test_bilinear_space_and_linear_time_interpolation():
    source = field(longitude=(0, 2), latitude=(0, 2), times=(0, 100),
                   u=np.array([[[0, 2], [2, 4]], [[1, 3], [3, 5]]]), v=0)
    east, north = CurrentSampler(source).sample(0.5, 1.0, 25)
    assert east == pytest.approx(1.75)
    assert north == 0


def test_descending_axes_and_0_to_360_longitude_match_signed_longitude():
    ascending = field(longitude=(-81, -80), latitude=(25, 26), u=0.25)
    descending = field(longitude=(280, 279), latitude=(26, 25), u=0.25)
    values = []
    for source, lon in ((ascending, -80.5), (descending, 279.5)):
        result = advect_current(source, latitude_deg=25.5, longitude_deg=lon,
                                start_time_utc=START, horizon_s=600)
        assert result["status"] == "COMPLETED"
        values.append(result["track"][-1])
    assert values[0] == values[1]


def test_missing_spatial_corner_never_becomes_zero_or_renormalized_current():
    source = field()
    source.valid_mask[:, 0, 0] = False
    source.eastward_m_s[:, 0, 0] = np.nan
    result = run(source)
    assert result["status"] == "UNSUPPORTED"
    assert result["reason_code"] == "MASKED_CURRENT_CELL"
    assert result["track"] == []
    assert result["completed_horizon_s"] == 0


def test_missing_future_time_corner_stops_before_accepting_first_step():
    source = field()
    source.valid_mask[1:, :, :] = False
    result = run(source)
    assert result["status"] == "UNSUPPORTED"
    assert result["reason_code"] == "MASKED_CURRENT_CELL"
    assert len(result["track"]) == 1  # Valid initial position, no invented future.


def test_temporal_expiry_keeps_last_supported_position_with_explicit_partial_status():
    source = field(times=(0, 600))
    result = run(source, step_s=60, output_step_s=300)
    assert result["status"] == "PARTIAL"
    assert result["reason_code"] == "OUTSIDE_FORCING_TIME"
    assert result["completed_horizon_s"] == 600
    assert result["track"][-1]["elapsed_s"] == 600
    assert result["track"][-1]["longitude_deg"] * METRES_LON == pytest.approx(150)


def test_starting_before_forcing_time_is_explicitly_unsupported():
    result = advect_current(field(), latitude_deg=0, longitude_deg=0,
                            start_time_utc="2026-10-16T23:59:59Z", horizon_s=600)
    assert result["status"] == "UNSUPPORTED"
    assert result["reason_code"] == "OUTSIDE_FORCING_TIME"
    assert result["track"] == []


def test_leaving_spatial_domain_does_not_clip_or_draw_unsupported_segment():
    source = field(longitude=(-0.001, 0.001), u=1)
    result = run(source, step_s=10, output_step_s=300)
    assert result["status"] == "PARTIAL"
    assert result["reason_code"] == "OUTSIDE_CURRENT_DOMAIN"
    assert 0 < result["completed_horizon_s"] < 120
    assert len(result["track"]) == 2
    assert 0 < result["track"][-1]["longitude_deg"] < 0.001


def test_a_masked_region_stops_even_when_later_grid_cells_exist():
    source = field(longitude=(-0.02, 0, 0.02), latitude=(-0.02, 0.02), u=1)
    source.valid_mask[:, :, 2] = False
    result = advect_current(source, latitude_deg=0, longitude_deg=-0.015,
                            start_time_utc=START, horizon_s=3600, step_s=100)
    assert result["status"] == "PARTIAL"
    assert result["reason_code"] == "MASKED_CURRENT_CELL"
    assert all(point["longitude_deg"] <= 0 for point in result["track"])


@pytest.mark.parametrize("kwargs", [
    {"longitude": (179, 180, 181)}, {"longitude": (-179, 179)},
    {"latitude": (84, 89)}, {"times": (0,)}, {"times": (0, 0)},
])
def test_rejects_dateline_poles_and_non_increasing_time(kwargs):
    with pytest.raises(ValueError):
        run(field(**kwargs))


def test_wrong_units_shape_and_invalid_valid_samples_are_configuration_errors():
    source = field()
    for invalid in (
        replace(source, metadata={"velocity_units": "cm/s"}),
        replace(source, northward_m_s=np.zeros((1, 1, 1))),
        replace(source, valid_mask=source.valid_mask.astype(int)),
        replace(source, eastward_m_s=np.full(source.eastward_m_s.shape, np.nan)),
        replace(source, eastward_m_s=np.full(source.eastward_m_s.shape, 100)),
        replace(source, selected_depth_m=float("nan")),
        replace(source, time_utc=np.array(["1800-01-01", "1800-01-02", "1800-01-03"],
                                          dtype="datetime64[us]")),
    ):
        with pytest.raises(ValueError):
            run(invalid)


@pytest.mark.parametrize("kwargs", [
    {"horizon_s": 21601}, {"horizon_s": True}, {"step_s": 0},
    {"step_s": 0.0001}, {"output_step_s": 0}, {"latitude_deg": True},
    {"latitude_deg": float("nan")}, {"start_time_utc": "2026-10-17T00:00:00"},
])
def test_invalid_requests_and_step_budget_never_create_fake_paths(kwargs):
    args = {"latitude_deg": 0, "longitude_deg": 0,
            "start_time_utc": START, "horizon_s": 1800, **kwargs}
    with pytest.raises(ValueError):
        advect_current(field(), **args)


def test_zero_current_remains_stationary_instead_of_adding_random_motion():
    result = run(field(u=0, v=0))
    assert result["status"] == "COMPLETED"
    assert all(point["latitude_deg"] == point["longitude_deg"] == point["speed_m_s"] == 0
               for point in result["track"])


def test_exact_valid_node_does_not_use_zero_weight_masked_neighbors():
    source = field(longitude=(0, 1), latitude=(0, 1), u=0, v=0)
    source.valid_mask[:, 1, 1] = False
    result = run(source)
    assert result["status"] == "COMPLETED"
