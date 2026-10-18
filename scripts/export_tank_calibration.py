"""Export one private saved tank mapping without opening a camera or loading credentials.

Run on the laptop that originally captured the calibration. This utility reads
only SQLite ``records`` of kind ``calibration``; it never opens settings, messages,
frames or token-reference files. The result is not approval for a new camera pose.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "nemo_saved_calibration_v1"
MAX_RECORD_BYTES = 65_536
LIST_LIMIT = 100
BASE_FIELDS = {
    "id", "calibration_id", "homography_image_to_cm", "mean_error_cm", "max_error_cm",
    "validation_count", "max_allowed_error_cm", "approved", "image_size_px",
    "camera_session_id", "plane", "units",
}
REUSE_FIELDS = {
    "method", "source_calibration_id", "source_content_sha256", "check_pixels",
    "check_world_cm", "water_plane_unchanged",
}
CALIBRATION_ID = re.compile(r"cal-[0-9a-f]{16}\Z")
PUBLIC_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,99}\Z")


def _finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _pairs(value):
    return (isinstance(value, list) and 3 <= len(value) <= 100
            and all(isinstance(pair, list) and len(pair) == 2
                    and all(_finite_number(v) for v in pair) for pair in value))


def checked_calibration(raw: str, record_id: str) -> dict:
    """Validate the bounded export contract and its existing content-derived ID."""
    if not isinstance(record_id, str) or not CALIBRATION_ID.fullmatch(record_id):
        raise ValueError("Invalid calibration identifier")
    if len(raw.encode("utf-8")) > MAX_RECORD_BYTES:
        raise ValueError("Calibration record exceeds 64 KiB")
    try:
        record = json.loads(raw)
        if not isinstance(record, dict) or set(record) not in (
                BASE_FIELDS, BASE_FIELDS | {"reuse"}):
            raise ValueError("Unexpected calibration fields")
        if record["id"] != record_id or record["calibration_id"] != record_id:
            raise ValueError("Calibration identifiers do not match")
        matrix = record["homography_image_to_cm"]
        if (not isinstance(matrix, list) or len(matrix) != 3
                or any(not isinstance(row, list) or len(row) != 3
                       or not all(_finite_number(v) for v in row) for row in matrix)):
            raise ValueError("Calibration must contain a finite 3 by 3 matrix")
        for key in ("mean_error_cm", "max_error_cm", "max_allowed_error_cm"):
            if not _finite_number(record[key]) or record[key] < 0:
                raise ValueError("Calibration error values must be finite and non-negative")
        if record["max_allowed_error_cm"] <= 0:
            raise ValueError("Calibration tolerance must be positive")
        if type(record["validation_count"]) is not int or not 0 <= record["validation_count"] <= 10000:
            raise ValueError("Invalid validation count")
        if type(record["approved"]) is not bool:
            raise ValueError("Invalid approval flag")
        size = record["image_size_px"]
        if size is not None and (not isinstance(size, list) or len(size) != 2
                                 or any(type(v) is not int or v < 2 for v in size)):
            raise ValueError("Invalid camera image size")
        session = record["camera_session_id"]
        if session is not None and (not isinstance(session, str)
                                    or not PUBLIC_ID.fullmatch(session)
                                    or not session.startswith(("usb-", "reference-pose-"))):
            raise ValueError("Invalid camera session identifier")
        if record["plane"] != "measured_water_surface" or record["units"] != "cm":
            raise ValueError("Only centimetre water-surface mappings can be exported")
        if "reuse" in record:
            reuse = record["reuse"]
            if not isinstance(reuse, dict) or set(reuse) != REUSE_FIELDS:
                raise ValueError("Unexpected calibration reuse fields")
            if (reuse["method"] != "fixed_homography_current_checks_v1"
                    or not isinstance(reuse["source_calibration_id"], str)
                    or not CALIBRATION_ID.fullmatch(reuse["source_calibration_id"])
                    or not isinstance(reuse["source_content_sha256"], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", reuse["source_content_sha256"])
                    or reuse["water_plane_unchanged"] is not True
                    or not _pairs(reuse["check_pixels"])
                    or not _pairs(reuse["check_world_cm"])
                    or len(reuse["check_pixels"]) != len(reuse["check_world_cm"])):
                raise ValueError("Invalid calibration reuse provenance")
        report = {k: v for k, v in record.items() if k not in {"id", "calibration_id"}}
        expected = "cal-" + hashlib.sha256(
            json.dumps(report, sort_keys=True, allow_nan=False).encode()).hexdigest()[:16]
        if expected != record_id:
            raise ValueError("Calibration content-derived identifier does not match")
    except (KeyError, TypeError, json.JSONDecodeError, OverflowError) as error:
        raise ValueError("Malformed saved calibration record") from error
    return record


def open_readonly(database: Path):
    database = Path(database).expanduser().resolve()
    if not database.is_file():
        raise ValueError("Calibration database was not found; no database was created")
    return sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)


def list_calibrations(database: Path) -> dict:
    with closing(open_readonly(database)) as db:
        rows = db.execute(
            "SELECT id, CASE WHEN length(CAST(payload AS BLOB)) <= ? THEN payload END "
            "FROM records WHERE kind='calibration' ORDER BY created DESC LIMIT ?",
            (MAX_RECORD_BYTES, LIST_LIMIT + 1),
        ).fetchall()
    summaries = []
    for record_id, raw in rows[:LIST_LIMIT]:
        display_id = (record_id if isinstance(record_id, str) and CALIBRATION_ID.fullmatch(record_id)
                      else "invalid-calibration-id")
        try:
            if raw is None:
                raise ValueError("Calibration record exceeds 64 KiB")
            record = checked_calibration(raw, record_id)
            summary = {key: record[key] for key in (
                "id", "camera_session_id", "image_size_px", "approved", "validation_count",
                "mean_error_cm", "max_error_cm", "max_allowed_error_cm",
            )}
            summary["integrity"] = "verified"
        except ValueError as error:
            summary = {"id": display_id, "integrity": "rejected", "error": str(error)}
        summaries.append(summary)
    return {"calibrations": summaries, "truncated": len(rows) > LIST_LIMIT}


def export_calibration(database: Path, calibration_id: str, output: Path) -> dict:
    if not CALIBRATION_ID.fullmatch(calibration_id):
        raise ValueError("Use a calibration ID from --list")
    with closing(open_readonly(database)) as db:
        row = db.execute(
            "SELECT CASE WHEN length(CAST(payload AS BLOB)) <= ? THEN payload END "
            "FROM records WHERE kind='calibration' AND id=?",
            (MAX_RECORD_BYTES, calibration_id),
        ).fetchone()
    if row is None:
        raise ValueError("Saved calibration was not found on this laptop")
    if row[0] is None:
        raise ValueError("Calibration record exceeds 64 KiB")
    record = checked_calibration(row[0], calibration_id)
    return write_calibration_bundle(record, output)


def write_private_json(payload: dict, output: Path) -> None:
    """Create one private JSON file outside tracked folders, without overwriting."""
    output = Path(output).expanduser().resolve()
    if output.is_relative_to(ROOT) and not any(
            output.is_relative_to(ROOT / folder) for folder in ("data/local", "work")):
        raise ValueError("Keep private exports outside Git-tracked folders; use data/local or /tmp")
    encoded = (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode()
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(encoded)
    except BaseException:
        output.unlink(missing_ok=True)
        raise


def write_calibration_bundle(record: dict, output: Path) -> dict:
    record = checked_calibration(json.dumps(record, allow_nan=False), record.get("id"))
    payload = {"schema_version": SCHEMA_VERSION, "calibration": record,
               "calibration_json": json.dumps(record, allow_nan=False, sort_keys=True)}
    write_private_json(payload, output)
    return {"calibration_id": record["calibration_id"], "exported": True,
            "schema_version": SCHEMA_VERSION}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/local/reeftrace.sqlite3")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List at most 100 saved mapping summaries")
    group.add_argument("--calibration-id", help="Export one intact saved mapping from this laptop")
    parser.add_argument("--output", type=Path, help="New private JSON file; existing files are never replaced")
    args = parser.parse_args(argv)
    if args.list and args.output is not None:
        parser.error("--output is only used with --calibration-id")
    if args.calibration_id and args.output is None:
        parser.error("--calibration-id requires --output")
    try:
        result = (list_calibrations(args.database) if args.list else
                  export_calibration(args.database, args.calibration_id, args.output))
    except (ValueError, OSError, sqlite3.Error) as error:
        # Do not print SQLite source text, private paths or record contents.
        detail = str(error) if isinstance(error, ValueError) else "Cannot read or export calibration"
        print(json.dumps({"error": detail}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
