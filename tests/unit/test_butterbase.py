import asyncio

import httpx
import pytest

from apps.core.reeftrace_core.butterbase import (
    ButterbaseConfig,
    ButterbaseError,
    butterbase_completion,
    checked_json,
)


def configured(monkeypatch):
    monkeypatch.setenv("BUTTERBASE_API_URL", "https://api.butterbase.ai")
    monkeypatch.setenv("BUTTERBASE_API_KEY", "bb_sk_test-only-not-a-real-key")
    monkeypatch.setenv("BUTTERBASE_MODEL", "fixture/model")
    monkeypatch.setenv("BUTTERBASE_ACCOUNT_ID", "88f8efa4-330d-4a0c-b570-0ea1858f446d")


def test_account_id_is_not_a_credential_and_public_catalog_needs_no_key(monkeypatch):
    monkeypatch.delenv("BUTTERBASE_API_KEY", raising=False)
    monkeypatch.delenv("BUTTERBASE_MODEL", raising=False)
    monkeypatch.setenv("BUTTERBASE_API_URL", "https://api.butterbase.ai")
    config = ButterbaseConfig.from_env(require_key=False)
    assert config.headers() == {}
    assert config.endpoint("public/models") == "https://api.butterbase.ai/v1/public/models"
    with pytest.raises(RuntimeError, match="personal key"):
        ButterbaseConfig.from_env()
    monkeypatch.setenv("BUTTERBASE_API_KEY", "88f8efa4-330d-4a0c-b570-0ea1858f446d")
    with pytest.raises(ValueError, match="contains an ID"):
        ButterbaseConfig.from_env()


def test_reject_insecure_or_malformed_gateway_url(monkeypatch):
    for url in [
        "http://api.butterbase.ai",
        "https://api.butterbase.ai/v1",
        "https://secret@example.org",
        "https://example.org?key=secret",
    ]:
        monkeypatch.setenv("BUTTERBASE_API_URL", url)
        with pytest.raises(ValueError, match="HTTPS service origin"):
            ButterbaseConfig.from_env(require_key=False)


def test_completion_uses_documented_gateway_without_account_header(monkeypatch):
    configured(monkeypatch)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"tool":"get_case","arguments":{}}'}}]}
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    output = asyncio.run(
        butterbase_completion([{"role": "user", "content": "Explain the evidence"}])
    )
    assert output == '{"tool":"get_case","arguments":{}}'
    assert str(requests[0].url) == "https://api.butterbase.ai/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer bb_sk_test-only-not-a-real-key"
    assert "88f8efa4" not in str(requests[0].headers)
    assert b"fixture/model" in requests[0].content


@pytest.mark.parametrize("status", [401, 402, 403, 404, 429, 500])
def test_error_guidance_never_echoes_vendor_secrets(status):
    response = httpx.Response(status, json={"error": {"message": "sensitive-key-value"}})
    with pytest.raises(ButterbaseError) as error:
        checked_json(response)
    assert error.value.status_code == status
    assert "sensitive-key-value" not in str(error.value)


def test_model_required_for_investigation(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setenv("BUTTERBASE_MODEL", "")
    with pytest.raises(RuntimeError, match="BUTTERBASE_MODEL"):
        asyncio.run(butterbase_completion([]))
