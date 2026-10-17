"""One case-bound tool backend for dashboard, Photon and replay evaluation."""
from __future__ import annotations

import copy


class CaseBackend:
    def __init__(self, service, case_id, *, operator=False):
        self.service = service
        self.case_id = case_id
        self.operator = operator
        self.created_proposal_ids = []
        self.case_revision = service.store.case(case_id)["revision"]

    async def call(self, name, arguments):
        store = self.service.store
        case = store.case(self.case_id)
        if (case["revision"] != self.case_revision
                or case["state"] in {"STOPPED", "RECOVERING"}):
            raise ValueError("Case changed, stopped or recovering; this investigation cannot use more tools")
        evidence_ids = [case["evidence_id"]] if case.get("evidence_id") else []
        if name == "get_case":
            return {"case_id": case["id"], "revision": case["revision"],
                    "mode": case["mode"], "state": case["state"],
                    "profile_id": case["profile_id"], "calibration_id": case["calibration_id"],
                    "observation_count": len(case["points"]), "evidence_ids": evidence_ids,
                    "permitted_sensitivity_presets": ["predeclared-transport-envelope-v1"]}
        if name == "get_source_evidence":
            if not evidence_ids:
                return {"ok": False, "reason": "Estimate has not been computed", "evidence_ids": []}
            return {"ok": True, "report": store.get("estimate", evidence_ids[0]),
                    "evidence_ids": evidence_ids}
        if name == "run_predeclared_sensitivity":
            if arguments.get("preset_id") != "predeclared-transport-envelope-v1":
                raise ValueError("Unregistered sensitivity preset")
            report = await self.service._sensitivity(self.case_id, self.case_revision)
            return {"ok": True, "analysis": report,
                    "evidence_ids": [report["id"], *evidence_ids]}
        if name == "observe_again":
            if case["mode"] != "LIVE" or case["state"] in {"STOPPED", "RECOVERING"}:
                return {"ok": False, "reason": "No live recording is permitted in this case/mode",
                        "evidence_ids": evidence_ids}
            profile = store.get("profile", case["profile_id"])
            self.service.validate_live(case, profile)
            recording = await self.service.record(case["profile_id"], 5, active_case=case)
            return {"ok": True, "new_recording_id": recording["id"],
                    "observed_points": sum(p.get("observed", False) for p in recording["points"]),
                    "usable_for_source_update": False, "same_object_verified": False,
                    "reason": "A genuine five-second recording was saved. Do not join across the gap; operator association review is needed before creating a new case. The frozen source report is unchanged.",
                    "evidence_ids": [*evidence_ids, recording["id"]]}
        if name == "propose_collection":
            proposal = self.service.propose(self.case_id, arguments.get("evidence_id"),
                                            operator=self.operator)
            self.created_proposal_ids.append(proposal["id"])
            return {"ok": True, "proposal_id": proposal["id"],
                    "kind": "manual_net", "evidence_ids": evidence_ids}
        raise ValueError("Unknown tool")


def conditional_report(evidence):
    """Numerical source table is rendered from authoritative estimator data only."""
    return {k: copy.deepcopy(v) for k, v in evidence.items()
            if k not in {"trace", "credentials"}}
