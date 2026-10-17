"""Data boundaries: units, masks, coordinates, budgets and a real tiny NOAA fixture."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import (
    load_copernicus_field,
    load_drifter_csv,
    metres_per_second_to_cm_per_second,
)
from apps.ocean.reeftrace_ocean.data import parse_drifter_csv
from scripts.fetch_public_sample import FILE_NAME, MAX_BYTES, validate_sample

ROOT = Path(__file__).resolve().parents[2]


def test_verified_historical_noaa_sample_and_provenance():
    path = ROOT / "data/public" / FILE_NAME
    payload = path.read_bytes()
    manifest = json.loads(path.with_suffix(".provenance.json").read_text())
    records = load_drifter_csv(path)
    assert len(records) == manifest["row_count"] == 24
    assert len(payload) == manifest["bytes"] < MAX_BYTES
    assert hashlib.sha256(payload).hexdigest() == manifest["sha256"]
    assert records[0].drifter_id == "8707978"
    assert records[0].eastward_m_s == pytest.approx(-0.0736)
    assert records[0].time_utc.year == 1987
    assert records[-1].time_utc.hour == 23
    assert manifest["purpose"] == "real historical data loading/replay smoke test only"
    validate_sample(payload)


def test_velocity_conversion_never_changes_coordinates():
    assert metres_per_second_to_cm_per_second([0.1, -0.2]).tolist() == [10.0, -20.0]


@pytest.mark.parametrize("bad_unit", ["cm/s", "knots", ""])
def test_noaa_rejects_wrong_units(bad_unit):
    text = (ROOT / "data/public" / FILE_NAME).read_text()
    with pytest.raises(ValueError, match="units"):
        parse_drifter_csv(text.replace(",m/s,m/s,m/s,m/s", f",{bad_unit},m/s,m/s,m/s", 1))


def test_noaa_rejects_missing_or_duplicate_time():
    text = (ROOT / "data/public" / FILE_NAME).read_text()
    with pytest.raises(ValueError, match="non-finite"):
        parse_drifter_csv(text.replace("-0.0736", "NaN", 1))
    lines = text.splitlines()
    with pytest.raises(ValueError, match="increasing"):
        parse_drifter_csv("\n".join(lines + [lines[-1]]))


def _write_field(tmp_path, *, units="m s-1", depth=True, longitude_units="degrees_east"):
    xr = pytest.importorskip("xarray")
    dims = (
        ("time", "depth", "latitude", "longitude") if depth else ("time", "latitude", "longitude")
    )
    values = np.array([[[[0.1, np.nan], [0.2, 0.3]]], [[[0.4, 0.5], [0.6, 0.7]]]])
    if not depth:
        values = values[:, 0]
    coords = {
        "time": np.array(["2026-10-01T00:00", "2026-10-01T01:00"], dtype="datetime64[ns]"),
        "latitude": ("latitude", [26.0, 26.083333], {"units": "degrees_north"}),
        "longitude": ("longitude", [-80.0, -79.916667], {"units": longitude_units}),
    }
    if depth:
        coords["depth"] = ("depth", [0.5], {"units": "m", "positive": "down"})
    dataset = xr.Dataset(
        {
            "utotal": (dims, values, {"units": units}),
            "vtotal": (dims, values * 0.5, {"units": units}),
        },
        coords=coords,
        attrs={"product": "SYNTHETIC_TEST_FIXTURE_NOT_COPERNICUS_DATA"},
    )
    path = tmp_path / "synthetic.nc"
    dataset.to_netcdf(path, engine="scipy")
    return path


def test_copernicus_reader_preserves_geography_and_fill_mask(tmp_path):
    field = load_copernicus_field(_write_field(tmp_path))
    assert field.eastward_m_s.shape == (2, 2, 2)
    assert field.selected_depth_m == 0.5
    assert field.valid_mask.sum() == 7
    assert np.isnan(field.eastward_m_s[0, 0, 1])
    assert field.longitude_deg[0] == -80
    assert field.eastward_m_s[0, 0, 0] == 0.1
    summary = field.summary()
    assert summary["coordinate_space"] == "geographic_lonlat_degrees"
    assert 8000 < summary["approx_east_west_grid_spacing_m_at_midlatitude"][0] < 9000
    assert summary["invalid_sample_count"] == 1
    assert summary["provenance"]["product"].startswith("SYNTHETIC")
    json.dumps(summary, allow_nan=False)


@pytest.mark.parametrize("units", ["cm/s", "knots", "degrees/s", ""])
def test_field_rejects_unexpected_velocity_units(tmp_path, units):
    with pytest.raises(ValueError, match="m/s"):
        load_copernicus_field(_write_field(tmp_path, units=units))


def test_field_rejects_projected_coordinates_and_excess_budget(tmp_path):
    with pytest.raises(ValueError, match="degrees_east"):
        load_copernicus_field(_write_field(tmp_path, longitude_units="m"))
    path = _write_field(tmp_path)
    with pytest.raises(ValueError, match="sample budget"):
        load_copernicus_field(path, max_samples=7)
    with pytest.raises(ValueError, match="file budget"):
        load_copernicus_field(path, max_file_bytes=1)


def test_field_requires_actual_velocity_variables_and_explicit_depth(tmp_path):
    path = _write_field(tmp_path)
    with pytest.raises(ValueError, match="Missing velocity"):
        load_copernicus_field(path, u_variable="invented_u")
    with pytest.raises(ValueError, match="Depth index"):
        load_copernicus_field(path, depth_index=1)
    field = load_copernicus_field(_write_field(tmp_path, depth=False))
    assert field.selected_depth_m is None


def test_field_does_not_open_remote_urls():
    pytest.importorskip("xarray")
    with pytest.raises(ValueError, match="local"):
        load_copernicus_field("https://example.com/large-global.nc")
