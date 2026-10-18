"""Prepare a private historical mapping from Megana's seven-point rig handoff.

Offline only: no supplied Python files are executed, no app server or credentials
are loaded, and no camera is opened. The exported source mapping is tied to the
historical reference pose. Fresh independent current-view checks are still needed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.vision.reeftrace_vision.calibration import fit_homography
from apps.vision.reeftrace_vision.foreground import EmptyTankReference
from scripts.export_tank_calibration import write_calibration_bundle, write_private_json

MAX_JSON_BYTES = 65_536
MAX_REFERENCE_BYTES = 64 * 1024 * 1024
IMAGE_SIZE = [1280, 720]
WORLD_SIZE_CM = [35.56, 22.86]
CORE_FIELDS = {"image_size_px", "declared_max_check_error_cm", "fit", "check"}
OPTIONAL_FIELDS = {"about", "frame", "method", "declared_tolerance_note",
                   "expected_check_errors_cm", "expected_cap_area_px"}
ROW_FIELDS = {"placement", "role", "pixel_in_reference_pose", "world_cm"}


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def load_placements(path: Path) -> tuple[dict, str]:
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("Placements file exceeds 64 KiB")
    raw = path.read_bytes()
    data = json.loads(raw)
    if (not isinstance(data, dict) or not CORE_FIELDS <= set(data)
            or set(data) - CORE_FIELDS - OPTIONAL_FIELDS):
        raise ValueError("Unexpected placements schema")
    if (data["image_size_px"] != IMAGE_SIZE
            or not _finite(data["declared_max_check_error_cm"])
            or data["declared_max_check_error_cm"] != 3.0):
        raise ValueError("This handoff requires its original 1280 by 720 image and 3.0 cm bound")
    for key in ("about", "frame", "method", "declared_tolerance_note"):
        if key in data and (not isinstance(data[key], str) or len(data[key]) > 2000):
            raise ValueError("Invalid descriptive placements metadata")
    for key, fields in (("expected_check_errors_cm", {"mean", "max"}),
                        ("expected_cap_area_px", {"c270_1280x720_pump_off"})):
        if key in data and (not isinstance(data[key], dict) or set(data[key]) != fields
                            or any(not _finite(v) or v < 0 for v in data[key].values())):
            raise ValueError("Invalid expected placements metadata")
    identifiers, pixel_pairs, world_pairs = [], [], []
    for role, count in (("fit", 4), ("check", 3)):
        rows = data[role]
        if not isinstance(rows, list) or len(rows) != count:
            raise ValueError("The historical handoff needs four fit and three separate check points")
        for row in rows:
            if (not isinstance(row, dict) or not ROW_FIELDS <= set(row)
                    or set(row) - ROW_FIELDS - {"where", "cap_area_px"}
                    or row["role"] != role or type(row["placement"]) is not int
                    or not 1 <= row["placement"] <= 7):
                raise ValueError("Invalid historical placement row")
            if "where" in row and (not isinstance(row["where"], str) or len(row["where"]) > 200):
                raise ValueError("Invalid placement location label")
            if "cap_area_px" in row and (not _finite(row["cap_area_px"]) or row["cap_area_px"] <= 0):
                raise ValueError("Invalid historical token image area")
            for key, limits in (("pixel_in_reference_pose", [1279, 719]),
                                ("world_cm", WORLD_SIZE_CM)):
                pair = row[key]
                if (not isinstance(pair, list) or len(pair) != 2
                        or any(not _finite(v) or not 0 <= v <= limit
                               for v, limit in zip(pair, limits, strict=True))):
                    raise ValueError("Historical placement coordinates are invalid or out of bounds")
            identifiers.append(row["placement"])
            pixel_pairs.append(tuple(row["pixel_in_reference_pose"]))
            world_pairs.append(tuple(row["world_cm"]))
    if (len(set(identifiers)) != 7 or len(set(pixel_pairs)) != 7
            or len(set(world_pairs)) != 7):
        raise ValueError("Historical fitting and check placements must be distinct")
    return data, hashlib.sha256(raw).hexdigest()


def load_reference(directory: Path):
    id_file = directory / "placement_reference_id.txt"
    if id_file.stat().st_size > 80:
        raise ValueError("Invalid historical reference identifier")
    reference_id = id_file.read_text().strip()
    if not re.fullmatch(r"ref-[0-9a-f]{16}", reference_id):
        raise ValueError("Invalid historical reference identifier")
    path = directory / "placement_reference.npz"
    if path.stat().st_size > MAX_REFERENCE_BYTES:
        raise ValueError("Historical reference exceeds the local size limit")
    expected_names = {name + ".npy" for name in (*EmptyTankReference._ARRAYS, "meta")}
    with zipfile.ZipFile(path) as archive:
        files = archive.infolist()
        if (len(files) != len(expected_names) or {f.filename for f in files} != expected_names
                or sum(f.file_size for f in files) > MAX_REFERENCE_BYTES):
            raise ValueError("Historical reference archive has unexpected arrays or size")
    with np.load(path, allow_pickle=False) as arrays:
        height, width = IMAGE_SIZE[::-1]
        for name in EmptyTankReference._ARRAYS:
            array = arrays[name]
            expected_shape = ((height, width, 3) if name in {"median", "median_bgr"}
                              else (height, width))
            if (array.shape != expected_shape or array.dtype.kind not in "bifu"
                    or not np.isfinite(array).all()):
                raise ValueError("Historical reference arrays have invalid shape or values")
        meta = arrays["meta"]
        if (meta.shape != (2,) or meta.dtype.kind not in "fiu" or not np.isfinite(meta).all()
                or not 5 <= meta[0] <= 60 or meta[0] != int(meta[0]) or not 0 <= meta[1] <= 255):
            raise ValueError("Historical reference metadata is invalid")
        reference = EmptyTankReference.from_arrays(arrays, expected_id=reference_id)
    return reference, hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_handoff(directory: Path, output: Path) -> dict:
    output = Path(output).expanduser().resolve()
    measurements_output = output.with_name(output.stem + ".measurements.json")
    if output.exists() or measurements_output.exists():
        raise ValueError("Output already exists; choose new private output filenames")
    directory = Path(directory).expanduser().resolve()
    data, placements_sha256 = load_placements(directory / "placements.json")
    reference, reference_sha256 = load_reference(directory)
    report = fit_homography(
        [row["pixel_in_reference_pose"] for row in data["fit"]],
        [row["world_cm"] for row in data["fit"]],
        [row["pixel_in_reference_pose"] for row in data["check"]],
        [row["world_cm"] for row in data["check"]], max_error_cm=3.0,
        image_size_px=IMAGE_SIZE,
        camera_session_id="reference-pose-" + reference.fingerprint.removeprefix("ref-"),
    )
    if not report["approved"]:
        raise ValueError("Historical checks do not meet the original 3.0 cm bound")
    record = {**report, "id": report["calibration_id"]}
    note = {
        "schema_version": "nemo_tank_handoff_measurements_v1",
        "historical_source_only": True, "current_camera_alignment_verified": False,
        "source_calibration_id": record["id"], "historical_reference_id": reference.fingerprint,
        "placements_sha256": placements_sha256, "reference_sha256": reference_sha256,
        "image_size_px": IMAGE_SIZE, "waterline_size_cm": WORLD_SIZE_CM,
        "coordinate_frame": "origin bottom-right inside waterline, pump side; +x left, +y up",
        "original_tolerance_cm": 3.0, "tolerance_selected_after_data": True,
        "fit": [{k: row[k] for k in ROW_FIELDS | {"where"} if k in row} for row in data["fit"]],
        "check": [{k: row[k] for k in ROW_FIELDS | {"where"} if k in row} for row in data["check"]],
    }
    # Both outputs are metadata only. No reference arrays or supplied executable are copied.
    write_calibration_bundle(record, output)
    try:
        write_private_json(note, measurements_output)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return {"calibration_id": record["id"], "reference_id": reference.fingerprint,
            "historical_source_only": True, "current_camera_alignment_verified": False,
            "mean_error_cm": report["mean_error_cm"], "max_error_cm": report["max_error_cm"],
            "validation_count": report["validation_count"], "private_metadata_files_created": 2}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = prepare_handoff(args.directory, args.output)
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as error:
        # No file contents, local paths or supplied prose are echoed.
        detail = str(error) if isinstance(error, ValueError) else "Cannot read or prepare tank handoff"
        print(json.dumps({"error": detail}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
