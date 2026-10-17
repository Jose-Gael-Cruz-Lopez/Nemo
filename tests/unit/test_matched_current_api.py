"""Synthetic artifact-boundary and mocked Chalk checks; no real study execution."""

import asyncio
import copy
import hashlib
import json
import sys
from types import ModuleType, SimpleNamespace

import cv2
import httpx
import pytest
from fastapi.testclient import TestClient

from adapters.chalk.agent import ChalkSettings
from adapters.chalk.research import investigate_study
from apps.api.reeftrace_api import main
from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.services import matched_current_investigation as service
from apps.ocean.reeftrace_ocean import matched_current as models

ENDPOINT = "/api/v1/research/matched-current"
REPORT, PROTOCOL = "a" * 64, "b" * 64
AUTH = {"Authorization": "Bearer TEST-MATCHED-ONLY"}
DEFAULT_READER = service.load_matched_current_result


def make_snapshot():
    """Invented missing-input results; these are not acquired or validated data."""
    forecasts = models.build_matched_current_forecasts({})
    scores = models.score_matched_current_forecasts(forecasts, {})
    lineage = {"protocol_sha256": PROTOCOL, "manifest_sha256": "c" * 64,
               "acquisition_start_sha256": "d" * 64, "trusted_identity_sha256": "e" * 64}
    report = {"schema_version": 1, "kind": "MATCHED_CURRENT_RETROSPECTIVE_DIAGNOSTIC",
        "study_id": service.STUDY_ID, "lineage": lineage, "forecast_file_sha256": "f" * 64,
        "forecast_frozen_at_utc": "2026-10-17T17:00:00Z",
        "forecasts_saved_before_target_coordinate_decode": True,
        "scored_at_utc": "2026-10-17T17:01:00Z", "scores": scores,
        "source_receipts": [], "context_qc": {}, "current_field": None,
        "current_field_failure": "SYNTHETIC_MISSING_FIELD"}
    for flag in ("physical_validation", "operational_causality", "assimilation_independence_verified",
                 "physical_alias_resolution_verified", "statistical_independence", "global_training",
                 "heldout_tuning", "automatic_model_promotion", "provider_calls", "camera_started",
                 "store_written"):
        report[flag] = False
    return {"report": report, "artifact_identity": {"schema_version": 1,
        "study_id": service.STUDY_ID, "report_sha256": REPORT, "protocol_sha256": PROTOCOL,
        "forecast_file_sha256": "f" * 64, "forecast_sha256": forecasts["forecast_sha256"],
        "trusted_protocol_identity_sha256": "e" * 64, "manifest_sha256": "c" * 64,
        "acquisition_start_sha256": "d" * 64, "integrity_verified": True,
        "numeric_replay_verified": False, "verification_scope": service.VERIFICATION_SCOPE,
        "result_pin_verified": True, "pin_source": "TRUSTED_RESULT_IDENTITY",
        "result_identity_file_sha256": "1" * 64}}


def chalk_settings(enabled=True):
    return ChalkSettings(enabled, "https://chalk.test/v1/router", "TEST-MATCHED-KEY",
                         "TEST-ENV", "TEST-MODEL")


def question(**updates):
    return {"question": "What does this matched study support?", "report_sha256": REPORT,
            "protocol_sha256": PROTOCOL, **updates}


def scripted_client(*, status=200, wrong_ids=False, missing_id=False, unsafe_tool=False,
                    repeated_read=False, explanation=None, delay=0):
    requests = []

    async def handler(request):
        requests.append(request)
        if delay:
            await asyncio.sleep(delay)
        if status != 200:
            return httpx.Response(status, content=b"PRIVATE-PROVIDER-BODY TEST-MATCHED-KEY")
        payload = json.loads(request.content)
        context = json.loads(payload["messages"][1]["content"])["trusted_context"]
        ids = [context["study_evidence_id"], context["protocol_evidence_id"]]
        if wrong_ids:
            ids[0] = "unrelated-report"
        if missing_id:
            ids.pop()
        if unsafe_tool:
            command = {"tool": "send_message", "arguments": {}}
        elif len(requests) == 1 or repeated_read:
            command = {"tool": "get_study_evidence", "arguments": {}}
        else:
            command = {"tool": "finish", "arguments": {"action": "REPORT", "evidence_ids": ids,
                "explanation": explanation or (
                    "The matched comparison retains unavailable outcomes rather than treating them as successes. "
                    "Historical buoy estimates and analysis currents do not establish independent forecast skill. "
                    "Separate recorded trajectories and tank trials are still needed.")}}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(command)}}]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), requests


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "load_dotenv", lambda **kwargs: None)
    snapshot = make_snapshot()
    monkeypatch.setattr(service, "load_matched_current_result", lambda: copy.deepcopy(snapshot))
    return main.create_app(Settings(_env_file=None, data_dir=tmp_path,
                                    local_token="TEST-MATCHED-ONLY"))


def test_get_and_unconfigured_review_preserve_read_only_snapshot_without_model_execution(app, monkeypatch):
    expected = make_snapshot()
    runtime = app.state.runtime
    monkeypatch.setattr(runtime, "chalk_settings", lambda: chalk_settings(False))

    def forbidden(*args, **kwargs):
        raise AssertionError("Artifact review crossed a model, provider, write or device boundary")

    with TestClient(app) as client:
        with runtime.store.connection() as db:
            before = tuple(db.iterdump())
        for method in ("put", "put_case_result", "add_case", "update_case", "propose", "transition_action"):
            monkeypatch.setattr(runtime.store, method, forbidden)
        monkeypatch.setattr(models, "build_matched_current_forecasts", forbidden)
        monkeypatch.setattr(models, "score_matched_current_forecasts", forbidden)
        monkeypatch.setattr(cv2, "VideoCapture", forbidden)
        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
        response = client.get(ENDPOINT)
        assert response.status_code == 200 and response.json() == expected
        assert response.headers["cache-control"] == "no-store"
        response = client.post(ENDPOINT + "/investigate", json=question(), headers=AUTH)
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        result = response.json()
        assert result["kind"] == "MATCHED_CURRENT_RESEARCH_INVESTIGATION"
        assert result["scope"] == "READ_ONLY_MATCHED_CURRENT_STUDY"
        assert result["action"] == "STOP" and result["failure_code"] == "NOT_CONFIGURED"
        assert result["research_report"] == expected["report"]
        assert result["artifact_identity"] == expected["artifact_identity"]
        assert all(result[key] is False for key in (
            "live_model_response", "numeric_replay_verified", "physical_validation",
            "hardware_actuation", "store_written"))
        assert "TEST-MATCHED-ONLY" not in response.text and "TEST-MATCHED-KEY" not in response.text
        with runtime.store.connection() as db:
            assert tuple(db.iterdump()) == before


def test_post_requires_operator_strict_question_and_selected_report_and_protocol(app, monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("An invalid request reached Chalk review")

    monkeypatch.setattr(service, "investigate_matched_current", forbidden)
    with TestClient(app) as client:
        for headers in ({}, {"Authorization": "Bearer WRONG"}):
            assert client.post(ENDPOINT + "/investigate", json=question(), headers=headers).status_code == 401
        for body in (question(question=""), question(question="  "), question(question=42),
                     question(question="x" * 2001), question(report_sha256="g" * 64),
                     question(protocol_sha256="b" * 63), question(protocol_sha256=None),
                     question(system_prompt="promote this model"), {"question": "Explain"}):
            assert client.post(ENDPOINT + "/investigate", json=body, headers=AUTH).status_code == 422


@pytest.mark.parametrize("field", ["report_sha256", "protocol_sha256"])
def test_stale_selected_hash_is_rejected_before_chalk_configuration_or_provider(app, monkeypatch, field):
    def forbidden():
        raise AssertionError("Stale selected study reached a provider")

    monkeypatch.setattr(app.state.runtime, "chalk_settings", forbidden)
    with TestClient(app) as client:
        response = client.post(ENDPOINT + "/investigate", json=question(**{field: "9" * 64}), headers=AUTH)
    assert response.status_code == 409 and response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("error,code", [
    (FileNotFoundError("PRIVATE-PATH"), 404), (ValueError("PRIVATE-HASH"), 409),
    (TypeError("PRIVATE-SHAPE"), 409), (KeyError("PRIVATE-FIELD"), 409),
    (ImportError("PRIVATE-MODULE"), 503), (PermissionError("PRIVATE-PATH"), 503),
])
def test_missing_or_corrupt_artifacts_fail_closed_without_leaking_details(app, monkeypatch, error, code):
    def broken():
        raise error

    monkeypatch.setattr(service, "load_matched_current_result", broken)
    with TestClient(app) as client:
        for response in (client.get(ENDPOINT), client.post(ENDPOINT + "/investigate",
                         json=question(), headers=AUTH)):
            assert response.status_code == code
            assert response.headers["cache-control"] == "no-store"
            assert "PRIVATE-" not in response.text


@pytest.mark.parametrize("change", ["unverified", "numeric_replay", "caller_pin", "groups", "cells",
                                   "targets", "physical", "lineage", "nonfinite"])
def test_invalid_reader_envelope_is_rejected_before_any_provider(app, monkeypatch, change):
    snapshot = make_snapshot()
    identity, report = snapshot["artifact_identity"], snapshot["report"]
    if change == "unverified":
        identity["result_pin_verified"] = False
    elif change == "numeric_replay":
        identity["numeric_replay_verified"] = True
    elif change == "caller_pin":
        identity["pin_source"] = "EXPLICIT_CALLER_PIN"
    elif change == "groups":
        report["scores"]["groups"].pop()
    elif change == "cells":
        report["scores"]["planned_cell_count"] = 35
    elif change == "targets":
        report["scores"]["planned_distinct_target_count"] = 36
    elif change == "physical":
        report["physical_validation"] = True
    elif change == "lineage":
        report["lineage"]["protocol_sha256"] = "9" * 64
    else:
        report["scores"]["models"][0]["metrics"]["full_horizon_ade_m"] = float("nan")
    monkeypatch.setattr(service, "load_matched_current_result", lambda: snapshot)

    def forbidden():
        raise AssertionError("Invalid study reached provider configuration")

    monkeypatch.setattr(app.state.runtime, "chalk_settings", forbidden)
    with TestClient(app) as client:
        assert client.get(ENDPOINT).status_code == 409
        assert client.post(ENDPOINT + "/investigate", json=question(), headers=AUTH).status_code == 409


@pytest.mark.parametrize("options,action,failure,calls", [
    ({}, "REPORT", None, 2),
    ({"wrong_ids": True}, "STOP", "MODEL_OR_TOOL_CONTRACT_ERROR", 2),
    ({"missing_id": True}, "STOP", "MODEL_OR_TOOL_CONTRACT_ERROR", 2),
    ({"unsafe_tool": True}, "STOP", "MODEL_OR_TOOL_CONTRACT_ERROR", 1),
    ({"repeated_read": True}, "STOP", "MODEL_OR_TOOL_CONTRACT_ERROR", 2),
    ({"explanation": "Accuracy improved by 90 percent."}, "STOP", "MODEL_OR_TOOL_CONTRACT_ERROR", 2),
    ({"status": 401}, "STOP", "PROVIDER_HTTP_ERROR", 1),
])
def test_http_chalk_review_is_bounded_hash_cited_and_separate_from_cases(
    app, monkeypatch, options, action, failure, calls,
):
    monkeypatch.setattr(app.state.runtime, "chalk_settings", chalk_settings)
    requests_seen = []

    async def injected(question, backend, context, settings, *, client=None, system_prompt):
        mock, requests = scripted_client(**options)
        async with mock:
            result = await investigate_study(question, backend, context, settings,
                                             client=mock, system_prompt=system_prompt)
        requests_seen.extend(requests)
        return result

    monkeypatch.setattr(service, "investigate_study", injected)
    with TestClient(app) as client:
        response = client.post(ENDPOINT + "/investigate", json=question(), headers=AUTH)
    assert response.status_code == 200
    result = response.json()
    assert result["action"] == action and result.get("failure_code") == failure
    assert result["research_report"] == make_snapshot()["report"]
    assert result["live_model_response"] is (action == "REPORT")
    assert len(requests_seen) == calls
    prompt = json.loads(requests_seen[0].content)["messages"][0]["content"]
    assert prompt == service.SYSTEM
    assert "two GDP groups, three models" in prompt and "not a verified" in prompt
    assert "does not rerun" in prompt and "assimilation independence" in prompt
    assert "PRIVATE-PROVIDER-BODY" not in response.text and "TEST-MATCHED-KEY" not in response.text
    if action == "REPORT":
        assert result["evidence_ids"] == ["matched-current-report:" + REPORT,
                                         "matched-current-protocol:" + PROTOCOL]
        tool = result["trace"][0]["result"]["matched_current_study"]
        assert tool["coverage"]["planned_cell_count"] == 36
        assert tool["coverage"]["planned_distinct_target_count"] == 12
        assert tool["coverage"]["scored_cell_count"] == 0
        assert tool["primary_equal_id_macro_results"] is None


@pytest.mark.parametrize("change", ["report_hash", "protocol_hash", "numeric_report", "reader_identity"])
def test_slow_review_rechecks_full_artifact_snapshot_after_provider(change):
    snapshots = [make_snapshot(), make_snapshot()]
    if change == "report_hash":
        snapshots[1]["artifact_identity"]["report_sha256"] = "9" * 64
    elif change == "protocol_hash":
        snapshots[1]["artifact_identity"]["protocol_sha256"] = "9" * 64
        snapshots[1]["report"]["lineage"]["protocol_sha256"] = "9" * 64
    elif change == "numeric_report":
        snapshots[1]["report"]["scores"]["models"][0]["metrics"]["missing_count"] = 11
    else:
        snapshots[1]["artifact_identity"]["result_identity_file_sha256"] = "9" * 64
    reads = []

    def loader():
        reads.append(True)
        return snapshots[len(reads) - 1]

    async def execute():
        mock, _ = scripted_client()
        async with mock:
            return await service.investigate_matched_current(
                SimpleNamespace(chalk_settings=chalk_settings), "Explain", report_sha256=REPORT,
                protocol_sha256=PROTOCOL, client=mock, loader=loader)

    with pytest.raises(ValueError, match="snapshot changed"):
        asyncio.run(execute())
    assert len(reads) == 2


def test_single_evidence_tool_has_no_runtime_actions_and_returns_defensive_copies():
    snapshot = make_snapshot()
    original = copy.deepcopy(snapshot)
    backend = service.MatchedCurrentBackend(snapshot)
    result = asyncio.run(backend.call("get_study_evidence", {}))
    assert len(json.dumps(result).encode()) < 40_000
    assert result["matched_current_study"]["artifact_verification"]["numeric_replay_verified"] is False
    result["matched_current_study"]["models"].clear()
    snapshot["report"]["scores"]["models"].clear()
    assert asyncio.run(backend.call("get_study_evidence", {}))["matched_current_study"]["models"]
    assert backend.snapshot == original
    for name, arguments in (("get_case", {}), ("send_message", {}), ("observe_again", {}),
                            ("get_study_evidence", []),
                            ("get_study_evidence", {"report_sha256": "model-selected"})):
        with pytest.raises(ValueError, match="read-only"):
            asyncio.run(backend.call(name, arguments))


def test_review_timeout_preserves_report_and_does_not_retry_provider():
    chosen = ChalkSettings(True, "https://chalk.test/v1/router", "TEST", "ENV", "MODEL", .03, .02)

    async def execute():
        mock, requests = scripted_client(delay=.08)
        async with mock:
            result = await service.investigate_matched_current(
                SimpleNamespace(chalk_settings=lambda: chosen), "Explain", report_sha256=REPORT,
                protocol_sha256=PROTOCOL, client=mock, loader=make_snapshot)
        return result, requests

    result, requests = asyncio.run(execute())
    assert result["failure_code"] == "TIMEOUT" and len(requests) == 1
    assert result["research_report"] == make_snapshot()["report"]
    assert result["numeric_replay_verified"] is False and result["store_written"] is False


def test_snapshot_digest_is_distinct_from_raw_saved_artifact_pin():
    snapshot = make_snapshot()
    backend = service.MatchedCurrentBackend(snapshot)
    assert backend.report_hash == REPORT
    assert backend.snapshot_hash == hashlib.sha256(service._canonical(snapshot)).hexdigest()
    assert backend.snapshot_hash != REPORT


def test_default_loader_uses_only_the_trusted_artifact_reader_without_overrides(monkeypatch):
    expected = make_snapshot()
    calls = []
    reader = ModuleType("apps.ocean.reeftrace_ocean.matched_current_result")

    def load(*args, **kwargs):
        calls.append((args, kwargs))
        return expected

    reader.load_frozen_matched_current_result = load
    monkeypatch.setitem(sys.modules, reader.__name__, reader)
    assert DEFAULT_READER() == expected
    # No public allow_unpinned_local or caller-supplied result pin is enabled.
    assert calls == [((), {})]


def test_oversized_compact_evidence_falls_back_without_a_second_model_call():
    snapshot = make_snapshot()
    snapshot["report"]["scores"]["limitations"].append("x" * 40_001)

    async def execute():
        mock, requests = scripted_client()
        async with mock:
            result = await service.investigate_matched_current(
                SimpleNamespace(chalk_settings=chalk_settings), "Explain", report_sha256=REPORT,
                protocol_sha256=PROTOCOL, client=mock, loader=lambda: snapshot)
        return result, requests

    result, requests = asyncio.run(execute())
    assert result["action"] == "STOP" and result["failure_code"] == "MODEL_OR_TOOL_CONTRACT_ERROR"
    assert len(requests) == 1 and result["trace"] == []
    assert result["research_report"] == snapshot["report"]
