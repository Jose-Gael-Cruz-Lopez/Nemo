"""Export public, verified ocean snapshots; no acquisition, keys or runtime/store."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from apps.api.reeftrace_api.services.ocean_prevention_investigation import snapshot_identity
from apps.ocean.reeftrace_ocean.ocean_prevention import SUPPORTED_SCENARIOS, run_ocean_prevention

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "dashboard/showcase/ocean-reports.json"
MODES = ("forecast_snapshot", "archived_forecast_snapshot")
ARCHIVAL_LIMITATION = (
    "The valid-time window has ended; this is an archived forecast snapshot, not live conditions."
)


def canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def mode_variant(report: dict, mode: str) -> dict:
    """Freshness changes representation only; never recompute or change trajectories."""
    if mode not in MODES:
        raise ValueError("Unsupported snapshot representation")
    variant = copy.deepcopy(report)
    variant.pop("report_sha256", None)
    variant["mode"] = mode
    # The source factory labels expiry using its execution clock. Derive that
    # presentation-only sentence from the selected representation instead, so
    # exporting before or after expiry produces the same two verified variants.
    variant["limitations"] = [
        item for item in variant["limitations"] if item != ARCHIVAL_LIMITATION
    ]
    if mode == "archived_forecast_snapshot":
        variant["limitations"].append(ARCHIVAL_LIMITATION)
    variant["report_sha256"] = hashlib.sha256(canonical(variant).encode()).hexdigest()
    snapshot_identity(variant)
    raw = canonical(variant)
    return {"report_json": raw, "bytes_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "report_sha256": variant["report_sha256"]}


def build_export(*, generated_at: datetime | None = None, source_commit: str | None = None) -> dict:
    now = generated_at or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Export time must be timezone-aware")
    if source_commit is None:
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    reports = {}
    for identity in SUPPORTED_SCENARIOS:
        report = run_ocean_prevention(identity)
        snapshot_identity(report)
        reports[identity] = {mode: mode_variant(report, mode) for mode in MODES}
    return {
        "schema_version": 1, "kind": "PUBLIC_READ_ONLY_OCEAN_SHOWCASE",
        "generated_at_utc": now.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "git_head_at_export": source_commit,
        "exporter_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "provenance": "Pinned local current bytes; verified method/scenario/report hashes. "
                      "Git HEAD identifies the export checkpoint; method_sha256 identifies "
                      "the exact scientific source bytes, including uncommitted changes.",
        "freshness_policy": "Select archived only after valid_end_utc. Both representations "
                            "have independently verified full-report hashes. Paths are identical.",
        "provider_calls": False, "network_acquisition": False, "store_written": False,
        "hardware_actuation": False, "reports": reports,
    }


def write_export(destination: Path = DESTINATION) -> dict:
    envelope = build_export()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(canonical(envelope) + "\n")
    return {"path": str(destination), "scenario_count": len(envelope["reports"]),
            "generated_at_utc": envelope["generated_at_utc"], "provider_calls": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DESTINATION)
    print(json.dumps(write_export(parser.parse_args().output)))
