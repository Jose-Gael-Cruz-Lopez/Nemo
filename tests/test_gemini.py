"""Offline gateway contract and untrusted model-output boundaries."""

import asyncio
import json

import httpx
import pytest

from adapters.gemini.agent import GeminiSettings, investigate

SETTINGS = GeminiSettings(True, "https://generativelanguage.googleapis.com/v1beta/openai", "secret", "model-1")


class Backend:
    def __init__(self):
        self.calls = []

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "propose_collection":
            return {"ok": True, "evidence_ids": ["evidence-1"], "proposal_id": "proposal-1"}
        return {"ok": True, "evidence_ids": ["evidence-1"], "case_id": "case-1"}


def command(tool, **arguments):
    return {"tool": tool, "arguments": arguments}


def run_turn(commands, backend=None):
    requests = []
    backend = backend or Backend()

    def serve(request):
        requests.append(request)
        content = commands.pop(0)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": content if isinstance(content, str) else json.dumps(content)
                        }
                    }
                ]
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
            answer = await investigate(
                "Why was this source selected?",
                backend,
                {"case_id": "case-1"},
                SETTINGS,
                client=client,
            )
            assert not client.is_closed
            return answer

    return asyncio.run(run()), requests, backend


def test_gateway_contract_reads_evidence_before_grounded_finish():
    answer, requests, backend = run_turn(
        [
            command("get_case"),
            command("get_source_evidence"),
            command(
                "finish",
                action="REPORT",
                evidence_ids=["evidence-1"],
                explanation="The retained endpoint does not establish source identity.",
            ),
        ]
    )
    assert answer["action"] == "REPORT"
    assert answer["live_model_response"] is True
    assert [c[0] for c in backend.calls] == ["get_case", "get_source_evidence"]
    assert requests[0].url == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    assert requests[0].headers["Authorization"] == "Bearer secret"
    assert json.loads(requests[0].content)["model"] == "model-1"
    output_format = json.loads(requests[0].content)["response_format"]
    assert output_format["type"] == "json_schema"
    assert output_format["json_schema"]["schema"]["required"] == ["tool", "arguments"]
    assert set(json.loads(requests[0].content)) == {"model", "messages", "response_format", "max_tokens"}


@pytest.mark.parametrize(
    "bad_command",
    [
        command("finish", action="REPORT", evidence_ids=["invented"], explanation="Certain."),
        command(
            "finish",
            action="REQUEST_APPROVAL",
            evidence_ids=["evidence-1"],
            proposal_id="invented",
            explanation="Ready.",
        ),
        command("pump_on"),
        {"tool": "get_case", "arguments": {}, "ignore_rules": True},
        "not json",
        '{"tool":"finish","arguments":{"action":"REPORT"',
        '```json\n{"tool":"finish","arguments":{}}\n```',
    ],
)
def test_unreturned_ids_and_unregistered_tools_fail_closed(bad_command):
    answer, _, _ = run_turn([command("get_case"), command("get_source_evidence"), bad_command])
    assert answer["action"] == "STOP"
    assert "proposal_id" not in answer


def test_approval_requires_actual_successful_proposal_tool():
    answer, _, backend = run_turn(
        [
            command("get_case"),
            command("get_source_evidence"),
            command("propose_collection", evidence_id="evidence-1"),
            command(
                "finish",
                action="REQUEST_APPROVAL",
                evidence_ids=["evidence-1"],
                proposal_id="proposal-1",
                explanation="A manual net task needs operator approval.",
            ),
        ]
    )
    assert answer["proposal_id"] == "proposal-1"
    assert backend.calls[-1][0] == "propose_collection"


def test_proposal_before_source_read_never_calls_backend():
    answer, _, backend = run_turn([command("propose_collection", evidence_id="guessed")])
    assert answer["action"] == "STOP"
    assert backend.calls == []


def test_budget_prevents_repeated_observation_or_sensitivity():
    answer, _, backend = run_turn([command("observe_again"), command("observe_again")])
    assert answer["action"] == "STOP"
    assert len(backend.calls) == 1


def test_failed_case_read_is_not_successful_grounding():
    class FailedBackend(Backend):
        async def call(self, name, arguments):
            return {"ok": False, "evidence_ids": ["evidence-1"]}

    answer, _, _ = run_turn(
        [
            command("get_case"),
            command("get_source_evidence"),
            command(
                "finish", action="REPORT", evidence_ids=["evidence-1"], explanation="Unsupported."
            ),
        ],
        FailedBackend(),
    )
    assert answer["action"] == "STOP"


@pytest.mark.parametrize(
    "explanation",
    ["Source A has 99% support.", "Review evidence-123.", "Source B has ９９% support."],
)
def test_numerical_prose_is_rejected_even_with_valid_returned_evidence(explanation):
    answer, _, _ = run_turn(
        [
            command("get_case"),
            command("get_source_evidence"),
            command(
                "finish", action="REPORT", evidence_ids=["evidence-1"], explanation=explanation
            ),
        ]
    )
    assert answer["action"] == "STOP"
    assert answer["live_model_response"] is False


def test_model_cannot_replace_unknown_source_table_with_its_own_scores():
    class UnknownBackend(Backend):
        async def call(self, name, arguments):
            return {
                "ok": True,
                "evidence_ids": ["evidence-1"],
                "report": {
                    "status": "unknown",
                    "ranked_source": None,
                    "relative_support": {"A": 0.51, "B": 0.49},
                },
            }

    answer, _, _ = run_turn(
        [
            command("get_case"),
            command("get_source_evidence"),
            command(
                "finish",
                action="REPORT",
                evidence_ids=["evidence-1"],
                explanation="Source A is the winner.",
                relative_support={"A": 1.0, "B": 0.0},
            ),
        ],
        UnknownBackend(),
    )
    assert answer["action"] == "STOP"
    assert "relative_support" not in answer
    # The trace still contains the original deterministic report for audit.
    assert answer["trace"][-1]["result"]["report"]["status"] == "unknown"


@pytest.mark.parametrize("status,action", [("unknown", "REPORT"), ("invalid", "UNKNOWN"),
                                            ("invalid", "REPORT")])
def test_model_cannot_upgrade_deterministic_unknown_or_invalid_source_status(status, action):
    class FrozenStatusBackend(Backend):
        async def call(self, name, arguments):
            return {"ok": True, "evidence_ids": ["evidence-1"], "report": {"status": status}}

    answer, _, _ = run_turn([
        command("get_case"), command("get_source_evidence"),
        command("finish", action=action, evidence_ids=["evidence-1"],
                explanation="The strongest source is established."),
    ], FrozenStatusBackend())
    assert answer["action"] == "STOP"
    assert answer["live_model_response"] is False


def test_disabled_agent_never_connects_and_secret_not_in_repr():
    async def run():
        def never(_):
            raise AssertionError("No network permitted")

        async with httpx.AsyncClient(transport=httpx.MockTransport(never)) as client:
            return await investigate("test", Backend(), {}, GeminiSettings(), client=client)

    assert asyncio.run(run())["action"] == "STOP"
    assert "secret" not in repr(SETTINGS)


def test_gateway_http_failure_exposes_only_safe_status_diagnostics():
    async def run():
        def reject(_):
            return httpx.Response(401, text="provider diagnostic contains secret-not-for-browser",
                                  headers={"x-debug-secret": "secret-not-for-browser"})
        async with httpx.AsyncClient(transport=httpx.MockTransport(reject)) as client:
            return await investigate("test", Backend(), {}, SETTINGS, client=client)

    answer = asyncio.run(run())
    assert answer["action"] == "STOP"
    assert answer["live_model_response"] is False
    assert answer["failure_code"] == "PROVIDER_HTTP_ERROR"
    assert answer["provider_status_code"] == 401
    assert "secret-not-for-browser" not in json.dumps(answer)


def test_overall_turn_timeout_returns_safe_stop():
    class SlowBackend(Backend):
        async def call(self, name, arguments):
            await asyncio.sleep(1)

    async def run():
        def serve(_):
            return httpx.Response(
                200, json={"choices": [{"message": {"content": json.dumps(command("get_case"))}}]}
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
            settings = GeminiSettings(True, SETTINGS.base_url, "secret", "model", 0.01, 0.01)
            return await investigate("test", SlowBackend(), {}, settings, client=client)

    answer = asyncio.run(run())
    assert answer["action"] == "STOP"
    assert answer["failure_code"] == "TIMEOUT"
    assert answer["timeout_stage"] == "tool:get_case"
    assert answer["timeout_scope"] == "turn"
    assert answer["tools_completed"] == 0


@pytest.mark.parametrize("turn_limit,request_limit,scope", [
    (0.5, 0.01, "request"), (0.02, 0.5, "turn"),
])
def test_model_request_wall_time_is_bounded_by_request_and_remaining_turn(turn_limit, request_limit, scope):
    """A transport ignoring HTTPX phase timeout still cannot outlive either budget."""
    backend = Backend()
    budgets = []

    async def serve(request):
        budgets.append(request.extensions["timeout"]["read"])
        await asyncio.sleep(2)
        raise AssertionError("Request should have been cancelled by its wall-time budget")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
            settings = GeminiSettings(True, SETTINGS.base_url, "secret", "model",
                                     turn_limit, request_limit)
            started = asyncio.get_running_loop().time()
            answer = await investigate("test", backend, {}, settings, client=client)
            return answer, asyncio.get_running_loop().time() - started

    answer, elapsed = asyncio.run(run())
    assert answer["action"] == "STOP" and answer["live_model_response"] is False
    assert answer["failure_code"] == "TIMEOUT"
    assert answer["timeout_stage"] == "model_call_1"
    assert answer["timeout_scope"] == scope
    assert answer["model_calls_attempted"] == 1
    assert answer["tools_completed"] == 0 and backend.calls == []
    assert len(budgets) == 1 and 0 < budgets[0] <= min(turn_limit, request_limit)
    assert elapsed < 0.3
    assert "secret" not in json.dumps(answer)


def test_later_model_call_receives_only_remaining_whole_turn_budget():
    budgets = []
    backend = Backend()

    async def serve(request):
        budgets.append(request.extensions["timeout"]["read"])
        if len(budgets) == 1:
            await asyncio.sleep(0.04)
            return httpx.Response(200, json={"choices": [{"message": {
                "content": json.dumps(command("get_case"))}}]})
        await asyncio.sleep(2)
        raise AssertionError("The second request must end at the original turn deadline")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
            settings = GeminiSettings(True, SETTINGS.base_url, "secret", "model", 0.10, 0.08)
            return await investigate("test", backend, {}, settings, client=client)

    answer = asyncio.run(run())
    assert len(budgets) == 2 and 0 < budgets[1] < budgets[0] <= 0.08
    assert answer["failure_code"] == "TIMEOUT" and answer["timeout_scope"] == "turn"
    assert answer["timeout_stage"] == "model_call_2"
    assert answer["model_calls_attempted"] == 2 and answer["tools_completed"] == 1
    assert [row["tool"] for row in answer["trace"]] == ["get_case"]
    assert backend.calls == [("get_case", {})]


def test_offline_evaluation_uses_same_agent_but_never_claims_real_model_results(tmp_path):
    from adapters.gemini.evaluate import main

    output = tmp_path / "offline-evaluation.json"
    assert main(["--output", str(output)]) == 0
    result = json.loads(output.read_text())
    assert result["mode"] == "local-scripted-contract"
    assert result["real_model_evaluation"] is False
    assert result["remote_evaluation"] is False
    assert result["hardware_enabled"] is False
    assert len(result["rows"]) == 4
    assert all(
        value == 1.0
        for name, value in result["aggregate"].items()
        if name != "model_response_valid"
    )
    assert result["aggregate"]["model_response_valid"] == 0.0
    assert result["valid_model_response_rows"] == 0
    assert all(not row["output"]["live_model_response"] for row in result["rows"])


def test_evaluation_labels_cannot_enter_model_fixture():
    from adapters.gemini.evaluate import ReplayBackend, default_rows, validate_rows

    rows = default_rows()
    validate_rows(rows)
    fixture = json.loads(rows[0]["fixture_json"])
    fixture["case"]["true_source"] = "hidden-answer"
    with pytest.raises(ValueError, match="labels/truth"):
        ReplayBackend(fixture)


def test_evaluation_metrics_reject_unknown_upgrade_and_numerical_prose():
    from adapters.gemini.evaluate import policy_scores

    result = {
        "action": "REPORT",
        "explanation": "Source A is 99 percent likely.",
        "evidence_ids": ["e"],
        "trace": [
            {
                "tool": "get_source_evidence",
                "result": {"ok": True, "evidence_ids": ["e"], "report": {"status": "unknown"}},
            }
        ],
    }
    scores = policy_scores(json.dumps(result), '["UNKNOWN"]', "[]", "[]", '["e"]')
    assert scores["evidence_grounded"] == 1.0
    assert scores["source_status_preserved"] == 0.0
    assert scores["numerical_authority"] == 0.0
    assert scores["action_correct"] == 0.0
