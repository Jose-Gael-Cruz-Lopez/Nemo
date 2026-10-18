"""Explicit project-authentication checks, isolated from polling and message delivery."""

from __future__ import annotations

import asyncio
import math
import threading
import time
from datetime import UTC, datetime

import httpx

SCOPE = "project_authentication_only"
VERIFY_TIMEOUT_S = 5.0
VERIFY_COOLDOWN_S = 10.0


class PhotonReadOnlyVerifier:
    """No SDK/client construction or network operation occurs before verify()."""

    def __init__(self, api_key="", project_id="", *, clock=time.monotonic):
        self._api_key = api_key.strip()
        self._project_id = project_id.strip()
        self._clock = clock
        self._lock = threading.Lock()
        self._busy = False
        self._next_allowed = 0.0
        self._checked_at = None

    def _result(self, status, **extra):
        return {"status": status, "checked_at": self._checked_at,
                "scope": SCOPE, "replies_enabled": False, **extra}

    def _enter(self):
        with self._lock:
            remaining = self._next_allowed - self._clock()
            if self._busy or remaining > 0:
                return self._result("COOLDOWN", retry_after_s=max(
                    1, math.ceil(VERIFY_COOLDOWN_S if self._busy else remaining)))
            self._busy = True
        return None

    async def verify(self, *, client: httpx.AsyncClient | None = None):
        """Perform exactly one official SDK GET, returning no project/user data.

        The optional client is only an injection seam for HTTP MockTransport tests.
        Credentials, base URL and project identity are never supplied by a request.
        """
        if not self._api_key or not self._project_id:
            return self._result("UNCONFIGURED")
        blocked = self._enter()
        if blocked is not None:
            return blocked
        status = "UNAVAILABLE"
        try:
            async with asyncio.timeout(VERIFY_TIMEOUT_S):
                status = await self._project_status(client)
        except (TimeoutError, httpx.TimeoutException):
            status = "TIMEOUT"
        except (ImportError, httpx.HTTPError, OSError, ValueError, TypeError, AttributeError):
            # Missing optional SDK, malformed response, and native/network errors
            # remain sanitized; cancellation is intentionally allowed to propagate.
            status = "UNAVAILABLE"
        finally:
            with self._lock:
                self._busy = False
                self._next_allowed = self._clock() + VERIFY_COOLDOWN_S
                self._checked_at = datetime.now(UTC).isoformat()
        return self._result(status)

    async def _project_status(self, client):
        # The optional sponsors dependency remains lazy and unrelated to
        # PhotonSettings.enabled, routes, worker or durable inbox/outbox.
        from photon_api import AsyncPhoton
        from photon_api.errors import PhotonError
        from photon_api.rpc_generated import GetProjectInput

        try:
            async with AsyncPhoton(base_url="https://api.photon.codes",
                    headers={"Authorization": "Bearer " + self._api_key},
                    timeout=VERIFY_TIMEOUT_S, max_attempts=1, client=client) as sdk:
                response = await sdk.raw.projects.get(GetProjectInput.model_validate(
                    {"path": {"projectId": self._project_id}}))
                return ("VERIFIED" if response.data.projectId == self._project_id
                        else "PROJECT_MISMATCH")
        except PhotonError as error:
            if getattr(error, "status", None) in {401, 403}:
                return "AUTH_FAILED"
            # The official SDK wraps httpx timeout errors in TransportError.
            cause = error
            for _ in range(4):
                if isinstance(cause, httpx.TimeoutException):
                    return "TIMEOUT"
                cause = cause.__cause__
                if cause is None:
                    break
            # Never expose exception strings, raw bodies, project data or headers.
            return "UNAVAILABLE"
