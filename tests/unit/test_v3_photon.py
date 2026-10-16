import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from apps.core.reeftrace_core.photon import ingress, normalize, retry_delay
from apps.core.reeftrace_core.store import Store

pytest.importorskip("photon_api")
from photon_api.generated.models import TextContent, UserSnapshot


def test_normalize_exact_route_and_ignore_missing_or_foreign_identity():
    human = SimpleNamespace(id="human", kind="human", platform="imessage", handle="assigned-human")
    agent = SimpleNamespace(id="agent", kind="agent", platform="imessage", handle="assigned-agent")
    space = SimpleNamespace(id="space", kind="direct", platform="imessage")
    received = UserSnapshot.model_construct(root=agent)
    message = SimpleNamespace(
        platform="imessage",
        status="received",
        id="vendor-1",
        createdAt="2026-10-16T16:00:00Z",
        receivedBy=received,
        sentBy=SimpleNamespace(root=human),
        space=SimpleNamespace(root=space),
        content=TextContent(type="text", format="plain", text="hello"),
    )
    item = SimpleNamespace(root=SimpleNamespace(root=message))
    routes = [
        {
            "human_handle": "assigned-human",
            "agent_handle": "assigned-agent",
            "role": "observer",
            "allowed_cases": ["case-1"],
            "active_case": "case-1",
        }
    ]
    start = datetime(2026, 10, 16, tzinfo=UTC)
    assert normalize(item, routes, start)["role"] == "observer"
    human.handle = "unassigned"
    assert normalize(item, routes, start) is None
    assert retry_delay("15") == 15


def test_pagination_follows_empty_page_and_nonstring_missing_token(tmp_path):
    stop = asyncio.Event()
    requests = []

    class Projects:
        async def list_messages(self, request):
            requests.append(request)
            if len(requests) == 1:
                return SimpleNamespace(items=[], nextPageToken="page-2")
            stop.set()
            return SimpleNamespace(items=[], nextPageToken=object())

    client = SimpleNamespace(projects=Projects())
    asyncio.run(ingress(client, Store(tmp_path / "messages.db"), "pho_prj_test", [], stop))
    assert len(requests) == 2
    assert requests[1].query.page_token == "page-2"
