# Tideward / ReefTrace — four-workstream remaining build plan

Updated 17 October 2026. The product name is Tideward; the repository and API remain
ReefTrace: <https://github.com/Jose-Gael-Cruz-Lopez/reeftrace>.

The shared objective is to show which declared entry points fit an observation,
compare two interception layouts before floating pollution reaches a marked
protected area, and evaluate the decision using separately recorded evidence.

**Current checkpoint:** the software works with historical NOAA data and explicitly
synthetic tabletop cases. The local demonstration contains 23 synthetic cases;
that count may grow during rehearsals and is not a physical trial count. The team
has not assembled or run the first physical rig. Public buoy data do not supply
missing tank measurements. This plan starts from that distinction.

This is the current four-workstream handoff for three named teammates: Megana,
Aarush / Arusha and Jose. Jose owns both P3 product/Chalk and P4 ML/Grok/datasets.
A fourth builder can assist with reproducibility when actually assigned; no fourth
teammate is assumed. Earlier three-person prompts describe
work already merged; do not rebuild those features. The existing field wizard,
source estimator, prevention comparison, trial ledger, validation method, Chalk
adapter, NOAA research and drift diagnostics are starting points. A fixed-parameter
Kalman diagnostic is implemented as another post-hoc comparison on already-viewed
NOAA trajectories; it is not new unseen evidence or a promoted production model.

## 1. One definite physical build

```text
DRY SIDE
Fixed overhead USB webcam ── USB cable / required host adapter ── laptop
                                                               │
                                                      dashboard + local API
                                                               │
                                                 optional network for Chalk

WET SIDE — no electrical connection to the laptop
Pump inlet in bin → pump outlet barb → 3/8-inch-ID vinyl tube
                                      → fixed submerged return outlet in same bin

One red floating token → observed surface path → marked protected polygon
                         with a manually positioned mesh collector upstream

Pump's original power cord → suitable protected mains outlet, operated manually
```

The core hardware is a laptop, one fixed USB webcam, the purchased pump, tubing,
bin, mesh collector, red tokens, a ruler and stable reference marks. There is no
Arduino-to-pump wiring, relay, breadboard power path or submerged servo. The
software's **Stop task** does not turn off the wall-powered pump.

### Inventory audit and final acquisition list

Megana must physically tick each required item in the first work block. “Required”
means present and usable before water trials; borrow it or buy it only if missing.
Cart screenshots establish intended purchases, not delivery or compatibility.

| Required item | What we know | Acceptance check and action if missing |
| --- | --- | --- |
| Laptop and charger | Team computing device available | Runs the repo; USB host/data port works; stays outside splash area. |
| One external USB webcam, its data cable and host adapter | USB webcam is the selected solution; actual possession/model not confirmed | Use a C920s if that is the unit obtained; another standard USB webcam is acceptable only after OpenCV enumerates it and the actual tank image is sharp. Obtain one USB webcam if none is present. If laptop has only USB-C, obtain the matching USB data adapter; do not assume a charge-only connection works. |
| Stable overhead mount | Not confirmed | Borrow a clamp/tripod/rigid support that fixes the complete bin in view. Secure the cable. No hand-held camera. |
| Pond Boss 80 GPH corded pump and supplied outlet adapters | User reports pump purchased | Read the actual model label/manual; identify the matching barb, flow control, operating water level and cord condition. Keep the original cord. |
| Approximately 3 ft / 0.9 m of clear vinyl **3/8-inch inside-diameter** tubing | Required in the current plan; possession not confirmed | Fit to the unit's supplied 3/8-inch adapter before cutting. Do not confuse inside and outside diameter. Obtain this tube only after that fit is checked. If the physical unit lacks that adapter, resolve the exact adapter mismatch first; do not force tubing onto another size. |
| Two suitable small hose clamps and two outlet/mount securing points | Not confirmed | Secure the barb connection and fix the return outlet with a clamp/tie outside the tracked region. Obtain missing clamps/ties. Black tape alone is not a hose seal or a reliable wet mount. |
| Sterilite 6 qt bin or an available larger watertight container | User reports this bin purchased | Measure interior length/width/depth and a usable waterline. Confirm pump submersion, overflow margin, overhead view and collector clearance together. If the purchased bin cannot meet these physical checks, borrow a larger bin; do not distort software dimensions to make it pass. |
| Top Fin mesh breeder / mesh collector | User reports purchase | Measure the actual assembled frame. Published item 5149544 is about 16.5 × 12.4 × 12.9 cm; fit in this particular bin is unverified. Use its mesh in a smaller securely mounted pocket if the full frame blocks the experiment. The measured pocket must retain this token through the declared horizon before modelling perfect absorption. |
| Three identical reusable red floating tokens | Not confirmed | Cut/borrow three equal pieces of clean red closed-cell foam or red plastic that float and appear as one valid red detection. Use **one token per run**, not all three together. Recover and account for every token. Do not use red coral in the camera scene. |
| Ruler/tape measure, seven stable water-plane marks, marker and tape | Black tape exists; other items not confirmed | Four or more mapping marks and at least three **different** check marks at the actual water-surface height. Measure centimetres from one fixed origin. Bin-floor marks are a different optical plane. Obtain missing ruler/marker/reference material. |
| Steady lamp, tray/towels, water and dry mains arrangement | Not confirmed | Reuse existing room/desk lighting if tracking is stable. Keep USB/laptop and plug connections dry; use the pump according to its manual and a suitable GFCI-protected supply. Disconnect pump power before adjusting wet equipment. Obtain or borrow missing practical supplies. |

The listed pump's current retailer page describes 3/8- and 1/2-inch barbed adapters
and no low-water shutoff. Its web copy has inconsistent cord-length details, so the
physical label/manual controls. “80 GPH” is maximum rated discharge, not measured
surface velocity or guaranteed flow through our installed hose. Begin with the
unit's approved low-flow setting and a submerged return aimed along a wall; verify
stable motion rather than assuming the small 6 qt bin is suitable.

Sources checked 17 October 2026:

- [Exact pump listing](https://www.lowes.com/pd/80-GPH-Submersible-Corded-Electric-Pond-Pump/5016653083)
- [Pond Boss manuals](https://thepondboss.net/pages/manuals)
- [Top Fin mesh breeder, item 5149544](https://www.petsmart.com/fish/maintenance-and-repair/breeders-and-nets/top-fin-aquarium-mesh-breeder-5149544.html)

**The protected zone is a measured polygon in the software, marked on the rig's
coordinate reference. Decorative coral is not required and should not delay the
experiment. No live coral or animals are used. 3D printing is not required.**
Use an existing rigid mount, clamp and mesh pocket. A later printed clip is an
accessory only after a measured need is demonstrated; do not build the project
around access to a mobile printer.

### Electronics already owned: keep the core independent of them

User inventory: two Arduino UNO R3 boards; HW-233 slide potentiometer; ULN2003
driver board; solderable PCB, breadboards and jumper wires; 3 W mini speaker;
two HC-SR04 sensors; LCD1602; Elegoo MB V2 breadboard supply; ACEBOTT QA052 car
shield; Waveshare four-digit display; UNO Proto Shield v5; ACEBOTT QA007 ESP32
board; 0.96-inch I2C OLED; incomplete ESP32-CAM; KLT-H4MF-OV5670 V2.0 MIPI camera;
SG90 servo; DHT11; black tape.

Use the tape for external position/reference marks. Store the other electronics
dry as spares. They are not required to prove tracing or prevention. The MIPI
camera does not plug directly into the UNO or a laptop USB port; the incomplete
ESP32-CAM setup has been removed from the selected build. HC-SR04 is not our
underwater flow sensor; DHT11 does not measure submerged water flow. The SG90 is
not a waterproof pump actuator. Do not buy programmers, relays, motor drivers,
extra sensors or speaker amplifiers for this iteration.

## 2. Four workstreams, clear owners, outputs and dependencies

| Owner | Responsibility | Can start now | Depends on | Finished when |
| --- | --- | --- | --- | --- |
| **P1 — Megana** | Physical rig, USB camera, mapping, drift commissioning | Audit actual parts; assemble dry fixture; follow existing wizard | Usable camera/pump/bin/tube/mesh and measured geometry | Real images, approved mapping, disjoint recorded drift sets, admitted immutable profiles for both layouts, field-receipt IDs/hashes and documented blocked gates. |
| **P2 — Aarush / Arusha** | Experimental protocol, blinded source checks, paired prevention releases and validation | Freeze development/final split, token class, source regions, outcome rules and ledger sheet; rehearse synthetic validation | P1's measured profiles and unchanged rig; P3's exact comparison/export | Every release has one ID and accounted token, missed outcomes stay unresolved, independent validation report matches exported hashes, predicted versus recorded outcomes are explained. |
| **P3 — Jose** | Product/UI, shared API wiring, Chalk, end-to-end integration and Trove | Publish these four assignments; run offline demo; improve labels/error flow | Owners' versioned contracts/PRs; physical evidence only when supplied | One understandable walkthrough, honest missing-data states, matching evidence/export/Chalk receipts, passing relevant tests and reviewed green merges. |
| **P4 — Jose, ML lead** | ML diagnostics, Grok-assisted research, dataset/protocol reproducibility; a fourth builder assists or owns reproducibility only when assigned | Replay existing NOAA experiments; audit vector/free-run results; prepare a fresh-data protocol | P1/P2's development recordings for any tank-model change; new independent data for new generalization claims | Reproducible report comparing fixed baselines and failures, preserved public hashes, a decision-relevant error diagnosis and a testable next-measurement proposal. |

Each workstream uses its own branch and focused PR. Jose owns both P3 and P4 and
works through their scopes sequentially, or delegates reproducibility to an actually
assigned support builder. Jose alone integrates shared API,
Runtime/Store, product shell, sponsor wiring and CI changes. Other owners request
a small integration change rather than editing those shared files simultaneously.
Do not overwrite the work already merged from Trace 1 and Trace 2.

### ML implementation roadmap: now versus evidence needed next

| Method and owner | Current status | Data and predeclared contract needed | Useful acceptance check |
| --- | --- | --- | --- |
| **Fixed constant-velocity Kalman diagnostic — P4, integrated by P3** | Implemented on the already-viewed NOAA trajectories; a post-hoc comparison, not fresh unseen evidence or a production-model promotion. | Freeze transition, process/measurement noise, state initialization and units. Correct state only with the training prefix; then predict the full held-out horizon without future measurement updates. Keep the same acquired/missing drifter slots and fixed baselines. | Show per-drifter/free-running ADE, FDE and motion-vector error, including losses and failures. Compare a simple fixed model before adding complexity; no claimed source attribution or calibrated probabilities. |
| **Gaussian-process spatial tank drift — P4 with P1/P2** | Proposed; not fitted or validated. The first physical rig and sufficient development coverage are still missing. | Dense, disjoint **DEVELOPMENT** trajectories spanning the actual measured water plane for each layout; preserve run/frame identity and actual timestamps. Predeclare kernel, spatial length scale, measurement noise, training/validation split and conservative support boundary. Freeze those choices before confirmation releases. | Beat the current frozen-field baseline on disjoint development-run free-running paths without crossing unmeasured holes; retain withheld tracks and denominators. Report predictive spread as a model assumption until empirical coverage is checked. |
| **HF-radar forcing plus learned residual — P4** | Future coastal study; no contemporaneously matched forcing or new independent drifter data has been acquired. | Versioned protocol, current-field coverage and QC/masks matched in UTC/coordinates/depth to drifters, availability/as-of semantics and whole physical-drifter alias groups held out. Learn residuals only from training groups; do not join modern radar fields to the existing 1987 sample or substitute interpolated retrospective data for operational observations. | Compare forcing-only, existing simple motion baselines and forcing-plus-residual on untouched physical drifters; include unmatched requests and failed coverage. Establish motion skill before claiming a better interception decision. |

Primary references explain the building blocks, not completed Tideward integrations:
[OpenCV KalmanFilter](https://docs.opencv.org/4.13.0/dd/d6a/classcv_1_1KalmanFilter.html)
documents separate prediction and measurement correction; [FilterPy process-noise
discretization](https://filterpy.readthedocs.io/en/latest/_modules/filterpy/common/discretization.html)
shows why a fixed noise definition and time step matter. [NOAA GDP hourly data](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php)
and [Elipot et al. 2016](https://www.aoml.noaa.gov/phod/gdp/papers/Elipot_et_al-2016.pdf)
describe the quality-controlled, interpolated product and its limits. [Gaussian-process
documentation](https://scikit-learn.org/stable/modules/gaussian_process.html)
explains kernel/noise assumptions; the development-data and support gates above are
our proposed experiment requirements. [IOOS HF radar](https://ioos.noaa.gov/project/hf-radar/)
and the [NDBC current-data catalog](https://dods.ndbc.noaa.gov/thredds/catalog/hfradar.html)
are the starting points for a later bounded forcing-acquisition protocol. None of
these references supplies missing tank evidence or proves coral benefit.

### Immediate work blocks

1. **First 45 minutes, the three named teammates:** record the coordinator-approved green `main`
   SHA; verify repo/Trove access; P1 ticks inventory while P2 freezes a draft pilot
   protocol, and Jose runs the offline HTTP audit before the P4 NOAA replay. A support
   builder can run the reproducibility checklist only after being assigned.
2. **Next 1–2 hours, parallel:** P1 builds the rig and maps the water plane; P2
   rehearses ledger/validation with synthetic fixtures; P3 resolves product/E2E
   issues, then switches to P4 diagnostic errors and an untuned protocol. Do not
   schedule Jose as two simultaneous builders.
3. **First valid physical drift session:** P1 records separate calibration and
   validation runs for each layout; P4 reviews coverage/vector/free-run errors.
   If a gate fails, add development measurements or fix the setup. Never widen a
   tolerance or radius merely to pass. P2 keeps these runs out of final validation.
4. **First physical pilot:** after both layouts and the source case are valid,
   P3 freezes a comparison with `trials_per_source=1`: three sources × two layouts
   = **six fresh releases**. P2 follows the exact frozen sequence. Twenty-second
   horizon is the working target; freeze a shorter supported horizon only before
   starting the plan. Incomplete slots remain missing. This is a feasibility pilot.
5. **Confirmation and presentation:** freeze any improved setup before new
   confirmation data. A quota of five gives 30 releases, not 30 independent tank
   setups. Complete it only within the actual event time available; never describe
   six or fewer releases as a finished 30-trial experiment. P3 presents the real
   denominators, disagreements and limitations. These blocks do not reset the
   hackathon clock or promise a physical result before the rig passes.

During a wet trial Megana maintains the marked configuration; Aarush releases and
retrieves one token and controls evaluator-only source truth; Jose observes and
records the first event/ledger entry, then checks the saved timing/visibility and
token accounting before the next release. A fourth support builder, if actually
available, can perform that separate check. Three people are sufficient by doing
these steps in sequence; do not omit a check to run simultaneous jobs. For blind
source testing, keep the release label hidden from the estimator and the person
reading its prediction until the result is saved.

Moving the collector can change flow. Restore a layout to its measured marks,
record the disturbance and perform the existing revalidation before reuse. Do not
recompute the source case after freezing a comparison: that archives its plan.

## 3. Shared start, tests and merge rules

Use the actual repository, not a copied starter. First inspect `git status --short`.
Preserve other people's uncommitted files. Fetch and fast-forward only a clean
checkout; create the assigned branch from the coordinator's tested `origin/main`.
Record `git rev-parse HEAD` in the PR. If a suggested branch already exists, inspect
its owner/history rather than resetting it. Do not force-push or push directly to
`main`. Jose merges only reviewed PRs with the required checks green.

Read `README.md`, `docs/integrated-team-demo.txt`, `docs/architecture.md`,
`docs/field-commissioning.md`, `docs/prevention-physics.md`,
`docs/prevention-workflow.md`, `docs/prevention-validation-protocol.md` and the
applicable `AGENTS.md`. For dashboard edits, read the installed Next.js guidance
required by `dashboard/AGENTS.md` before changing components.

From the repo root, run a hardware/provider-free baseline:

```sh
.venv/bin/python scripts/dev.py --check
.venv/bin/python scripts/e2e_offline.py
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check apps adapters scripts tests
.venv/bin/python -m pip check
git diff --exit-code -- data/public data/sample_runs
```

Dashboard checks, from `dashboard/`:

```sh
node --test tests/*.test.mjs
npm run lint
npx next typegen
npx tsc --noEmit
npm run build
```

`e2e_offline.py` starts its own temporary API and disables/guards providers,
messaging and cameras. Its blocked live/hardware scopes must remain blocked.
Tests use isolated stores and fake devices, not private live data. Regular
`scripts/e2e_demo.py` and sponsor-aware audits can make live calls; Jose coordinates
them explicitly instead of treating them as offline tests.

For the interactive app use `.venv/bin/python scripts/dev.py`. If preflight reports
the already-authorized Photon worker is configured, Jose handles that existing
launch setting rather than another owner toggling it. **Leave live Photon settings
unchanged and send no new test messages under these assignments.** No keys, phone
handles, `.env`, billing changes or provider-account screenshots go in Trove,
Grok, Git, PRs or public reports. Live Chalk readiness and successful model response
are separate facts. Unavailable Chalk must leave deterministic results usable.

Camera frames, SQLite and real evaluator truth stay under ignored `data/local/`
or another explicitly private local directory. Commit only small scrubbed synthetic
fixtures and public-data provenance that has been deliberately reviewed. Preserve
existing pinned CSVs, manifests, frozen algorithm files and hashes.

## 4. Copyable prompt — P1 Megana, rig and commissioning

```text
Owner: Megana. Project: Tideward / ReefTrace.
Repository: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace
Suggested branch: team/rig-commissioning-v2, from coordinator-approved green main.

Read docs/four-person-build-plan.md and docs/field-commissioning.md first. Earlier
Trace 1 software is already merged; preserve it. The first physical tank has not
run. Do not represent synthetic fixtures or the 23 demo cases as physical trials.

Your goal is an actual fixed USB-webcam rig and two traceable measured layout
profiles. Start by photographing/reading the pump model privately and ticking the
required inventory audit: webcam/data cable/host adapter, rigid overhead mount,
working 80 GPH pump, correct supplied barb, about 3 ft of 3/8-inch-ID vinyl tube,
clamps, measured watertight bin, fitted mesh pocket, identical red floating tokens,
ruler, water-plane reference marks and stable lighting. Confirm actual adapter
fit before tubing purchase/cutting. Measure bin and mesh clearance; 6 qt capacity
does not guarantee pump operating depth or room for the assembled breeder frame.
Use the mesh in a smaller secured pocket if needed and validate its retention.

Use one definite wiring path: USB webcam -> laptop. The pump runs manually on
its original cord; no Arduino, ESP32-CAM, MIPI camera, relay, servo or breadboard
power wiring. Keep electronics dry. Use a measured protected polygon; decorative
coral and 3D printing are not build dependencies.

In Camera, explicitly select/start the external webcam. Fit the water-plane map
from four or more measured correspondences and at least three distinct check
marks. Save session/calibration IDs. Record at least two independent training
drift runs plus separate validation drift for each layout. Use one token at a
time. Run existing recorded-vector and free-running-path inspections; unsupported
paths, gaps or bad error are evidence to repair the rig, not to relax gates.
Create separately recorded baseline/intervention fields with nonoverlapping
recordings and freeze their profiles using development-declared tolerances.
Follow disturbance/revalidation and freeze the field receipt only when gates pass.

Own new rig checklist/run-log documentation and narrowly scoped fixes to your
existing field-workflow components/tests. Demonstrate any code bug before editing
vision/capture/calibration. Jose alone edits shared main.py, Runtime/Store, product
shell, sponsor adapters and CI; send a small integration request if needed.

Deliver: inventory PRESENT/MISSING/FIT-FAILED record; measured setup sketch and
waterline/outlet/camera/collector marks; real calibration/recording/profile/field
receipt IDs and hashes; exact remaining blockers; scoped tests and focused PR.
Keep raw images/private paths/evaluator source answers out of public commits.
No automatic camera opening, messages, credential work or physical-validity claim
from fake capture. A blocked hardware gate is an honest deliverable, not READY.
```

## 5. Copyable prompt — P2 Aarush / Arusha, experiment and validation

```text
Owner: Aarush Mane / Arusha (confirm your display name in Trove).
Project: Tideward / ReefTrace.
Repository: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace
Suggested branch: team/experiment-validation-v2, from approved green main.

Read docs/four-person-build-plan.md, docs/prevention-workflow.md,
docs/prevention-validation-protocol.md and actual trial/export schemas. Your
earlier Trace 2 method is merged. Do not rebuild it or silently replace contracts.

Own the experimental question and the independent evidence: does the upstream
layout reduce first entry into the same protected polygon under matched token,
source, waterline and declared horizon? First prepare the protocol and rehearse
with synthetic fixtures while Megana commissions the real rig. Declare complete
run/session development-vs-confirmation partitions before viewing final outcomes.
Release labels belong to the evaluator/validation ledger, never CaseInput or the
Chalk source-inference tools.

After P1 supplies two admitted measured profiles and P3 freezes the comparison,
perform a six-release pilot using trials_per_source=1 (A/B/C, two layouts) in the
exact saved sequence. Follow the existing rig disturbance/revalidation process
on layout changes. A subsequent five-per-cell plan is 30 NEW releases and must be
frozen separately; do not pool pilot/development outcomes as final confirmation.

For each actual release: one recovered token, stable configured layout, new
recording begun after plan freeze, exact trial key, source/layout, event time and
token accounting. Zone entry before later collection is still zone_entry. Lasting
interception/no_entry requires observing the complete frozen horizon. Lost tracking
or an unaccounted token is unresolved. Retry a failed request with the exact saved
key/body; never release another token merely because a network request timed out.

Run the existing offline validator on a scrubbed export. Check plan/profile/flow/
evaluation hashes, denominator arithmetic, duplicate identities, independent split
references and disagreements with predictions. Missing/unresolved observations
remain in bounds. Report wrong source rankings, Unknown and Invalid separately;
an always-Unknown estimator is not successful source validation.

Own new physical protocol/checklist, evaluator-only local run log and focused
validation tests/bug fixes. Numerical changes require a reproducer and coordination
with Jose before shared contracts change. Do not edit API/runtime/store, dashboard,
Chalk/Photon or public NOAA datasets. Never forge physical outcomes to finish UI.

Deliver: frozen protocol; actual completed/planned/unresolved counts; separate
synthetic and physical evaluation; matching export and validation report hashes;
one next-needed measurement justified by the evidence; exact tests and focused PR.
Do not claim statistical significance, proven polluter identity, corals saved or
ocean-scale benefit from a small tabletop pilot. No provider/camera automation.
```

## 6. Copyable prompt — P3 Jose, product/UI, Chalk and Trove

```text
Owner: Jose. Project: Tideward / ReefTrace.
Repository: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace
Suggested branch: team/product-integration-v2, from approved green main.
Trove workspace: https://trov.dev/nemo/#mywork

Read docs/four-person-build-plan.md, integrated-team-demo.txt, architecture,
integration and verification docs, plus dashboard/AGENTS.md and the required
installed Next.js guides. Keep the light-blue frosted-glass design and existing hero/local
operator entry flow; this iteration is product clarity and reliable actions.

You own shared API/runtime/store wiring, page shell, sponsor integration, evidence
export/history and CI. You also own P4 ML/Grok/datasets: keep its branch and
review checkpoint separate from P3, and sequence your time between both streams.
Coordinate P1/P2 contracts and the P4 model contract rather than duplicating their
math. Review existing merged work before changing it. Begin with scripts/e2e_offline.py
and the actual browser: source observation -> source support/Unknown -> declared
sensitivity -> prevention layouts -> trial ledger -> export/validation -> Chalk.

Make every state understandable: historical buoy versus synthetic replay versus
recorded but unverified tank capture; position error cm/m versus vector error
cm/s or m/s; supported fraction and withheld whole runs; planned versus actual
releases; source support versus calibrated probability. The predicted path must
not reset to observed positions. Preserve the continuous reflected-step support
guard in the new free-running diagnostic and its explicit D=0/no-traps scope.

Keep deterministic tables authoritative. Ask Chalk only about exact saved case,
comparison and evaluation evidence; display actual live-response/tool citations.
Timeouts/STOP/stale case or trial revision must not create a successful-looking
receipt. Preserve working numerical results when a provider is unavailable.
Keep existing live Photon configuration unchanged; do not send new messages,
change pairing, retrieve keys or alter billing as part of this assignment.

Publish four named handoffs/prompts in the existing Nemo project linked to this
exact repository. Assign P1 Megana, P2 Aarush/Arusha, P3 Jose and P4 Jose (ML
lead). A fourth builder can assist or own reproducibility only when an actual
member is assigned; do not invent an unassigned primary ML owner. Verify
member/project visibility and repository association with an actual member view or an explicit teammate confirmation.
Creating a handoff is not proof of visibility, branch creation or completed work.
Do not publish secrets, raw local camera evidence or phone numbers. Include branch,
allowed files, dependency, acceptance checks and PR link in each handoff.

Deliver: clear end-to-end walkthrough and browser evidence; passing scoped/full
checks appropriate to integrated changes; Trove links with visibility evidence;
reviewed PRs merged only after green required checks; exact final main SHA and
remaining physical/provider blockers. Preserve other people's edits and never
force-push or discard teammate work. Do not call mocked providers live evidence.
```

## 7. Copyable prompt — P4 Jose, ML/Grok and reproducible datasets

```text
Owner: Jose, ML lead. A fourth builder assists or owns reproducibility when
actually assigned; Jose remains the primary P4 owner. Project: Tideward / ReefTrace.
Repository: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace
Suggested branch: team/ml-evidence-v2, from approved green main.
Existing Grok project/conversation:
https://grok.com/project/709fdaeb-06db-41bd-843b-81f567b993da?tab=conversations&chat=139b9a9d-215a-47f0-9f1f-81db9103e724

Read four-person-build-plan.md, ml-experiment-audit.txt, motion-vector-research.txt,
datasets.md, research-learning-plan.md and frozen protocol/manifests. Current
NOAA data already exists; the four-drifter vector analysis is post-hoc and has two
missing acquisition slots. Do not call it fresh unseen validation. The fixed-parameter
Kalman diagnostic now implemented is also post-hoc on already-viewed data;
review its stated measurement/process assumptions and preserve all comparisons. It
is not proof of fresh unseen generalization or authority to promote a model. The
pooled residual model was worse; do not tune on these outcomes until a score improves.

Your goal is a decision-relevant error diagnosis and the smallest justified next
model/data experiment. Replay current fixed models, preserve losses and failed
denominators, inspect per-drifter/horizon vectors and free-running errors. The
same observations reused by four models are not four new measurements. Match
UTC, units, physical drifter aliases, development/final groups and as-of metadata.
Do not edit any pinned CSV, protocol/manifest/hash, benchmark.py, ablation.py,
multidrifter.py or lopo.py merely to make integrity checks pass.

Use the existing Grok project for detailed review of public code/contracts and
primary-source papers. Provide the repo URL, exact commit, scientific question,
data roles, split, units, failed results and permitted scope. Ask it to challenge
leakage, object-depth mismatch, invalid uncertainty and the link from lower motion
error to layout decisions. Grok's text is a review proposal; locally reproduce and
test every accepted change. It does not automatically have working repo write access.
Never paste keys, .env, private recordings or evaluator release answers into Grok.

When P1 supplies DEVELOPMENT drift recordings, use frozen recorded-field vector
and free-running diagnostics to locate missing support or systematic error. More
calibration in the needed region may be better than a larger model. Propose a new
bounded method only with explicit training inputs, baselines, no future resets,
whole-run holdouts, numerical contracts and an untouched confirmation protocol.
P2's final releases must not be used to choose parameters or a preferred layout.

For future ocean work, prepare a versioned acquisition protocol before fetching
new data: source/license/schema, region/time/depth, whole physical drifter IDs,
excluded viewed IDs, metadata-only selection, request/byte budgets and retained
failures. IOOS hourly coastal currents require matched coverage/QC; GLORYS begins
1993 and cannot join the 1987 sample. GTS WMO IDs need GDP identity mapping.
MDMAP shoreline counts require survey effort and are not source labels. No broad
download, external weight import or ocean model replaces missing tank ground truth.

Own new isolated ML/research modules, owned tests and new protocol/report files;
coordinate imports/API/UI through your separate P3 integration stream. Preserve
existing frozen modules and shared
adapters. Deliver one reproducible report, primary citations, exact metrics/counts,
one useful next measurement, scoped tests and a focused PR. No automated model
promotion, false probabilities, provider/account changes or new messages.
```

## 8. Final demonstration and handoff receipt

Jose should show the informative trajectory and Unknown endpoint, explain conditional
support, compare both layouts, show actual planned/released/unresolved denominators,
inspect the recorded-field diagnostics, export matching evidence and ask Chalk to
explain its limitations. Show real historical NOAA as a separate motion benchmark.

If physical gates are incomplete, present the synthetic software rehearsal and the
unfinished physical checklist explicitly. A genuine negative result or Unknown is
better evidence than an invented success.

Every owner hands back: owner/branch/starting SHA; exact files changed; executable
test commands and results; synthetic/historical/recorded data origin; actual artifact
IDs/hashes; remaining blockers; PR URL. Jose records final reviewed main SHA and
Trove assignment links. This document alone does not create Trove invitations,
publish handoffs, create branches, run hardware or establish visibility to members.
