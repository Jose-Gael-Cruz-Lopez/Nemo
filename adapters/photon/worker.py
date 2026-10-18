"""Independent polling, investigation and durable reply delivery loops."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Protocol

from .transport import (
    Inbound,
    Outgoing,
    PhotonSettings,
    PhotonTransport,
    normalize,
    retry_delay,
)


class Store(Protocol):
    def load_session_start(self) -> str: ...
    def ingest_once(self, item: Inbound) -> bool: ...
    def claim_inbound(self) -> Inbound | None: ...
    def claim_control_inbound(self) -> Inbound | None: ...
    def finish_inbound(self, inbound_id: str, outgoing: Outgoing) -> None: ...
    def completed_inbound(self, inbound_id: str) -> Inbound | None: ...
    def fail_inbound(self, inbound_id: str, error: str) -> None: ...
    def claim_outgoing(self) -> Outgoing | None: ...
    def update_outgoing(
        self,
        key: str,
        status: str,
        *,
        request_id: str | None = None,
        error: str | None = None,
        retry_after_s: float | None = None,
    ) -> None: ...
    def log_transport_error(self, kind: str, detail: str) -> None: ...


class Transport(Protocol):
    async def list_page(self, created_since: str, page_token: str | None = None): ...
    async def send_saved(self, row: Outgoing) -> tuple[int, str | None]: ...
    async def close(self) -> None: ...


class ReplyAuthorizationError(ValueError):
    """A durable reply must become terminal without crossing the transport boundary."""


class PhotonWorker:
    def __init__(
        self,
        settings: PhotonSettings,
        store: Store,
        handler: Callable[[Inbound], Awaitable[str]],
        *,
        transport: Transport | None = None,
        client=None,
    ):
        self.settings, self.store, self.handler = settings, store, handler
        self.transport = transport or PhotonTransport(settings, client=client)
        self._blocked = False

    def readiness(self) -> dict:
        result = self.settings.readiness()
        if self._blocked:
            result = {
                **result,
                "ready": False,
                "reasons": [*result["reasons"], "authorization_failed_restart_required"],
            }
        return result

    def _route_authorized(self, item: Inbound) -> bool:
        route = next((route for route in self.settings.routes
                      if route.human_handle == item.human_handle
                      and route.agent_handle == item.agent_handle), None)
        return (route is not None and route.role == item.role
                and tuple(route.allowed_cases) == item.allowed_cases)

    def _authorize_queued_reply(self, row: Outgoing) -> None:
        """A saved reply keeps its body/key, but never bypasses current authorization."""
        try:
            item = self.store.completed_inbound(row.parent_message_id)
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise ReplyAuthorizationError("Queued reply lacks a valid completed inbound") from error
        if not isinstance(item, Inbound):
            raise ReplyAuthorizationError("Queued reply lacks a valid completed inbound")
        if (row.parent_message_id != item.id or row.key != "reeftrace:reply:" + item.id
                or row.space_id != item.space_id or row.agent_id != item.agent_id):
            raise ReplyAuthorizationError("Queued reply no longer matches its durable inbound")
        if not self._route_authorized(item):
            raise ReplyAuthorizationError("Queued reply route authorization changed")

    async def poll_once(self) -> int:
        if not self.readiness()["ready"]:
            return 0
        since = self.store.load_session_start()
        start = datetime.fromisoformat(since)
        token: str | None = None
        seen_tokens: set[str] = set()
        ingested = 0
        # Rescan the persisted session to catch eventually consistent late rows.
        for _ in range(100):
            page = await self.transport.list_page(since, token)
            for item in page.items:
                try:
                    inbound = normalize(
                        item, self.settings.routes, start, project_id=self.settings.project_id
                    )
                except (AttributeError, TypeError, ValueError):
                    self.store.log_transport_error("unsupported_message", "schema branch")
                    continue
                if inbound is not None:
                    ingested += int(self.store.ingest_once(inbound))
            next_token = page.nextPageToken
            if not isinstance(next_token, str) or not next_token:
                return ingested
            if next_token in seen_tokens:
                raise ValueError("Repeated Photon page token")
            seen_tokens.add(next_token)
            token = next_token
        raise ValueError("Photon session exceeded 100 pages; start a new session")

    async def process_once(self, *, control: bool = False) -> bool:
        if not self.readiness()["ready"]:
            return False
        item = self.store.claim_control_inbound() if control else self.store.claim_inbound()
        if item is None:
            return False
        if not self._route_authorized(item):
            self.store.fail_inbound(item.id, "Route authorization changed")
            return True
        try:
            # STOP/CANCEL/APPROVE parsing and case revision checks belong to handler.
            text = await self.handler(item)
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Handler returned an empty reply")
            row = Outgoing(
                "reeftrace:reply:" + item.id, item.space_id, item.agent_id, item.id, text
            )
            # One transaction saves immutable body/key and marks inbox complete.
            self.store.finish_inbound(item.id, row)
        except (ValueError, KeyError, RuntimeError) as error:
            self.store.fail_inbound(item.id, type(error).__name__)
        return True

    async def send_once(self) -> bool:
        if not self.readiness()["ready"]:
            return False
        row = self.store.claim_outgoing()
        if row is None:
            return False
        try:
            # A retry or restart may occur after this route's role/cases were
            # revoked. Re-read completed durable input before every network send.
            self._authorize_queued_reply(row)
            status, request_id = await self.transport.send_saved(row)
            if status != 202:
                raise ValueError("Unexpected Photon acceptance status")
            # Accepted is NOT delivery/read confirmation.
            self.store.update_outgoing(row.key, "accepted", request_id=request_id)
        except Exception as error:  # noqa: BLE001 - durable boundary also accepts injected transports
            # Never store exception bodies, user text, credentials or raw response.
            status = getattr(error, "status", None)
            request_id = getattr(error, "request_id", None)
            terminal = status in {400, 401, 403, 404, 409, 422} or isinstance(error, ValueError)
            if status in {401, 403}:
                self._blocked = True
            self.store.update_outgoing(
                row.key,
                "failed" if terminal else "pending",
                request_id=request_id,
                error=type(error).__name__,
                retry_after_s=retry_delay(error),
            )
        return True

    async def _pause(self, stop: asyncio.Event, seconds: float) -> None:
        try:
            await asyncio.wait_for(stop.wait(), timeout=seconds)
        except TimeoutError:
            pass

    async def _poll_loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set() and not self._blocked:
            delay = self.settings.poll_interval_s
            try:
                await self.poll_once()
            except Exception as error:  # noqa: BLE001 - isolate optional SDK/transport failures
                status = getattr(error, "status", None)
                self.store.log_transport_error(
                    "photon_poll",
                    f"{type(error).__name__}; status={status}; "
                    f"request={getattr(error, 'request_id', None)}",
                )
                if status in {401, 403}:
                    self._blocked = True
                delay = retry_delay(error)
            await self._pause(stop, delay)

    async def _process_loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set() and not self._blocked:
            if not await self.process_once():
                await self._pause(stop, 0.2)

    async def _send_loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set() and not self._blocked:
            if not await self.send_once():
                await self._pause(stop, 0.2)

    async def _control_loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set() and not self._blocked:
            if not await self.process_once(control=True):
                await self._pause(stop, 0.1)

    async def run(self, stop: asyncio.Event) -> None:
        if not self.readiness()["ready"]:
            return
        tasks = [
            asyncio.create_task(loop(stop))
            for loop in (self._poll_loop, self._process_loop, self._control_loop, self._send_loop)
        ]
        stopper = asyncio.create_task(stop.wait())
        try:
            done, _ = await asyncio.wait([*tasks, stopper], return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()  # surface an unexpected processor/storage failure to the caller
        finally:
            for task in [*tasks, stopper]:
                task.cancel()
            await asyncio.gather(*tasks, stopper, return_exceptions=True)
            await self.transport.close()
