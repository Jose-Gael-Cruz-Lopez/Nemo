# Tideward · ReefTrace

Tideward helps teams compare where to intercept floating pollution before it reaches a protected area, then inspect whether recorded outcomes support that choice. The software demonstrates source tracing, two-layout comparisons and Chalk explanations with synthetic examples, alongside a separate forecast study using real historical NOAA drifters.

**Tideward** is the product name. Repository names, Python packages, environment variables and API identifiers remain **ReefTrace**. The current product is a controlled prototype: its software works without a physical rig, while real tank performance and environmental benefit remain unmeasured.

## Start locally

Use Python 3.12 and Node 20.9+; the verified development environment uses Python 3.12 and Node 24. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,sponsors]'
cd dashboard
npm ci
cd ..
.venv/bin/python scripts/dev.py
```

The launcher checks dependencies and local ports, bootstraps a private `.env` and a missing/blank `REEFTRACE_LOCAL_TOKEN`, then starts the single-worker API at **http://127.0.0.1:8000** and dashboard at **http://127.0.0.1:3000**. Existing nonblank settings are preserved. Verified running services are reused; unrelated listeners are reported rather than killed. Ctrl+C stops only services that invocation started. `.venv/bin/python scripts/dev.py --check` performs a read-only preflight.

The root page is the public introduction. Use `/login` or the workspace's operator-access control to enter the local `REEFTRACE_LOCAL_TOKEN` privately; `/workspace` also permits public research viewing. This is shared local operator access, not individual email accounts. The token lives in tab memory and clears on reload; provider keys stay on the server.

The launcher never changes sponsor enable flags. Starting a new API with `PHOTON_ENABLED=true` requires the explicit `--allow-photon` flag; an already running API and its authorized worker are left untouched. A software demo does not require changing any messaging setting or starting the Camera page.

## Three-part software demo

Start in **Overview**, choose **Start software demo**, and follow **Follow the evidence**. The [click-by-click runbook](docs/integrated-team-demo.txt) covers the longer presentation.

1. **Trace a source — Open source trace.** In Investigations, connect operator access, choose **Load demo**, then inspect the saved observed-trajectory report. The synthetic moving example already ranks candidate C; **Recompute source support** is an optional deliberate recomputation that changes its evidence identity. **Test sensitivity** reruns the declared assumption variants, not a new observation. Expand **Choose a different observation** to inspect the retained endpoint (**Unknown**) or invalid-mapping example (**Invalid**). Ask Chalk to explain the saved evidence and its limits.
2. **Compare two layouts — Compare layouts.** In Prevention, choose **Load prevention demo**. Inspect the protected surface polygon, baseline/intervention paths, predicted entry bounds and separately labelled synthetic trial outcomes. The stock prevention demo uses its own frozen synthetic case/layout fixture; it does not silently reuse the source case selected in Investigations. The advanced creation form can anchor a new comparison to a chosen active source report. Physical trial count remains zero.
3. **Explain the evidence — Ask Chalk.** Ask the source investigator what supports its conclusion, or ask the prevention investigator to compare frozen predictions with the recorded outcomes. Inspect its live-response flag, cited evidence IDs and tool trace. A prevention review binds the exact comparison/evaluation snapshot and cannot turn an Unknown source into an accepted ranking. Provider failure leaves the numerical evidence available.

For real geographic evidence, open **Data lab** and choose **Load buoy comparison**. Inspect all six groups and five models, then choose **Explain this result** under **What does this result mean?**. This separate research discussion does not fetch more NOAA data, train a shared model or change a tank source report. Setup/saved observations and research details are collapsed disclosures; the advanced pages remain available.

Loading the source demo already prepares example evidence; explicitly recomputing a case creates a new evidence identity/revision. Repeated loads reuse active demo cases. Loading after STOP creates an active replacement while preserving the stopped history. The full workspace retains the other diagnostics, Camera commissioning and Settings for deliberate advanced use.

## What is working, and what the evidence proves

| Part | Current implementation and evidence | Remaining boundary |
| --- | --- | --- |
| Source tracing | Synthetic moving, retained-endpoint and invalid examples; forward simulation, sensitivity gates, saved reports and explanatory Chalk tools | No measured physical source-identification accuracy |
| Prevention | Protected zone, two frozen layouts, simulated first-entry outcomes, separate trial ledgers, retry safety, exports and validation receipts | No completed physical release or measured interception benefit |
| Fresh NOAA study | Six acquired GDP-ID days, five fixed algorithms, **180/180 scored outcomes**, **36 unique later intervals**, verified raw/selection/forecast/report lineage | Historical buoy motion, not observed plastic, a water-tank validation or an independent reef experiment |
| Chalk | Live case-bound investigations and a live fresh-study **REPORT verified on 17 October 2026**; exact evidence citations and bounded read-only research tools | Configuration readiness alone is not a live response; timeouts/provider failures preserve deterministic results |
| Photon | Durable inbox/outbox, scoped direct conversation and strict control commands; a previously authorized automatic round trip was independently observed Delivered | No messages are needed by this demo or the software handoffs; HTTP 202 acceptance alone is not delivery |
| Camera/field commissioning | Implemented capture, mapping, drift fitting, admission checks and immutable field receipts; synthetic contract tests | The real assembled rig, measured mapping/drift and physical trials have not been commissioned here |
| Grok/xAI | Grok-assisted design/code review, deterministic evidence briefing and server-side Voice API adapter | No funded live xAI Voice result or completed Voice API eligibility is claimed; voice remains disabled |

The final local software verification on 17 October 2026 passed **1,061 Python tests**, **122 frontend tests**, and **122 PASS / 0 FAIL / 6 expected BLOCKED** offline HTTP checks. Ruff, generated route types, TypeScript and the production build passed. Actual browser checks covered the revised guide, Ranked/Unknown/Invalid source states, separate prevention example, recorded-outcome disclosure and real NOAA results; the guide also had no horizontal overflow at 390 px. Live-provider failures were preserved and two discovered research-orchestration defects received regressions. The blocked offline scopes are not counted as successful physical or device tests. GitHub runs Python/scientific replay, isolated HTTP workflows, and dashboard lint/types/build on pushes and pull requests; inspect the exact commit's hosted result separately.

## Data roles, units and algorithms

The [algorithm and contract audit](docs/algorithm-contract-audit.md) gives the equations, actual code references, assumptions and failure rules. The following datasets have different jobs:

| Input or output | Role and units | What it must not be used as |
| --- | --- | --- |
| Synthetic token observations/profiles | Reproducible software development fixtures; tank positions in **cm**, elapsed time in **s** | Measured water behavior or an independent physical test |
| Recorded token tracks, when available | Mapping starts in pixels; accepted water-plane positions are **cm**, token drift is **cm/s**. Separate recordings fit and validate a local field | NOAA ocean forcing or a measurement of pure water velocity independent of token behavior |
| Known release labels and trial outcomes | Evaluator truth in the separate trial ledger; zone/capture times in **s** | Source-estimator features or proof that a model's guess was correct |
| Fresh NOAA positions | Historical latitude/longitude mapped to local **m**; velocity errors in **m/s**; each GDP-ID day's first **18** positions are permitted context, final **6** are evaluation positions | Tank calibration, plastic-source labels or proof of operational real-time causality |
| Satellite reef context | Pinned historical NOAA Coral Reef Watch heat stress in degree-heating weeks | Current tank conditions, confirmed bleaching, or input to source rankings |

The tank path uses OpenCV red HSV segmentation and gap-preserving single-token tracking, a checked planar homography, finite-difference drift samples, spatial cell medians and inverse-distance interpolation. A bounded forward advection–diffusion simulator compares declared candidate releases with the observed history or retained endpoint. It saves conditional relative support, then applies observation, fit, separation and sensitivity gates. It does not reconstruct a unique past by reversing a velocity arrow. Source percentages are **relative support under assumptions**, not calibrated polluter probabilities.

Prevention compares the same protected polygon and declared sources across two registered layouts. It tracks first zone entry and retention events under frozen scenarios; unsupported paths remain unknown. Predicted particles, recorded synthetic releases and operator-reported physical releases keep separate denominators. The trial ledger's missing/unresolved bounds are accounting bounds, not statistical confidence intervals or demonstrated ecological benefit. A numerical report can be `SIMULATED_COMPARISON` or `WITHHELD_UNSUPPORTED_FLOW`; withholding is not a zero-effect result.

The fresh geographic study compares stationary persistence, last drift, mean drift, own-prefix ridge velocity AR(1), and a fixed constant-velocity Kalman estimator. Kalman assumes position standard deviation **100 m** (`R = 10000 I m²`) and continuous white-acceleration spectral density **1e-6 m²/s³**. Its forecast begins at the filtered last context state; other models begin at the raw last context observation. No future measurement updates are used. Observed ellipse diagnostics use `P_position + R`, not the latent position covariance alone; nominal hit counts remain uncalibrated.

On these six new GDP-ID days, last drift has the lowest mean position error (**ADE 1,573.423 m**), compared with Kalman **1,655.662 m** and ridge **1,772.130 m**. That negative result for the more complex models is retained without retuning or automatic promotion. Different IDs and distinct selected WMOs do not prove physical or statistical independence: **10 old aliases remain unresolved**, and NOAA hourly positions are retrospectively QC/interpolated, potentially using later raw fixes upstream. The earlier blocked acquisition and pre-outcome parser/transport amendment are preserved. See the [fresh study guide](docs/fresh-noaa-study.md) for all metrics, identities, hashes and limitations.

Older reference-buoy, training-origin, four-drifter, transfer, Kalman and motion-vector panels remain inspectable research history. Their already-viewed outcomes must not be relabelled as new independent tests. No trained neural trash detector or matched ocean-current forcing has been added to the operational tank model.

## Application states and evidence freshness

Numerical status, case state, agent action and delivery status are separate contracts:

| Contract | Actual states/transitions |
| --- | --- |
| Case | New observation → `OBSERVED`. A committed estimate → `INVESTIGATE` and a new revision/evidence ID, even if its numerical result is Invalid. STOP → `STOPPED`, increments revision and cancels pending recovery tasks. Any recorded manual terminal outcome → `RECOVERING`; new observations/revalidation are required for later live work. |
| Source report | `ranked`, `unknown` or `invalid`. Unknown may retain conditional support values but has no accepted ranked source. Invalid/Unknown are scientific outcomes, not fabricated zero error or a forced winner. |
| Manual recovery task | Current eligible LIVE case → `proposed`; approval within the 60-second expiry gate → `awaiting_human`; operator outcome → `manual_recovered`, `failed` or `uncertain`. Pending tasks can be `cancelled`. Approval is a human task, not motor execution. Synthetic/replay cases cannot create one. |
| Prevention comparison | Frozen to exact source evidence/revision, layout/profile identities and trial plan. A recompute, STOP or recovery makes it archival (`CASE_CHANGED_OR_STOPPED`); history remains readable, while new trials/reviews are rejected. New trials create a new evaluation digest; a stale Chalk answer/receipt cannot silently follow it. |
| Trial ledger | Immutable one-release rows: `zone_entry`, `intercepted_before_entry`, `no_entry` or `unresolved`. The same key/body retries exactly; a changed body with the same key conflicts. Per-source/layout quotas are enforced. The UI shows the counterbalanced next slot; the API records out-of-order entries and reports `order_followed=false` rather than silently correcting them. |
| Chalk result | Case agent actions include `REPORT`, `UNKNOWN`, `OBSERVE_MORE`, `REQUEST_APPROVAL`, `STOP`; a research review permits only `REPORT`/`STOP`. An agent's STOP ends that turn without authorizing an action; it is not automatically a case STOP. Revision/snapshot checks reject results made stale while a model was responding. |
| Photon | Inbox `pending → processing → done/failed`; outbox `pending → sending → accepted/failed`, with leases and immutable-key/body retries for retryable transport failures. `accepted` means HTTP 202, not Delivered/read. Strict authorized `STOP`, `CANCEL`, `APPROVE` commands bypass conversational generation; quoted prose is not a command. |

STOP never erases saved evidence and does not cut external pump power. The software contains no pump, gantry or autonomous robot actuator. Public research loads are read-only; source/prevention model calls and state changes require local operator access.

### Two export/validation contracts

The current-case `analysis_bundle_v1` export has `payload_sha256` and `payload_canonical_json`. Importing its validation manifest checks exact identity, partition and recomputed trial accounting; it returns **`IDENTITY_AND_ACCOUNTING_CHECKED_METHOD_NOT_RERUN`**. It does not rerun the separate numerical method or prove an independent experiment.

Trace 2's offline validator uses its distinct `content_hash` envelope and full immutable method inputs. Its published synthetic alternatives are alternative outcomes for the same fixture, not additive independent trials. Do not rename hashes or treat a redacted product export as a complete method-replay bundle. [The validation protocol](docs/prevention-validation-protocol.md), [Trace 3 contract](docs/trace3-research-and-contract.md), and [Aarush's merged rehearsal](docs/experiment-validation-v2.md) explain the boundary.

## Current software-only team work

Use the two copyable prompts in [software handoffs](docs/software-handoffs.md):

- **Megana:** existing-demo acceptance, accessibility and browser end-to-end evidence.
- **Aarush:** export/validator contract documentation and missing/unresolved/retry edge-case tests.

These assignments do not depend on a webcam, pump, calibration or new physical data. Jose owns shared application state, scientific interfaces, live provider configuration and final integration. Earlier [four-person](docs/four-person-build-plan.md) and [three-person](docs/team-handoff-prompts.md) plans remain history; they do not expand these current software-only scopes.

Next software work is concrete: extend guided-demo acceptance/accessibility regressions, strengthen the export/method boundary tests, keep hosted CI green on each exact commit, and retain provider-failure/stale-response behavior. An [optional synthetic first-passage bookkeeping audit](docs/algorithm-contract-audit.md#11-next-synthetic-audit-first-passage-bookkeeping) tests exact destination/support partitions; it changes neither frozen algorithms nor physical evidence. Physical calibration and independent source/interception trials are a separate later measurement task; extra ocean-model training cannot replace them. Grok is used interactively for review; its recurring research schedule remains paused. GitHub checks run on code changes.

## Updated physical rig guide

The [11-page rig guide](docs/tideward-rig-guide.pdf) replaces the earlier clipped build guide. It distinguishes reported inventory from items still needing purchase or confirmation, specifies the selected C920s USB camera and actual pump-adapter check, and gives assembly, mapping, separate layout measurements and first-trial steps. [Connection diagram](docs/assets/tideward-rig-connections.png) · [measured tank map](docs/assets/tideward-rig-measured-map.png).

Use the webcam's USB connection to the laptop and the pump's original, separately operated AC cord. The return tube carries water within the same bin; the original cord goes over the rim without cutting the tank. Decorative coral, 3D printing and the unused Arduino/ESP32 boards are not required by this selected plan. The guide is a planned build, not a claim that the rig or any physical trial has been completed. Megana and Aarush's current handoffs remain software-only.

## Reproduce software checks

The safest complete software rehearsal starts its own temporary API/store on a random loopback port and guards every provider, camera and Photon path:

```sh
.venv/bin/python scripts/e2e_offline.py --output work/offline-http-audit.json
.venv/bin/python scripts/evaluate_fresh_drifter_study.py --output work/fresh-noaa-replay.json
.venv/bin/python -m ruff check apps adapters scripts tests
cd dashboard
node --test tests/*.test.mjs
npm run lint
npx next typegen
npx tsc --noEmit
npm run build
```

For the full Python suite and optional SDK/NetCDF dependencies, use the isolated recipe in [CI](docs/ci.md); use a source copy without private `.env` or a live store. `.[ocean]` enables the prepared Copernicus/NetCDF readers, not automatic downloads. `.[evaluations]` enables explicit Chalk remote-evaluation tooling; importing/deploying real cloud tasks is outside the offline demo.

The older live-server commands `scripts/e2e_demo.py` and `scripts/e2e_prevention.py` can contact a configured Chalk gateway and read private local settings. They do not send Photon messages or open a camera, but they are distinct from the guarded offline runner. A passing local suite is not a completed hosted CI run, a live provider response or a physical accuracy measurement.

## Reference map

- [Architecture](docs/architecture.md), [algorithm/contract audit](docs/algorithm-contract-audit.md), [physics](docs/physics.md), [prevention physics](docs/prevention-physics.md).
- [Integrated demo](docs/integrated-team-demo.txt), [prevention workflow](docs/prevention-workflow.md), [verification](docs/verification.md), [CI](docs/ci.md).
- [Fresh NOAA study](docs/fresh-noaa-study.md), [datasets](docs/datasets.md), [original real-data research](docs/research-real-data.md), [motion-vector research](docs/motion-vector-research.txt), [current Grok build record](docs/grok-fresh-build.md), [earlier Kalman build record](docs/grok-kalman-build.md).
- [Chalk/Photon contracts and live-verification history](docs/integrations.md), [satellite/Grok Voice contract](docs/grok-space-context.md).
- [Later field commissioning](docs/field-commissioning.md), [original execution plan](docs/execution-plan.md). Camera frames, contacts, raw physical recordings and credentials stay in ignored local storage; no electronics purchase or physical experiment is required for the current software handoffs.
