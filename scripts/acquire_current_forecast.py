"""Explicitly freeze a small public PacIOOS forecast; never called by API reads.

The fixed study requests one surface layer, three valid times and a small box.
Existing snapshots are never overwritten. Review the receipt hash before use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from apps.ocean.reeftrace_ocean.current_forecast import (
    ATTRIBUTION,
    DATA_DIR,
    DATASET_ID,
    END_UTC,
    FILE_NAME,
    MANIFEST_FILE,
    MAX_BYTES,
    MAX_METADATA_BYTES,
    METADATA_FILE,
    METADATA_URL,
    PRODUCT_URL,
    QUERY,
    SOURCE_URL,
    START_UTC,
    _metadata,
    parse_current_csv,
)


def _fetch(client: httpx.Client, url: str, limit: int) -> tuple[bytes, dict]:
    with client.stream("GET", url) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Expected an HTTP 200 data response")
        payload = bytearray()
        for chunk in response.iter_bytes():
            payload.extend(chunk)
            if len(payload) > limit:
                raise ValueError("Source response exceeds its explicit byte budget")
        return bytes(payload), {
            "http_status": response.status_code,
            "server_date": response.headers.get("Date"),
            "content_type": response.headers.get("Content-Type"),
            "last_modified": response.headers.get("Last-Modified"),
        }


def acquire(output_dir: Path) -> dict:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Refusing to overwrite an existing current forecast snapshot")
    with httpx.Client(timeout=60, follow_redirects=False) as client:
        metadata, metadata_transport = _fetch(client, METADATA_URL, MAX_METADATA_BYTES)
        info = _metadata(metadata)
        payload, csv_transport = _fetch(client, SOURCE_URL, MAX_BYTES)
    captured = datetime.now(UTC)
    field = parse_current_csv(payload)
    summary = field.summary()
    manifest = {
        "schema_version": 1, "dataset_id": DATASET_ID,
        "data_origin": "REAL_PACIOOS_ROMS_FORECAST_MODEL_OUTPUT",
        "source_url": SOURCE_URL, "metadata_url": METADATA_URL,
        "product_url": PRODUCT_URL, "attribution": ATTRIBUTION,
        "captured_at_utc": captured.isoformat().replace("+00:00", "Z"),
        "valid_start_utc": START_UTC, "valid_end_utc": END_UTC,
        "model_issue_time_utc": None,
        "future_valid_times_at_acquisition": captured < datetime.fromisoformat(START_UTC),
        "request": {
            "query": QUERY, "variables": ["u", "v"], "depth_index": 0,
            "requested_depth_m": 0.25, "latitude_bounds_deg": [20.5, 21.5],
            "longitude_bounds_deg": [-158.8, -157.4],
            "valid_times_utc": [START_UTC, "2026-10-17T21:00:00Z", END_UTC],
            "axis_selection": "ERDDAP nearest coordinate knots, stride 1",
        },
        "files": {
            "csv": {"name": FILE_NAME, "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(), **csv_transport},
            "metadata": {"name": METADATA_FILE, "bytes": len(metadata),
                         "sha256": hashlib.sha256(metadata).hexdigest(), **metadata_transport},
        },
        "grid": {
            "shape": summary["shape"], "valid_sample_count": summary["valid_sample_count"],
            "invalid_sample_count": summary["invalid_sample_count"],
            "latitude_range_deg": summary["latitude_range_deg"],
            "longitude_range_deg": summary["longitude_range_deg"],
            "depth_m": 0.25, "time_step_s": 10800,
            "nominal_resolution_m": 4000, "velocity_units": "m/s",
        },
        "source_metadata": info,
        "scope": "Hypothetical offshore passive-tracer preview; no observed waste track or skill score",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / FILE_NAME).write_bytes(payload)
    (output_dir / METADATA_FILE).write_bytes(metadata)
    manifest_bytes = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode()
    (output_dir / MANIFEST_FILE).write_bytes(manifest_bytes)
    return {
        "output_dir": str(output_dir), "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "snapshot_sha256": manifest["files"]["csv"]["sha256"], "grid": manifest["grid"],
        "future_valid_times_at_acquisition": manifest["future_valid_times_at_acquisition"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR)
    arguments = parser.parse_args()
    print(json.dumps(acquire(arguments.output_dir), indent=2))
