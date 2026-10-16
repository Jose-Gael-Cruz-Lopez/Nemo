"""Shared application operations; the agent has no truth or actuator access."""

import asyncio
import os
from functools import lru_cache

from .contracts import CaseInput, ModelConfig, Profile
from .engine import PRESETS, estimate, sensitivity
from .store import Store


@lru_cache
def get_store():
    return Store(os.environ.get("REEFTRACE_DB_PATH", "data/runs/reeftrace.sqlite3"))


def profile_for(store, calibration_id):
    profiles = [p for p in store.list("profile") if p["profile"]["id"] == calibration_id]
    if not profiles:
        raise KeyError("Calibration profile not registered")
    return Profile.model_validate(profiles[0]["profile"])


def register_profile(store, profile):
    if any(p["profile"]["id"] == profile.id for p in store.list("profile")):
        raise ValueError("Calibration IDs are immutable; create a new ID")
    return store.put("profile", {"profile": profile.model_dump()})


def create_case(store, case, config=None):
    profile = profile_for(store, case.calibration_id)
    config = config or ModelConfig()
    if case.mode == "live" and (
        store.setting("rig_state") != "ready"
        or store.setting("active_calibration") != case.calibration_id
    ):
        profile = profile.model_copy(update={"validity": "invalid"})
    stored = store.put("case", case.model_dump())
    result = estimate(case, profile, config)
    result["sensitivity_result_ids"] = []
    if not result["reason_codes"]:
        variants = [result]
        for low, high in PRESETS.values():
            variant_config = config.model_copy(update={"min_age_s": low, "max_age_s": high})
            if variant_config != config:
                variants.append(estimate(case, profile, variant_config))
        sensitive = len({r["source"] for r in variants}) > 1
        analysis = store.put(
            "analysis",
            {
                "case_id": stored["id"],
                "preset_id": "automatic_v3_envelope",
                "results": [dict(r) for r in variants],
                "assumption_sensitive": sensitive,
            },
            stored["id"],
        )
        result["sensitivity_result_ids"] = [analysis["id"]]
        if sensitive:
            result.update(status="unknown", source="Unknown")
            result["reason_codes"].append("ASSUMPTION_SENSITIVE")
    report = store.put(
        "estimate",
        {**result, "case_id": stored["id"], "model_config": config.model_dump()},
        stored["id"],
    )
    return {"case": stored, "estimate": report}


def analyze(store, case_id, preset_id):
    case = CaseInput.model_validate(
        {k: v for k, v in store.get(case_id, "case").items() if k not in {"id", "created_at"}}
    )
    parent = store.latest_evidence(case_id)
    result = sensitivity(
        case,
        profile_for(store, case.calibration_id),
        ModelConfig.model_validate(parent["model_config"]),
        preset_id,
    )
    return store.put(
        "analysis", {**result, "case_id": case_id, "parent_estimate": parent["id"]}, case_id
    )


class LocalBackend:
    def __init__(
        self, store, case_id, operator="local-operator", conversation="dashboard", role="operator"
    ):
        self.store, self.case_id = store, case_id
        self.operator, self.conversation, self.role = operator, conversation, role
        self.evidence_id = store.latest_evidence(case_id)["id"]
        self.returned = set()
        self.proposals = set()

    async def call(self, name, arguments):
        if self.store.latest_evidence(self.case_id)["id"] != self.evidence_id:
            raise ValueError("Evidence changed during investigation")
        if name == "get_case":
            case = self.store.get(self.case_id, "case")
            return {
                "case_id": self.case_id,
                "mode": case["mode"],
                "evidence_mode": case["evidence_mode"],
                "calibration_id": case["calibration_id"],
                "evidence_ids": [],
            }
        if name == "get_source_evidence":
            result = self.store.latest_evidence(self.case_id)
            self.returned.add(result["id"])
            return {**result, "evidence_ids": [result["id"]]}
        if name == "run_predeclared_sensitivity":
            result = await asyncio.to_thread(
                analyze, self.store, self.case_id, arguments["preset_id"]
            )
            self.returned.add(result["id"])
            return {**result, "evidence_ids": [result["id"]]}
        if name == "observe_again":
            result = self.store.put(
                "observation_request",
                {
                    "case_id": self.case_id,
                    "duration_s": 3,
                    "state": "pending",
                    "reason": "Capture worker must supply actual new evidence",
                },
                self.case_id,
            )
            return {"request_id": result["id"], "state": "pending", "evidence_ids": []}
        if name == "propose_collection":
            if (
                self.role != "operator"
                or arguments["evidence_id"] not in self.returned
                or arguments["evidence_id"] != self.evidence_id
            ):
                raise ValueError("Operator and current returned source evidence required")
            proposal = self.store.propose(
                self.case_id, self.evidence_id, self.operator, self.conversation
            )
            self.proposals.add(proposal["id"])
            return {**proposal, "evidence_ids": [self.evidence_id]}
        raise ValueError("Unsupported tool")
