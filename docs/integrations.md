# Gemini, Postgres and Photon integration

This branch replaces Chalk Model Gateway with the direct Gemini API. Main's
case-bound tool loop, frozen numerical reports, revision checks, bounded tools,
manual recovery approvals and Photon queue behavior are retained.

## Gemini

Set `REEFTRACE_AI_PROVIDER=gemini`, `GEMINI_API_KEY` and `GEMINI_MODEL` in ignored
`.env`. `GEMINI_ENABLED` defaults to true; false disables inference. Configuration
readiness does not prove a live request. `GeminiSettings` accepts enabled,
base_url, api_key, model, turn_timeout_s and request_timeout_s. Defaults use
`https://generativelanguage.googleapis.com/v1beta/openai/chat/completions`, a
server-only Bearer key and JSON output. No environment ID is required.

The same agent serves the new dashboard and Photon. Source numbers stay in the
authoritative report; numerical generated prose is rejected. Unknown/invalid
reports cannot be upgraded by the model. Manual proposals require returned
current evidence; the model never approves or actuates hardware.

Run `python -m scripts.check_gemini --test` to check a small live JSON response.
Run `python -m adapters.gemini.evaluate --mode local` for offline policy fixtures,
or add `--live-model` for actual inference. Evaluation results remain local.
Chalk SDK dependencies and remote evaluation deployment have been removed.

## Neon or Supabase Postgres

`DATABASE_URL` selects the server database. Neon uses its pooled URI; Supabase
can use a session-pooler URI with the project's database password. Both use TLS.
An empty value selects SQLite. `SUPABASE_DATABASE_URL` is only an optional saved
alternative; the app uses one primary database and does not dual-write.

Workspace tables use private schema `reeftrace_workspace`. Earlier `/v1` records
remain untouched in schema `reeftrace`. No existing SQLite data is uploaded.
Transactions retain serialized manual approvals and queue claims. Camera frames
stay local. Never expose database credentials through `NEXT_PUBLIC_` variables.

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

Run `python -m pytest -q tests/test_gemini.py tests/test_photon.py`. The current tests
check malformed/unauthorized tools, returned evidence/proposal IDs, deadlines,
generated SDK request/response contracts, route filtering, session rescans, deduplication,
durable-before-send ordering and identical retries. With the sponsors extra absent,
the application starts offline and SDK contract tests skip.

Gemini has separate live model proof as described above; Photon still needs an authorized
phone round trip before any conversation claim. Demo evidence should name the configured model, case/evidence IDs, tool trace,
inbound message ID and accepted request ID; do not label mocks as live sponsor calls.
