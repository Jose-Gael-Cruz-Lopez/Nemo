"""Fetch one fixed historical NOAA drifter-day (24 rows, capped at 32 KB), no secrets."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apps.ocean.reeftrace_ocean.data import parse_drifter_csv

DATASET_ID = "drifter_hourly_qc"
DRIFTER_ID = "8707978"
START = "1987-10-03T00:00:00Z"
END = "1987-10-03T23:00:00Z"
QUERY = (
    f'ID,time,latitude,longitude,ve,vn,err_ve,err_vn&ID="{DRIFTER_ID}"&time>={START}&time<={END}'
)
SOURCE_URL = f"https://erddap.aoml.noaa.gov/gdp/erddap/tabledap/{DATASET_ID}.csv?" + quote(
    QUERY, safe=",&="
)
METADATA_URL = "https://erddap.aoml.noaa.gov/gdp/erddap/info/drifter_hourly_qc/index.html"
MAX_BYTES = 32_000
FILE_NAME = "noaa-gdp-8707978-19871003.csv"


def validate_sample(payload: bytes) -> list:
    if len(payload) > MAX_BYTES:
        raise ValueError("NOAA sample exceeds 32 KB budget")
    records = parse_drifter_csv(payload.decode("utf-8"))
    if len(records) != 24 or {record.drifter_id for record in records} != {DRIFTER_ID}:
        raise ValueError("Expected exactly one selected drifter and 24 hourly rows")
    if records[0].time_utc.isoformat().replace("+00:00", "Z") != START:
        raise ValueError("Unexpected first sample time")
    if records[-1].time_utc.isoformat().replace("+00:00", "Z") != END:
        raise ValueError("Unexpected last sample time")
    if any(
        (right.time_utc - left.time_utc).total_seconds() != 3600
        for left, right in itertools.pairwise(records)
    ):
        raise ValueError("Expected regular hourly sample timestamps")
    return records


def fetch_sample(output_dir: str | Path, *, force: bool = False) -> dict:
    directory = Path(output_dir)
    destination = directory / FILE_NAME
    manifest_path = destination.with_suffix(".provenance.json")
    if not force and (destination.exists() or manifest_path.exists()):
        raise FileExistsError("Sample/provenance already exists; use --force to replace explicitly")
    payload = bytearray()
    with httpx.stream("GET", SOURCE_URL, timeout=30, follow_redirects=False) as response:
        response.raise_for_status()
        size = response.headers.get("content-length")
        if size and int(size) > MAX_BYTES:
            raise ValueError("NOAA response exceeds 32 KB budget")
        for chunk in response.iter_bytes():
            payload.extend(chunk)
            if len(payload) > MAX_BYTES:
                raise ValueError("NOAA response exceeds 32 KB budget")
    records = validate_sample(bytes(payload))
    manifest = {
        "schema_version": 1,
        "source_url": SOURCE_URL,
        "metadata_url": METADATA_URL,
        "provider": "NOAA AOML Global Drifter Program",
        "dataset_id": DATASET_ID,
        "product_doi": "10.25921/x46c-3620",
        "dataset_release_reference": "v2.01; endpoint metadata reviewed 2026-10-16",
        "license_from_endpoint_metadata": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "NOAA Global Drifter Program; Elipot et al. (2022), DOI 10.25921/x46c-3620",
        "retrieved_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "row_count": len(records),
        "drifter_id": DRIFTER_ID,
        "time_start_utc": START,
        "time_end_utc": END,
        "schema": {
            "ID": "trajectory identifier, string",
            "time": "UTC ISO-8601",
            "latitude": "degrees_north",
            "longitude": "degrees_east",
            "ve": "eastward velocity, m/s",
            "vn": "northward velocity, m/s",
            "err_ve": "95% confidence interval in eastward velocity, m/s",
            "err_vn": "95% confidence interval in northward velocity, m/s",
        },
        "purpose": "real historical data loading/replay smoke test only",
        "not_validated": [
            "tank source attribution",
            "plastic source attribution",
            "ocean forecast skill",
        ],
    }
    directory.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/public"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = fetch_sample(args.output_dir, force=args.force)
    print(
        json.dumps(
            {key: result[key] for key in ("row_count", "bytes", "sha256", "purpose")}, indent=2
        )
    )


if __name__ == "__main__":
    main()
