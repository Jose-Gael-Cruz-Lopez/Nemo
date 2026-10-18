"""Offline service/API contract fixtures, never scientific acquisition or scoring.

The synthetic fixture exercises publication guards, not a scientific result. A
separate test reads real saved artifacts only when their publication anchor exists.
"""

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
from adapters.chalk.research import investigate_study
from apps.api.reeftrace_api import main
from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.services import ocean_source_investigation as service

ENDPOINT = "/api/v1/research/ocean-source"
AUTH = {"Authorization": "Bearer TEST-OCEAN-SOURCE-ONLY"}
DEFAULT_READER = service.load_ocean_source_result


def fake_snapshot(*, tutorial=False):
    """An explicitly invented complete interface fixture, not a generated score."""
    groups = []
    for identifier in service.GROUP_IDS:
        candidates = [{"model_id": model, "status": "COMPLETED", "reason_code": None,
            "earlier_time_utc": "2022-06-01T00:00:00Z", "latitude_deg": 30., "longitude_deg": -75.}
            for model in service.MODEL_IDS]
        scenarios = [{"scenario_id": f"test-scenario-{index}", "status": "COMPLETED",
            "reason_code": None, "completed_lookback_s": 21600., "track": [],
            "endpoint_offset_east_north_m": [0., 0.], "current_bias_east_north_m_s": [0., 0.],
            "solver": {"method": "SYNTHETIC_INTERFACE_FIXTURE"}}
            for index in range(25)]
        groups.append({"group_id": identifier,
            "observed_endpoint": {"time_utc": "2022-06-01T06:00:00Z",
                                  "latitude_deg": 30., "longitude_deg": -75.},
            "penultimate_observation": {"time_utc": "2022-06-01T05:00:00Z",
                                       "latitude_deg": 30., "longitude_deg": -75.},
            "candidates": candidates, "reverse_current": {"nominal_scenario_id": "center|zero",
                "scenarios": scenarios, "coverage": {"planned_scenarios": 25,
                    "completed_scenarios": 25, "partial_scenarios": 0, "unsupported_scenarios": 0},
                "earlier_candidates": [{"lookback_hours": hour, "planned_scenarios": 25,
                    "available_count": 25, "points": []} for hour in [1, 3, 6]]},
            "numerical_closure": {"status": "COMPLETED", "reason_code": None,
                "endpoint_distance_m": 0., "forward_track": []}})
    forecasts = {"schema_version": 1, "kind": "OCEAN_SOURCE_BACKTRACKING_FORECASTS",
        "study_id": service.STUDY_ID, "analysis_scope": service.ANALYSIS_SCOPE,
        "group_ids": list(service.GROUP_IDS), "model_ids": list(service.MODEL_IDS),
        "planned_model_rows": 6, "planned_distinct_earlier_positions": 2,
        "earlier_truth_used": False, "inference_uses_only_last_two_positions": True,
        "scenarios_per_group": 25, "groups": groups}
    report = {"schema_version": 1, "kind": "OCEAN_SOURCE_EXPLORATORY_RESULT",
        "study_id": service.STUDY_ID, "protocol_sha256": "b" * 64, "forecast_file_sha256": "c" * 64,
        "analysis_scope": service.ANALYSIS_SCOPE, "previously_viewed_earlier_positions": True,
        "forecasts_saved_before_earlier_truth_decode": True,
        "new_data_acquisition": False, "provider_calls": False, "physical_validation": False,
        "source_attribution_validated": False, "automatic_model_promotion": False,
        "forecasts": forecasts, "validation": {"kind": "OCEAN_SOURCE_EARLIER_POSITION_VALIDATION",
            "analysis_scope": service.ANALYSIS_SCOPE, "previously_viewed_earlier_positions": True,
            "planned_model_rows": 6,
            "planned_distinct_earlier_positions": 2, "scored_model_rows": 6,
            "primary_complete": True, "primary_mean_earlier_position_error_m": None,
            "rows": []}, "limitations": ["Synthetic API fixture; not a measured result."]}
    if tutorial:
        tutorial_groups = []
        for identifier in service.GROUP_IDS:
            raw = [{"time_utc": f"2022-06-01T0{hour}:00:00Z", "latitude_deg": 30.,
                    "longitude_deg": -75.} for hour in [1, 2, 3]]
            filtered = [{**point, "east_m": 0., "north_m": 0., "eastward_m_s": 0.,
                         "northward_m_s": 0., "status": status, "covariance": [[1., 0.], [0., 1.]]}
                        for point, status in zip(raw, ["POSITION_ONLY", "INITIALIZED", "UPDATED"], strict=True)]
            branch = {"status": "COMPLETED", "reason_code": None, "track": raw,
                      "completed_horizon_s": 10800.}
            tutorial_groups.append({"group_id": identifier, "status": "COMPLETED", "reason_code": None,
                "raw_observations": raw, "connected_path": raw, "filtered_states": filtered,
                "filtered_anchor": raw[-1], "formula": {"equation": "SYNTHETIC_INTERFACE_FIXTURE"},
                "backward": {**branch, "completed_lookback_s": 10800.}, "forward": branch})
        tutorial_forecasts = {"kind": "THREE_FIX_BIDIRECTIONAL_FORECASTS", "group_ids": list(service.GROUP_IDS),
            "observation_times_utc": [f"2022-06-01T0{hour}:00:00Z" for hour in [1, 2, 3]],
            "anchor_time_utc": "2022-06-01T03:00:00Z", "earlier_truth_used": False,
            "later_truth_used": False, "position_std_m": 100.,
            "acceleration_spectral_density_m2_s3": 1e-6,
            "analysis_scope": service.ANALYSIS_SCOPE, "previously_viewed_validation_positions": True,
            "physical_validation": False, "source_attribution_validated": False,
            "stages": [{"id": stage, "title": stage, "formula": "SYNTHETIC_INTERFACE_FIXTURE"}
                       for stage in service.TUTORIAL_STAGES],
            "groups": tutorial_groups, "limitations": ["Synthetic tutorial interface fixture."]}
        report["forecasts"]["pipeline_tutorial"] = copy.deepcopy(tutorial_forecasts)
        report["pipeline_tutorial"] = {"kind": "THREE_FIX_BIDIRECTIONAL_RESEARCH_WALKTHROUGH",
            "forecasts": tutorial_forecasts, "validation": {"kind": "THREE_FIX_BIDIRECTIONAL_VALIDATION",
                "planned_rows": 8, "scored_rows": 0,
                "rows": [{"group_id": identifier, "time_utc": time, "status": "FORECAST_UNAVAILABLE",
                          "direction": "backward" if time == service.TUTORIAL_VALIDATION_TIMES[0] else "forward"}
                         for identifier in service.GROUP_IDS for time in service.TUTORIAL_VALIDATION_TIMES],
                "analysis_scope": service.ANALYSIS_SCOPE, "previously_viewed_validation_positions": True,
                "physical_validation": False, "statistical_independence": False,
                "source_attribution_validated": False}}
        report["pipeline_saved_before_any05_06_position_decode"] = True
        report["all_tutorial_forecasts_saved_before_validation_truth_decode"] = True
    pins = SimpleNamespace(STUDY_ID=service.STUDY_ID, PROTOCOL_SHA256="b" * 64,
        REPORT_SHA256=service._report_file_digest(report), FORECAST_SHA256="c" * 64,
        IDENTITY_SHA256="d" * 64)
    identity = {"schema_version": 1, "kind": "OCEAN_SOURCE_RESULT_IDENTITY",
        "study_id": service.STUDY_ID, "protocol_sha256": pins.PROTOCOL_SHA256,
        "report_sha256": pins.REPORT_SHA256, "forecast_file_sha256": pins.FORECAST_SHA256,
        "identity_sha256": pins.IDENTITY_SHA256, "integrity_verified": True,
        "external_result_pin_verified": True, "numeric_replay_verified": False,
        "verification_scope": service.VERIFICATION_SCOPE,
        "externally_trusted_pin_required_for_publication": True}
    return {"report": report, "artifact_identity": identity}, pins


@pytest.fixture
def saved(monkeypatch):
    snapshot, pins = fake_snapshot()
    monkeypatch.setattr(service, "_pins", lambda: pins)
    return snapshot, pins


@pytest.fixture
def app(tmp_path, monkeypatch, saved):
    monkeypatch.setattr(main, "load_dotenv", lambda **kwargs: None)
    monkeypatch.setattr(service, "load_ocean_source_result", lambda: copy.deepcopy(saved[0]))
    application = main.create_app(Settings(_env_file=None, data_dir=tmp_path,
                                         local_token="TEST-OCEAN-SOURCE-ONLY"))
    assert ENDPOINT in application.openapi()["paths"]
    return application


def question(pins, **changes):
    return {"question": "What is conditional about this earlier-position result?",
            "report_sha256": pins.REPORT_SHA256, "protocol_sha256": pins.PROTOCOL_SHA256,
            "identity_sha256": pins.IDENTITY_SHA256, **changes}


def settings(enabled=True):
    return ChalkSettings(enabled, "https://chalk.test/v1/router", "TEST-OCEAN-SOURCE-KEY",
                         "TEST-ENV", "TEST-MODEL")


def mock_provider(*, status=200, wrong_ids=False, missing_id=False, unsafe=False,
                  repeat=False, premature=False, explanation=None, action="REPORT", delay=0):
    requests = []

    async def handler(request):
        requests.append(request)
        if delay:
            await asyncio.sleep(delay)
        if status != 200:
            return httpx.Response(status, content=b"PRIVATE-PROVIDER TEST-OCEAN-SOURCE-KEY")
        payload = json.loads(request.content)
        context = json.loads(payload["messages"][1]["content"])["trusted_context"]
        ids = [context["study_evidence_id"], context["protocol_evidence_id"]]
        if wrong_ids:
            ids[0] = "origin-residual-report:" + "a" * 64
        if missing_id:
            ids.pop()
        if unsafe:
            command = {"tool": "send_message", "arguments": {}}
        elif (len(requests) == 1 and not premature) or repeat:
            command = {"tool": "get_study_evidence", "arguments": {}}
        else:
            command = {"tool": "finish", "arguments": {"action": action,
                "evidence_ids": ids, "explanation": explanation or (
                    "These are conditional earlier buoy positions under stated current assumptions. "
                    "The sensitivity cases are not calibrated source probabilities, and closure is "
                    "numerical consistency rather than physical validation. "
                    "An independent known-release experiment is still needed.")}}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(command)}}]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), requests


def test_get_and_disabled_review_are_read_only_no_devices_network_or_scoring(app, saved, monkeypatch):
    snapshot, pins = saved
    runtime = app.state.runtime
    monkeypatch.setattr(runtime, "chalk_settings", lambda: settings(False))

    def forbidden(*args, **kwargs):
        raise AssertionError("Read-only research crossed a provider/store/device boundary")

    with TestClient(app) as client:
        with runtime.store.connection() as db:
            before = tuple(db.iterdump())
        for method in ("put", "put_case_result", "add_case", "update_case", "propose", "transition_action"):
            monkeypatch.setattr(runtime.store, method, forbidden)
        monkeypatch.setattr(cv2, "VideoCapture", forbidden)
        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
        response = client.get(ENDPOINT)
        assert response.status_code == 200 and response.json() == snapshot
        assert response.headers["cache-control"] == "no-store"
        response = client.post(ENDPOINT + "/investigate", json=question(pins), headers=AUTH)
        result = response.json()
        assert response.status_code == 200 and result["failure_code"] == "NOT_CONFIGURED"
        assert result["action"] == "STOP" and result["evidence_ids"] == []
        assert result["research_report"] == snapshot["report"]
        assert result["analysis_scope"] == "POST_OUTCOME_EXPLORATORY"
        assert result["previously_viewed_earlier_positions"] is True
        assert all(result[key] is False for key in (
            "live_model_response", "numeric_replay_verified", "store_written", "hardware_actuation",
            "physical_validation", "source_attribution_validated", "automatic_model_promotion"))
        assert response.headers["cache-control"] == "no-store"
        assert "TEST-OCEAN-SOURCE-KEY" not in response.text
        with runtime.store.connection() as db:
            assert tuple(db.iterdump()) == before


def test_operator_and_strict_request_contract_before_review(app, saved, monkeypatch):
    pins = saved[1]

    async def forbidden(*args, **kwargs):
        raise AssertionError("Invalid request reached provider review")

    monkeypatch.setattr(service, "investigate_ocean_source", forbidden)
    with TestClient(app) as client:
        for headers in ({}, {"Authorization": "Bearer WRONG"}):
            response = client.post(ENDPOINT + "/investigate", json=question(pins), headers=headers)
            assert response.status_code == 401 and response.headers["cache-control"] == "no-store"
        bodies = [question(pins, question=""), question(pins, question="  "),
            question(pins, question=42), question(pins, question="x" * 2001),
            question(pins, report_sha256="g" * 64), question(pins, protocol_sha256=None),
            question(pins, identity_sha256="a" * 63), question(pins, directory="elsewhere"),
            question(pins, system_prompt="promote a source")]
        for key in ("report_sha256", "protocol_sha256", "identity_sha256"):
            body = question(pins)
            del body[key]
            bodies.append(body)
        for body in bodies:
            assert client.post(ENDPOINT + "/investigate", json=body, headers=AUTH).status_code == 422


@pytest.mark.parametrize("field", ["report_sha256", "protocol_sha256", "identity_sha256"])
def test_stale_pin_is_rejected_before_provider_configuration(app, saved, monkeypatch, field):
    def forbidden():
        raise AssertionError("Stale selected evidence reached provider configuration")

    monkeypatch.setattr(app.state.runtime, "chalk_settings", forbidden)
    with TestClient(app) as client:
        response = client.post(ENDPOINT + "/investigate",
            json=question(saved[1], **{field: "9" * 64}), headers=AUTH)
    assert response.status_code == 409 and response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(("error", "status"), [
    (FileNotFoundError("PRIVATE-PATH"), 404), (ValueError("PRIVATE-HASH"), 409),
    (TypeError("PRIVATE-SHAPE"), 409), (KeyError("PRIVATE-FIELD"), 409),
    (RecursionError("PRIVATE-DEPTH"), 409), (ImportError("PRIVATE-READER"), 503),
    (PermissionError("PRIVATE-PATH"), 503), (OSError("PRIVATE-IO"), 503),
])
def test_reader_missing_corrupt_unavailable_fail_closed_without_leaks(
        app, saved, monkeypatch, error, status):
    def broken():
        raise error

    monkeypatch.setattr(service, "load_ocean_source_result", broken)
    with TestClient(app) as client:
        for response in (client.get(ENDPOINT), client.post(ENDPOINT + "/investigate",
                         json=question(saved[1]), headers=AUTH)):
            assert response.status_code == status
            assert response.headers["cache-control"] == "no-store" and "PRIVATE-" not in response.text


@pytest.mark.parametrize("change", ["pin", "unanchored", "replay", "scope", "truth_used",
    "origin_leak", "count", "group", "candidate", "nonfinite", "physical"])
def test_corrupt_snapshot_never_reaches_provider(app, saved, monkeypatch, change):
    snapshot = copy.deepcopy(saved[0])
    report, identity = snapshot["report"], snapshot["artifact_identity"]
    if change == "pin":
        identity["identity_sha256"] = "9" * 64
    elif change == "unanchored":
        identity["external_result_pin_verified"] = False
    elif change == "replay":
        identity["numeric_replay_verified"] = True
    elif change == "scope":
        report["analysis_scope"] = "CONFIRMATORY"
    elif change == "truth_used":
        report["forecasts"]["earlier_truth_used"] = True
    elif change == "origin_leak":
        report["forecasts"]["inference_uses_only_last_two_positions"] = False
    elif change == "count":
        report["forecasts"]["scenarios_per_group"] = 24
    elif change == "group":
        report["forecasts"]["groups"][0]["group_id"] = "elsewhere"
    elif change == "candidate":
        report["forecasts"]["groups"][0]["candidates"][2]["model_id"] = "origin_residual_current"
    elif change == "nonfinite":
        report["validation"]["test_nonfinite"] = float("nan")
    else:
        report["physical_validation"] = True
    monkeypatch.setattr(service, "load_ocean_source_result", lambda: snapshot)

    def forbidden():
        raise AssertionError("Corrupt result reached provider configuration")

    monkeypatch.setattr(app.state.runtime, "chalk_settings", forbidden)
    with TestClient(app) as client:
        assert client.get(ENDPOINT).status_code == 409
        assert client.post(ENDPOINT + "/investigate", json=question(saved[1]), headers=AUTH).status_code == 409


@pytest.mark.parametrize(("options", "action", "failure", "calls"), [
    ({}, "REPORT", None, 2), ({"premature": True}, "REPORT", None, 2),
    ({"action": "STOP"}, "STOP", None, 2),
    ({"wrong_ids": True}, "STOP", "MODEL_OR_TOOL_CONTRACT_ERROR", 2),
    ({"missing_id": True}, "STOP", "MODEL_OR_TOOL_CONTRACT_ERROR", 2),
    ({"unsafe": True}, "STOP", "MODEL_OR_TOOL_CONTRACT_ERROR", 1),
    ({"repeat": True}, "STOP", "MODEL_OR_TOOL_CONTRACT_ERROR", 2),
    ({"explanation": "Source confidence is 90 percent."}, "STOP", "MODEL_OR_TOOL_CONTRACT_ERROR", 2),
    ({"status": 401}, "STOP", "PROVIDER_HTTP_ERROR", 1),
])
def test_mock_provider_scoped_citations_tools_calls_and_prose(
        app, saved, monkeypatch, options, action, failure, calls):
    seen = []
    monkeypatch.setattr(app.state.runtime, "chalk_settings", settings)

    async def injected(question, backend, context, configuration, *, client=None, system_prompt):
        mock, requests = mock_provider(**options)
        async with mock:
            result = await investigate_study(question, backend, context, configuration,
                                             client=mock, system_prompt=system_prompt)
        seen.extend(requests)
        return result

    monkeypatch.setattr(service, "investigate_study", injected)
    with TestClient(app) as client:
        response = client.post(ENDPOINT + "/investigate", json=question(saved[1]), headers=AUTH)
    result = response.json()
    assert response.status_code == 200 and result["action"] == action
    assert result.get("failure_code") == failure and len(seen) == calls
    assert result["live_model_response"] is (failure is None)
    assert result["research_report"] == saved[0]["report"]
    assert result["kind"] == "OCEAN_SOURCE_RESEARCH_INVESTIGATION"
    assert result["scope"] == "READ_ONLY_POST_OUTCOME_EARLIER_POSITION_DIAGNOSTIC"
    assert "PRIVATE-PROVIDER" not in response.text and "TEST-OCEAN-SOURCE-KEY" not in response.text
    assert json.loads(seen[0].content)["messages"][0]["content"] == service.SYSTEM
    if failure is None:
        assert result["evidence_ids"] == ["ocean-source-report:" + saved[1].REPORT_SHA256,
                                         "ocean-source-protocol:" + saved[1].PROTOCOL_SHA256]
        assert len(result["trace"]) == 1
        evidence = result["trace"][0]["result"]["ocean_source_diagnostic"]
        assert evidence["inference"]["earlier_truth_used"] is False
        assert evidence["inference"]["scenarios_per_group"] == 25
        assert evidence["separate_retrospective_validation"] == saved[0]["report"]["validation"]
        assert all(value is False for value in evidence["scientific_flags"].values())


@pytest.mark.parametrize("change", ["report", "reader_metadata", "missing"])
def test_snapshot_recheck_after_provider_rejects_generation_changes(saved, change):
    snapshot, pins = saved
    newer = copy.deepcopy(snapshot)
    if change == "report":
        newer["report"]["validation"]["scored_model_rows"] = 5
    else:
        newer["artifact_identity"]["reader_extra_metadata"] = "new generation"
    reads = []

    def loader():
        reads.append(True)
        if len(reads) == 2 and change == "missing":
            raise FileNotFoundError("Artifact disappeared during review")
        return snapshot if len(reads) == 1 else newer

    async def execute():
        mock, requests = mock_provider()
        async with mock:
            with pytest.raises((ValueError, FileNotFoundError)):
                await service.investigate_ocean_source(SimpleNamespace(chalk_settings=settings),
                    "Explain", report_sha256=pins.REPORT_SHA256, protocol_sha256=pins.PROTOCOL_SHA256,
                    identity_sha256=pins.IDENTITY_SHA256, client=mock, loader=loader)
        return requests

    assert len(asyncio.run(execute())) == len(reads) == 2


def test_backend_has_no_actions_and_returns_defensive_compact_copies(saved):
    snapshot, _ = saved
    backend = service.OceanSourceBackend(snapshot)
    result = asyncio.run(backend.call("get_study_evidence", {}))
    assert len(json.dumps(result).encode()) <= 40000
    result["ocean_source_diagnostic"]["inference"]["groups"].clear()
    snapshot["report"]["forecasts"]["groups"].clear()
    again = asyncio.run(backend.call("get_study_evidence", {}))
    assert len(again["ocean_source_diagnostic"]["inference"]["groups"]) == 2
    for name, arguments in (("send_message", {}), ("first_score", {}), ("get_case", {}),
                           ("get_study_evidence", []), ("get_study_evidence", {"directory": "elsewhere"})):
        with pytest.raises(ValueError, match="read-only"):
            asyncio.run(backend.call(name, arguments))
    for group in again["ocean_source_diagnostic"]["inference"]["groups"]:
        assert all("track" not in scenario for scenario in group["reverse_current"]["scenarios"])
        assert all("points" not in row for row in group["reverse_current"]["earlier_candidates"])
        assert "forward_track" not in group["numerical_closure"]


def test_tutorial_compact_evidence_retains_stages_filtered_state_and_separate_validation(monkeypatch):
    snapshot, pins = fake_snapshot(tutorial=True)
    monkeypatch.setattr(service, "_pins", lambda: pins)
    result = service.compact_evidence(snapshot)["ocean_source_diagnostic"]
    assert "pipeline_tutorial" not in result["inference"]
    tutorial = result["pipeline_tutorial"]
    assert tutorial["kind"] == "THREE_FIX_BIDIRECTIONAL_RESEARCH_WALKTHROUGH"
    assert tutorial["inference"]["stages"] == snapshot["report"]["pipeline_tutorial"]["forecasts"]["stages"]
    assert tutorial["inference"]["earlier_truth_used"] is False
    assert tutorial["inference"]["later_truth_used"] is False
    assert tutorial["separate_retrospective_validation"] == snapshot["report"]["pipeline_tutorial"]["validation"]
    for group in tutorial["inference"]["groups"]:
        assert len(group["raw_observations"]) == len(group["filtered_states"]) == 3
        assert all("covariance" not in state for state in group["filtered_states"])
        assert "connected_path" not in group
        assert all("track" not in group[direction] for direction in ("backward", "forward"))
        assert all(group[direction]["status"] == "COMPLETED" for direction in ("backward", "forward"))
    assert len(json.dumps(result).encode()) <= 40000


@pytest.mark.parametrize("change", ["stage", "time", "future_used", "assumptions", "missing_group",
    "raw_count", "causal_state", "branch", "denominator", "validation_id", "source_validated"])
def test_tutorial_contract_rejects_relabelled_or_dropped_parts_even_with_a_matching_report_digest(
        monkeypatch, change):
    snapshot, pins = fake_snapshot(tutorial=True)
    report = snapshot["report"]
    inference, validation = report["pipeline_tutorial"]["forecasts"], report["pipeline_tutorial"]["validation"]
    if change == "stage":
        inference["stages"][0]["id"] = "learned_origin"
    elif change == "time":
        inference["anchor_time_utc"] = "2022-06-01T06:00:00Z"
    elif change == "future_used":
        inference["later_truth_used"] = True
    elif change == "assumptions":
        inference["position_std_m"] = 1.
    elif change == "missing_group":
        inference["groups"].pop()
    elif change == "raw_count":
        inference["groups"][0]["raw_observations"].pop()
    elif change == "causal_state":
        inference["groups"][0]["filtered_states"][0]["status"] = "SMOOTHED_FROM_FUTURE"
    elif change == "branch":
        del inference["groups"][0]["forward"]
    elif change == "denominator":
        validation["planned_rows"] = 7
        validation["rows"].pop()
    elif change == "validation_id":
        validation["rows"][0]["group_id"] = "different"
    else:
        validation["source_attribution_validated"] = True
    report["forecasts"]["pipeline_tutorial"] = copy.deepcopy(inference)
    pins.REPORT_SHA256 = service._report_file_digest(report)
    snapshot["artifact_identity"]["report_sha256"] = pins.REPORT_SHA256
    monkeypatch.setattr(service, "_pins", lambda: pins)
    with pytest.raises(ValueError, match="tutorial"):
        service.snapshot_identity(snapshot)


def test_timeout_is_bounded_without_retry(saved):
    snapshot, pins = saved
    configuration = ChalkSettings(True, "https://chalk.test/v1/router", "TEST", "ENV", "MODEL", .03, .02)

    async def execute():
        mock, requests = mock_provider(delay=.08)
        async with mock:
            result = await service.investigate_ocean_source(
                SimpleNamespace(chalk_settings=lambda: configuration), "Explain",
                report_sha256=pins.REPORT_SHA256, protocol_sha256=pins.PROTOCOL_SHA256,
                identity_sha256=pins.IDENTITY_SHA256, client=mock, loader=lambda: copy.deepcopy(snapshot))
        return result, requests

    result, requests = asyncio.run(execute())
    assert result["failure_code"] == "TIMEOUT" and len(requests) == 1
    assert result["research_report"] == snapshot["report"]


def test_missing_publication_anchor_is_unavailable_and_accepts_no_override(monkeypatch):
    def absent(name):
        assert name == service.PIN_MODULE
        raise ModuleNotFoundError("No published anchor", name=name)

    monkeypatch.setattr(service.importlib, "import_module", absent)
    with pytest.raises(FileNotFoundError):
        DEFAULT_READER()
    with pytest.raises(TypeError):
        DEFAULT_READER(expected_identity_sha256="a" * 64)


def test_actual_saved_publication_is_read_only_when_available(monkeypatch):
    try:
        service._pins()
    except FileNotFoundError:
        pytest.skip("Scientific result has not been scored and externally published yet")
    from scripts import evaluate_ocean_source as artifact

    def forbidden(*args, **kwargs):
        raise AssertionError("Saved publication read attempted scientific execution or network")

    for name in ("build_ocean_source_forecasts", "score_ocean_source_forecasts"):
        from apps.ocean.reeftrace_ocean import ocean_source
        monkeypatch.setattr(ocean_source, name, forbidden)
    from apps.ocean.reeftrace_ocean import ocean_source_pipeline
    for name in ("build_pipeline_forecasts", "score_pipeline_forecasts", "filter_three_positions",
                 "corrected_current_field", "backtrack_current"):
        monkeypatch.setattr(ocean_source_pipeline, name, forbidden)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
    paths = [path for path in artifact.DIRECTORY.rglob("*") if path.is_file()]
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    snapshot = DEFAULT_READER()
    assert service.snapshot_identity(snapshot)
    assert len(json.dumps(service.compact_evidence(snapshot)).encode()) <= 40000
    assert before == {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
