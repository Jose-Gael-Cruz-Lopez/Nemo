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

## Run the full HTTP audit

With the local API running:

```sh
.venv/bin/python scripts/e2e_demo.py --output work/e2e-demo.json
```

The script accepts only an HTTP loopback origin and reads the private operator token from the repository `.env` without printing it. It checks health, rejected unauthorized writes, idempotent demo loading, case selection, re-estimation of ranked/Unknown/invalid observations, sensitivity lineage, Chalk's preserved numerical evidence, saved manual-task history, the real NOAA experiment and STOP on a disposable copy. It opens no camera and sends no Photon messages. If Chalk is configured, its investigation is a real, metered model request.

The JSON report distinguishes:

- **PASS:** the particular software assertion succeeded.
- **FAIL:** the workflow broke or returned a result outside its contract. The command exits with code 1.
- **BLOCKED:** a live account, authorized device conversation or physical measurement is still needed. A missing Chalk response is not replaced with a fake success.

`summary.software_workflow_passed` means there were no failed software assertions. `summary.complete_live_product_verified` remains false while any blockers exist. The CLI exits successfully for a completed local audit with recorded external blockers; it does not claim all integrations or physical hardware were verified. Provider diagnostics contain a safe failure category/status, never upstream bodies, request headers or secrets.

## Configure the sponsor integrations

### Current commissioning evidence

The actual local HTTP audit recorded **18 PASS, 0 FAIL, 3 BLOCKED**. The browser exercised the source-tracing workflow and the real NOAA Data lab. The remaining blockers are physical webcam/tank commissioning, a live Chalk model response, and a complete Photon device conversation.

Photon Beta **authentication was checked against the real service** after the user's approval. A 30-day custom project key with `project:read` and `project:write` is stored only in private `.env`. The official SDK's read-only `raw.projects.list_messages` request returned **HTTP 200** and its response passed schema validation. The local evidence record is `work/photon-live-auth.json`; it records no secret or account identifier. No messages were sent. The shared line and exact sender/agent route remain unassigned, and `PHOTON_ENABLED=false`. A user must supply their intended send-from identity and authorize the test reply before the channel round trip can be demonstrated.

Chalk still has no provider connection, gateway key or selected model. Its current `NOT_CONFIGURED` fallback is an honest blocked live-model check, not a successful model answer. Configuration-readiness fields remain separate from the explicit Photon authentication evidence and from device delivery.

### Chalk Model Gateway

Follow the [official Model Gateway setup](https://docs.chalk.ai/docs/model-gateway). Configure a provider connection and permitted model, then issue a scoped gateway key for the intended environment. In private `.env`, set:

```dotenv
CHALK_ENABLED=true
CHALK_ROUTER_BASE_URL=https://api.chalk.ai/v1/router
CHALK_ROUTER_API_KEY=YOUR_GATEWAY_KEY
CHALK_ENV_ID=YOUR_ENVIRONMENT_ID
CHALK_MODEL=YOUR_PERMITTED_MODEL_OR_PUBLISHED_ROUTE
```

ReefTrace calls `/chat/completions` using a Bearer key and `X-Chalk-Env-Id`. Select an available connection-prefixed model or published route. Dedicated deployments may use their own API host. Restart the API after editing `.env`. Require a returned trace, evidence ID and `live_model_response: true`; readiness alone proves only configuration. A missing credential, provider HTTP failure, timeout or invalid tool output produces STOP. Safe HTTP diagnostics expose only the status code. The [official gateway documentation](https://docs.chalk.ai/docs/model-gateway) defines these endpoint/authentication/model contracts.

### Photon 2.0 / Beta

Follow the **Beta** [project setup](https://photon.codes/docs/beta/get-started/project) and [iMessage guide](https://photon.codes/docs/beta/get-started/imessage). They specify Python `photonhq-api==0.5.0`, import `photon_api`, API origin `https://api.photon.codes`, a Bearer key and a `pho_prj_...` project ID. This repository uses that product; Spectrum Stable examples use a separate contract.

In [the Beta dashboard](https://app.beta.photon.codes), select the project, create a key with `project:read` and `project:write`, and assign a shared line to the exact human send-from phone/email identity. The human must initiate the conversation. Put the actual assigned identities and allowed case ID in private `.env`:

```dotenv
PHOTON_ENABLED=true
PHOTON_API_KEY=YOUR_PROJECT_KEY
PHOTON_PROJECT_ID=YOUR_PROJECT_ID
PHOTON_ROUTES_JSON=[{"human_handle":"YOUR_SEND_FROM_IDENTITY","agent_handle":"PHOTON_ASSIGNED_NUMBER","role":"operator","allowed_cases":["ACTUAL_CASE_ID"]}]
```

Start this deliberately messaging-enabled configuration with:

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
npm run lint
npm run build
npm audit --omit=dev
```

The final full Python suite passed **231 tests**, with zero failures, errors or skips and one existing Starlette/httpx TestClient deprecation warning. Ruff reported zero issues across the repository. Dashboard ESLint, TypeScript and the optimized production build passed. The actual loopback HTTP demo recorded **18 PASS, 0 FAIL and 3 BLOCKED** checks; its camera, live Chalk and Photon round-trip checks remain blocked. The browser also exercised demo loading, ranked/Unknown/invalid source evidence, sensitivity, the explicit unavailable-Chalk response, NOAA replay, search, reload persistence, STOP on a disposable case, and readable setup validation. At a 390px viewport the Data lab page had no horizontal page overflow. These software checks do not substitute for physical or live-service commissioning.

| Area | Automated evidence | What still needs a real-world check |
|---|---|---|
| USB vision and geometry | Actual OpenCV images, projective mapping, association/freshness and simulated capture-worker tests | Connected C920s, intended OS permissions, real image quality and timing |
| Tank transport and tracing | Measured-record admission, heldout split rules, bounded particle physics, sensitivity, ambiguity and source gates | Real independent drift/retention runs and blind source-release trials |
| Case/action state | SQLite transactions, STOP races, task restoration, role/approval/outcome guards | A supervised physical recovery and honest recorded outcome |
| Chalk | Real adapter with explicit HTTP MockTransport, bounded tools, returned IDs, Unknown preservation and safe diagnostics | Successful account-backed model response and quality review |
| Photon | Official 0.5.0 SDK contract tests plus a real read-only HTTP 200 authentication/schema check | Shared-line assignment, authorized route and actual device round trip; no send performed |
| Public-data ML | Pinned real NOAA CSV, training-only fits, chronological holdout, geographic geometry and leakage regressions | Many independent trajectories and matched forcing before operational claims |

The runtime has no motor, pump, relay or serial actuator command. Local source tracing does not use geographic coordinates, and the Data lab does not manufacture tank cases. A five-second manual-collection target-age gate can expire during an LLM or human round trip; obtain fresh case evidence rather than treating a fresh preview as a renewed target. Copernicus remains a separate, explicit authenticated-download experiment, with the resolution/access limits in [datasets.md](datasets.md).
