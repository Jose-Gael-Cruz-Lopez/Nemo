"""Full local UI API workflow and race regressions; no live sponsor or camera calls.

The configured gateway test uses the real bounded agent with an explicit HTTP
MockTransport. It verifies wiring, not real-model quality or physical accuracy.
"""

import asyncio
import json
import threading
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from adapters.chalk.agent import ChalkSettings
from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.api.reeftrace_api.services.investigation import CaseBackend

AUTH = {"Authorization": "Bearer workflow-test"}
FIXTURES = Path(__file__).resolve().parents[2] / "data/sample_runs"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("CHALK_ENABLED", "false")
    monkeypatch.setenv("PHOTON_ENABLED", "false")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "[]")
    monkeypatch.setenv("GROK_VOICE_ENABLED", "false")
    return create_app(Settings(data_dir=tmp_path, local_token="workflow-test"))


def load(client):
    response = client.post("/api/v1/demo/load", headers=AUTH, json={})
    assert response.status_code == 200, response.text
    return response.json()["cases"]


@pytest.mark.parametrize("origin", ["http://127.0.0.1:3000", "http://localhost:3000"])
def test_dashboard_private_network_preflight_allows_exact_local_origin_and_keeps_auth(app, origin):
    with TestClient(app) as client:
        preflight = client.options("/api/v1/demo/load", headers={
            "Origin": origin, "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
            "Access-Control-Request-Private-Network": "true"})
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == origin
        assert preflight.headers["access-control-allow-private-network"] == "true"
        denied = client.post("/api/v1/demo/load", headers={"Origin": origin}, json={})
        assert denied.status_code == 401
        assert denied.headers["access-control-allow-origin"] == origin
        assert app.state.runtime.store.cases() == []


@pytest.mark.parametrize("origin", ["https://untrusted.example", "http://127.0.0.1:3001",
                                     "http://localhost:3000.untrusted.example", "null"])
def test_private_network_preflight_rejects_external_or_inexact_origins(app, origin):
    with TestClient(app) as client:
        response = client.options("/api/v1/demo/load", headers={
            "Origin": origin, "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
            "Access-Control-Request-Private-Network": "true"})
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers
        assert app.state.runtime.store.cases() == []


def test_private_network_permission_cannot_be_widened_by_wildcard_or_external_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTON_ENABLED", "false")
    app = create_app(Settings(data_dir=tmp_path, local_token="cors-test-only",
                              allowed_origins=["*", "https://external.example"]))
    with TestClient(app) as client:
        for origin in ("https://external.example", "https://another.example"):
            response = client.options("/api/v1/demo/load", headers={
                "Origin": origin, "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Private-Network": "true"})
            assert response.status_code == 400
            assert "access-control-allow-origin" not in response.headers
        assert client.post("/api/v1/demo/load", json={}).status_code == 401
        assert app.state.runtime.store.cases() == []


def test_buttons_load_compute_sensitivity_investigate_and_stop_with_real_pipeline(app):
    with TestClient(app) as client:
        loaded = load(client)
        assert [row["evidence"]["status"] for row in loaded] == ["ranked", "unknown", "invalid"]
        case_id = loaded[0]["case"]["id"]
        assert any(row["id"] == case_id for row in client.get("/api/v1/cases").json())
        case = client.get(f"/api/v1/cases/{case_id}").json()
        assert case["mode"] == "SYNTHETIC"
        assert case["points"]
        compute = client.post(f"/api/v1/cases/{case_id}/estimate", headers=AUTH, json={})
        assert compute.status_code == 200, compute.text
        evidence = compute.json()
        assert evidence["ranked_source"] == "C"
        assert evidence["id"] != loaded[0]["evidence"]["id"]
        assert evidence["confidence_kind"] == "relative_support_not_probability"
        sensitivity = client.post(f"/api/v1/cases/{case_id}/sensitivity", headers=AUTH,
                                  json={"preset_id": "predeclared-transport-envelope-v1"})
        assert sensitivity.status_code == 200, sensitivity.text
        assert sensitivity.json()["parent_estimate_id"] == evidence["id"]
        assert len(sensitivity.json()["variants"]) == 2
        answer = client.post(f"/api/v1/cases/{case_id}/investigate", headers=AUTH,
                             json={"text": "Which candidate source fits the path?"}).json()
        assert answer["action"] == "STOP"
        assert answer["live_model_response"] is False
        assert "not configured" in answer["explanation"]
        assert answer["source_report"] == evidence
        assert client.post(f"/api/v1/cases/{case_id}/stop", headers=AUTH, json={}).status_code == 200
        for operation, body in [("estimate", {}), ("sensitivity", {
                "preset_id": "predeclared-transport-envelope-v1"})]:
            assert client.post(f"/api/v1/cases/{case_id}/{operation}", headers=AUTH,
                               json=body).status_code == 409
        stopped = client.post(f"/api/v1/cases/{case_id}/investigate", headers=AUTH,
                              json={"text": "Keep going"}).json()
        assert stopped["live_model_response"] is False
        assert stopped["source_report"] is None
        assert client.get(f"/api/v1/cases/{case_id}/evidence").json() == evidence


def test_reloading_demo_reuses_active_fixtures_without_reopening_stopped_cases(app):
    with TestClient(app) as client:
        first = load(client)
        again = load(client)
        assert [row["case"]["id"] for row in again] == [row["case"]["id"] for row in first]
        assert [row["evidence"]["id"] for row in again] == [row["evidence"]["id"] for row in first]
        assert len(client.get("/api/v1/cases").json()) == 3
        stopped_id = first[0]["case"]["id"]
        client.post(f"/api/v1/cases/{stopped_id}/stop", headers=AUTH, json={})
        replacement = load(client)
        assert replacement[0]["case"]["id"] != stopped_id
        assert replacement[1:]==first[1:]
        assert client.get(f"/api/v1/cases/{stopped_id}").json()["state"] == "STOPPED"
        assert len(client.get("/api/v1/cases").json()) == 4


def test_concurrent_demo_load_is_serialized_and_does_not_duplicate_cases(app):
    async def run():
        first, second = await asyncio.gather(
            app.state.runtime.load_demo(FIXTURES), app.state.runtime.load_demo(FIXTURES))
        assert [row["case"]["id"] for row in first["cases"]] == [
            row["case"]["id"] for row in second["cases"]]
        assert second["reused_cases"] == 3
        assert len(app.state.runtime.store.cases()) == 3
    asyncio.run(run())


def test_chalk_real_agent_uses_case_tools_sensitivity_and_frozen_api_report(app, monkeypatch):
    import adapters.chalk.agent as chalk

    original = chalk.investigate
    runtime = app.state.runtime
    monkeypatch.setattr(runtime, "chalk_settings", lambda: ChalkSettings(
        enabled=True, base_url="https://contract.example/router", api_key="mock-only",
        environment_id="test-env", model="test-model"))
    calls = []

    def respond(request):
        payload = json.loads(request.content)
        calls.append(payload)
        step = len(calls)
        if step == 1:
            command = {"tool": "get_case", "arguments": {}}
        elif step == 2:
            command = {"tool": "get_source_evidence", "arguments": {}}
        elif step == 3:
            command = {"tool": "run_predeclared_sensitivity", "arguments": {
                "preset_id": "predeclared-transport-envelope-v1"}}
        else:
            results = [json.loads(message["content"])["tool_result"] for message in
                       payload["messages"] if message["role"] == "user"
                       and "tool_result" in json.loads(message["content"])]
            report = next(result["data"]["report"] for result in results
                          if result["name"] == "get_source_evidence")
            command = {"tool": "finish", "arguments": {"action": "REPORT",
                "evidence_ids": [report["id"]],
                "explanation": "The observed path supports a conditional candidate ranking; the saved sensitivity checks preserve that result."}}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(command)}}]})

    async def offline_contract(*args, **kwargs):
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            result = await original(*args, **kwargs, client=client)
        # The transport was simulated; never present this as a live sponsor result.
        result["live_model_response"] = False
        result["test_transport"] = "scripted-http-contract"
        return result

    monkeypatch.setattr(chalk, "investigate", offline_contract)
    with TestClient(app) as client:
        row = load(client)[0]
        response = client.post(f"/api/v1/cases/{row['case']['id']}/investigate", headers=AUTH,
                               json={"text": "Compare the path and run the frozen sensitivity checks."})
        assert response.status_code == 200, response.text
        answer = response.json()
        assert answer["action"] == "REPORT"
        assert answer["live_model_response"] is False
        assert answer["test_transport"] == "scripted-http-contract"
        assert answer["source_report"] == row["evidence"]
        assert [entry["tool"] for entry in answer["trace"]] == [
            "get_case", "get_source_evidence", "run_predeclared_sensitivity"]
        assert len(calls) == 4
        assert "true_source" not in json.dumps(calls)
        saved = runtime.store.list("investigation")[0]
        assert saved["source_report"]["id"] == row["evidence"]["id"]


@pytest.mark.parametrize("operation,kind", [("compute", "estimate"), ("sensitivity", "analysis")])
def test_stop_during_numerical_work_discards_result_atomically(app, monkeypatch, operation, kind):
    runtime = app.state.runtime
    case = asyncio.run(runtime.load_demo(FIXTURES))["cases"][0]["case"]
    before = len(runtime.store.list(kind))
    started, release = threading.Event(), threading.Event()

    def slow_estimate(*_, **__):
        started.set()
        assert release.wait(2)
        return {"status": "ranked", "relative_support": {"A": 1.0}, "sensitivity_results": []}

    monkeypatch.setattr("apps.estimation.reeftrace_estimation.estimate", slow_estimate)

    async def run():
        task = asyncio.create_task(getattr(runtime, operation)(case["id"]))
        assert await asyncio.to_thread(started.wait, 1)
        runtime.store.stop_case(case["id"])
        release.set()
        with pytest.raises(ValueError, match="discarded"):
            await task

    asyncio.run(run())
    assert runtime.store.case(case["id"])["state"] == "STOPPED"
    assert len(runtime.store.list(kind)) == before


@pytest.mark.parametrize("change", ["stop", "revision"])
def test_agent_tools_cannot_continue_after_case_changed(app, change):
    runtime = app.state.runtime
    case = asyncio.run(runtime.load_demo(FIXTURES))["cases"][0]["case"]
    backend = CaseBackend(runtime, case["id"])
    if change == "stop":
        runtime.store.stop_case(case["id"])
    else:
        runtime.store.update_case(case["id"], case["revision"], {"state": "INVESTIGATE"})
    with pytest.raises(ValueError, match="Case changed"):
        asyncio.run(backend.call("get_source_evidence", {}))


def test_missing_camera_is_a_clear_conflict_without_an_internal_server_error(app):
    with TestClient(app) as client:
        response = client.get("/api/v1/camera/frame.jpg")
        assert response.status_code == 409
        assert "Camera is stopped" in response.json()["detail"]
        response = client.post("/api/v1/camera/record", headers=AUTH,
                               json={"duration_s": 1})
        assert response.status_code == 409
        assert "Provide profile_id" in response.json()["detail"]
        assert client.get("/api/v1/recordings").json() == []


def test_manual_action_history_survives_reopening_and_is_case_scoped(app, monkeypatch):
    from apps.api.reeftrace_api.schemas.contracts import CaseInput

    runtime = app.state.runtime
    row = asyncio.run(runtime.load_demo(FIXTURES))["cases"][0]
    live = dict(row["case"], mode="LIVE")
    live = runtime.store.add_case({key: value for key, value in live.items()
                                  if key in CaseInput.model_fields})
    live = runtime.store.update_case(live["id"], live["revision"], {
        "evidence_id": row["evidence"]["id"], "state": "INVESTIGATE"})
    # This regression tests persistence/task lifecycle, not a physical camera.
    monkeypatch.setattr(runtime, "validate_live", lambda *_, **__: None)
    action = runtime.propose(live["id"], row["evidence"]["id"], operator=True)
    with TestClient(app) as client:
        assert client.get(f"/api/v1/cases/{live['id']}/actions").json() == [action]
        assert client.get(f"/api/v1/cases/{row['case']['id']}/actions").json() == []
        assert client.get("/api/v1/cases/missing-case/actions").status_code == 404
        client.post(f"/api/v1/actions/{action['id']}/cancel", headers=AUTH, json={})
        assert client.get(f"/api/v1/cases/{live['id']}/actions").json()[0]["state"] == "cancelled"


def test_e2e_audit_script_exercises_api_and_truthfully_keeps_external_blockers(app):
    from scripts.e2e_demo import audit

    with TestClient(app) as client:
        result = audit("http://127.0.0.1:8000", "workflow-test", client=client)
    assert result["summary"]["software_workflow_passed"], result
    assert result["summary"]["FAIL"] == 0
    assert result["summary"]["BLOCKED"] == 4
    assert result["summary"]["complete_live_product_verified"] is False
    assert result["evidence"]["live_chalk_response"] is False
    assert result["evidence"]["real_data_split"]["heldout_count"] == 6
    assert result["evidence"]["training_diagnostic_split"]["test_data_used"] is False
    assert [row["source_status"] for row in result["evidence"]["frozen_briefings"]] == [
        "ranked", "unknown", "invalid"]
    assert len(result["evidence"]["satellite_sample_sha256"]) == 64
    assert result["xai_audio_requested"] is False
    assert "workflow-test" not in json.dumps(result)


@pytest.mark.parametrize("unsafe_state", ["photon", "camera", "actuator"])
def test_e2e_audit_refuses_active_messaging_or_hardware_before_any_mutation(unsafe_state):
    from scripts.e2e_demo import audit

    requests = []
    readiness = {"photon": {"enabled": unsafe_state == "photon"},
                 "camera": {"running": unsafe_state == "camera"},
                 "hardware_actuation": unsafe_state == "actuator"}

    def respond(request):
        requests.append(request)
        assert request.method == "GET", "Unsafe preflight must never reach an API mutation"
        assert request.url.path in {"/api/v1/health", "/api/v1/status"}
        return httpx.Response(200, json={"status": "ok"} if request.url.path.endswith("health")
                              else readiness)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = audit("http://127.0.0.1:8000", "private-audit-test-token", client=client)
    assert result["summary"]["software_workflow_passed"] is False
    assert result["summary"]["FAIL"] > 0
    assert len(requests) == 2
    assert result["evidence"] == {}
    assert "private-audit-test-token" not in json.dumps(result)


@pytest.mark.parametrize("origin", ["https://127.0.0.1:8000", "http://example.com",
                                     "http://localhost:8000/?key=secret", "http://me:secret@localhost"])
def test_e2e_audit_cannot_send_operator_token_to_an_external_origin(origin):
    from scripts.e2e_demo import local_api

    with pytest.raises(ValueError, match="loopback"):
        local_api(origin)
