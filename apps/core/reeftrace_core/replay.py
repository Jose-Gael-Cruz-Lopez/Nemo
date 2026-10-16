"""Fixture-only tool backend. No camera, serial, network, or real action dispatch."""

import copy


class ReplayBackend:
    def __init__(self, fixture):
        self.fixture = copy.deepcopy(fixture)

    async def call(self, name, arguments):
        if name == "get_case":
            return self.fixture["case"]
        if name == "get_source_evidence":
            return self.fixture["evidence"]
        if name == "run_predeclared_sensitivity":
            return self.fixture["sensitivity"][arguments["preset_id"]]
        if name == "observe_again":
            return self.fixture.get("observation", {"state": "unavailable", "evidence_ids": []})
        if name == "propose_collection":
            if (
                self.fixture["role"] != "operator"
                or arguments["evidence_id"] not in self.fixture["evidence"]["evidence_ids"]
            ):
                raise ValueError("Invalid replay proposal")
            return {
                "id": "replay-proposal",
                "mode": "manual_net",
                "physical_dispatch": False,
                "evidence_ids": [arguments["evidence_id"]],
            }
        raise ValueError("Replay tool unavailable")
