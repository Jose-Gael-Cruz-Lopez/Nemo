"""Invented packed NetCDF fixtures; no HYCOM values or buoy outcomes acquired."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import hycom
from apps.ocean.reeftrace_ocean.advection import CurrentSampler, advect_current
from apps.ocean.reeftrace_ocean.field import _wgs84_metres_per_degree

netcdf = pytest.importorskip("netCDF4")
ORIGIN = np.datetime64("2022-06-01T00:00:00", "us")
BASE_HOURS = float((ORIGIN - np.datetime64("2000-01-01", "us")) / np.timedelta64(1, "h"))
SCALE32, ZERO32, FILL16 = np.float32("0.001"), np.float32(0), np.int16(-30000)


def write_subset(path, *, times=(0, 3, 6), longitude=(280, 281), latitude=(-1, 1),
                 depth=(15,), velocity_dtype="i2", velocity_dims=hycom.DIMS,
                 scale=SCALE32, offset=ZERO32, fill=FILL16,
                 missing=FILL16, units="m/s", time_units=hycom.TIME_UNITS,
                 calendar="gregorian", positive="down", coordinate_dtype="f8",
                 masked_u=None, masked_v=None, u_values=None, change=None):
    """Write actual raw integers with automatic CF encoding disabled on writes."""
    with netcdf.Dataset(path, "w", format="NETCDF4") as dataset:
        sizes = {"time": len(times), "depth": len(depth), "lat": len(latitude), "lon": len(longitude)}
        for name, size in sizes.items():
            dataset.createDimension(name, size)
        for name, values, coord_units in (
            ("time", BASE_HOURS + np.asarray(times), time_units), ("depth", depth, "m"),
            ("lat", latitude, "degrees_north"), ("lon", longitude, "degrees_east"),
        ):
            var = dataset.createVariable(name, coordinate_dtype, (name,))
            var.units = coord_units
            var[:] = values
            if name == "time":
                var.calendar = calendar
            if name == "depth":
                var.positive = positive
        shape = tuple(sizes[name] for name in velocity_dims)
        for name, masked, raw in (("water_u", masked_u, 500), ("water_v", masked_v, 0)):
            var = dataset.createVariable(name, velocity_dtype, velocity_dims, fill_value=fill)
            var.units, var.scale_factor, var.add_offset = units, scale, offset
            var.setncattr("missing_value", missing)
            var.set_auto_maskandscale(False)
            values = np.full(shape, raw, dtype=velocity_dtype)
            if name == "water_u" and u_values is not None:
                values[:] = u_values
            if masked is not None:
                values[masked] = fill
            var[:] = values
        dataset.history = "/Users/PRIVATE_ACCOUNT/private-local-path must never enter metadata"
        if change is not None:
            change(dataset)
    return path


def test_raw_int16_is_masked_before_exact_decimal_scale_once_and_axes_are_preserved(tmp_path):
    path = write_subset(tmp_path / "synthetic.nc", masked_u=(0, 0, 0, 0), masked_v=(1, 0, 1, 1))
    field = hycom.load_hycom_field(path)
    assert field.longitude_deg.tolist() == [-80, -79]
    assert field.latitude_deg.tolist() == [-1, 1]
    np.testing.assert_array_equal(field.time_utc, ORIGIN + np.array([0, 3, 6]).astype("timedelta64[h]"))
    assert field.selected_depth_m == 15
    assert field.eastward_m_s[0, 0, 1] == 0.5  # Not .0005 or .5000000237487257.
    assert field.northward_m_s[0, 0, 1] == 0
    for index in ((0, 0, 0), (1, 1, 1)):
        assert not field.valid_mask[index]
        assert np.isnan(field.eastward_m_s[index]) and np.isnan(field.northward_m_s[index])
    assert int(field.valid_mask.sum()) == 10
    assert field.metadata["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert field.metadata["source_bytes"] == path.stat().st_size
    assert field.metadata["raw_encoding"]["decode_count"] == 1
    assert field.metadata["source_origin_verified"] is False
    assert "PRIVATE_ACCOUNT" not in json.dumps(field.metadata)
    assert str(path.resolve()) not in json.dumps(field.metadata)


def test_reviewed_float32_encoding_is_not_adopted_as_a_different_physical_scale(tmp_path):
    encoded = np.float32("0.001")
    assert float(encoded) != 0.001  # The reviewed metadata are binary float32.
    field = hycom.load_hycom_field(write_subset(tmp_path / "float32.nc", scale=encoded))
    assert field.eastward_m_s[0, 0, 0] == 0.5
    for index, scale in enumerate((np.float64("0.001"), np.nextafter(encoded, np.float32(np.inf)),
                                   np.float32("0.01"), np.float32("0.000001"))):
        with pytest.raises(ValueError, match="HYCOM_METADATA_ERROR"):
            hycom.load_hycom_field(write_subset(tmp_path / f"changed-{index}.nc", scale=scale))


def test_normalization_edge_and_descending_indices_do_not_reorder_velocity_values(tmp_path):
    assert hycom.normalize_native_longitudes([359.92])[0] == pytest.approx(-0.08, abs=1e-10)
    values = np.array([[[[500, 600], [700, 800]]]] * 3, dtype=np.int16)
    field = hycom.load_hycom_field(write_subset(tmp_path / "descending.nc", longitude=(281, 280),
                                               latitude=(1, -1), u_values=values))
    assert field.longitude_deg.tolist() == [-79, -80]
    assert field.latitude_deg.tolist() == [1, -1]
    np.testing.assert_allclose(field.eastward_m_s[0], [[0.5, 0.6], [0.7, 0.8]], rtol=0, atol=1e-15)


@pytest.mark.parametrize("longitude", [(280, 280), (280, 282, 281), (179, 181), (350, 0),
                                        (-80, -79), (360, 361), (280, np.nan), (280, np.inf)])
def test_changed_or_seamed_native_longitude_support_fails_without_sorting(longitude):
    with pytest.raises(ValueError, match="HYCOM_METADATA_ERROR"):
        hycom.normalize_native_longitudes(longitude)


def integration(field):
    return advect_current(field, latitude_deg=0, longitude_deg=-79.9,
                          start_time_utc="2022-06-01T03:00:00Z", horizon_s=21600,
                          step_s=300, output_step_s=3600)


def test_masked_next_knot_is_immediately_unsupported_not_partial(tmp_path):
    field = hycom.load_hycom_field(write_subset(tmp_path / "masked-next.nc", masked_u=2))
    result = integration(field)
    assert result["status"] == "UNSUPPORTED"
    assert result["reason_code"] == "MASKED_CURRENT_CELL"
    assert result["completed_horizon_s"] == result["accepted_steps"] == 0
    assert len(result["track"]) == 1 and result["track"][0]["elapsed_s"] == 0


def test_only_three_hour_prefix_is_supported_before_masked_nine_hour_knot(tmp_path):
    field = hycom.load_hycom_field(write_subset(tmp_path / "partial.nc", times=(0, 3, 6, 9), masked_v=3))
    result = integration(field)
    assert result["status"] == "PARTIAL"
    assert result["reason_code"] == "MASKED_CURRENT_CELL"
    assert result["completed_horizon_s"] == 10800
    assert [point["elapsed_s"] for point in result["track"]] == [0, 3600, 7200, 10800]
    east = (result["track"][-1]["longitude_deg"] + 79.9) * _wgs84_metres_per_degree(0)[0]
    assert east == pytest.approx(5400, abs=1e-6)  # Numerical float tolerance, not physical accuracy.
    assert result["track"][-1]["time_utc"] == "2022-06-01T06:00:00Z"


def test_integrator_retains_exact_spatial_support_without_wrapping_or_extrapolation(tmp_path):
    sampler = CurrentSampler(hycom.load_hycom_field(write_subset(tmp_path / "domain.nc")))
    assert sampler.sample(0, -80, 0) == (0.5, 0)
    for latitude, longitude in ((0, -80.0001), (0, -78.9999), (-1.0001, -79.5), (1.0001, -79.5)):
        with pytest.raises(ValueError, match="OUTSIDE_CURRENT_DOMAIN"):
            sampler.sample(latitude, longitude, 0)
    with pytest.raises(ValueError, match="UNSUPPORTED_GEOGRAPHY"):
        sampler.sample(0, 280, 0)


@pytest.mark.parametrize("options", [
    {"velocity_dtype": "f4"}, {"velocity_dtype": "u2", "fill": np.uint16(30000)},
    {"velocity_dims": ("time", "depth", "lon", "lat")},
    {"velocity_dims": ("time", "lat", "lon")}, {"units": "cm/s"},
    {"depth": (0,)}, {"depth": (14.999,)}, {"depth": (15, 20)}, {"positive": "up"},
    {"coordinate_dtype": "f4"}, {"missing": np.int16(-29999)}, {"missing": np.float64(-30000)},
    {"fill": np.int16(-29999)}, {"offset": np.float32(1)}, {"offset": np.float64(0)},
    {"latitude": (-1, -1)}, {"latitude": (-1, 1, 0)}, {"latitude": (-81, -79)},
    {"latitude": (84, 86)}, {"latitude": (-1, np.nan)},
    {"calendar": "360_day"}, {"calendar": "standard"}, {"time_units": "days since 2000-01-01"},
    {"times": (0, 6)}, {"times": (0, 3, 3)}, {"times": (6, 3, 0)},
    {"times": (0, 3.5)}, {"times": (0, np.nan)}, {"times": (-30000, -29997)},
    {"change": lambda d: d.renameVariable("water_v", "other_v")},
    {"change": lambda d: d.variables["water_u"].setncattr("_Unsigned", "true")},
    {"change": lambda d: d.variables["water_u"].delncattr("scale_factor")},
    {"change": lambda d: d.variables["depth"].setncattr("units", "cm")},
    {"change": lambda d: d.variables["lon"].setncattr("units", "radians")},
    {"change": lambda d: d.variables["lat"].setncattr("missing_value", np.float64(-1))},
    {"change": lambda d: d.variables["time"].setncattr("scale_factor", np.float32(1))},
    {"change": lambda d: d.variables["time"].delncattr("calendar")},
    {"change": lambda d: d.variables["water_v"].delncattr("missing_value")},
    {"change": lambda d: d.variables["water_v"].setncattr("scale_factor", np.float32("0.01"))},
    {"change": lambda d: d.variables["water_v"].setncattr("add_offset", np.float32(1))},
    {"u_values": 12000},
])
def test_unexpected_encoding_shape_depth_units_time_or_domain_is_rejected(tmp_path, options):
    with pytest.raises(ValueError, match="HYCOM_METADATA_ERROR"):
        hycom.load_hycom_field(write_subset(tmp_path / "bad.nc", **options))


def test_file_and_sample_limits_are_hard_bounds_and_remote_paths_are_not_opened(tmp_path):
    path = write_subset(tmp_path / "bounded.nc")
    for kwargs in ({"max_file_bytes": path.stat().st_size - 1}, {"max_samples": 11},
                   {"max_samples": 0}, {"max_samples": True}, {"max_file_bytes": False},
                   {"max_samples": hycom.MAX_SAMPLES + 1}, {"max_file_bytes": hycom.MAX_FILE_BYTES + 1}):
        with pytest.raises(ValueError, match="HYCOM_METADATA_ERROR"):
            hycom.load_hycom_field(path, **kwargs)
    for invalid in (tmp_path / "missing.nc", "https://example.test/currents.nc"):
        with pytest.raises(ValueError, match="HYCOM_METADATA_ERROR"):
            hycom.load_hycom_field(invalid)
    malformed = tmp_path / "not-netcdf.nc"
    malformed.write_bytes(b"not a NetCDF payload")
    with pytest.raises(ValueError, match="supported NetCDF"):
        hycom.load_hycom_field(malformed)
