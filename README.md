# Nemo · ReefTrace

Nemo starts with **where floating pollution could have come from**: compare an observed path with declared candidate sources, preserve uncertainty, then use motion predictions to compare interception layouts and test the outcome. Source tracing remains the core question; prevention is the next decision, not a replacement for origin inference. The controlled tank workflow implements candidate-source support, frozen comparisons and trial ledgers. The separate ocean view compares two hypothetical layouts using real changing PacIOOS model currents; historical NOAA drifter studies evaluate motion models.

**Nemo** is the product name. Repository names, Python packages, environment variables and API identifiers remain **ReefTrace**. The current product is a controlled prototype: its software works without a physical rig, while real tank performance and environmental benefit remain unmeasured.

**Source-origin scope:** Investigations starts with tank source tracing: registered profiles compare **two to five declared entry regions** (the reusable estimator accepts two to eight) using forward particles and saved trajectory/retention evidence. Ranked, Unknown and Invalid remain distinct; support bars are conditional compatibility, not calibrated polluter probabilities. **Ocean source research** is a separate bounded retrospective prototype using saved real HYCOM currents: a five-step observed → connected → Kalman-filtered → explicit formula → backward/forward walkthrough, plus a 25-case earlier-position sensitivity diagnostic. It does not search arbitrary ocean locations or establish a pollution release/polluter identity. Better forward-motion error does not by itself demonstrate source accuracy. Read [the source-first mission](docs/source-tracing-mission.md) and [the new ocean source workflow](docs/ocean-source-research.md).

Start with the [complete product handbook](docs/tideward-product-guide.md) for every feature and graph, and [Chalk in Nemo](docs/chalk-user-guide.md) for the AI integration's job, permissions, current model selection and failure behavior. Historical setup notes retain their original context; the current handbook explains which capabilities are local, public, verified or awaiting physical measurements.

**Read the science in plain language:** [all actual datasets and their tank relevance](#datasets-what-nemo-actually-uses) · [formulas F1–F17](#scientific-formulas-explained-through-the-tank-experiment) · [real-tank measurement sequence](#turn-the-formulas-into-the-real-tank-experiment). The inventory distinguishes acquired inputs, reused observations, synthetic fixtures and research-only candidates.

**Latest ocean-source walkthrough checkpoint — 17 October local / 18 October UTC:** the five-stage display now uses the pinned real NOAA/HYCOM result, with separate backward and forward branches, layer controls and reserved-position validation. The six-hour current-only reverse model performed **worse** than last observed drift: mean earlier-position miss **8,696.82 m versus 2,197.73 m** (stationary: **6,069.35 m**). The separate three-hour filtered tutorial is a different task, not a demonstrated improvement over that six-hour comparison. Neither result identifies a verified pollution release.

Local verification passed **2,017 Python tests, 320 frontend tests and 241 isolated HTTP checks**, with zero HTTP failures and six explicitly blocked live-provider/physical scopes. Ruff, ESLint, TypeScript, dependency consistency and an isolated production build passed. Browser checks exercised all five stages, both groups, fixed axes, time scrubbing, comparison disclosure, the disabled-Chalk STOP path and a 390 px layout. These are software checks, not tank validation or a new live Chalk/Photon test. See [the exact verification scope](docs/research-evidence/nemo-source-first-pipeline-verification-20261018.json).

**Next camera task:** [Trove #3, assigned to Aarush](https://trov.dev/nemo/#tickets/3), proposes OpenCV reference-marker registration, a projected centimetre grid, black tray/green filter boundary layers and stale-mapping detection. This is planned work; automatic registration is not shipped or physically validated. Known scale and separate check points remain necessary.

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

### View the connected camera without a tank

Open **Camera** in the local workspace. The live preview and controls appear first; a tank is not required. The connected **C270 was verified as device 0 on this Mac at 1280 × 720**. The pixel grid has a checkbox and cursor coordinates; it does not claim centimetre calibration. A continuous, session-bound MJPEG connection displays the latest frames at up to 15 fps without per-frame React updates. Capture preserves the device's native mode (about 24 fps in a two-second C270 check), while recorded tracking defaults to 10 Hz. Tank commissioning is collapsed under **Calibrate a tank and record trials when ready**. See [camera preview and coordinate setup](docs/camera-preview.md).

The [public ocean showcase deployment plan](docs/public-ocean-showcase.md) is a separate read-only view with checked numerical snapshots. It does not expose the local camera, experiment store or provider credentials; deployment status and its public URL must be verified separately.

## Three-part software demo

Start in **Overview**, choose **Start software demo**, and follow **Follow the evidence**. The [click-by-click runbook](docs/integrated-team-demo.txt) covers the longer presentation.

1. **Trace a source — Open source trace.** In Investigations, connect operator access, choose **Load demo**, then inspect the saved observed-trajectory report. The synthetic moving example already ranks candidate C; **Recompute source support** is an optional deliberate recomputation that changes its evidence identity. **Test sensitivity** reruns the declared assumption variants, not a new observation. Expand **Choose a different observation** to inspect the retained endpoint (**Unknown**) or invalid-mapping example (**Invalid**). Ask Chalk to explain the saved evidence and its limits.
2. **Compare two layouts — Compare layouts.** Prevention defaults to **Ocean · changing currents**. Click **Compare ocean layouts** for one combined dynamic-current plot, independent layer checkboxes and a one-release filter. The downstream what-if predicts **6** reef-proxy entries without interception, **2** with central coverage and **4** with flanking coverage. This proxy was chosen after viewing the forecast; it is an illustrative scenario, not independent performance evidence. **Original proxy · no-entry model control** preserves the original zero-entry tie. For recorded outcomes, deliberately select **Tank experiment & trial ledger**, then **Load prevention demo**; its synthetic case and ledger remain separate. Physical trial count remains zero.
3. **Explain the evidence — Ask Chalk.** In the ocean report, click **Ask Chalk about these layouts** for a read-only explanation bound to its exact forcing, method, scenario and report hashes. The source and tank investigators remain available in their own workflows. Inspect the live-response flag and evidence citations. Provider failure leaves the numerical evidence available; an explanation cannot alter counts or turn an Unknown source into an accepted ranking.

**Data lab** opens the same combined ocean comparison, rather than a second default trajectory graph. For the six-group/five-model NOAA study, expand **Research details and historical buoy validation**, then choose **Load buoy comparison** and **Explain this result** under **What does this result mean?**. These read-only replays do not acquire data, retrain models or change a tank source report.

**Watch both trajectory directions:** in **Investigations → Ocean source research**, explicitly load the saved study. Use the five stage buttons or one-pass playback to see real scattered observations, the connected path, the causal Kalman estimate, its current-plus-offset formula and backward/forward branches. Recorded earlier/later positions and reconstruction errors stay behind **Show reserved comparison positions**. Select both GDP examples, toggle layers without rescaling and inspect the separate 25-case lookback sensitivity. The [ocean-source guide](docs/ocean-source-research.md) separates possible earlier positions, future rendezvous, numerical closure and source-validation claims.

**Saved ocean-source result:** the five-stage walkthrough now reconstructs and predicts actual historical buoy positions. It uses only **01:00/02:00/03:00 UTC** observations, initializes velocity at 02:00 and causally updates at 03:00; it is not an RTS smoother. From that filtered anchor, the same changing HYCOM field plus one fixed motion offset runs backward to 00:00 and forward through 06:00. The withheld positions are decoded only after both groups' forecasts have been saved and read back. All **8/8 planned evaluation cells** were scored, representing **eight distinct earlier/later positions on two already-viewed GDP-ID groups**, not eight independent source experiments.

| GDP group | Backward 00:00 position error | Forward final 06:00 position error |
| --- | ---: | ---: |
| `300234066836710` | **403.531 m** | **860.020 m** |
| `300534061292930` | **389.248 m** | **1,023.657 m** |

The separate six-hour **06:00→00:00 current-only** reconstruction scored **6/6 model/group rows** on two earlier positions. Its mean miss was **8,696.822 m**, worse than last-drift backward **2,197.726 m** and stationary **6,069.353 m**. All **25/25 sensitivity paths per group** completed, but their spread is not calibrated uncertainty. Tiny forward/backward numerical closure errors do not overturn these observed misses. This is a bounded, post-outcome geographic prototype; **pollution-release/source attribution remains unvalidated**, and physical tank trial count remains zero. The [saved result](data/research/ocean-source-v1/evaluation.json) and [method/results guide](docs/ocean-source-research.md#saved-first-score-results) retain both positive and negative findings without retuning.

**3D tank replay:** in Prevention, select **Tank experiment & trial ledger**, load a saved comparison and choose **Open 3D tank**. Orbit the schematic, select a layout/source, toggle layers and scrub saved paths. Full-ensemble counts remain fixed when the drawing changes. Physical recordings use a separate capture clock; unmeasured depth/equipment are schematic, and absent real trials stay absent. See [the 3D guide](docs/tank-simulator.md).

**Matched-current comparison:** Data Lab now defaults its **Study version** selector to **v2 · compatibility amendment**. Choose **Load matched-current study** to read the separately frozen HYCOM/GDP result: **36/36 cells scored** across two buoy groups, three fixed candidates and six later hours. Equal-ID macro ADE is stationary **3,490.119 m**, last observed drift **1,510.232 m**, and HYCOM current-only **5,063.020 m**. Current-only did not improve on last drift on this small retrospective sample; no automatic model promotion or operational winner follows. The selector retains **v1 · preserved original attempt**, with its immutable **0/36** compatibility-failure ledger. Read [v2 results, exact hashes and offline replay](docs/matched-current-v2-results.md), the [frozen amendment proposal](docs/matched-current-v2-amendment.md), and [v1 history](docs/matched-current-results.md). Both attempts remain separate; the shared numerical engine and all 14 v1-pinned source files are unchanged.

The default ocean comparison uses only changing-current advection. The earlier single-release/frozen-current diagnostic remains a separate API and numerical baseline; its straight path is not the product's default forecast. The saved valid window is 17 October 2026 18:00 UTC–18 October 00:00 UTC and automatically becomes an archived model scenario afterward. See [ocean prevention](docs/ocean-prevention.md) for the current workflow and [current-driven prediction](docs/current-driven-prediction.md) for the underlying solver and earlier diagnostic.

**Does a smaller time step change the result?** Open this disclosure beneath the ocean comparison in Prevention or Data Lab. It separates three RK4 integration-step runs from contact checks on one fine path, retaining all six releases and incomplete coverage. The solver lands on forcing timestamps and samples on a start-relative clock, avoiding fractional-timestamp false stops. The current numerical check retains central **2/6** versus flanking **4/6** and the control tie; agreement under these settings is numerical sensitivity, not physical accuracy or improved ML skill. See [the RK4 quality guide](docs/rk4-numerical-quality.md).

Loading the source demo already prepares example evidence; explicitly recomputing a case creates a new evidence identity/revision. Repeated loads reuse active demo cases. Loading after STOP creates an active replacement while preserving the stopped history. The full workspace retains the other diagnostics, Camera commissioning and Settings for deliberate advanced use.

**New exploratory motion diagnostic:** a separately committed constant initial residual adds the final observed drift minus the origin HYCOM current to a copy of the current field, then uses the existing WGS84/RK4 integrator. Its saved first score retains **48/48 cells using twelve already-viewed processed positions**. Equal-ID average miss is **1,030.049 m** for the residual candidate versus **1,510.232 m** last drift and **5,063.020 m** current-only. Both groups improve descriptively, but the candidate was designed after viewing the earlier outcome; this is not an unseen-data or operational improvement claim. The pinned read-only `/api/v1/research/origin-residual` API and its operator-protected Chalk review are implemented separately. The new diagnostic is available in **Data Lab → Research details and historical buoy validation → Load drift-offset study**, with all four saved model rows, both groups, fixed-scale path toggles and a separate bounded Chalk review. Here ‘origin’ means forecast start, not pollution source; source inference remains in Investigations. No operational model is automatically changed. See [the card guide](docs/origin-residual-datalab.md). Read [the saved result and exact identities](docs/origin-residual-results.md). A local explicit numerical replay reproduced the saved forecasts and scores without rewriting artifacts; that is separate from the API reader's saved-byte verification.

## What is working, and what the evidence proves

The **five-stage NOAA ocean walkthrough** passed **2016 Python tests, 320 frontend tests and 241 guarded HTTP checks**, with zero failures and six explicit external/physical blockers. Ruff, ESLint, TypeScript and an isolated production build passed. Actual browser checks covered both groups, the five stages, one-pass playback, time scrubbing, fixed-domain layers, separate validation reveal, operator gating, disabled-Chalk STOP and a 320 px layout without horizontal overflow. The disposable browser store stayed unchanged and all six side-effect guards stayed zero. The normal local API was then refreshed to load the new route while preserving private integration settings; no new live Chalk test, explicit Photon test message, camera action or xAI API call was initiated. See [the exact local verification receipt](docs/research-evidence/nemo-bidirectional-pipeline-verification-20261018.json); hosted CI remains a separate exact-commit check.

The historical source-first/Data Lab integration checkpoint passed **1,914 Python tests,
299 frontend tests and 207 isolated HTTP checks**, with zero HTTP failures and
the same six expected external/physical blockers, plus Ruff, ESLint, TypeScript
and an isolated production build. Browser checks loaded the pinned four-model
result, inspected both groups, verified fixed scores/axes when toggling paths,
and retained **STOP · No live model response** with providers disabled. All five
device/provider/messaging/scientific-execution guard counters stayed zero and
the disposable store was unchanged. The active API and Photon worker were not
restarted; loading previously added routes there is a separate runtime step.
The [local receipt](docs/research-evidence/nemo-source-first-origin-ui-verification-20261017.json)
records exact sources and scope. Hosted CI for the resulting commit is separate.

| Part | Current implementation and evidence | Remaining boundary |
| --- | --- | --- |
| Source tracing | Synthetic moving, retained-endpoint and invalid examples; forward simulation, sensitivity gates, saved reports and explanatory Chalk tools | No measured physical source-identification accuracy |
| Geographic earlier-position research | Saved NOAA/HYCOM five-stage causal-filter walkthrough; **8/8** earlier/later cells, plus a separate **6/6** six-hour backward baseline comparison and **25-case** sensitivity per group | Two previously viewed buoy groups; conditional earlier positions are not verified pollution releases, calibrated source probabilities or a worldwide attribution system |
| Ocean prevention | Two layouts with the same 2 km of ideal interception line, six shared changing-current paths, illustrative reef proxy, first-contact events, conservative entry bounds and snapshot-bound Chalk | Downstream geometry is a disclosed post-preview what-if; no mapped reef boundary, measured collector efficiency or ecological benefit |
| Tank prevention | Protected zone, two frozen layouts, simulated first-entry outcomes, separate trial ledgers, retry safety, exports and validation receipts | No completed physical release or measured interception benefit |
| 3D tank scene | Lazy-loaded interactive schematic of the exact saved comparison; layout/source/layer controls, playback and separate verified recording paths | Display interpolation and schematic equipment are not CFD; no physical release alignment or positional accuracy is invented |
| Fresh NOAA study | Six acquired GDP-ID days, five fixed algorithms, **180/180 scored outcomes**, **36 unique later intervals**, verified raw/selection/forecast/report lineage | Historical buoy motion, not observed plastic, a water-tank validation or an independent reef experiment |
| Matched-depth current study | Distinct frozen v2 amendment, six successful requests, two GDP payloads, **36/36 scored**, prior forecast receipts, exact replay and version-bound Data Lab/Chalk | v1 retains **0/36**; current-only errors exceed last drift on this sample; no independent forecast/plastic/tank/reef validation or automatic promotion |
| Changing ocean currents | Real PacIOOS three-hourly surface u/v, bounded WGS84/RK4 particle transport and time-selectable arrows; dynamic advection drives ocean-mode layout comparisons | Hypothetical six-hour releases, coarse source support, no measured waste skill or transfer into tank physics |
| Chalk | Live case-bound investigations and a live fresh-study **REPORT verified on 17 October 2026**; exact evidence citations and bounded read-only research tools | Configuration readiness alone is not a live response; timeouts/provider failures preserve deterministic results |
| Photon | Durable inbox/outbox, scoped direct conversation and strict control commands; a previously authorized automatic round trip was independently observed Delivered | No messages are needed by this demo or the software handoffs; HTTP 202 acceptance alone is not delivery |
| Camera/field commissioning | Connected C270 live preview verified at 1280 × 720 on this Mac; pixel guide, conditional water-plane grid, mapping, drift fitting, admission checks and immutable field receipts | Live preview is not calibration; the tank rig, measured mapping/drift and physical trials have not been commissioned here |
| Grok/xAI | Grok-assisted design/code review, deterministic evidence briefing and server-side Voice API adapter | No funded live xAI Voice result or completed Voice API eligibility is claimed; voice remains disabled |

The final local software verification on 17 October 2026 passed **1,061 Python tests**, **122 frontend tests**, and **122 PASS / 0 FAIL / 6 expected BLOCKED** offline HTTP checks. Ruff, generated route types, TypeScript and the production build passed. Actual browser checks covered the revised guide, Ranked/Unknown/Invalid source states, separate prevention example, recorded-outcome disclosure and real NOAA results; the guide also had no horizontal overflow at 390 px. Live-provider failures were preserved and two discovered research-orchestration defects received regressions. The blocked offline scopes are not counted as successful physical or device tests. GitHub runs Python/scientific replay, isolated HTTP workflows, and dashboard lint/types/build on pushes and pull requests; inspect the exact commit's hosted result separately.

The later merged-PR/interface checkpoint passed **1,091 Python tests**, **134 frontend tests**, and the same **122 PASS / 0 FAIL / 6 expected BLOCKED** isolated HTTP workflow. Ruff, dependency consistency, ESLint, route types, TypeScript and the production build passed. No frozen model or dataset changed. Hosted CI for the exact final commit must still be checked separately.

The changing-current checkpoint passed **1,170 Python tests**, **144 frontend tests**, and **128 PASS / 0 FAIL / 6 expected BLOCKED** isolated HTTP checks. It adds a distinct PacIOOS snapshot and current-forced solver; original GDP study files remain unchanged. The browser verified the current-time slider, independent layer toggles, fixed plot scale, mobile help and safe disabled-Chalk behavior. The exact final hosted CI result is linked in the change report. Analytic tests and a real data replay do not establish waste-prediction skill.

The earlier complete local checkpoint passed **1,641 Python tests**, **223 frontend tests**, and **153 PASS / 0 FAIL / 6 expected BLOCKED** isolated HTTP checks, plus Ruff, ESLint, route types, TypeScript and the production build. A separate fresh-process reader/API/replay check passed 105 tests. The HTTP harness proves zero camera opens, provider requests, Photon sends or polls in its disposable process. The later matched-current archive was moved byte-for-byte outside the historical public-fixture inventory; all 18 file hashes and both old/new replay identities remain unchanged. Physical hardware and live-device scopes are not counted as passed. Exact hosted CI must still be checked for the pushed commit.

The v2 pre-acquisition checkpoint passed **1,770 Python tests**, **331 focused subset checks** and **225 frontend tests**. After the actual result existed, the extended disposable HTTP run passed **174 / 0 FAIL / 6 expected BLOCKED**, including explicit v1/v2 identity selection, cross-version/stale-pin rejection and an unchanged full-store digest with providers disabled. Actual browser checks displayed **36/36**, both buoy groups, independent path checkboxes/hourly displacement arrows and invariant axes/metrics; switching to v1 showed **0/36**, then back to v2 restored the saved result. A separate live Chalk **REPORT** cited the exact v2 report/protocol. No camera, new Photon message, xAI API or billing change was used. The final post-acquisition full suite then passed **1,779 Python tests** with one upstream dependency warning; frontend remains **225 passed** and HTTP **174 / 0 / 6 blocked**. Lint/types/build passed. [Hosted run 39073934821](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/actions/runs/39073934821) passed all 1,779 Python tests and both HTTP/dashboard jobs, but its separate byte-exact v2 replay failed on Linux rounding. A [post-outcome portability verifier](docs/matched-current-v2-portable-verification.md) now preserves exact frozen inputs and accepts only explicitly bounded computed-float differences; 30 additional regression tests passed on macOS and Linux. The original evaluator, data and scientific result are unchanged. Hosted verification of this follow-up is a separate release check.

## Interface and first visit

The current local workspace keeps the light-blue Nemo palette with a full-height scientific layout, square cards, thin rules and a **220 px** desktop sidebar. **Experiment overview** starts with **Start software demo** and three short steps: source tracing, layout comparison and evidence review. Setup and saved observations begin collapsed; duplicate team controls and the four-builder badge are removed. The actual supplied **Glyph Trail** core retains its Bayer/glyph/diffusion math as a pale-blue decorative background, with pointer events disabled, a **24 fps / 600,000-pixel / 192-stamp** budget and visibility/reduced-motion cleanup. It never represents current or observation data. See [the concise scientific workspace/demo guide](docs/nemo-scientific-demo.md).

The cinematic landing adapts Blue Marine's observed journey patterns into **Welcome → Observe → Trace → Prevent → Verify**, using an original silent **20-second 1080p Higgsfield ocean video**, self-hosted **Rajdhani**, smaller **32–52 px** chapter headings and actual native-scroll progress. The current globe uses the supplied **AtomicGlobe / MeridianGlobe** code: its baked Natural Earth point cloud produces **7,996 dots**, retains all six original shaders and uses the existing Three.js dependency without a Framer package. Source snapshots, exact hashes and adaptations are recorded in [the landing guide](docs/ocean-landing-journey.md). **Scroll to explore** and the bottom landing disclaimer are removed; scientific limits remain with feature results.

**Start journey** waits for its actual **460 ms** entry animation, then scrolls to Observe and focuses its heading; the next Tab reaches **Open observations**. **Open workspace** skips the introduction. There is no eyebrow copy, narration, caption panel or manual motion control. Automatic reduced-motion/hidden-tab handling, a still fallback, **1.5** globe pixel-ratio and **30 fps** caps remain. [Hosted run 39079486572](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/actions/runs/39079486572) passed all three jobs for historical **`f3353e0`**. The newer AtomicGlobe/Glyph Trail/scientific-workspace revision is **local and unreleased**, with final combined tests/build pending at this documentation checkpoint; earlier totals do not verify it. Protected actions and provider keys retain their existing gates.

Prevention and Data Lab begin with one ocean comparison graph. Checkboxes independently show the no-interception context, both layout paths, reef proxy, interceptors and current arrows. The release selector filters only the drawing; all six releases remain in every count, and common axis/arrow scales remain fixed. Historical NOAA paths and observed/predicted/error vectors retain their own checkbox controls inside **Research details and historical buoy validation**. The full five-model table is behind **Compare all five models**. Metric-label help works on hover, keyboard focus and touch; Escape dismisses it. See [the interface design notes](docs/interface-design.md).

## Data roles, units and algorithms

The [algorithm and contract audit](docs/algorithm-contract-audit.md) gives the equations, actual code references, assumptions and failure rules. The following datasets have different jobs:

| Input or output | Role and units | What it must not be used as |
| --- | --- | --- |
| Synthetic token observations/profiles | Reproducible software development fixtures; tank positions in **cm**, elapsed time in **s** | Measured water behavior or an independent physical test |
| Recorded token tracks, when available | Mapping starts in pixels; accepted water-plane positions are **cm**, token drift is **cm/s**. Separate recordings fit and validate a local field | NOAA ocean forcing or a measurement of pure water velocity independent of token behavior |
| Known release labels and trial outcomes | Evaluator truth in the separate trial ledger; zone/capture times in **s** | Source-estimator features or proof that a model's guess was correct |
| Fresh NOAA positions | Historical latitude/longitude mapped to local **m**; velocity errors in **m/s**; each GDP-ID day's first **18** positions are permitted context, final **6** are evaluation positions | Tank calibration, plastic-source labels or proof of operational real-time causality |
| PacIOOS current forecast | Pinned geographic model u/v in **m/s**, at **0.25 m** depth; bilinear space/linear time interpolation for six-hour passive-tracer previews and ocean-layout comparisons | Observed waste motion, a score improvement, measured reef protection or centimetre tank forcing |
| Satellite reef context | Pinned historical NOAA Coral Reef Watch heat stress in degree-heating weeks | Current tank conditions, confirmed bleaching, or input to source rankings |

The tank path uses OpenCV red HSV segmentation and gap-preserving single-token tracking, a checked planar homography, finite-difference drift samples, spatial cell medians and inverse-distance interpolation. A bounded forward advection–diffusion simulator compares declared candidate releases with the observed history or retained endpoint. It saves conditional relative support, then applies observation, fit, separation and sensitivity gates. It does not reconstruct a unique past by reversing a velocity arrow. Source percentages are **relative support under assumptions**, not calibrated polluter probabilities.

Tank prevention compares the same protected polygon and declared sources across two registered layouts. It tracks first zone entry and retention events under frozen scenarios; unsupported paths remain unknown. Predicted particles, recorded synthetic releases and operator-reported physical releases keep separate denominators. The trial ledger's missing/unresolved bounds are accounting bounds, not statistical confidence intervals or demonstrated ecological benefit. A numerical report can be `SIMULATED_COMPARISON` or `WITHHELD_UNSUPPORTED_FLOW`; withholding is not a zero-effect result.

Ocean prevention integrates each of six hypothetical releases once through the same dynamic field, then evaluates no interception and two absorbing-line layouts with the same 2 km total length. First contact determines capture or reef-proxy entry; reef entry wins simultaneous ties. Unsupported paths remain unresolved in the full denominator: entry bounds are `[known entries, known entries + unresolved]`. A layout is preferred only when its upper entry bound is strictly below the other's lower bound; otherwise the result is `TIE` or `INDETERMINATE`. Five-minute output chords do not increase the source's roughly 4 km / three-hour resolution. Ideal capture does not model barrier-flow interaction, waves, object response or measured collection efficiency. See [the complete ocean method and limits](docs/ocean-prevention.md).

The fresh geographic study compares stationary persistence, last drift, mean drift, own-prefix ridge velocity AR(1), and a fixed constant-velocity Kalman estimator. Kalman assumes position standard deviation **100 m** (`R = 10000 I m²`) and continuous white-acceleration spectral density **1e-6 m²/s³**. Its forecast begins at the filtered last context state; other models begin at the raw last context observation. No future measurement updates are used. Observed ellipse diagnostics use `P_position + R`, not the latent position covariance alone; nominal hit counts remain uncalibrated.

On these six new GDP-ID days, last drift has the lowest mean position error (**ADE 1,573.423 m**), compared with Kalman **1,655.662 m** and ridge **1,772.130 m**. That negative result for the more complex models is retained without retuning or automatic promotion. Different IDs and distinct selected WMOs do not prove physical or statistical independence: **10 old aliases remain unresolved**, and NOAA hourly positions are retrospectively QC/interpolated, potentially using later raw fixes upstream. The earlier blocked acquisition and pre-outcome parser/transport amendment are preserved. See the [fresh study guide](docs/fresh-noaa-study.md) for all metrics, identities, hashes and limitations.

Older reference-buoy, training-origin, four-drifter, transfer, Kalman and motion-vector panels remain inspectable research history. Their already-viewed outcomes must not be relabelled as new independent tests. No trained neural trash detector or matched ocean-current forcing has been added to the operational tank model.

The ocean solver uses `dX/dt = u(X,t)` with geographic metric derivatives, resampling the real forecast at the changing particle position and time. It can turn when the supplied flow turns. The original frozen buoy study remains unchanged; no cosmetic curve is added to its persistence or constant-velocity models. Future physical tank predictions need timestamped tank measurements, not rescaled ocean fields.

The public, offline `GET /api/v1/research/ocean-prevention` accepts only the two fixed `scenario_id` presets. Operator-protected `POST /api/v1/research/ocean-prevention/investigate` requires `question`, `scenario_id`, `snapshot_sha256`, `method_sha256`, `scenario_sha256` and `report_sha256`. It rejects stale selections before provider access and rechecks the complete report afterward. Chalk has one read-only evidence tool, at most two bounded model calls, and only `REPORT`/`STOP`; a report cites exactly `ocean-comparison:<report hash>` and `ocean-method:<method hash>`. It cannot write cases/trials, acquire currents, actuate hardware or message Photon. Full contracts and request examples are in [ocean prevention](docs/ocean-prevention.md).

### Replay the planned tank in 3D

In **Prevention → Tank experiment & trial ledger**, select a saved comparison or load the synthetic prevention demo, then choose **Open 3D tank**. The large interactive scene shows the saved source regions, collector footprints, protected-zone proxy and representative surface paths. Choose a layout and source, orbit or inspect overhead, toggle layers, and play or scrub the saved paths. The Three.js viewer loads only after that explicit action, pauses outside view and preserves accessible 2D maps.

The scene reads the **same frozen simulation and evaluation** as the numerical report; it does not generate cosmetic currents, run browser-side physics or count display lines as outcomes. The synthetic demo's 40 × 30 cm footprint is a declared example, not a measurement of the team's bin. Walls, depth, camera mount, pump, tubing and coral proxy are schematic. This is a 3D presentation of a water-surface model, not computational fluid dynamics or a validated digital twin. NOAA/HYCOM ocean coordinates remain separate from tank centimetres.

**Predicted versus actual** means frozen full-ensemble counts beside separately reported physical outcomes. No real tank trial has been captured here. When a prospective, correctly calibrated recording is linked to an admitted measured trial, the scene can show its gapped centimetre samples on a separate capture clock. Capture start is not verified token release: the viewer does not align those clocks, choose the closest simulated particle or invent an RMSE. All missing/unresolved releases remain in the trial bounds. See [the tank simulator guide](docs/tank-simulator.md) for the exact endpoint, evidence checks, controls and physical validation steps. The public Vercel ocean showcase remains a separate read-only ocean demonstration.

The 17 October 3D integration checkpoint passed **1,549 Python tests**, **208 frontend tests** and **142 guarded HTTP checks / 0 failures / 6 expected external or physical blockers**, plus Ruff, ESLint, route types, TypeScript and an isolated production build. Actual Chrome checks covered WebGL, source/layout filters, layers, keyboard orbit and scrubbing, playback completion, close/reopen cleanup and a 390 px viewport. A separate live Chalk explanation used the exact saved comparison/evaluation and preserved Unknown source identity and zero physical trials. The [local verification receipt](docs/grok-evidence/tank3d-local-verification.json) identifies the tested source hashes; hosted CI must be checked for the exact subsequent commit.

The HYCOM/NOAA matched-current workflow now has distinct trusted v1/v2 identities, acquisition/forecast/score artifacts and pure read-only result readers. `GET /api/v1/research/matched-current?study_version=v2` selects the completed amendment; omission retains v1 API compatibility. Operator-protected `POST /api/v1/research/matched-current/investigate` binds `study_version`, `report_sha256` and `protocol_sha256` before a bounded Chalk turn and rechecks the full snapshot afterward. It never acquires, scores or mutates cases. The [Grok review continuation](docs/grok-evidence-continuation.md) retains static advice and corrections separately from local execution. The earlier [design](docs/matched-current-study-plan.md) preserves its original proposal chronology; [v2 results](docs/matched-current-v2-results.md) describe the actual completed attempt. Existing six-group NOAA scores and ocean/tank physics remain unchanged.

## Datasets: what Nemo actually uses

Nemo uses four environmental products: historical NOAA buoy positions, a saved PacIOOS current forecast, a historical HYCOM current subset, and NOAA satellite-derived coral heat-stress values. They answer different questions. The ocean studies help test motion calculations; the tank needs its own measured camera mapping, drift recordings and release outcomes.

The saved buoy trajectory files contain **13 logical GDP identifiers and 326 hourly position records**. This count excludes selection metadata, identity registries, generated forecasts and repeated use of the same positions by different algorithms. Thirteen logical IDs do not establish thirteen independent physical deployments; unresolved aliases and correlated observations remain limitations.

| Product | What is actually saved | What Nemo uses it for | Relevance to the real tank |
| --- | --- | --- | --- |
| NOAA Global Drifter Program hourly product | Small historical trajectory subsets: 13 logical IDs, 326 position rows | Compare motion forecasts with later processed buoy positions | Tests coordinate, timing and evaluation methods; cannot supply tank flow or centimetre calibration |
| PacIOOS ROMS Main Hawaiian Islands | One three-time, near-surface current-model snapshot | Dynamic ocean trajectories and two idealized interception layouts | Demonstrates the decision workflow; does not measure the pump, token or tank |
| HYCOM GOFS 3.1 historical currents | Three forcing times at 15 m, matched to two historical GDP groups | Compare current-only and current-plus-initial-motion forecasts | Helps investigate model structure; a 15 m ocean field cannot be transferred into a shallow tank |
| NOAA Coral Reef Watch Degree Heating Week | Seven daily values at one historical Florida Keys grid cell | Explain environmental heat-stress context beside the evidence briefing | Explains why a receiving area can be vulnerable; does not measure the artificial coral or validate interception |

### 1. NOAA buoy positions: actual trajectory inputs

**Source:** NOAA AOML Global Drifter Program, ERDDAP dataset `drifter_hourly_qc`, endpoint release v2.01, DOI [10.25921/x46c-3620](https://doi.org/10.25921/x46c-3620). The saved endpoint metadata identifies **CC BY 4.0**. These are quality-controlled, mathematically interpolated hourly buoy positions, not raw GPS fixes or observations of plastic.

All times below are UTC. Row counts count position records only, excluding CSV column and units rows.

| Saved study group | GDP identifier | Position interval | Position rows |
| --- | --- | --- | ---: |
| Initial historical fixture | `8707978` | 1987-10-03 00:00–23:00 | 24 |
| Earlier Atlantic cohort | `12730` | 2000-06-01 00:00–23:00 | 24 |
| Earlier Atlantic cohort | `12731` | 2000-06-01 00:00–23:00 | 24 |
| Earlier North Pacific cohort | `300234063243480` | 2020-06-01 00:00–23:00 | 24 |
| Earlier North Pacific cohort | `300234063472530` | 2020-06-01 00:00–23:00 | 24 |
| Fresh Atlantic cohort | `300234062321360` | 2021-06-01 00:00–23:00 | 24 |
| Fresh Atlantic cohort | `300234062953270` | 2021-06-01 00:00–23:00 | 24 |
| Fresh Indian cohort | `300234060609830` | 2021-06-01 00:00–23:00 | 24 |
| Fresh Indian cohort | `300234063435990` | 2021-06-01 00:00–23:00 | 24 |
| Fresh North Pacific cohort | `300234063123200` | 2022-06-01 00:00–23:00 | 24 |
| Fresh North Pacific cohort | `300234065385690` | 2022-06-01 00:00–23:00 | 24 |
| Matched-current/residual cohort | `300234066836710` | 2022-05-31 00:00–2022-06-01 06:00 | 31 |
| Matched-current/residual cohort | `300534061292930` | 2022-05-31 00:00–2022-06-01 06:00 | 31 |
| **Total** | **13 logical IDs** | **Historical subsets, not a continuous record** | **326** |

For the first eleven IDs, each 24-row trajectory supplies 18 earlier context positions and six later targets. The two matched-current IDs supply 25 context positions followed by six hourly targets; their forecast origin is **2022-06-01 00:00 UTC**. In that matched study, stationary and current-only use the origin; last drift and the initial-residual candidate use the final two context fixes. The earlier 23 context positions are descriptive/QC context, not a fitted training set for those four candidates.

Latitude/longitude are geographic degrees. Ocean velocity and velocity-error diagnostics use metres per second; position errors use metres. The earlier CSVs also contain published `ve`, `vn`, `err_ve` and `err_vn` columns, but those columns do not enter the fixed motion models. The matched-current trajectory CSVs request only ID, time, latitude and longitude.

The initial 1987 day was selected to demonstrate access and ingestion, then reused for a small chronological forecast example. It was not selected as a representative generalization benchmark. The older four-group study acquired four of six planned slots; failed Indian-basin slots remain missing. The subsequent six-group study is a separate, complete acquisition. NOAA's upstream interpolation can use later raw fixes, so Nemo's own forecast-before-scoring checks do not establish raw real-time forecast causality.

**Tank relevance:** these records exercise the same ideas of position, velocity, forecast error and evidence preservation. They contain no tank source labels, camera calibration, mesh-capture outcomes or pump measurements. Model performance on an ocean buoy cannot be reported as tank-token accuracy or proof that a reef was protected.

Saved inputs and methods: [initial CSV](data/public/noaa-gdp-8707978-19871003.csv), [initial provenance](data/public/noaa-gdp-8707978-19871003.provenance.json), [earlier cohort](data/public/noaa-multidrifter-v1/README.md), [fresh selection](data/public/noaa-fresh-drifter-v2/selection.json), [fresh study](docs/fresh-noaa-study.md), and [matched-current acquisition manifest](data/research/matched-current-v2/manifest.json).

### 2. PacIOOS: the ocean prevention scenario's changing currents

**Source:** PacIOOS / University of Hawaiʻi, [ROMS Main Hawaiian Islands](https://www.pacioos.hawaii.edu/metadata/roms_hiig.html), ERDDAP dataset `roms_hiig`. The saved source is forecast-model output, not directly measured debris motion.

- Variables: eastward `u` and northward `v`, in **m/s**.
- Valid times: **2026-10-17 18:00**, **21:00**, and **2026-10-18 00:00 UTC**.
- Selected depth: **0.25 m**; source interval **three hours**; nominal spacing roughly **4 km**.
- Actual saved grid: **3 × 29 × 37** time/latitude/longitude cells: **3,219 total**, **2,997 valid**, **222 masked**.
- Actual bounds: **20.500412–21.505518° N**, **−158.79059 to −157.40552° longitude**.
- CSV size: **222,654 bytes**; captured **2026-10-17 17:02:30.709198 UTC**.
- A separately verified single model issue time is **not available**. The source is an FMRC Best Dataset aggregation, with assimilation described in its metadata. Retrieval before valid time does not by itself prove complete operational forecast causality.

The default ocean comparison replays this fixed snapshot. The saved valid-time window has ended; it is an **archived forecast scenario**, not live conditions. Opening the page does not download newer currents. Interpolated arrows and smooth RK4 trajectories do not add observations or resolve reef-scale eddies. The two layout drawings are idealized first-contact interception hypotheses, not measured collection hardware.

**Tank relevance:** this dataset makes the changing-current layout demonstration concrete, but its geographic metres/m/s do not calibrate a camera in centimetres. Its modeled velocity is not the pump's volumetric flow rate. A physical mesh can alter local flow; the ocean what-if holds currents unchanged.

Read the [saved manifest, exact source URLs and licence](data/current_fields/pacioos-current-forecast-v1/manifest.json), [input guide](data/current_fields/pacioos-current-forecast-v1/README.md), and [ocean comparison contract](docs/ocean-prevention.md).

### 3. HYCOM: the matched historical current experiment

**Source:** HYCOM GOFS 3.1, `GLBy0.08/expt_93.0/uv3z/2022`, via the [HYCOM NCSS dataset metadata](https://ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z/2022/dataset.xml).

- Variables: `water_u`, `water_v`, decoded to **m/s**.
- Valid times: **2022-06-01 00:00, 03:00 and 06:00 UTC**.
- Selected depth: exactly **15 m**.
- Raw dimensions: **time=3, depth=1, latitude=251, longitude=188**.
- Accepted current array: **3 × 251 × 188**, with **135,318 valid** and **6,246 masked** cells out of **141,564**.
- Actual latitude support: **25–35° N**. Actual normalized longitude support: **−80 to −65.03997802734375°**. The requested nominal −65° edge is not an extra saved coordinate.
- At the tile's middle latitude, approximate spacing is **7.715–7.721 km east–west** and **4.434 km north–south**. Spacing is not a guarantee of effective physical resolution.
- Each separately retained v1/v2 NetCDF body is **572,604 bytes**, with its own raw hash. Preserve their separate acquisition identities.

The v1 attempt downloaded current bytes but blocked both trajectory requests after metadata admission failed; its result remains **0/36**. The separate v2 amendment acquired both 31-row buoy trajectories and scored **36/36** model/hour cells. The later initial-residual diagnostic reuses v2's two groups and current inputs; it adds a fourth candidate and **no new scientific acquisition**.

**Tank relevance:** matching model currents with buoy motion helps investigate the forecasting calculation. A 15 m ocean product cannot measure shallow tank circulation, and a drogued buoy is not equivalent to loose surface plastic or the team's foam token. An initial observed-motion residual can combine object response, forcing error and processing differences; it is not an identified tank drag or windage coefficient.

Read [v1 acquisition receipts](data/research/matched-current-v1/manifest.json), [v2 acquisition receipts](data/research/matched-current-v2/manifest.json), [actual HYCOM support](docs/matched-current-v2-results.md#5-actual-current-support-not-an-expanded-nominal-tile), and [the separate exploratory residual result](docs/origin-residual-results.md).

### 4. NOAA Coral Reef Watch: historical reef heat context

**Source:** NOAA Coral Reef Watch daily global **5 km Degree Heating Week**, version **3.1**; ERDDAP dataset `noaacrwdhwDaily`, variable `degree_heating_week`.

- One Florida Keys-area grid cell: **24.575° N, −81.525° longitude**.
- **Seven daily rows**, **1–7 July 2023**, at **12:00 UTC** each day.
- Units: **°C-weeks**. Saved values: **2.96, 3.18, 3.43, 3.72, 3.99, 4.24, 4.53**.
- Original CSV: **383 bytes**; retrieved **2026-10-17 02:04:02.088121 UTC**.

DHW is accumulated heat-stress context from an analyzed satellite-derived product. These are not seven raw satellite images. The displayed values do not directly confirm bleaching and are not current conditions. The seven-day excerpt reads NOAA's already calculated DHW; Nemo does not reconstruct twelve weeks of heat stress from seven days.

**Tank relevance:** the panel explains environmental vulnerability. It does not measure the artificial coral, change source scores or current vectors, estimate ecological damage, or show that interception reduced heat stress.

Read [the CSV](data/public/noaa-coral-context/noaa-crw-dhw-florida-keys-20230701-20230707.csv), [exact provenance and reuse terms](data/public/noaa-coral-context/noaa-crw-dhw-florida-keys-20230701-20230707.provenance.json), and [the interpretation guide](docs/grok-space-context.md#the-real-space-data-artifact).

### Metadata, reused observations and score counts

Dataset descriptions, candidate-origin snapshots, ID/WMO registries and drogue metadata are saved for selection, identity checks and provenance. An identifier appearing in a registry does not mean its complete trajectory was downloaded or used to train a model.

| Research result | Reused inputs | Meaning of its count |
| --- | --- | --- |
| Earlier four-group comparison | Four 24-position trajectories | 96 scored model/hour outcomes from 24 later target positions; two of six planned groups were not acquired |
| LOPO and fixed Kalman diagnostics | The same four earlier trajectories | Additional algorithm comparisons, not four new drifters or newly independent observations |
| Fresh six-group study | Six separate 24-position trajectories | 180 scored model/hour outcomes sharing 36 later target positions |
| Matched-current v2 | Two 31-position trajectories plus HYCOM | 36 scored model/hour outcomes sharing 12 later processed positions |
| Initial-residual diagnostic | The same matched v2 groups and forcing | 48 scored model/hour outcomes reusing those same 12 already-viewed targets; explicitly post-outcome exploratory |

Generated forecasts, cached API responses, public-showcase snapshots and replay reports are derived artifacts, not additional source observations. A score count must not be described as the number of independent experiments. Failed acquisitions remain visible: the first fresh-study attempt selected no trajectories, and the separate Indian extension acquired no new trajectories after its timeout.

### Synthetic data and the missing real experiment

The bundled tank demonstration contains **synthetic** flow samples, a generated drift field, synthetic observations and separately stored evaluator-only release truth. The OpenCV replay uses generated red-token frames. Analytic current fields and hand-authored trial-ledger scenarios test numerical and software behavior. None of those fixtures is measured tank footage, a physical release or an observed capture outcome.

The real experiment still needs its own fixed overhead camera, independently checked water-surface mapping, separate drift-fitting and validation recordings for each layout, and new known-source releases under a frozen protocol. Every token must be accounted for, including unresolved outcomes. A verified release-time/identity anchor is additionally required before matched-time positional error is reported. The current 3D tank is a schematic replay of saved surface paths; it does not manufacture these missing measurements.

Read [synthetic fixture declarations](data/sample_runs/README.md), [field commissioning](docs/field-commissioning.md), [physical validation protocol](docs/prevention-validation-protocol.md), and [3D replay limitations](docs/tank-simulator.md).

### Researched sources that are not integrated datasets

These sources were investigated as possible future inputs. Their scientific payloads or model weights have **not** been downloaded and integrated into Nemo's evidence pipeline:

| Candidate | Possible future use |
| --- | --- |
| TrashCan | Underwater debris detection/segmentation; not overhead red-token training |
| MARIDA | Sentinel-2 multispectral debris-feature segmentation; not an RGB webcam dataset |
| SeaClear Marine Debris Dataset | Underwater ROV object/segmentation evaluation; not release-source labels |
| GLAD near-surface drifter trajectories | Additional motion/dispersion studies with launch-group dependence retained |
| NOAA IOOS/HF-radar currents | Coastal current observations where region/time coverage matches a separate object track |
| NOAA GTS/OSMC fixes | Availability-aware motion evaluation with raw message-time and identifier audits |
| NOAA MDMAP shoreline surveys | Debris amount/type context with survey area, effort and protocol retained |
| Copernicus SMOC merged currents | A separately acquired surface transport input; the implemented local NetCDF reader is not proof of a download |
| Copernicus GLORYS12 reanalysis | A separately designed historical forcing comparison with assimilation limitations |
| NASA OSCAR final v2 | Satellite-informed ocean-scale current research; distinct from the older `jplOscar` mirror inspected for metadata |

OpenDrift/Leeway and OceanParcels are researched model frameworks and examples, not measurement datasets acquired by this project. Documentation or a catalogue entry does not establish access, licensing of every weight, training readiness or a successful experiment. See [the dataset catalogue](docs/datasets.md), [additional researched sources](docs/research-real-data.md), [readiness/next-study notes](docs/grok-ml-next-study.md), and [current-data proposals](docs/next-current-data-study.md).

### Decorative map data

The repository also contains **Natural Earth 1:110 million land**: a commit-pinned, public-domain GeoJSON with **127 land polygons**, **5,143 coordinate pairs** and **138,160 original bytes**. It supports globe presentation, not coastline navigation, mapped reef boundaries, current measurements or tank calculations. Its display role is separate from all four environmental products above. Read [the map provenance](docs/research-evidence/landing-globe-natural-earth.json).


## Scientific formulas, explained through the tank experiment

This is the implemented scientific stack. **Source tracing stays first:** measure a floating token's path, compare plausible release regions, preserve Unknown when the evidence is insufficient, then compare interventions. Ocean movement studies test a different scale and object. The equations below do not make a buoy a piece of plastic or turn a software replay into a physical experiment.

### Symbols and units

| Symbol | Simple meaning | Units or role |
| --- | --- | --- |
| $p,X,z$ | Position, modeled position, observed position | Tank: cm; ocean metric frame: m; API geography: degrees |
| $t,\Delta t$ | Timestamp or elapsed interval | s; ocean timestamps are UTC |
| $u,v$ | Drift vector, or east/north current components | Tank cm/s; ocean m/s |
| $D$ | Constant random spreading strength | Tank cm²/s |
| $\pi_s,w_a$ | Declared candidate-source and release-age weights | Normalized nonnegative weights; source weights are positive |
| $P,Q,R$ | State, process-noise and measurement-noise covariance | Mixed position/velocity units; defined for the Kalman model below |
| $N$ | Number of particles, releases or samples in the stated calculation | Always inspect the denominator; model paths are not independent physical trials |

The camera homography $H_{\rm camera}$ is a **3×3 mapping**; the Kalman observation matrix $H_K$ is **2×4**. They share a conventional letter but are unrelated. Observation quality $g_i$ below is also different from Kalman acceleration spectral density $q$.

### F1. Find the red token and map pixels to centimetres

OpenCV's 8-bit HSV mask accepts hue $[0,10]\cup[170,179]$, saturation $S\ge100$ and brightness $V\ge70$. A 3×3 opening and closing clean the mask. Contours must occupy 25 pixels² to 5% of the frame. Their image centre is:

$$
u_{px}=m_{10}/m_{00},\qquad v_{px}=m_{01}/m_{00}.
$$

The water-plane homography then gives:

$$
\begin{bmatrix}\tilde x\\\tilde y\\w\end{bmatrix}
=H_{\rm camera}\begin{bmatrix}u_{px}\\v_{px}\\1\end{bmatrix},
\qquad x_{cm}=\tilde x/w,\quad y_{cm}=\tilde y/w.
$$

Independent mapping checks use $e_i=\|\hat p_i-p_i\|_2$ and $e_{\max}=\max_i e_i$. Approval requires the declared maximum-error threshold; the default is **0.5 cm**, with at least **four fit pairs and three separate noncollinear check pairs**. A missed or ambiguous token breaks the track. Association also breaks for nonpositive time, gaps over 0.5 s, or displacement greater than $20\Delta t$ cm.

**In our tank:** measure marks at the actual water surface, keep the webcam fixed, and use independent marks to test the map. Moving the camera or waterline requires revalidation. This is planar mapping; it does not recover depth or correct all lens/refraction effects. Accepted detector `quality=1` is a declared value, not calibrated confidence. [Mapping code](apps/vision/reeftrace_vision/calibration.py), [tracking code](apps/vision/reeftrace_vision/tracking.py).

### F2. Measure drift from the observed path

$$
v_x=\frac{x_2-x_1}{t_2-t_1},\qquad
v_y=\frac{y_2-y_1}{t_2-t_1},\qquad
c=\frac{p_1+p_2}{2},\qquad |v|=\sqrt{v_x^2+v_y^2}.
$$

**Simple meaning:** distance divided by time estimates how fast and in which direction the token moved. Samples use non-overlapping associated pairs separated by 0.1–0.5 s. Gaps remain gaps; there is no invented observation between them.

**In our tank:** these measurements describe the floating token under that pump setting, water depth and layout. Timestamps currently use host receipt time, not an independently measured camera exposure clock. Pump GPH measures volume throughput; it cannot be substituted for local token velocity. [Sample extraction](apps/vision/reeftrace_vision/tracking.py).

### F3. Fit a spatial drift field from separate recordings

Positions enter grid cells $c=\lfloor(p-p_{\min})/h\rfloor$. Each cell keeps median position and componentwise median velocity. Nearby cells contribute through inverse-distance weighting:

$$
\hat u(p)=\frac{\sum_{j\in K}w_jv_j}{\sum_{j\in K}w_j},
\qquad
w_j=\max(\|p-p_j\|^2,10^{-12})^{-\alpha/2}.
$$

Exact-node queries return that node's velocity. Defaults are eight neighbours and $\alpha=2$. Support is separate:

$$
S(p)=\mathbf1\{p\text{ inside tank bounds and }\min_j\|p-p_j\|\le r\}.
$$

Node scatter and validation error use $\sqrt{\operatorname{mean}\|v_{pred}-v_{obs}\|^2}$. Validation RMSE includes supported validation samples only, so its coverage must also be shown. The reusable fitter defaults to **5 cm cells / 10 cm radius**; the recorded-flow API defaults to **1 cm / 3 cm**. These are different entry points, not competing measured estimates.

**In our tank:** use separate recordings to fit and check each layout's drift. Current tank flow is a frozen spatial field $u(x,y)$; changing pump conditions are not a commissioned time-varying tank model. A numerical velocity outside support is not usable measured evidence. [Flow model](apps/transport/reeftrace_transport/flow.py).

### F4. Simulate forward from each candidate source

$$
dX_t=[u(X_t)+b]dt+\sqrt{2D}\,dW_t,
$$

$$
X^*_{k+1}=X_k+[u(X_k)+b]\Delta t+
\sqrt{2D\Delta t}\,\xi_k,\qquad \xi_k\sim N(0,I_2).
$$

This Euler–Maruyama model combines measured drift, a declared bias $b$ and constant isotropic dispersion $D$. Particles start uniformly over each candidate polygon. Rectangle walls reflect movement; validated traps absorb on first contact, including crossings between saved nodes. Once absorbed, a particle remains absorbed.

The resolution heuristic halves the step until

$$
V_{\max}\Delta t+3\sqrt{2D\Delta t}\le\ell_{\min}/2.
$$

This is a numerical heuristic, not a guaranteed bound on a Gaussian jump.

**In our tank:** particles represent possible histories of one standardized token under the fitted conditions. Fix dispersion, bias, age prior and step rules before blind releases. This is not a pressure/volume/3D fluid solver and does not predict how an interceptor changes the water. [Transport code](apps/transport/reeftrace_transport/simulation.py).

### F5. Compare each candidate's histories with what the camera saw

For source $s$, particle $n$, possible age $a$ at the first observation and observed positions $z_i$:

$$
r_i=X_{sn}(a+t_i)-z_i,
\qquad
L_s=\sum_aw_a\frac1N\sum_n
\exp\left[-\frac12\sum_{d=x,y}r_d^TC^{-1}r_d\right].
$$

The shared temporal residual covariance is:

$$
C_{ij}=\frac{\sigma_z^2e^{-|t_i-t_j|/\tau}}{\sqrt{g_ig_j}}
+\sigma_m^2+\mathbf1_{i=j}\frac{0.05\sigma_z^2}{g_i}.
$$

Defaults: position bandwidth $\sigma_z=0.7$ cm, shared model bandwidth $\sigma_m=0.3$ cm, correlation time $\tau=0.8$ s. The shared-offset term contributes to **every** covariance entry. Many adjacent observations cannot average it away. Gaussian factors common to sources are omitted; this is a compatibility kernel, not a calibrated density.

For a first-seen-retained endpoint, only already-retained simulated particles contribute:

$$
L_s=\sum_aw_a\frac1N\sum_n\mathbf1_{\rm retained}
\exp[-\|X_{sn}(a)-z\|^2/(2\sigma^2)],
\qquad \sigma^2=\sigma_z^2/g+\sigma_m^2.
$$

The denominator remains **all particles**, including ones that never arrive. Earlier observed history takes priority over an endpoint-only interpretation.

**In our tank:** compare a measured path against candidate releases without exposing the true release label to this function. A shared retained endpoint can erase information; a source may stay Unknown even when the token is clearly visible. [Likelihood implementation](apps/estimation/reeftrace_estimation/estimator.py).

### F6. Normalize source support and decide whether to abstain

$$
S_s=\frac{\pi_sL_s}{\sum_j\pi_jL_j},\qquad
A=L_{\rm leader}^{1/m}.
$$

The implementation uses log-sum-exp to avoid numerical underflow. $A$ is a length-normalized absolute-fit diagnostic for the leading source, with $m$ selected observations. It is not a p-value. If every likelihood is zero, no uniform posterior is fabricated.

**Simple meaning:** a source gets more support when its allowed paths match the observation better, after the declared prior. The result is explicitly `relative_support_not_probability`, conditional on the candidate set and model. Registered app profiles allow 2–5 sources; the reusable estimator allows 2–8.

| Default gate | Requirement |
| --- | --- |
| Absolute fit | At least 0.02 for the prior-weighted leader |
| Top-two prior-weighted support margin | At least 0.20 |
| Top-two likelihood-only support margin | At least 0.10 |
| Observed-field support | 1.00 |
| Minimum candidate mean particle-time path support | 0.90 |
| Mean observation quality | At least 0.50 |
| Trajectory evidence | At least 3 points over 0.5 s; at most 20 selected points |
| Calibration, token, retention and sensitivity | Must satisfy their explicit contracts; changed leader or status under a declared sensitivity variant withholds acceptance |

**In our tank:** `ranked` with a non-null `ranked_source` is an accepted identification. `unknown` is abstention, even with a leading source and bars; `invalid` rejects unusable input. Record every attempt. High relative support cannot guarantee that an unlisted true source will be detected as unknown. [Source gates](apps/estimation/reeftrace_estimation/estimator.py), [mission and source-validation plan](docs/source-tracing-mission.md).

### F7. Follow changing geographic currents without mixing degrees and metres

Ocean mode uses bilinear spatial and linear temporal interpolation:

$$
(u,v)(\phi,\lambda,t)=\sum_{ijk}w_i^tw_j^\phi w_k^\lambda(u,v)_{ijk}.
$$

WGS84 converts current in m/s into geographic movement. With latitude/longitude in radians:

$$
N(\phi)=\frac a{\sqrt{1-e^2\sin^2\phi}},\quad
M(\phi)=\frac{a(1-e^2)}{(1-e^2\sin^2\phi)^{3/2}},\quad
\dot\phi=\frac v{M(\phi)},\quad
\dot\lambda=\frac u{N(\phi)\cos\phi}.
$$

Here $a=6378137$ m, $f=1/298.257223563$, $e^2=f(2-f)$. Code uses equivalent metre-per-degree derivatives. The separate position-only NOAA models use a spherical azimuthal-equidistant east/north map with radius **6,371,008.8 m** and a 50 km prediction-domain limit; this is not the WGS84 ellipsoid.

For $\dot X=f(t,X)$, classical RK4 advances:

$$
k_1=f(t,X),\quad k_2=f(t+h/2,X+hk_1/2),\quad
k_3=f(t+h/2,X+hk_2/2),\quad k_4=f(t+h,X+hk_3),
$$

$$
X_{next}=X+\tfrac h6(k_1+2k_2+2k_3+k_4).
$$

**Simple meaning:** sample changing currents at the start, two estimated midpoints and end of each short step. Masked contributors and missing times stop support; no extrapolation is substituted. Steps align with forcing knots. A smaller step improves a numerical approximation, not the source data's coastal resolution.

**In our tank:** the transferable idea is advancing position under a measured field. Geographic ocean arrays cannot calibrate tank centimetres. The current ocean model has no explicit object windage, diffusion, beaching or physical interceptor response. [Geographic solver](apps/ocean/reeftrace_ocean/advection.py), [geodesy](apps/ocean/reeftrace_ocean/field.py), [numerical checks](docs/rk4-numerical-quality.md).

### F8. Compare against simple movement baselines

Let $p_n$ be the last context position and $v_i=(p_{i+1}-p_i)/\Delta t$.

| Model | Equation | Beginner explanation and tank relevance |
| --- | --- | --- |
| Stationary | $\hat p_{n+h}=p_n$ | Predict no movement. A useful minimum baseline for a future tank replay. |
| Last drift | $\hat p_{n+h}=p_n+h\Delta t\,v_{last}$ | Continue the latest measured movement. Can beat a complex model. |
| Mean drift | $\hat p_{n+h}=p_n+h\Delta t\,\bar v$ | Continue the average earlier velocity. |

The existing NOAA baseline implementations assume hourly cadence. They are not already commissioned irregular-time centimetre models. [Baselines](apps/ocean/reeftrace_ocean/benchmark.py), [mean drift](apps/ocean/reeftrace_ocean/ablation.py).

### F9. Ridge velocity AR(1) and pooled transfer diagnostic

Centre velocity samples by mean $\mu$ and divide by one scalar scale $s=\max(\sqrt{\operatorname{mean}(v-\mu)^2},10^{-9})$. Earlier and next samples form $X,Y$:

$$
A=(X^TX+\alpha I)^{-1}X^TY,\quad\alpha=1,
$$

$$
\hat v_{k+1}=\mu+(\hat v_k-\mu)A,\qquad
\hat p_{k+1}=\hat p_k+\Delta t\hat v_{k+1}.
$$

Code solves the linear system rather than explicitly inverting it. If spectral radius $\rho(A)>0.98$, scale $A$ by $0.98/\rho(A)$. The row-vector convention matters. Own-prefix ridge estimates two mean components and four matrix entries from its permitted prefix only. The post-hoc pooled diagnostic estimates the shared matrix from three other groups' centred prefixes, retaining the held group's permitted mean/last velocity.

**Simple meaning:** learn a small rule for how motion changes, then forecast without resetting to future observations. **In our tank:** the test discipline transfers, but the ocean-fitted coefficients and noise assumptions do not. No model is promoted automatically. [Ridge code](apps/ocean/reeftrace_ocean/benchmark.py), [pooled diagnostic](apps/ocean/reeftrace_ocean/lopo.py).

### F10. Constant-velocity Kalman filter

The research state is $x=[p_x,p_y,v_x,v_y]^T$, in metres and m/s:

$$
F=\begin{bmatrix}I_2&\Delta tI_2\\0&I_2\end{bmatrix},\quad
Q=q\begin{bmatrix}\Delta t^3I_2/3&\Delta t^2I_2/2\\\Delta t^2I_2/2&\Delta tI_2\end{bmatrix},
\quad H_K=[I_2\ 0],\quad R=\sigma_p^2I_2.
$$

Fixed assumptions: $\sigma_p=100$ m, **$R=10000I_2$ m²**, $q=10^{-6}$ m²/s³. This is continuous white acceleration, not the alternative constant-acceleration-per-interval noise convention.

Initialize at the second fix, separated by $\delta$:

$$
x_1=\begin{bmatrix}z_1\\(z_1-z_0)/\delta\end{bmatrix},\qquad
P_1=\begin{bmatrix}R&R/\delta\\R/\delta&2R/\delta^2\end{bmatrix}.
$$

Predict, then update using permitted context positions:

$$
x^-=Fx,\quad P^-=FPF^T+Q,\quad S=H_KP^-H_K^T+R,
\quad K=P^-H_K^TS^{-1},
$$

$$
x^+=x^-+K(z-H_Kx^-),\quad
P^+=(I-KH_K)P^-(I-KH_K)^T+KRK^T.
$$

The implementation uses a gain solve and the Joseph covariance update. Once forecasting begins, no held observation updates are allowed. The anchor is the filtered last context state, unlike raw-position baselines.

**Simple meaning:** balance a simple motion prediction against noisy position observations while carrying model spread. **In our tank:** do not reuse a 100 m assumed error for centimetre measurements. This filter is a separate geographic diagnostic; the tank source engine is the forward-particle comparison above. [Kalman code](apps/ocean/reeftrace_ocean/kalman.py), [exact contract audit](docs/algorithm-contract-audit.md).

### F11. Initial current residual: a separate exploratory diagnostic

$$
b=v_{last}-u_{HYCOM}(X_0,t_0),\qquad
u_{corrected}(X,t)=u_{HYCOM}(X,t)+b.
$$

The offset stays constant in local east/north components and the original RK4 follows the corrected copied field. There is no fitted coefficient, decay or clipping.

**Simple meaning:** let the final observed drift supply one initial discrepancy from the ocean model. **In our tank:** this is not an identified windage coefficient or a calibrated pump correction. It reuses two already-viewed groups and twelve target positions. “Origin” here means forecast start, not a pollution release source. Do not give a reverse-origin calculation a residual derived at the unknown earlier position. [Saved residual study](docs/origin-residual-results.md).

### F12. Measure position, speed and direction errors

For position errors $e_h$ at $H$ prediction times:

$$
ADE=\frac1H\sum_he_h,\qquad FDE=e_H,\qquad
RMSE_p=\sqrt{\frac1H\sum_he_h^2}.
$$

ADE is the average miss; FDE is the final miss; RMSE emphasizes large misses. Tank errors use Euclidean centimetres. Geographic errors use a declared spherical great-circle distance:

$$
d=2R_E\arcsin\sqrt{\sin^2(\Delta\phi/2)+\cos\phi_1\cos\phi_2\sin^2(\Delta\lambda/2)},
\qquad R_E=6371008.8\text{ m}.
$$

Velocity differences use actual successive predicted positions, not future-observation resets:

$$
r_v=v_{pred}-v_{obs},\quad RMSE_v=\sqrt{\operatorname{mean}\|r_v\|^2},
\quad b_{speed}=\|v_{pred}\|-\|v_{obs}\|,
\quad MAE_{speed}=\operatorname{mean}|b_{speed}|.
$$

Tank direction error is $\arccos[\operatorname{clip}((v_p\cdot v_o)/(\|v_p\|\|v_o\|),-1,1)]$. Ocean headings use $\operatorname{atan2}(v_E,v_N)\bmod360^\circ$ and the wrapped absolute heading difference. Direction is withheld below 0.01 cm/s in the tank diagnostic or 0.005 m/s in the ocean diagnostic.

$$
skill=1-\frac{\sum e_{model}}{\sum e_{baseline}}.
$$

The zero-baseline denominator gives null skill. Positive skill is a descriptive reduction in miss, not significance. Equal-group summaries weight complete drifter groups equally; primary results are withheld when required coverage is incomplete.

**In our tank:** score a complete withheld recording or release, preserve gaps and unsuccessful runs, and report coverage alongside error. The separate recorded-path diagnostic forecasts from the first position only using deterministic reflected forward Euler, $X_{k+1}=\operatorname{Reflect}[X_k+u(X_k)\Delta t]$, with $D=0$ and no traps or later position updates. It checks continuous reflected-segment support; the frozen source/prevention engines use finite-node support. [Vector diagnostics](apps/vision/reeftrace_vision/vector_diagnostic.py), [recorded-path diagnostic](apps/vision/reeftrace_vision/field_trajectory_diagnostic.py), [ocean metrics](apps/ocean/reeftrace_ocean/vector_diagnostics.py).

### F13. Distinguish model spread from validated uncertainty

Kalman observed-position checks add measurement noise to latent position spread:

$$
d_M^2=(\hat p-z)^T(P_{pp}+R)^{-1}(\hat p-z),\qquad
d_M^2\le-2\ln(1-a).
$$

The threshold is the nominal two-dimensional Gaussian level $a$. Other training diagnostics use the 90th percentile (`higher` quantile) of earlier expanding-origin errors. Overlapping errors and assumed noise do not establish calibrated 90% coverage.

**In our tank:** source-support bars, scenario envelopes, missing-data bounds and Gaussian ellipses mean different things. A visibly narrow cloud is not proof of accuracy. Independent release-labelled data are needed to evaluate uncertainty and wrong accepted identifications. [Uncertainty contract](docs/algorithm-contract-audit.md).

### F14. Compare interception by the first event

$$
\tau_Z=\inf\{t:X_t\in Z\},\qquad
\tau_T=\inf\{t:X_t\in T\}.
$$

**Simple meaning:** did the token enter the protected zone before encountering an interceptor, within the declared horizon? In ocean mode reef entry wins simultaneous ties. Tank event timestamps are numerical-node upper bounds; ocean contacts are interpolated along supported output chords.

Let $E$ be supported zone entries, $U$ paths unsupported/unresolved before an event or horizon, and $N$ all planned model particles/releases:

$$
p_{entry}\in[E/N,(E+U)/N].
$$

For baseline bounds $[L_b,U_b]$ and intervention bounds $[L_i,U_i]$:

$$
B\in[L_b-U_i,\ U_b-L_i].
$$

Tank recommendations check every declared source/scenario and are withheld if any particle's event-prefix nodes lack support. Ocean layout A is preferred only when its upper entry bound is strictly below B's lower bound; otherwise show a resolved tie or indeterminate result. Unknown paths never disappear from a favorable denominator. These are accounting bounds, not confidence intervals.

**In our tank:** measure separate fields for both layouts; the software does not derive the new water flow from collector geometry. Count full ensembles rather than a few display lines. A no-event tank `unresolved_count` is different from an unsupported path and from an unresolved physical observation. [Tank prevention](apps/estimation/reeftrace_estimation/prevention.py), [ocean prevention](apps/ocean/reeftrace_ocean/ocean_prevention.py).

### F15. Keep missing real trials in predicted-versus-measured accounting

For $P$ planned releases, $R$ logged releases, $E$ zone entries, $U$ unresolved outcomes and $M=P-R$ missing slots:

$$
p_{planned}\in[E/P,(E+U+M)/P],\qquad
p_{logged}\in[E/R,(E+U)/R].
$$

With no logged releases, observed bounds remain **[0,1] with denominator 0**, not a measured zero rate. Benefit subtracts opposite bound endpoints as above. Keep synthetic and operator-reported physical ledgers separate; an operator entry is not automatically camera-verified or a causal-effect estimate.

**In our tank:** freeze and counterbalance the release plan, record entries/interceptions/no-entry/unresolved outcomes, and retain missed planned releases. Do not turn missing evidence into success. [Trial accounting](apps/api/reeftrace_api/services/prevention.py).

### F16. Read satellite heat context and the 3D scene correctly

Nemo reads NOAA's already-produced Degree Heating Week series; it does not calculate DHW from raw satellite temperature images. Its simple displayed change is $DHW_{last}-DHW_{first}$, here $4.53-2.96=1.57$ °C-weeks.

**In our tank:** the reef proxy explains why interception might matter; heat stress does not identify this token's origin or establish coral damage from plastic. The 3D scene replays the same saved surface paths and counts with schematic equipment. It is not a second physics engine. Chalk explains saved numerical evidence; Python computes the authoritative numerical results. [Satellite reader](apps/ocean/reeftrace_ocean/satellite.py), [3D guide](docs/tank-simulator.md).

### F17. Trace backward and forward from a filtered observation

The ocean-source prototype reverses a deterministic field using **both** the negative velocity and decreasing actual time:

$$
\frac{dY}{d\tau}=-u(Y,T-\tau),\qquad Y(0)=X_{observed}.
$$

A copied field reverses time knots/arrays/masks and negates u/v, then the unchanged positive-time RK4 integrates increasing lookback age. Merely negating today's velocity while advancing through tomorrow's snapshots is incorrect. This local ODE reversal does not require a divergence-free field. Random diffusion, beaching and capture cannot simply be undone this way.

The five-step walkthrough separately uses three permitted fixes at 01:00/02:00/03:00 UTC: scatter → connected observed path → causal Kalman-filtered estimates → explicit drift rule → both directions. Its three-fix filter is a separately declared teaching/research example; it does not change the frozen eight-or-more-fix benchmark. From the filtered 03:00 position/velocity:

$$
b_{03}=v_{filtered,03}-u_{HYCOM}(X_{filtered,03},03{:}00),
\qquad \dot X=u_{HYCOM}(X,t)+b_{03}.
$$

The same constant east/north offset is added to a copied field for both branches. The backward equation negates that **whole corrected field** at decreasing physical time; the forward branch advances normally. No earlier/later validation position updates either branch. A future endpoint is a conditional candidate interception rendezvous at a stated time, not guaranteed capture or an optimized physical collector location.

The separate 06:00→00:00 diagnostic shows earlier candidates under 25 fixed endpoint/current perturbation cases at one/three/six-hour lookbacks. They are a sensitivity envelope, not calibrated probabilities or confidence coverage. All cases and failures stay visible; no hull spans missing support. Numerical forward closure and distance to the actual earlier buoy position are separate checks. The saved current-only six-hour mean miss is **8,696.822 m**, versus **2,197.726 m** for last drift; reversing the dynamic current model does not guarantee a more accurate historical position. Both groups are previously viewed, so this is retrospective exploratory reconstruction, not independent pollutant-source validation.

Read the saved study without recomputing it:

```sh
.venv/bin/python -m scripts.evaluate_ocean_source
```

The historical one-time scoring command was `.venv/bin/python -m scripts.evaluate_ocean_source --first-score`. It requires committed reviewed methods and an unused output directory; it refuses to overwrite this existing attempt. The normal reader verifies saved identities/lineage without running inference or contacting a provider. See [the execution and identity contract](docs/ocean-source-research.md#read-the-saved-study-without-running-it-again).

**In our tank:** the observed/filtered/hypothesis labels help inspect a track, but use measured centimetres, actual timing and the tank's own checked drift field. Ocean metre-scale noise and HYCOM at fifteen metres do not transfer. Keep the existing forward candidate-source estimator for blind known-release trials, especially when retention erases path history. [Full ocean-source method, visual stages, API and validation boundary](docs/ocean-source-research.md).

### Turn the formulas into the real tank experiment

| Step | What the team actually measures or freezes | Formulas and evidence | Passing software does not replace |
| --- | --- | --- | --- |
| 1. Set the physical conditions | Inside dimensions, waterline/depth, fixed dry camera, token class, pump outlet and manual setting | Real geometry and session identity | Measuring the team's own bin; the synthetic 40×30 cm map is not its dimensions |
| 2. Approve the water-plane map | ≥4 fit marks plus ≥3 independent check marks at the water surface | F1, maximum error and saved map | A physically checked centimetre mapping |
| 3. Measure each layout's drift | Separate fitting and validation recordings, valid associations and timestamps | F2–F3, validation RMSE plus coverage | Pure water-current measurements or an ocean-to-tank conversion |
| 4. Freeze source inference | Candidate polygons, priors, release-age window, noise/dispersion, gates, variants and full release plan | F4–F6; source/time truth kept evaluator-only | Known-source, independently recorded releases |
| 5. Run blind source trials | Same token and conditions; estimator sees permitted path, never the actual source label | Save Ranked/Unknown/Invalid report before unblinding | Actual source-identification accuracy; retain all planned failures/abstentions |
| 6. Evaluate source results | Unblind labels after saving report; distinguish correct/wrong accepted from abstentions | Correct accepted / planned; correct accepted / accepted; wrong accepted / accepted; accepted / planned; zero denominators stay undefined | A lower NOAA ADE cannot establish these source fractions |
| 7. Compare interventions | Same protected region, independent layout fields, frozen counterbalanced release plan | F14 predicted events; F15 separately logged actual outcomes | Collector efficiency, flow feedback and ecological benefit |
| 8. Review and preserve evidence | Original timestamps/recordings, map/profile IDs, hashes, settings, all trials and missing slots | F12–F15; explicit Chalk explanation bound to evidence | A model answer is not a measurement or permission to change an outcome |

**Current boundary:** physical tank source/interception trials remain zero. NOAA/HYCOM/PacIOOS support separate ocean movement research. They cannot supply missing centimetre calibration, source labels, a plastic response model or measured reef protection. The next source-labelled experiment must keep complete runs/sessions disjoint, freeze decisions before outcomes and never rerun or retune until a favorable answer appears.


## Application states and evidence freshness

Numerical status, case state, agent action and delivery status are separate contracts:

| Contract | Actual states/transitions |
| --- | --- |
| Case | New observation → `OBSERVED`. A committed estimate → `INVESTIGATE` and a new revision/evidence ID, even if its numerical result is Invalid. STOP → `STOPPED`, increments revision and cancels pending recovery tasks. Any recorded manual terminal outcome → `RECOVERING`; new observations/revalidation are required for later live work. |
| Source report | `ranked`, `unknown` or `invalid`. Unknown may retain conditional support values but has no accepted ranked source. Invalid/Unknown are scientific outcomes, not fabricated zero error or a forced winner. |
| Manual recovery task | Current eligible LIVE case → `proposed`; approval within the 60-second expiry gate → `awaiting_human`; operator outcome → `manual_recovered`, `failed` or `uncertain`. Pending tasks can be `cancelled`. Approval is a human task, not motor execution. Synthetic/replay cases cannot create one. |
| Prevention comparison | Frozen to exact source evidence/revision, layout/profile identities and trial plan. A recompute, STOP or recovery makes it archival (`CASE_CHANGED_OR_STOPPED`); history remains readable, while new trials/reviews are rejected. New trials create a new evaluation digest; a stale Chalk answer/receipt cannot silently follow it. |
| Ocean comparison | Read-only `COMPLETED`, `PARTIAL` or `UNSUPPORTED` forcing result; independent `BEST_LAYOUT`, `TIE` or `INDETERMINATE` recommendation. Four hashes bind source, method, selected scenario and complete report. Expiry changes forecast mode and report identity; it never becomes a physical trial or tank comparison. |
| Trial ledger | Immutable one-release rows: `zone_entry`, `intercepted_before_entry`, `no_entry` or `unresolved`. The same key/body retries exactly; a changed body with the same key conflicts. Per-source/layout quotas are enforced. The UI shows the counterbalanced next slot; the API records out-of-order entries and reports `order_followed=false` rather than silently correcting them. |
| Chalk result | Case agent actions include `REPORT`, `UNKNOWN`, `OBSERVE_MORE`, `REQUEST_APPROVAL`, `STOP`; a research review permits only `REPORT`/`STOP`. An agent's STOP ends that turn without authorizing an action; it is not automatically a case STOP. Revision/snapshot checks reject results made stale while a model was responding. |
| Photon | Inbox `pending → processing → done/failed`; outbox `pending → sending → accepted/failed`, with leases and immutable-key/body retries for retryable transport failures. `accepted` means HTTP 202, not Delivered/read. Strict authorized `STOP`, `CANCEL`, `APPROVE` commands bypass conversational generation; quoted prose is not a command. |

STOP never erases saved evidence and does not cut external pump power. The software contains no pump, gantry or autonomous robot actuator. Public research loads are read-only; source/prevention model calls and state changes require local operator access.

### Two export/validation contracts

The current-case `analysis_bundle_v1` export has `payload_sha256` and `payload_canonical_json`. Importing its validation manifest checks exact identity, partition and recomputed trial accounting; it returns **`IDENTITY_AND_ACCOUNTING_CHECKED_METHOD_NOT_RERUN`**. It does not rerun the separate numerical method or prove an independent experiment.

Trace 2's offline validator uses its distinct `content_hash` envelope and full immutable method inputs. Its published synthetic alternatives are alternative outcomes for the same fixture, not additive independent trials. Do not rename hashes or treat a redacted product export as a complete method-replay bundle. [The export-contract audit](docs/software-export-contract.md), [validation protocol](docs/prevention-validation-protocol.md), [Trace 3 contract](docs/trace3-research-and-contract.md), and [Aarush's merged rehearsal](docs/experiment-validation-v2.md) explain the boundary.

## Merged software team work and next steps

The two software-only assignments in [software handoffs](docs/software-handoffs.md) are merged into `main`:

- **Megana — [PR #6](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/pull/6):** [browser demo acceptance matrix](docs/software-demo-acceptance.md), four frontend regressions, explicit button types, step descriptions and a stronger guide focus outline. The matrix distinguishes browser, Node, Python, HTTP, code inspection and blocked scopes.
- **Aarush — [PR #7](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/pull/7):** [export/validator contract audit](docs/software-export-contract.md) and 30 synthetic regressions covering missing/unresolved outcomes, retries, conflicting identities, quota/order accounting, stale receipts and the distinction between product accounting and numerical method replay. This PR does not implement the full current-case method bridge.

These assignments do not depend on a webcam, pump, calibration or new physical data. Jose owns shared application state, scientific interfaces, live provider configuration and final integration. Earlier [four-person](docs/four-person-build-plan.md) and [three-person](docs/team-handoff-prompts.md) plans remain history; they do not expand these current software-only scopes.

Jose's integration follow-up strengthens global/login keyboard focus, moves focus to the source Chalk heading from the Overview guide, announces completed Data Lab reviews and prevention freeze/save results, and removes duplicated no-live-response text. The Prevention URL's `case` parameter retains the source-case context used by the advanced creation form; the loaded comparison has its own visible identity and may be a separate synthetic example.

Next work is concrete: commission the physical camera/mapping and separately measured flow layouts; freeze and run independent source/interception trials; implement and review a complete current-case-to-method-input bridge before claiming numerical method replay for a product export; and verify assistive-technology behavior on real screen readers and additional browsers. The [optional synthetic first-passage bookkeeping audit](docs/algorithm-contract-audit.md#11-next-synthetic-audit-first-passage-bookkeeping) remains a proposal, not an implemented change to frozen algorithms. Retain provider-failure/stale-response behavior and inspect CI for each exact commit. Grok is used interactively for review; its recurring research schedule remains paused. GitHub checks run on code changes. Funded xAI Voice validation and sponsor-track eligibility remain unverified; a chat subscription or unredeemed credit code is not an API result.

## Updated physical rig guide

The [11-page rig guide](docs/tideward-rig-guide.pdf) replaces the earlier clipped build guide. It distinguishes reported inventory from items still needing purchase or confirmation, specifies the earlier planned C920s USB camera and actual pump-adapter check, and gives assembly, mapping, separate layout measurements and first-trial steps. The available **C270 now supplies the live preview**; buying a C920s is not required for that step. See [the current camera guide](docs/camera-preview.md). [Connection diagram](docs/assets/tideward-rig-connections.png) · [measured tank map](docs/assets/tideward-rig-measured-map.png).

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

Ocean integration verification on 17 October 2026: **1,263 Python tests, 163 frontend tests and 137 guarded HTTP checks passed**, with zero HTTP failures and six explicitly blocked external/physical scopes. ESLint, TypeScript and the production build passed. Browser checks covered the single graph, layer and release filters, fixed scales, changing arrow times, scenario reset, the preserved tie, tank access and a 390 px viewport without horizontal overflow. A separate live Chalk `REPORT` cited the displayed comparison and method; these software checks do not establish physical protection or model accuracy.

## Reference map

Historical RK4 numerical-quality checkpoint: **1,365 Python tests, 191 frontend tests and 137 guarded HTTP checks passed**, with zero HTTP failures and six expected blocked external/physical scopes. Ruff, ESLint, route types, TypeScript and an isolated production build passed. Browser checks covered Data Lab/Prevention, layer/release controls, fixed axes, current times, scenario reset and the control tie. A separate live Chalk `REPORT` cited the exact final comparison/method and explained numerical precision separately from physical accuracy. The [safe local receipt](docs/grok-evidence/rk4-final-local-verification.json) records source hashes and scope; inspect hosted CI for the exact pushed commit separately. No physical trial or xAI API call was performed. Later verification checkpoints are recorded above.

The [original matched-current design](docs/matched-current-study-plan.md) is preserved as historical planning. The executed [v1 attempt](docs/matched-current-results.md) retains **0/36 scored cells** after compatibility failures; the separately frozen [v2 compatibility amendment and results](docs/matched-current-v2-results.md) completed **36/36** across two buoy groups and a fixed six-hour horizon. Current-only RK4 had larger mean errors than last observed drift on this small retrospective sample. Neither result changes the earlier six-group NOAA study, promotes a model or validates the physical tank.

- [Complete product and team guide](docs/tideward-product-guide.md): every workspace feature, graph, integration, API family, evidence contract and remaining validation task; the team-facing copy is published in Trov.
- [Architecture](docs/architecture.md), [algorithm/contract audit](docs/algorithm-contract-audit.md), [physics](docs/physics.md), [prevention physics](docs/prevention-physics.md).
- [Integrated demo](docs/integrated-team-demo.txt), [ocean prevention](docs/ocean-prevention.md), [tank prevention workflow](docs/prevention-workflow.md), [verification](docs/verification.md), [CI](docs/ci.md).
- [Live camera and future calibration](docs/camera-preview.md), [read-only public ocean showcase](docs/public-ocean-showcase.md).
- [Fresh NOAA study](docs/fresh-noaa-study.md), [datasets](docs/datasets.md), [original real-data research](docs/research-real-data.md), [motion-vector research](docs/motion-vector-research.txt), [current Grok build record](docs/grok-fresh-build.md), [earlier Kalman build record](docs/grok-kalman-build.md).
- [Chalk/Photon contracts and live-verification history](docs/integrations.md), [satellite/Grok Voice contract](docs/grok-space-context.md).
- [Later field commissioning](docs/field-commissioning.md), [original execution plan](docs/execution-plan.md). Camera frames, contacts, raw physical recordings and credentials stay in ignored local storage; no electronics purchase or physical experiment is required for the current software handoffs.
