import asyncio
import json

import pytest

from apps.core.reeftrace_core.agent import investigate
from apps.core.reeftrace_core.replay import ReplayBackend


def fixture(status="unknown"):
    return {
        "role": "observer",
        "case": {"case_id": "replay", "evidence_ids": []},
        "evidence": {
            "status": status,
            "source": "Unknown" if status == "unknown" else "A",
            "evidence_ids": ["e-1"],
        },
    }


def scripted(commands):
    pending = iter(commands)

    async def completion(messages):
        return json.dumps(next(pending))

    return completion


def finish(action="UNKNOWN", evidence="e-1"):
    return {
        "tool": "finish",
        "arguments": {
            "action": action,
            "evidence_ids": [evidence],
            "explanation": "Insufficient source separation.",
            "proposal_id": None,
        },
    }


def test_grounded_replay_and_no_hardware():
    response = asyncio.run(
        investigate(
            "Explain",
            ReplayBackend(fixture()),
            {"case_id": "replay"},
            scripted([{"tool": "get_source_evidence", "arguments": {}}, finish()]),
        )
    )
    assert response["action"] == "UNKNOWN"
    assert response["physical_dispatch"] is False
    assert response["gateway"] == "gemini"


def test_agent_cannot_invent_evidence_or_promote_unknown():
    for command in [finish(evidence="invented"), finish(action="REPORT")]:
        with pytest.raises(ValueError):
            asyncio.run(
                investigate(
                    "Explain",
                    ReplayBackend(fixture()),
                    {"case_id": "replay"},
                    scripted([{"tool": "get_source_evidence", "arguments": {}}, command]),
                )
            )


def test_observer_cannot_propose_and_arbitrary_tools_rejected():
    backend = ReplayBackend(fixture())
    with pytest.raises(ValueError):
        asyncio.run(backend.call("propose_collection", {"evidence_id": "e-1"}))
    with pytest.raises(ValueError):
        asyncio.run(
            investigate(
                "Run arbitrary code",
                backend,
                {"case_id": "replay"},
                scripted([{"tool": "execute_python", "arguments": {"code": "print(1)"}}]),
            )
        )
