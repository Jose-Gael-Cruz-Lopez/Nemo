# ReefTrace: satellite context and an evidence-grounded voice briefing

This feature preserves source tracing as the core. It joins two explicitly separate views: a frozen tabletop source report and a real historical satellite-derived reef thermal-stress series. A user can read or listen to the same short, deterministic briefing. Satellite heat context never changes source scores, release ages, priors or a confidence gate.

## Exact implemented contracts

```python
from apps.ocean.reeftrace_ocean.satellite import load_satellite_context
from adapters.grok import GrokVoiceSettings, build_briefing, synthesize_briefing

context = load_satellite_context()          # Offline; verifies reviewed bytes and provenance.
briefing = build_briefing(frozen_source_report, context)
settings = GrokVoiceSettings(enabled=False) # Default: no provider requests.
result = await synthesize_briefing(briefing, settings)
```

These modules do not read `.env`, launch workers, send phone messages, invoke Photon, change Gemini, start cameras or actuate hardware. The application supplies settings and the authorized, saved numerical report. A success contains `audio_bytes` for an `audio/mpeg` HTTP response; the whole result is not JSON serializable. A failure contains a safe `failure_code`, optional upstream status and no audio, key, response body or exception string.

**Application integration requirements:** bind the click endpoint to the authorized case; generate its briefing on the server from the saved report; recheck the case revision and stopped state before returning audio. Do not accept arbitrary narration, a client-supplied source report or a script hash as authorization. Hashes identify frozen inputs and detect changes; they are not signatures. The audio endpoint is an explicit user action with no automatic retries or preloading. Display the written text even when voice is unavailable.

`build_briefing` preserves ranked/Unknown/Invalid, labels synthetic observations, retains “relative support is not probability,” rejects contradictory source support, and requires any supplied satellite context to equal the verified offline record. It does not use arbitrary notes or LLM narration. The speech provider therefore does not generate a new source conclusion or invent a heat value.

## The real space-data artifact

Provider: NOAA Coral Reef Watch. Product: daily global 5 km satellite-derived Degree Heating Week (DHW), version 3.1. Dataset ID: `noaacrwdhwDaily`. Variable: `degree_heating_week`, units `degree_Celsius_weeks`. Coordinates: **24.575° N, 81.525° W**, one ocean grid cell in the Florida Keys area. Dates: **1–7 July 2023, 12:00 UTC daily**. The dataset is derived from a Level 4 satellite sea-surface-temperature analysis; the metadata lists satellite and in situ source instruments, so this is an analyzed satellite-derived product rather than seven raw satellite images. [NOAA metadata](https://coastwatch.noaa.gov/erddap/info/noaacrwdhwDaily/index.html).

Verified raw CSV: `data/public/noaa-coral-context/noaa-crw-dhw-florida-keys-20230701-20230707.csv`, **383 bytes**, seven rows. SHA-256:

```text
5e3248ce6247aece0d5736678bba36010cb4b0a2053c40e1ba7b69bba125c101
```

The matching `.provenance.json` records the exact HTTPS request, retrieval UTC time, units, attribution and digest. The loader checks both bytes against a code-pinned digest and every reviewed manifest field. It rejects missing units, wrong coordinates, timestamps, extra rows, missing values and inconsistent provenance. A data hash cannot establish that NOAA's physical analysis is error-free; it ensures the reproducible fixture is the reviewed source artifact.

| Date in July 2023 | DHW, °C-weeks |
|---|---:|
| 1 | 2.96 |
| 2 | 3.18 |
| 3 | 3.43 |
| 4 | 3.72 |
| 5 | 3.99 |
| 6 | 4.24 |
| 7 | 4.53 |

DHW accumulates heat stress over the previous twelve weeks. NOAA associates **4 °C-weeks with bleaching risk**; a displayed value is not direct confirmation that coral bleached. This seven-day excerpt reads NOAA's already computed DHW rather than attempting to reconstruct twelve weeks from seven days. The fixed historical cell is not current conditions, a measurement of the tank, a current field, a plastic detector or source-attribution ground truth. [NOAA DHW explanation](https://coralreefwatch.noaa.gov/product/5km/index_5km_dhw.php).

NOAA metadata permits unrestricted use of CRW data while requesting source attribution/citation. Preserve NOAA credit and the product/version/source links. A separately designed future operational triage policy could combine an actual geolocated debris observation and contemporaneous heat context; the present demo does not validate such a policy or measure a cleanup benefit.

Reproduce the source fetch, without an account or credential:

```sh
.venv/bin/python scripts/fetch_satellite_context.py
```

The script refuses an existing fixture unless `--force` is supplied. Even with `--force`, changed source bytes fail the reviewed hash rather than silently redefining the demonstration. Network retrieval is capped at sixteen kilobytes, has a thirty-second timeout and refuses redirects. Ordinary dashboard reads load the local fixture, with no NOAA network dependency. The date and location are deliberately fixed for reproducibility; the UI must not call the result live.

## xAI Voice implementation

The minimal operation is server-side **POST `https://api.x.ai/v1/tts`**, using `Authorization: Bearer <XAI_API_KEY>` and JSON `{text, voice_id:"eve", language:"en"}`. The documented default response is raw MP3 audio. The basic request has no model field; do not invent a `grok-*` text-model ID for this TTS endpoint. [Official Text to Speech documentation](https://docs.x.ai/developers/model-capabilities/audio/text-to-speech).

`GrokVoiceSettings` defaults to disabled, hides the key from its representation, limits requests to twenty seconds by default and output to two megabytes. `synthesize_briefing` validates the frozen script hash, requests the fixed HTTPS endpoint, rejects redirects, does not retry, requires MP3 content type, and enforces declared and streamed audio-size limits. Provider errors return sanitized status only. The permanent API key stays in the server; never place it in browser code or a public environment variable. A valid account/key and usable quota are still needed; offline mock tests are not live provider commissioning.

## If the challenge specifically requires interactive Grok Voice

Text to Speech is documented under xAI's Voice APIs. Challenge interpretation belongs to the organizers; do not claim this automatically satisfies a narrower requirement for a conversational voice agent. The documented interactive route is **`wss://api.x.ai/v1/realtime?model=grok-voice-3.0`**. Currently `grok-voice-latest` aliases that version. Configure with `session.update`, send a text message with `conversation.item.create` and `input_text`, then request `response.create`. Receive `response.output_audio.delta` and `response.done`. Versioned model selection avoids an alias changing during a demo. [Speech to Speech documentation](https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech).

A browser may use a short-lived token issued by a server POST to **`https://api.x.ai/v1/realtime/client_secrets`**, with an `expires_after.seconds` value such as 300. Use browser WebSocket protocol `xai-client-secret.<ephemeral-token>`; never expose the permanent API key. The token endpoint must itself be authenticated and bounded. This is a future extension, not part of the implemented TTS adapter. [Official ephemeral tokens](https://docs.x.ai/developers/model-capabilities/audio/ephemeral-tokens).

The current requirements mentioned by the team also include Cursor and real space data. This module supplies real satellite-derived context and an xAI speech integration path; code running in another editor is not evidence of Cursor use. Preserve real build evidence and verify the event's precise submission requirements without inventing sponsor eligibility.

## Verification

```sh
.venv/bin/python -m pytest tests/test_grok.py tests/unit/test_satellite.py -q
.venv/bin/ruff check adapters/grok apps/ocean/reeftrace_ocean/satellite.py \
  scripts/fetch_satellite_context.py tests/test_grok.py tests/unit/test_satellite.py
```

The tests are offline. They cover provenance tampering, dimensional/date/location errors, frozen briefing semantics, Unknown/Invalid preservation, unsupported input, disabled/no-key behavior, exact outgoing TTS contract, no redirect/retry, timeout, size/content failures and secret-safe errors. Physical tracing validation, a successful paid-provider call, and challenge submission remain distinct from these software checks.
