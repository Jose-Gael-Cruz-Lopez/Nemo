"""Pinned satellite-derived heat context, independent of tank source attribution."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]
DATASET_ID = "noaacrwdhwDaily"
FILE_NAME = "noaa-crw-dhw-florida-keys-20230701-20230707.csv"
SAMPLE_SHA256 = "5e3248ce6247aece0d5736678bba36010cb4b0a2053c40e1ba7b69bba125c101"
START_UTC = "2023-07-01T12:00:00Z"
END_UTC = "2023-07-07T12:00:00Z"
LATITUDE = 24.575
LONGITUDE = -81.525
MAX_BYTES = 16_000
DATA_ORIGIN = "REAL_HISTORICAL_NOAA_SATELLITE_DERIVED"
QUERY = (
    f"degree_heating_week[({START_UTC}):1:({END_UTC})]"
    f"[({LATITUDE})][({LONGITUDE})]"
)
SOURCE_URL = (
    f"https://coastwatch.noaa.gov/erddap/griddap/{DATASET_ID}.csv?"
    + quote(QUERY, safe="")
)
METADATA_URL = f"https://coastwatch.noaa.gov/erddap/info/{DATASET_ID}/index.html"
METHOD_URL = "https://coralreefwatch.noaa.gov/product/5km/index_5km_dhw.php"
ATTRIBUTION = "NOAA Coral Reef Watch, daily global 5 km satellite DHW product, version 3.1"
HEADERS = ("time", "latitude", "longitude", "degree_heating_week")
UNITS = ("UTC", "degrees_north", "degrees_east", "degree_Celsius_weeks")
LIMITATIONS = [
    ("Historical satellite-derived context for one Florida Keys-area grid cell in July 2023; "
     "not current reef conditions or the location of the tabletop case."),
    "The 0.05-degree grid is approximately 5 km, not individual coral-branch resolution.",
    "DHW is accumulated thermal stress, not direct observation of coral bleaching or mortality.",
    "Temperature heat stress is not an ocean-current, plastic-detection or source-origin label.",
    "These values never enter the tank source score, priors, release ages or calibration.",
]


def parse_satellite_csv(payload: bytes) -> list[dict]:
    """Validate the small, explicitly selected historical experiment, without inference."""
    if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_BYTES:
        raise ValueError("Satellite CSV must be nonempty and within 16 KB")
    try:
        reader = csv.reader(io.StringIO(payload.decode("utf-8")))
        if tuple(next(reader, [])) != HEADERS or tuple(next(reader, [])) != UNITS:
            raise ValueError("Unexpected satellite CSV columns or units")
        rows = list(reader)
        if len(rows) != 7:
            raise ValueError("Expected exactly seven historical daily satellite rows")
        records = []
        start = datetime.fromisoformat(START_UTC)
        for index, row in enumerate(rows):
            if len(row) != 4:
                raise ValueError("Malformed satellite CSV row")
            timestamp = datetime.fromisoformat(row[0])
            if timestamp.tzinfo is None or timestamp != start + timedelta(days=index):
                raise ValueError("Unexpected historical satellite timestamp/cadence")
            latitude, longitude, dhw = map(float, row[1:])
            if (not all(map(math.isfinite, (latitude, longitude, dhw)))
                    or abs(latitude - LATITUDE) > 1e-6
                    or abs(longitude - LONGITUDE) > 1e-6
                    or not 0 <= dhw <= 100):
                raise ValueError("Satellite coordinate, missing value or heat stress is invalid")
            records.append({
                "time_utc": timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "latitude_deg": latitude,
                "longitude_deg": longitude,
                "degree_heating_week_c_weeks": dhw,
            })
    except (UnicodeDecodeError, OverflowError, csv.Error) as error:
        raise ValueError("Malformed satellite CSV") from error
    return records


def satellite_manifest(payload: bytes, *, retrieved_at_utc: str) -> dict:
    """Create provenance only for the reviewed source bytes, never a replacement fixture."""
    records = parse_satellite_csv(payload)
    digest = hashlib.sha256(payload).hexdigest()
    if digest != SAMPLE_SHA256:
        raise ValueError("Satellite source changed; review bytes before updating the pinned digest")
    return {
        "schema_version": 1,
        "provider": "NOAA Coral Reef Watch",
        "dataset_id": DATASET_ID,
        "product_version": "3.1",
        "data_origin": DATA_ORIGIN,
        "source_url": SOURCE_URL,
        "metadata_url": METADATA_URL,
        "method_url": METHOD_URL,
        "attribution": ATTRIBUTION,
        "license": "NOAA CRW use without restriction; source citation and credit requested",
        "license_url": METADATA_URL,
        "retrieved_at_utc": retrieved_at_utc,
        "sha256": digest,
        "bytes": len(payload),
        "row_count": len(records),
        "time_start_utc": START_UTC,
        "time_end_utc": END_UTC,
        "latitude_deg": LATITUDE,
        "longitude_deg": LONGITUDE,
        "units": "degree_Celsius_weeks",
        "purpose": "independent historical reef thermal-stress context, not source tracing",
    }


def load_satellite_context(data_dir: str | Path | None = None) -> dict:
    """Load and integrity-check the offline context; opens no network or account."""
    directory = Path(data_dir) if data_dir is not None else ROOT / "data/public/noaa-coral-context"
    path = directory / FILE_NAME
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Satellite CSV exceeds the 16 KB budget")
    payload = path.read_bytes()
    manifest_path = path.with_suffix(".provenance.json")
    if manifest_path.stat().st_size > MAX_BYTES:
        raise ValueError("Satellite provenance exceeds the 16 KB budget")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("retrieved_at_utc"), str):
        raise TypeError("Satellite provenance must contain its retrieval time")
    expected = satellite_manifest(payload, retrieved_at_utc=manifest["retrieved_at_utc"])
    if manifest != expected:
        raise ValueError("Satellite provenance differs from the reviewed source record")
    records = parse_satellite_csv(payload)
    first, last = records[0], records[-1]
    result = {
        "schema_version": 1,
        "data_origin": DATA_ORIGIN,
        "title": "Historical satellite reef heat context",
        "dataset_id": DATASET_ID,
        "location": {
            "description": "Florida Keys-area ocean grid cell; independent historical context",
            "latitude_deg": LATITUDE, "longitude_deg": LONGITUDE,
            "grid_resolution_degrees": 0.05,
            "nominal_resolution_km": 5,
        },
        "period": {"start_utc": START_UTC, "end_utc": END_UTC},
        "time_series": records,
        "units": "degree_Celsius_weeks",
        "summary": {
            "first_dhw_c_weeks": first["degree_heating_week_c_weeks"],
            "latest_dhw_c_weeks": last["degree_heating_week_c_weeks"],
            "change_c_weeks": round(last["degree_heating_week_c_weeks"]
                                    - first["degree_heating_week_c_weeks"], 6),
            "bleaching_risk_threshold_c_weeks": 4.0,
            "last_sample_at_or_above_bleaching_risk_threshold": (
                last["degree_heating_week_c_weeks"] >= 4.0
            ),
            "interpretation": "DHW reached a level associated with bleaching risk; "
                              "this does not confirm observed bleaching.",
        },
        "source_attribution": {
            "status": "NOT_SUPPORTED_BY_THIS_DATASET", "used_in_source_ranking": False,
        },
        "provenance": {**manifest, "integrity_verified": True},
        "limitations": list(LIMITATIONS),
    }
    json.dumps(result, allow_nan=False)
    return result
