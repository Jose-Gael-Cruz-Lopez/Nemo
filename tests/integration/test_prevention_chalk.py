"""Actual prevention runtime/ledger; only the external model transport is mocked."""

import asyncio
import json

import httpx
import pytest

from adapters.chalk.agent import ChalkSettings
from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.services.prevention_investigation import (
    PreventionCaseBackend,
    investigate_prevention,
)
from apps.api.reeftrace_api.services.runtime import Runtime


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTON_ENABLED", "false")
    service = Runtime(Settings(data_dir=tmp_path, local_token="test"))
    monkeypatch.setattr(service, "chalk_settings", lambda: ChalkSettings(
        True, "https://example.test/router", "private", "env", "model"))
    return service


def model_client(*, final_hook=None):
    calls = []

    def serve(request):
        messages = json.loads(request.content)["messages"]
        context = json.loads(messages[1]["content"])["trusted_context"]
        index = len(calls)
        calls.append(request)
        if index < 3:
            command = {"tool": ["get_case", "get_source_evidence", "get_prevention_evidence"][index],
                       "arguments": {}}
        else:
            if final_hook:
                final_hook()
            command = {"tool": "finish", "arguments": {"action": "UNKNOWN", "evidence_ids": [
                context["source_evidence_id"], context["prevention_comparison_id"],
                context["prevention_evaluation_id"]], "explanation":
                "The source remains uncertain. The frozen layout simulation and synthetic trial ledger are separate; no physical prevention is verified."}}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(command)}}]})
    return httpx.AsyncClient(transport=httpx.MockTransport(serve)), calls


def test_review_returns_exact_comparison_and_evaluation_without_actions(runtime):
    async def run():
        detail = await runtime.prevention.load_demo()
        client, requests = model_client()
        async with client:
            result = await investigate_prevention(runtime, detail["comparison"]["id"],
                                                  "Explain the intervention evidence.", client=client)
        assert result["live_model_response"] is True
        assert result["comparison_id"] == detail["comparison"]["id"]
        assert result["evaluation_digest"] == detail["evaluation"]["snapshot_hash"]
        assert result["prevention_evaluation"] == detail["evaluation"]
        assert len(requests) == 4
        assert len(runtime.store.list("prevention_investigation")) == 1
        assert runtime.store.list("action") == []
        assert runtime.photon_settings().enabled is False
        assert [row["tool"] for row in result["trace"]] == [
            "get_case", "get_source_evidence", "get_prevention_evidence"]
        return detail
    detail = asyncio.run(run())
    assert detail["evaluation"]["by_origin"]["OPERATOR_REPORTED_PHYSICAL"]["plan"]["recorded_total"] == 0


@pytest.mark.parametrize("change", ["stop", "recompute", "trial"])
def test_slow_review_cannot_commit_after_evidence_or_trial_change(runtime, change):
    async def run():
        detail = await runtime.prevention.load_demo()
        comparison = detail["comparison"]

        def mutate():
            if change == "stop":
                runtime.store.stop_case(comparison["case_id"])
            elif change == "recompute":
                case = runtime.store.case(comparison["case_id"])
                runtime.store.update_case(case["id"], case["revision"], {"state": "INVESTIGATE"})
            else:
                # An immutable ledger append during a network call changes the
                # exact evaluation snapshot, even without a case revision.
                trial = dict(detail["trials"][0])
                trial.pop("id")
                trial["trial_key"] = "concurrent-ledger-test"
                runtime.store.put("prevention_trial", trial)
        client, _ = model_client(final_hook=mutate)
        async with client:
            with pytest.raises(ValueError, match="changed|stopped|ledger|evaluation"):
                await investigate_prevention(runtime, comparison["id"], "Explain.", client=client)
        assert runtime.store.list("prevention_investigation") == []
    asyncio.run(run())


def test_backend_is_read_only_and_does_not_leak_raw_trial_notes(runtime):
    async def run():
        detail = await runtime.prevention.load_demo()
        backend = PreventionCaseBackend(runtime, detail)
        result = await backend.call("get_prevention_evidence", {})
        assert "trials" not in result
        assert "nominal_paths" not in result["comparison"]["numerical_report"]
        assert "note" not in json.dumps(result["evaluation"])
        with pytest.raises(ValueError, match="read-only"):
            await backend.call("observe_again", {})
    asyncio.run(run())
