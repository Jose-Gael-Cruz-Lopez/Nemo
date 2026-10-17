"""Actual API/runtime/store with explicitly mocked model and camera prerequisites."""

import asyncio
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from adapters.photon.transport import Inbound
from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.api.reeftrace_api.schemas.contracts import CaseInput
from apps.api.reeftrace_api.services.investigation import CaseBackend

AUTH = {"Authorization": "Bearer test"}


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("CHALK_ENABLED", "false")
    monkeypatch.setenv("PHOTON_ENABLED", "false")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "[]")
    return create_app(Settings(data_dir=tmp_path, local_token="test"))


def seed_case(runtime, *, mode="SYNTHETIC"):
    profile = {
        "id": "profile-1",
        "calibration_id": "calibration-1",
        "data_origin": "SYNTHETIC",
        "token_class": "test-token",
        "bounds": {"x_min_cm": 0, "x_max_cm": 10, "y_min_cm": 0, "y_max_cm": 10},
        "sources": [{"id": "A"}, {"id": "B"}],
        "transport": {"particles_per_source": 20, "dt_s": 0.1, "max_age_s": 1},
    }
    runtime.register_profile(profile)
    observation = CaseInput(
        profile_id=profile["id"],
        calibration_id=profile["calibration_id"],
        token_class="test-token",
        mode="SYNTHETIC",
        points=[],
    ).model_dump()
    observation["mode"] = mode
    case = runtime.store.add_case(observation)
    evidence = runtime.store.put(
        "estimate",
        {
            "case_id": case["id"],
            "status": "unknown",
            "ranked_source": None,
            "relative_support": {"A": 0.51, "B": 0.49},
            "confidence_kind": "relative_support_not_probability",
            "reason_codes": ["SOURCE_AMBIGUOUS"],
            "physical_validation": False,
            "data_origin": "SYNTHETIC",
            "mode": mode,
        },
    )
    case = runtime.store.update_case(
        case["id"], case["revision"], {"evidence_id": evidence["id"], "state": "INVESTIGATE"}
    )
    return case, evidence


def phone_message(case_id, text, *, role="operator", allowed_cases=None):
    return Inbound(
        "message-1",
        "2026-10-16T12:00:00Z",
        "human-1",
        "+15550001111",
        "agent-1",
        "+15550002222",
        "space-1",
        role,
        (case_id,) if allowed_cases is None else allowed_cases,
        text,
    )


def test_api_auth_and_sponsor_readiness_never_exposes_keys(app, monkeypatch):
    monkeypatch.setenv("CHALK_ROUTER_API_KEY", "SECRET-CHALK")
    monkeypatch.setenv("PHOTON_API_KEY", "SECRET-PHOTON")
    case, _ = seed_case(app.state.runtime)
    with TestClient(app) as client:
        status = client.get("/api/v1/status")
        assert status.status_code == 200
        assert status.json()["hardware_actuation"] is False
        assert status.json()["collection_mode"] == "manual_net"
        assert "SECRET" not in status.text
        assert status.json()["chalk"]["connection_verified"] is False
        assert client.post(f"/api/v1/cases/{case['id']}/stop").status_code == 401
        assert (
            client.post(
                f"/api/v1/cases/{case['id']}/stop", headers={"Authorization": "Bearer wrong"}
            ).status_code
            == 401
        )
        assert app.state.runtime.store.case(case["id"])["state"] == "INVESTIGATE"
        assert client.post(f"/api/v1/cases/{case['id']}/stop", headers=AUTH).status_code == 200


def test_api_disabled_chalk_is_graceful_and_saved_scores_remain_available(app):
    case, evidence = seed_case(app.state.runtime)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/cases/{case['id']}/investigate", json={"text": "Why source B?"}, headers=AUTH
        )
        assert response.status_code == 200
        answer = response.json()
        assert answer["action"] == "STOP"
        assert answer["live_model_response"] is False
        assert answer["source_report"] == evidence
        assert client.get(f"/api/v1/cases/{case['id']}/evidence").json() == evidence


def test_synthetic_case_cannot_create_live_recovery_and_truth_fields_are_rejected(app):
    case, evidence = seed_case(app.state.runtime)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/actions/propose",
            headers=AUTH,
            json={"case_id": case["id"], "evidence_id": evidence["id"]},
        )
        assert response.status_code == 409
        request = {
            "profile_id": "profile-1",
            "calibration_id": "calibration-1",
            "token_class": "test-token",
            "mode": "SYNTHETIC",
            "true_source": "A",
        }
        assert client.post("/api/v1/cases", headers=AUTH, json=request).status_code == 422


def test_duplicate_approval_and_outcome_are_transactionally_consumed(app, monkeypatch):
    runtime = app.state.runtime
    case, evidence = seed_case(runtime, mode="LIVE")
    # This test targets task transitions; it does not pretend to validate a camera.
    monkeypatch.setattr(runtime, "validate_live", lambda *_, **__: None)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/actions/propose",
            headers=AUTH,
            json={"case_id": case["id"], "evidence_id": evidence["id"]},
        )
        assert response.status_code == 200
        action = response.json()
        url = f"/api/v1/actions/{action['id']}"
        assert (
            client.post(
                url + "/outcome",
                headers=AUTH,
                json={
                    "outcome": "manual_recovered",
                    "recovered_count": 1,
                    "note": "One test token",
                },
            ).status_code
            == 409
        )
        assert client.post(url + "/approve", headers=AUTH).status_code == 200
        assert client.post(url + "/approve", headers=AUTH).status_code == 409
        assert (
            client.post(
                url + "/outcome",
                headers=AUTH,
                json={"outcome": "manual_recovered", "recovered_count": 0, "note": "No token"},
            ).status_code
            == 409
        )
        assert (
            client.post(
                url + "/outcome",
                headers=AUTH,
                json={
                    "outcome": "manual_recovered",
                    "recovered_count": 1,
                    "note": "One test token",
                },
            ).status_code
            == 200
        )
        assert (
            client.post(
                url + "/outcome",
                headers=AUTH,
                json={"outcome": "manual_recovered", "recovered_count": 1, "note": "Duplicate"},
            ).status_code
            == 409
        )
        assert client.post(url + "/cancel", headers=AUTH).status_code == 409


def test_stale_camera_blocks_approval_even_when_task_was_previously_proposed(app):
    runtime = app.state.runtime
    case, evidence = seed_case(runtime, mode="LIVE")
    action = runtime.store.propose(case["id"], evidence["id"], allowed=True)
    with TestClient(app) as client:
        response = client.post(f"/api/v1/actions/{action['id']}/approve", headers=AUTH)
        assert response.status_code == 409
        assert "camera" in response.json()["detail"].lower()
        assert runtime.store.action(action["id"])["state"] == "proposed"


def test_stop_while_model_awaits_discards_proposal_and_old_numerical_report(app, monkeypatch):
    runtime = app.state.runtime
    case, evidence = seed_case(runtime)

    async def run():
        started, release = asyncio.Event(), asyncio.Event()

        async def slow_model(*_, **__):
            started.set()
            await release.wait()
            return {
                "action": "REQUEST_APPROVAL",
                "evidence_ids": [evidence["id"]],
                "proposal_id": "a-superseded-proposal",
                "explanation": "Old answer",
                "trace": [],
            }

        monkeypatch.setattr("adapters.chalk.agent.investigate", slow_model)
        task = asyncio.create_task(runtime.investigate(case["id"], "Explain the source"))
        await asyncio.wait_for(started.wait(), 0.5)
        runtime.store.stop_case(case["id"])
        release.set()
        result = await task
        assert result["action"] == "STOP"
        assert result["source_report"] is None
        assert result["evidence_ids"] == []
        assert "proposal_id" not in result
        saved = runtime.store.list("investigation")[0]
        assert saved["source_report"] is None

    asyncio.run(run())


def test_stopped_case_never_calls_model(app, monkeypatch):
    runtime = app.state.runtime
    case, _ = seed_case(runtime)
    runtime.store.stop_case(case["id"])

    async def never(*_, **__):
        raise AssertionError("No model call on stopped case")

    monkeypatch.setattr("adapters.chalk.agent.investigate", never)
    answer = asyncio.run(runtime.investigate(case["id"], "Retry the old question"))
    assert answer["action"] == "STOP"
    assert answer["source_report"] is None


def test_backend_is_case_bound_and_rejects_unregistered_sensitivity(app):
    runtime = app.state.runtime
    case, evidence = seed_case(runtime)
    backend = CaseBackend(runtime, case["id"], operator=False)

    async def run():
        assert (await backend.call("get_case", {}))["case_id"] == case["id"]
        assert (await backend.call("get_source_evidence", {}))["report"] == evidence
        with pytest.raises(ValueError, match="Unregistered"):
            await backend.call("run_predeclared_sensitivity", {"preset_id": "invented"})
        with pytest.raises(ValueError, match="Operator"):
            await backend.call("propose_collection", {"evidence_id": evidence["id"]})

    asyncio.run(run())


@pytest.mark.parametrize(
    "text", ["STOP", "CANCEL", "APPROVE", "STOP x extra", "APPROVE a with conditions"]
)
def test_malformed_control_commands_never_fall_through_to_agent(app, monkeypatch, text):
    runtime = app.state.runtime
    case, _ = seed_case(runtime)

    async def never(*_, **__):
        raise AssertionError("Malformed control commands must not reach the model")

    monkeypatch.setattr(runtime, "investigate", never)
    response = asyncio.run(runtime.photon_handler(phone_message(case["id"], text)))
    assert "Command format" in response
    assert runtime.store.case(case["id"])["state"] == "INVESTIGATE"


def test_phone_command_authorization_is_separate_from_model_language(app):
    runtime = app.state.runtime
    case, _ = seed_case(runtime)
    observer = phone_message(case["id"], "STOP " + case["id"], role="observer")
    assert "denied" in asyncio.run(runtime.photon_handler(observer))
    wrong_case = replace(observer, role="operator", allowed_cases=("other-case",))
    assert "denied" in asyncio.run(runtime.photon_handler(wrong_case))
    assert runtime.store.case(case["id"])["state"] == "INVESTIGATE"
    allowed = replace(observer, role="operator")
    assert "Pump power is unchanged" in asyncio.run(runtime.photon_handler(allowed))
    assert runtime.store.case(case["id"])["state"] == "STOPPED"


def test_phone_numerical_report_uses_store_not_model_fields(app, monkeypatch):
    runtime = app.state.runtime
    case, evidence = seed_case(runtime)

    async def model(*_, **__):
        return {
            "action": "UNKNOWN",
            "evidence_ids": [evidence["id"]],
            "explanation": "The saved evidence remains ambiguous.",
            "trace": [],
            "source_report": {"relative_support": {"A": 1.0, "B": 0.0}},
        }

    monkeypatch.setattr("adapters.chalk.agent.investigate", model)
    text = asyncio.run(runtime.photon_handler(phone_message(case["id"], "Why this source?")))
    assert '"A": 0.51' in text and '"B": 0.49' in text
    assert '"A": 1.0' not in text


@pytest.mark.parametrize("final_action", ["STOP", "REPORT", "UNKNOWN"])
def test_unused_agent_proposal_is_cancelled_instead_of_left_approvable(
    app, monkeypatch, final_action
):
    runtime = app.state.runtime
    case, evidence = seed_case(runtime, mode="LIVE")
    monkeypatch.setattr(runtime, "validate_live", lambda *_, **__: None)
    created = []

    async def model(_, backend, *__, **___):
        proposal = await backend.call("propose_collection", {"evidence_id": evidence["id"]})
        created.append(proposal["proposal_id"])
        return {
            "action": final_action,
            "explanation": "No proposal is published.",
            "evidence_ids": [evidence["id"]],
            "trace": [],
        }

    monkeypatch.setattr("adapters.chalk.agent.investigate", model)
    asyncio.run(runtime.investigate(case["id"], "Investigate"))
    assert runtime.store.action(created[0])["state"] == "cancelled"
    with pytest.raises(ValueError):
        runtime.approve(created[0])


def test_successful_approval_request_keeps_only_its_published_proposal(app, monkeypatch):
    runtime = app.state.runtime
    case, evidence = seed_case(runtime, mode="LIVE")
    monkeypatch.setattr(runtime, "validate_live", lambda *_, **__: None)

    async def model(_, backend, *__, **___):
        proposal = await backend.call("propose_collection", {"evidence_id": evidence["id"]})
        return {
            "action": "REQUEST_APPROVAL",
            "proposal_id": proposal["proposal_id"],
            "explanation": "A person must approve the manual net task.",
            "evidence_ids": [evidence["id"]],
            "trace": [],
        }

    monkeypatch.setattr("adapters.chalk.agent.investigate", model)
    result = asyncio.run(runtime.investigate(case["id"], "Prepare a manual recovery task"))
    assert result["action"] == "REQUEST_APPROVAL"
    assert runtime.store.action(result["proposal_id"])["state"] == "proposed"
    assert runtime.approve(result["proposal_id"])["state"] == "awaiting_human"


@pytest.mark.parametrize("failure", ["exception", "cancelled"])
def test_agent_exception_or_task_cancellation_cleans_up_its_proposal(app, monkeypatch, failure):
    runtime = app.state.runtime
    case, evidence = seed_case(runtime, mode="LIVE")
    monkeypatch.setattr(runtime, "validate_live", lambda *_, **__: None)
    created = []

    async def run():
        started, block = asyncio.Event(), asyncio.Event()

        async def model(_, backend, *__, **___):
            proposal = await backend.call("propose_collection", {"evidence_id": evidence["id"]})
            created.append(proposal["proposal_id"])
            started.set()
            if failure == "exception":
                raise RuntimeError("Simulated model/adapter exception")
            await block.wait()

        monkeypatch.setattr("adapters.chalk.agent.investigate", model)
        task = asyncio.create_task(runtime.investigate(case["id"], "Investigate"))
        await asyncio.wait_for(started.wait(), 0.5)
        if failure == "cancelled":
            task.cancel()
        with pytest.raises(RuntimeError if failure == "exception" else asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert runtime.store.action(created[0])["state"] == "cancelled"


def test_operator_outcome_during_investigation_is_preserved_without_cleanup_failure(app, monkeypatch):
    runtime = app.state.runtime
    case, evidence = seed_case(runtime, mode="LIVE")
    monkeypatch.setattr(runtime, "validate_live", lambda *_, **__: None)
    completed = []

    async def model(_, backend, *__, **___):
        proposal = await backend.call("propose_collection", {"evidence_id": evidence["id"]})
        runtime.approve(proposal["proposal_id"])
        runtime.store.transition_action(proposal["proposal_id"], "manual_recovered",
                                        note={"recovered_count": 1})
        completed.append(proposal["proposal_id"])
        return {"action": "REPORT", "explanation": "An old investigation completed.",
                "evidence_ids": [evidence["id"]], "trace": []}

    monkeypatch.setattr("adapters.chalk.agent.investigate", model)
    result = asyncio.run(runtime.investigate(case["id"], "Investigate and propose a manual task"))
    assert result["action"] == "STOP"
    assert result["live_model_response"] is False
    assert result["source_report"] is None
    assert runtime.store.action(completed[0])["state"] == "manual_recovered"
