"""Selectable server-side AI provider; credentials never enter the dashboard."""

import os

import httpx

from .butterbase import butterbase_completion


def ai_provider():
    provider = os.environ.get("REEFTRACE_AI_PROVIDER", "gemini").strip().lower()
    if provider not in {"gemini", "butterbase"}:
        raise ValueError("REEFTRACE_AI_PROVIDER must be gemini or butterbase")
    return provider


def gemini_key():
    return (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()


def ai_configured():
    if ai_provider() == "gemini":
        return bool(gemini_key() and os.environ.get("GEMINI_MODEL"))
    return bool(os.environ.get("BUTTERBASE_API_KEY") and os.environ.get("BUTTERBASE_MODEL"))


async def gemini_completion(messages):
    key = gemini_key()
    model = os.environ.get("GEMINI_MODEL", "").strip()
    if not key or not model:
        raise RuntimeError("Set GEMINI_API_KEY and GEMINI_MODEL in .env")
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        response = await client.post(
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            headers={"Authorization": "Bearer " + key},
            json={
                "model": model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "max_tokens": 4096,
                "stream": False,
            },
        )
    if response.status_code >= 400:
        hints = {
            400: "Check model availability and request parameters.",
            401: "Check your Gemini API key.",
            403: "Check API key permissions and account access.",
            404: "Choose an available GEMINI_MODEL.",
            429: "Free quota or rate limit reached; retry later.",
        }
        raise RuntimeError(
            f"Gemini HTTP {response.status_code}: "
            + hints.get(response.status_code, "Provider unavailable; retry later.")
        )
    try:
        choice = response.json()["choices"][0]
        content = choice["message"]["content"]
        if choice.get("finish_reason") != "stop" or not isinstance(content, str) or not content:
            raise ValueError("Gemini returned an incomplete or empty response")
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("Gemini returned an unsupported response") from error
    return content


async def ai_completion(messages):
    if ai_provider() == "butterbase":
        return await butterbase_completion(messages)
    return await gemini_completion(messages)
