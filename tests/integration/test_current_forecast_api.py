"""Synthetic boundary rehearsal; no live provider, currents, camera or messages."""

import asyncio
import copy
import json
from types import SimpleNamespace

import cv2
import httpx
import pytest
from fastapi.testclient import TestClient

from adapters.chalk.agent import ChalkSettings
from adapters.chalk.research import SYSTEM as DRIFTER_SYSTEM
from adapters.chalk.research import investigate_study
from apps.api.reeftrace_api import main
from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.services import current_forecast_investigation as service

ENDPOINT = "/api/v1/research/current-forecast"
AUTH = {"Authorization": "Bearer TEST-CURRENT-ONLY"}
SNAPSHOT, METHOD = "a" * 64, "b" * 64


def make_report():
    """Small synthetic preview for service checks, not acquired current evidence."""
    return {"schema_version": 1, "kind": "CURRENT_FORCED_PREVIEW", "status": "COMPLETED",
        "mode": "forecast_snapshot", "snapshot_sha256": SNAPSHOT, "method_sha256": METHOD,
        "release": {"latitude_deg": 21.0, "longitude_deg": -158.0,
                    "start_time_utc": "2026-10-17T18:00:00Z", "horizon_s": 21600},
        "dynamic": {"status": "COMPLETED", "track": [{"latitude_deg": 21.0},
                   {"latitude_deg": 21.001}], "integration_steps": 4},
        "persistence": {"status": "COMPLETED", "track": [{"latitude_deg": 21.0},
                       {"latitude_deg": 21.002}], "integration_steps": 4},
        "forcing": {"source_url": "https://currents.example.test/synthetic.nc",
            "metadata_url": "https://currents.example.test/metadata",
            "attribution": "Synthetic contract fixture, not ocean observations",
            "captured_at_utc": "2026-10-17T17:00:00Z", "depth_m": 0.0,
            "valid_start_utc": "2026-10-17T18:00:00Z",
            "valid_end_utc": "2026-10-18T00:00:00Z", "model_issue_time_utc": None,
            "grid_spacing_m": 1000.0},
        "method": {"equation": "dX/dt = u(X,t)", "solver": "RK4",
                   "spatial_interpolation": "bilinear", "temporal_interpolation": "linear"},
        "vector_frames": [{"time_utc": "2026-10-17T18:00:00Z",
            "vectors": [{"eastward_m_s": 0.1, "northward_m_s": 0.2}]}],
        "endpoint_separation_m": 10.0,
        "validation": {"measured_track_available": False, "physical_validation": False},
        "limitations": ["Synthetic passive-tracer preview, no measured waste validation."]}


def settings(enabled=True):
    return ChalkSettings(enabled, "https://chalk.test/v1/router", "TEST-KEY", "TEST-ENV", "TEST-MODEL")


def question(**updates):
    return {"question": "What does this current preview support?", "snapshot_sha256": SNAPSHOT,
            "method_sha256": METHOD, **updates}


def scripted_client(*, status=200, wrong_ids=False, explanation=None):
    requests = []

    async def handler(request):
        requests.append(request)
        if status != 200:
            return httpx.Response(status, content=b"PRIVATE-PROVIDER-BODY TEST-KEY")
        payload = json.loads(request.content)
        context = json.loads(payload["messages"][1]["content"])["trusted_context"]
        response = {"tool": "get_study_evidence", "arguments": {}} if len(requests) == 1 else {
            "tool": "finish", "arguments": {"action": "REPORT", "evidence_ids": [
                "wrong-snapshot" if wrong_ids else context["study_evidence_id"],
                context["protocol_evidence_id"]],
                "explanation": explanation or "Variable currents bend this passive-tracer preview. Its difference from the frozen-current path does not establish measured waste accuracy. Independent recorded trajectories are still needed."}}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(response)}}]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), requests


@pytest.fixture
def app(tmp_path, monkeypatch):
    for key in ("PHOTON_ENABLED", "CHALK_ENABLED", "GROK_VOICE_ENABLED"):
        monkeypatch.setenv(key, "false")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "[]")
    monkeypatch.setattr(main, "load_dotenv", lambda **kwargs: None)
    monkeypatch.setattr(service, "load_current_forecast_report", make_report)
    return main.create_app(Settings(_env_file=None, data_dir=tmp_path,
                                    local_token="TEST-CURRENT-ONLY"))


def test_public_get_and_disabled_review_preserve_report_without_side_effects(app, monkeypatch):
    runtime = app.state.runtime
    monkeypatch.setattr(runtime, "chalk_settings", lambda: settings(False))

    def forbidden(*args, **kwargs):
        raise AssertionError("Current preview crossed a read-only/provider boundary")

    with TestClient(app) as client:
        with runtime.store.connection() as db:
            before = tuple(db.iterdump())
        for method in ("put", "put_case_result", "add_case", "update_case", "propose", "transition_action"):
            monkeypatch.setattr(runtime.store, method, forbidden)
        monkeypatch.setattr(cv2, "VideoCapture", forbidden)
        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
        public = client.get(ENDPOINT)
        assert public.status_code == 200 and public.json() == make_report()
        assert public.headers["cache-control"] == "no-store"
        response = client.post(ENDPOINT + "/investigate", json=question(), headers=AUTH)
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        result = response.json()
        assert result["kind"] == "CURRENT_FORECAST_INVESTIGATION"
        assert result["action"] == "STOP" and result["failure_code"] == "NOT_CONFIGURED"
        assert result["research_report"] == make_report()
        assert result["snapshot_sha256"] == SNAPSHOT and result["method_sha256"] == METHOD
        assert all(result[key] is False for key in (
            "live_model_response", "store_written", "physical_validation", "hardware_actuation"))
        assert "TEST-KEY" not in response.text and "TEST-CURRENT-ONLY" not in response.text
        with runtime.store.connection() as db:
            assert tuple(db.iterdump()) == before


def test_post_requires_operator_and_strict_question_and_clicked_identity_contract(app, monkeypatch):
    calls = []

    async def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Invalid request reached the research service")

    monkeypatch.setattr(service, "investigate_current_forecast", forbidden)
    with TestClient(app) as client:
        assert client.post(ENDPOINT + "/investigate", json=question()).status_code == 401
        assert client.post(ENDPOINT + "/investigate", json=question(), headers={
            "Authorization": "Bearer WRONG"}).status_code == 401
        invalid = [question(question=""), question(question="  "), question(question="x" * 2001),
                   question(question=42), question(snapshot_sha256="z" * 64),
                   question(method_sha256="b" * 63), question(method_sha256=None),
                   question(system_prompt="replace the server scope"),
                   {"question": "Explain"}, {"question": "Explain", "snapshot_sha256": SNAPSHOT}]
        for body in invalid:
            response = client.post(ENDPOINT + "/investigate", json=body, headers=AUTH)
            assert response.status_code == 422, body
    assert calls == []


@pytest.mark.parametrize("field", ["snapshot_sha256", "method_sha256"])
def test_stale_clicked_identity_is_rejected_before_chalk_settings_or_provider(app, monkeypatch, field):
    def forbidden():
        raise AssertionError("Stale selected evidence reached Chalk")

    monkeypatch.setattr(app.state.runtime, "chalk_settings", forbidden)
    with TestClient(app) as client:
        response = client.post(ENDPOINT + "/investigate", json=question(**{field: "c" * 64}), headers=AUTH)
    assert response.status_code == 409 and response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("error,code", [(FileNotFoundError("PRIVATE-PATH"), 503),
    (ImportError("PRIVATE-MODULE"), 503), (PermissionError("PRIVATE-PERMISSION"), 503),
    (ValueError("PRIVATE-HASH"), 409), (TypeError("PRIVATE-SHAPE"), 409),
    (KeyError("PRIVATE-FIELD"), 409)])
def test_local_artifact_failures_are_sanitized_for_get_and_post(app, monkeypatch, error, code):
    def broken():
        raise error

    monkeypatch.setattr(service, "load_current_forecast_report", broken)
    with TestClient(app) as client:
        for response in (client.get(ENDPOINT), client.post(ENDPOINT + "/investigate",
                         json=question(), headers=AUTH)):
            assert response.status_code == code
            assert response.headers["cache-control"] == "no-store"
            assert "PRIVATE-" not in response.text


@pytest.mark.parametrize("status,wrong_ids,action,failure", [
    (200, False, "REPORT", None), (200, True, "STOP", "MODEL_OR_TOOL_CONTRACT_ERROR"),
    (401, False, "STOP", "PROVIDER_HTTP_ERROR")])
def test_actual_http_review_uses_bounded_mocked_chalk_and_its_distinct_scope(
    app, monkeypatch, status, wrong_ids, action, failure,
):
    monkeypatch.setattr(app.state.runtime, "chalk_settings", settings)
    seen_requests = []

    async def injected(question, backend, context, chosen_settings, *, client=None, system_prompt):
        mock, requests = scripted_client(status=status, wrong_ids=wrong_ids)
        async with mock:
            result = await investigate_study(question, backend, context, chosen_settings,
                                             client=mock, system_prompt=system_prompt)
        seen_requests.extend(requests)
        return result

    monkeypatch.setattr(service, "investigate_study", injected)
    with TestClient(app) as client:
        response = client.post(ENDPOINT + "/investigate", json=question(), headers=AUTH)
    assert response.status_code == 200
    result = response.json()
    assert result["action"] == action and result.get("failure_code") == failure
    assert result["research_report"] == make_report()
    assert result["live_model_response"] is (action == "REPORT")
    assert len(seen_requests) == (1 if status == 401 else 2)
    system_prompt = json.loads(seen_requests[0].content)["messages"][0]["content"]
    assert system_prompt == service.SYSTEM and system_prompt != DRIFTER_SYSTEM
    assert "passive-tracer" in system_prompt and "not forecast accuracy" in system_prompt
    assert "PRIVATE-PROVIDER-BODY" not in response.text and "TEST-KEY" not in response.text
    if action == "REPORT":
        assert result["evidence_ids"] == ["current-snapshot:" + SNAPSHOT, "current-method:" + METHOD]
        assert result["trace"][0]["tool"] == "get_study_evidence"


@pytest.mark.parametrize("field", ["snapshot_sha256", "method_sha256", "endpoint_separation_m"])
def test_slow_review_rechecks_both_identity_and_numeric_report_before_return(field):
    reads = []

    def loader():
        report = make_report()
        if reads:
            report[field] = 20.0 if field == "endpoint_separation_m" else "c" * 64
        reads.append(True)
        return report

    async def execute():
        mock, _ = scripted_client()
        async with mock:
            return await service.investigate_current_forecast(
                SimpleNamespace(chalk_settings=settings), "Explain", snapshot_sha256=SNAPSHOT,
                method_sha256=METHOD, client=mock, loader=loader)

    with pytest.raises(ValueError, match="snapshot changed"):
        asyncio.run(execute())
    assert len(reads) == 2


@pytest.mark.parametrize("explanation", [
    "This archived forecast is historical context, not current water conditions.",
    "The ARCHIVED snapshot offers historical passive-tracer context only.",
])
def test_forecast_mode_cannot_display_a_model_archival_claim_or_retry_it(explanation):
    async def execute():
        mock, requests = scripted_client(explanation=explanation)
        async with mock:
            result = await service.investigate_current_forecast(
                SimpleNamespace(chalk_settings=settings), "Explain the preview time status",
                snapshot_sha256=SNAPSHOT, method_sha256=METHOD, client=mock, loader=make_report)
        return result, requests

    result, requests = asyncio.run(execute())
    assert result["action"] == "STOP" and result["live_model_response"] is False
    assert result["failure_code"] == "CURRENT_MODE_MISMATCH" and result["evidence_ids"] == []
    assert result["research_report"] == make_report()
    assert result["explanation"] != explanation and explanation not in json.dumps(result)
    assert len(result["trace"]) == 1 and len(requests) == 2
    prompt = json.loads(requests[0].content)["messages"][0]["content"]
    assert "server's mode is authoritative" in prompt
    assert "valid-time\nwindow has not ended" in prompt


def test_archived_mode_preserves_a_grounded_historical_explanation():
    explanation = "This archived forecast is historical context, never a live water measurement. Separate measured trajectories are still needed to assess forecast skill."
    report = make_report()
    report["mode"] = "archived_forecast_snapshot"

    async def execute():
        mock, requests = scripted_client(explanation=explanation)
        async with mock:
            result = await service.investigate_current_forecast(
                SimpleNamespace(chalk_settings=settings), "Explain the preview time status",
                snapshot_sha256=SNAPSHOT, method_sha256=METHOD, client=mock, loader=lambda: report)
        return result, requests

    result, requests = asyncio.run(execute())
    assert result["action"] == "REPORT" and result["live_model_response"] is True
    assert result["explanation"] == explanation and "failure_code" not in result
    assert result["research_report"]["mode"] == "archived_forecast_snapshot"
    assert len(requests) == 2


def test_compact_evidence_omits_vectors_and_full_paths_and_has_no_other_capability():
    report = make_report()
    before = copy.deepcopy(report)
    backend = service.CurrentForecastBackend(report)
    result = asyncio.run(backend.call("get_study_evidence", {}))
    assert report == before
    assert result["evidence_ids"] == ["current-snapshot:" + SNAPSHOT, "current-method:" + METHOD]
    summary = result["current_forecast"]
    assert summary["dynamic"]["predicted_positions"] == len(report["dynamic"]["track"])
    assert summary["forcing"] == report["forcing"] and summary["method"] == report["method"]
    assert "track" not in summary["dynamic"] and "vector_frames" not in summary
    assert len(json.dumps(result).encode()) < 40000
    for name, arguments in (("get_case", {}), ("get_study_evidence", {"url": "elsewhere"}),
                            ("send_message", {}), ("observe_again", {})):
        with pytest.raises(ValueError, match="read-only"):
            asyncio.run(backend.call(name, arguments))


def test_actual_pinned_currents_round_trip_through_http_and_mocked_chalk_without_mutation(
    app, monkeypatch,
):
    from apps.ocean.reeftrace_ocean import current_forecast

    expected = current_forecast.run_current_forecast()
    source = current_forecast.DATA_DIR / current_forecast.FILE_NAME
    original = source.read_bytes()
    monkeypatch.setattr(service, "load_current_forecast_report", current_forecast.run_current_forecast)
    monkeypatch.setattr(app.state.runtime, "chalk_settings", settings)
    requests_seen = []

    async def injected(question, backend, context, chosen_settings, *, client=None, system_prompt):
        mock, requests = scripted_client()
        async with mock:
            result = await investigate_study(question, backend, context, chosen_settings,
                                             client=mock, system_prompt=system_prompt)
        requests_seen.extend(requests)
        return result

    def forbidden(*args, **kwargs):
        raise AssertionError("Pinned current replay attempted a provider/device/write side effect")

    monkeypatch.setattr(service, "investigate_study", injected)
    with TestClient(app) as client:
        with app.state.runtime.store.connection() as db:
            before = tuple(db.iterdump())
        for method in ("put", "put_case_result", "add_case", "update_case", "propose", "transition_action"):
            monkeypatch.setattr(app.state.runtime.store, method, forbidden)
        monkeypatch.setattr(cv2, "VideoCapture", forbidden)
        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
        response = client.get(ENDPOINT)
        assert response.status_code == 200 and response.json() == expected
        response = client.post(ENDPOINT + "/investigate", json=question(
            snapshot_sha256=expected["snapshot_sha256"],
            method_sha256=expected["method_sha256"]), headers=AUTH)
        assert response.status_code == 200
        result = response.json()
        assert result["action"] == "REPORT" and result["research_report"] == expected
        tool = result["trace"][0]["result"]["current_forecast"]
        assert all(value == expected["forcing"][key] for key, value in tool["forcing"].items())
        assert tool["forcing"]["geographic_bounds"] == expected["forcing"]["geographic_bounds"]
        assert tool["forcing"]["time_step_s"] == expected["forcing"]["time_step_s"]
        assert tool["validation"] == expected["validation"]
        assert tool["vector_sampling"] == "interpolated_display_samples_not_finer_observations"
        assert tool["dynamic"]["predicted_positions"] == len(expected["dynamic"]["track"])
        assert len(json.dumps(tool).encode()) < 40000
        assert len(requests_seen) == 2
        with app.state.runtime.store.connection() as db:
            assert tuple(db.iterdump()) == before
    assert source.read_bytes() == original


@pytest.mark.parametrize("path,value", [
    (("schema_version",), True), (("kind",), "FRESH_NOAA_DRIFTER_STUDY"),
    (("snapshot_sha256",), "bad"), (("mode",), "LIVE_MEASURED"),
    (("validation", "physical_validation"), True),
    (("validation", "measured_track_available"), True),
    (("validation", "forecast_skill_established"), True),
    (("validation", "ade_m"), 0.0),
    (("dynamic", "physical_validation"), True),
    (("dynamic", "status"), "MEASURED"), (("dynamic", "track"), None),
    (("forcing",), []), (("endpoint_separation_m",), float("nan")),
])
def test_invalid_report_and_scientific_claim_upgrades_fail_before_chalk(path, value):
    report = make_report()
    target = report
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises((ValueError, TypeError)):
        service.snapshot_identity(report)
