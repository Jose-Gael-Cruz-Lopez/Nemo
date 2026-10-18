"""Build/check an optional PUBLIC synthetic source-demo cache, never ocean scores.

The builder uses a brand-new temporary Runtime, no main app, no .env, provider,
physical recordings or messaging. It caches the normal three public fixtures;
no parameters or scientific claims change. Runtime import is opt-in and cannot
replace an existing cloud database. All input/method bytes are bound explicitly.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import math
import os
import re
import sqlite3
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATABASE = "reeftrace.sqlite3"
MANIFEST = "manifest.json"
MAX_DATABASE_BYTES = 8_388_608
MAX_MANIFEST_BYTES = 64_000
FIXTURE_FILES = ("data/sample_runs/synthetic_profile.json", "data/sample_runs/synthetic_observations.json")
TABLES = {"records", "cases", "actions", "settings", "inbox", "outbox", "transport_errors"}
EMPTY_TABLES = {"actions", "inbox", "outbox", "transport_errors"}
RECORD_COUNTS = {"profile": 1, "estimate": 3}
IDENTIFIER = re.compile(r"^(case|estimate)-[0-9a-f]{16}$")
ESTIMATE_KEYS = {
    "id", "case_id", "calibration_id", "profile_id", "model_version", "config_hash",
    "inference_mode", "status", "ranked_source", "leading_source", "compatible_sources",
    "relative_support", "confidence_kind", "absolute_fit", "best_absolute_fit", "margin",
    "likelihood_margin", "coverage", "coverage_detail", "reason_codes", "source_diagnostics",
    "assumptions", "sensitivity_results", "evidence_frame_ids", "data_origin", "physical_validation",
    "mode", "source_priors", "likelihood_support",
}
FORBIDDEN_KEYS = {"api_key", "credentials", "authorization", "human_handle", "agent_handle",
                  "phone_number", "camera_session_id", "recording_id", "jpeg", "image_bytes"}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _read(path, maximum):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Public seed requires regular files, never symlinks")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if not raw or len(raw) > maximum:
        raise ValueError("Public seed file exceeds its byte budget")
    return raw


def _method_hashes():
    paths = ["deploy/seed_demo.py", "apps/api/reeftrace_api/services/runtime.py",
             "apps/api/reeftrace_api/services/store.py", "apps/api/reeftrace_api/schemas/contracts.py"]
    for package in ("estimation/reeftrace_estimation", "transport/reeftrace_transport"):
        paths.extend(str(path.relative_to(ROOT)) for path in sorted((ROOT / "apps" / package).glob("*.py")))
    return {name: _sha(_read(ROOT / name, 300_000)) for name in paths}


def _fixture_hashes():
    return {name: _sha(_read(ROOT / name, 300_000)) for name in FIXTURE_FILES}


def _fixtures():
    from apps.api.reeftrace_api.schemas.contracts import CaseInput

    profile = json.loads(_read(ROOT / FIXTURE_FILES[0], 300_000))
    items = json.loads(_read(ROOT / FIXTURE_FILES[1], 300_000))
    if profile.get("data_origin") != "SYNTHETIC" or not isinstance(items, list) or len(items) != 3:
        raise ValueError("Only the three public synthetic source fixtures may be seeded")
    expected_profile = copy.deepcopy(profile)
    if "sensitivity_variants" not in expected_profile:
        diffusion = profile.get("transport", {}).get("diffusivity_cm2_s", .05)
        expected_profile["sensitivity_variants"] = [
            {"id": "dispersion_x0.5", "transport": {"diffusivity_cm2_s": diffusion * .5}},
            {"id": "dispersion_x2.0", "transport": {"diffusivity_cm2_s": diffusion * 2.}},
        ]
    expected = {}
    for item in items:
        clean = {key: value for key, value in item.items() if key in CaseInput.model_fields}
        clean.update(profile_id=profile["id"], mode="SYNTHETIC")
        # Matches Runtime.load_demo exactly: the fixture key precedes schema defaults.
        key = _sha(_canonical({"profile": profile, "observation": clean}))
        observation = CaseInput(**clean).model_dump()
        if observation["camera_session_id"] is not None or any(
                not frame.startswith("synthetic-") for frame in observation["evidence_frame_ids"]):
            raise ValueError("Only fixture-labelled synthetic evidence identifiers are allowed")
        expected[key] = observation
    if len(expected) != 3:
        raise ValueError("Public synthetic fixtures must be distinct")
    return expected_profile, expected


def _safe_json(raw):
    value = json.loads(raw)
    _canonical(value)  # Reject nonfinite payloads, including nested NaN.

    def inspect(item):
        if isinstance(item, dict):
            if any(str(key).lower() in FORBIDDEN_KEYS and entry is not None for key, entry in item.items()):
                raise ValueError("Public seed contains a private or physical-evidence field")
            for entry in item.values():
                inspect(entry)
        elif isinstance(item, list):
            for entry in item:
                inspect(entry)
    inspect(value)
    return value


def _check_database(path):
    """Read-only logical checks; never execute SQL supplied by the manifest."""
    expected_profile, expected_cases = _fixtures()
    # immutable avoids creating WAL/SHM next to the read-only image bundle.
    uri = Path(path).resolve().as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        if db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise ValueError("Public seed database integrity check failed")
        schema = db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master").fetchall()
        tables = {name for kind, name, _table, _sql in schema if kind == "table"}
        if tables != TABLES or any(kind not in {"table", "index"} or
                (kind == "index" and (sql is not None or not name.startswith("sqlite_autoindex_") or table not in TABLES))
                for kind, name, table, sql in schema):
            raise ValueError("Public seed database contains unexpected tables, views or triggers")
        for table in EMPTY_TABLES:
            if db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] != 0:
                raise ValueError("Public seed cannot contain actions, messages or transport state")
        settings = db.execute("SELECT key,value FROM settings").fetchall()
        if len(settings) != 1 or settings[0][0] != "session_start":
            raise ValueError("Public seed cannot contain configured projects or private settings")
        if datetime.fromisoformat(settings[0][1]).utcoffset() is None:
            raise ValueError("Public seed session timestamp is invalid")
        records = db.execute("SELECT kind,id,payload FROM records").fetchall()
        counts = {kind: sum(row[0] == kind for row in records) for kind in RECORD_COUNTS}
        if len(records) != 4 or counts != RECORD_COUNTS:
            raise ValueError("Public seed may contain only one profile and three estimates")
        profile_row = next((row for row in records if row[0] == "profile"), None)
        if profile_row is None or _safe_json(profile_row[2]) != expected_profile or profile_row[1] != expected_profile["id"]:
            raise ValueError("Public seed profile does not match the shipped synthetic fixture")
        estimates = {row[1]: _safe_json(row[2]) for row in records if row[0] == "estimate"}
        case_rows = db.execute("SELECT id,payload,revision FROM cases").fetchall()
        if len(case_rows) != 3:
            raise ValueError("Public seed must retain all three synthetic cases")
        seen = set()
        for identifier, raw, revision in case_rows:
            case = _safe_json(raw)
            key = case.get("demo_fixture_key")
            expected = expected_cases.get(key)
            metadata_keys = {"id", "created_at", "revision", "state", "evidence_id", "demo_fixture_key"}
            if (expected is None or key in seen or set(case) != set(expected) | metadata_keys
                    or any(case.get(name) != value for name, value in expected.items())
                    or case.get("id") != identifier or not IDENTIFIER.fullmatch(identifier)
                    or case.get("revision") != revision or revision != 2 or case.get("state") != "INVESTIGATE"
                    or not isinstance(case.get("created_at"), (int, float)) or not math.isfinite(case["created_at"])):
                raise ValueError("Public seed case does not match a complete synthetic fixture")
            seen.add(key)
            evidence = estimates.get(case.get("evidence_id"))
            if (not isinstance(evidence, dict) or set(evidence) - ESTIMATE_KEYS
                    or evidence.get("id") != case["evidence_id"] or not IDENTIFIER.fullmatch(evidence["id"])
                    or evidence.get("case_id") != identifier or evidence.get("mode") != "SYNTHETIC"
                    or evidence.get("profile_id") != expected_profile["id"] or evidence.get("data_origin") != "SYNTHETIC"
                    or evidence.get("physical_validation") is not False
                    or evidence.get("confidence_kind") != "relative_support_not_probability"
                    or evidence.get("status") not in {"ranked", "unknown", "invalid"}
                    or evidence.get("evidence_frame_ids") != expected["evidence_frame_ids"]):
                raise ValueError("Public seed estimate is not fixture-bound synthetic evidence")
        if len(seen) != 3 or len({case[0] for case in case_rows}) != 3:
            raise ValueError("Public seed cases cannot be replaced or duplicated")
    return {"cases": 3, "record_counts": RECORD_COUNTS, "recordings": 0, "messages": 0,
            "physical_evidence": False, "synthetic_evidence_identifiers_only": True}


def validate_bundle(directory):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir() or {path.name for path in directory.iterdir()} != {DATABASE, MANIFEST}:
        raise ValueError("Public seed bundle must contain exactly its database and manifest")
    raw_manifest = _read(directory / MANIFEST, MAX_MANIFEST_BYTES)
    manifest = json.loads(raw_manifest)
    database = _read(directory / DATABASE, MAX_DATABASE_BYTES)
    expected = {"schema_version": 1, "kind": "NEMO_PUBLIC_SYNTHETIC_SOURCE_SEED", "database_file": DATABASE,
        "database_sha256": _sha(database), "database_bytes": len(database),
        "fixture_sha256": _fixture_hashes(), "method_sha256": _method_hashes(),
        "summary": _check_database(directory / DATABASE), "physical_validation": False,
        "provider_calls": False, "ocean_first_score_executed": False}
    if not isinstance(manifest, dict) or set(manifest) != set(expected) | {"built_at_utc"} or any(
            manifest.get(key) != value for key, value in expected.items()):
        raise ValueError("Public seed manifest, fixture or method identity changed")
    when = datetime.fromisoformat(manifest["built_at_utc"])
    if when.utcoffset() is None or when.utcoffset().total_seconds() != 0:
        raise ValueError("Public seed build timestamp must be UTC")
    if _read(directory / DATABASE, MAX_DATABASE_BYTES) != database or _read(directory / MANIFEST, MAX_MANIFEST_BYTES) != raw_manifest:
        raise ValueError("Public seed bundle changed during validation")
    return manifest, database


def install_seed(directory, seed_directory):
    """Only an empty, already-owned cloud store may receive the validated cache."""
    from apps.api.reeftrace_api.cloud import CLOUD_MARKER, CLOUD_MARKER_CONTENT

    directory = Path(directory)
    target = directory / DATABASE
    if target.exists():
        return "EXISTING_STORE_UNCHANGED"
    marker = directory / CLOUD_MARKER
    if marker.is_symlink() or marker.read_text() != CLOUD_MARKER_CONTENT or {path.name for path in directory.iterdir()} != {CLOUD_MARKER}:
        raise ValueError("Public seed import requires an empty owned cloud store")
    _manifest, database = validate_bundle(seed_directory)
    # Link a fully written private staging file atomically; never replace a DB.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".public-seed-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(database)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        try:
            os.link(temporary, target)
        except FileExistsError:
            return "EXISTING_STORE_UNCHANGED"
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return "IMPORTED_PUBLIC_SYNTHETIC_FIXTURES"


def build_seed(output_directory):
    """Explicit build-time computation of existing synthetic fixtures only."""
    from adapters.chalk.agent import ChalkSettings
    from adapters.photon.transport import PhotonSettings
    from apps.api.reeftrace_api.cloud import CloudCamera
    from apps.api.reeftrace_api.core.settings import Settings
    from apps.api.reeftrace_api.services.runtime import Runtime

    output = Path(output_directory)
    if output.is_symlink() or (output.exists() and any(output.iterdir())):
        raise ValueError("Never overwrite a public seed bundle")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="nemo-public-seed-build-") as scratch:
        runtime = Runtime(Settings(_env_file=None, data_dir=Path(scratch), local_token=""))
        runtime.camera = CloudCamera()
        runtime.chalk_settings = lambda: ChalkSettings(enabled=False)
        runtime.photon_settings = lambda: PhotonSettings(enabled=False)
        loaded = asyncio.run(runtime.load_demo(ROOT / "data/sample_runs"))
        if len(loaded["cases"]) != 3 or loaded["mode"] != "SYNTHETIC":
            raise ValueError("Synthetic source demo did not produce all three cases")
        # SQLite backup creates a standalone file, with no transient WAL/SHM.
        with runtime.store.connection() as source_db, closing(sqlite3.connect(output / DATABASE)) as destination:
            source_db.backup(destination)
            destination.execute("PRAGMA journal_mode=DELETE")
            destination.execute("VACUUM")
        database = _read(output / DATABASE, MAX_DATABASE_BYTES)
        manifest = {"schema_version": 1, "kind": "NEMO_PUBLIC_SYNTHETIC_SOURCE_SEED", "database_file": DATABASE,
            "database_sha256": _sha(database), "database_bytes": len(database),
            "fixture_sha256": _fixture_hashes(), "method_sha256": _method_hashes(),
            "summary": _check_database(output / DATABASE), "physical_validation": False,
            "provider_calls": False, "ocean_first_score_executed": False,
            "built_at_utc": datetime.now(UTC).isoformat()}
        with (output / MANIFEST).open("xb") as stream:
            stream.write(json.dumps(manifest, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n")
    validate_bundle(output)
    for path in output.iterdir():
        os.chmod(path, 0o444)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_seed(args.output_dir)
    print(json.dumps({"kind": manifest["kind"], "summary": manifest["summary"],
                      "database_sha256": manifest["database_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
