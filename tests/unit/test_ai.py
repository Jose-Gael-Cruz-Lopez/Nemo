import asyncio

import httpx
import pytest

from apps.core.reeftrace_core import ai


def test_missing_key_never_calls_network(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="Set GEMINI_API_KEY"):
        asyncio.run(ai.gemini_completion([]))


@pytest.mark.parametrize("status,finish", [(200, "stop"), (200, "length"), (429, "stop")])
def test_gemini_protocol_and_safe_errors(monkeypatch, status, finish):
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    original_client = httpx.AsyncClient

    def handler(request):
        assert request.url.host == "generativelanguage.googleapis.com"
        assert request.headers["Authorization"] == "Bearer test-secret"
        return httpx.Response(status, json={
            "choices": [{"finish_reason": finish, "message": {"content": '{"ok":true}'}}],
            "error": "test-secret",
        })

    monkeypatch.setattr(ai.httpx, "AsyncClient", lambda **kw: original_client(
        transport=httpx.MockTransport(handler), **kw
    ))
    if status == 429:
        with pytest.raises(RuntimeError, match="Free quota") as error:
            asyncio.run(ai.gemini_completion([]))
        assert "test-secret" not in str(error.value)
    elif finish == "length":
        with pytest.raises(ValueError, match="incomplete"):
            asyncio.run(ai.gemini_completion([]))
    else:
        assert asyncio.run(ai.gemini_completion([])) == '{"ok":true}'
