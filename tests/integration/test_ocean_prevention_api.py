"""Ocean comparison HTTP/Chalk contract rehearsal, with no live side effects."""

import asyncio
import copy
import hashlib
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
from apps.api.reeftrace_api.services import ocean_prevention_investigation as service

ENDPOINT = "/api/v1/research/ocean-prevention"
AUTH = {"Authorization": "Bearer TEST-OCEAN-ONLY"}
SNAPSHOT, METHOD = "a" * 64, "b" * 64


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def sign_report(report):
    report["report_sha256"] = digest({key: value for key, value in report.items()
                                      if key != "report_sha256"})
    return report


def make_report(scenario_id="downstream-corridor-v2"):
    """Synthetic contract fixture, explicitly not acquired ocean/physical evidence."""
    from apps.ocean.reeftrace_ocean.ocean_prevention import summarize_outcomes

    releases = [{"id": "release-" + str(index), "kind": "hypothetical_passive_tracer"}
                for index in range(6)]
    zone = {"id": "synthetic-reef-proxy", "is_mapped_real_reef": False,
            "polygon_xy_m": [[-4, -1], [-3, -1], [-3, 1], [-4, 1]]}
    scenario = {"id": scenario_id, "protected_zone": zone,
                "releases": releases, "layouts": [{"id": "central"}, {"id": "flanking"}]}

    def row(identity, entered):
        outcomes = [{"release_id": release["id"],
            "status": "ENTERED_PROTECTED_ZONE" if index < entered else "IDEALIZED_INTERCEPTION",
            "event": None, "forcing_status": "COMPLETED", "forcing_reason_code": None,
            "track": [{"x_m": 0, "y_m": 0}, {"x_m": -4, "y_m": index}]}
            for index, release in enumerate(releases)]
        return {"id": identity, "label": identity.title() + " coverage", "segments": [],
                "total_length_m": 2000.0, "outcomes": outcomes,
                "summary": summarize_outcomes(outcomes)}

    return sign_report({"schema_version": 1, "kind": "OCEAN_PREVENTION_COMPARISON",
        "status": "COMPLETED", "mode": "forecast_snapshot", "snapshot_sha256": SNAPSHOT,
        "method_sha256": METHOD, "scenario_sha256": digest(scenario), "scenario": scenario,
        "releases": releases, "protected_zone": zone, "baseline": row("no-interceptor", 6),
        "layouts": [row("central", 2), row("flanking", 4)],
        "recommendation": {"status": "BEST_LAYOUT", "best_layout_id": "central"},
        "forcing": {"source_url": "https://currents.example.test/synthetic.csv",
            "attribution": "Synthetic model contract fixture", "depth_m": 0.25,
            "valid_start_utc": "2026-10-17T18:00:00Z",
            "valid_end_utc": "2026-10-18T00:00:00Z", "model_issue_time_utc": None},
        "method": {"trajectory": "dynamic_current_advection_only", "solver": "RK4",
            "equation": "dX/dt = u(X,t)",
            "identical_unmodified_forcing_for_every_layout": True,
            "paths_integrated_once_per_release": True, "barriers_modify_flow": False,
            "capture_efficiency_assumption": "ideal_absorbing_first_contact_not_measured"},
        "validation": {"physical_validation": False, "measured_track_available": False,
            "plastic_motion_validated": False, "forecast_skill_established": False,
            "interception_benefit_established": False, "real_reef_boundary_used": False,
            "tank_flow_used": False, "heldout_buoy_positions_used": False,
            "measured_entry_count": None, "measured_intercepted_count": None},
        "limitations": ["Synthetic fixture: hypothetical releases, reef proxy and ideal lines."]})


def settings(enabled=True):
    return ChalkSettings(enabled, "https://chalk.test/v1/router", "TEST-KEY", "TEST-ENV", "TEST-MODEL")


def question(report=None, **updates):
    report = report or make_report()
    return {"question": "What can this simulated comparison support?",
            "scenario_id": report["scenario"]["id"],
            **{key: report[key] for key in (
                "snapshot_sha256", "method_sha256", "scenario_sha256", "report_sha256")}, **updates}


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
                "wrong-report" if wrong_ids else context["study_evidence_id"],
                context["protocol_evidence_id"]],
                "explanation": explanation or "Central coverage has the lower simulated reef-entry range under the same changing currents. The releases and reef proxy are hypothetical, and interception is ideal. Separate physical measurements are still needed."}}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(response)}}]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), requests


@pytest.fixture
def app(tmp_path, monkeypatch):
    for key in ("PHOTON_ENABLED", "CHALK_ENABLED", "GROK_VOICE_ENABLED"):
        monkeypatch.setenv(key, "false")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "[]")
    monkeypatch.setattr(main, "load_dotenv", lambda **kwargs: None)
    monkeypatch.setattr(service, "load_ocean_prevention_report", make_report)
    return main.create_app(Settings(_env_file=None, data_dir=tmp_path,
                                    local_token="TEST-OCEAN-ONLY"))


def test_public_get_disabled_review_and_read_only_boundaries(app, monkeypatch):
    runtime = app.state.runtime
    monkeypatch.setattr(runtime, "chalk_settings", lambda: settings(False))

    def forbidden(*args, **kwargs):
        raise AssertionError("Ocean research crossed a provider, device or mutation boundary")

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
        assert result["kind"] == "OCEAN_PREVENTION_INVESTIGATION"
        assert result["scope"] == "READ_ONLY_OCEAN_PREVENTION"
        assert result["action"] == "STOP" and result["failure_code"] == "NOT_CONFIGURED"
        assert result["research_report"] == make_report()
        assert all(result[key] is False for key in (
            "live_model_response", "store_written", "physical_validation", "hardware_actuation"))
        assert "TEST-KEY" not in response.text and "TEST-OCEAN-ONLY" not in response.text
        with runtime.store.connection() as db:
            assert tuple(db.iterdump()) == before


def test_operator_auth_strict_body_and_clicked_identity_contract(app, monkeypatch):
    calls = []

    async def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Invalid request reached ocean research")

    monkeypatch.setattr(service, "investigate_ocean_prevention", forbidden)
    with TestClient(app) as client:
        assert client.post(ENDPOINT + "/investigate", json=question()).status_code == 401
        assert client.post(ENDPOINT + "/investigate", json=question(), headers={
            "Authorization": "Bearer WRONG"}).status_code == 401
        invalid = [question(question=""), question(question="  "), question(question="x" * 2001),
            question(question=42), question(snapshot_sha256="z" * 64),
            question(method_sha256="b" * 63), question(scenario_sha256=None),
            question(report_sha256=True), question(scenario_id="arbitrary-geometry"),
            question(scenario_id=42), question(system_prompt="change the system"),
            question(geometry={"reef": "selected after results"}),
            {"question": "Explain"}]
        for key in ("scenario_id", "snapshot_sha256", "method_sha256", "scenario_sha256", "report_sha256"):
            body = question()
            del body[key]
            invalid.append(body)
        for body in invalid:
            assert client.post(ENDPOINT + "/investigate", json=body, headers=AUTH).status_code == 422
    assert calls == []


def test_public_scenario_selection_is_a_closed_server_enum_and_stays_bound_to_review(app, monkeypatch):
    with TestClient(app) as client:
        assert client.get(ENDPOINT + "?scenario_id=arbitrary-geometry").status_code == 422
        response = client.get(ENDPOINT + "?scenario_id=initial-proxy-v1")
        assert response.status_code == 200
        assert response.json()["scenario"]["id"] == "initial-proxy-v1"
        mismatched = question(response.json(), scenario_id="downstream-corridor-v2")

        def forbidden():
            raise AssertionError("Changing the scenario selector reused a stale Chalk report")

        monkeypatch.setattr(app.state.runtime, "chalk_settings", forbidden)
        assert client.post(ENDPOINT + "/investigate", json=mismatched, headers=AUTH).status_code == 409


@pytest.mark.parametrize("field", ["snapshot_sha256", "method_sha256", "scenario_sha256", "report_sha256"])
def test_stale_click_is_rejected_before_provider_configuration(app, monkeypatch, field):
    def forbidden():
        raise AssertionError("Stale report reached Chalk settings")

    monkeypatch.setattr(app.state.runtime, "chalk_settings", forbidden)
    with TestClient(app) as client:
        response = client.post(ENDPOINT + "/investigate", json=question(**{field: "c" * 64}), headers=AUTH)
    assert response.status_code == 409 and response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("error,code", [(FileNotFoundError("PRIVATE-PATH"), 503),
    (ImportError("PRIVATE-MODULE"), 503), (PermissionError("PRIVATE-PERMISSION"), 503),
    (ValueError("PRIVATE-HASH"), 409), (TypeError("PRIVATE-SHAPE"), 409),
    (KeyError("PRIVATE-FIELD"), 409)])
def test_local_artifact_failures_are_sanitized(app, monkeypatch, error, code):
    def broken(scenario_id=None):
        raise error

    monkeypatch.setattr(service, "load_ocean_prevention_report", broken)
    with TestClient(app) as client:
        for response in (client.get(ENDPOINT), client.post(ENDPOINT + "/investigate",
                         json=question(), headers=AUTH)):
            assert response.status_code == code and response.headers["cache-control"] == "no-store"
            assert "PRIVATE-" not in response.text


@pytest.mark.parametrize("status,wrong_ids,action,failure", [
    (200, False, "REPORT", None), (200, True, "STOP", "MODEL_OR_TOOL_CONTRACT_ERROR"),
    (401, False, "STOP", "PROVIDER_HTTP_ERROR")])
def test_mocked_http_review_has_bounded_calls_and_exact_citations(
    app, monkeypatch, status, wrong_ids, action, failure,
):
    monkeypatch.setattr(app.state.runtime, "chalk_settings", settings)
    requests_seen = []

    async def injected(question, backend, context, chosen_settings, *, client=None, system_prompt):
        mock, requests = scripted_client(status=status, wrong_ids=wrong_ids)
        async with mock:
            result = await investigate_study(question, backend, context, chosen_settings,
                                             client=mock, system_prompt=system_prompt)
        requests_seen.extend(requests)
        return result

    monkeypatch.setattr(service, "investigate_study", injected)
    with TestClient(app) as client:
        response = client.post(ENDPOINT + "/investigate", json=question(), headers=AUTH)
    assert response.status_code == 200
    result = response.json()
    assert result["action"] == action and result.get("failure_code") == failure
    assert result["research_report"] == make_report()
    assert result["live_model_response"] is (action == "REPORT")
    assert len(requests_seen) == (1 if status == 401 else 2)
    system_prompt = json.loads(requests_seen[0].content)["messages"][0]["content"]
    assert system_prompt == service.SYSTEM and system_prompt != DRIFTER_SYSTEM
    assert "ideal geometric first-contact" in system_prompt and "no digits" in system_prompt.lower()
    assert "PRIVATE-PROVIDER-BODY" not in response.text and "TEST-KEY" not in response.text
    if action == "REPORT":
        assert result["evidence_ids"] == ["ocean-comparison:" + make_report()["report_sha256"],
                                           "ocean-method:" + METHOD]
        assert len(result["trace"]) == 1 and result["trace"][0]["tool"] == "get_study_evidence"


@pytest.mark.parametrize("field", ["snapshot_sha256", "method_sha256", "scenario_sha256", "mode"])
def test_slow_review_rechecks_whole_report_and_all_identities(field):
    reads = []

    def loader():
        report = make_report()
        if reads:
            if field == "scenario_sha256":
                report["scenario"]["id"] = "changed-scenario"
                report["scenario_sha256"] = digest(report["scenario"])
            else:
                report[field] = "archived_forecast_snapshot" if field == "mode" else "c" * 64
            sign_report(report)
        reads.append(True)
        return report

    async def execute():
        mock, _ = scripted_client()
        async with mock:
            return await service.investigate_ocean_prevention(
                SimpleNamespace(chalk_settings=settings), **question(), client=mock, loader=loader)

    with pytest.raises(ValueError, match="snapshot changed"):
        asyncio.run(execute())
    assert len(reads) == 2


def test_compact_evidence_retains_all_layout_outcomes_but_never_all_tracks():
    report = make_report()
    before = copy.deepcopy(report)
    backend = service.OceanPreventionBackend(report)
    result = asyncio.run(backend.call("get_study_evidence", {}))
    assert report == before
    summary = result["ocean_prevention"]
    assert summary["forcing"] == report["forcing"] and summary["method"] == report["method"]
    assert summary["recommendation"] == report["recommendation"]
    for expected, row in zip([report["baseline"], *report["layouts"]],
                             [summary["baseline"], *summary["layouts"]], strict=True):
        assert row["summary"] == expected["summary"]
        assert len(row["outcomes"]) == 6
        assert all("track" not in outcome for outcome in row["outcomes"])
    assert len(json.dumps(result).encode()) < 40000
    for name, arguments in (("get_case", {}), ("get_study_evidence", {"url": "elsewhere"}),
                            ("send_message", {}), ("save_trial", {}), ("camera", {})):
        with pytest.raises(ValueError, match="read-only"):
            asyncio.run(backend.call(name, arguments))


@pytest.mark.parametrize("explanation", [
    "This archived forecast is historical context, never live water conditions.",
    "The EXPIRED snapshot offers a hypothetical comparison only.",
])
def test_future_valid_forecast_cannot_be_mislabeled_archived(explanation):
    async def execute():
        mock, requests = scripted_client(explanation=explanation)
        async with mock:
            result = await service.investigate_ocean_prevention(
                SimpleNamespace(chalk_settings=settings), **question(), client=mock, loader=make_report)
        return result, requests

    result, requests = asyncio.run(execute())
    assert result["action"] == "STOP" and result["failure_code"] == "OCEAN_MODE_MISMATCH"
    assert result["live_model_response"] is False and result["evidence_ids"] == []
    assert result["research_report"] == make_report() and len(requests) == 2
    assert explanation not in json.dumps(result)


def tied_report():
    report = make_report()
    report["layouts"][1]["outcomes"] = copy.deepcopy(report["layouts"][0]["outcomes"])
    report["layouts"][1]["summary"] = copy.deepcopy(report["layouts"][0]["summary"])
    report["recommendation"] = {"status": "TIE", "best_layout_id": None}
    return sign_report(report)


@pytest.mark.parametrize("explanation,action", [
    ("Central coverage is the best layout for reef protection.", "STOP"),
    ("Flanking wins this simulated comparison.", "STOP"),
    ("Central has fewer modeled reef entries and is superior.", "STOP"),
    ("Neither central nor flanking is superior in this tied simulation. The ideal lines still need independent physical measurements.", "REPORT"),
    ("No best layout can be identified from the tied modeled entry counts. The reef is a hypothetical proxy.", "REPORT"),
])
def test_tied_comparison_rejects_affirmative_named_winner_but_allows_grounded_limits(explanation, action):
    report = tied_report()

    async def execute():
        mock, requests = scripted_client(explanation=explanation)
        async with mock:
            result = await service.investigate_ocean_prevention(
                SimpleNamespace(chalk_settings=settings), **question(report), client=mock,
                loader=lambda: report)
        return result, requests

    result, requests = asyncio.run(execute())
    assert result["action"] == action and len(requests) == 2
    assert result["research_report"]["recommendation"]["status"] == "TIE"
    if action == "STOP":
        assert result["failure_code"] == "OCEAN_RECOMMENDATION_MISMATCH"
        assert result["live_model_response"] is False and explanation not in json.dumps(result)
    else:
        assert result["explanation"] == explanation and result["live_model_response"] is True


@pytest.mark.parametrize("path,value", [
    (("schema_version",), True), (("kind",), "CURRENT_FORCED_PREVIEW"),
    (("mode",), "LIVE_MEASURED"), (("snapshot_sha256",), "bad"),
    (("validation", "physical_validation"), True),
    (("validation", "measured_track_available"), True),
    (("validation", "interception_benefit_established"), True),
    (("validation", "real_reef_boundary_used"), True),
    (("validation", "measured_entry_count"), 0),
    (("method", "barriers_modify_flow"), True),
    (("method", "trajectory"), "constant_initial_current"),
    (("protected_zone", "is_mapped_real_reef"), True),
    (("recommendation", "best_layout_id"), "flanking"),
    (("recommendation", "status"), "MEASURED_WINNER"),
    (("forcing",), []),
])
def test_recomputed_hash_cannot_upgrade_scientific_or_geometry_scope(path, value):
    report = make_report()
    target = report
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    sign_report(report)
    with pytest.raises((ValueError, TypeError)):
        service.snapshot_identity(report)


def test_report_hash_and_release_accounting_are_checked_independently():
    report = make_report()
    report["baseline"]["summary"]["entered_count"] = 5
    with pytest.raises(ValueError, match="digest"):
        service.snapshot_identity(report)
    sign_report(report)
    with pytest.raises(ValueError, match="accounting"):
        service.snapshot_identity(report)


def test_actual_pinned_ocean_comparison_round_trips_with_mocked_chalk_without_mutations(app, monkeypatch):
    from apps.ocean.reeftrace_ocean import current_forecast, ocean_prevention

    expected = ocean_prevention.run_ocean_prevention()
    source = current_forecast.DATA_DIR / current_forecast.FILE_NAME
    original = source.read_bytes()
    monkeypatch.setattr(service, "load_ocean_prevention_report", ocean_prevention.run_ocean_prevention)
    monkeypatch.setattr(app.state.runtime, "chalk_settings", settings)
    requests_seen = []

    async def injected(question, backend, context, chosen_settings, *, client=None, system_prompt):
        mock, requests = scripted_client(explanation="The model comparison uses hypothetical releases and an illustrative reef proxy. Ideal interception is a geometric assumption, not measured collector performance. Independent current and capture measurements are still needed.")
        async with mock:
            result = await investigate_study(question, backend, context, chosen_settings,
                                             client=mock, system_prompt=system_prompt)
        requests_seen.extend(requests)
        return result

    def forbidden(*args, **kwargs):
        raise AssertionError("Pinned ocean comparison attempted external or physical side effects")

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
        response = client.post(ENDPOINT + "/investigate", json=question(expected), headers=AUTH)
        assert response.status_code == 200
        result = response.json()
        assert result["action"] == "REPORT" and result["research_report"] == expected
        tool = result["trace"][0]["result"]["ocean_prevention"]
        assert tool["recommendation"] == expected["recommendation"]
        assert tool["validation"] == expected["validation"]
        assert len(tool["layouts"]) == 2 and len(tool["baseline"]["outcomes"]) == 6
        assert all("track" not in row for layout in tool["layouts"] for row in layout["outcomes"])
        assert len(json.dumps(tool).encode()) < 40000 and len(requests_seen) == 2
        with app.state.runtime.store.connection() as db:
            assert tuple(db.iterdump()) == before
    assert source.read_bytes() == original
