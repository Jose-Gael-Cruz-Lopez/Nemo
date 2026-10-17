"""New immutable matched-current design, identity and receipt checks; no network/scoring."""
from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import math
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlencode

ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = ROOT / "data/public/matched-current-v1"
STUDY_ID = "matched-current-gdp-hycom-15m-v1"
IDENTITY_RELATIVE = "apps/ocean/reeftrace_ocean/matched_current_identity.py"
MODEL_IDS = ("stationary", "last_drift", "current_only")
GROUPS = (("300234066836710", "6202613"), ("300534061292930", "4102636"))
ORIGIN = "2022-06-01T00:00:00Z"
CONTEXT_START = "2022-05-31T00:00:00Z"
END = "2022-06-01T06:00:00Z"
CSV_COLUMNS = ["ID", "time", "latitude", "longitude"]
CSV_UNITS = ["", "UTC", "degrees_north", "degrees_east"]
GDP_BASE = "https://erddap.aoml.noaa.gov/gdp/erddap/tabledap/drifter_hourly_qc"
HYCOM_BASE = "https://ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z/2022"
METADATA = {
    "gdp_metadata": ("gdp-hourly.das", "66cdd12aff149d25cfa03fbcbe2046fb5657e7aa31795f0bfa0c41c3527efd39"),
    "gdp_identity": ("gdp-origin-identity-drogue.csv", "fe20f70d249e8e099ba63e97341ed52c3c1dff34f5055b6946a4438679b6a339"),
    "hycom_metadata": ("hycom-2022-ncss-dataset.xml", "741d5fcc5cd784415c9b8582394a05f4102f81f0d883821e8267a61ea698164d"),
}
SOURCE_PATHS = (
    "apps/__init__.py", "apps/ocean/__init__.py", "apps/ocean/reeftrace_ocean/__init__.py",
    "apps/ocean/reeftrace_ocean/matched_current_protocol.py",
    "apps/ocean/reeftrace_ocean/matched_current.py", "apps/ocean/reeftrace_ocean/hycom.py",
    "apps/ocean/reeftrace_ocean/advection.py", "apps/ocean/reeftrace_ocean/field.py",
    "apps/ocean/reeftrace_ocean/benchmark.py", "apps/ocean/reeftrace_ocean/data.py",
    "scripts/freeze_matched_current_protocol.py", "scripts/fetch_matched_current_study.py",
    "scripts/evaluate_matched_current_study.py", "pyproject.toml",
)
ROLE_ORDER = ("gdp_metadata", "gdp_identity", "hycom_metadata",
              *("trajectory:" + identifier for identifier, _ in GROUPS), "hycom_currents")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def when(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.utcoffset() != timedelta(0):
        raise ValueError("Matched-current timestamps require UTC")
    return result


def read_bytes(path, maximum=12 * 1024 * 1024) -> bytes:
    with Path(path).open("rb") as stream:
        value = stream.read(maximum + 1)
    if len(value) > maximum:
        raise ValueError("Matched-current artifact exceeds its byte budget")
    return value


def save_json(path, value) -> str:
    path = Path(path)
    payload = canonical_json(value)
    with path.open("xb") as stream:
        stream.write(payload)
    with path.with_suffix(".sha256").open("x") as stream:
        stream.write(sha(payload) + "\n")
    return sha(payload)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key in matched-current artifact")
        result[key] = value
    return result


def pinned_json(directory, name, expected=None):
    path = _safe_path(Path(directory), name + ".json")
    raw = read_bytes(path, 1024 * 1024)
    digest = sha(raw)
    if expected is not None and digest != expected or read_bytes(
        _safe_path(Path(directory), name + ".sha256"), 80
    ).decode().strip() != digest:
        raise ValueError("Matched-current artifact hash changed")
    value = json.loads(raw, object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise TypeError("Matched-current artifact requires a JSON object")
    return value, digest


def _safe_path(directory: Path, relative: str) -> Path:
    path = directory / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("Unsafe matched-current artifact path")
    if not path.resolve().is_relative_to(directory.resolve()):
        raise ValueError("Matched-current artifact escapes its directory")
    if any((directory / Path(*Path(relative).parts[:i])).is_symlink()
           for i in range(1, len(Path(relative).parts) + 1)):
        raise ValueError("Symlinked matched-current artifact is not accepted")
    return path


def _git_head(root: Path) -> str:
    value = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("Invalid source checkpoint")
    return value


def contract() -> dict:
    """All acquisition choices are fixed before values; never infer a new query."""
    identity_query = ("ID,WMO,typebuoy,drogue_lost_date,DrogueCenterDepth"
                      "&time=2022-06-01T00:00:00Z&latitude>=25&latitude<=35"
                      "&longitude>=-80&longitude<=-65&distinct()")
    sources = {
        "gdp_metadata": {"url": GDP_BASE + ".das", "raw_path": "raw/gdp-metadata.das",
                         "max_bytes": 256 * 1024, "depends_on": []},
        "gdp_identity": {"url": GDP_BASE + ".csv?" + quote(identity_query, safe=",&="),
                         "raw_path": "raw/gdp-origin-identity.csv",
                         "max_bytes": 32 * 1024, "depends_on": []},
        "hycom_metadata": {"url": HYCOM_BASE + "/dataset.xml",
                           "raw_path": "raw/hycom-metadata.xml",
                           "max_bytes": 256 * 1024, "depends_on": []},
    }
    for role, (_, digest) in METADATA.items():
        sources[role]["expected_sha256"] = digest
    for identifier, _ in GROUPS:
        query = (",".join(CSV_COLUMNS) + f'&ID="{identifier}"'
                 f"&time>={CONTEXT_START}&time<={END}")
        sources["trajectory:" + identifier] = {
            "url": GDP_BASE + ".csv?" + quote(query, safe=",&="),
            "raw_path": "raw/drifter-" + identifier + ".csv", "max_bytes": 32 * 1024,
            "depends_on": ["gdp_metadata", "gdp_identity"],
        }
    current_query = urlencode([
        ("var", "water_u,water_v"), ("north", "35"), ("south", "25"),
        ("west", "280"), ("east", "295"), ("horizStride", "1"),
        ("time_start", ORIGIN), ("time_end", END), ("timeStride", "1"),
        ("vertCoord", "15"), ("accept", "netcdf"),
    ])
    sources["hycom_currents"] = {
        "url": HYCOM_BASE + "?" + current_query, "raw_path": "raw/hycom-currents.nc",
        "max_bytes": 8 * 1024 * 1024, "depends_on": ["hycom_metadata"],
    }
    return {
        "schema_version": 1, "kind": "RETROSPECTIVE_MATCHED_CURRENT_PROTOCOL",
        "study_id": STUDY_ID, "design_status": "FROZEN_BEFORE_SCIENTIFIC_VALUE_ACQUISITION",
        "groups": [{"drifter_id": i, "wmo": w} for i, w in GROUPS], "models": list(MODEL_IDS),
        "windows": {"context_start_utc": CONTEXT_START, "origin_time_utc": ORIGIN,
                    "end_utc": END, "context_count": 25, "heldout_count": 6,
                    "cadence_s": 3600, "horizons_s": list(range(3600, 21601, 3600))},
        "gdp_schema": {"columns": CSV_COLUMNS, "units": CSV_UNITS, "row_count": 31,
                       "coordinate_decoding_during_acquisition": False},
        "forcing": {"source": "HYCOM_GOFS_3.1_GLBy0.08_expt93.0_UV3Z_2022",
                    "depth_m": 15, "variables": ["water_u", "water_v"],
                    "native_bbox": {"west": 280, "east": 295, "south": 25, "north": 35},
                    "times_utc": [ORIGIN, "2022-06-01T03:00:00Z", END],
                    "native_stride": 1, "longitude": "((lon+180)%360)-180; preserve native indices",
                    "raw_fill": -30000, "decimal_scale": 0.001, "offset": 0,
                    "solver_step_s": 300, "output_step_s": 3600, "maximum_samples": 250000,
                    "maximum_steps": 2048, "maximum_speed_m_s": 10},
        "budgets": {"requests_max": 6, "total_bytes": 12 * 1024 * 1024,
                    "connect_timeout_s": 5, "timeout_s": 45, "wall_time_s": 180,
                    "retries": 0, "redirects": False, "fallback_endpoints": False,
                    "connections": 1, "accept_encoding": "identity",
                    "oversize_detection_chunk_bytes": 8192,
                    "total_bytes_scope": "retained body cap; one detection chunk may exceed it"},
        "sources": sources, "role_order": list(ROLE_ORDER),
        "transport_references": [
            "https://docs.unidata.ucar.edu/tds/current/userguide/ncss_grid.html",
            "https://www.hycom.org/dataserver/access-methods/ncss",
        ],
        "metrics": {"planned_groups": 2, "planned_model_tracks": 6, "planned_cells": 36,
                    "unique_future_targets": 12, "score": "spherical_great_circle_metres_R6371008.8",
                    "primary": "equal-ID macro ADE/FDE withheld unless all36 cells scored",
                    "failures": "retain every planned cell, null error and explicit reasons"},
        "isolation": {"context_for_models": "origin only; last_drift final two only",
                      "all_tracks_frozen_before_future_coordinate_access": True,
                      "no_fitting_or_tuning": True, "no_replacements": True},
        "flags": {"physical_validation": False, "operational_causality": False,
                  "assimilation_independence_verified": False, "statistical_independence": False,
                  "physical_alias_resolution_verified": False, "automatic_model_promotion": False},
    }


def build_protocol(root=None) -> dict:
    root = Path(root or ROOT)
    evidence = {}
    for role, (name, expected) in METADATA.items():
        path = root / "docs/research-evidence/matched-current-metadata" / name
        payload = read_bytes(path)
        if sha(payload) != expected:
            raise ValueError("Existing matched-current metadata seed changed")
        evidence[role] = {"path": path.relative_to(root).as_posix(),
                          "bytes": len(payload), "sha256": expected}
    identity_paths = ("data/public/noaa-fresh-drifter-v2/raw/identity-aliases.csv",
                      "data/public/noaa-fresh-drifter-v2/exclusions.json",
                      "data/public/noaa-fresh-drifter-v2/selection.json")
    for name in identity_paths:
        payload = read_bytes(root / name)
        evidence[name] = {"path": name, "bytes": len(payload), "sha256": sha(payload)}
    # Metadata-only identity audit. Never touch any position/forecast file.
    rows = list(csv.reader(io.StringIO(read_bytes(root / identity_paths[0]).decode())))
    if rows[:2] != [["ID", "WMO"], ["", ""]]:
        raise ValueError("Identity registry schema changed")
    by_id, by_wmo = {}, {}
    for row in rows[2:]:
        if len(row) != 2:
            raise ValueError("Identity registry row changed")
        identifier, wmo = row
        if wmo.isdigit() and int(wmo) > 0:
            by_id.setdefault(identifier, set()).add(wmo)
            by_wmo.setdefault(wmo, set()).add(identifier)
    exclusions = json.loads(read_bytes(root / identity_paths[1]))["reserved_gdp_ids"]
    selected = json.loads(read_bytes(root / identity_paths[2]))["groups"]
    exposed = {g["drifter_id"] for g in selected}
    for identifier, wmo in GROUPS:
        if (by_id.get(identifier) != {wmo} or by_wmo.get(wmo) != {identifier}
                or identifier in exclusions or identifier in exposed):
            raise ValueError("Matched-current identity/exclusion audit failed")
    return {**contract(), "frozen_at_utc": utc(),
            "source_checkpoint": {"git_head": _git_head(root),
                                  "note": "Commit all pinned sources, protocol and identity before values."},
            "implementation_sha256": {name: sha(read_bytes(root / name)) for name in SOURCE_PATHS},
            "metadata_evidence": evidence}


def freeze_protocol(directory=None, *, root=None) -> dict:
    """Explicit metadata-only generator. Never called by a public/API reader."""
    root = Path(root or ROOT)
    directory = Path(directory or root / "data/public/matched-current-v1")
    identity = root / IDENTITY_RELATIVE
    if directory.exists() or identity.exists():
        raise ValueError("Matched-current design already exists; never overwrite a freeze")
    value = build_protocol(root)
    directory.mkdir(parents=True, exist_ok=False)
    digest = save_json(directory / "protocol.json", value)
    identity.parent.mkdir(parents=True, exist_ok=True)
    with identity.open("x") as stream:
        stream.write(f'STUDY_ID = {STUDY_ID!r}\nPROTOCOL_SHA256 = {digest!r}\n')
    return {"study_id": STUDY_ID, "protocol_sha256": digest,
            "scientific_values_acquired": False, "identity_generated": True}


def _trusted_hash(root: Path) -> str:
    path = root / IDENTITY_RELATIVE
    if not path.exists():
        raise ValueError("Matched-current protocol is not frozen; trusted identity is absent")
    try:
        tree = ast.parse(read_bytes(path, 512).decode())
    except SyntaxError as error:
        raise ValueError("Untrusted matched-current identity syntax") from error
    values = {}
    for node in tree.body:
        if (not isinstance(node, ast.Assign) or len(node.targets) != 1
                or not isinstance(node.targets[0], ast.Name) or not isinstance(node.value, ast.Constant)
                or not isinstance(node.value.value, str) or node.targets[0].id in values):
            raise ValueError("Untrusted matched-current identity source")
        values[node.targets[0].id] = node.value.value
    if (set(values) != {"STUDY_ID", "PROTOCOL_SHA256"} or values["STUDY_ID"] != STUDY_ID
            or not re.fullmatch(r"[0-9a-f]{64}", values["PROTOCOL_SHA256"])):
        raise ValueError("Untrusted matched-current identity constants")
    return values["PROTOCOL_SHA256"]


def load_protocol(directory=None, *, root=None):
    root = Path(root or ROOT)
    directory = Path(directory or root / "data/public/matched-current-v1")
    protocol, digest = pinned_json(directory, "protocol", _trusted_hash(root))
    expected = contract()
    if set(protocol) != set(expected) | {"frozen_at_utc", "source_checkpoint",
                                         "implementation_sha256", "metadata_evidence"}:
        raise ValueError("Matched-current protocol schema changed")
    if any(protocol[k] != v for k, v in expected.items()):
        raise ValueError("Matched-current protocol query, schema or scientific contract changed")
    when(protocol["frozen_at_utc"])
    checkpoint = protocol["source_checkpoint"]
    if (set(checkpoint) != {"git_head", "note"}
            or not re.fullmatch(r"[0-9a-f]{40}", checkpoint["git_head"])):
        raise ValueError("Matched-current source checkpoint changed")
    if set(protocol["implementation_sha256"]) != set(SOURCE_PATHS):
        raise ValueError("Matched-current dependency set changed")
    for name, expected_hash in protocol["implementation_sha256"].items():
        if sha(read_bytes(root / name)) != expected_hash:
            raise ValueError("Matched-current implementation changed after freeze")
    expected_evidence = build_protocol(root)["metadata_evidence"]
    if protocol["metadata_evidence"] != expected_evidence:
        raise ValueError("Matched-current metadata/identity seed changed after freeze")
    return protocol, {"protocol_sha256": digest,
                      "trusted_identity_sha256": sha(read_bytes(root / IDENTITY_RELATIVE, 512))}


def validate_trajectory_schema(payload: bytes, identifier: str) -> None:
    """Validate structure only; coordinate cells deliberately remain undecoded."""
    try:
        rows = list(csv.reader(io.StringIO(payload.decode("utf-8")), strict=True))
    except csv.Error as error:
        raise ValueError("Malformed GDP trajectory CSV") from error
    if len(rows) != 33 or rows[:2] != [CSV_COLUMNS, CSV_UNITS]:
        raise ValueError("GDP trajectory needs exact31-row frozen schema/units")
    start = when(CONTEXT_START)
    for index, row in enumerate(rows[2:]):
        expected = (start + timedelta(hours=index)).isoformat().replace("+00:00", "Z")
        if len(row) != 4 or row[0] != identifier or row[1] != expected:
            raise ValueError("GDP trajectory ID or hourly UTC structure changed")


def validate_source(role: str, payload: bytes, source: dict) -> None:
    if role in METADATA and sha(payload) != source["expected_sha256"]:
        raise ValueError("PINNED_METADATA_CHANGED")
    if role.startswith("trajectory:"):
        validate_trajectory_schema(payload, role.split(":", 1)[1])
    if role == "hycom_currents" and not payload.startswith(
            (b"CDF\x01", b"CDF\x02", b"\x89HDF\r\n\x1a\n")):
        raise ValueError("HYCOM_RESPONSE_IS_NOT_NETCDF")


NETCDF_CONTENT_TYPES = {"application/x-netcdf", "application/x-netcdf4",
                        "application/netcdf", "application/octet-stream"}
TRANSPORT_FAILURES = {
    "HTTPError", "RequestError", "TransportError", "TimeoutException", "NetworkError",
    "ProtocolError", "ConnectError", "ReadError", "WriteError", "CloseError", "ConnectTimeout",
    "ReadTimeout", "WriteTimeout", "PoolTimeout", "RemoteProtocolError", "LocalProtocolError",
    "UnsupportedProtocol", "ProxyError", "DecodingError", "TooManyRedirects", "HTTPStatusError",
}


def _failure_semantics(row, body, spec, dependencies_ok, attempts, received, retained, limits):
    """Recompute observable failure conditions, not just self-reported status strings."""
    role, status, reason = row["role"], row["status"], row["reason"]
    attempted, complete = row["request_attempted"], row["response_complete"]
    http_status, encoding = row["http_status"], row["content_encoding"]
    if not dependencies_ok:
        return (status == "BLOCKED" and reason == "DEPENDENCY_UNAVAILABLE" and not attempted
                and not complete and http_status is None and row["raw_path"] is None
                and body is None and row["received_bytes"] == row["retained_bytes"] == 0
                and encoding is row["content_type"] is None)
    if status == "BLOCKED":
        return False
    if not attempted:
        exhausted = (row["elapsed_wall_s"] >= limits["wall_time_s"]
                     or attempts >= limits["requests_max"] or received >= limits["total_bytes"])
        return (status == "FETCH_FAILED" and reason == "ACQUISITION_BUDGET_EXHAUSTED"
                and exhausted and not complete and http_status is None and body is None
                and row["raw_path"] is None and row["received_bytes"] == row["retained_bytes"] == 0
                and encoding is row["content_type"] is None)
    if status in {"METADATA_INVALID", "SCHEMA_INVALID"}:
        expected = "METADATA_INVALID" if role in METADATA else "SCHEMA_INVALID"
        expected_reason = "PINNED_METADATA_CHANGED" if role in METADATA else "FROZEN_VALUE_SCHEMA_INVALID"
        if (status != expected or reason != expected_reason or http_status != 200
                or not complete or body is None or encoding not in {"", "identity"}
                or role == "hycom_currents" and row["content_type"] not in NETCDF_CONTENT_TYPES):
            return False
        try:
            validate_source(role, body, spec)
        except (ValueError, UnicodeError, TypeError, OverflowError):
            return True
        return False
    if status != "FETCH_FAILED":
        return False
    if reason == "HTTP_ERROR":
        return complete and http_status is not None and http_status != 200
    if reason == "CONTENT_ENCODING_MISMATCH":
        return complete and http_status == 200 and encoding not in {"", "identity", None}
    if reason == "CONTENT_TYPE_MISMATCH":
        return (complete and http_status == 200 and encoding in {"", "identity"}
                and role == "hycom_currents" and row["content_type"] not in NETCDF_CONTENT_TYPES)
    if complete:
        return False
    if reason == "RESPONSE_SIZE_BUDGET":
        return (http_status is not None and row["received_bytes"] > row["retained_bytes"]
                and (row["retained_bytes"] == spec["max_bytes"]
                     or retained + row["retained_bytes"] == limits["total_bytes"]))
    if reason == "WALL_TIME_BUDGET":
        return http_status is not None and row["elapsed_wall_s"] >= limits["wall_time_s"]
    return reason == "ACQUISITION_DEADLINE" or reason in TRANSPORT_FAILURES


def load_acquisition(directory=None, *, root=None):
    root = Path(root or ROOT)
    directory = Path(directory or root / "data/public/matched-current-v1")
    protocol, hashes = load_protocol(directory, root=root)
    if not (directory / "manifest.json").exists():
        return protocol, None, hashes, {}
    manifest, digest = pinned_json(directory, "manifest")
    start_receipt, start_hash = pinned_json(directory, "acquisition-start")
    if (manifest.get("study_id") != STUDY_ID or manifest.get("protocol_sha256") != hashes["protocol_sha256"]
            or manifest.get("trusted_identity_sha256") != hashes["trusted_identity_sha256"]
            or manifest.get("scientific_scores_computed") is not False
            or manifest.get("no_replacements") is not True
            or [r["role"] for r in manifest["source_receipts"]] != list(ROLE_ORDER)):
        raise ValueError("Matched-current acquisition lineage changed")
    started, finished = when(manifest["started_at_utc"]), when(manifest["finished_at_utc"])
    if (started < when(protocol["frozen_at_utc"]) or finished < started
            or start_receipt.get("study_id") != STUDY_ID
            or start_receipt.get("protocol_sha256") != hashes["protocol_sha256"]
            or start_receipt.get("trusted_identity_sha256") != hashes["trusted_identity_sha256"]
            or start_receipt.get("scientific_scores_computed") is not False
            or start_receipt.get("git_head_at_acquisition") != manifest.get("git_head_at_acquisition")
            or not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("git_head_at_acquisition")))
            or not when(protocol["frozen_at_utc"]) <= when(start_receipt["started_at_utc"]) <= started):
        raise ValueError("Matched-current acquisition chronology changed")
    sources, attempts, received, retained = {}, 0, 0, 0
    previous_elapsed = 0
    previous_finished = started
    statuses = {"DOWNLOADED", "FETCH_FAILED", "BLOCKED", "METADATA_INVALID", "SCHEMA_INVALID"}
    for row in manifest["source_receipts"]:
        role = row["role"]
        spec = protocol["sources"][role]
        if (row["source_url"] != spec["url"] or row["status"] not in statuses
                or type(row["request_attempted"]) is not bool
                or type(row["received_bytes"]) is not int or row["received_bytes"] < 0
                or type(row["retained_bytes"]) is not int or not 0 <= row["retained_bytes"] <= spec["max_bytes"]
                or row["bytes"] != row["retained_bytes"]
                or row["received_bytes"] < row["retained_bytes"]
                or row["received_bytes"] > row["retained_bytes"] + 8192
                or type(row["response_complete"]) is not bool
                or row["http_status"] is not None and (type(row["http_status"]) is not int
                                                       or not 100 <= row["http_status"] <= 599)
                or type(row["elapsed_wall_s"]) not in {int, float}
                or not math.isfinite(row["elapsed_wall_s"])
                or row["elapsed_wall_s"] < previous_elapsed
                or when(row["started_at_utc"]) < previous_finished
                or not when(row["started_at_utc"]) <= when(row["finished_at_utc"]) <= finished):
            raise ValueError("Matched-current acquisition receipt changed")
        if row["raw_path"] is None:
            if row["retained_bytes"] or row["sha256"] is not None:
                raise ValueError("Missing matched-current raw body changed")
            body = None
        else:
            if row["raw_path"] != spec["raw_path"]:
                raise ValueError("Matched-current raw path changed")
            path = _safe_path(directory, row["raw_path"])
            body = read_bytes(path, spec["max_bytes"])
            detached = _safe_path(directory, Path(row["raw_path"]).with_suffix(".sha256").as_posix())
            if (len(body) != row["retained_bytes"] or sha(body) != row["sha256"]
                    or read_bytes(detached, 80).decode().strip() != sha(body)):
                raise ValueError("Matched-current raw body hash changed")
        dependencies_ok = all(sources.get(dep) is not None for dep in spec["depends_on"])
        if row["status"] == "DOWNLOADED":
            if (body is None or not dependencies_ok or row["http_status"] != 200
                    or row["response_complete"] is not True or row["reason"] is not None
                    or not row["request_attempted"] or row["received_bytes"] != row["retained_bytes"]
                    or row["content_encoding"] not in {"", "identity"}
                    or role == "hycom_currents" and row["content_type"] not in NETCDF_CONTENT_TYPES):
                raise ValueError("Matched-current success contradicts its transport/dependencies")
            validate_source(role, body, spec)
            sources[role] = body
        else:
            if not _failure_semantics(row, body, spec, dependencies_ok, attempts, received,
                                      retained, protocol["budgets"]):
                raise ValueError("Matched-current failure reason contradicts its actual evidence")
            sources[role] = None
        attempts += row["request_attempted"]
        received += row["received_bytes"]
        retained += row["retained_bytes"]
        previous_elapsed = row["elapsed_wall_s"]
        previous_finished = when(row["finished_at_utc"])
    if (attempts != manifest["requests_attempted"] or attempts > protocol["budgets"]["requests_max"]
            or received != manifest["response_bytes_received"]
            or retained != manifest["response_bytes_retained"]
            or retained > protocol["budgets"]["total_bytes"]
            or received > protocol["budgets"]["total_bytes"] + 8192):
        raise ValueError("Matched-current acquisition budget accounting changed")
    hashes["manifest_sha256"] = digest
    hashes["acquisition_start_sha256"] = start_hash
    return protocol, manifest, hashes, sources
