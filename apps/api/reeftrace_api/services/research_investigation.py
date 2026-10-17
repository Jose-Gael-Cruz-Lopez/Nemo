"""Public-study snapshots and an isolated read-only research discussion."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import re

from adapters.chalk.research import investigate_study


def load_fresh_physics_report() -> dict:
    """Lazy import keeps acquisition/research execution out of API startup."""
    from apps.ocean.reeftrace_ocean.fresh_drifter import run_fresh_drifter_study
    return run_fresh_drifter_study()


def snapshot_identity(report: dict) -> tuple[str, str]:
    if (not isinstance(report, dict) or report.get("schema_version") != 1
            or report.get("kind") != "FRESH_NOAA_DRIFTER_STUDY"
            or report.get("design_status") != "FROZEN_NEW_GDP_ID_GROUP_EVALUATION_WITH_KNOWN_ALIAS_EXCLUSIONS"
            or report.get("status") not in {
                "NOT_ACQUIRED", "ACQUISITION_BLOCKED", "PARTIAL_COVERAGE", "COMPLETED"}):
        raise ValueError("Unsupported verified fresh-study identity")
    protocol = report.get("protocol_sha256")
    if not isinstance(protocol, str) or re.fullmatch(r"[0-9a-f]{64}", protocol) is None:
        raise ValueError("Fresh-study protocol hash is unavailable")
    if (not isinstance(report.get("coverage"), dict)
            or not isinstance(report.get("groups"), list)
            or not isinstance(report.get("models"), list)
            or not isinstance(report.get("provenance"), dict)
            or not isinstance(report.get("flags"), dict)
            or not isinstance(report.get("protocol", {}), dict)):
        raise TypeError("Fresh-study evidence structure is invalid")
    flags = report["flags"]
    if not isinstance(flags.get("new_acquisition"), bool) or any(flags.get(key) is not False for key in (
            "physical_validation", "calibrated_probability", "automatic_model_promotion",
            "provider_calls", "camera_started", "store_written", "operational_causality",
            "statistical_independence")):
        raise ValueError("Fresh-study scientific boundaries changed")
    if (report["provenance"].get("integrity_verified") is not True
            or report["provenance"].get("hashes", {}).get("protocol_sha256") != protocol):
        raise ValueError("Fresh-study verified provenance is inconsistent")
    payload = json.dumps(report, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode()
    if len(payload) > 1_000_000:
        raise ValueError("Fresh study exceeds its snapshot byte budget")
    return hashlib.sha256(payload).hexdigest(), protocol


class StudyBackend:
    """One server-bound snapshot; no runtime, store, camera or action capability."""

    def __init__(self, report: dict):
        self.report = copy.deepcopy(report)
        self.report_hash, self.protocol_hash = snapshot_identity(self.report)
        self.evidence_ids = ["fresh-study:" + self.report_hash,
                             "fresh-protocol:" + self.protocol_hash]

    async def call(self, name: str, arguments: dict) -> dict:
        if name != "get_study_evidence" or arguments:
            raise ValueError("Research has one read-only server-bound evidence tool")
        model_keys = ("id", "label", "status", "metrics", "reason_codes", "complete_groups")
        group_keys = ("block_id", "slot", "drifter_id", "wmo", "status", "reason_codes")
        report = self.report
        groups = [{**{key: group[key] for key in group_keys if key in group},
                   "models": [{key: model[key] for key in model_keys if key in model}
                              for model in group.get("models", [])]}
                  for group in report.get("groups", [])]
        return copy.deepcopy({"ok": True, "evidence_ids": self.evidence_ids,
            "study": {"kind": report["kind"], "design_status": report["design_status"],
                "status": report["status"], "snapshot_report_sha256": self.report_hash,
                "protocol_sha256": self.protocol_hash, "coverage": report["coverage"],
                "models": [{key: model[key] for key in model_keys if key in model}
                           for model in report.get("models", [])], "groups": groups,
                "provenance": report.get("provenance", {}), "flags": report.get("flags", {}),
                "model_definitions": report.get("protocol", {}).get("models", {}),
                "pre_outcome_amendment": report.get("protocol", {}).get("pre_outcome_amendment"),
                "limitations": report.get("limitations", []),
                "interpretation": "Public buoy-motion forecasts, not plastic source attribution or tank prevention. Missing and failed outcomes stay unknown. Different drifter IDs do not prove statistical independence; no calibrated probability or automatic model promotion."}})


async def investigate_fresh_physics(runtime, question: str, *, client=None, loader=None) -> dict:
    """Keep deterministic evidence visible on model failure; reject stale snapshots."""
    read = loader or load_fresh_physics_report
    report = await asyncio.to_thread(read)
    backend = StudyBackend(report)
    result = await investigate_study(question, backend,
        {"study_evidence_id": backend.evidence_ids[0],
         "protocol_evidence_id": backend.evidence_ids[1]}, runtime.chalk_settings(), client=client)
    # Research lineage must still match when a slow model response finishes.
    latest = await asyncio.to_thread(read)
    if snapshot_identity(latest) != (backend.report_hash, backend.protocol_hash):
        raise ValueError("Fresh-study snapshot changed during the research review")
    return {"schema_version": 1, "kind": "FRESH_DRIFTER_RESEARCH_INVESTIGATION",
        "scope": "READ_ONLY_FRESH_STUDY", **result, "research_report": report,
        "snapshot_report_sha256": backend.report_hash, "protocol_sha256": backend.protocol_hash,
        "store_written": False, "physical_validation": False, "hardware_actuation": False}
