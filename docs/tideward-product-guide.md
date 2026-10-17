# Tideward: current product handbook (native USB build)

Current documentation checkpoint: **17 October 2026**. Repository: [Jose-Gael-Cruz-Lopez/reeftrace](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace). **Tideward** is the product name; ReefTrace remains the repository, package and API name.

This is the current complete guide. It supersedes **Tideward — complete product handbook · 17 October 2026**, including that earlier version's pending USB restart investigation, and older setup notes that assume a C920s camera, disabled Photon, or a single default constant-velocity ocean graph. Earlier Trov entries remain reference history. Older study protocols and verification receipts remain historical records rather than being rewritten. The source-controlled guide and its linked technical documents are the detailed reference; the Trov Product document is the team-facing copy.

## 1. What the product does

Tideward helps a team ask where floating pollution could come from, compare where to intercept it before it reaches a protected area, and preserve evidence for checking whether the intervention actually worked. It combines a local camera experiment, numerical transport models, public ocean research and a bounded AI evidence interpreter.

The software has three distinct evidence environments:

| Environment | Inputs and purpose | What a result means |
| --- | --- | --- |
| Ocean comparison | Real, pinned PacIOOS model currents; hypothetical releases, interceptor lines and protected-area proxy | A conditional model comparison, not measured waste movement or a validated reef deployment |
| Tank workflow | Synthetic rehearsal fixtures now; approved camera mapping and measured drift recordings when the rig is commissioned | Source support and frozen layout comparisons conditional on that tank setup; physical accuracy still needs independent trials |
| NOAA research | Historical Global Drifter Program buoy positions, frozen study protocols and fixed models | A replayable comparison of buoy-motion algorithms, not tank calibration or proof of plastic transport skill |

**Real data input, a working interface, a live AI reply and physical validation are different achievements.** The app labels their boundaries rather than combining them into a single success indicator. No underwater robot, autonomous collector, pump controller or trained neural trash detector is implemented.

## 2. Where to use it

### Full local experiment application

Use Python 3.12 and Node 20.9 or newer. From a fresh repository checkout:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,sponsors]'
cd dashboard
npm ci
cd ..
.venv/bin/python scripts/dev.py --check
.venv/bin/python scripts/dev.py
```

The local dashboard is `http://127.0.0.1:3000`; its single-worker FastAPI backend is `http://127.0.0.1:8000`. The launcher bootstraps a private `.env` and local operator token if missing, preserves existing nonblank settings, checks ports, and stops only processes that invocation owns. Credentials and recorded frames are not documentation or public repository content.

The root page introduces Observe → Trace → Prevent. `/workspace` allows public research viewing. `/login` and the operator-access control accept the local operator token privately for protected operations. This is shared local operator access, not individual email/password accounts; the browser holds the token only in tab memory and clears it on reload. Provider keys remain server-side.

The launcher never silently changes sponsor enable flags. A new API process with Photon enabled requires `scripts/dev.py --allow-photon`. Preserve the team's current authorized setting; a read-only demo does not require sending a message or opening the camera.

### Public Vercel ocean demonstration

[Open the Tideward public ocean demo](https://tideward-ocean-demo.vercel.app/demo).

This deployment is deliberately a **read-only ocean showcase**, using checked exported numerical snapshots and the same comparison interface. It includes both fixed scenarios, trajectory/layer checkboxes, release filtering, current arrows, time selection and method disclosures. It has no connection to the Mac webcam, local SQLite, local operator access, Chalk, Photon or xAI credentials. A disabled Chalk control explains this boundary; it does not masquerade a saved answer as a live model response.

The Vercel setting is `TIDEWARD_PUBLIC_SHOWCASE=true`. `/`, `/workspace` and `/login` redirect to `/demo` in that deployment; the localhost FastAPI rewrite is disabled. Do not upload the private `.env` or expose the local API through a public URL. See [public deployment architecture](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/public-ocean-showcase.md).

## 3. Workspace feature map

| Section | Main task | Advanced material kept behind disclosures |
| --- | --- | --- |
| Overview | Start the guided software demonstration and follow the evidence | Saved status, more detailed context and deliberate advanced links |
| Investigations | Load or inspect an observation, compute source support, test assumption sensitivity, ask Chalk | Other observations, complete evidence, case history and controlled manual recovery workflow |
| Prevention | Default ocean comparison; explicitly switch to Tank experiment & trial ledger for local trials | Frozen comparison creation, methods, evaluation exports and validation receipts |
| Camera | Large local USB preview, pixel grid and cursor inspection; controls beneath the image | Tank calibration, drift recording, field/profile admission and commissioning receipt |
| Data Lab | The same single ocean comparison, with controlled overlays | Historical NOAA studies, model tables, motion/uncertainty diagnostics, data provenance and research explanation |
| Settings/operator controls | Inspect configuration readiness and connect local operator access | No browser exposure of permanent provider keys or promise that readiness equals a successful service request |

Scientific details remain available without forcing a first-time presenter to read every field. The interface uses the light-blue Tideward palette, sharp-edged panels, visible units and concise result summaries.

## 4. Ocean prevention: the default demonstration

1. Open **Prevention**. Leave **Ocean · changing currents** selected.
2. Choose **Compare ocean layouts**. The app loads one combined geographic transport plot and the same six releases for no interception, central coverage and flanking coverage.
3. Start with both layout paths visible. Use their independent checkboxes to isolate them. Turn on the no-interception context to inspect what would happen without either line.
4. Show or hide the reef-area proxy, interceptor segments and current arrows. Use one release at a time if overlapping paths are difficult to read. Filtering changes the drawing, not the six-release score denominator or plot scale.
5. Move the current-time control. It changes the displayed current-arrow sample; it does not invent another trajectory or rerun a new experiment. Paths already use currents that vary in space and time.
6. Read the outcome table and recommendation, then select **Ask Chalk about these layouts** in the full local app. The public Vercel showcase cannot make this live request.
7. Select **Original proxy · no-entry model control** to show that a scenario with no baseline entries correctly returns a tie. A scenario change clears the previous report/review rather than carrying stale evidence forward.

### The two fixed scenarios

Both evaluate six hypothetical simultaneous releases over six hours. Each layout has **2,000 m of ideal interception line**; one central segment is compared with two flanking segments of equal total length. All share the same source currents, releases and time horizon.

| Scenario | No-interception entries | Central-layout entries | Flanking-layout entries | Interpretation |
| --- | --- | --- | --- | --- |
| `downstream-corridor-v2` | 6 of 6 | 2 of 6 | 4 of 6 | Central has the lower simulated entry count in this illustrative geometry |
| `initial-proxy-v1` | 0 of 6 | 0 of 6 | 0 of 6 | Tie; capturing different numbers of particles does not establish protection where none would enter |

The downstream proxy was chosen **after viewing the earlier forecast paths**. Its disclosure stays in the report: it is a useful what-if demonstration, not a preregistered independent performance test. Neither rectangle is a mapped real reef. An entry is a modeled geometric crossing, not measured coral damage. Counts are not probabilities or tonnes of plastic removed.

### What the ocean graph represents

- **Path:** a hypothetical passive particle position as it is transported by the model current.
- **Current arrow:** east/north water-model velocity at a sampled position/time, not a measured debris velocity. Display interpolation adds no observed resolution.
- **Protected polygon:** the declared receiving-area proxy; it identifies the first crossing the comparison tries to avoid.
- **Interceptor line:** ideal absorption at first contact. It does not simulate collector capacity, leakage, re-release or the flow changes caused by a real barrier.
- **Common axes:** metres in a fixed local geographic frame. Toggles never rescale the map to make one layout look better. Overlapping prefixes are expected because releases use identical forcing before interception.

The forcing is a pinned PacIOOS Hawaiʻi ROMS snapshot: roughly 4 km grid support, three-hourly east/north velocities at 0.25 m depth, with valid times **17 October 2026 18:00 UTC to 18 October 00:00 UTC**. It is not a continually refreshed live feed. After the valid window, the report explicitly becomes an archived forecast scenario and receives a new complete-report hash. A captured forecast is model output even before expiry, never a camera or ocean measurement.

### Physics and decision rule

The ocean solver uses `dX/dt = u(X,t)`: sample velocity at the particle's changing position and time, then advance using bounded WGS84/RK4 integration. Space uses bilinear interpolation; time uses linear interpolation. Missing values, unsupported geometry or exhausted forcing stop supported integration rather than extending a convincing-looking line.

Each release is integrated once; its unmodified path is evaluated against each layout. First-contact geometry decides whether interception occurs before protected-area entry. Entry wins an exact-time tie conservatively. Event times are interpolated on five-minute output chords, not independently observed timestamps.

For `n` releases, the entry-count bound is `[known entries, known entries + unresolved]`. Every unresolved path remains in the denominator. A layout wins only if its upper entry bound is strictly below the other layout's lower bound; otherwise the result is `TIE` or `INDETERMINATE`. These are accounting bounds, not statistical confidence intervals. See [ocean method, geometry and hashes](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/ocean-prevention.md).

## 5. Source investigations: tracing without claiming certainty

In **Investigations**, connect operator access and choose **Load demo**. The moving synthetic example already has a saved report ranking candidate C. **Recompute source support** deliberately computes a new report and changes its revision/evidence identity. **Test sensitivity** checks predeclared assumption variants rather than recording new observations.

The estimator forward-simulates particles from declared candidate regions and compares the simulated moving history or retained arrival with permitted observations. It uses measured/synthetic local flow, candidate geometry, age assumptions, diffusion and support constraints. It does not simply reverse a current arrow to discover a unique past.

| Scientific result | Meaning | Presenter wording |
| --- | --- | --- |
| `ranked` | One declared candidate passes the model's fit, separation and sensitivity gates | “This candidate is better supported under this frozen setup.” |
| `unknown` | Available observations/assumptions cannot support an accepted ranking | “The evidence does not distinguish a source.” |
| `invalid` | A required input or mapping is invalid | “Fix the measurement/setup before interpreting a source.” |

The retained-endpoint example is **Unknown** because different histories can lead to the same stuck object. Conditional support values do not become accepted source identification merely because numbers exist. Scores are relative support under the model and candidate set; they are not calibrated probabilities that a polluter caused an event. Known release labels belong only to evaluator records and never enter source-estimation features.

The source plot is an observed path or retained point plus the model's candidate comparison. It is not an ocean forecast. Satellite heat stress, public debris images and NOAA buoys do not determine its ranking.

## 6. What Chalk does, exactly

**Chalk is the evidence interpreter and model gateway; Python remains the numerical authority.** The deterministic code computes tracks, source support, entry counts, bounds and states. Chalk routes bounded language-model requests to a configured provider and allows the model to read specific evidence through server-controlled tools. It returns a short explanation and evidence citations; it does not invent replacement scientific numbers.

Typical jobs are: explain why a source is Unknown; describe the assumptions behind a preferred layout; distinguish predicted counts from trial outcomes; explain why a more complex buoy model did not beat a simple one; and state the next independent measurement needed. If the provider fails or the evidence becomes stale, deterministic results remain readable and the AI response safely stops.

### The local request path

```text
User question + selected evidence
  → operator-authenticated FastAPI endpoint
  → snapshot/revision checks
  → bounded investigator + allowlisted read tools
  → Chalk Model Gateway
  → configured underlying model provider
  → validated structured finish and exact evidence citations
  → freshness recheck → explanation in the UI
```

The gateway endpoint is `https://api.chalk.ai/v1/router/chat/completions`, with a server-held bearer gateway key, matching `X-Chalk-Env-Id` and exact permitted model identifier. Private configuration uses `CHALK_ENABLED`, `CHALK_ROUTER_API_KEY`, `CHALK_ENV_ID`, `CHALK_MODEL` and the configured base URL. Copy values privately into the ignored server configuration; never put actual values in Trov, prompts, browser screenshots, the public deployment or GitHub.

**Chalk gateway credentials and a Google Gemini provider key are different.** The gateway key authorizes access to a Chalk environment/connection; the underlying provider credential funds/authenticates the selected model. Google AI Studio free-tier API access is distinct from a Google Cloud trial and a consumer Gemini subscription. No trial-credit entitlement is assumed by this app. The previously authorized Gemini connection has no gateway-enforced daily token budget because the gateway rejected quota enforcement. Local call/time budgets limit each turn; they are not a billing cap. No paid billing is enabled by this guide.

### Evidence-specific permissions

| Investigator | Allowed evidence and output | Limits |
| --- | --- | --- |
| Source case | `get_case`, `get_source_evidence`, registered sensitivity, observe-again and manual collection proposal, subject to role/state gates | At most nine model calls, limited repeated reads, once per other tool; 25-second per-request cap within a 60-second whole turn; no automatic provider retry/switch |
| Tank prevention | Case, source report, exact comparison and evaluation snapshot | Must read/cite required evidence; read-only comparison review cannot alter trials or physics; concurrent trial/STOP/recompute invalidates stale response |
| Ocean prevention | One `get_study_evidence` read for the selected scenario, forcing, method and complete report | At most two bounded model calls and one read; only `REPORT`/`STOP`; cites exactly ocean-comparison and ocean-method identities |
| Fresh NOAA study | Frozen study/protocol evidence and aggregate comparison | Read-only `REPORT`/`STOP`; no acquisition, retraining or model promotion |

Source actions can include `REPORT`, `UNKNOWN`, `OBSERVE_MORE`, `REQUEST_APPROVAL` and `STOP`. A collection proposal is an expiring human task; the model never approves it or runs a motor. An agent's `STOP` ends its turn; it does not by itself stop a case or unplug a pump. Numeric scores remain separate authoritative fields; generated prose with prohibited numerical claims is rejected. Evidence citations establish which report was read, not a guarantee that every sentence is correct.

For ocean review, the browser sends `question`, `scenario_id`, `snapshot_sha256`, `method_sha256`, `scenario_sha256` and `report_sha256`. The server rejects a stale selection before the provider call and verifies freshness after it. Hashes bind the actual displayed result; selecting a different scenario cannot silently reuse the old answer.

**Readiness is not live verification.** Configuration may report ready while `connection_verified` remains false. A completed response must explicitly indicate a live model response. Live case, fresh-study and ocean `REPORT` turns were verified during development; outages/timeouts are still possible. No remote Chalk-hosted evaluation deployment is claimed. See [integration contracts and verification history](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/integrations.md) and [Chalk adapter](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/tree/main/adapters/chalk).

## 7. Tank prevention and predicted versus recorded results

In **Prevention**, deliberately choose **Tank experiment & trial ledger**. **Load prevention demo** loads a clearly synthetic frozen comparison and rehearsal outcomes, separate from the source case and ocean map. The advanced form freezes exact source evidence/revision, baseline and intervention profiles, protected polygon, horizon, particle count and release quota.

Tank geometry is measured in **cm**; time is **s**. Baseline and intervention share candidate sources and protected zone but require separately measured/validated drift fields for a physical test: installing a mesh can change flow. The software does not copy the ocean current field into the tank or copy one layout's measured field into the other.

The simulator checks first zone entry versus collection, including within-step reflected paths. Entering before a later capture still counts as an arrival. Unsupported flow withholds a robust recommendation. Predeclared uncertainty scenarios remain visible; source-support scores are not used as calibrated source weights.

### One release, one immutable trial row

Permitted outcomes are `zone_entry`, `intercepted_before_entry`, `no_entry` and `unresolved`. Interception/no-entry requires full-horizon accounting; a lost token or tracking failure is unresolved. A captured token must remain captured through the horizon. A linked video is provenance, not automatic verification that the human-entered outcome is true.

The UI proposes the next counterbalanced source/layout slot. Out-of-order submissions remain recorded and explicitly report order not followed. The same submission key and body can be retried after a timeout; changing the body for that key conflicts. **Never release a second token merely because saving the first timed out.** Quotas, unique recording lineage, recording-after-freeze and stale-case checks protect accounting.

Predicted particles, hand-authored synthetic outcomes and operator-reported physical releases have separate labels and denominators. Released-only and planned-slot bounds keep missing/unresolved observations visible. A difference bound spanning zero does not establish improvement; these pilot accounting bounds are not confidence intervals. No physical release or measured interception benefit is claimed by the current demonstration.

## 8. Camera, grids and future field commissioning

The actual connected camera is a **Logitech C270**, verified on this Mac as **USB device 0 at 1280 × 720**. Device indices may change after reconnection or on another computer. The earlier C920s shopping plan is not a requirement for the working preview. Use the camera's USB connection to the laptop; no ESP32-CAM programmer, Arduino wiring or MIPI adapter is needed for this selected plan.

Open **Camera**. If it is live, leave it running; otherwise connect operator access, select the external device and choose **Start webcam**. **Close webcam** ends capture. No water tank, pump, calibration or token is required to see the feed. The feed is full-width and keeps the native aspect ratio without cropping; capture controls form a rectangle underneath it.

The optimized preview uses one continuous session-bound MJPEG stream, sending the newest JPEG at up to **15 fps** rather than fetching each frame and rerendering the whole workspace. Capture uses the device's native/default mode; it does not force an unsupported resolution or frame rate. Recorded tracking separately defaults to **10 Hz**. Status polling is every three seconds; cursor updates are animation-frame throttled, grid geometry memoized, and collapsed commissioning opens no duplicate hidden preview. A changed/stale session ends the stream instead of silently switching camera. This reduces software overhead; it does not promise zero end-to-end camera latency.

The restart investigation found that this C270 could open/read at its native **1280 × 720**, while forcing **1920 × 1080** appeared to be accepted but caused reads to fail; forcing **30 fps** was rejected. The fix leaves the native/default capture mode intact. A sustained local sample delivered **49 new frames in 2.011 s**, approximately **24.37 fps**; this run's measured rate is not a fixed requested rate or a guaranteed long-duration device rate.

Actual local hardware verification completed **two API start/fresh cycles separated by graceful stop/restart**, reaching fresh frames in **0.635 s** and **0.637 s** on this Mac's AVFOUNDATION backend. Each HTTP preview delivered twelve multipart frames with strictly increasing sequence numbers, measured at **14.69 fps** and **14.63 fps** (median inter-frame intervals **67.85 ms** and **68.28 ms**). The camera was left on and fresh. This is bounded startup/restart and stream-throughput evidence; inter-frame spacing is not independently measured optical end-to-end latency, long-duration reliability or tank accuracy.

### Pixels and measured coordinates

- **Pixel guide (px):** image-top-left origin, +x right, +y down; at 1280 × 720, valid centres are x 0–1279 and y 0–719. Display resizing does not change native coordinates. The hover crosshair shows pixels, not a ruler.
- **Measured grid (cm):** disabled until a valid, approved water-surface homography matches the current session and image size. It projects the measured plane and clips to the fit-mark hull; no centimetre cursor values are claimed outside it.
- Choose a fixed water-surface corner as tank `(0,0)` and measure consistently. Use at least four spread-out fit marks and three separate noncollinear check marks. Declare error tolerance before fitting; the existing default is 0.5 cm. Units are explicitly converted to cm.
- Grid spacing is a visualization choice, not measurement precision or model cell size. Moving the camera, changing resolution or changing the water plane requires a new mapping.

For calibrated positions and actual receipt time difference, `vx=(x2−x1)/Δt`, `vy=(y2−y1)/Δt` and `speed=sqrt(vx²+vy²)` in cm/s. Receipt times are not independently measured exposure times. OpenCV uses two red HSV hue ranges to find one controlled red token; missing/multiple detections preserve gaps rather than inventing motion. This is color segmentation, not a general learned plastic detector. Pump GPH cannot be converted directly to a local token velocity.

### Commissioning sequence when the tank exists

1. Fix the dry overhead camera, fill to a measured waterline and mark pump/outlet/mesh positions. Keep original pump power manual and separate from laptop electronics.
2. Fit and independently check the measured water-surface mapping.
3. Record separate training and validation drift runs that cover the region of interest; never split adjacent frames into supposedly independent runs.
4. Fit the supported local drift field and inspect held-out velocity/trajectory error and coverage. Do not widen thresholds to force a pass.
5. Admit measured profiles with fixed candidate regions, bounds and collection geometry. Re-measure both layouts separately.
6. Record a new source case, complete the server's preflight and explicit operator attestations, then freeze the field receipt.
7. Freeze the independent trial plan before releases; log all attempts including failures and missing outcomes.

The field receipt checks stored artifact hashes, disjoint recording identities, current camera/mapping/flow/profile and rig state. Operator attestations are not independent hardware verification. Synthetic fake capture tests exercise the protocol without establishing physical accuracy. A rig disturbance or manual recovery requires new drift/revalidation before live actions resume. See [camera guide](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/camera-preview.md), [field commissioning](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/field-commissioning.md) and [rig guide PDF](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/tideward-rig-guide.pdf).

## 9. Data Lab, models and graph meanings

Data Lab opens the same combined ocean comparison so there is one primary default transport graph. Expand **Research details and historical buoy validation** to inspect NOAA studies; historical drifters from other years/places are not overlaid as if they validate the current Hawaiʻi scenario.

| Plot/metric | Meaning | Interpretation limit |
| --- | --- | --- |
| Observed trajectory | The dataset's successive recorded/interpolated positions | Historical buoy positions are not observed plastic or tank measurements |
| Forecast path | A fixed model's prediction from only permitted context | A curved path is not automatically a more accurate prediction |
| Observed/predicted velocity arrows | Position differences or model velocities in their stated units | Token drift, buoy drift and Eulerian water current are different quantities |
| Error/residual vector | Predicted minus observed displacement/velocity | Direction and scale matter; an arrow is not source attribution |
| ADE | Mean position error across scored future steps, in metres for ocean studies | An aggregate on this study, not worldwide skill |
| FDE | Position error at the final forecast step | Does not describe all intermediate events |
| Velocity error | Difference from observed later-interval drift, in m/s | Interpolated buoy products can share upstream information |
| Kalman ellipse/hit count | Declared model covariance plus observation error for observed-position diagnostics | Nominal coverage is uncalibrated, not demonstrated uncertainty reliability |

The newer frozen study uses six GDP-ID days previously unscored by this project. Every group has 24 hourly positions: the first **18** are context, the last **6** are evaluation. It compares five fixed algorithms: stationary persistence, last drift, mean drift, own-prefix ridge velocity AR(1), and constant-velocity Kalman. It scores **180 model outcomes** over **36 unique later intervals**; repeated models are not independent new observations.

The descriptive mean ADE result is last drift **1,573.423 m**, Kalman **1,655.662 m**, ridge **1,772.130 m**. The more complex model did not win; the result is retained without retuning or automatic promotion. Kalman fixes position standard deviation at 100 m and continuous white-acceleration spectral density at `1e-6 m²/s³`; it does not update from withheld future observations.

Selection rules, protocols, raw bytes, failed acquisition, parser/transport amendment, hashes and fixed forecast inputs are retained. Ten older aliases remain unresolved. Distinct GDP IDs/WMOs do not prove physical/statistical independence. NOAA hourly positions are retrospectively quality-controlled/interpolated and may depend upstream on later raw fixes; this is not an operational causal real-time validation.

Earlier reference-buoy, training-prefix, multidrifter, transfer/leave-one-group-out, Kalman and vector panels remain research history. Already-viewed outcomes cannot become a fresh held-out test. Copernicus/NetCDF readers and acquisition instructions exist, but no automatic worldwide field download or matched current-versus-plastic skill study is claimed. TrashCan/MARIDA are catalogued research candidates, not trained models or deployed datasets in this camera pipeline.

See [fresh NOAA study](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/fresh-noaa-study.md), [motion-vector research](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/motion-vector-research.txt), [datasets](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/datasets.md) and [algorithm/state audit](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/algorithm-contract-audit.md).

## 10. Satellite context, evidence briefing and Grok

The satellite panel is a pinned historical NOAA Coral Reef Watch heat-stress/DHW time series for a Florida Keys-area cell. It explains ecological vulnerability; it is not present-day tank water temperature, confirmed coral bleaching, pollution provenance or a feature in source likelihoods.

The evidence briefing builds a deterministic script from a current saved source report plus separately labelled satellite context. A server-side xAI text-to-speech adapter is implemented, with explicit operator invocation and revision/STOP checks. **Voice remains disabled and no funded live Voice API result is claimed.** The sponsor credit code, a Grok web conversation or a consumer subscription is not proof of API use or track eligibility. This guide does not redeem credits, enable billing or make xAI requests.

Grok was used interactively for planning, model/physics review and coding handoffs. Research build records preserve corrections and negative results. Only GitHub push/pull-request checks are the requested recurring automation; a prior Grok research schedule is paused. See [Grok/satellite contract](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-space-context.md) and [fresh build record](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-fresh-build.md).

## 11. Photon: messaging, not an actuator

Photon 2.0 Beta supplies the prepared direct iMessage conversation. The server uses `photonhq-api==0.5.0` against `https://api.photon.codes`, with a private project key and an allowlisted human/agent/case route. A human-initiated conversation and assigned sender are required; an arbitrary judge number is not assumed to work.

The previously authorized local worker is enabled. A corrected automatic round trip was independently observed as Delivered during development. This documentation task sends **no messages** and does not change configuration. A ready/worker-running flag is not delivery proof; HTTP 202 means accepted, not Delivered/read.

The worker polls into a durable inbox, validates authorized routes, separates strict STOP/CANCEL/APPROVE commands from ordinary questions, invokes the permitted case investigator and writes the immutable reply body/idempotency key before sending. Leases permit crash recovery. Exact retries preserve body/key; a changed payload cannot silently reuse a key. Quoted prose mentioning APPROVE is not a command. A separate control lane can process STOP while a conversational model is slow.

Photon cannot determine numerical scientific results or operate a pump. Software STOP cancels eligible tasks without cutting the pump's original AC power. No Photon secrets, contacts, conversation IDs or test-message transcripts belong in public docs. See [Photon adapter](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/tree/main/adapters/photon) and [live integration history](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/integrations.md).

## 12. Architecture and exact API map

```text
Next.js browser UI
  → local FastAPI control plane (operator authentication for changes/model calls)
  → Python vision / estimation / ocean services
  → local SQLite WAL + immutable evidence artifacts

USB webcam → isolated capture process → latest-frame queue → MJPEG preview
                          → explicit recording → red-token tracking → calibrated cm tracks

Pinned ocean bytes → verified current reader → dynamic RK4 tracks → layout event comparison
Pinned NOAA bytes + frozen protocol → fixed forecasts → withheld-position scores

Selected immutable evidence → bounded Chalk investigator → gateway → configured LLM
Authorized Photon inbox → durable worker → case investigator → persisted outbox → Photon
```

Tank coordinates stay cm/cm·s⁻¹; geographic research uses degrees mapped to m and velocities m/s. Geographic angles are never added directly to metres, and ocean fields are never rescaled into measured tank flow. The public Vercel showcase instead serves checked JSON exports through Next.js; it has no local Python/device/provider access.

All local paths below have prefix `/api/v1`. The running local API's `/docs` is the generated OpenAPI reference for exact schemas. Read routes expose intentionally public research/status/evidence summaries; do not expose this loopback experiment API publicly. All POST state/model/camera routes require the operator dependency unless otherwise documented by the running schema.

| API family | Main routes and function |
| --- | --- |
| Health/access | `GET /health`, `/status`, `/operator/session` (authenticated operator check) |
| Cases/evidence | `GET/POST /cases`; `GET /cases/{id}`, `/evidence`, `/actions`; `POST /cases/{id}/estimate`, `/sensitivity`, `/investigate`, `/stop` |
| Profiles and vision | `GET/POST /profiles`; `POST /vision/calibrate`, `/flow/fit`, `/flow/fit-recordings` |
| Camera/recordings | `POST /camera/start`, `/camera/stop`, `/camera/record`; `GET /camera/frame.jpg`, `/camera/stream.mjpg`, `/recordings`, `/recordings/{id}/flow-samples`; `POST /recordings/{id}/case` |
| Local flow diagnostics | `GET /flow/{id}/vector-diagnostic`, `/flow/{id}/trajectory-diagnostic` |
| Field receipt | `POST /field-sessions/preflight`, `/field-sessions`; `GET /field-sessions`, `/field-sessions/{id}` |
| Tank comparison | `GET/POST /prevention/comparisons`; `GET /prevention/comparisons/{id}`; `POST .../{id}/trials`, `.../{id}/investigate`; `POST /prevention/demo` |
| Product export/validation | `GET .../{id}/export`, `/validation-template`, `/validation-reports`, `/validation-reports/{report_id}`; `POST .../{id}/validation-reports` |
| Ocean comparison | `GET /research/ocean-prevention?scenario_id=...`; `POST /research/ocean-prevention/investigate` |
| Earlier current diagnostic | `GET /research/current-forecast`; `POST /research/current-forecast/investigate` (not a second default graph) |
| NOAA/research | `GET /datasets`, `/research/real-data`, `/research/fresh-physics`, `/research/training-diagnostic`, `/research/motion-ablation`, `/research/multi-drifter`, `/research/dataset-readiness`, `/research/lopo-diagnostic`, `/research/kalman-diagnostic`, `/research/vector-diagnostic`, `/research/cohort-vectors`; `POST /research/fresh-physics/investigate` |
| Briefing/context | `GET /research/satellite-context`, `/cases/{id}/briefing`; `POST /cases/{id}/briefing/audio` (disabled provider unless explicitly configured) |
| Manual tasks/rig | `POST /actions/propose`, `/actions/{id}/approve`, `/actions/{id}/cancel`, `/actions/{id}/outcome`, `/rig/disturbed`, `/rig/revalidate`; `GET /actions/{id}` |
| Synthetic loading | `POST /demo/load` creates/reuses labelled rehearsal cases, never physical validation |

The public deployment implements only `GET /showcase/api/v1/research/ocean-prevention` for the two fixed scenarios. Unknown/duplicate query fields fail; POST is 405; hash/schema corruption fails closed. It is not a hosted substitute for every API in the table.

## 13. States, freshness and immutable identity

| Contract | States and consequences |
| --- | --- |
| Case | New observation `OBSERVED`; committed estimate `INVESTIGATE` with new evidence/revision; explicit STOP `STOPPED`; manual terminal outcome `RECOVERING` pending new observation/revalidation |
| Source report | `ranked`, `unknown`, `invalid`, independently of case state |
| Manual task | `proposed` → human-approved `awaiting_human` within expiry → `manual_recovered`, `failed` or `uncertain`; pending tasks can be cancelled; no autonomous actuation |
| Tank comparison | Frozen to source revision/evidence/profiles/plan; recompute/STOP/recovery archives it, preserves history and rejects new stale trials/reviews |
| Ocean forcing/report | `COMPLETED`, `PARTIAL`, `UNSUPPORTED`; recommendation separately `BEST_LAYOUT`, `TIE`, `INDETERMINATE`; expired window changes forecast mode/report identity |
| Trial ledger | Immutable per-release outcomes; identical retries reuse a row, conflicting payloads fail; new trials change the evaluation digest |
| Chalk | Valid structured finish and exact evidence IDs; stale/failed/invalid result stops safely; an old answer cannot become current by remaining on screen |
| Photon | Inbox pending/processing/done/failed; outbox pending/sending/accepted/failed; accepted is not delivered |

Hashes identify different objects: raw forcing bytes, method source, selected scenario, full ocean report, calibration/profile/flow, case evidence and trial evaluation. They are not interchangeable. Checks before and after a network response prevent concurrent changes from authorizing an old result. STOP preserves evidence/history and does not switch external power.

### Two different validation/export contracts

The product `analysis_bundle_v1` export carries `payload_sha256` plus `payload_canonical_json`. Its validation import checks identity/partition/recomputed trial accounting and reports `IDENTITY_AND_ACCOUNTING_CHECKED_METHOD_NOT_RERUN`. This is not a fresh numerical simulation or independent physical test.

The separate offline method validator has a `content_hash` envelope and full immutable method inputs. It can rerun that method when the proper complete bundle exists. A redacted product export is not automatically that full bundle; the complete current-case-to-method-input bridge remains future work. Synthetic alternate outcomes for one fixture are alternatives, not additive independent trials. See [export contract audit](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/software-export-contract.md).

## 14. Testing: what passed and what did not run

The ocean integration checkpoint passed **1,263 Python tests, 163 frontend tests and 137 guarded HTTP checks**, with zero HTTP failures and six intentionally blocked external/physical scopes. Ruff, ESLint, generated route types, TypeScript and a production build passed. Browser checks covered layer/release filtering, fixed scales, changing arrow times, scenario reset, the control tie, tank access and a 390 px viewport. A separate live Chalk ocean `REPORT` cited the displayed report/method. Later camera/showcase changes have their own added tests and exact-commit CI; inspect [GitHub Actions](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/actions) for the current head rather than reusing an earlier total.

Safe software rehearsal:

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

Run full Python/HTTP checks in an isolated source copy without private `.env`, live store, device access or provider flags, using [the CI recipe](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/ci.md). The guarded HTTP runner blocks camera, Photon, audio and model network paths. It verifies real local HTTP workflows with synthetic data, not real hardware. Build in a separate copy if the live Next dev server is being used; concurrent builds can disrupt its `.next` artifacts.

Legacy live-server E2E commands can contact configured Chalk and read private settings. They are not the same as the guarded offline runner. A successful unit/mock test, a successful browser action, a successful hosted CI run, a live provider result and a measured physical accuracy test must be reported separately.

The later camera integration checkpoint passed **1,291 Python tests and 180 frontend tests**, with lint/types/build and the same **137 guarded HTTP PASS / 0 FAIL / 6 expected BLOCKED**. The final native-mode correction additionally passed **31 focused tests** and the separate actual start/stop/restart and multipart-stream verification described in Section 8. Inspect the exact pushed commit's hosted CI separately; a previous suite or the bounded hardware check does not establish physical experiment accuracy or sustained camera reliability.

## 15. What must be validated next

1. **Tank metrology:** measured water-plane mapping with independent checkpoints; stable camera, waterline, lighting and timestamps. A live image alone completes none of this.
2. **Drift quality:** separate training/validation token runs, supported-region coverage, held-out velocity/path error, no gap bridging or adjacent-frame leakage.
3. **Two physical layouts:** independently measured flow for each setup, frozen plan/source regions/quotas/horizon, one accounted token per trial, all unsuccessful attempts retained.
4. **Prediction against outcomes:** compare predicted entries with separately observed/reported entries and interception retention. Keep unresolved/missing outcomes in bounds and report possible adverse effects.
5. **Ocean validation:** contemporaneous independent drifters/object motion, matched forcing, real protected boundaries, windage/waves/diffusion/shoreline/retention and measured collector efficiency. A tank validates a controlled tabletop method, not full ocean deployment scale or coral benefit.
6. **Method/export bridge:** full inputs for a current product export before calling it a numerical-method replay. Further screen-reader/browser checks remain worthwhile.

No API purchase, new neural model or extra dataset is a substitute for those measurements. The current inventory's Arduino/ESP32, ultrasonic sensors, displays, servo and MIPI camera are unused by the USB-camera/manual-pump plan. Coral decoration and 3D printing are demonstration aids, not required functioning components. Confirm the actual pump outlet adapter against its manual before selecting tubing; do not infer dimensions from a generic pump photo.

## 16. Team responsibilities and merged work

- **Megana:** Trace/Lane 1 field evidence and later software demo acceptance/accessibility. Merged [PR 6](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/pull/6) adds the acceptance matrix and frontend regressions. Software acceptance is not completed tank commissioning.
- **Aarush:** Trace/Lane 2 prevention validation, export contracts and missing/unresolved/retry/stale-evidence regressions. Merged [PR 7](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/pull/7) audits the export boundary; earlier pilot templates remain unexecuted physically.
- **Jose:** Trace/Lane 3 shared product/state integration, Chalk/provider configuration, UI, Grok-assisted research, final review and eventual physical commissioning with explicit assigned help.
- **Fourth builder when assigned:** rig assembly/metrology and independent trial operation/logging under the frozen protocol, without changing others' scientific interfaces or provider settings.

Older Trov handoffs may be claimed/history items. They do not replace this reference guide or automatically grant repository access. Current repository permissions, org membership and actual task acceptance must be checked in their respective UIs. See [software handoffs](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/software-handoffs.md) and [four-person plan](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/four-person-build-plan.md), treating earlier physical assignments as planned work rather than completed trials.

## 17. Complete technical documentation index

All links target the existing repository's `main` branch; historical documents retain their original context. This guide's current C270, enabled-authorized Photon, combined ocean default and public-showcase boundaries take precedence over stale narrative examples.

| Need | Reference |
| --- | --- |
| Full overview, start commands and current implementation | [README](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/README.md) |
| Click-by-click presentation | [Integrated team demo](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/integrated-team-demo.txt) |
| Scientific algorithms, exact states and formulas | [Algorithm/contract audit](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/algorithm-contract-audit.md) · [Physics](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/physics.md) |
| Dynamic ocean transport and layout comparison | [Current-driven prediction](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/current-driven-prediction.md) · [Ocean prevention](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/ocean-prevention.md) |
| Tank predictions, trials and validation | [Workflow](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/prevention-workflow.md) · [Prevention physics](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/prevention-physics.md) · [Validation protocol](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/prevention-validation-protocol.md) |
| Export identity versus numerical replay | [Software export contract](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/software-export-contract.md) · [Trace 3 contract](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/trace3-research-and-contract.md) · [Pilot rehearsal](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/experiment-validation-v2.md) |
| Hardware and camera | [Current camera guide](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/camera-preview.md) · [Rig PDF](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/tideward-rig-guide.pdf) · [Connections visual](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/assets/tideward-rig-connections.png) · [Measured-map visual](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/assets/tideward-rig-measured-map.png) · [Field commissioning](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/field-commissioning.md) |
| NOAA datasets and ML diagnostics | [Fresh study](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/fresh-noaa-study.md) · [Datasets](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/datasets.md) · [Original research](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/research-real-data.md) · [Motion vectors](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/motion-vector-research.txt) |
| Chalk, Photon and live-proof boundaries | [Integration contracts](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/integrations.md) · [Chalk source](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/tree/main/adapters/chalk) · [Photon source](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/tree/main/adapters/photon) |
| Grok development and disabled Voice | [Fresh build](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-fresh-build.md) · [Kalman record](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-kalman-build.md) · [Satellite/Voice contract](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-space-context.md) |
| Structure, verification and UI | [Architecture](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/architecture.md) · [Verification](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/verification.md) · [CI](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/ci.md) · [Demo acceptance matrix](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/software-demo-acceptance.md) · [Interface design](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/interface-design.md) |
| Hosted read-only architecture | [Public ocean showcase](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/public-ocean-showcase.md) · [Live public demo](https://tideward-ocean-demo.vercel.app/demo) |
| Team scope | [Current software handoffs](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/software-handoffs.md) · [Four-person build plan](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/four-person-build-plan.md) |

Documentation intentionally excludes private keys, phone contacts, camera frames, raw physical recordings, local session identifiers and private receipts. Keep these in ignored local storage. Update this guide and its Trov copy when a new verified capability or physical result changes these boundaries.
