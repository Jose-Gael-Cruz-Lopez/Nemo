"""Explicit first score or immutable offline replay of the distinct v2 study.

V1 failures remain immutable. V2 changes coordinate-encoding admission only;
shared model definitions, physical units, trajectories and scoring are unchanged.

Acquisition is a separate command. This wrapper saves all fixed-model forecasts
before decoding any reserved future coordinates. Public readers must only read
the resulting frozen artifacts; importing this module does not score anything.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from apps.ocean.reeftrace_ocean.hycom import load_hycom_field_bytes
from apps.ocean.reeftrace_ocean.matched_current import (
    GROUP_IDS,
    HORIZONS_S,
    MODEL_IDS,
    ORIGIN,
    build_matched_current_forecasts,
    forecast_sha256,
    score_matched_current_forecasts,
)

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "data/research/matched-current-v2"
EXPECTED_TIMES = tuple(
    (ORIGIN + timedelta(hours=hour)).isoformat().replace("+00:00", "Z")
    for hour in range(-24, 7)
)


def canonical_json(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _save(path: Path, value: dict) -> str:
    raw = canonical_json(value)
    with path.open("xb") as stream:
        stream.write(raw)
    with path.with_suffix(".sha256").open("x") as stream:
        stream.write(_sha(raw) + "\n")
    return _sha(raw)


def _pinned(path: Path) -> tuple[dict, str]:
    with path.open("rb") as stream:
        raw = stream.read(4_194_305)
    if len(raw) > 4_194_304:
        raise ValueError("Matched-current result exceeds the frozen local byte budget")
    with path.with_suffix(".sha256").open("rb") as stream:
        detached = stream.read(81)
    if len(detached) > 80 or detached.decode("ascii").strip() != _sha(raw):
        raise ValueError("Matched-current result detached hash changed")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise TypeError("Matched-current result must be an object")
    return value, _sha(raw)


def _utc_clock(value, label: str) -> datetime:
    """Require a usable UTC receipt clock, including during immutable replay."""
    try:
        when = datetime.fromisoformat(value) if isinstance(value, str) else None
        if when is None or when.utcoffset() != timedelta(0):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"Invalid UTC {label} timestamp") from None
    return when


def _forecast_chronology(document: dict, manifest: dict) -> datetime:
    frozen = _utc_clock(document.get("frozen_at_utc"), "forecast")
    if frozen < _utc_clock(manifest.get("finished_at_utc"), "acquisition manifest"):
        raise ValueError("Forecast receipt predates acquisition manifest completion")
    for receipt in manifest["source_receipts"]:
        if frozen < _utc_clock(receipt.get("finished_at_utc"), "acquisition"):
            raise ValueError("Forecast receipt predates acquisition completion")
    return frozen


def parse_position_strings(raw: bytes, group_id: str) -> tuple[list[dict], list[dict]]:
    """Validate only CSV identity/structure/time; do not decode coordinates here."""
    try:
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8")), strict=True))
    except (UnicodeDecodeError, csv.Error) as error:
        raise ValueError("GDP_CSV_INVALID") from error
    if (len(rows) != 33 or rows[0] != ["ID", "time", "latitude", "longitude"]
            or rows[1] != ["", "UTC", "degrees_north", "degrees_east"]):
        raise ValueError("GDP_CSV_SCHEMA_OR_COUNT_CHANGED")
    result = []
    for row, expected_time in zip(rows[2:], EXPECTED_TIMES, strict=True):
        if len(row) != 4 or row[0] != group_id or row[1] != expected_time:
            raise ValueError("GDP_ID_OR_EXACT_HOURLY_SCHEDULE_CHANGED")
        result.append({"drifter_id": group_id, "time_utc": row[1],
                       "latitude_deg": row[2], "longitude_deg": row[3]})
    return result[:25], result[25:]


def _context_qc(context: list[dict]) -> dict:
    """Descriptive past-only QC, called after forecasts are frozen, not a gate."""
    invalid = []
    for index, row in enumerate(context):
        try:
            latitude, longitude = float(row["latitude_deg"]), float(row["longitude_deg"])
            valid = (math.isfinite(latitude) and math.isfinite(longitude)
                     and -90 <= latitude <= 90 and -180 <= longitude <= 180)
        except (TypeError, ValueError, OverflowError):
            valid = False
        if not valid:
            invalid.append(index)
    return {"planned_context_rows": 25, "received_context_rows": len(context),
            "invalid_coordinate_indices": invalid, "used_as_whole_group_admission_gate": False,
            "first_23_positions_used_by_models": False}


def _native_axis_contract(field) -> None:
    """Accept only the reviewed native representation; never snap its labels.

    Generic raw decoding already requires float64 NetCDF coordinate variables.
    The native numbers stored in those variables must be exact promoted
    float32 labels. Latitude follows its rounded nominal lattice exactly;
    longitude allows at most one float32 ULP from its rounded nominal lattice.
    These are encoding checks, not interpolation/physics error tolerances.
    """
    latitude = field.latitude_deg
    longitude = field.longitude_deg
    if (latitude.shape != (251,) or longitude.shape != (188,)
            or latitude.dtype != np.dtype("float64")
            or longitude.dtype != np.dtype("float64")
            or not np.isfinite(latitude).all() or not np.isfinite(longitude).all()
            or not np.all(np.diff(latitude) > 0) or not np.all(np.diff(longitude) > 0)):
        raise ValueError("HYCOM_V2_NATIVE_AXIS_COUNT_DTYPE_OR_MONOTONICITY_CHANGED")
    # The generic reader normalized the actual native longitude values without
    # sorting. In this fixed western Atlantic tile, adding 360 reverses that
    # exact binary operation; interpolation keeps the original normalized array.
    native_longitude = longitude + 360.0
    latitude_nominal = (25.0 + 0.04 * np.arange(251)).astype(np.float32)
    longitude_nominal = (280.0 + 0.08 * np.arange(188)).astype(np.float32)
    if (not np.array_equal(latitude, latitude.astype(np.float32).astype(np.float64))
            or not np.array_equal(native_longitude,
                                  native_longitude.astype(np.float32).astype(np.float64))):
        raise ValueError("HYCOM_V2_NATIVE_LABELS_NOT_EXACT_FLOAT32_PROMOTED_TO_FLOAT64")
    if not np.array_equal(latitude, latitude_nominal.astype(np.float64)):
        raise ValueError("HYCOM_V2_LATITUDE_ROUNDED_FLOAT32_LATTICE_CHANGED")
    longitude_error = np.abs(native_longitude - longitude_nominal.astype(np.float64))
    longitude_ulp = np.spacing(longitude_nominal).astype(np.float64)
    if (np.any(longitude_error > longitude_ulp)
            or latitude[0] < 25.0 or latitude[-1] > 35.0
            or native_longitude[0] != 280.0 or native_longitude[-1] > 295.0):
        raise ValueError("HYCOM_V2_LONGITUDE_ENCODING_ULP_OR_NATIVE_BOUNDS_CHANGED")
    expected_shape = (3, 251, 188)
    if (field.eastward_m_s.shape != expected_shape
            or field.northward_m_s.shape != expected_shape
            or field.valid_mask.shape != expected_shape
            or field.valid_mask.dtype != np.dtype("bool")):
        raise ValueError("HYCOM_V2_NATIVE_ARRAY_SHAPE_OR_MASK_CHANGED")


def _study_field(payload: bytes):
    field = load_hycom_field_bytes(payload)
    expected = np.array(["2022-06-01T00:00:00", "2022-06-01T03:00:00",
                         "2022-06-01T06:00:00"], dtype="datetime64[us]")
    if not np.array_equal(field.time_utc, expected):
        raise ValueError("HYCOM_REQUESTED_THREE_TIMES_CHANGED")
    if field.selected_depth_m != 15.0:
        raise ValueError("HYCOM_REQUESTED_SINGLETON_FIFTEEN_METRE_DEPTH_CHANGED")
    _native_axis_contract(field)
    return field


def _inputs(directory: Path):
    from apps.ocean.reeftrace_ocean.matched_current_v2_protocol import load_acquisition

    protocol, manifest, hashes, sources = load_acquisition(directory)
    if manifest is None:
        raise ValueError("Matched-current acquisition has not been attempted; no first score is possible")
    if ([group["drifter_id"] for group in protocol["groups"]] != list(GROUP_IDS)
            or protocol["models"] != list(MODEL_IDS)
            or protocol["windows"]["horizons_s"] != list(HORIZONS_S)
            or protocol["windows"]["origin_time_utc"] != EXPECTED_TIMES[24]):
        raise ValueError("Frozen protocol and model implementation identities disagree")
    receipts = {receipt["role"]: receipt for receipt in manifest["source_receipts"]}
    contexts, targets, failures = {}, {}, {}
    for group_id in GROUP_IDS:
        role = "trajectory:" + group_id
        raw = sources.get(role)
        if raw is None:
            failures[group_id] = receipts[role]["reason"] or receipts[role]["status"]
            continue
        try:
            contexts[group_id], targets[group_id] = parse_position_strings(raw, group_id)
        except ValueError as error:
            failures[group_id] = str(error)
    forcing, current_failure = None, None
    current = receipts["hycom_currents"]
    if sources.get("hycom_currents") is not None:
        try:
            forcing = _study_field(sources["hycom_currents"])
        except (ValueError, ImportError) as error:
            current_failure = str(error)
        else:
            # The decoder consumes the immutable bytes already returned by
            # acquisition verification. Retain this independent digest check as
            # a guard against a changed decoder contract or wrong object.
            if (forcing.metadata.get("sha256") != current["sha256"]
                    or forcing.metadata.get("sha256") != _sha(sources["hycom_currents"])):
                raise ValueError("HYCOM decoded byte identity differs from verified acquisition provenance")
    else:
        current_failure = current["reason"] or current["status"]
    fields = {group_id: forcing for group_id in GROUP_IDS} if forcing is not None else {}
    current_failures = {group_id: current_failure for group_id in GROUP_IDS} if current_failure else {}
    forecasts = build_matched_current_forecasts(
        contexts, fields, failures_by_group=failures, current_failures_by_group=current_failures,
    )
    return protocol, manifest, hashes, contexts, targets, forecasts, forcing, current_failure


def evaluate_study(directory: Path = DIRECTORY, *, first_score: bool = False) -> dict:
    directory = Path(directory)
    forecast_path = directory / "forecasts.json"
    result_path = directory / "evaluation.json"
    if first_score and any(path.exists() for path in (
        forecast_path, result_path, forecast_path.with_suffix(".sha256"),
        result_path.with_suffix(".sha256"),
    )):
        raise ValueError("A first-score attempt already exists; preserve its artifacts")
    if not first_score and not result_path.is_file():
        raise ValueError("Study is not scored; replay never performs a first score")
    (protocol, manifest, hashes, contexts, targets, forecasts,
     forcing, current_failure) = _inputs(directory)
    lineage = {key: value for key, value in hashes.items() if key.endswith("sha256")}
    forecast_document = {
        "schema_version": 1, "kind": "FROZEN_MATCHED_CURRENT_FORECASTS",
        "study_id": protocol["study_id"], "lineage": lineage,
        "forecasts": forecasts, "future_coordinates_decoded": False,
    }
    if first_score:
        forecast_document["frozen_at_utc"] = datetime.now(UTC).isoformat()
        _forecast_chronology(forecast_document, manifest)
        forecast_file_hash = _save(forecast_path, forecast_document)
    else:
        saved, forecast_file_hash = _pinned(forecast_path)
        if {key: value for key, value in saved.items() if key != "frozen_at_utc"} != forecast_document:
            raise ValueError("Saved forecast receipt differs from exact frozen inputs or implementation")
        forecast_document = saved
    frozen_at = _forecast_chronology(forecast_document, manifest)
    frozen_result = None
    if not first_score:
        frozen_result, _ = _pinned(result_path)
        if _utc_clock(frozen_result.get("scored_at_utc"), "score") < frozen_at:
            raise ValueError("Score timestamp predates its forecast receipt")
    # This readback proves the persisted object exists before any target number
    # is decoded. Hashes identify the prior forecasts, not an external attestation.
    saved, digest = _pinned(forecast_path)
    if (digest != forecast_file_hash or saved != forecast_document
            or forecast_sha256(saved["forecasts"]) != saved["forecasts"]["forecast_sha256"]):
        raise ValueError("Forecast readback identity changed before scoring")
    scores = score_matched_current_forecasts(forecasts, targets)
    report = {
        "schema_version": 1, "kind": "MATCHED_CURRENT_RETROSPECTIVE_DIAGNOSTIC",
        "study_id": protocol["study_id"], "lineage": lineage,
        "forecast_file_sha256": forecast_file_hash,
        "forecast_frozen_at_utc": forecast_document["frozen_at_utc"],
        "forecasts_saved_before_target_coordinate_decode": True,
        "source_receipts": manifest["source_receipts"],
        "context_qc": {group_id: _context_qc(contexts.get(group_id, [])) for group_id in GROUP_IDS},
        "current_field": forcing.summary() if forcing is not None else None,
        "current_field_failure": current_failure,
        "scores": scores,
        "physical_validation": False, "operational_causality": False,
        "assimilation_independence_verified": False,
        "physical_alias_resolution_verified": False, "statistical_independence": False,
        "global_training": False, "heldout_tuning": False, "automatic_model_promotion": False,
        "provider_calls": False, "camera_started": False, "store_written": False,
    }
    if first_score:
        report["scored_at_utc"] = datetime.now(UTC).isoformat()
        if _utc_clock(report["scored_at_utc"], "score") < frozen_at:
            raise ValueError("Score timestamp predates its forecast receipt")
        _save(result_path, report)
    else:
        if {key: value for key, value in frozen_result.items() if key != "scored_at_utc"} != report:
            raise ValueError("Offline replay differs from the saved first score")
        report = frozen_result
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    parser.add_argument("--first-score", action="store_true",
                        help="Explicitly save forecasts and first scores after frozen acquisition.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate_study(args.directory, first_score=args.first_score)
    payload = canonical_json(report)
    if args.output:
        with args.output.open("xb") as stream:
            stream.write(payload)
    else:
        print(payload.decode(), end="")


if __name__ == "__main__":
    main()
