"""Server-side Butterbase AI gateway adapter. Account IDs are metadata, not credentials."""

import os
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import UUID

import httpx

DEFAULT_API_URL = "https://api.butterbase.ai"
ERROR_HINTS = {
    400: "Request rejected; check the model and supported request parameters.",
    401: "Personal API key missing, invalid or revoked. Your account ID is not an API key.",
    402: "Butterbase reports insufficient credits; review the account balance.",
    403: "Access denied; the personal API key needs ai:gateway permission.",
    404: "Model or endpoint not found; select an exact ID returned by the model list.",
    429: "Rate limited; wait before retrying.",
}


class ButterbaseError(RuntimeError):
    def __init__(self, status_code):
        self.status_code = status_code
        hint = ERROR_HINTS.get(status_code, "Butterbase is unavailable; retry later.")
        super().__init__(f"Butterbase HTTP {status_code}: {hint}")


@dataclass(frozen=True)
class ButterbaseConfig:
    api_url: str
    api_key: str
    model: str
    account_id: str

    @classmethod
    def from_env(cls, *, require_key=True, require_model=False):
        url = (os.environ.get("BUTTERBASE_API_URL") or DEFAULT_API_URL).rstrip("/")
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError(
                "BUTTERBASE_API_URL must be an HTTPS service origin, without /v1, credentials or query parameters"
            )
        key = (os.environ.get("BUTTERBASE_API_KEY") or "").strip()
        model = (os.environ.get("BUTTERBASE_MODEL") or "").strip()
        account = (os.environ.get("BUTTERBASE_ACCOUNT_ID") or "").strip()
        if require_key and not key:
            raise RuntimeError(
                "Set BUTTERBASE_API_KEY in .env to a personal key with ai:gateway scope"
            )
        if key:
            try:
                UUID(key)
            except ValueError:
                pass
            else:
                raise ValueError(
                    "BUTTERBASE_API_KEY contains an ID; use a personal API key instead"
                )
        if require_model and not model:
            raise RuntimeError(
                "Set BUTTERBASE_MODEL to an exact ID returned by scripts/check_butterbase.py"
            )
        return cls(url, key, model, account)

    def headers(self):
        return {"Authorization": "Bearer " + self.api_key} if self.api_key else {}

    def endpoint(self, path):
        return self.api_url + "/v1/" + path.lstrip("/")


def checked_json(response):
    if response.status_code >= 400:
        # Raw vendor errors can echo credentials; never expose their bodies.
        raise ButterbaseError(response.status_code)
    return response.json()


async def butterbase_completion(messages):
    config = ButterbaseConfig.from_env(require_model=True)
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        response = await client.post(
            config.endpoint("chat/completions"),
            headers=config.headers(),
            json={"model": config.model, "messages": messages, "max_tokens": 1200, "stream": False},
        )
        payload = checked_json(response)
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError("Butterbase returned an unsupported completion response") from error
        if not isinstance(content, str):
            raise TypeError("Butterbase completion content must be text")
        return content
