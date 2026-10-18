"""One mocked project GET; never creates a worker, message or provider connection."""

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

from apps.api.reeftrace_api.services import photon_readonly
from apps.api.reeftrace_api.services.photon_readonly import PhotonReadOnlyVerifier
from deploy.start import api_environment, next_environment

KEY = "read-only-fake-key-never-live"
PROJECT = "project-test-only"


def project(project_id=PROJECT):
    return {"projectId": project_id, "agentProfile": {
        "avatarUrl": "https://private.invalid/avatar", "firstName": "PRIVATE_HANDLE", "lastName": None},
        "createdAt": "2026-10-17T00:00:00Z", "createdByAccountId": "private-account",
        "createdByActorId": None, "createdByActorKind": None, "deletedAt": None,
        "name": "PRIVATE_PROJECT_NAME", "organizationId": "private-organization",
        "slug": "private-slug", "updatedAt": "2026-10-17T00:00:00Z"}


def sanitized(result, expected):
    assert result["status"] == expected
    assert result["scope"] == "project_authentication_only"
    assert result["replies_enabled"] is False
    assert set(result) <= {"status", "scope", "checked_at", "replies_enabled", "retry_after_s"}
    text = json.dumps(result)
    for private in (KEY, PROJECT, "PRIVATE_HANDLE", "PRIVATE_PROJECT_NAME", "private-account",
                    "private-organization", "sensitive-upstream-message"):
        assert private not in text


@pytest.mark.parametrize("response_status,payload,expected", [
    (200, project(), "VERIFIED"),
    (200, project("wrong-private-project"), "PROJECT_MISMATCH"),
    (401, {"detail": "sensitive-upstream-message"}, "AUTH_FAILED"),
    (403, {"detail": "sensitive-upstream-message"}, "AUTH_FAILED"),
    (503, {"detail": "sensitive-upstream-message"}, "UNAVAILABLE"),
    (200, {"secret": "sensitive-upstream-message"}, "UNAVAILABLE"),
])
def test_exact_official_sdk_get_is_single_attempt_and_returns_only_sanitized_status(
        response_status, payload, expected):
    pytest.importorskip("photon_api")
    requests = []

    def serve(request):
        requests.append(request)
        assert request.method == "GET"
        assert str(request.url) == "https://api.photon.codes/v1/projects/" + PROJECT
        assert request.headers["Authorization"] == "Bearer " + KEY
        assert not request.content
        return httpx.Response(response_status, json=payload)

    async def run():
        verifier = PhotonReadOnlyVerifier(KEY, PROJECT)
        assert requests == []  # Construction does not even instantiate the SDK.
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
            result = await verifier.verify(client=client)
            sanitized(result, expected)
            assert result["checked_at"]
            assert len(requests) == 1  # Including retryable HTTP503.
            assert not client.is_closed, "The caller owns its injected client"
            again = await verifier.verify(client=client)
            sanitized(again, "COOLDOWN")
            assert again["retry_after_s"] >= 1
            assert len(requests) == 1

    asyncio.run(run())


def test_missing_credentials_do_not_construct_an_sdk_or_contact_the_network(monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("Unconfigured verification attempted HTTP")

    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)

    async def run():
        for key, project_id in (("", ""), (KEY, ""), ("", PROJECT), ("  ", PROJECT)):
            result = await PhotonReadOnlyVerifier(key, project_id).verify()
            sanitized(result, "UNCONFIGURED")
            assert result["checked_at"] is None

    asyncio.run(run())


def test_missing_optional_sdk_is_unavailable_without_leaking_import_details(monkeypatch):
    monkeypatch.setitem(sys.modules, "photon_api", None)
    result = asyncio.run(PhotonReadOnlyVerifier(KEY, PROJECT).verify())
    sanitized(result, "UNAVAILABLE")


def test_readonly_credentials_reach_only_python_while_legacy_messaging_stays_disabled():
    env = {"REEFTRACE_LOCAL_TOKEN": "operator-test-only-" + "x" * 32,
           "PHOTON_READONLY_API_KEY": KEY, "PHOTON_READONLY_PROJECT_ID": PROJECT,
           "PHOTON_ENABLED": "true", "PHOTON_API_KEY": "do-not-enable",
           "PHOTON_PROJECT_ID": "do-not-enable", "PHOTON_ROUTES_JSON": "untrusted"}
    python = api_environment(env, Path("/app"))
    assert python["PHOTON_READONLY_API_KEY"] == KEY
    assert python["PHOTON_READONLY_PROJECT_ID"] == PROJECT
    assert python["PHOTON_ENABLED"] == "false"
    assert python["PHOTON_API_KEY"] == python["PHOTON_PROJECT_ID"] == ""
    assert python["PHOTON_ROUTES_JSON"] == "[]"
    frontend = next_environment(env, 8080)
    assert not any(key.startswith("PHOTON") for key in frontend)
    assert KEY not in frontend.values() and PROJECT not in frontend.values()


def test_sdk_wrapped_http_timeout_is_sanitized_without_retries():
    pytest.importorskip("photon_api")
    calls = []

    def timeout(request):
        calls.append(request)
        raise httpx.ReadTimeout("sensitive-upstream-message", request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
            result = await PhotonReadOnlyVerifier(KEY, PROJECT).verify(client=client)
        sanitized(result, "TIMEOUT")
        assert len(calls) == 1

    asyncio.run(run())


def test_total_deadline_cancels_pending_get_and_does_not_leave_a_busy_verifier(monkeypatch):
    pytest.importorskip("photon_api")
    monkeypatch.setattr(photon_readonly, "VERIFY_TIMEOUT_S", 0.02)
    clock = [0.0]
    cancelled = []

    async def pending(request):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    async def run():
        verifier = PhotonReadOnlyVerifier(KEY, PROJECT, clock=lambda: clock[0])
        async with httpx.AsyncClient(transport=httpx.MockTransport(pending)) as client:
            result = await asyncio.wait_for(verifier.verify(client=client), timeout=1)
            sanitized(result, "TIMEOUT")
            assert cancelled == [True]
            sanitized(await verifier.verify(client=client), "COOLDOWN")
        clock[0] = 11
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=project()))) as client:
            sanitized(await verifier.verify(client=client), "VERIFIED")

    asyncio.run(run())


def test_overlapping_checks_fail_fast_and_cancelled_owner_releases_its_gate():
    pytest.importorskip("photon_api")
    clock = [0.0]

    async def run():
        entered = asyncio.Event()
        calls = []

        async def pending(request):
            calls.append(request)
            entered.set()
            await asyncio.Event().wait()

        verifier = PhotonReadOnlyVerifier(KEY, PROJECT, clock=lambda: clock[0])
        async with httpx.AsyncClient(transport=httpx.MockTransport(pending)) as client:
            owner = asyncio.create_task(verifier.verify(client=client))
            await asyncio.wait_for(entered.wait(), timeout=1)
            sanitized(await asyncio.wait_for(verifier.verify(client=client), timeout=0.2), "COOLDOWN")
            assert len(calls) == 1
            owner.cancel()
            with pytest.raises(asyncio.CancelledError):
                await owner
        clock[0] = 11
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=project()))) as client:
            sanitized(await verifier.verify(client=client), "VERIFIED")

    asyncio.run(run())
