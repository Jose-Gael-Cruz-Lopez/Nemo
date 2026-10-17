# Chalk in Tideward: what it does and how to use it

Documentation checkpoint: **17 October 2026**. Tideward is the product; `reeftrace` remains the repository and package name. This guide describes implemented behavior, not a claim of physical validation. It contains no keys, private environment IDs, contacts or local recording data.

## The simple answer

**Chalk is the evidence explainer you can ask about Tideward's results.** Tideward's Python code calculates the trajectories, source support, reef-area entries and trial accounting. Chalk connects a language model to the exact saved evidence, so it can explain what those results support, why a result is uncertain and what to measure next.

For example, the app can show that one layout has fewer modeled reef-area entries. Chalk can explain that comparison and its assumptions, while making clear that a simulated interception is not yet a measured environmental benefit. Its value is helping a user reason about evidence and decide the next experiment.

## What each part is responsible for

| Part | Job |
| --- | --- |
| USB camera and OpenCV | Obtain images and track a controlled red token. A checked mapping converts pixels to tank centimetres when the real setup is ready. |
| Python scientific services | Fit supported drift, compute conditional source support, integrate ocean paths, compare interception geometry, score fixed buoy models and account for trials. These services produce the authoritative numbers. |
| Chalk Model Gateway | Authenticate and route a bounded language-model request to the configured model connection. It is an integration service, not an ocean-current sensor or a trajectory-training dataset. |
| Tideward's bounded investigator | Decide which evidence tools a request may use, enforce limits, reject invalid output and verify citations/freshness. These controls are implemented in this repository. |
| Underlying language model | Interpret the permitted evidence and write a concise explanation under that contract. It can still make a reasoning mistake; correct citation identity alone does not prove every sentence. |
| Photon | Receive an authorized messaging question and deliver the case investigator's reply. Messaging transport and scientific reasoning have separate responsibilities. |
| Human operator | Approve eligible manual tasks, associate a new recording, run the physical rig and independently record what happened. |

The scientific report remains readable if Chalk is unavailable. A convincing AI paragraph cannot replace a missing measurement or upgrade an Unknown source to a supported identification.

## Where Chalk appears in the product

### 1. Investigations: explain a source case

Load or create an observation, compute source support, then ask a question about that case. Useful questions include:

- “What does this observation support, and what remains uncertain?”
- “Why did this retained endpoint return Unknown?”
- “Which assumption matters most, and what new measurement could distinguish the candidates?”

The investigator reads the current case and source report. It can run only a registered sensitivity preset. In a validated LIVE case, it can save one genuine five-second observation through `observe_again`; that saved frame-and-point recording does not automatically update the source ranking or join tracks across a gap. Operator association review is required. In an eligible case it can propose an expiring human manual-net task. A proposal is not approval, a pump command or automatic collection. Synthetic/replay cases cannot use the live recording tool.

The final action is one of `REPORT`, `UNKNOWN`, `OBSERVE_MORE`, `REQUEST_APPROVAL` or `STOP`, with checked evidence IDs. The source result itself independently remains `ranked`, `unknown` or `invalid`.

### 2. Prevention: interpret the ocean layout comparison

In the full local app, open **Prevention**, keep **Ocean · changing currents**, choose **Compare ocean layouts**, then **Ask Chalk about these layouts**. Ask:

> “Which layout is better supported by this scenario, what assumptions drive that result, and what must we validate before using it?”

The server binds the answer to the selected current snapshot, method, scenario and full report. The investigator gets one read-only evidence tool, at most two model calls and only `REPORT` or `STOP`. A successful report must cite exactly the comparison and method identities returned by that tool.

In the downstream illustrative scenario, the deterministic table shows central-layout entries of two out of six and flanking-layout entries of four out of six. Chalk explains why the central geometry performs better in that model, while retaining the ideal-capture assumption, coarse current support and hypothetical reef-area proxy. The original no-entry control remains a tie; a different number of captures does not prove protection when neither layout has a threatened entry.

The numerical-quality feature also passes a compact integration-step/contact-chord summary to this review. Smaller-step agreement concerns numerical sensitivity to a fixed field; it is not observed waste accuracy, a probability of reef protection or a measured effect. A separate final local live review cited the exact report/method and explained both checks without changing the scientific numbers.

### 3. Prevention: interpret tank predictions and recorded trials

Switch to **Tank experiment & trial ledger**. Chalk reviews the frozen comparison, its source evidence and exact evaluation snapshot; a selected validation receipt adds its own required evidence. Useful question:

> “Do the recorded outcomes support the predicted improvement, and which missing or unresolved releases prevent a stronger conclusion?”

It must keep modeled particles, synthetic rehearsal outcomes and operator-reported physical trials distinct. It cannot fill missing trials, change the physics or edit the trial ledger. The application can save its review receipt without altering the scientific evidence.

### 4. Data Lab: explain the fresh NOAA model study

Expand the historical buoy-research material and request a study explanation. Ask:

> “What did the fixed models learn from the permitted context, how did they perform on later positions, and why doesn't this validate plastic interception?”

The review reads the frozen study and protocol. It preserves failed acquisitions, incomplete coverage, all denominators and the fact that the more complex algorithm did not win this study. It cannot download new trajectories, retrain a model, promote a winner or transform historical buoy drift into tank calibration.

### 5. Earlier changing-current diagnostic

A separate read-only research endpoint can explain changing-current versus frozen-current forecast paths. The main interface now uses the combined ocean comparison. Separation between two forecasts is a difference between model outputs, not a measured accuracy improvement.

## How a request works end to end

```text
Selected case/report + your question
  → operator-authenticated local API
  → validate identity, permissions and evidence freshness
  → choose the investigator's allowlisted tools
  → Chalk gateway → configured language model
  → permitted evidence read or gated source-workflow tool
  → structured finish with exact evidence IDs
  → validate output and recheck freshness
  → show concise explanation beside the authoritative report
```

The server sends a bounded relevant evidence package, not arbitrary access to the laptop or repository. The model does not receive permanent provider credentials, private contact routes or unrestricted camera access. User questions and quoted evidence are treated as data rather than authority to expand tools.

The default limits are a **60-second whole turn**, at most **25 seconds per model request**, and a request limit of **1,024 completion tokens**. The source investigator permits at most nine model calls with repeated-read/tool limits. Ocean/current/NOAA investigators permit at most two calls and one evidence read. Time spent in tools also consumes the turn budget. These limits contain each interaction; they do not enforce an account-wide daily spending cap.

Generated explanations use nonnumerical prose; the UI renders scores and metrics from the deterministic report. Disallowed numerical prose, invalid JSON, unrelated citations or invalid actions are rejected. Research `REPORT` conclusions require both returned citations; `STOP` may cite a permitted subset or none. If the selected report changes during the network call, the stale answer is rejected rather than silently attached to new results.

## Current connection, Gemini and cloud trials

The inspected local configuration on **17 October 2026** selects **`openai/gpt-6-sol` through the Chalk sponsor router**. Earlier Gemini setup notes describe provisioning history. They do not mean today's selected model is Gemini or that a personal Gemini API account is required for this sponsor-router configuration.

| Item | Meaning |
| --- | --- |
| Chalk gateway key | Authorizes the matching Chalk environment/model connection. It is not interchangeable with a Google provider key. |
| Chalk environment ID | Identifies the authorized Chalk environment. It must match the key and connection. |
| Exact model ID | Names a permitted model on that router. The app does not silently switch models on failure. |
| Google AI Studio API key | Authorizes Google's Gemini API for a connection that uses that provider; provider quotas and billing belong to that Google project. |
| Google Cloud trial | A separate Cloud billing entitlement whose eligibility and terms must be checked in the user's account. Tideward does not assume it exists or activate it. |
| Consumer Gemini subscription | Access to the consumer app does not by itself establish this application's API access or credits. |

The request URL is `https://api.chalk.ai/v1/router/chat/completions`. Private server settings are:

```dotenv
CHALK_ENABLED=true
CHALK_ROUTER_BASE_URL=https://api.chalk.ai/v1/router
CHALK_ROUTER_API_KEY=<private matching gateway key>
CHALK_ENV_ID=<private matching environment ID>
CHALK_MODEL=<exact authorized model ID>
```

Enter actual values only in the ignored local server configuration. Do not paste them into Trov, public GitHub, a Grok prompt, a screenshot or a browser client bundle. Restart the owned local API after a deliberate configuration change. A teammate needs authorized private configuration for their own environment; copying a documentation example does not grant model access.

The earlier Gemini gateway key was created without a gateway-enforced daily token budget after quota enforcement was rejected. Per-turn limits are not a billing cap. This documentation publication changes no provider settings, buys no credits, invokes no model and enables no billing.

## Readiness, a live answer and a safe failure

The current local readiness status reports enabled/ready. Its `connection_verified: false` is deliberately returned by the configuration checker: reading status does not run a model. It does not mean that every historical live request failed. Successful source, NOAA and ocean turns were separately recorded during development; availability must still be verified for the actual session.

A completed model turn reports `provider: chalk` and `live_model_response: true`, with the required tool trace and evidence citations. A timeout or invalid answer can return a safe `STOP` with `live_model_response: false`. That is an AI failure outcome, not a zero scientific score and not an automatic case STOP.

| Symptom | What to check |
| --- | --- |
| Not configured | Server enable flag, matching private key/environment/model, API restart after saving. Do not expose values while diagnosing. |
| HTTP 401/403 | Key type, environment match and model/connection permission. A provider key pasted as a gateway key is not interchangeable. |
| Provider failure or timeout | Preserve the deterministic report and safe failure trace. Confirm provider availability; do not silently change models or start unbounded retries. |
| Stale evidence | Reload the selected current report and deliberately ask again. Do not reuse the old response with a new scenario/revision. |
| Model/tool contract error | Inspect the safe trace and returned evidence IDs; malformed output is rejected rather than rendered as verified science. |
| Public Vercel button disabled | Expected: the hosted deployment is a read-only ocean showcase, with no live Chalk, camera, Photon or local store credentials. Use the full local app for live investigations. |

## Relationship to Photon

An authorized Photon conversation can invoke the same source-case investigator. Photon moves the question and reply; Chalk supplies the bounded evidence discussion. Enabling a messaging worker can enable replies, so a documentation or read-only demonstration must not silently change that setting. This publication sends no Photon message and leaves the previously authorized configuration unchanged.

## What is verified, and what remains

The final local numerical-quality checkpoint passed **1,365 Python tests, 191 frontend tests and 137 guarded HTTP checks**, with zero HTTP failures and six deliberately blocked external/physical scopes; lint, TypeScript and the isolated production build passed. These checks cover contracts, failures, stale identities and workflows; the guarded HTTP run does not invoke a provider. A separate browser-driven live Chalk `REPORT` was verified against the final report and method identities and explained the new numerical-quality summary. Neither that turn nor the tests establish physical accuracy. No remote Chalk-hosted evaluation run is claimed; inspect hosted CI for the exact pushed code commit separately.

The real tank is not commissioned. Required work includes measured calibration, separate held-out drift runs, independently measured layout flows and frozen trials with all missing/failed outcomes retained. Chalk helps explain those requirements; it cannot complete them in prose.

## Implementation references

- [Complete product handbook](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/tideward-product-guide.md)
- [Integration contracts and historical live checks](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/integrations.md)
- [Case investigator](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/adapters/chalk/agent.py) and [gated case tools](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/apps/api/reeftrace_api/services/investigation.py)
- [Read-only research investigator](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/adapters/chalk/research.py)
- [Ocean evidence binding](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/apps/api/reeftrace_api/services/ocean_prevention_investigation.py)
- [Evaluation tooling and its explicit remote-deployment boundary](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/tree/main/adapters/chalk)
