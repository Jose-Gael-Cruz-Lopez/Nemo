"""Mocked gateway tests; no credentials, provider requests or scientific scores."""

import asyncio
import json

import httpx
import pytest

from adapters.chalk.agent import ChalkSettings
from adapters.chalk.research import investigate_study

SETTINGS = ChalkSettings(True, "https://chalk.test/v1/router", "test-only-key", "test-env", "test-model")
CONTEXT = {"study_evidence_id": "fresh-study:" + "a" * 64,
           "protocol_evidence_id": "fresh-protocol:" + "b" * 64}
IDS = list(CONTEXT.values())


class Backend:
    def __init__(self, *, result=None, delay=0):
        self.calls = []
        self.result = result or {"ok": True, "evidence_ids": IDS,
                                 "study": {"status": "PARTIAL_COVERAGE"}}
        self.delay = delay

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        if self.delay:
            await asyncio.sleep(self.delay)
        assert name == "get_study_evidence" and arguments == {}
        return self.result


def command(tool, **arguments):
    return {"tool": tool, "arguments": arguments}


def finish(**updates):
    return command("finish", **{"action": "REPORT", "evidence_ids": IDS,
        "explanation": "The available buoy results remain conditional on the frozen design.", **updates})


def run(commands, *, backend=None, settings=SETTINGS, question="What do these results support?",
        context=CONTEXT, status=200, response_body=None, delay=0):
    requests, active = [], backend or Backend()
    async def handler(request):
        requests.append(request)
        if delay:
            await asyncio.sleep(delay)
        if response_body is not None:
            return httpx.Response(status, content=response_body, request=request)
        reply = commands[len(requests) - 1]
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return httpx.Response(status, json={"choices": [{"message": {"content": text}}]}, request=request)
    async def execute():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await investigate_study(question, active, context, settings, client=client)
            assert not client.is_closed, "Injected clients belong to their caller"
            return result
    return asyncio.run(execute()), requests, active


def test_success_reads_exact_snapshot_and_cites_both_hash_bound_ids():
    result, requests, backend = run([command("get_study_evidence"), finish()])
    assert result["action"] == "REPORT" and result["live_model_response"] is True
    assert result["evidence_ids"] == IDS
    assert backend.calls == [("get_study_evidence", {})]
    assert len(requests) == 2 and len(result["trace"]) == 1
    assert result["trace"][0]["read_origin"] == "model_requested"
    assert str(requests[0].url) == "https://chalk.test/v1/router/chat/completions"
    assert requests[0].headers["Authorization"] == "Bearer test-only-key"
    assert requests[0].headers["X-Chalk-Env-Id"] == "test-env"
    payload = json.loads(requests[1].content)
    assert payload["model"] == "test-model" and payload["max_completion_tokens"] == 1024
    assert json.loads(payload["messages"][-1]["content"])["tool_result"]["data"]["evidence_ids"] == IDS


@pytest.mark.parametrize("bad", [
    command("get_case"), command("get_source_evidence"), command("observe_again"),
    command("propose_collection", evidence_id="case-evidence"),
    command("get_study_evidence", url="https://elsewhere.test"),
    {"tool": "get_study_evidence", "arguments": {}, "execute": True},
    '```json\n{"tool":"get_study_evidence","arguments":{}}\n```',
    '{"tool":"finish","arguments":',
])
def test_mutating_unregistered_or_model_selected_tools_are_never_dispatched(bad):
    result, requests, backend = run([bad])
    assert result["action"] == "STOP" and result["failure_code"] == "MODEL_OR_TOOL_CONTRACT_ERROR"
    assert len(requests) == 1 and backend.calls == []


@pytest.mark.parametrize("bad_finish", [
    finish(evidence_ids=IDS[:1]), finish(evidence_ids=[*IDS, IDS[0]]),
    finish(evidence_ids=[IDS[0], "fresh-protocol:" + "c" * 64]),
    finish(action="REQUEST_APPROVAL"), finish(proposal_id="not-allowed"),
    finish(explanation="The model reduced error by 90 percent."),
    finish(explanation="The model reduced error by ９０ percent."),
])
def test_missing_or_forged_citations_and_generated_numbers_fail_closed(bad_finish):
    result, requests, backend = run([command("get_study_evidence"), bad_finish])
    assert result["action"] == "STOP" and result["live_model_response"] is False
    assert result["failure_code"] == "MODEL_OR_TOOL_CONTRACT_ERROR"
    assert len(requests) == 2 and len(backend.calls) == 1


def test_live_overlong_but_otherwise_valid_report_is_not_truncated_or_accepted():
    # Public-study prose from the bounded live failure: valid JSON, citations and
    # no digits, but the previously unstated explanation length rule was missed.
    explanation = (
        "This completed public NOAA drifter study compares fixed buoy-motion forecasts on previously "
        "unscored GDP-ID groups. Every planned outcome in the completed study was scored, with no "
        "missing or failed outcomes. Last-observed-drift had the lowest aggregate trajectory and "
        "velocity errors; the ridge and Kalman models performed better on some individual groups, "
        "so the comparison does not establish a universally best model. The design was frozen before "
        "trajectory acquisition, but that is not proof of independent validation: different IDs do "
        "not establish physical or statistical independence, and alias resolution remains unverified. "
        "An earlier acquisition was blocked by metadata transport timeouts and a parser rejection; "
        "its corrections preceded scoring, and it produced no model outcomes. IDs had appeared in "
        "selection metadata and an identity registry, neither of which was a scored trajectory "
        "evaluation. Physical validation still requires testing the motion assumptions and "
        "applicability beyond these historical buoys; NOAA positions are quality-controlled and "
        "interpolated, so raw-fix causality is unestablished. The results do not validate plastic "
        "tracking or interception benefit, calibrated probabilities, operational causality, or "
        "automatic model promotion.")
    assert len(explanation) == 1268 and not any(c.isdigit() for c in explanation)
    result, requests, backend = run([command("get_study_evidence"), finish(explanation=explanation)])
    assert result["action"] == "STOP" and result["live_model_response"] is False
    assert result["failure_code"] == "MODEL_OR_TOOL_CONTRACT_ERROR"
    assert result["explanation"] != explanation[:1200]
    assert len(requests) == 2 and len(backend.calls) == 1
    system = json.loads(requests[0].content)["messages"][0]["content"]
    assert "eight hundred characters" in system and "four short sentences" in system


def test_concise_model_comparison_with_limits_and_next_measurement_is_accepted():
    explanation = (
        "Last drift had the lowest aggregate miss, while more complex models did better on some "
        "groups; this does not select a universal winner. The earlier acquisition failures produced "
        "no model outcomes before the amendment. Retrospective interpolation and unresolved aliases "
        "limit causal and independence claims. Separate recorded token trials and drift validation "
        "are still needed; these historical buoys do not establish plastic sources, interception "
        "benefit or calibrated probabilities.")
    assert len(explanation) < 800 and not any(c.isdigit() for c in explanation)
    result, requests, backend = run([command("get_study_evidence"), finish(explanation=explanation)])
    assert result["action"] == "REPORT" and result["live_model_response"] is True
    assert result["explanation"] == explanation and result["evidence_ids"] == IDS
    assert len(requests) == 2 and len(backend.calls) == 1


@pytest.mark.parametrize("early", [finish(), finish(action="STOP", evidence_ids=[],
    explanation="The study evidence tool is unavailable.")])
def test_premature_finish_gets_one_authorized_read_before_final_grounded_turn(early):
    result, requests, backend = run([early, finish()])
    assert result["action"] == "REPORT" and result["live_model_response"] is True
    assert result["explanation"] == finish()["arguments"]["explanation"]
    assert result["evidence_ids"] == IDS
    assert backend.calls == [("get_study_evidence", {})]
    assert len(requests) == 2 and len(result["trace"]) == 1
    assert result["trace"][0]["read_origin"] == "server_required_after_premature_finish"
    final_messages = json.loads(requests[1].content)["messages"]
    supplied = json.loads(final_messages[-1]["content"])
    assert supplied["tool_result"]["data"] == backend.result
    assert "previous finish was not accepted" in supplied["orchestration_notice"]
    assert "first command" in final_messages[0]["content"]


def test_grounded_stop_stays_stop_with_read_trace_and_does_not_become_report():
    final_stop = finish(action="STOP", evidence_ids=[],
                        explanation="This request is outside the study scope.")
    result, requests, backend = run([command("get_study_evidence"), final_stop])
    assert result["action"] == "STOP" and result["live_model_response"] is True
    assert result["evidence_ids"] == [] and result["explanation"] == final_stop["arguments"]["explanation"]
    assert len(requests) == 2 and backend.calls == [("get_study_evidence", {})]
    assert len(result["trace"]) == 1


def test_premature_stop_cannot_finish_if_the_required_read_fails():
    active = Backend(result={"ok": False, "evidence_ids": []})
    early = finish(action="STOP", evidence_ids=[], explanation="The study evidence tool is unavailable.")
    result, requests, backend = run([early], backend=active)
    assert result["action"] == "STOP" and result["live_model_response"] is False
    assert result["failure_code"] == "MODEL_OR_TOOL_CONTRACT_ERROR"
    assert result["explanation"] != early["arguments"]["explanation"]
    assert len(requests) == 1 and len(backend.calls) == 1 and result["trace"] == []


def test_premature_stop_recovery_does_not_allow_an_extra_read_or_model_retry():
    early = finish(action="STOP", evidence_ids=[], explanation="The study evidence tool is unavailable.")
    result, requests, backend = run([early, command("get_study_evidence")])
    assert result["action"] == "STOP" and result["live_model_response"] is False
    assert result["failure_code"] == "MODEL_OR_TOOL_CONTRACT_ERROR"
    assert len(requests) == 2 and backend.calls == [("get_study_evidence", {})]
    assert len(result["trace"]) == 1


def test_repeated_read_is_bounded_and_unrelated_backend_evidence_is_rejected():
    result, requests, backend = run([command("get_study_evidence"), command("get_study_evidence")])
    assert result["action"] == "STOP" and len(requests) == 2 and len(backend.calls) == 1
    active = Backend(result={"ok": True, "evidence_ids": ["wrong", "other"]})
    result, requests, _ = run([command("get_study_evidence")], backend=active)
    assert result["failure_code"] == "MODEL_OR_TOOL_CONTRACT_ERROR" and len(requests) == 1


@pytest.mark.parametrize("question", ["", "  ", "a" * 2001, None])
def test_invalid_questions_make_no_gateway_or_tool_calls(question):
    result, requests, backend = run([], question=question)
    assert result["failure_code"] == "INVALID_REQUEST" and not requests and not backend.calls


def test_unconfigured_or_invalid_context_never_calls_gateway():
    result, requests, _ = run([], settings=ChalkSettings())
    assert result["failure_code"] == "NOT_CONFIGURED" and not requests
    result, requests, _ = run([], context={"study_evidence_id": []})
    assert result["failure_code"] == "INVALID_CONTEXT" and not requests


def test_provider_failure_is_sanitized_and_does_not_leak_response_body():
    result, _, _ = run([], status=401, response_body=b"private-provider-body test-only-key")
    assert result["failure_code"] == "PROVIDER_HTTP_ERROR" and result["provider_status_code"] == 401
    assert "private-provider-body" not in json.dumps(result) and "test-only-key" not in json.dumps(result)


def test_gateway_and_tool_wall_clock_timeouts_are_bounded():
    settings = ChalkSettings(True, SETTINGS.base_url, "test", "env", "model", .03, .02)
    result, _, backend = run([command("get_study_evidence")], settings=settings, delay=.08)
    assert result["failure_code"] == "TIMEOUT" and result["timeout_stage"] == "model_call"
    assert backend.calls == []
    result, _, backend = run([command("get_study_evidence")], settings=settings, backend=Backend(delay=.08))
    assert result["failure_code"] == "TIMEOUT" and result["timeout_stage"] == "tool:get_study_evidence"
    assert len(backend.calls) == 1


def test_provider_and_evidence_byte_budgets_do_not_send_a_second_model_call():
    result, requests, _ = run([], response_body=b"x" * 64001)
    assert result["failure_code"] == "MODEL_OR_TOOL_CONTRACT_ERROR" and len(requests) == 1
    active = Backend(result={"ok": True, "evidence_ids": IDS, "study": {"large": "x" * 40000}})
    result, requests, _ = run([command("get_study_evidence")], backend=active)
    assert result["failure_code"] == "MODEL_OR_TOOL_CONTRACT_ERROR" and len(requests) == 1
