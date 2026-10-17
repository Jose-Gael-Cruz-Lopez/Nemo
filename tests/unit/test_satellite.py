"""Satellite context must be real, pinned, bounded and unable to alter source inference."""

import copy
import json
from pathlib import Path

import pytest

from apps.ocean.reeftrace_ocean import satellite
from apps.ocean.reeftrace_ocean.satellite import (
    FILE_NAME,
    ROOT,
    SAMPLE_SHA256,
    load_satellite_context,
    parse_satellite_csv,
)
from scripts.fetch_satellite_context import fetch_satellite_context

DIRECTORY = ROOT / "data/public/noaa-coral-context"


def payload():
    return (DIRECTORY / FILE_NAME).read_bytes()


def test_pinned_satellite_rows_and_provenance_preserve_historical_meaning():
    report = load_satellite_context()
    assert report["data_origin"] == "REAL_HISTORICAL_NOAA_SATELLITE_DERIVED"
    assert report["provenance"]["integrity_verified"] is True
    assert report["provenance"]["sha256"] == SAMPLE_SHA256
    assert report["provenance"]["bytes"] == 383
    assert report["provenance"]["row_count"] == 7
    assert report["time_series"][0]["time_utc"] == "2023-07-01T12:00:00Z"
    assert report["time_series"][-1]["time_utc"] == "2023-07-07T12:00:00Z"
    assert [row["degree_heating_week_c_weeks"] for row in report["time_series"]] == [
        2.96, 3.18, 3.43, 3.72, 3.99, 4.24, 4.53,
    ]
    assert report["location"]["latitude_deg"] == 24.575
    assert report["location"]["longitude_deg"] == -81.525
    assert report["summary"]["change_c_weeks"] == 1.57
    assert report["source_attribution"]["used_in_source_ranking"] is False
    assert report["source_attribution"]["status"] == "NOT_SUPPORTED_BY_THIS_DATASET"
    assert any("not current" in item for item in report["limitations"])
    assert any("not direct observation" in item for item in report["limitations"])
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("change", [
    lambda text: text.replace("degree_Celsius_weeks", "metres"),
    lambda text: text.replace("24.575", "25.575"),
    lambda text: text.replace("-81.525", "278.475"),
    lambda text: text.replace("2023-07-03T12:00:00Z", "2023-07-03T13:00:00Z"),
    lambda text: text.replace(",2.96", ",NaN"),
    lambda text: text.replace(",2.96", ",-327.68"),
    lambda text: text.replace(",2.96", ",101"),
    lambda text: text + "2023-07-08T12:00:00Z,24.575,-81.525,5\n",
])
def test_wrong_units_locations_times_and_missing_values_are_not_context(change):
    with pytest.raises(ValueError):
        parse_satellite_csv(change(payload().decode()).encode())


def test_loading_refuses_changed_bytes_even_with_a_forged_manifest(tmp_path):
    changed = payload().replace(b",2.96", b",2.97")
    manifest = json.loads((DIRECTORY / Path(FILE_NAME).with_suffix(".provenance.json")).read_text())
    import hashlib
    manifest["sha256"] = hashlib.sha256(changed).hexdigest()
    (tmp_path / FILE_NAME).write_bytes(changed)
    (tmp_path / Path(FILE_NAME).with_suffix(".provenance.json")).write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="source changed"):
        load_satellite_context(tmp_path)


def test_loading_refuses_relabelled_metadata_and_oversized_fixture(tmp_path):
    original_manifest = json.loads(
        (DIRECTORY / Path(FILE_NAME).with_suffix(".provenance.json")).read_text()
    )
    (tmp_path / FILE_NAME).write_bytes(payload())
    altered = copy.deepcopy(original_manifest)
    altered["source_url"] = "https://example.com/fake-source"
    manifest_path = tmp_path / Path(FILE_NAME).with_suffix(".provenance.json")
    manifest_path.write_text(json.dumps(altered))
    with pytest.raises(ValueError, match="provenance differs"):
        load_satellite_context(tmp_path)
    (tmp_path / FILE_NAME).write_bytes(b"x" * (satellite.MAX_BYTES + 1))
    with pytest.raises(ValueError, match="16 KB"):
        load_satellite_context(tmp_path)


def test_fetch_requires_explicit_overwrite_without_network_access(monkeypatch):
    import httpx

    def forbidden(*args, **kwargs):
        raise AssertionError("existing fixture must not reach the network")

    monkeypatch.setattr(httpx, "stream", forbidden)
    with pytest.raises(FileExistsError):
        fetch_satellite_context(DIRECTORY)


def test_context_returns_independent_documents():
    first = load_satellite_context()
    first["time_series"][0]["degree_heating_week_c_weeks"] = -999
    first["limitations"].clear()
    second = load_satellite_context()
    assert second["time_series"][0]["degree_heating_week_c_weeks"] == 2.96
    assert second["limitations"]
