"""Prevention review is evidence-bound and cannot mutate the physical workflow."""

import asyncio
import json

import httpx
import pytest

from adapters.chalk.agent import ChalkSettings, investigate

CONTEXT = {"case_id": "case-a", "source_evidence_id": "estimate-a",
           "prevention_comparison_id": "comparison-a",
           "prevention_evaluation_id": "evaluation-a"}
SETTINGS = ChalkSettings(True, "https://example.test/router", "private", "env", "model")


class PreventionBackend:
    def __init__(self, status="ranked"):
        self.calls = []
        self.status = status

    async def call(self, name, args):
        self.calls.append(name)
        return {"ok": True, "report": {"status": self.status}, "evidence_ids":
                ["comparison-a", "evaluation-a"] if name == "get_prevention_evidence"
                else ["estimate-a"]}


def run(commands, *, status="ranked", context=None):
    backend = PreventionBackend(status)

    def serve(request):
        tool, args = commands.pop(0)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(
            {"tool": tool, "arguments": args})}}]})

    async def turn():
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
            return await investigate("Compare the frozen layouts.", backend,
                                     CONTEXT if context is None else context,
                                     SETTINGS, client=client)
    return asyncio.run(turn()), backend.calls


def finish(action="REPORT", ids=None):
    return ("finish", {"action": action, "evidence_ids": ids or
            ["estimate-a", "comparison-a", "evaluation-a"],
            "explanation": "Simulated predictions and demonstration trials are separate; physical validation remains pending."})


def test_prevention_reads_and_cites_all_frozen_evidence():
    answer, calls = run([("get_case", {}), ("get_source_evidence", {}),
                         ("get_prevention_evidence", {}), finish()])
    assert answer["action"] == "REPORT"
    assert answer["live_model_response"] is True
    assert calls == ["get_case", "get_source_evidence", "get_prevention_evidence"]


@pytest.mark.parametrize("tail", [
    [finish(ids=["estimate-a"])],
    [("get_prevention_evidence", {}), finish(ids=["estimate-a", "comparison-a"])],
    [("observe_again", {})],
    [("run_predeclared_sensitivity", {"preset_id": "preset"})],
    [("propose_collection", {"evidence_id": "estimate-a"})],
])
def test_prevention_missing_grounding_and_mutations_fail_closed(tail):
    answer, calls = run([("get_case", {}), ("get_source_evidence", {}), *tail])
    assert answer["action"] == "STOP"
    assert answer["live_model_response"] is False
    assert not set(calls) & {"observe_again", "run_predeclared_sensitivity", "propose_collection"}


def test_prevention_cannot_upgrade_unknown_source():
    prefix = [("get_case", {}), ("get_source_evidence", {}), ("get_prevention_evidence", {})]
    rejected, _ = run([*prefix, finish()], status="unknown")
    accepted, _ = run([*prefix, finish("UNKNOWN")], status="unknown")
    assert rejected["live_model_response"] is False
    assert accepted["action"] == "UNKNOWN" and accepted["live_model_response"] is True


def test_ordinary_case_cannot_read_arbitrary_prevention_evidence():
    answer, calls = run([("get_prevention_evidence", {})], context={"case_id": "case-a"})
    assert answer["action"] == "STOP" and calls == []
