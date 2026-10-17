# Start, demonstrate and verify ReefTrace

Updated 16 October 2026 for the USB webcam build on branch `codex/software-execution`. The runnable product compares declared tank entry points and preserves Unknown when the observation cannot distinguish them. The separate Data lab forecasts a real historical buoy trajectory. Passing tests and synthetic demos do not establish real reef-cleanup or plastic-source accuracy.

## Start the team workspace

From the repository root, with the installation in [README](../README.md#start-locally) completed:

```sh
.venv/bin/python scripts/dev.py --check
.venv/bin/python scripts/dev.py
```

Open [the local dashboard](http://127.0.0.1:3000). In **Operator access**, enter `REEFTRACE_LOCAL_TOKEN` from the private root `.env`. This token stays in tab memory. Put Chalk/Photon credentials only in the server's private `.env`; never enter them in the browser or commit them. The launcher creates or repairs a missing local token and preserves existing settings. Ctrl+C stops only the processes that launcher started.

The API uses a single worker at `http://127.0.0.1:8000`; its [interactive API reference](http://127.0.0.1:8000/docs) describes every request. The camera stays closed until an operator starts it. The pump remains on its original power cord, with no software actuation.

Browser private-network preflights are allowed only for the explicitly configured
dashboard origins `http://127.0.0.1:3000` and `http://localhost:3000`. Wildcard,
external, lookalike and different-port origins cannot gain that permission.
An allowed preflight does not authorize a write: each mutation still requires
the private operator token. After updating the API code, restart the API once to
load the corrected middleware; a dashboard reload alone does not update it.

## Run the source-tracing demonstration

| Step | Click / action | What a correct result looks like |
|---|---|---|
| Load | **Load demo** | Three explicitly synthetic observations: ranked path, ambiguous endpoint, invalid mapping. A repeat load reuses active cases. |
| Select | Open **Observed trajectory** | The saved points, candidate regions and immutable source report appear. |
| Trace | **Compute source support** | A new evidence ID, `status: ranked`, candidate `C`, and `confidence_kind: relative_support_not_probability` for this development fixture. |
| Challenge assumptions | **Test sensitivity** | The two frozen dispersion variants, tied to the latest baseline evidence ID. No post-hoc parameter search. |
| Explain | Ask Chalk what fits and what remains uncertain | A genuine gateway answer cites returned evidence and shows its tool trace. An unavailable gateway instead returns STOP, `live_model_response: false`, and the saved numerical report. |
| Test ambiguity | Open **Retained endpoint** | Unknown remains visible because candidate histories converge at the shared pocket. The LLM cannot upgrade this report to a confident source ranking. |
| Test bad mapping | Open the invalid-calibration observation | Invalid remains visible. Invalid mapping cannot authorize recovery. |
| Stop | **Stop task** | The case becomes STOPPED. Compute/sensitivity cannot continue, and late numerical/model results cannot replace the stopped state. The physical pump is unchanged. |

STOP is durable. An explicit later **Load demo** creates a fresh replacement for a stopped fixture and retains its old record. Manual recovery is available only for fresh, recorded LIVE cases, not synthetic data. Pending/approved tasks are stored in SQLite and available through `GET /api/v1/cases/{id}/actions` after selecting or reopening an observation. A recorded physical outcome is not overwritten by a late agent result.

## Run a real-data experiment in Data lab

Open **Data lab** (or **Explore real data** from Overview), then click **Run real-data replay**. Inspect **Observed motion and forecast paths**, **Held-out model comparison**, and **Dataset provenance**. The committed sample has 24 hourly positions from NOAA drifter `8707978` on 3 October 1987. The first 18 points fit the models; the final six are held out in a free-running forecast. The pinned original CSV hash and provenance are verified before fitting. No account, current ocean API request or model download is required.

| Model | Mean heldout position error | Final six-hour error |
|---|---:|---:|
| Stationary persistence | 3,855.0 m | 6,774.6 m |
| Last observed displacement | 4,385.8 m | 9,832.2 m |
| Learned ridge velocity autoregression | 3,557.4 m | 7,561.2 m |

The learned model improves mean error on this selected day but has worse endpoint error than stationary persistence. Six dependent heldout points do not establish operational forecast skill. The NOAA positions are interpolated estimates, so our chronological split cannot remove possible look-ahead from upstream processing. This dataset contains no plastic-release or producer labels; its source-attribution result is explicitly unsupported. See [the full protocol and mathematics](research-real-data.md), the [NOAA product description](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php) and [official dataset metadata](https://erddap.aoml.noaa.gov/gdp/erddap/info/drifter_hourly_qc/index.html).

Reproduce the same result locally or read it through the API:

```sh
.venv/bin/python scripts/evaluate_real_data.py --output work/real-data-example.json
curl --fail http://127.0.0.1:8000/api/v1/research/real-data
```

The separate training diagnostic uses five expanding origins inside those first
18 points, with six forecast horizons and all three models. It verifies the pinned
CSV directly and never runs the held-out benchmark or selects a model. Read it at
`GET /api/v1/research/training-diagnostic`; its `test_data_used` and
`model_selection_performed` fields must both remain false.

In an investigation, **Load satellite context** reads the pinned historical NOAA
Coral Reef Watch sample; **Read briefing text** produces a deterministic script
bound to the saved source evidence and its hash. The seven-day satellite series
is ecological context and never changes the tank source ranking. The text and
script hashes can be verified without xAI credentials. **Generate Grok narration**
is a separate authenticated provider request and remains disabled under the
current setup; reading text is not proof of a live Voice API call.

## Run the full HTTP audit

With the local API running:

```sh
.venv/bin/python scripts/e2e_demo.py --output work/e2e-demo.json
```

The script accepts only an HTTP loopback origin and reads the private operator token from the repository `.env` without printing it. Before any mutation or model request, it refuses a running camera, hardware actuation or an enabled Photon worker. It checks rejected unauthorized writes, idempotent demo loading, case selection, re-estimation of ranked/Unknown/invalid observations, sensitivity lineage, the NOAA holdout and training-only diagnostic, pinned satellite provenance, frozen briefing hashes, Chalk's preserved numerical evidence, saved manual-task history and STOP on a disposable copy. It opens no camera, sends no Photon messages and never requests xAI audio. If Chalk is configured, its one investigation is a real, metered model turn.

The JSON report distinguishes:

- **PASS:** the particular software assertion succeeded.
- **FAIL:** the workflow broke or returned a result outside its contract. The command exits with code 1.
- **BLOCKED:** a live account, authorized device conversation or physical measurement is still needed. A missing Chalk response is not replaced with a fake success.

`summary.software_workflow_passed` means there were no failed software assertions. `summary.complete_live_product_verified` remains false while any blockers exist. The CLI exits successfully for a completed local audit with recorded external blockers; it does not claim all integrations or physical hardware were verified. Provider diagnostics contain a safe failure category/status, never upstream bodies, request headers or secrets.

## Configure the sponsor integrations

### Current commissioning evidence

The final expanded actual local HTTP audit recorded **27 PASS, 0 FAIL,
3 BLOCKED** in `work/e2e-final.json`. Chalk returned a genuine **REPORT** with
`live_model_response: true`, a nonempty tool trace and the current source evidence
ID. The saved deterministic report stayed exactly equal to the re-computed
report. The audit verified the training-only diagnostic, historical satellite
provenance, all three frozen briefing statuses and STOP. Its remaining blockers
are physical webcam/tank commissioning, the intentionally disabled Photon device
conversation and uninvoked xAI speech. No camera, actuator, Photon send or audio
request was used. The report passed a scan against the private credentials/route
values and strong token patterns without exposing them.

Photon Beta **authentication was checked against the real service** after the user's approval. A 30-day custom project key with `project:read` and `project:write` is stored only in private `.env`. The official SDK's read-only `raw.projects.list_messages` request returned **HTTP 200** and its response passed schema validation. The local evidence record is `work/photon-live-auth.json`; it records no secret or account identifier. The shared-line assignment is Active, and the exact sender/agent route is configured privately. **The user prohibits test messages and automatic replies, so `PHOTON_ENABLED=false` remains required.** No messages were sent. Authentication and assignment do not establish a device conversation.

Chalk has a configured native Gemini connection, a scoped gateway key and a permitted Flash model. Earlier real investigations completed with `live_model_response: true`, successful case/source tool reads and the frozen evidence ID. Subsequent rehearsals also encountered intermittent provider HTTP 503 and TIMEOUT responses. After the bounded latency fix and API restart, the final expanded audit again completed a genuine REPORT. A future failure still returns STOP with the unchanged numerical report, even after an earlier success. The request budget is now 25 seconds, bounded by the remaining 60-second whole-turn deadline; no retries or provider reasoning fields are added. Timeout diagnostics identify the stage and completed tools without exposing provider content. Readiness alone is not a live success. See [the current integration evidence and limits](integrations.md).

### Chalk Model Gateway

Follow the [official Model Gateway setup](https://docs.chalk.ai/docs/model-gateway). Configure a provider connection and permitted model, then issue a scoped gateway key for the intended environment. In private `.env`, set:

```dotenv
CHALK_ENABLED=true
CHALK_ROUTER_BASE_URL=https://api.chalk.ai/v1/router
CHALK_ROUTER_API_KEY=YOUR_GATEWAY_KEY
CHALK_ENV_ID=YOUR_ENVIRONMENT_ID
CHALK_MODEL=YOUR_PERMITTED_MODEL_OR_PUBLISHED_ROUTE
```

ReefTrace calls `/chat/completions` using a Bearer key and `X-Chalk-Env-Id`. Select an available connection-prefixed model or published route. Dedicated deployments may use their own API host. Restart the API after editing `.env`; rotating only the provider credential inside the existing Chalk connection does not require a local restart if the gateway key, environment and model remain unchanged. Require a returned trace, evidence ID and `live_model_response: true`; readiness alone proves only configuration. A missing credential, provider HTTP failure, timeout or invalid tool output produces STOP. Safe HTTP diagnostics expose only the status code; timeout fields contain the call stage and counts. The [official gateway documentation](https://docs.chalk.ai/docs/model-gateway) defines these endpoint/authentication/model contracts.

### Photon 2.0 / Beta

Follow the **Beta** [project setup](https://photon.codes/docs/beta/get-started/project) and [iMessage guide](https://photon.codes/docs/beta/get-started/imessage). They specify Python `photonhq-api==0.5.0`, import `photon_api`, API origin `https://api.photon.codes`, a Bearer key and a `pho_prj_...` project ID. This repository uses that product; Spectrum Stable examples use a separate contract.

In [the Beta dashboard](https://app.beta.photon.codes), select the project, create a key with `project:read` and `project:write`, and assign a shared line to the exact human send-from phone/email identity. The human must initiate the conversation. Put the actual assigned identities and allowed case ID in private `.env`:

```dotenv
PHOTON_ENABLED=false
PHOTON_API_KEY=YOUR_PROJECT_KEY
PHOTON_PROJECT_ID=YOUR_PROJECT_ID
PHOTON_ROUTES_JSON=[{"human_handle":"YOUR_SEND_FROM_IDENTITY","agent_handle":"PHOTON_ASSIGNED_NUMBER","role":"operator","allowed_cases":["ACTUAL_CASE_ID"]}]
```

Keep the current worker disabled. Only after a new explicit authorization for
replies, set `PHOTON_ENABLED=true` and start that messaging-enabled configuration with:

```sh
.venv/bin/python scripts/dev.py --allow-photon
```

Use a separate data directory for a different Photon project. The worker polls plain direct iMessages, validates the exact route, and replies using the received agent/space/message IDs and a durable idempotency key. An accepted provider response is not proof of device delivery. Verify an authorized, human-initiated question and actual reply on the device; record the inbound/evidence IDs and accepted request ID. Do not assume a judge's unassigned number can use the shared line. The [integration guide](integrations.md) documents STOP/CANCEL/APPROVE grammar and durable delivery semantics.

## Automated checks and evidence boundaries

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check apps adapters scripts tests
.venv/bin/python -m pip check
cd dashboard
node --test tests/*.test.mjs
npm run lint
npm run build
npm audit --omit=dev
```

The current strict full Python suite passed **320 tests**, with zero failures,
errors or skips in **63.02 seconds** and one existing Starlette/httpx TestClient
deprecation warning. All sponsor services were explicitly disabled for that test
process. Full repository Ruff and `pip check` passed. This includes regressions
for private-network CORS/authentication, model request/turn deadlines,
truncated-output rejection, source/STOP races and the expanded audit's no-message
and no-hardware guards. Six frontend state and read-recovery regressions also passed, covering
atomic evidence refresh so recomputing source support clears an old
investigation, sensitivity result and approval display together.

The earlier actual loopback HTTP rehearsal returned an explicit Chalk TIMEOUT
while preserving its source report. This motivated the bounded request-budget
change and safe stage diagnostics. The final expanded script recorded **27 PASS,
0 FAIL and 3 BLOCKED**, with a real Chalk REPORT; its added public-data/briefing
checks and separate untested-audio blocker are included in those new counts.
Earlier browser checks covered demo loading, ranked/Unknown/invalid evidence,
sensitivity, NOAA replay, search, reload persistence, STOP and setup validation.
These software checks do not substitute for physical or live-service
commissioning.

| Area | Automated evidence | What still needs a real-world check |
|---|---|---|
| USB vision and geometry | Actual OpenCV images, projective mapping, association/freshness and simulated capture-worker tests | Connected C920s, intended OS permissions, real image quality and timing |
| Tank transport and tracing | Measured-record admission, heldout split rules, bounded particle physics, sensitivity, ambiguity and source gates | Real independent drift/retention runs and blind source-release trials |
| Case/action state | SQLite transactions, STOP races, task restoration, role/approval/outcome guards | A supervised physical recovery and honest recorded outcome |
| Browser/API | Exact local-origin private-network preflights, untrusted-origin rejection and unchanged operator authentication | The intended browser/OS against the restarted local services |
| Chalk | Real adapter with explicit HTTP MockTransport, strict tools/IDs/Unknown preservation, request and whole-turn deadlines; earlier account-backed REPORT | Current provider availability and review of each generated answer; a timeout remains a failed live response |
| Photon | Official 0.5.0 SDK contract tests, real read-only HTTP 200 auth/schema check and Active assignment | Actual device round trip remains untested; replies stay disabled by user instruction |
| Public-data ML | Pinned real NOAA CSV, training-only fits, five-origin diagnostic, separate chronological holdout, geographic geometry and leakage regressions | Many independent trajectories and matched forcing before operational claims |
| Satellite and briefing | Pinned NOAA heat-stress provenance, no source-ranking influence, immutable evidence/script hashes and mocked audio/STOP races | Explicitly authorized live xAI speech requires a configured key; no live speech claim |

The runtime has no motor, pump, relay or serial actuator command. Local source tracing does not use geographic coordinates, and the Data lab does not manufacture tank cases. A five-second manual-collection target-age gate can expire during an LLM or human round trip; obtain fresh case evidence rather than treating a fresh preview as a renewed target. Copernicus remains a separate, explicit authenticated-download experiment, with the resolution/access limits in [datasets.md](datasets.md).
