"""Shared server-only Gemini configuration and validated JSON completion transport."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass(frozen=True)
class GeminiSettings:
    enabled: bool = False
    base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    api_key: str = field(default="", repr=False)
    model: str = ""
    turn_timeout_s: float = 60.0
    request_timeout_s: float = 25.0

    @classmethod
    def from_env(cls):
        return cls(
            enabled=os.getenv("GEMINI_ENABLED", "true").lower() == "true",
            api_key=(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")).strip(),
            model=os.getenv("GEMINI_MODEL", "").strip(),
        )

    def readiness(self) -> dict[str, Any]:
        reasons = []
        if not self.enabled:
            reasons.append("disabled")
        if not self.api_key:
            reasons.append("missing_api_key")
        if not self.model:
            reasons.append("missing_model")
        return {"provider": "gemini", "enabled": self.enabled, "ready": not reasons,
                "connection_verified": False, "reasons": reasons}


class GeminiHTTPError(RuntimeError):
    """Provider status without its potentially sensitive body or request details."""

    def __init__(self, status_code):
        self.status_code = status_code
        hints = {
            400: "Check model availability and request parameters.",
            401: "Check your Gemini API key.",
            403: "Check API key permissions and account access.",
            404: "Choose an available GEMINI_MODEL.",
            429: "Free quota or rate limit reached; retry later.",
        }
        super().__init__(f"Gemini HTTP {status_code}: " + hints.get(
            status_code, "Provider unavailable; retry later."))


async def gemini_completion(messages, settings=None, *, client=None, timeout=None, schema=None):
    settings = settings or GeminiSettings.from_env()
    if not settings.readiness()["ready"]:
        raise RuntimeError("Set GEMINI_API_KEY and GEMINI_MODEL; enable GEMINI_ENABLED")
    owned = client is None
    http = client or httpx.AsyncClient(follow_redirects=False)
    try:
        response = await http.post(
            settings.base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": "Bearer " + settings.api_key},
            json={"model": settings.model, "messages": messages,
                  "response_format": ({"type": "json_schema", "json_schema": {
                      "name": "reeftrace_command", "strict": True, "schema": schema,
                  }} if schema is not None else {"type": "json_object"}), "max_tokens": 4096},
            timeout=timeout if timeout is not None else settings.request_timeout_s,
        )
        if response.status_code >= 400:
            raise GeminiHTTPError(response.status_code)
        try:
            choice = response.json()["choices"][0]
            content = choice["message"]["content"]
            if (choice.get("finish_reason", "stop") != "stop"
                    or not isinstance(content, str) or not content or len(content) > 12000):
                raise ValueError("Gemini returned an incomplete or invalid response")
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError("Gemini returned an unsupported response") from error
        return content
    finally:
        if owned:
            await http.aclose()
