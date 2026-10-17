"""Synthetic contract rehearsal for a public study and read-only Chalk review.

These fixtures contain no NOAA trajectories, and no physical or acquisition
result is created by these tests. Actual pinned-study replay is tested separately.
"""

import asyncio
import copy
import json
import shutil
from types import SimpleNamespace

import cv2
import httpx
import pytest
from fastapi.testclient import TestClient

from adapters.chalk.agent import ChalkSettings
from adapters.chalk.research import investigate_study
from apps.api.reeftrace_api import main
from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.services import research_investigation as service

ENDPOINT = "/api/v1/research/fresh-physics"
AUTH = {"Authorization": "Bearer TEST-RESEARCH-ONLY"}


def make_report():
    """Synthetic pending-state envelope, with no invented measured positions."""
    identifiers = ("stationary", "last_drift", "mean_drift", "ridge_ar1", "kalman_cv")
    return {"schema_version": 1, "kind": "FRESH_NOAA_DRIFTER_STUDY",
        "study_id": "SYNTHETIC-CONTRACT-REHEARSAL-ONLY", "status": "NOT_ACQUIRED",
        "design_status": "FROZEN_NEW_GDP_ID_GROUP_EVALUATION_WITH_KNOWN_ALIAS_EXCLUSIONS",
        "protocol_sha256": "b" * 64,
        "protocol": {"pre_outcome_amendment": {"parent_model_outcomes": 0,
            "reason": ["Synthetic parser/transport amendment rehearsal only."]}},
        "coverage": {"target_groups": 6, "selected_groups": 0, "downloaded_groups": 0,
            "scored_groups": 0, "models": 5, "horizons": 6, "planned_outcomes": 180,
            "attempted_outcomes": 0, "scored_outcomes": 0, "failed_outcomes": 0,
            "unfilled_outcomes": 180, "unique_observed_intervals": 0,
            "common_target_cohort_complete": False},
        "groups": [{"block_id": "synthetic-pending", "slot": slot, "drifter_id": None,
                    "wmo": None, "status": "NOT_ACQUIRED", "reason_codes": ["NOT_ACQUIRED"],
                    "training_track": [], "heldout_track": [], "models": []}
                   for slot in range(1, 7)],
        "models": [{"id": identifier, "label": identifier, "metrics": None,
                    "reason_codes": ["INCOMPLETE_TARGET_COHORT"]} for identifier in identifiers],
        "provenance": {"integrity_verified": True, "hashes": {"protocol_sha256": "b" * 64},
                       "source_receipts": []},
        "flags": {"new_acquisition": False, "physical_validation": False,
            "calibrated_probability": False, "automatic_model_promotion": False,
            "provider_calls": False, "camera_started": False, "store_written": False,
            "operational_causality": False, "statistical_independence": False},
        "limitations": ["Synthetic pending envelope for boundary tests; not acquisition evidence."]}


def scripted_client(*, premature_stop=False):
    requests = []
    async def handler(request):
        requests.append(request)
        payload = json.loads(request.content)
        context = json.loads(payload["messages"][1]["content"])["trusted_context"]
        response = ({"tool": "finish", "arguments": {"action": "STOP", "evidence_ids": [],
            "explanation": "The study evidence tool is unavailable."}} if premature_stop else
            {"tool": "get_study_evidence", "arguments": {}}) if len(requests) == 1 else {
            "tool": "finish", "arguments": {"action": "REPORT", "evidence_ids": [
                context["study_evidence_id"], context["protocol_evidence_id"]],
                "explanation": "The available drifter study remains conditional on its frozen design and stated data limits."}}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(response)}}]})
    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), requests


def settings(enabled=True):
    return ChalkSettings(enabled, "https://chalk.test/v1/router", "TEST-KEY", "TEST-ENV", "TEST-MODEL")


def test_pending_study_can_be_explained_with_exact_hashes_without_acquisition_or_store():
    report = make_report()
    before = copy.deepcopy(report)
    reads = []
    def loader():
        reads.append(True)
        return report
    async def execute():
        client, requests = scripted_client()
        async with client:
            result = await service.investigate_fresh_physics(
                SimpleNamespace(chalk_settings=settings), "What is ready?", client=client, loader=loader)
        assert len(requests) == 2
        return result
    result = asyncio.run(execute())
    report_hash, protocol_hash = service.snapshot_identity(report)
    assert result["action"] == "REPORT" and result["live_model_response"] is True
    assert result["snapshot_report_sha256"] == report_hash
    assert result["evidence_ids"] == ["fresh-study:" + report_hash, "fresh-protocol:" + protocol_hash]
    assert result["research_report"] == report == before
    assert result["store_written"] is False and result["hardware_actuation"] is False
    assert len(reads) == 2
    tool_study = result["trace"][0]["result"]["study"]
    assert tool_study["coverage"] == report["coverage"]
    assert tool_study["provenance"] == report["provenance"]
    assert tool_study["pre_outcome_amendment"] == report["protocol"]["pre_outcome_amendment"]
    assert all(row["metrics"] is None for row in tool_study["models"])
    assert "training_track" not in json.dumps(tool_study)


def test_canonical_snapshot_is_order_stable_but_preserves_numeric_and_identity_changes():
    report = make_report()
    reordered = {key: report[key] for key in reversed(report)}
    assert service.snapshot_identity(report) == service.snapshot_identity(reordered)
    changed = copy.deepcopy(report)
    changed["coverage"]["planned_outcomes"] = 180.0
    assert service.snapshot_identity(report) != service.snapshot_identity(changed)
    changed["study_id"] = "different"
    assert service.snapshot_identity(report) != service.snapshot_identity(changed)


def test_disabled_chalk_preserves_the_report_and_never_opens_http(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Disabled research must not open a model client")
    monkeypatch.setattr(httpx, "AsyncClient", forbidden)
    result = asyncio.run(service.investigate_fresh_physics(
        SimpleNamespace(chalk_settings=lambda: settings(False)), "Explain", loader=make_report))
    assert result["action"] == "STOP" and result["failure_code"] == "NOT_CONFIGURED"
    assert result["research_report"] == make_report()


def test_changed_snapshot_during_provider_turn_is_not_committed_or_returned():
    count = []
    def loader():
        report = make_report()
        if count:
            report["coverage"]["selected_groups"] = 1
        count.append(True)
        return report
    async def execute():
        client, _ = scripted_client()
        async with client:
            return await service.investigate_fresh_physics(
                SimpleNamespace(chalk_settings=settings), "Explain", client=client, loader=loader)
    with pytest.raises(ValueError, match="snapshot changed"):
        asyncio.run(execute())


@pytest.mark.parametrize("field,value", [
    ("kind", "CASE_SOURCE_REPORT"), ("design_status", "UNFROZEN"),
    ("protocol_sha256", "not-a-sha"), ("status", "PROMOTED"),
    ("groups", None), ("protocol", None),
])
def test_unsupported_identity_or_structure_is_rejected_before_the_gateway(field, value):
    report = make_report()
    report[field] = value
    with pytest.raises((ValueError, TypeError)):
        service.snapshot_identity(report)


@pytest.mark.parametrize("flag", ["physical_validation", "calibrated_probability",
                                 "automatic_model_promotion", "statistical_independence"])
def test_research_cannot_promote_scientific_claims(flag):
    report = make_report()
    report["flags"][flag] = True
    with pytest.raises(ValueError, match="boundaries"):
        service.snapshot_identity(report)


def test_provenance_mismatch_nonfinite_or_oversized_snapshot_fail_closed():
    report = make_report()
    report["provenance"]["hashes"]["protocol_sha256"] = "c" * 64
    with pytest.raises(ValueError, match="provenance"):
        service.snapshot_identity(report)
    report = make_report()
    report["coverage"]["scored_outcomes"] = float("nan")
    with pytest.raises(ValueError):
        service.snapshot_identity(report)
    report = make_report()
    report["limitations"] = ["x" * 1_000_001]
    with pytest.raises(ValueError, match="byte budget"):
        service.snapshot_identity(report)


@pytest.fixture
def app(tmp_path, monkeypatch):
    for key in ("PHOTON_ENABLED", "CHALK_ENABLED", "GROK_VOICE_ENABLED"):
        monkeypatch.setenv(key, "false")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "[]")
    monkeypatch.setattr(main, "load_dotenv", lambda **kwargs: None)
    monkeypatch.setattr(service, "load_fresh_physics_report", make_report)
    return main.create_app(Settings(_env_file=None, data_dir=tmp_path, local_token="TEST-RESEARCH-ONLY"))


def test_public_get_and_unconfigured_post_are_read_only_and_keep_report(app, monkeypatch):
    runtime = app.state.runtime
    monkeypatch.setattr(runtime, "chalk_settings", lambda: settings(False))
    def forbidden(*args, **kwargs):
        raise AssertionError("Research crossed a read-only/provider boundary")
    with TestClient(app) as client:
        with runtime.store.connection() as db:
            before = tuple(db.iterdump())
        for method in ("put", "put_case_result", "add_case", "update_case", "propose", "transition_action"):
            monkeypatch.setattr(runtime.store, method, forbidden)
        monkeypatch.setattr(cv2, "VideoCapture", forbidden)
        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
        response = client.get(ENDPOINT)
        assert response.status_code == 200 and response.json() == make_report()
        assert response.headers["cache-control"] == "no-store"
        response = client.post(ENDPOINT + "/investigate", json={"question": "Explain"}, headers=AUTH)
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        assert response.json()["failure_code"] == "NOT_CONFIGURED"
        assert response.json()["research_report"] == make_report()
        assert "TEST-KEY" not in response.text and "TEST-RESEARCH-ONLY" not in response.text
        with runtime.store.connection() as db:
            assert tuple(db.iterdump()) == before


def test_post_requires_auth_and_strict_question_contract_before_model_calls(app, monkeypatch):
    calls = []
    async def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Invalid or unauthenticated request reached the gateway")
    monkeypatch.setattr(service, "investigate_fresh_physics", forbidden)
    with TestClient(app) as client:
        assert client.post(ENDPOINT + "/investigate", json={"question": "Explain"}).status_code == 401
        for body in ({"text": "Explain"}, {"question": "Explain", "case_id": "unrelated"},
                     {"question": "x" * 2001}, {"question": ""}):
            assert client.post(ENDPOINT + "/investigate", json=body, headers=AUTH).status_code == 422
    assert calls == []


@pytest.mark.parametrize("error,code", [(FileNotFoundError("PRIVATE-PATH"), 503),
    (ImportError("PRIVATE-MODULE"), 503), (PermissionError("PRIVATE-PERMISSION"), 503),
    (ValueError("PRIVATE-HASH-DETAIL"), 409), (TypeError("PRIVATE-SHAPE"), 409),
    (KeyError("PRIVATE-FIELD"), 409)])
def test_get_and_post_artifact_errors_are_sanitized_no_store(app, monkeypatch, error, code):
    def broken():
        raise error
    monkeypatch.setattr(service, "load_fresh_physics_report", broken)
    with TestClient(app) as client:
        for response in (client.get(ENDPOINT), client.post(ENDPOINT + "/investigate",
                         json={"question": "Explain"}, headers=AUTH)):
            assert response.status_code == code
            assert response.headers["cache-control"] == "no-store"
            assert "PRIVATE-" not in response.text


def test_actual_http_post_uses_bounded_mocked_chalk_tools_and_returns_exact_snapshot(app, monkeypatch):
    monkeypatch.setattr(app.state.runtime, "chalk_settings", settings)
    calls = []
    async def injected(question, backend, context, chosen_settings, *, client=None):
        async with scripted_client()[0] as mock_client:
            result = await investigate_study(question, backend, context, chosen_settings, client=mock_client)
        calls.append(result)
        return result
    monkeypatch.setattr(service, "investigate_study", injected)
    with TestClient(app) as client:
        response = client.post(ENDPOINT + "/investigate", json={"question": "Explain"}, headers=AUTH)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    result = response.json()
    assert len(calls) == 1 and result["action"] == "REPORT" and result["live_model_response"] is True
    assert result["research_report"] == make_report()
    assert len(result["trace"]) == 1 and result["trace"][0]["tool"] == "get_study_evidence"


def test_actual_pinned_public_reader_and_compact_tool_fit_read_only_boundaries(app, monkeypatch):
    from apps.ocean.reeftrace_ocean import fresh_drifter
    expected = fresh_drifter.run_fresh_drifter_study()
    runtime = app.state.runtime
    monkeypatch.setattr(service, "load_fresh_physics_report", fresh_drifter.run_fresh_drifter_study)
    def forbidden(*args, **kwargs):
        raise AssertionError("Actual public research replay attempted acquisition or another side effect")
    with TestClient(app) as client:
        with runtime.store.connection() as db:
            before = tuple(db.iterdump())
        for method in ("put", "put_case_result", "add_case", "update_case", "propose", "transition_action"):
            monkeypatch.setattr(runtime.store, method, forbidden)
        monkeypatch.setattr(fresh_drifter, "freeze_first_report", forbidden)
        monkeypatch.setattr(cv2, "VideoCapture", forbidden)
        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
        response = client.get(ENDPOINT)
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        assert response.json() == expected
        backend = service.StudyBackend(response.json())
        tool = asyncio.run(backend.call("get_study_evidence", {}))
        assert len(json.dumps(tool, allow_nan=False).encode()) < 40000
        assert tool["study"]["pre_outcome_amendment"] == expected["protocol"]["pre_outcome_amendment"]
        assert tool["study"]["pre_outcome_amendment"]["parent_model_outcomes"] == 0
        assert tool["study"]["coverage"] == expected["coverage"]
        assert tool["study"]["models"] == expected["models"]
        assert tool["study"]["provenance"] == expected["provenance"]
        with runtime.store.connection() as db:
            assert tuple(db.iterdump()) == before


@pytest.mark.parametrize("premature_stop", [False, True])
def test_actual_report_works_through_mocked_chalk_and_later_lineage_change_is_rejected(premature_stop):
    from apps.ocean.reeftrace_ocean.fresh_drifter import run_fresh_drifter_study
    actual = run_fresh_drifter_study()
    async def execute(loader):
        mock_client, requests = scripted_client(premature_stop=premature_stop)
        async with mock_client:
            result = await service.investigate_fresh_physics(SimpleNamespace(chalk_settings=settings),
                "Explain the study limits and any recorded acquisition amendment.",
                client=mock_client, loader=loader)
        assert len(requests) == 2
        return result
    result = asyncio.run(execute(lambda: copy.deepcopy(actual)))
    assert result["action"] == "REPORT" and result["research_report"] == actual
    assert result["protocol_sha256"] == actual["protocol_sha256"]
    assert result["snapshot_report_sha256"] == service.snapshot_identity(actual)[0]
    assert len(result["trace"]) == 1
    assert result["trace"][0]["read_origin"] == (
        "server_required_after_premature_finish" if premature_stop else "model_requested")
    assert result["trace"][0]["result"]["study"]["coverage"] == actual["coverage"]
    reads = []
    def changed_lineage():
        snapshot = copy.deepcopy(actual)
        if reads:
            old = snapshot["provenance"]["hashes"].get("reference_report_sha256")
            snapshot["provenance"]["hashes"]["reference_report_sha256"] = "d" * 64 if old != "d" * 64 else "e" * 64
        reads.append(True)
        return snapshot
    with pytest.raises(ValueError, match="snapshot changed"):
        asyncio.run(execute(changed_lineage))
    assert len(reads) == 2


def test_actual_trajectory_tampering_is_blocked_before_chalk_and_never_rewrites_public_data(
    app, tmp_path, monkeypatch,
):
    from apps.ocean.reeftrace_ocean import fresh_drifter
    public = fresh_drifter.DIRECTORY
    manifest = json.loads((public / "manifest.json").read_text())
    relative = manifest["trajectories"][0]["raw_path"]
    original = (public / relative).read_bytes()
    corrupt = tmp_path / "corrupt-study-copy"
    shutil.copytree(public, corrupt)
    (corrupt / relative).write_bytes(original + b"\n")
    monkeypatch.setattr(service, "load_fresh_physics_report",
                        lambda: fresh_drifter.run_fresh_drifter_study(corrupt))
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid public data reached the Chalk gateway")
    monkeypatch.setattr(app.state.runtime, "chalk_settings", forbidden)
    with TestClient(app) as client:
        for response in (client.get(ENDPOINT), client.post(ENDPOINT + "/investigate",
                         json={"question": "Explain the altered study"}, headers=AUTH)):
            assert response.status_code == 409
            assert response.headers["cache-control"] == "no-store"
            assert "corrupt-study-copy" not in response.text
    assert (public / relative).read_bytes() == original
