"""Offline gateway contract and untrusted model-output boundaries."""

import asyncio
import importlib
import inspect
import json
import sys

import httpx
import pytest

from adapters.chalk.agent import ChalkSettings, investigate

SETTINGS = ChalkSettings(True, "https://chalk.example/v1/router", "secret", "env-1", "model-1")


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
    assert requests[0].url == "https://chalk.example/v1/router/chat/completions"
    assert requests[0].headers["Authorization"] == "Bearer secret"
    assert requests[0].headers["X-Chalk-Env-Id"] == "env-1"
    assert json.loads(requests[0].content)["model"] == "model-1"


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
            return await investigate("test", Backend(), {}, ChalkSettings(), client=client)

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
            settings = ChalkSettings(True, SETTINGS.base_url, "secret", "env", "model", 0.01, 0.01)
            return await investigate("test", SlowBackend(), {}, settings, client=client)

    assert asyncio.run(run())["action"] == "STOP"


def test_offline_evaluation_uses_same_agent_but_never_claims_real_model_results(tmp_path):
    from adapters.chalk.evaluate import main

    output = tmp_path / "offline-evaluation.json"
    assert main(["--mode", "local", "--output", str(output)]) == 0
    result = json.loads(output.read_text())
    assert result["mode"] == "local-scripted-contract"
    assert result["real_model_evaluation"] is False
    assert result["remote_chalk_evaluation"] is False
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
    assert "adapters.chalk.evaluation_tasks" not in sys.modules


def test_evaluation_labels_cannot_enter_model_fixture():
    from adapters.chalk.evaluate import ReplayBackend, default_rows, validate_rows

    rows = default_rows()
    validate_rows(rows)
    fixture = json.loads(rows[0]["fixture_json"])
    fixture["case"]["true_source"] = "hidden-answer"
    with pytest.raises(ValueError, match="labels/truth"):
        ReplayBackend(fixture)


def test_evaluation_metrics_reject_unknown_upgrade_and_numerical_prose():
    from adapters.chalk.evaluate import policy_scores

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


def test_current_chalk_sdk_declaration_contract_without_any_deployment(monkeypatch):
    chalk = pytest.importorskip("chalkcompute")
    function_signature = inspect.signature(chalk.function)
    scorer_signature = inspect.signature(chalk.scorers.json_valid)
    declarations = []

    def declare(func=None, **kwargs):
        function_signature.bind(func, **kwargs)
        declarations.append(kwargs)
        return (lambda target: target) if func is None else func

    def scorer(**kwargs):
        scorer_signature.bind(**kwargs)
        return "offline-scorer-declaration"

    # The real decorator would immediately queue a cloud deployment. Replace it
    # before importing task definitions, while using actual Image/Secret objects.
    monkeypatch.setattr(chalk, "function", declare)
    monkeypatch.setattr(chalk.scorers, "json_valid", scorer)
    module_name = "adapters.chalk.evaluation_tasks"
    try:
        module = importlib.import_module(module_name)
        assert isinstance(module.IMAGE, chalk.Image)
        assert len(module.SECRETS) == 3
        assert list(inspect.signature(module.reeftrace_task).parameters) == [
            "fixture_json",
            "request",
        ]
        assert len(declarations) == 7
        assert declarations[0]["call_timeout"] == 90
        assert module.valid_json == "offline-scorer-declaration"
    finally:
        sys.modules.pop(module_name, None)
        # Import machinery also caches the child on its parent package.
        package = importlib.import_module("adapters.chalk")
        if hasattr(package, "evaluation_tasks"):
            delattr(package, "evaluation_tasks")
