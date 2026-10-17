"""Actual immutable validation receipts; only the external model HTTP is mocked.

No provider traffic, Photon messages, camera capture or actuator is permitted.
"""

import asyncio
import copy
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from adapters.chalk.agent import ChalkSettings
from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.api.reeftrace_api.schemas.prevention import ComparisonInput, TrialInput
from apps.api.reeftrace_api.schemas.validation_reports import ValidationReportInput
from apps.api.reeftrace_api.services.prevention_investigation import (
    PreventionCaseBackend,
    investigate_prevention,
)
from apps.api.reeftrace_api.services.validation_reports import (
    accept_validation_report,
    template_validation_report,
)

AUTH = {"Authorization": "Bearer validation-chalk-test-only"}
PROTOCOL = "untrusted-protocol-label-never-model-context"
READS = ["get_case", "get_source_evidence", "get_prevention_evidence", "get_validation_evidence"]


@pytest.fixture
def app(tmp_path, monkeypatch):
    for key in ("CHALK_ENABLED", "PHOTON_ENABLED", "GROK_VOICE_ENABLED"):
        monkeypatch.setenv(key, "false")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "[]")
    app = create_app(Settings(data_dir=tmp_path, local_token="validation-chalk-test-only"))
    monkeypatch.setattr(app.state.runtime, "chalk_settings", lambda: ChalkSettings(
        True, "https://provider.invalid/router", "test-key-not-live", "test-env", "test-model"))
    return app


def trial(runtime, comparison_id, key="next-release", *, layout="baseline"):
    return runtime.prevention.add_trial(comparison_id, TrialInput(
        trial_key=key, layout=layout, source_id="A", data_origin="SYNTHETIC_DEMO",
        outcome="zone_entry", entry_time_s=15.0, interception_time_s=None,
        token_accounted=True, physical_confirmed=False, horizon_completed=True,
        note="Hand-authored synthetic test release, not measured physical evidence."))


async def prepare(runtime):
    demo = await runtime.prevention.load_demo()
    original = demo["comparison"]
    # Reuse a genuinely computed synthetic source estimate and frozen profiles,
    # while leaving space in this NEW comparison for concurrent ledger tests.
    keys = ("case_id", "baseline_profile_id", "intervention_profile_id", "protected_zone_cm",
            "horizon_s")
    detail = await runtime.prevention.create_comparison(ComparisonInput(
        **{key: original[key] for key in keys}, name="Validation-scoped software rehearsal",
        particles=20, trials_per_source=2))
    cid = detail["comparison"]["id"]
    trial(runtime, cid, "development-release")
    detail = trial(runtime, cid, "validation-release", layout="intervention")
    manifest = template_validation_report(runtime, cid)
    ids = manifest["validation_trial_ids"]
    manifest.update(protocol_id=PROTOCOL, purpose="DECLARED_VALIDATION_SPLIT",
                    development_trial_ids=ids[:1], validation_trial_ids=ids[1:])
    accepted = accept_validation_report(runtime, cid, ValidationReportInput(report=manifest))
    return detail, accepted


def scripted_client(*, reads=None, omit_citation=False, wrong_citation=False,
                    finish_hook=None, command=None):
    requests = []
    chosen_reads = READS if reads is None else reads

    def serve(request):
        payload = json.loads(request.content)
        assert payload["max_completion_tokens"] == 1024
        messages = payload["messages"]
        context = json.loads(messages[1]["content"])["trusted_context"]
        index = len(requests)
        requests.append(copy.deepcopy(payload))
        if command:
            reply = command(context)
        elif index < len(chosen_reads):
            reply = {"tool": chosen_reads[index], "arguments": {}}
        else:
            if finish_hook:
                finish_hook()
            ids = [context["source_evidence_id"], context["prevention_comparison_id"],
                   context["prevention_evaluation_id"]]
            if not omit_citation:
                ids.append("validation-report-wrong" if wrong_citation else context["validation_report_id"])
            reply = {"tool": "finish", "arguments": {"action": "UNKNOWN", "evidence_ids": ids,
                "explanation": "Source identity remains uncertain. The declared validation split has checked accounting, while its independence and physical reef benefit remain unverified."}}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(reply)}}]})
    return httpx.AsyncClient(transport=httpx.MockTransport(serve)), requests


def record_counts(runtime):
    with runtime.store.connection() as db:
        return {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in ("cases", "actions", "inbox", "outbox")}


def test_actual_template_import_and_scoped_review_reads_four_tools_and_cites_exact_four_ids(app):
    runtime = app.state.runtime
    async def run():
        detail, accepted = await prepare(runtime)
        comparison = detail["comparison"]
        before_case = runtime.store.case(comparison["case_id"])
        before_counts = record_counts(runtime)
        before_ledger = copy.deepcopy(detail)
        client, requests = scripted_client()
        async with client:
            result = await investigate_prevention(runtime, comparison["id"],
                "Explain the selected receipt and the next useful measurement.", client=client,
                validation_report_id=accepted["report"]["id"])
        assert result["live_model_response"] is True  # Mocked model transport, never a live provider.
        assert result["action"] == "UNKNOWN"
        expected_ids = {comparison["source_evidence_id"], comparison["id"],
                        detail["evaluation"]["id"], accepted["report"]["id"]}
        assert len(result["evidence_ids"]) == 4 and set(result["evidence_ids"]) == expected_ids
        assert [entry["tool"] for entry in result["trace"]] == READS
        assert len(requests) == 5
        assert result["validation_report_id"] == accepted["report"]["id"]
        assert result["validation_checks"]["method_rerun"] is False
        assert result["validation_checks"]["physical_validation"] is False
        assert runtime.store.case(comparison["case_id"]) == before_case
        assert record_counts(runtime) == before_counts
        assert runtime.prevention.comparison_detail(comparison["id"]) == before_ledger
        receipts = runtime.store.list("prevention_investigation")
        assert len(receipts) == 1 and receipts[0]["id"] == result["investigation_id"]
        assert receipts[0]["validation_report_id"] == accepted["report"]["id"]
        assert receipts[0]["evaluation_digest"] == detail["evaluation"]["snapshot_hash"]
        model_input = json.dumps(requests)
        for private in (PROTOCOL, "development_trial_ids", "validation_trial_ids", "protocol_id"):
            assert private not in model_input
        validation_tool = result["trace"][-1]["result"]
        assert set(validation_tool) == {"ok", "checks", "summary", "verification", "evidence_ids"}
        for trial_id in accepted["report"]["development_trial_ids"] + accepted["report"]["validation_trial_ids"]:
            assert trial_id not in json.dumps(validation_tool)
            assert trial_id not in model_input
        assert runtime.photon_settings().enabled is False
        assert runtime.camera.status()["running"] is False
    asyncio.run(run())


@pytest.mark.parametrize("failure", ["missing_tool", "missing_citation", "wrong_citation"])
def test_validation_read_and_its_exact_citation_are_mandatory(app, failure):
    runtime = app.state.runtime
    async def run():
        detail, accepted = await prepare(runtime)
        client, _ = scripted_client(reads=READS[:-1] if failure == "missing_tool" else READS,
            omit_citation=failure == "missing_citation", wrong_citation=failure == "wrong_citation")
        async with client:
            result = await investigate_prevention(runtime, detail["comparison"]["id"], "Explain.",
                client=client, validation_report_id=accepted["report"]["id"])
        assert result["action"] == "STOP"
        assert result["live_model_response"] is False
        assert result["failure_code"] == "MODEL_OR_TOOL_CONTRACT_ERROR"
        assert result["evidence_ids"] == []
        assert record_counts(runtime)["actions"] == 0
    asyncio.run(run())


@pytest.mark.parametrize("failure", ["stale", "stopped", "cross_comparison", "missing_report"])
def test_incorrect_or_archival_validation_receipt_is_rejected_before_any_model_request(app, failure):
    runtime = app.state.runtime
    async def run():
        detail, accepted = await prepare(runtime)
        cid = detail["comparison"]["id"]
        report_id = accepted["report"]["id"]
        if failure == "stale":
            trial(runtime, cid)
        elif failure == "stopped":
            runtime.store.stop_case(detail["comparison"]["case_id"])
        elif failure == "cross_comparison":
            other, _ = await prepare(runtime)
            cid = other["comparison"]["id"]
        else:
            report_id = "validation-report-does-not-exist"
        client, requests = scripted_client()
        async with client:
            with pytest.raises((KeyError, ValueError)):
                await investigate_prevention(runtime, cid, "Explain.", client=client,
                                             validation_report_id=report_id)
        assert requests == []
        assert runtime.store.list("prevention_investigation") == []
    asyncio.run(run())


@pytest.mark.parametrize("change", ["trial", "stop", "revision"])
def test_network_turn_cannot_commit_after_trial_case_or_stop_change(app, change):
    runtime = app.state.runtime
    async def run():
        detail, accepted = await prepare(runtime)
        comparison = detail["comparison"]
        def mutate():
            if change == "trial":
                trial(runtime, comparison["id"])
            elif change == "stop":
                runtime.store.stop_case(comparison["case_id"])
            else:
                case = runtime.store.case(comparison["case_id"])
                runtime.store.update_case(case["id"], case["revision"], {"state": "INVESTIGATE"})
        client, requests = scripted_client(finish_hook=mutate)
        async with client:
            with pytest.raises(ValueError, match="changed|stopped|stale|evaluation"):
                await investigate_prevention(runtime, comparison["id"], "Explain.", client=client,
                                             validation_report_id=accepted["report"]["id"])
        assert len(requests) == 5
        assert runtime.store.list("prevention_investigation") == []
        assert record_counts(runtime)["actions"] == 0
    asyncio.run(run())


@pytest.mark.parametrize("forbidden", ["observe_again", "run_predeclared_sensitivity", "propose_collection"])
def test_validation_review_cannot_observe_recompute_or_propose_actions(app, forbidden):
    runtime = app.state.runtime
    async def run():
        detail, accepted = await prepare(runtime)
        args = ({"preset_id": "predeclared-transport-envelope-v1"}
                if forbidden == "run_predeclared_sensitivity" else
                {"evidence_id": detail["comparison"]["source_evidence_id"]}
                if forbidden == "propose_collection" else {})
        client, _ = scripted_client(command=lambda context: {"tool": forbidden, "arguments": args})
        before = copy.deepcopy(detail)
        async with client:
            result = await investigate_prevention(runtime, detail["comparison"]["id"], "Explain.",
                client=client, validation_report_id=accepted["report"]["id"])
        assert result["action"] == "STOP" and result["trace"] == []
        assert result["failure_code"] == "MODEL_OR_TOOL_CONTRACT_ERROR"
        assert runtime.prevention.comparison_detail(detail["comparison"]["id"]) == before
        assert runtime.camera.status()["running"] is False
        assert record_counts(runtime)["actions"] == 0
    asyncio.run(run())


def test_backend_rechecks_receipt_and_does_not_expose_validation_without_selection(app):
    runtime = app.state.runtime
    async def run():
        detail, accepted = await prepare(runtime)
        unselected = PreventionCaseBackend(runtime, detail)
        with pytest.raises(ValueError, match="read-only"):
            await unselected.call("get_validation_evidence", {})
        selected = PreventionCaseBackend(runtime, detail, accepted)
        trial(runtime, detail["comparison"]["id"])
        with pytest.raises(ValueError, match="ledger changed"):
            await selected.call("get_validation_evidence", {})
    asyncio.run(run())


def test_api_validation_selection_requires_operator_and_rejects_missing_receipt(app, monkeypatch):
    import apps.api.reeftrace_api.services.prevention_investigation as investigator

    async def unexpected_model(*args, **kwargs):
        raise AssertionError("A missing validation receipt must fail before the model transport")
    monkeypatch.setattr(investigator, "investigate", unexpected_model)
    with TestClient(app) as client:
        detail, _ = asyncio.run(prepare(app.state.runtime))
        url = f"/api/v1/prevention/comparisons/{detail['comparison']['id']}/investigate"
        body = {"text": "Explain.", "validation_report_id": "validation-report-missing"}
        assert client.post(url, json=body).status_code == 401
        assert client.post(url, headers=AUTH, json=body).status_code == 404
        assert app.state.runtime.store.list("prevention_investigation") == []
