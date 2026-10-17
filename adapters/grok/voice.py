"""Deterministic evidence briefing and bounded server-side xAI Text to Speech.

The TTS provider speaks application-generated text; it does not decide the source.
Nothing reads .env, starts background work, sends messages or controls hardware.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from apps.ocean.reeftrace_ocean.satellite import DATA_ORIGIN, SAMPLE_SHA256, load_satellite_context

TTS_URL = "https://api.x.ai/v1/tts"
MAX_TEXT_CHARACTERS = 2000
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")


@dataclass(frozen=True)
class GrokVoiceSettings:
    enabled: bool = False
    api_key: str = field(default="", repr=False)
    request_timeout_s: float = 20.0
    max_audio_bytes: int = 2_000_000

    def readiness(self) -> dict[str, Any]:
        reasons = []
        if not self.enabled:
            reasons.append("disabled")
        if not isinstance(self.api_key, str) or not self.api_key.strip():
            reasons.append("missing_api_key")
        if (not isinstance(self.request_timeout_s, (int, float))
                or not math.isfinite(self.request_timeout_s)
                or not 0 < self.request_timeout_s <= 60
                or isinstance(self.max_audio_bytes, bool)
                or not isinstance(self.max_audio_bytes, int)
                or not 1 <= self.max_audio_bytes <= 5_000_000):
            reasons.append("invalid_limits")
        return {
            "provider": "xai", "capability": "text_to_speech", "enabled": self.enabled,
            "ready": not reasons, "connection_verified": False, "reasons": reasons,
        }


def _safe_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise ValueError(f"Invalid {label} identifier")
    return value


def _canonical_hash(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def build_briefing(source_report: dict, satellite_context: dict | None = None) -> dict:
    """Render frozen numerical evidence; never read arbitrary model-written narration.

    Supplied satellite context must match the pinned offline report exactly. The
    API must bind this source report to its authorized case and recheck revision
    before returning speech, just as it does for an LLM investigation.
    """
    if not isinstance(source_report, dict):
        raise TypeError("A frozen source report is required")
    # Snapshot caller-owned data before inspecting or rendering it.
    report = json.loads(json.dumps(source_report, allow_nan=False))
    status = report.get("status")
    if status not in {"ranked", "unknown", "invalid"}:
        raise ValueError("Unsupported source report status")
    case_id = _safe_id(report.get("case_id"), "case")
    evidence_id = report.get("id")
    if evidence_id is not None:
        evidence_id = _safe_id(evidence_id, "evidence")
    origin = report.get("data_origin", "UNVERIFIED")
    if origin not in {"SYNTHETIC", "MEASURED_TANK", "UNVERIFIED"}:
        raise ValueError("Unsupported source data origin")
    if report.get("confidence_kind") != "relative_support_not_probability":
        raise ValueError("Source support must retain its uncalibrated interpretation")
    intro = {
        "SYNTHETIC": "This is a synthetic tabletop tracing demonstration.",
        "MEASURED_TANK": "This is a controlled tabletop tracing observation.",
        "UNVERIFIED": "The origin of this tabletop evidence is unverified.",
    }[origin]
    if status == "ranked":
        source = _safe_id(report.get("ranked_source"), "source")
        support = report.get("relative_support")
        if not isinstance(support, dict) or source not in support or not 2 <= len(support) <= 8:
            raise ValueError("Ranked report requires its complete candidate support table")
        for key, value in support.items():
            _safe_id(key, "source")
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or not 0 <= value <= 1):
                raise ValueError("Invalid relative source support")
        if abs(sum(support.values()) - 1.0) > 1e-6 or support[source] < max(support.values()):
            raise ValueError("Ranked source contradicts its support table")
        source_text = (
            f"Source {source} has the strongest conditional fit among the declared entry points. "
            f"Its relative support is {100 * support[source]:.1f} percent. "
            "That is not a calibrated probability or proof of origin."
        )
    elif status == "unknown":
        if report.get("ranked_source") is not None:
            raise ValueError("An Unknown report cannot identify a ranked source")
        source_text = (
            "The source remains unknown. The available observations and model assumptions "
            "do not support a defensible ranking. More identifying evidence may be needed."
        )
    else:
        if report.get("ranked_source") is not None:
            raise ValueError("An invalid report cannot identify a ranked source")
        source_text = "The source analysis is invalid. Resolve its evidence or calibration " \
                      "problems before interpreting any source scores."
    expected = load_satellite_context()
    satellite = expected if satellite_context is None else satellite_context
    if not isinstance(satellite, dict) or satellite != expected:
        raise ValueError("Satellite briefing must use the integrity-verified historical context")
    summary = satellite["summary"]
    heat_text = (
        "Separately, a NOAA satellite-derived Florida Keys-area grid cell recorded "
        f"{summary['latest_dhw_c_weeks']:.2f} degree Celsius weeks of accumulated heat stress "
        "on July seventh, twenty twenty-three. This is historical reef heat context at "
        "approximately five kilometre resolution. It is not a measurement of this tank, "
        "proof of observed bleaching, or evidence of where the plastic came from. "
        "Satellite heat data did not change the source ranking."
    )
    text = f"{intro} {source_text} {heat_text} No hardware action is authorized by this briefing."
    return {
        "schema_version": 1,
        "text": text,
        "case_id": case_id,
        "source_evidence_id": evidence_id,
        "source_report_hash": _canonical_hash(report),
        "source_status": status,
        "source_data_origin": origin,
        "satellite_data_origin": DATA_ORIGIN,
        "satellite_sample_sha256": SAMPLE_SHA256,
        "satellite_used_in_source_ranking": False,
        "script_hash": hashlib.sha256(text.encode()).hexdigest(),
        "narration_method": "deterministic_frozen_evidence_template",
    }


def _failure(code: str, *, status_code: int | None = None) -> dict:
    result = {
        "ok": False, "provider": "xai", "capability": "text_to_speech",
        "failure_code": code, "live_provider_response": False,
        "message": "Voice briefing unavailable; the saved text and evidence remain available.",
    }
    if status_code is not None:
        result["provider_status_code"] = status_code
    return result


async def synthesize_briefing(
    briefing: dict, settings: GrokVoiceSettings, *, client: httpx.AsyncClient | None = None,
) -> dict:
    """One explicit speech request, no retries, redirects, messages or background work.

    Success includes bytes for a server audio response, not a JSON response.
    A supplied HTTP client remains owned by its caller. No upstream bodies or
    exception strings enter failures because they may contain sensitive details.
    """
    if not settings.readiness()["ready"]:
        return _failure("NOT_CONFIGURED")
    if (not isinstance(briefing, dict)
            or briefing.get("narration_method") != "deterministic_frozen_evidence_template"
            or briefing.get("satellite_used_in_source_ranking") is not False):
        return _failure("INVALID_BRIEFING")
    text = briefing.get("text")
    if (not isinstance(text, str) or not 1 <= len(text) <= MAX_TEXT_CHARACTERS
            or briefing.get("script_hash") != hashlib.sha256(text.encode()).hexdigest()):
        return _failure("INVALID_BRIEFING")
    owned = client is None
    http = client or httpx.AsyncClient(follow_redirects=False)
    try:
        async with asyncio.timeout(settings.request_timeout_s):
            async with http.stream(
                "POST", TTS_URL,
                headers={"Authorization": "Bearer " + settings.api_key,
                         "Content-Type": "application/json"},
                json={"text": text, "voice_id": "eve", "language": "en"},
                timeout=settings.request_timeout_s, follow_redirects=False,
            ) as response:
                response.raise_for_status()
                if response.headers.get("content-type", "").split(";", 1)[0] != "audio/mpeg":
                    return _failure("INVALID_AUDIO_RESPONSE")
                length = response.headers.get("content-length")
                if length and (not length.isdigit() or int(length) > settings.max_audio_bytes):
                    return _failure("AUDIO_SIZE_LIMIT")
                audio = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=16384):
                    if len(audio) + len(chunk) > settings.max_audio_bytes:
                        return _failure("AUDIO_SIZE_LIMIT")
                    audio.extend(chunk)
                if not audio:
                    return _failure("INVALID_AUDIO_RESPONSE")
                return {
                    "ok": True, "audio_bytes": bytes(audio), "content_type": "audio/mpeg",
                    "provider": "xai", "capability": "text_to_speech",
                    "live_provider_response": True, "voice_id": "eve",
                    "script_hash": briefing["script_hash"],
                    "source_report_hash": briefing.get("source_report_hash"),
                }
    except httpx.HTTPStatusError as error:
        return _failure("PROVIDER_HTTP_ERROR", status_code=error.response.status_code)
    except (httpx.HTTPError, TimeoutError):
        return _failure("PROVIDER_CONNECTION_OR_TIMEOUT")
    finally:
        if owned:
            await http.aclose()
