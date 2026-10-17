"""Read-only Chalk review of a frozen comparison and exact trial snapshot."""

from __future__ import annotations

import asyncio
import copy

from adapters.chalk.agent import investigate

from .investigation import CaseBackend, conditional_report


class PreventionCaseBackend(CaseBackend):
    def __init__(self, runtime, detail):
        self.detail = copy.deepcopy(detail)
        self.comparison = self.detail["comparison"]
        super().__init__(runtime, self.comparison["case_id"], operator=False)

    async def call(self, name, arguments):
        self.service.prevention.assert_active(self.comparison)
        current = self.service.prevention.comparison_detail(self.comparison["id"],
                                                           require_active=True)
        if current["evaluation"]["snapshot_hash"] != self.detail["evaluation"]["snapshot_hash"]:
            raise ValueError("Trial ledger changed; start a review of the new evaluation")
        if name == "get_prevention_evidence" and not arguments:
            # Raw release labels stay in their evaluation ledger. Only the
            # deterministic aggregate snapshot is supplied to the model.
            comparison = copy.deepcopy(self.comparison)
            comparison["numerical_report"].pop("nominal_paths", None)
            return {"ok": True, "comparison": comparison,
                    "evaluation": copy.deepcopy(self.detail["evaluation"]),
                    "evidence_ids": [self.comparison["id"], self.detail["evaluation"]["id"]],
                    "interpretation": "Simulated layout predictions are separate from trial outcomes. Trial source labels are evaluation truth, never source inference. No reef benefit is established."}
        if name in {"get_case", "get_source_evidence"} and not arguments:
            result = await super().call(name, arguments)
            if name == "get_case":
                result["permitted_sensitivity_presets"] = []
                result["review_scope"] = "read_only_prevention_comparison"
            return result
        raise ValueError("Prevention investigations permit read-only frozen evidence tools only")


async def investigate_prevention(runtime, comparison_id, text, *, client=None):
    service = runtime.prevention
    initial = service.comparison_detail(comparison_id, require_active=True)
    case_id = initial["comparison"]["case_id"]
    lock = runtime.case_locks.setdefault(case_id, asyncio.Lock())
    async with lock:
        detail = service.comparison_detail(comparison_id, require_active=True)
        comparison, evaluation = detail["comparison"], detail["evaluation"]
        backend = PreventionCaseBackend(runtime, detail)
        source = runtime.store.get("estimate", comparison["source_evidence_id"])
        result = await investigate(text, backend,
            {"case_id": case_id, "role": "operator",
             "case_revision": comparison["case_revision"],
             "source_evidence_id": comparison["source_evidence_id"],
             "prevention_comparison_id": comparison_id,
             "prevention_evaluation_id": evaluation["id"],
             "evaluation_digest": evaluation["snapshot_hash"]},
            runtime.chalk_settings(), client=client)
        result.update(case_id=case_id, comparison_id=comparison_id,
                      evaluation_digest=evaluation["snapshot_hash"],
                      source_report=conditional_report(source),
                      prevention_report=copy.deepcopy(comparison),
                      prevention_evaluation=copy.deepcopy(evaluation))
        # This transaction checks both case freshness and ledger freshness after
        # the network turn, including a concurrent manual trial or STOP.
        receipt = service.commit_for_comparison("prevention_investigation", result, comparison,
            expected_evaluation_hash=evaluation["snapshot_hash"])
        result["investigation_id"] = receipt["id"]
        return result
