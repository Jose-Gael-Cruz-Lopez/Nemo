"""Pinned Photon Beta contract, with no account provisioning or implicit sends."""

from __future__ import annotations

import importlib.util
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx


@dataclass(frozen=True)
class RouteConfig:
    human_handle: str
    agent_handle: str
    role: str
    allowed_cases: tuple[str, ...]


@dataclass(frozen=True)
class Inbound:
    id: str
    created_at: str
    human_id: str
    human_handle: str
    agent_id: str
    agent_handle: str
    space_id: str
    role: str
    allowed_cases: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class Outgoing:
    key: str
    space_id: str
    agent_id: str
    parent_message_id: str
    text: str


@dataclass(frozen=True)
class PhotonSettings:
    enabled: bool = False
    api_key: str = field(default="", repr=False)
    project_id: str = ""
    routes: tuple[RouteConfig, ...] = ()
    base_url: str = "https://api.photon.codes"
    poll_interval_s: float = 2.0
    timeout_s: float = 5.0
    max_attempts: int = 2
    max_retry_after_s: float = 3.0

    def readiness(self) -> dict[str, Any]:
        reasons = []
        if not self.enabled:
            reasons.append("disabled")
        if not self.api_key:
            reasons.append("missing_api_key")
        if not self.project_id:
            reasons.append("missing_project_id")
        if not self.routes:
            reasons.append("missing_routes")
        if any(
            not r.human_handle or not r.agent_handle or not r.role or not r.allowed_cases
            for r in self.routes
        ):
            reasons.append("incomplete_route")
        if len({(r.human_handle, r.agent_handle) for r in self.routes}) != len(self.routes):
            reasons.append("duplicate_route")
        if importlib.util.find_spec("photon_api") is None:
            reasons.append("sdk_not_installed")
        return {
            "provider": "photon",
            "enabled": self.enabled,
            "ready": not reasons,
            "connection_verified": False,
            "reasons": reasons,
        }


def normalize(
    item: Any,
    routes: tuple[RouteConfig, ...],
    session_start: datetime,
    *,
    project_id: str | None = None,
) -> Inbound | None:
    """Accept only current, explicitly routed, plain direct iMessages.

    Importing the generated model types here keeps the local app usable without
    the optional photon extra. Group chats, attachments and events are ignored.
    """
    from photon_api.generated.models import TextContent, UserSnapshot

    m = item.root.root
    if m.platform != "imessage" or m.status != "received":
        return None
    if project_id is not None and m.projectId != project_id:
        return None
    created = datetime.fromisoformat(m.createdAt)
    if session_start.tzinfo is None or created.tzinfo is None or created < session_start:
        return None
    if not isinstance(m.receivedBy, UserSnapshot):
        return None
    human, agent, space = m.sentBy.root, m.receivedBy.root, m.space.root
    if any(x.platform != "imessage" for x in (human, agent, space)):
        return None
    if human.kind != "human" or agent.kind != "agent":
        return None
    if human.id == agent.id or space.kind != "direct":
        return None
    route = next(
        (r for r in routes if r.human_handle == human.handle and r.agent_handle == agent.handle),
        None,
    )
    if route is None or not isinstance(m.content, TextContent):
        return None
    if m.content.format != "plain" or not m.content.text.strip() or len(m.content.text) > 4000:
        return None
    return Inbound(
        m.id,
        m.createdAt,
        human.id,
        human.handle,
        agent.id,
        agent.handle,
        space.id,
        route.role,
        tuple(route.allowed_cases),
        m.content.text.strip(),
    )


def retry_delay(error: Exception, *, minimum: float = 2.0) -> float:
    """Respect Retry-After even when the SDK's own waiting cap was exceeded."""
    headers = getattr(error, "headers", {})
    raw = next((v for k, v in headers.items() if k.lower() == "retry-after"), None)
    if raw is not None:
        try:
            seconds = float(raw)
            if math.isfinite(seconds):
                return max(minimum, seconds)
        except (ValueError, TypeError):
            try:
                when = parsedate_to_datetime(raw)
                if when.tzinfo is None:
                    when = when.replace(tzinfo=UTC)
                return max(minimum, (when - datetime.now(UTC)).total_seconds())
            except (ValueError, TypeError, OverflowError):
                pass
    return max(minimum, 10.0)


class PhotonTransport:
    """Lazy official SDK wrapper. Supplied HTTP client remains caller-owned."""

    def __init__(self, settings: PhotonSettings, *, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self._client = client
        self._sdk: Any = None

    def _get_sdk(self):
        if not self.settings.readiness()["ready"]:
            raise RuntimeError("Photon is disabled or incomplete")
        if self._sdk is None:
            from photon_api import AsyncPhoton

            self._sdk = AsyncPhoton(
                base_url=self.settings.base_url,
                headers={"Authorization": "Bearer " + self.settings.api_key},
                timeout=self.settings.timeout_s,
                max_attempts=self.settings.max_attempts,
                max_retry_after=self.settings.max_retry_after_s,
                client=self._client,
            )
        return self._sdk

    async def list_page(self, created_since: str, page_token: str | None = None):
        from photon_api.rpc_generated import ListMessagesInput

        query: dict[str, Any] = {
            "createdSince": created_since,
            "direction": "received",
            "order": "asc",
            "pageSize": 100,
            "platform": "imessage",
        }
        if page_token is not None:
            query["pageToken"] = page_token
        return await self._get_sdk().projects.list_messages(
            ListMessagesInput.model_validate(
                {
                    "path": {"id": self.settings.project_id},
                    "query": query,
                }
            )
        )

    async def send_saved(self, row: Outgoing) -> tuple[int, str | None]:
        from photon_api.rpc_generated import SendMessageInput

        if (
            not row.key
            or len(row.key) > 255
            or not row.key.isascii()
            or any(not 32 <= ord(char) <= 126 for char in row.key)
        ):
            raise ValueError("Invalid durable idempotency key")
        if not all((row.space_id, row.agent_id, row.parent_message_id, row.text.strip())):
            raise ValueError("Incomplete durable reply")
        response = await self._get_sdk().raw.projects.send_message(
            SendMessageInput.model_validate(
                {
                    "path": {"id": self.settings.project_id},
                    "headers": {"idempotency-key": row.key},
                    "body": {
                        "spaceId": row.space_id,
                        "senderId": row.agent_id,
                        "parentMessageId": row.parent_message_id,
                        "content": {"type": "text", "format": "plain", "text": row.text},
                    },
                }
            )
        )
        return response.status, response.request_id

    async def close(self) -> None:
        # The SDK closes even an injected client; preserve caller ownership here.
        if self._sdk is not None and self._client is None:
            await self._sdk.close()
