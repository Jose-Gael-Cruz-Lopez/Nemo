"""Pinned saved-artifact API and mocked Chalk only; no first score or providers."""

import asyncio
import copy
import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import cv2
import httpx
import pytest
from fastapi.testclient import TestClient

from adapters.chalk.agent import ChalkSettings
from adapters.chalk.research import investigate_study
from apps.api.reeftrace_api import main
from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.services import origin_residual_investigation as service
from apps.ocean.reeftrace_ocean import origin_residual as model
from scripts import evaluate_origin_residual_diagnostic as frozen

ENDPOINT = "/api/v1/research/origin-residual"
AUTH = {"Authorization": "Bearer TEST-ORIGIN-ONLY"}
DEFAULT_READER = service.load_origin_residual_result


@pytest.fixture(scope="module")
def saved_snapshot():
    return DEFAULT_READER()


@pytest.fixture
def app(tmp_path, monkeypatch, saved_snapshot):
    monkeypatch.setattr(main, "load_dotenv", lambda **kwargs: None)
    monkeypatch.setattr(service, "load_origin_residual_result", lambda: copy.deepcopy(saved_snapshot))
    return main.create_app(Settings(_env_file=None, data_dir=tmp_path,
                                    local_token="TEST-ORIGIN-ONLY"))


def question(**updates):
    return {"question": "What does this exploratory residual result support?",
            "report_sha256": service.REPORT_SHA256,
            "protocol_sha256": service.PROTOCOL_SHA256,
            "identity_sha256": service.IDENTITY_SHA256, **updates}


def chalk_settings(enabled=True):
    return ChalkSettings(enabled, "https://chalk.test/v1/router", "TEST-ORIGIN-KEY",
                         "TEST-ENV", "TEST-MODEL")


def scripted_client(*, status=200, wrong_ids=False, missing_id=False, unsafe_tool=False,
                    repeated_read=False, explanation=None, delay=0, premature_finish=False):
    requests = []

    async def handler(request):
        requests.append(request)
        if delay:
            await asyncio.sleep(delay)
        if status != 200:
            return httpx.Response(status, content=b"PRIVATE-PROVIDER-BODY TEST-ORIGIN-KEY")
        payload = json.loads(request.content)
        context = json.loads(payload["messages"][1]["content"])["trusted_context"]
        ids = [context["study_evidence_id"], context["protocol_evidence_id"]]
        if wrong_ids:
            ids[0] = "matched-current-report:" + service.REPORT_SHA256
        if missing_id:
            ids.pop()
        if unsafe_tool:
            command = {"tool": "send_message", "arguments": {}}
        elif (len(requests) == 1 and not premature_finish) or repeated_read:
            command = {"tool": "get_study_evidence", "arguments": {}}
        else:
            command = {"tool": "finish", "arguments": {"action": "REPORT", "evidence_ids": ids,
                "explanation": explanation or (
                    "The residual candidate has lower descriptive error on these already-viewed buoy targets. "
                    "This is post-outcome development, not confirmatory forecast skill or physical validation. "
                    "A new frozen cohort and independent calibrated tank trials are still needed.")}}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(command)}}]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), requests


def archive_hashes():
    paths = list(frozen.DIRECTORY.rglob("*"))
    protocol = json.loads((frozen.SOURCE_DIRECTORY / "protocol.json").read_text())
    paths.extend(frozen.ROOT / relative for relative in protocol["implementation_sha256"])
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths if path.is_file()}


def test_get_and_disabled_chalk_are_read_only_actual_pinned_evidence(app, monkeypatch, saved_snapshot):
    runtime = app.state.runtime
    monkeypatch.setattr(runtime, "chalk_settings", lambda: chalk_settings(False))

    def forbidden(*args, **kwargs):
        raise AssertionError("Read-only research crossed a score/provider/store/device boundary")

    before_files = archive_hashes()
    with TestClient(app) as client:
        with runtime.store.connection() as db:
            before_store = tuple(db.iterdump())
        for method in ("put", "put_case_result", "add_case", "update_case", "propose", "transition_action"):
            monkeypatch.setattr(runtime.store, method, forbidden)
        monkeypatch.setattr(model, "build_forecasts", forbidden)
        monkeypatch.setattr(model, "score_forecasts", forbidden)
        monkeypatch.setattr(model, "corrected_field", forbidden)
        monkeypatch.setattr(frozen, "first_score", forbidden)
        monkeypatch.setattr(frozen.source, "_inputs", forbidden)
        monkeypatch.setattr(cv2, "VideoCapture", forbidden)
        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
        # Exercise the actual reader with every execution path forbidden.
        monkeypatch.setattr(service, "load_origin_residual_result", DEFAULT_READER)
        response = client.get(ENDPOINT)
        assert response.status_code == 200 and response.json() == saved_snapshot
        assert response.headers["cache-control"] == "no-store"
        response = client.post(ENDPOINT + "/investigate", json=question(), headers=AUTH)
        result = response.json()
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        assert result["action"] == "STOP" and result["failure_code"] == "NOT_CONFIGURED"
        assert result["research_report"] == saved_snapshot["report"]
        assert result["analysis_scope"] == "POST_OUTCOME_EXPLORATORY"
        assert result["previously_viewed_target_outcomes"] is True
        assert all(result[key] is False for key in (
            "live_model_response", "numeric_replay_verified", "physical_validation",
            "hardware_actuation", "store_written", "automatic_model_promotion"))
        assert "TEST-ORIGIN-KEY" not in response.text and "TEST-ORIGIN-ONLY" not in response.text
        with runtime.store.connection() as db:
            assert tuple(db.iterdump()) == before_store
    assert archive_hashes() == before_files


def test_post_requires_operator_question_and_all_three_pins(app, monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("Invalid request reached Chalk review")

    monkeypatch.setattr(service, "investigate_origin_residual", forbidden)
    with TestClient(app) as client:
        for headers in ({}, {"Authorization": "Bearer WRONG"}):
            response = client.post(ENDPOINT + "/investigate", json=question(), headers=headers)
            assert response.status_code == 401 and response.headers["cache-control"] == "no-store"
        bodies = [question(question=""), question(question="  "), question(question=42),
                  question(question="x" * 2001), question(report_sha256="g" * 64),
                  question(protocol_sha256=None), question(identity_sha256="a" * 63),
                  question(study_version="v2"), question(system_prompt="promote me")]
        for key in ("report_sha256", "protocol_sha256", "identity_sha256"):
            body = question()
            del body[key]
            bodies.append(body)
        for body in bodies:
            assert client.post(ENDPOINT + "/investigate", json=body, headers=AUTH).status_code == 422


@pytest.mark.parametrize("field", ["report_sha256", "protocol_sha256", "identity_sha256"])
def test_any_stale_selected_pin_fails_before_provider_configuration(app, monkeypatch, field):
    def forbidden():
        raise AssertionError("Stale selection reached provider configuration")

    monkeypatch.setattr(app.state.runtime, "chalk_settings", forbidden)
    with TestClient(app) as client:
        response = client.post(ENDPOINT + "/investigate", json=question(**{field: "9" * 64}), headers=AUTH)
    assert response.status_code == 409 and response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(("error", "code"), [
    (FileNotFoundError("PRIVATE-PATH"), 404), (ValueError("PRIVATE-HASH"), 409),
    (TypeError("PRIVATE-SHAPE"), 409), (KeyError("PRIVATE-FIELD"), 409),
    (RecursionError("PRIVATE-DEPTH"), 409), (ImportError("PRIVATE-MODULE"), 503),
    (PermissionError("PRIVATE-PATH"), 503), (OSError("PRIVATE-IO"), 503),
])
def test_reader_errors_fail_closed_without_detail_leaks(app, monkeypatch, error, code):
    def broken():
        raise error

    monkeypatch.setattr(service, "load_origin_residual_result", broken)
    with TestClient(app) as client:
        for response in (client.get(ENDPOINT), client.post(ENDPOINT + "/investigate",
                         json=question(), headers=AUTH)):
            assert response.status_code == code
            assert response.headers["cache-control"] == "no-store"
            assert "PRIVATE-" not in response.text


@pytest.mark.parametrize("change", [
    "unanchored", "identity", "protocol", "report", "identity_schema_bool", "replay_claim", "scope", "known_targets",
    "cell_count", "target_count", "physical", "promotion", "foreign_study", "forecast_rehashed",
    "nonfinite",
])
def test_invalid_snapshot_or_rehashed_forecast_is_rejected_before_provider(
        app, monkeypatch, saved_snapshot, change):
    snapshot = copy.deepcopy(saved_snapshot)
    identity, report = snapshot["artifact_identity"], snapshot["report"]
    if change == "unanchored":
        identity["external_result_pin_verified"] = False
    elif change in {"identity", "protocol", "report"}:
        identity[change + "_sha256"] = "9" * 64
    elif change == "identity_schema_bool":
        identity["schema_version"] = True
    elif change == "replay_claim":
        identity["numeric_replay_verified"] = True
    elif change == "scope":
        report["analysis_scope"] = "UNSEEN_CONFIRMATORY"
    elif change == "known_targets":
        report["previously_viewed_target_outcomes"] = False
    elif change == "cell_count":
        report["scores"]["planned_cell_count"] = 36
    elif change == "target_count":
        report["scores"]["planned_distinct_target_count"] = 48
    elif change == "physical":
        report["physical_validation"] = True
    elif change == "promotion":
        report["scores"]["automatic_model_promotion"] = True
    elif change == "foreign_study":
        report["study_id"] = "matched-current-gdp-hycom-15m-v2"
    elif change == "forecast_rehashed":
        forecasts = snapshot["forecasts"]
        forecasts["groups"][0]["candidates"][3]["cells"][0]["latitude_deg"] += 0.00001
        forecasts["forecast_sha256"] = model.forecast_sha256(forecasts)
    else:
        report["scores"]["primary_equal_id_macro_results"][0]["equal_id_macro_ade_m"] = float("nan")
    monkeypatch.setattr(service, "load_origin_residual_result", lambda: snapshot)

    def forbidden():
        raise AssertionError("Invalid snapshot reached provider configuration")

    monkeypatch.setattr(app.state.runtime, "chalk_settings", forbidden)
    with TestClient(app) as client:
        assert client.get(ENDPOINT).status_code == 409
        assert client.post(ENDPOINT + "/investigate", json=question(), headers=AUTH).status_code == 409


@pytest.mark.parametrize(("options", "action", "failure", "calls"), [
    ({}, "REPORT", None, 2),
    ({"premature_finish": True}, "REPORT", None, 2),
    ({"wrong_ids": True}, "STOP", "MODEL_OR_TOOL_CONTRACT_ERROR", 2),
    ({"missing_id": True}, "STOP", "MODEL_OR_TOOL_CONTRACT_ERROR", 2),
    ({"unsafe_tool": True}, "STOP", "MODEL_OR_TOOL_CONTRACT_ERROR", 1),
    ({"repeated_read": True}, "STOP", "MODEL_OR_TOOL_CONTRACT_ERROR", 2),
    ({"explanation": "Improves accuracy by 90 percent."}, "STOP", "MODEL_OR_TOOL_CONTRACT_ERROR", 2),
    ({"status": 401}, "STOP", "PROVIDER_HTTP_ERROR", 1),
])
def test_mocked_chalk_is_bounded_read_only_new_evidence_and_truthful_scope(
        app, monkeypatch, saved_snapshot, options, action, failure, calls):
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
    before = archive_hashes()
    with TestClient(app) as client:
        response = client.post(ENDPOINT + "/investigate", json=question(), headers=AUTH)
    result = response.json()
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert result["action"] == action and result.get("failure_code") == failure
    assert result["research_report"] == saved_snapshot["report"]
    assert result["analysis_scope"] == "POST_OUTCOME_EXPLORATORY"
    assert result["previously_viewed_target_outcomes"] is True
    assert result["live_model_response"] is (action == "REPORT")
    assert len(requests_seen) == calls
    first = json.loads(requests_seen[0].content)
    assert first["messages"][0]["content"] == service.SYSTEM
    context = json.loads(first["messages"][1]["content"])["trusted_context"]
    assert context["identity_sha256"] == service.IDENTITY_SHA256
    assert context["analysis_scope"] == "POST_OUTCOME_EXPLORATORY"
    assert "PRIVATE-PROVIDER-BODY" not in response.text and "TEST-ORIGIN-KEY" not in response.text
    assert archive_hashes() == before
    if action == "REPORT":
        assert result["evidence_ids"] == ["origin-residual-report:" + service.REPORT_SHA256,
                                         "origin-residual-protocol:" + service.PROTOCOL_SHA256]
        tool = result["trace"][0]["result"]["origin_residual_diagnostic"]
        assert tool["coverage"]["planned_cell_count"] == tool["coverage"]["scored_cell_count"] == 48
        assert tool["coverage"]["planned_distinct_target_count"] == 12
        assert tool["analysis_scope"] == "POST_OUTCOME_EXPLORATORY"
        assert all(value is False for value in tool["scientific_flags"].values())
        assert tool["model_definition"]["residual_transport"] == "constant_local_east_north_components"


@pytest.mark.parametrize("change", ["report_number", "forecast_number", "reader_metadata", "missing"])
def test_post_provider_full_snapshot_readback_rejects_every_generation_change(saved_snapshot, change):
    snapshots = [copy.deepcopy(saved_snapshot), copy.deepcopy(saved_snapshot)]
    if change == "report_number":
        snapshots[1]["report"]["scores"]["primary_equal_id_macro_results"][3]["equal_id_macro_ade_m"] += 1
    elif change == "forecast_number":
        snapshots[1]["forecasts"]["groups"][0]["candidates"][3]["cells"][0]["latitude_deg"] += 0.001
    elif change == "reader_metadata":
        snapshots[1]["artifact_identity"]["extra_reader_metadata"] = "changed"
    reads = []

    def loader():
        reads.append(True)
        if change == "missing" and len(reads) == 2:
            raise FileNotFoundError("Artifact disappeared during model call")
        return snapshots[len(reads) - 1]

    async def execute():
        mock, requests = scripted_client()
        async with mock:
            with pytest.raises((ValueError, FileNotFoundError)):
                await service.investigate_origin_residual(
                    SimpleNamespace(chalk_settings=chalk_settings), "Explain",
                    report_sha256=service.REPORT_SHA256, protocol_sha256=service.PROTOCOL_SHA256,
                    identity_sha256=service.IDENTITY_SHA256, client=mock, loader=loader)
        return requests

    assert len(asyncio.run(execute())) == len(reads) == 2


def test_backend_has_one_bound_evidence_tool_and_defensive_copies(saved_snapshot):
    snapshot = copy.deepcopy(saved_snapshot)
    backend = service.OriginResidualBackend(snapshot)
    result = asyncio.run(backend.call("get_study_evidence", {}))
    assert len(json.dumps(result).encode()) <= 40000
    result["origin_residual_diagnostic"]["models"].clear()
    snapshot["report"]["scores"]["models"].clear()
    assert len(asyncio.run(backend.call("get_study_evidence", {}))["origin_residual_diagnostic"]["models"]) == 4
    for name, arguments in (("send_message", {}), ("get_case", {}), ("first_score", {}),
                            ("get_study_evidence", []), ("get_study_evidence", {"directory": "elsewhere"})):
        with pytest.raises(ValueError, match="read-only"):
            asyncio.run(backend.call(name, arguments))


def test_timeout_does_not_retry_and_keeps_post_outcome_report(saved_snapshot):
    settings = ChalkSettings(True, "https://chalk.test/v1/router", "TEST", "ENV", "MODEL", .03, .02)

    async def execute():
        mock, requests = scripted_client(delay=.08)
        async with mock:
            result = await service.investigate_origin_residual(
                SimpleNamespace(chalk_settings=lambda: settings), "Explain",
                report_sha256=service.REPORT_SHA256, protocol_sha256=service.PROTOCOL_SHA256,
                identity_sha256=service.IDENTITY_SHA256, client=mock,
                loader=lambda: copy.deepcopy(saved_snapshot))
        return result, requests

    result, requests = asyncio.run(execute())
    assert result["failure_code"] == "TIMEOUT" and len(requests) == 1
    assert result["research_report"] == saved_snapshot["report"]
    assert result["analysis_scope"] == "POST_OUTCOME_EXPLORATORY"
    assert result["store_written"] is result["physical_validation"] is False


def test_default_loader_accepts_no_request_pin_or_path_override(monkeypatch, saved_snapshot):
    calls = []

    def reader(*args, **kwargs):
        calls.append((args, kwargs))
        return copy.deepcopy(saved_snapshot)

    monkeypatch.setattr(frozen, "read_diagnostic", reader)
    assert DEFAULT_READER() == saved_snapshot
    assert calls == [((), {"expected_identity_sha256": service.IDENTITY_SHA256})]
    with pytest.raises(TypeError):
        DEFAULT_READER(directory="untrusted")


@pytest.mark.parametrize("name", ["identity", "protocol", "forecasts", "evaluation"])
def test_actual_saved_artifact_tampering_fails_closed_without_repair(
        app, tmp_path, monkeypatch, name):
    directory = tmp_path / "copied-diagnostic"
    shutil.copytree(frozen.DIRECTORY, directory)
    path = directory / f"{name}.json"
    path.write_bytes(path.read_bytes() + b" ")
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    monkeypatch.setattr(service, "load_origin_residual_result", lambda: frozen.read_diagnostic(
        directory, expected_identity_sha256=service.IDENTITY_SHA256))
    with TestClient(app) as client:
        assert client.get(ENDPOINT).status_code == 409
        assert client.post(ENDPOINT + "/investigate", json=question(), headers=AUTH).status_code == 409
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == before


def test_missing_actual_directory_does_not_create_or_score_a_diagnostic(app, tmp_path, monkeypatch):
    directory = tmp_path / "missing-diagnostic"
    monkeypatch.setattr(service, "load_origin_residual_result", lambda: frozen.read_diagnostic(
        directory, expected_identity_sha256=service.IDENTITY_SHA256))
    with TestClient(app) as client:
        assert client.get(ENDPOINT).status_code == 404
        assert client.post(ENDPOINT + "/investigate", json=question(), headers=AUTH).status_code == 404
    assert not directory.exists()


def test_report_and_full_forecast_are_bound_to_exact_literal_pins(saved_snapshot):
    assert service.snapshot_identity(saved_snapshot) == (
        service.REPORT_SHA256, service.PROTOCOL_SHA256, service.IDENTITY_SHA256)
    # This is stored-artifact validation only, not rerunning model/scoring code.
    report = saved_snapshot["report"]
    assert report["scores"]["primary_equal_id_macro_results"][3]["model_id"] == "origin_residual_current"
    assert report["scores"]["primary_equal_id_macro_results"][3]["equal_id_macro_ade_m"] == 1030.0494632017758
    assert Path(frozen.DIRECTORY / "identity.json").is_file()
