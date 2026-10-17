import asyncio

import httpx
import pytest

from adapters.gemini import client as ai


def test_missing_key_never_calls_network(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="Set GEMINI_API_KEY"):
        asyncio.run(ai.gemini_completion([]))


@pytest.mark.parametrize("status,finish", [(200, "stop"), (200, "length"), (429, "stop")])
def test_gemini_protocol_and_safe_errors(monkeypatch, status, finish):
    monkeypatch.setenv("GEMINI_ENABLED", "true")
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


def test_disabled_gemini_never_calls_network_even_with_credentials(monkeypatch):
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")

    def unexpected_client(**kwargs):
        raise AssertionError("Disabled inference must not create an HTTP client")

    monkeypatch.setattr(ai.httpx, "AsyncClient", unexpected_client)
    with pytest.raises(RuntimeError, match="enable GEMINI_ENABLED"):
        asyncio.run(ai.gemini_completion([]))
