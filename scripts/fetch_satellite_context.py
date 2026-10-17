"""Fetch the pinned seven-row NOAA satellite context, capped at 16 KB; no credentials."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apps.ocean.reeftrace_ocean.satellite import (
    FILE_NAME,
    MAX_BYTES,
    ROOT,
    SOURCE_URL,
    satellite_manifest,
)


def fetch_satellite_context(output_dir: str | Path, *, force: bool = False) -> dict:
    directory = Path(output_dir)
    path = directory / FILE_NAME
    provenance_path = path.with_suffix(".provenance.json")
    if not force and (path.exists() or provenance_path.exists()):
        raise FileExistsError("Satellite fixture exists; use --force to replace explicitly")
    payload = bytearray()
    with httpx.stream("GET", SOURCE_URL, timeout=30, follow_redirects=False) as response:
        response.raise_for_status()
        size = response.headers.get("content-length")
        if size and int(size) > MAX_BYTES:
            raise ValueError("Satellite response exceeds 16 KB")
        for chunk in response.iter_bytes(chunk_size=4096):
            if len(payload) + len(chunk) > MAX_BYTES:
                raise ValueError("Satellite response exceeds 16 KB")
            payload.extend(chunk)
    manifest = satellite_manifest(
        bytes(payload), retrieved_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )
    directory.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    provenance_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/public/noaa-coral-context")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    manifest = fetch_satellite_context(args.output_dir, force=args.force)
    print(json.dumps({key: manifest[key] for key in ("row_count", "bytes", "sha256")}, indent=2))


if __name__ == "__main__":
    main()
