# P2 experiment protocol and evaluator checklist

Owner: Aarush Mane (`@aarushmane`). Coordination: [issue #4](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/issues/4),
with Jose and `megana111`. Branch: `team/experiment-validation-v2`.
Starting checkpoint: `521d8f95281b4f78dc4a809a8882113bcfa98bb0`, published in
[Nemo's master prompt](https://trov.dev/nemo/#prompts/tideward-four-person-build-master-plan).
The requested historical handoff was read at `4ef5b50cef86da3df697b25229193a3214cff24e`.
The published ReefTrace 2 v3 assigns this follow-up; the earlier validator is merged.

**Physical execution: BLOCKED.** No measured profiles, rig receipts or releases
have been supplied to this session. This is a protocol draft and synthetic
software rehearsal, not a frozen physical experiment or physical result.
Coordination was requested; teammate acknowledgment is pending. No API, numerical
comparison, exporter, inference schema or provider configuration is changed.
Photon replies and xAI voice stay off for this task. All wet actions are manual.

## Question and protocol freeze

Does an upstream mesh reduce first entry into the **same** protected polygon,
for each declared A/B/C source, under matched token, waterline and horizon?
Compare first-entry counts/bounds; do not weight outcomes by source support.

Before a real release, save a private, dated protocol receipt containing:

- Unique protocol ID and role: `development-pilot` or `confirmation`. The pilot
  is development. A subsequent confirmation is a new experiment with new IDs.
- Coordinator-approved code SHA; comparison ID, plan ID/hash, exact ordered
  sequence, horizon, protected polygon and unchanged baseline/intervention
  profile and flow IDs/hashes. Twenty seconds is the target; a shorter supported
  horizon must be frozen before the plan, never after an outcome.
- Measured token class, source polygons, bounds, waterline, pump/outlet/camera/
  collector marks, calibration and field-receipt references. Megana supplies two
  admitted layout-specific fields with disjoint training and validation drift.
- Whole run, recording and session inventories for development (including drift
  fitting, gate validation, pilot and any parameter selection) and confirmation.
  Reserve confirmation session IDs before collection; append recording/trial IDs
  as acquired, without changing group membership. New recordings begin after
  comparison freeze. IDs alone do not prove independence or unseen outcomes.
- Selected layout, selection basis, model/scenario settings and stopping rules,
  frozen before inspecting confirmation outcomes. Stop for rig disturbance,
  failed drift support, token loss, missing provenance or insufficient time.
  Record failures; no outcome-driven early success or replacement of bad runs.
- Jose/Megana/Aarush acknowledgment and freeze time, preceding recordings and
  releases. Until completed, label the document DRAFT/BLOCKED, never READY.

Do not tune on confirmation outcomes. If settings/layouts change, close that plan
as incomplete, preserve its missing/unresolved slots, and freeze a new development
protocol followed by untouched confirmation sessions. Pilot releases cannot be
relabelled as confirmation. Physical calibration and flow-validation recordings
are development inputs, not held-out intervention releases.

## Pilot and separate confirmation

Ask Jose to freeze `trials_per_source=1` for three sources and two layouts:
**six planned releases**. Read `comparison.plan.sequence`; do not generate a
replacement order. For A/B/C the current counterbalanced sequence is A baseline,
A intervention, B intervention, B baseline, C baseline, C intervention.

A later `trials_per_source=5` comparison has **30 new planned releases**, with a
new protocol, comparison and recordings; six pilot releases do not count toward
it. Thirty releases are not thirty independent tank setups. Report session reuse.
Restoring a collector to its marks still requires the existing disturbance and
fresh layout-specific drift revalidation. Do not recompute source evidence after
freezing a comparison; that archives it. If a new case is necessary, ask Jose for
an explicitly new comparison rather than writing into the archived one.

Megana maintains the marked configuration; Aarush releases/retrieves one token
and holds source truth; Jose records the first event and checks footage/timing/
accounting. For blinded source checks, save the estimator's complete source report
ID/status/ranking **before revealing the release label**. Record ranked-correct,
ranked-wrong, Unknown and Invalid separately, including all attempted runs. An
always-Unknown estimator has not demonstrated source accuracy. Prevention results
remain separate from this source-identification assessment.

## Per-release checklist and recovery

1. Confirm the saved next slot, stable waterline/configuration, current measured
   profile and revalidation receipt. Have exactly one recovered token available.
2. Begin one fresh layout-linked recording after plan freeze; save its session
   and recording IDs. Keep the known release source in the evaluator log only.
3. Before submission, save the exact `TrialInput` key/body privately. Use a key
   unique to this comparison/run. Observe through the fixed horizon; save first
   entry and later collection separately. Do not infer history from an endpoint.
4. Choose the existing outcome fields without changing their meaning:

   | Observation | Ledger outcome |
   | --- | --- |
   | Zone entry, even if collected later | `zone_entry`, observed entry time and optional later interception time; accounted token |
   | Lasting capture before entry, observed throughout horizon | `intercepted_before_entry`, capture time, no entry time, accounted token, completed horizon |
   | No entry during complete observed horizon | `no_entry`, no event times, accounted token, completed horizon |
   | Lost tracking, ambiguous order, incomplete non-entry observation or unaccounted token | `unresolved`, no claimed event times; retain actual accounting/horizon flags |

5. Reconcile the server's returned trial ID, ordinal and exact body with the log.
   After a timeout, recover/retry **the same key/body** and read the ledger. Never
   release another token because acknowledgment was lost. A changed body with
   the same key is a conflict requiring investigation, not a new physical run.
6. Recover/account for the token before the next slot. If a release occurred but
   its outcome is unknown, log unresolved; if no release occurred, leave a missing
   planned slot. Do not erase an unfavorable run or fill it using another image.

`TrialInput` also requires physical origin/confirmation for real trials and a
recording linked to the admitted layout. These attestations are operator reports,
not independent physical verification. The server's gates remain authoritative.

## Private run log

Copy [the blank header](templates/experiment-run-log-v2.csv) to an explicitly
private local directory such as ignored `data/local/experiment-validation/`.
Never commit real source answers, raw camera images, keys, phone handles or paths.
The CSV is a human worksheet, **not** a new import/API schema or source-inference
input. Store exact retry bodies beside it privately; never reconstruct a changed
retry from shorthand columns. Keep failed/missing runs in the worksheet.

Use one row per reserved slot; keep physical observation fields blank until
observed. `split` is declared before collection; `release_occurred` distinguishes
missing from unresolved. `source_report_id` and `source_status` precede unblinding.
Track drift revalidation in `rig_check_id`; a blank required reference blocks
release. Export only deliberate scrubbed aggregates through the existing exporter.

## Rehearsal, export and reporting boundaries

Run the pinned offline method on its **synthetic** fixtures:

```sh
.venv/bin/python -m scripts.evaluate_prevention_validation \
  tests/fixtures/prevention_validation/unresolved_analysis_bundle_v1.json \
  --development-protocol development-prevention-v1 \
  --validation-protocol heldout-prevention-v1 \
  --output /tmp/reeftrace-p2-synthetic-validation.json
```

This is the Lane 2 method format and is not the product export wire format.
The product `analysis_bundle_v1` uses `payload_sha256` / `payload_canonical_json`;
its validation import checks identity/accounting and explicitly says
`IDENTITY_AND_ACCOUNTING_CHECKED_METHOD_NOT_RERUN`. The method CLI consumes the
separate `content_hash` envelope documented in prevention-validation-protocol.md.
Do not rename fields or feed one format to the other, or present a saved synthetic
method replay as validation of a current physical comparison. Jose owns any
reviewed bridge/export integration; this protocol proposes no schema change.

For actual data, request Jose's matching reviewed export/method input, protocol
receipts and immutable flow/profile references. Verify exact comparison, plan,
input/export/evaluation and resulting report IDs/hashes. If no compatible method
bundle exists, report method validation BLOCKED while retaining the checked
accounting receipt. Do not fabricate missing provenance to make the CLI accept it.

Report separately per origin, source and layout: planned, actual releases,
missing, unresolved, unaccounted tokens, entry/capture counts and both planned/
released bounds. Report the model's particle denominator/fraction/bounds separately.
Preserve contradictory held-out results and losses. Never pool synthetic and
physical cohorts, or multiply releases by the number of simulation scenarios.
Particle fractions are model-conditional, not calibrated probabilities.

Use the existing next-measurement rule: unsupported flow first needs independent
layout-specific drift. Otherwise retain the reported decision-changing source/
scenario and request an independent paired trial under a **new frozen plan** when
quota is complete. If no region is identified, say so. More images of an already
retained endpoint or crops of an existing frame are not independent measurements.
A small, counterbalanced pilot supports no significance, causal reef benefit,
polluter identity, ocean accuracy, coral-survival or CO2 claim.

Current physical counts: **0 completed; 0 unresolved observed; six pilot slots
proposed, not yet frozen**. Thirty confirmation slots are a subsequent proposal.
Next prerequisite: Megana's independent, admitted layout drift/profile evidence
and Jose's exact frozen pilot/export contract, not another model or synthetic run.

## Software verification

```sh
.venv/bin/python -m pytest -q tests/integration/test_experiment_protocol.py \
  tests/unit/test_prevention_validation.py tests/unit/test_method_validation.py
.venv/bin/python -m ruff check apps adapters scripts tests
.venv/bin/python -m pip check
.venv/bin/python scripts/e2e_offline.py
git diff --exit-code -- data/public data/sample_runs
```

The rehearsal uses disposable stores and synthetic profiles; no physical gate is
mocked into success. Run full Python/dashboard checks before the PR. Run tests
from a temporary working directory with the repository on `PYTHONPATH` to avoid
loading a private repository `.env`. The standard `dev.py --check` reads local
configuration; it is excluded from this no-private-key-inspection assignment.

For the full suite, existing tests need the relative `tests/` and public/sample
fixture paths. This temporary-directory recipe preserves those paths without a
private `.env` or a live local store:

```sh
.venv/bin/python - <<'PY'
import os
import subprocess
import tempfile
from pathlib import Path

root = Path.cwd()
with tempfile.TemporaryDirectory(prefix="reeftrace-p2-full-") as scratch:
    work = Path(scratch)
    (work / "tests").symlink_to(root / "tests", target_is_directory=True)
    (work / "data").mkdir()
    for name in ("sample_runs", "public"):
        (work / "data" / name).symlink_to(root / "data" / name, target_is_directory=True)
    env = os.environ.copy()
    env.update(PYTHONPATH=str(root), CHALK_ENABLED="false",
               PHOTON_ENABLED="false", GROK_VOICE_ENABLED="false")
    result = subprocess.run(
        [str(root / ".venv/bin/python"), "-m", "pytest", str(root / "tests"),
         "-q", "--strict-config", "--strict-markers", "-ra"], cwd=work, env=env)
    raise SystemExit(result.returncode)
PY
```

Only synthetic test data are written to temporary stores. The existing isolated
HTTP runner independently guards provider HTTP, camera open and Photon send/poll.
Real data and local application configuration are not inputs to this rehearsal.

### Rehearsal receipt — 17 October 2026

- Four new P2 integration scenarios pass. Scoped integration/method/validation
  suite: **60 passed**. Full isolated Python suite: **955 passed, 1 skipped** in
  166.34 s. The skip is the optional `chalkcompute` SDK import; no live Chalk
  readiness is claimed. One existing Starlette/httpx deprecation warning remains.
- Repository Ruff and dependency check pass; public/sample fixture diff is empty.
- Isolated HTTP audit: **116 PASS, 0 FAIL, 6 BLOCKED**; camera-open, provider-HTTP,
  Photon-send and Photon-poll attempt counters all zero. Live/physical verification
  remains false.
- Dashboard: **97 Node tests pass**; lint, Next route generation, TypeScript and
  production build pass. Existing module-type and outer-lockfile warnings remain.
- Synthetic method CLI output exactly matches the shared fixture, report
  `prevention-validation-bd92669f971508341fc5`, hash
  `bd92669f971508341fc5744991f3ebb825dcaa36310d088d96174b7f4a650430`.
  Its source-B independent-pair recommendation concerns that synthetic example,
  not an unperformed physical pilot.

The first broad run omitted relative fixture paths in the temporary directory;
those path failures were corrected in the harness, with no product/test-source
change. The complete rerun above passed. No private configuration was read by the
harness. Teammate acknowledgment and actual measured artifacts remain outstanding.
