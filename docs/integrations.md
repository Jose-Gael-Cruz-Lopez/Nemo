# Chalk and Photon integration

The camera, inference, evidence tables and manual recovery workflow run locally.
Sponsor adapters are optional. `readiness()` reports configuration and installed SDK
availability; `connection_verified: false` means it is **not** a live connectivity test.
Neither adapter reads process environment variables. Application settings create the
dataclasses and inject credentials once. Never send credentials to the browser.

## Current live verification status — 16 October 2026

The local product's full HTTP audit completed with **18 PASS, 0 FAIL and 3 BLOCKED** checks. Physical webcam/tank commissioning and a complete Photon device conversation remain separate from that software pass. Chalk was subsequently verified through the live investigation described below.

Photon Beta authentication has been tested against the real service. After the user's approval, a 30-day custom project key with `project:read` and `project:write` permissions was stored only in private `.env`. The official Python SDK's read-only `raw.projects.list_messages` call returned **HTTP 200**, and the response passed SDK schema validation. `work/photon-live-auth.json` records the verification without account IDs or secrets. The Photon dashboard now shows the user's shared-line assignment as **Active**, and the exact observed sender/agent pair is saved privately in a route restricted to one synthetic case. This does not establish a delivered agent conversation. **The user's latest instruction prohibits test messages and automatic replies: `PHOTON_ENABLED=false` must remain in force.** No Photon message has been sent by the agent. After the local API restart, readiness has only the expected `disabled` reason; readiness remains separate from live connectivity verification.

The existing Google Gemini free-tier key was connected to the teammate-authorized Chalk environment using the native Gemini provider. Chalk's connection test succeeded and discovered 63 models. A new gateway key was issued privately, restricted to that Gemini connection. The user approved connection-wide model scope because Chalk's key picker did not expose the discovered model list. The user separately approved omitting a gateway daily token budget because Chalk's server rejected budgeted keys with `quota enforcement is disabled (set ROUTER_QUOTA_BACKEND)`. **There is no gateway-enforced daily token cap.** ReefTrace requests only `gemini/gemini-3.8-flash`, retains its bounded tool/request deadlines, and Google billing remains on the existing free tier.

A real gateway request returned HTTP 200. An initial investigation hit a transient provider HTTP 503 after reading the case; a later bounded investigation completed with `provider: chalk`, `live_model_response: true`, `action: REPORT`, successful case/source tool reads and the actual frozen evidence ID. The exact source report remained unchanged and retained `SYNTHETIC` and `physical_validation: false`. Private local receipts record the result without publishing credentials. Readiness remains a configuration check (`connection_verified: false`); this separate successful investigation is the live evidence. No remote Chalk evaluation run has been deployed.

## Grok and satellite context

The Grok project has detailed instructions and an actual source-based ML review conversation. Cursor, using its Grok model, is implementing the reviewed training-only diagnostic. These coding activities are distinct from use of the Grok Voice API.

The application now has a deterministic frozen-evidence briefing, a pinned real NOAA satellite-derived DHW time series, and a server-side xAI text-to-speech adapter. Audio generation requires an explicit operator click and `GROK_VOICE_ENABLED=true` plus private `XAI_API_KEY`. The user selected finishing without a live key because their API dashboard requires a payment method and prepaid credits. Voice remains disabled; passing mocked adapter tests does not prove a live Grok call or completed sponsor eligibility. See [satellite and speech contract](grok-space-context.md).

Satellite heat stress is historical ecological context for a Florida Keys-area grid cell, not a tank observation, confirmed bleaching, plastic provenance, or input to source ranking. Its independent origin and limitations are retained in the UI and spoken script.
## Chalk

`ChalkSettings` takes `enabled`, `base_url`, `api_key`, `environment_id`, `model`,
`turn_timeout_s=60` and `request_timeout_s=15`. Obtain a scoped gateway key and a model
permitted by the selected environment; the official [gateway setup](https://docs.chalk.ai/docs/model-gateway)
explains provisioning. Event credits are not assumed.

```python
from adapters.chalk import ChalkSettings, investigate

# backend is already bound to an authenticated case and allowed actions.
answer = await investigate(
    "Why is this source ambiguous?", backend,
    {"case_id": case_id, "revision": revision},
    ChalkSettings(enabled=True, api_key=router_key,
                  environment_id=environment_id, model=model_id),
)
```

The backend implements `async call(name, arguments) -> dict`. Registered tools are
`get_case`, `get_source_evidence`, `run_predeclared_sensitivity(preset_id)`,
`observe_again`, and `propose_collection(evidence_id)`. The application validates the
registered preset, current evidence, role and state. Each successful tool result
contains `ok: true` and `evidence_ids: list[str]`; proposal results additionally contain
`proposal_id`. Failed results use `ok: false` and do not establish grounding.

Only returned evidence/proposal IDs are accepted at finish. There are at most nine
model calls, two case/source reads each, and one call per other tool. Invalid output,
HTTP errors, or timeout produce STOP, without authorization. The final answer is a
structured choice, cited IDs and short explanation. **The application renders all
source scores from the frozen deterministic report.** Digits in generated explanations
are rejected; put IDs only in their separate fields. Valid ID citations do not
guarantee that every generated sentence is correct. Recheck case revision before
committing an investigation, especially after a concurrent STOP.

The adapter never authorizes a recovery task or switches a pump. A
REQUEST_APPROVAL finish only cites a proposal already created by the local backend.
Runtime cancels invocation-owned proposals after failure, cancellation, STOP or an
unused proposal finish; an expiry alone would leave an approval-capable orphan.

For a remote sponsor evaluation, use frozen fixture backends, `chalkcompute` tasks,
and the [evaluation quick start](https://docs.chalk.ai/docs/evaluations/quick-start).
Test grounding/unknown preservation and illegal actions as well as JSON validity.
Cloud evaluations require a configured account and remote Function queue; passing
local pytest tests is not proof of a completed Chalk evaluation.

### Reproduce agent-policy evaluation

Run the default rehearsal without a model key or cloud deployment:

```sh
python -m adapters.chalk.evaluate --mode local --output data/local/agent-contract.json
```

This passes four explicitly hand-authored development fixtures through the **same**
agent using scripted HTTP responses and a frozen ReplayBackend. It measures structure,
returned IDs, tool policy, preservation of Unknown/invalid status, and numerical-field
authority. It reports `real_model_evaluation: false` and zero valid live responses.
These results verify the agent's contract; they do not estimate an LLM's accuracy or
physical source-identification accuracy.

After configuring the gateway, use `--live-model` for a genuine model evaluation on
the local machine. `.env` is read only at the CLI boundary. This makes metered model
requests but does not deploy functions or access hardware.

For Chalk-hosted evaluation, install `pip install -e '.[evaluations]'`, authenticate
the Chalk CLI, select the intended environment, and run explicitly:

```sh
python -m adapters.chalk.evaluate --mode remote --git-sha YOUR_COMMIT_SHA --output data/local/chalk-evaluation.json
```

This uploads frozen rows and deploys the task/scorers, then saves evaluation/run IDs,
result dataset identifiers and row-level errors. `model_response_valid` distinguishes
a valid model finish from a safe fallback after model failure. A completed run can
contain failed rows; inspect its saved errors and all score columns.

The task receives only `fixture_json` and `request`. Allowed-action and evidence labels
are separate scorer arguments; scripted model commands are never uploaded. Fixtures
with hidden truth/scorer-label keys in their model input are rejected. The remote task
imports the shared agent and only the frozen backend; it has no camera, Store, Photon
or physical-action path. Dry-run proposal IDs are never valid local application tasks.
Use a separate frozen JSONL file with `--fixtures PATH --split test` for held-out data;
the built-in development fixtures cannot be relabeled as a test split.

Current constructors and signatures were checked against installed **chalkcompute
2.13.7** and **pyarrow 26.0.0**. Importing a real `@chalkcompute.function` definition
immediately queues deployment. Therefore `evaluation_tasks.py` is imported only by
explicit remote mode; the offline app never imports it. Offline declaration tests
replace deployment decorators while retaining the actual SDK Image/Secret constructors.
No remote function or evaluation run was exercised during this build. A separate live
gateway investigation was subsequently verified as described above. [Function packaging](https://docs.chalk.ai/docs/functions/defining-a-function)
and [image APIs](https://docs.chalk.ai/docs/compute/images) document the deployment contract.

## Photon 2.0

Install the optional pinned dependency with `pip install -e '.[sponsors]'`. The API is
Photon **Beta**, package `photonhq-api==0.5.0`, import `photon_api`, bearer project key,
base `https://api.photon.codes`. [Official iMessage setup](https://photon.codes/docs/beta/get-started/imessage)
requires an assigned sender and a human-initiated conversation. Use a prepared operator
phone; a judge's unassigned number cannot be assumed to work. Stable Spectrum examples
use a different product contract.

```python
from adapters.photon import PhotonSettings, PhotonWorker, RouteConfig

settings = PhotonSettings(
    enabled=True, api_key=project_key, project_id=project_id,
    routes=(RouteConfig(human_handle, agent_handle, "operator", (case_id,)),),
)
# Bind this data directory to this project before enabling the worker.
store.bind_photon_project(project_id)
worker = PhotonWorker(settings, store, handle_authenticated_message)
await worker.run(stop_event)
```

Leave `enabled=False` until credentials, the authorized route, and an intended live
channel are configured. Enabling polling also enables replies to accepted inbound
messages. No account creation, channel assignment, or unsolicited first contact is
performed by this adapter. Tests use fake transports or SDK HTTP mocks; they never
send external messages.

RouteConfig contains exact observed `human_handle`, `agent_handle`, `role`, and
`allowed_cases`. Inbound includes the canonical human ID, agent ID, direct space ID,
message ID, timestamp and text. Check authorization against current routes again when
claiming a saved inbound message. Root command parsing must use strict full-command
grammar; quoted prose mentioning APPROVE must not approve anything. STOP means stop
the software task and invalidate proposals; the AC circulation pump stays manually
powered and running unless the operator unplugs it.

`PhotonWorker` runs polling, ordinary investigation, control commands and outbox
delivery separately. Store methods are short synchronous transactions:

```text
load_session_start() -> str
ingest_once(Inbound) -> bool
claim_inbound() -> Inbound | None
claim_control_inbound() -> Inbound | None
finish_inbound(inbound_id, Outgoing) -> None  # atomically save reply + complete inbox
fail_inbound(inbound_id, error) -> None
claim_outgoing() -> Outgoing | None
update_outgoing(key, status, *, request_id=None, error=None, retry_after_s=None) -> None
log_transport_error(kind, detail) -> None
```

The two inbound claim methods must claim disjoint queues. Leases must exceed handler
deadlines and permit recovery after a process crash. Reply key
`reeftrace:reply:<incoming-id>` and its immutable body are saved before sending. The
sender is the received agent ID, not the human sender ID. A timed-out write retries
with exactly the same saved body/key. The outbox uses `pending` for retry, `accepted`
for HTTP 202, and `failed` for permanent rejection. **Accepted is not delivered/read.**
401/403 block all worker lanes until configuration is fixed and restarted.

Polling scans from the persisted RFC3339 session start and deduplicates IDs, following
page tokens even across empty pages. This handles late indexing without exposing a
webhook or tunnel. Start a new intentionally scoped demo session to avoid accepting
old approvals; never delete inbox deduplication records while reusing its session start.

Official contracts: [SDK source](https://github.com/photon-hq/api/tree/main/packages/python),
[pagination](https://photon.codes/docs/beta/api-client/pagination),
[raw responses](https://photon.codes/docs/beta/api-client/raw-responses),
[retries/timeouts](https://photon.codes/docs/beta/api-client/retries-and-timeouts).

## Verification boundaries

Run `python -m pytest -q tests/test_chalk.py tests/test_photon.py`. The current tests
check malformed/unauthorized tools, returned evidence/proposal IDs, deadlines,
generated SDK request/response contracts, route filtering, session rescans, deduplication,
durable-before-send ordering and identical retries. With the sponsors extra absent,
the application starts offline and SDK contract tests skip.

Chalk has separate live model proof as described above; Photon still needs an authorized
phone round trip before any conversation claim. Demo evidence should name the configured model, case/evidence IDs, tool trace,
inbound message ID and accepted request ID; do not label mocks as live sponsor calls.
