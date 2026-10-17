"""Invented packed currents and nominal coordinates only; no source-value GETs."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import hycom
from apps.ocean.reeftrace_ocean.advection import CurrentSampler
from apps.ocean.reeftrace_ocean.field import OceanField
from apps.ocean.reeftrace_ocean.matched_current import GROUP_IDS, ORIGIN
from scripts import evaluate_matched_current_v2_study as wrapper

netcdf = pytest.importorskip("netCDF4")


def axes():
    latitude = (25.0 + 0.04 * np.arange(251)).astype(np.float32).astype(np.float64)
    longitude = (280.0 + 0.08 * np.arange(188)).astype(np.float32)
    # An invented mix of reviewed +/-one-ULP labels; the last value reproduces
    # only the published coordinate edge, never a saved scientific current.
    longitude[20] = np.nextafter(longitude[20], np.float32(-np.inf))
    longitude[40] = np.nextafter(longitude[40], np.float32(np.inf))
    longitude[-1] = np.nextafter(longitude[-1], np.float32(np.inf))
    return latitude, longitude.astype(np.float64)


def packed_subset(tmp_path, *, latitude=None, longitude=None, times=(0, 3, 6), depth=(15,),
                  coordinate_dtype="f8", masked_u=None, masked_v=None, change=None):
    """Raw signed integers invented here; disable netCDF's automatic CF encoding."""
    lat, lon = axes()
    latitude = lat if latitude is None else latitude
    longitude = lon if longitude is None else longitude
    path = tmp_path / "invented-v2-current.nc"
    base_hours = float((np.datetime64("2022-06-01T00", "us")
                        - np.datetime64("2000-01-01", "us")) / np.timedelta64(1, "h"))
    sizes = {"time": len(times), "depth": len(depth), "lat": len(latitude),
             "lon": len(longitude)}
    with netcdf.Dataset(path, "w", format="NETCDF4") as dataset:
        for name, size in sizes.items():
            dataset.createDimension(name, size)
        for name, values, units in (
            ("time", base_hours + np.asarray(times), hycom.TIME_UNITS),
            ("depth", depth, "m"), ("lat", latitude, "degrees_north"),
            ("lon", longitude, "degrees_east"),
        ):
            coordinate = dataset.createVariable(name, coordinate_dtype, (name,))
            coordinate.units = units
            coordinate[:] = values
            if name == "time":
                coordinate.calendar = "gregorian"
            if name == "depth":
                coordinate.positive = "down"
        shape = tuple(sizes[name] for name in hycom.DIMS)
        for name, raw, masked in (("water_u", 100, masked_u), ("water_v", 0, masked_v)):
            variable = dataset.createVariable(name, "i2", hycom.DIMS,
                                              fill_value=np.int16(hycom.FILL))
            variable.units = "m/s"
            variable.scale_factor, variable.add_offset = np.float32("0.001"), np.float32(0)
            variable.missing_value = np.int16(hycom.FILL)
            variable.set_auto_maskandscale(False)
            values = np.full(shape, raw, dtype=np.int16)
            if masked is not None:
                values[masked] = np.int16(hycom.FILL)
            variable[:] = values
        if change:
            change(dataset)
    return path.read_bytes()


def test_reviewed_float32_labels_are_preserved_without_snapping_or_domain_expansion(tmp_path):
    lat, lon = axes()
    payload = packed_subset(tmp_path, masked_u=(0, 0, 10, 20), masked_v=(2, 0, 40, 50))
    field = wrapper._study_field(payload)
    np.testing.assert_array_equal(field.latitude_deg, lat)
    np.testing.assert_array_equal(field.longitude_deg, lon - 360.0)
    assert lon[-1] == 294.96002197265625
    assert field.longitude_deg[-1] == -65.03997802734375
    assert field.longitude_deg[-1] != -65.0
    assert field.metadata["sha256"] == wrapper._sha(payload)
    assert field.metadata["raw_encoding"]["decode_count"] == 1
    assert field.eastward_m_s[0, 0, 0] == 0.1
    for index in ((0, 10, 20), (2, 40, 50)):
        assert not field.valid_mask[index]
        assert np.isnan(field.eastward_m_s[index]) and np.isnan(field.northward_m_s[index])
    sampler = CurrentSampler(field)
    assert sampler.sample(30, field.longitude_deg[-1], 0) == (0.1, 0.0)
    with pytest.raises(ValueError, match="OUTSIDE_CURRENT_DOMAIN"):
        sampler.sample(30, -65.02, 0)
    with pytest.raises(ValueError, match="MASKED_CURRENT_CELL"):
        sampler.sample(lat[10], field.longitude_deg[20], 0)


@pytest.mark.parametrize("direction", [-1, 1])
def test_one_longitude_ulp_is_the_limit_not_a_decimal_spacing_tolerance(tmp_path, direction):
    lat, lon = axes()
    nominal = np.float32(280.0 + 0.08 * 90)
    toward = np.float32(np.inf if direction > 0 else -np.inf)
    lon[90] = float(np.nextafter(nominal, toward))
    field = wrapper._study_field(packed_subset(tmp_path, latitude=lat, longitude=lon))
    assert field.longitude_deg[90] + 360.0 == lon[90]
    lon[90] = float(np.nextafter(np.float32(lon[90]), toward))
    with pytest.raises(ValueError, match="ULP"):
        wrapper._study_field(packed_subset(tmp_path, latitude=lat, longitude=lon))


@pytest.mark.parametrize("change", ["latitude_ulp", "latitude_half_ulp", "longitude_half_ulp",
                                   "longitude_shift", "coarsen", "missing_latitude",
                                   "missing_longitude", "reverse_latitude", "reverse_longitude",
                                   "duplicate", "native_lower_bound", "native_inward_west",
                                   "nonfinite"])
def test_shifted_coarsened_missing_or_undeclared_axis_encodings_fail_closed(tmp_path, change):
    lat, lon = axes()
    if change == "latitude_ulp":
        lat[50] = float(np.nextafter(np.float32(lat[50]), np.float32(np.inf)))
    elif change == "latitude_half_ulp":
        lat[50] += float(np.spacing(np.float32(lat[50]))) / 2
    elif change == "longitude_half_ulp":
        lon[50] += float(np.spacing(np.float32(lon[50]))) / 2
    elif change == "longitude_shift":
        lon = (lon + 0.04).astype(np.float32).astype(np.float64)
    elif change == "coarsen":
        lon = (280 + 0.16 * np.arange(188)).astype(np.float32).astype(np.float64)
    elif change == "missing_latitude":
        lat = np.delete(lat, 100)
    elif change == "missing_longitude":
        lon = np.delete(lon, 100)
    elif change == "reverse_latitude":
        lat = lat[::-1]
    elif change == "reverse_longitude":
        lon = lon[::-1]
    elif change == "duplicate":
        lon[80] = lon[79]
    elif change == "native_lower_bound":
        lon[0] = float(np.nextafter(np.float32(280), np.float32(-np.inf)))
    elif change == "native_inward_west":
        lon[0] = float(np.nextafter(np.float32(280), np.float32(np.inf)))
    else:
        lat[100] = np.nan
    with pytest.raises(ValueError, match="HYCOM"):
        wrapper._study_field(packed_subset(tmp_path, latitude=lat, longitude=lon))


@pytest.mark.parametrize("options", [
    {"coordinate_dtype": "f4"}, {"coordinate_dtype": "i4"},
    {"depth": (0,)}, {"depth": (15.001,)}, {"depth": (0, 15)},
    {"times": (1, 4, 7)}, {"times": (0, 3, 9)}, {"times": (0, 3, 6, 9)},
    {"change": lambda ds: ds.variables["lat"].setncattr("units", "radians")},
    {"change": lambda ds: ds.variables["lon"].setncattr("scale_factor", np.float32(1))},
    {"change": lambda ds: ds.variables["time"].setncattr("calendar", "noleap")},
    {"change": lambda ds: ds.variables["depth"].setncattr("positive", "up")},
    {"change": lambda ds: ds.variables["water_u"].setncattr("scale_factor", np.float32("0.01"))},
])
def test_shared_raw_dtype_units_time_depth_and_scale_guards_are_not_relaxed(tmp_path, options):
    with pytest.raises(ValueError, match="HYCOM"):
        wrapper._study_field(packed_subset(tmp_path, **options))


def test_all_masked_currents_stay_unsupported_without_blocking_the_two_baselines(tmp_path):
    field = wrapper._study_field(packed_subset(tmp_path, masked_u=slice(None)))
    assert not field.valid_mask.any()
    contexts = {group: [{"drifter_id": group,
        "time_utc": (ORIGIN - timedelta(hours=24 - i)).isoformat(),
        "latitude_deg": "30", "longitude_deg": "-75"} for i in range(25)]
        for group in GROUP_IDS}
    forecasts = wrapper.build_matched_current_forecasts(contexts, dict.fromkeys(GROUP_IDS, field))
    for group in forecasts["groups"]:
        assert [candidate["status"] for candidate in group["candidates"]] == [
            "COMPLETED", "COMPLETED", "UNSUPPORTED"]
        assert group["candidates"][2]["reason_code"] == "CURRENT_FIELD_ALL_MASKED"
        assert group["candidates"][2]["available_count"] == 0
    assert forecasts["planned_cell_count"] == 36


def test_field_admission_does_not_mutate_the_shared_decoded_field(tmp_path, monkeypatch):
    payload = packed_subset(tmp_path)
    field = hycom.load_hycom_field_bytes(payload)
    before = {name: getattr(field, name).copy() for name in (
        "latitude_deg", "longitude_deg", "time_utc", "valid_mask",
        "eastward_m_s", "northward_m_s")}
    monkeypatch.setattr(wrapper, "load_hycom_field_bytes", lambda raw: field if raw is payload else None)
    assert wrapper._study_field(payload) is field
    for name, values in before.items():
        np.testing.assert_array_equal(getattr(field, name), values)


def test_previously_disclosed_saved_coordinates_pass_without_reading_any_velocity_variable():
    """Compatibility-only prior exposure; not a scientific-value-unseen design.

    Only lat/lon coordinate variables are read. Dummy shape/mask arrays are
    invented; no currents, GDP targets, advection or model scores are decoded.
    """
    path = Path(__file__).resolve().parents[2] / (
        "data/research/matched-current-v1/raw/hycom-currents.nc")
    if not path.is_file():
        pytest.skip("Previously disclosed v1 coordinate artifact is not present")
    payload = path.read_bytes()
    assert wrapper._sha(payload) == (
        "7005d62128f100066c6d7120fc4e32c4a6c524814d1085dcc19996dfbc910065")
    with netcdf.Dataset("saved-coordinate-only", mode="r", memory=payload) as dataset:
        dataset.set_auto_maskandscale(False)
        latitude = np.asarray(dataset.variables["lat"][:])
        native_longitude = np.asarray(dataset.variables["lon"][:])
    shape = (3, 251, 188)
    field = OceanField(
        np.array(["2022-06-01T00", "2022-06-01T03", "2022-06-01T06"],
                 dtype="datetime64[us]"),
        hycom.normalize_native_longitudes(native_longitude), latitude,
        np.zeros(shape), np.zeros(shape), np.zeros(shape, dtype=bool), 15.,
        {"kind": "SAVED_COORDINATES_ONLY_INVENTED_ARRAY_SHAPES"},
    )
    wrapper._native_axis_contract(field)
    assert field.longitude_deg[-1] == -65.03997802734375
    np.testing.assert_array_equal(native_longitude, field.longitude_deg + 360)
