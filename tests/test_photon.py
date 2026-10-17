"""Real pinned SDK over MockTransport; never contacts Photon or sends a message."""

import asyncio
import copy
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

from adapters.photon.transport import (
    Inbound,
    Outgoing,
    PhotonSettings,
    PhotonTransport,
    RouteConfig,
    normalize,
    retry_delay,
)
from adapters.photon.worker import PhotonWorker

ROUTE = RouteConfig("+15550001111", "+15550002222", "operator", ("case-1",))
SETTINGS = PhotonSettings(True, "not-a-live-key", "project-1", (ROUTE,), max_attempts=1)
TIME = "2026-10-16T12:00:00Z"
START = datetime(2026, 10, 16, 11, tzinfo=UTC)


def message_payload():
    user = {
        "platform": "imessage",
        "kind": "human",
        "id": "human-1",
        "handle": ROUTE.human_handle,
        "projectId": "project-1",
        "metadata": {},
        "details": {},
    }
    agent = {**user, "kind": "agent", "id": "agent-1", "handle": ROUTE.agent_handle}
    space = {
        "platform": "imessage",
        "kind": "direct",
        "id": "space-1",
        "projectId": "project-1",
        "metadata": {},
        "details": {},
        "participantIds": ["human-1", "agent-1"],
    }
    return {
        "platform": "imessage",
        "status": "received",
        "id": "incoming-1",
        "projectId": "project-1",
        "createdAt": TIME,
        "updatedAt": TIME,
        "sentBy": user,
        "receivedBy": agent,
        "space": space,
        "metadata": {},
        "timestamps": {"receivedAt": TIME},
        "content": {"type": "text", "format": "plain", "text": "Why source B?"},
    }


def parsed_message(payload=None):
    pytest.importorskip("photon_api")
    from photon_api.generated.models import MessagePage

    return MessagePage.model_validate({"items": [payload or message_payload()]}).items[0]


class MemoryStore:
    def __init__(self):
        self.inbox, self.outbox, self.updates = {}, {}, []
        self.finished = set()
        self.failed = {}
        self.errors = []

    def load_session_start(self):
        return START.isoformat()

    def ingest_once(self, item):
        if item.id in self.inbox:
            return False
        self.inbox[item.id] = item
        return True

    def claim_inbound(self):
        return next((v for k, v in self.inbox.items() if k not in self.finished), None)

    claim_control_inbound = claim_inbound

    def finish_inbound(self, ident, row):
        self.outbox.setdefault(row.key, row)
        self.finished.add(ident)

    def fail_inbound(self, ident, error):
        self.failed[ident] = error
        self.finished.add(ident)

    def claim_outgoing(self):
        return next(iter(self.outbox.values()), None)

    def update_outgoing(self, key, status, **kwargs):
        self.updates.append((key, status, kwargs))
        if status != "pending":
            self.outbox.pop(key)

    def log_transport_error(self, kind, detail):
        self.errors.append((kind, detail))


def test_normalizes_real_sdk_models_and_rejects_wrong_route_and_old_session():
    result = normalize(parsed_message(), (ROUTE,), START, project_id="project-1")
    assert result.agent_id == "agent-1"
    assert result.human_id == "human-1"
    assert result.allowed_cases == ("case-1",)
    assert normalize(parsed_message(), (), START) is None
    assert normalize(parsed_message(), (ROUTE,), START, project_id="other-project") is None
    assert normalize(parsed_message(), (ROUTE,), datetime(2027, 1, 1, tzinfo=UTC)) is None
    payload = message_payload()
    payload["space"]["kind"] = "group"
    assert normalize(parsed_message(payload), (ROUTE,), START) is None
    payload = message_payload()
    payload.pop("receivedBy")
    assert normalize(parsed_message(payload), (ROUTE,), START) is None


def test_official_sdk_http_contract_get_and_idempotent_post():
    pytest.importorskip("photon_api")
    requests = []

    def serve(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"items": [message_payload()]})
        dispatched = copy.deepcopy(message_payload())
        dispatched.update(status="dispatched", id="outgoing-1", timestamps={"dispatchedAt": TIME})
        dispatched["sentBy"], dispatched["receivedBy"] = (
            dispatched["receivedBy"],
            dispatched["sentBy"],
        )
        return httpx.Response(202, headers={"x-request-id": "request-1"}, json=dispatched)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
            transport = PhotonTransport(SETTINGS, client=client)
            page = await transport.list_page(TIME)
            assert len(page.items) == 1
            row = Outgoing(
                "reeftrace:reply:incoming-1", "space-1", "agent-1", "incoming-1", "Unknown."
            )
            assert await transport.send_saved(row) == (202, "request-1")
            await transport.close()
            assert not client.is_closed

    asyncio.run(run())
    assert requests[0].url.path == "/v1/projects/project-1/messages"
    assert requests[0].url.params["createdSince"] == TIME
    assert requests[0].url.params["direction"] == "received"
    assert requests[0].headers["Authorization"] == "Bearer not-a-live-key"
    assert requests[1].headers["idempotency-key"] == "reeftrace:reply:incoming-1"
    body = json.loads(requests[1].content)
    assert body["senderId"] == "agent-1"
    assert body["spaceId"] == "space-1"
    assert body["parentMessageId"] == "incoming-1"


def test_poll_rescans_session_deduplicates_and_follows_empty_page_token():
    pytest.importorskip("photon_api")
    store = MemoryStore()

    class Transport:
        def __init__(self):
            self.calls = []

        async def list_page(self, since, token=None):
            self.calls.append((since, token))
            return SimpleNamespace(
                items=[] if token is None else [parsed_message()],
                nextPageToken="next" if token is None else None,
            )

    async def handler(_):
        return "Unknown."

    async def run():
        transport = Transport()
        worker = PhotonWorker(SETTINGS, store, handler, transport=transport)
        assert await worker.poll_once() == 1
        assert await worker.poll_once() == 0
        assert len(transport.calls) == 4
        assert all(call[0] == START.isoformat() for call in transport.calls)

    asyncio.run(run())


def test_persists_immutable_reply_before_send_and_reuses_key_on_uncertain_failure():
    pytest.importorskip("photon_api")
    store = MemoryStore()
    store.ingest_once(normalize(parsed_message(), (ROUTE,), START))

    class Transport:
        def __init__(self):
            self.calls = []

        async def send_saved(self, row):
            assert store.finished == {"incoming-1"}
            assert row.key in store.outbox
            self.calls.append(row)
            if len(self.calls) == 1:
                raise httpx.ReadTimeout("uncertain response")
            return 202, "request-2"

    async def handler(_):
        return "Source unknown; more observation is needed."

    async def run():
        transport = Transport()
        worker = PhotonWorker(SETTINGS, store, handler, transport=transport)
        assert await worker.process_once()
        assert transport.calls == []
        assert await worker.send_once()
        assert store.updates[-1][1] == "pending"
        assert await worker.send_once()
        assert store.updates[-1][1] == "accepted"
        assert transport.calls[0] == transport.calls[1]

    asyncio.run(run())


def test_revoked_route_and_disabled_configuration_cannot_dispatch():
    store = MemoryStore()
    item = Inbound(
        "m",
        TIME,
        "h",
        ROUTE.human_handle,
        "a",
        ROUTE.agent_handle,
        "s",
        "unauthorized-role",
        ROUTE.allowed_cases,
        "APPROVE guessed",
    )
    store.ingest_once(item)

    async def never(_):
        raise AssertionError("Handler must not run")

    async def run():
        disabled = PhotonWorker(PhotonSettings(), store, never)
        assert await disabled.process_once() is False
        assert await disabled.send_once() is False
        if SETTINGS.readiness()["ready"]:
            worker = PhotonWorker(SETTINGS, store, never)
            assert await worker.process_once()
            assert store.failed == {"m": "Route authorization changed"}

    asyncio.run(run())
    assert "not-a-live-key" not in repr(SETTINGS)


def test_retry_after_is_not_shortened_by_sdk_wait_cap():
    assert retry_delay(SimpleNamespace(headers={"Retry-After": "120"})) == 120


def test_sqlite_control_lane_remains_responsive_during_slow_investigation(tmp_path):
    pytest.importorskip("photon_api")
    from apps.api.reeftrace_api.services.store import Store

    store = Store(tmp_path)
    store.bind_photon_project("project-1")
    question = Inbound(
        "question-1",
        TIME,
        "h",
        ROUTE.human_handle,
        "a",
        ROUTE.agent_handle,
        "s",
        ROUTE.role,
        ROUTE.allowed_cases,
        "Why source B?",
    )
    control = Inbound(
        "stop-1",
        TIME,
        "h",
        ROUTE.human_handle,
        "a",
        ROUTE.agent_handle,
        "s",
        ROUTE.role,
        ROUTE.allowed_cases,
        "STOP case-1",
    )
    assert store.ingest_once(question)
    assert store.ingest_once(control)
    assert not store.ingest_once(question)

    async def run():
        investigating, release, stopped = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def handler(item):
            if item.id == "question-1":
                investigating.set()
                await release.wait()
                return "Investigation stopped because the case revision changed."
            stopped.set()
            return "Case stopped. The AC pump is not remotely controlled."

        worker = PhotonWorker(SETTINGS, store, handler)
        slow = asyncio.create_task(worker.process_once())
        await asyncio.wait_for(investigating.wait(), 0.5)
        assert await asyncio.wait_for(worker.process_once(control=True), 0.5)
        assert stopped.is_set() and not slow.done()
        release.set()
        assert await slow

    asyncio.run(run())
    reopened = Store(tmp_path)
    assert not reopened.ingest_once(question)
    assert reopened.claim_inbound() is None
    assert reopened.claim_control_inbound() is None
    saved = reopened.claim_outgoing()
    assert saved.key == "reeftrace:reply:stop-1"
    assert saved.parent_message_id == "stop-1"
    with pytest.raises(ValueError, match="different Photon project"):
        reopened.bind_photon_project("other-project")


def test_authentication_failure_blocks_worker_instead_of_repeated_sends():
    pytest.importorskip("photon_api")
    store = MemoryStore()
    row = Outgoing("reeftrace:reply:m", "s", "a", "m", "Unknown.")
    store.outbox[row.key] = row

    class Denied(Exception):
        status = 403
        request_id = "denied-request"

        def __init__(self):
            super().__init__("Forbidden")
            self.headers = {}

    class Transport:
        async def send_saved(self, _):
            raise Denied()

    async def handler(_):
        return "Unused"

    async def run():
        worker = PhotonWorker(SETTINGS, store, handler, transport=Transport())
        assert await worker.send_once()
        assert store.updates[-1][1] == "failed"
        assert worker.readiness()["ready"] is False
        assert "authorization_failed_restart_required" in worker.readiness()["reasons"]
        assert not await worker.send_once()

    asyncio.run(run())
