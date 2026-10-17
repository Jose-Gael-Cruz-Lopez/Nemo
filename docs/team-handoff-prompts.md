# Three-person implementation handoff

These prompts are for the **next iteration after the current prevention slice is
merged and green**. Give each person a separate repository branch/task in Trove.
Do not ask three people to rebuild the existing comparison, ledger or dashboard.
No external task has been created or messaged by this document.

The scope is a coastal decision-support **prototype tested in a tank**. The
software does not establish ocean transport accuracy, coral benefit, a known
polluter or an autonomous cleanup capability. Existing hardware is sufficient:
USB camera, laptop, tank, independently powered circulation pump and manual mesh.
No new actuator, robot, sensor, 3D printing or model-provider purchase is required.

## Starting point: already implemented

- Source tracking/calibration, recorded drift fitting, immutable profiles,
  conditional source evidence, sensitivity, Unknown/Invalid and durable STOP.
- A bounded two-layout first-passage simulator; registered profiles, source and
  flow hashes; frozen protected zone and experiment plan.
- A separate idempotent one-token trial ledger, full-horizon attestation,
  conservative missing/unresolved bounds and separate synthetic/physical groups.
- A Prevention dashboard, explicitly synthetic rehearsal, read-only Chalk review
  and a local HTTP audit. These are implemented, not new assignments.
- Public NOAA drifter benchmark, training-only diagnostic and historical satellite
  context. These do not supply tank flow or source labels.
- Photon transport is implemented, but **`PHOTON_ENABLED=false` must stay false**.
  No test messages, automatic replies or channel experiments are authorized.
- xAI narration remains disabled/unverified. No new credentials or billing work.

Read `README.md`, `docs/architecture.md`, `docs/verification.md`,
`docs/prevention-workflow.md`, `docs/prevention-physics.md` and applicable
`AGENTS.md` before editing. For dashboard code, read the installed Next.js guides
required by `dashboard/AGENTS.md`.

## Ownership and integration rules

| Lane | Outcome | Exclusive write scope |
| --- | --- | --- |
| 1 — Field evidence | A guided, reproducible calibration/recording workflow and a frozen field-session manifest | New field-session backend/schema/router/tests; new field-workflow UI; vision fixes only when demonstrated by a regression |
| 2 — Validation | Offline prediction-versus-outcome validation and an honest next-measurement recommendation | New validation module/CLI/fixtures/tests; numerical prevention fixes only when demonstrated by a regression |
| 3 — Product integration | Mount the two additions, export reproducible evidence and verify the complete experience | Shared API/runtime wiring, product shell, Chalk integration, export, browser/E2E tests and CI |

Lane 3 alone edits `apps/api/reeftrace_api/main.py`,
`apps/api/reeftrace_api/services/runtime.py`,
`apps/api/reeftrace_api/services/store.py`, `dashboard/app/page.tsx`,
`adapters/chalk/**`, `.github/workflows/**`, and existing prevention UI/service
wiring. Other lanes send a small integration request instead of editing them.
Existing inference schemas stay unchanged unless all three approve a versioned
contract change. In particular, **never add release truth to `CaseInput`**.

Start each branch from the coordinator's exact green `main` SHA **after** the
prevention slice lands. Record that SHA in the PR. Suggested branches:
`team/field-evidence`, `team/prediction-validation`, `team/product-integration`.
Do not push directly to `main`, force-push another person's branch or merge an
unrelated historical implementation. Use one focused PR per lane. Lane 3 reviews
contract compatibility; the coordinator merges only after required checks pass.
Rebase/update from `main` after a prerequisite merges and rerun affected checks.

## Shared contract freeze

The existing prevention API is the baseline; inspect its current schemas instead
of inventing a parallel contract:

| Existing endpoint under `/api/v1` | Contract to preserve |
| --- | --- |
| POST `/prevention/comparisons` | Active case/current noninvalid source evidence, baseline profile matching case, compatible registered profiles, frozen zone/horizon/plan |
| GET `/prevention/comparisons/{id}` | `{comparison,trials,evaluation,is_current,archive_reason}`; archival reads remain available |
| POST `/prevention/comparisons/{id}/trials` | Exact stable `trial_key`, one token, explicit outcome/time/accounting/horizon attestation; retry never means release another token |
| POST `/prevention/comparisons/{id}/investigate` | Read-only evidence review tied to source revision and `evaluation.snapshot_hash` |
| POST `/prevention/demo` | Clearly synthetic software rehearsal, never physical rates |

`comparison.data_origin` is `SYNTHETIC` or `MEASURED_TANK`. Trial origin is
`SYNTHETIC_DEMO` or `OPERATOR_REPORTED_PHYSICAL`. Keep both evaluation groups,
including empty groups. Planned slots and actual releases are different counts;
missing/unresolved slots remain unknown. Source scores are not probabilities and
cannot become weights for ecological benefit. The fixed field, reflecting walls
and perfect absorbing retention are model assumptions, not measured guarantees.

The following **new contracts are proposals for this iteration**, not endpoints
that already exist. Agree their exact JSON/type fixtures before parallel coding:

1. **Field manifest v1, Lane 1 producer.** A frozen receipt references
   `profile_id`, `calibration_id`, `camera_session_id`, disjoint training and
   validation recording IDs, `rig_check_id` when applicable, checks and warnings.
   Include `schema_version`, ID/hash and explicit provenance. Reuse existing
   immutable artifacts; exclude source-release truth, credentials, absolute local
   paths and raw camera images. Do not claim hardware is independently verified.
2. **Analysis bundle v1, Lane 3 producer / Lane 2 consumer.** Whitelisted snapshots
   of a comparison, numerical report, frozen plan, trial ledger, evaluation hash,
   profile/flow provenance and optional field-manifest reference. Include an
   explicit evaluation-truth section for trial source labels. Keep it out of
   source inference. Exclude arbitrary notes by default, phone identities, tokens,
   full SQLite dumps, raw images and unrelated cases. A content hash covers the
   canonical payload; detached timestamp metadata must not change that hash.
3. **Validation report v1, Lane 2 producer / Lane 3 consumer.** Include input hash,
   origin, protocol/split identity, denominators, missing/unresolved counts,
   per-layout/per-source predicted-versus-observed diagnostics, limitations and a
   recommendation with reason codes. No significance or calibrated-probability
   claim. Output must be finite and deterministic for the same input/config.

Commit small non-personal **synthetic contract fixtures** under
`tests/fixtures/team_handoff/`: Lane 1 owns `field_manifest_v1.json`; Lane 2 owns
`validation_report_v1.json`; Lane 3 owns `analysis_bundle_v1.json`. Each owner
provides a schema/type and a parser test. Never relabel a synthetic fixture as a
physical experiment. Keep public NOAA and existing demo fixtures unchanged.

## Copy/paste prompt 1 — Field evidence and commissioning

```text
You own Lane 1 of the next ReefTrace iteration. Start from the coordinator's green
main SHA after the prevention slice merges, on branch team/field-evidence. Read
README, architecture, verification, prevention workflow/physics and AGENTS first.
The current tracking, recording, drift fitting and source/prevention engines
already exist. Build the missing guided field workflow; do not rebuild them.

Goal: let an operator turn one measured tank setup into a reproducible, validated
profile and frozen field-session receipt without editing JSON by guesswork.

Exclusive write scope:
- New apps/api/reeftrace_api/schemas/field_sessions.py
- New apps/api/reeftrace_api/services/field_sessions.py
- New apps/api/reeftrace_api/api/v1/endpoints/field_sessions.py
- New dashboard/app/components/field-workflow.tsx and field-workflow.module.css
- New tests/integration/test_field_sessions.py, tests/unit/test_field_protocol.py
- New dashboard/app/components/field-workflow-state.ts
- New dashboard/tests/field-workflow-state.test.mjs
- tests/fixtures/team_handoff/field_manifest_v1.json
- docs/field-commissioning.md
- Existing apps/vision/reeftrace_vision/{calibration,capture,tracking}.py and their
  unit tests ONLY for an actual demonstrated bug; coordinate before a change.

Do not edit main.py, Runtime/Store, CaseInput, page.tsx, existing prevention
modules, sponsor adapters or CI. Lane 3 owns mounting your router/component.

Deliver one linear workflow: operator-selected camera session; four or more
mapping correspondences and at least three separate check points; approved
water-plane mapping; separate training/validation drift recordings; immutable
recorded-flow result; measured profile admission; first source observation.
Reuse the existing endpoints and gates. Do not manufacture drift, weaken a gate,
join tracks across gaps or substitute a fresh preview for fresh case evidence.
Provide measured-unit help, explicit missing-data states and a saved receipt of
which immutable objects passed. A draft is not an approved physical setup.

Propose the field-manifest v1 JSON/schema to Lanes 2/3 before coding integration.
Your new router can expose POST /field-sessions and GET /field-sessions/{id};
these are NEW endpoints, mounted only by Lane 3. The POST should validate existing
artifact references, persist an immutable receipt and require operator auth via
the shared dependency provided by Lane 3. Do not accept arbitrary caller claims
as evidence that existing numerical/calibration gates passed.

Physical action and power stay manual. Keep Photon false, no provider/account
changes, no private-key inspection or automatic camera opening. Tests use
explicit fake capture and synthetic image fixtures, labelled as such. Mock the
capture device, not the admission gates that the workflow is meant to prove. If actual
hardware is unavailable, produce an executable operator checklist and report
that gate blocked instead of marking physical commissioning complete.

Definition of done: wizard parses the actual API contracts, preserves draft on
recoverable failure, explains every blocked step, never promotes incomplete data
to measured validity, and returns a reproducible field-manifest ID/hash. Include
router mount instructions and component props for Lane 3; no shared-file edits.

Required E2E scenarios: missing camera; stale/restarted session; wrong units or
invalid mapping; overlap between train/validation recordings; unsupported flow;
successful explicit fake-capture protocol; rig disturbance; and a fresh case
after revalidation. Invalid paths create no false READY receipt. Run your scoped
Python/Node tests and Ruff; provide exact results and a PR with the starting SHA.
```

## Copy/paste prompt 2 — Prediction validation and next measurement

```text
You own Lane 2 of the next ReefTrace iteration, branch team/prediction-validation
from the coordinator's green main SHA. Existing compare_layouts, conservative
trial evaluation, frozen plans and the NOAA diagnostic already exist. Do not
rebuild them, fit a new detector for appearance, or change public-data results.

Goal: produce one offline, reproducible validation report from an exported
prevention analysis bundle, then recommend the most useful NEXT independent
measurement when an intervention decision is unresolved.

Exclusive write scope:
- New apps/estimation/reeftrace_estimation/prevention_validation.py
- New scripts/evaluate_prevention_validation.py
- New tests/unit/test_prevention_validation.py
- New tests/fixtures/team_handoff/validation_report_v1.json and owned small
  validation fixtures under tests/fixtures/prevention_validation/
- New docs/prevention-validation-protocol.md
- Existing apps/estimation/reeftrace_estimation/prevention.py and
  tests/unit/test_prevention.py ONLY for a demonstrated numerical defect;
  preserve the frozen comparison contract and coordinate any output change.

Do not edit API/runtime/store, trial schemas, dashboard, Chalk, CI or Lane 1's
field-manifest implementation. Lane 3 provides a whitelisted analysis_bundle_v1
export. Agree that schema and your validation_report_v1 fixture with Lane 3 first.

Implement a bounded CLI accepting a local bundle path, explicit development/test
protocol identifiers and an output path. Verify hashes/IDs, finite values, origin
labels and denominator accounting. Refuse changed frozen plans, incompatible
profiles, mixed synthetic/physical pooling and overlap between development and
validation trial/recording IDs. Keep source-release labels in evaluation only.
Do not call providers, download models/data, inspect .env, open cameras or alter
SQLite. No training on held-out outcomes or relabelling development data as test.

Compare per-source/per-layout simulated first-entry fractions/bounds against the
recorded outcome bounds with their actual denominators. Report missing planned
slots, unresolved observations and whether the suggested layout remained useful
on new trials. Keep source identification accuracy and intervention performance
separate. Fractions from particles are model-conditional, not proven calibrated
probabilities. Overlapping trials/sessions and small pilot samples do not justify
significance, ocean accuracy, coral survival or CO2 claims.

Implement a transparent NEXT-MEASUREMENT heuristic, not an untested optimal
active-learning claim: first request independent drift in unsupported regions;
otherwise identify a declared source/scenario whose uncertainty changes the
layout decision and recommend another independent paired trial. If the saved
report cannot identify a useful region, say so. Watching another image of an
already retained endpoint does not recover missing history; cropping an already
recorded full-frame image is not a new sensor observation. Never move a collector
without requiring fresh layout-specific drift validation.

Definition of done: identical input/config produces identical finite report/hash;
invalid inputs fail clearly; the report exposes both predicted and observed
quantities and cannot claim physical results from the synthetic demo. Supply a
small pure-function interface and example report for Lane 3 to render/explain.

Required tests: known synthetic first-entry/capture ordering; all-unresolved and
incomplete/unbalanced plans; a model prediction contradicted by reported trials;
mixed origins; duplicate recording/trial identities; stale/tampered hashes; train/
test leakage; and a held-out result that does not favor the proposed model.
Run scoped tests and Ruff, then provide a PR with commands/results and limitations.
```

## Copy/paste prompt 3 — Product, evidence export, Chalk and integration

```text
You own Lane 3, branch team/product-integration from the coordinator's green main
SHA after the current prevention slice lands. Your job is to integrate Lanes 1/2
and prove the complete story; the current source/prevention application exists.

Exclusive write scope:
- apps/api/reeftrace_api/main.py and services/runtime.py: minimal shared wiring
- services/store.py: only necessary reviewed transaction/integrity helpers
- New apps/api/reeftrace_api/schemas/evidence_export.py
- New apps/api/reeftrace_api/services/evidence_export.py
- New apps/api/reeftrace_api/api/v1/endpoints/evidence_export.py
- Existing prevention service/investigation wiring and adapters/chalk/**
- dashboard/app/page.tsx and existing prevention workspace/state components
- New dashboard/app/components/validation-report.tsx, validation-report.module.css
  and validation-report-state.ts
- New dashboard/tests/validation-report-state.test.mjs
- scripts/e2e_demo.py, scripts/e2e_prevention.py
- New tests/integration/test_evidence_export.py and test_team_workflow.py
- .github/workflows/**, docs/verification.md, docs/integrations.md, README.md
- tests/fixtures/team_handoff/analysis_bundle_v1.json

Do not edit Lane 1's field-session/vision files or Lane 2's validation/numerical
files. Integrate their small reviewed APIs; request changes rather than copying
their algorithms into your UI or backend. Freeze shared contracts with both
owners before wiring. Do not rewrite working components or replace the stack.

Implement a deliberate evidence-export action for one selected comparison. A new
GET /prevention/comparisons/{id}/export can return analysis_bundle_v1 with canonical
hash, exact immutable comparison/plan/trials/evaluation and required profile/flow
provenance. Validate identity and exclude credentials, phone handles, absolute
paths, arbitrary notes, raw camera data and unrelated cases. Keep source-release
truth in a marked evaluation section; never send it to source inference tools.
Archive exports remain readable and labelled; stale plans cannot accept writes.

Mount Lane 1's router with existing operator authentication and component with
the existing request/token state. Surface Lane 2's report and deterministic next-
measurement reasons. Prefer a small report view over another dashboard system.
Add an explicit import/validate action if a local CLI report must return to UI;
verify input comparison/evaluation hashes before accepting it. Do not accept an
arbitrary file as the current authoritative numerical result.

Extend the read-only Chalk evidence backend only when the new report contract is
frozen. Return aggregate reports/IDs/digests, not full trajectories or raw notes.
Preserve all strict JSON/tool/citation rules, Unknown/Invalid status and existing
request/whole-turn limits. An unavailable provider must leave the deterministic
report usable. A changed case or trial/evaluation digest must reject a stale model
answer atomically; do not overwrite a prior manual outcome. Numerical tables are
rendered from frozen backend reports, never from generated prose.

Keep PHOTON_ENABLED=false and xAI voice disabled. Do not send messages, enable
background replies, alter account/billing/model configuration, request private
keys or add an actuator. All automated integration uses fake provider transport
with explicit mock labels. Do not run a metered live model audit without separate
human coordination; the existing HTTP scripts can call configured Chalk.

Definition of done: the operator can complete a guided setup rehearsal, open a
frozen comparison, log/recover one exact trial submission, export the evidence,
validate it offline and view a matching report/Chalk explanation. Preserve
refresh/reload recovery, accessibility, responsive layout, source lineage and
archival states. No optimistic success or silent retry of writes/model calls.

Required E2E scenarios: missing operator token; new field receipt and comparison;
export roundtrip/hash tampering; duplicate/pending trial recovery after network
failure; physical-vs-synthetic separation; incomplete and contradictory outcomes;
STOP/recompute during async work; trial change during Chalk review; stale imported
validation; offline provider fallback; and mobile keyboard/error states.

Run the full offline Python/Ruff/dependency checks, dashboard Node tests/lint/types/
production build, and the scientific fixture-diff check. Use explicit fake capture
and fake providers, never physical claims. Add meaningful new checks to CI with
read-only permissions and no secrets. Open a focused PR; after Lane 1/2 merges,
update from main and repeat only checks affected by integration changes.
```

## Handoffs and definition of a finished iteration

1. **Contract checkpoint:** all three agree the three versioned fixtures and
   ownership boundaries. Record decisions in PR descriptions. No mid-build JSON
   renames or hidden new required fields.
2. **Lane 1 → Lane 3:** router factory/mount instruction, component props, fixture,
   commissioning checklist and scoped test evidence. A blocked physical gate is
   an explicit state, not a reason to fabricate a passing receipt.
3. **Lane 3 → Lane 2:** a scrubbed synthetic export and parser contract first;
   actual operator-reported data can follow privately. No unreviewed database dump.
4. **Lane 2 → Lane 3:** deterministic function/CLI, report fixture, reason codes,
   limitations and evidence that contradictory outcomes stay visible.
5. **Final integration:** one demonstrable path, one adversarial path and one
   unavailable-provider path. The coordinator reviews/merges green PRs and records
   the final SHA and actual checks; no one claims another person's unfinished work.

From the repository root, the shared offline baseline is:

```sh
CHALK_ENABLED=false PHOTON_ENABLED=false GROK_VOICE_ENABLED=false \
  .venv/bin/python -m pytest -q --strict-config --strict-markers -ra
.venv/bin/python -m ruff check apps adapters scripts tests
.venv/bin/python -m pip check
git diff --exit-code -- data/public data/sample_runs
cd dashboard
node --test tests/*.test.mjs
npm run lint
npx next typegen
npx tsc --noEmit
npm run build
```

Use isolated test data and explicit fake transports. Run `scripts/dev.py --check`
for a read-only launch preflight. The existing HTTP demo scripts may make a real
metered Chalk turn when credentials are configured; they are **not** the default
offline smoke checks. A human must coordinate any such run, while Photon stays off.

The final demo should say: **we preserved uncertain source identity, compared a
declared interception choice, and made the measured evidence and its limitations
inspectable.** If hardware trials have not happened, show the synthetic rehearsal
and the executable field protocol, and name physical validation as unfinished.
