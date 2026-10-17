# Two software-only handoffs

These are the current assignments for **Megana** and **Aarush**. They supersede the hardware/field portions of older Trace 1/Trace 2 prompts for this iteration. Both can start from the current repository without a tank, camera, pump, electronics, new model or new dataset.

Repository: [Jose-Gael-Cruz-Lopez/reeftrace](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace). Product: Tideward; existing ReefTrace package/API names remain unchanged. Jose owns final integration, shared workspace state, scientific interfaces and live provider configuration. These prompts are repository deliverables; they do not claim a Trove post or teammate acknowledgment has occurred.

## Shared start and merge rules

1. Read [README](../README.md), [the algorithm/contract audit](algorithm-contract-audit.md), [the integrated demo](integrated-team-demo.txt), and the task-specific documents below. Inspect current code before relying on a historical prompt.
2. Use a clean checkout of the latest `origin/main`, record its exact SHA, and create the task branch below. Preserve existing local work; do not reset or discard it. If another teammate has already changed an owned file, coordinate the overlap before editing it.
3. Work only in the assigned files. Do not push directly to `main`; open a PR with the actual behavior, evidence and remaining blockers. Jose merges after checks and review.
4. Automated tests use temporary stores, synthetic inputs and mocked providers. The guarded `scripts/e2e_offline.py` creates its own loopback API, turns providers off in that child process, and records attempted side effects. It does not point at or reconfigure the running application.
5. Preserve every declared missing/failed/unresolved outcome. A contract test is software evidence, not a new NOAA score, real physical release or live provider evaluation.

**Out of scope for both tasks:** physical capture, camera selection/calibration, electronics/tubing/pump work, field admission or flow thresholds, scientific estimator/simulator changes, frozen NOAA protocols/data/reports/model files, provider keys/billing/routes/enable flags, Photon messages or automatic-reply changes, and shared `main.py`/Runtime/Store/workspace orchestration changes. Identify a required shared-contract fix with a reproducible test and a proposed minimal patch for Jose; do not silently redefine it in your lane.

## Megana — demo acceptance, accessibility and browser E2E

Branch: `team/software-demo-acceptance`.

**Outcome:** a new teammate can understand and complete the existing software demo, including its honest failure states, with mouse or keyboard. This lane validates and improves presentation of current behavior; it does not add scientific capability or physical setup.

Allowed scope:

- New `docs/software-demo-acceptance.md` with the exact tested checkpoint, browser/version, click sequence, expected/actual results and sanitized evidence references.
- Focused new acceptance tests under `dashboard/tests/` using the existing test stack. Browser automation may exercise the existing app; clearly separate actual browser tests from Node-only parser tests.
- Small accessibility fixes inside the existing leaf demo component and its CSS module, after confirming its current path with Jose. Keep component names/navigation/contracts stable. Shared workspace state, root routing and backend integration remain Jose's scope.
- No new dependency, account, cloud deployment or test framework is required. If a real gap needs one, document the gap before proposing it.

### Copyable prompt for Megana

> Work on Tideward/ReefTrace's existing software demo from the latest green main. Record the starting SHA and use branch `team/software-demo-acceptance`. Read README, docs/algorithm-contract-audit.md and docs/integrated-team-demo.txt, then inspect the actual Overview demo component, operator provider, evidence-freshness helpers and relevant dashboard tests. Do not implement an older physical Trace 1 prompt.
>
> Your task is demo acceptance, accessibility and browser end-to-end verification. First produce an acceptance matrix for Overview’s “Follow the evidence”: “Trace a source” / “Open source trace”, “Compare two layouts” / “Compare layouts”, and “Explain the evidence” / “Ask Chalk”. Also verify the separate existing fresh NOAA Data Lab study and its research discussion. Use the current UI's labels rather than inventing a new navigation structure. The stock prevention demo has its own source case; do not claim it inherited a different selected case ID.
>
> Exercise the source demo: load/reuse the synthetic cases; inspect candidate C on the observed-trajectory example and its saved report; deliberately use “Recompute source support” to test evidence-revision behavior; inspect sensitivity; confirm retained endpoint stays Unknown and invalid calibration stays Invalid. Source bars are conditional support, not calibrated probabilities. Loading a demo can already prepare evidence. Recomputing changes its revision/evidence identity, so previous answers must not be presented as current.
>
> Exercise Prevention: load the existing synthetic comparison, inspect the protected polygon and both layouts, then compare simulated entry bounds with separately labelled recorded synthetic outcomes. Confirm that the real physical count remains zero. Inspect missing/unresolved counts, planned versus released denominators, and archival behavior after the anchored source case changes. Do not edit a scientific profile to make an intervention appear better. When testing trial entry, create an explicitly synthetic disposable comparison rather than changing an immutable completed example or claiming a physical release.
>
> Exercise Data Lab’s “Load buoy comparison” action and “Explain this result” discussion: all six target groups, five models, 180 scores and 36 unique observed intervals must remain distinguishable. Verify local metre paths, m/s errors, raw versus filtered model starts, provenance, amendment history and unresolved-alias limitations. Last drift currently has the lowest aggregate error; no model is automatically promoted and the data do not establish plastic sources or reef benefit.
>
> Check the research discussion with the existing mocked/offline provider seams: exact study/protocol citations, unrelated/stale response rejection, configured-but-failed gateway, timeout, unconfigured STOP and an answer whose tool evidence was altered. The deterministic report must remain visible on failure. An earlier independently verified live Chalk REPORT is recorded evidence, not a reason to fabricate a new live success. No live provider call, key inspection or Photon message is needed for this assignment.
>
> Test keyboard navigation, visible focus, accessible names, form labels, error/status announcements, disabled/loading controls, and cancellation when navigating away or changing the loaded report. Verify useful layout at approximately 390 px and desktop widths; no invisible or off-screen primary action. Preserve reduced-motion preferences where animations exist. Fix only small leaf-component accessibility/presentation defects within your scope. Do not redesign the site or change shared state/routing to make the checklist pass.
>
> Use the existing team's local operator session privately for authorized app clicks; never put its token in screenshots, URLs, logs, fixtures or a PR. Do not change a running service's configuration. For automated mutation tests use public test-only credentials and disposable stores following existing fixtures. Keep the camera off and do not send messages. If a browser check cannot be executed in your environment, mark it BLOCKED with the exact reason instead of reporting a Node test as a browser pass.
>
> Add meaningful regressions for defects you actually find. Produce docs/software-demo-acceptance.md with the acceptance matrix, reproduction steps, exact commands/results and remaining limitations. Run the relevant Node tests, lint and TypeScript checks; run the guarded offline HTTP workflow when checking the full story. Open a PR rather than pushing directly to main. State any proposed shared-contract fix separately for Jose. Do not alter frozen scientific artifacts, hardware paths, provider settings or another teammate's files.

Acceptance before PR:

- The same synthetic observation/case and its report identity are shown together; loading/recomputing/stopping cannot retain a stale answer as current.
- Unknown, Invalid, no physical outcomes, unavailable acquisition and provider failure remain understandable successful handling of limitations.
- The demo works with keyboard and small-screen layout; evidence includes real browser execution where available.
- Node-only checks, actual browser checks and unavailable live/physical scopes are labelled separately.
- No secret, contact, physical recording or false live/provider/physical result enters the PR.

Suggested checks, using the already installed dashboard dependencies:

```sh
cd dashboard
node --test tests/*.test.mjs
npm run lint
npx next typegen
npx tsc --noEmit
npm run build
cd ..
.venv/bin/python scripts/e2e_offline.py --output work/megana-software-http.json
```

Do not run a production build into a development server's active `.next` directory while teammates use it; use the project's existing isolated verification approach or coordinate the build window.

## Aarush — export/validator contract and unresolved edge cases

Branch: `team/software-export-validation`.

**Outcome:** software consumers can tell exactly which export they have, which checks ran, and why incomplete or contradictory outcomes remain uncertain. The earlier merged P2 protocol is useful context; this assignment does not conduct its proposed physical pilot.

Allowed scope:

- New `docs/software-export-contract.md` describing the two existing wire formats and a reproducible synthetic export/import rehearsal.
- New `tests/integration/test_software_export_edges.py` and focused new unit tests where they exercise an existing public function.
- An optional, separate `tests/unit/test_prevention_bookkeeping_audit.py` after the primary contract work, limited to the existing synthetic algorithm invariants described below.
- Small, explicitly synthetic new fixtures under `tests/fixtures/software_export_edges/`, if an inline disposable-store fixture is insufficient. Do not rewrite an existing fixture, public NOAA file, schema or reference report.
- Clarifications to your own new documentation/tests only. Existing production exporters/validators and shared schemas remain unchanged unless Jose separately assigns a reviewed fix.

### Copyable prompt for Aarush

> Work from the latest green ReefTrace main, record its SHA, and use branch `team/software-export-validation`. Read README, docs/algorithm-contract-audit.md, docs/trace3-research-and-contract.md, docs/prevention-validation-protocol.md and your merged docs/experiment-validation-v2.md. Inspect the actual ComparisonInput/TrialInput, evidence-export schemas/service, validation-report schemas/service, offline Trace 2 validator, and existing integration tests. Do not rerun or rebuild the old physical P2 assignment.
>
> Own the software contract audit and new edge-case regressions. Create docs/software-export-contract.md explaining that the product analysis_bundle_v1 uses payload_sha256/payload_canonical_json, while the distinct offline method envelope uses content_hash and full immutable replay inputs. An accepted current-case manifest proves identity, declared partition and recomputed accounting only: IDENTITY_AND_ACCOUNTING_CHECKED_METHOD_NOT_RERUN. It does not rerun a numerical method or establish an independent experiment. Do not invent a bridge by renaming hash fields or treating a redacted export as full method input.
>
> Build disposable synthetic comparisons through existing services/schemas. Add targeted tests for zero recorded releases, missing planned slots, unresolved/lost-token outcomes, an observed zone entry followed by later collection, and no-entry/interception requiring the complete frozen horizon. Show exact planned and released denominators; missing/unresolved states must not become successes or zero error. Preserve an outcome that contradicts the simulated recommendation.
>
> Test exact trial-key/body retries and changed-body conflicts, per-source/layout quota, duplicate record/identity handling, and source-case revision/STOP archival. The current API can record an out-of-plan order and marks order_followed=false; test that behavior rather than silently changing it to rejection. Synthetic and operator-reported physical origins stay separate, and a synthetic profile must reject a physical-outcome claim. No physical recording or measured profile is needed for those negative tests.
>
> Audit export whitelist/canonical hashing and immutable comparison/profile/evaluation binding. Test that altered identities, changed payloads, incompatible envelope fields, overlapping or incomplete development/validation partitions, and a stale evaluation cannot produce a current accepted receipt. Recomputing a JSON hash alone must not turn changed scientific inputs into a trusted method replay. If a protection belongs to a different existing layer, name and test that layer rather than duplicating its implementation.
>
> Verify that trial release labels remain evaluator truth and never enter source-estimator observations or Chalk's source evidence as new identifying data. Read-only prevention Chalk reviews may inspect deterministic aggregate counts and an exact current validation receipt; they cannot change the ledger or promote a rehearsal to physical validation. Tests use mocked provider transports only. Do not inspect or change keys, messages, enable flags, hardware settings, camera calibration, field thresholds, frozen models or the scientific engine.
>
> Only after the primary export/ledger cases are covered, optionally propose a bounded synthetic bookkeeping audit from docs/algorithm-contract-audit.md section 11. For the existing competing ensemble, Z (zone first), T (other trap first) and F (no event by horizon) are disjoint and sum exactly to N. Support S is orthogonal, so the six cells Z&S, Z&~S, T&S, T&~S, F&S and F&~S also sum exactly to N. Unsupported particles are not a fourth destination. Use equal 1/N weights, retain admitted initially unsupported particles, and distinguish a rejected invalid configuration from an admitted ensemble. Check persistent absorption, node-time event bounds and support only through the first event/horizon against independently derived synthetic expectations. Use exact integer conservation, not an arbitrary 1e-12 mass-leak or physical-success tolerance. Do not confuse the model's F/unresolved_count with an unresolved operator trial. This is an optional new test/proposal, not permission to change frozen source/prevention code, physics, thresholds or empirical claims.
>
> Put new regressions in tests/integration/test_software_export_edges.py and any narrowly justified new unit/fixture files. Use temporary stores and explicitly synthetic inputs; never call the running user's API/store. Keep full raw/expected result comparisons meaningful, including discrete IDs, status, origin and denominators, rather than asserting only that a request returned success. Use narrow floating tolerance only where the actual calculation requires it; never apply it to hashes, IDs or counts.
>
> Write the exact accepted/refused input example, authoritative output fields, method-not-rerun boundary and remaining unimplemented bridge in docs/software-export-contract.md. Run focused tests, Ruff and the guarded offline HTTP runner. If you find a production defect, provide its failing regression and a minimal proposed patch for Jose instead of changing shared APIs, Runtime/Store, main.py, export schemas or frozen scientific code yourself. Open a PR with exact evidence and remaining blockers; do not push directly to main or claim a physical trial occurred.

The optional follow-up is specified in [section 11 of the mathematical audit](algorithm-contract-audit.md#11-next-synthetic-audit-first-passage-bookkeeping). It must remain a separate synthetic test design and can be omitted from the first PR; it does not block delivery of the primary export/validator work.

Acceptance before PR:

- Both export formats and their verification scope are clear, with no invented adapter or independent-validation claim.
- Missing/unresolved/contradictory outcomes preserve exact identities and denominators across ledger → evaluation → export → receipt.
- Exact retries are idempotent; changed data, stale contexts and invalid partitions fail at the intended existing boundary.
- Test data are synthetic and disposable; existing public/frozen scientific bytes and shared production contracts are unchanged.

Suggested focused checks:

```sh
.venv/bin/python -m pytest -q tests/integration/test_software_export_edges.py \
  tests/integration/test_experiment_protocol.py \
  tests/unit/test_prevention_validation.py tests/unit/test_method_validation.py
.venv/bin/python -m ruff check tests/integration/test_software_export_edges.py
.venv/bin/python scripts/e2e_offline.py --output work/aarush-software-http.json
git diff --check
git diff --exit-code -- data/public data/sample_runs
```

Use the temporary-working-directory full-suite recipe in the **Software verification** section of [the merged P2 protocol](experiment-validation-v2.md) when broad checks are needed; that recipe, not its physical experiment, is relevant here. A focused passing test does not replace CI on the eventual PR commit.

## Return contract for both teammates

Each PR should state: starting SHA and branch; owned files; concrete before/after behavior or discovered defect; exact commands and results; actual browser evidence versus mocked tests; and unresolved blockers. Link the original task and avoid posting credentials or private local artifacts. Jose reviews shared boundaries, integrates accepted changes and updates the final main-checkpoint receipt.
