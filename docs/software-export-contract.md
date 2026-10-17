# Software export and validation contract audit

Owner: Aarush Mane (`aarushmane`, Nemo). Branch: `team/software-export-validation`.
Starting main SHA: **7448d1fe3aca230acd4cb7001b0c0b2380fe1d67**.
Starting CI: [green run 39046621295](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/actions/runs/39046621295).
Task: [Trov handoff #11](https://trov.dev/nemo/#handoffs/11) and the Aarush prompt in
[software-handoffs.md](software-handoffs.md). This is the software-only follow-up,
not execution of the earlier physical P2 assignment.

## Two formats, two verification scopes

Both historical formats use the string `analysis_bundle_v1`, but their complete
schemas and meanings differ. The schema-version string alone cannot select a parser.

| Boundary | Product export | Separate offline Trace 2 method input |
| --- | --- | --- |
| Producer/consumer | `export_comparison` → `AnalysisBundle` → current-case split manifest | Full frozen method fixture → `validate_bundle` / local CLI |
| Outer fields | `schema_version`, `payload`, `payload_canonical_json`, `payload_sha256`, `metadata` | `schema_version`, `id`, `payload`, `content_hash`, optional detached metadata as defined by its validator |
| Digest | SHA-256 of exact canonical payload string; parsed payload must agree | SHA-256 of canonical full method payload; ID prefix binds digest |
| Numerical inputs | Whitelisted comparison, numerical aggregates, plan, compact profile/flow provenance | Full immutable numerical profiles/flow nodes plus comparison/report and protocol inventories |
| Trial truth | Marked `evaluation_truth.trials`; notes, trial keys and private request hashes removed | Evaluation-only source-label join, scrubbed trials and session/split inventories |
| Verification | Identity, declared partition and recomputed release accounting | Full engine replay plus identity/hash/split/accounting checks |
| Independence | Not proved by declarations/IDs | Not proved by IDs or exporter session receipts either |
| Physical result | Never automatically verified | `physical_validation=false`; synthetic input is not physical evidence |

Product canonical JSON uses sorted keys, compact separators, ASCII escaping and
finite numbers. The protected string preserves distinctions such as `1.0` versus
`1` across browser JSON serialization. `AnalysisBundle` checks canonical bytes,
parsed payload agreement and digest; it is not a signature, a store lookup or a
numerical replay. Detached export time does not change the payload digest.

Adding `content_hash` to a product bundle is an extra-field error. Renaming
`payload_sha256` to `content_hash` does not produce full method inputs; the method
validator refuses it. Removing redacted fields cannot be reversed by renaming a
hash. No bridge is implemented or proposed by this PR.

## Authoritative product flow

1. `ComparisonInput` binds a current noninvalid source report, case revision,
   registered compatible profiles, protected polygon, horizon and frozen plan.
2. `TrialInput` validates event/accounting/full-horizon claims. `add_trial` checks
   the comparison's current case, source/layout quota, event horizon, origin and
   recording references, then transactionally saves one immutable key/body.
3. `evaluate` recomputes counts/bounds from all saved trials, preserving both origin
   groups. Planned slots and actual releases remain separate denominators.
4. `export_comparison` reads one consistent store snapshot, checks stored record
   identities, profile/flow hashes, source lineage, plan/report settings, trial
   request digests, quotas and origins, then projects the strict export whitelist.
5. `ValidationReportInput` parses a split manifest. `accept_validation_report`
   re-exports the current comparison, requires an exact partition of that origin's
   existing trials, and recomputes accounting. Its writer transaction rechecks
   case freshness and evaluation hash before persisting the receipt.
6. A new trial archives an earlier receipt as `EVALUATION_CHANGED`. A changed/stopped
   source case archives it as `CASE_CHANGED_OR_STOPPED`; archival reads remain
   available. Old manifests cannot be accepted as current.

The receipt is authoritative only for its checked scope:

```json
{
  "verification": "IDENTITY_AND_ACCOUNTING_CHECKED_METHOD_NOT_RERUN",
  "checks": {
    "identity_verified": true,
    "accounting_verified": true,
    "method_rerun": false,
    "physical_validation": false
  }
}
```

`verification` is under `report`; `checks` is a sibling in the returned detail.
Other authoritative fields are report comparison/case/source/revision IDs,
`input_payload_sha256`, `evaluation_snapshot_hash`, canonical split IDs,
`summary.by_source`, missing/unresolved counts, origin, fixed limitations,
`next_measurement`, `is_current` and `archive_reason`. Caller-supplied metrics,
prose, probabilities or method results are not accepted as authoritative tables.

## Accepted/refused input examples

The exact executable accepted construction is:

```python
# runtime is a DISPOSABLE synthetic runtime; cid identifies its current comparison
# with at least one recorded synthetic trial. Never point audit tests at a live store.
manifest = template_validation_report(runtime, cid)
body = ValidationReportInput(report=manifest)
accepted = accept_validation_report(runtime, cid, body)
assert accepted["checks"] == {
    "identity_verified": True, "accounting_verified": True,
    "method_rerun": False, "physical_validation": False,
}
```

The request is exactly `{"report": manifest}`. The manifest fields are:

```python
{
    "schema_version": "validation_report_v1",
    "comparison_id": cid,
    "input_payload_sha256": bundle["payload_sha256"],
    "evaluation_snapshot_hash": bundle["payload"]["evaluation_truth"]["evaluation"]["snapshot_hash"],
    "data_origin": "SYNTHETIC",
    "outcome_origin": "SYNTHETIC_DEMO",
    "protocol_id": "contract-rehearsal-v1",
    "purpose": "CONTRACT_REHEARSAL",
    "development_trial_ids": [],
    "validation_trial_ids": sorted(t["id"] for t in bundle["payload"]["evaluation_truth"]["trials"]
                                   if t["data_origin"] == "SYNTHETIC_DEMO"),
}
```

These expressions supply exact current IDs/hashes rather than fabricated reusable
receipts. A rehearsal is not preregistration. A `DECLARED_VALIDATION_SPLIT` may
partition the recorded origin into development and validation; validation must be
nonempty. Development outcomes are excluded from validation successes without
shrinking the original per-cell validation target.

Exact refused transformations of the accepted request:

```python
bad = copy.deepcopy(manifest)
bad["evaluation_snapshot_hash"] = "0" * 64
# ValueError in current-lineage check; no receipt saved.

bad = copy.deepcopy(manifest)
bad["purpose"] = "DECLARED_VALIDATION_SPLIT"
bad["development_trial_ids"] = bad["validation_trial_ids"][:1]
# ValidationError in split schema: partitions overlap; no service write.

bad = copy.deepcopy(manifest)
bad["content_hash"] = bad.pop("input_payload_sha256")
# ValidationError: missing product binding and forbidden method-envelope field.
```

Omitting a recorded trial, adding a foreign trial, duplicate split IDs, a different
comparison or changed payload digest are likewise refused. Duplicate/overlapping
recording references are checked by `_check_manifest`; recordings used for flow
fitting/validation cannot be confirmation releases. Direct adversarial policy
inputs test that guard without fabricating admitted physical profiles. Empty
ledgers export unknown bounds but cannot create an empty accepted split receipt.

## Outcome and denominator invariants

The new tests use three sources, two layouts and quota one: six planned slots.
For each layout there are three planned slots, regardless of actual releases.
At zero releases the planned interval is `[0,1]` with denominator 3; released
bounds are `[0,1]` with denominator 0, not an observed zero-entry success.

With one baseline entry and one lost intervention token, there are two releases,
four missing slots, one unresolved and one unaccounted token. Neither missing nor
unresolved becomes a capture. Per-cell planned/released denominators remain one
for each executed cell; unexecuted cells have released denominator zero. Full
export aggregates and receipt lineage are compared, not merely HTTP success.

Zone entry at 6 s followed by collection at 8 s remains `zone_entry`, not prevention.
`no_entry` and `intercepted_before_entry` require complete horizon observation and
accounted tokens; invalid requests fail at `TrialInput` before a ledger write.
A synthetic layout rejects a physical-outcome claim before writing any trial.
Both synthetic and physical evaluation groups remain present and never pool.

A completed contradictory rehearsal records baseline entry fraction 0 and
intervention entry fraction 1 for every source despite simulated recommendation
`INTERVENTION`. The recorded effect is -1, the simulation stays unchanged, and no
causal/physical/method-rerun flag is promoted. Contradiction is evidence to retain.

Exact key/body retries return the same trial/evaluation. Changed data under that
key conflict; a new key cannot evade the per-source/layout/origin quota. Existing
API behavior records an out-of-plan order and marks `order_followed=false`; these
tests preserve that behavior rather than adding a new refusal policy.

## Truth and read-only Chalk

Release truth belongs to the evaluator ledger. `CaseInput` rejects an added release
source field. Trial submission/review must not change the saved source report.
Candidate source polygons/IDs are legitimate model inputs; actual per-release
answers and trial notes are different data and never become new identifying cues.

The test uses a genuinely computed synthetic source report and `httpx.MockTransport`.
The four scoped tools read case, source evidence, aggregate prevention and the exact
current validation receipt. Raw trial IDs/keys/notes and per-trial source joins
are absent from model messages. Aggregate per-source counts can be reviewed, but
they are evaluation, not new source observations. Write tools are refused; ledger
and source records remain byte-for-byte equivalent as parsed JSON after review.
The returned receipt retains `method_rerun=false` and `physical_validation=false`.
A mocked response labelled `live_model_response` by the transport-facing API is
still mocked test evidence, not a new live provider verification.

## Rehashing is not a scientific replay

The product parser accepts a schema-valid edited numerical count if its canonical
payload/digest are recomputed consistently. This is its documented self-consistency
scope, not a method-verification bypass. Current-case receipts are generated from
the server's own exact export, not that untrusted edited bundle.

The separate full method test edits a numerical count, updates comparison protocol
commitments, recomputes exported evaluation and outer hashes/IDs, then still gets
`Stale/tampered numerical report` from engine replay. Discrete counts, IDs and
hashes are exact. Existing narrowly scoped display-coordinate rounding tolerance
is unchanged. No production defect requiring a shared patch was identified by
these cases. Full method replay of a redacted product export remains unimplemented;
Jose owns any future reviewed producer/consumer bridge.

## Verification and limitations

Run:

```sh
.venv/bin/python -m pytest -q tests/integration/test_software_export_edges.py \
  tests/integration/test_experiment_protocol.py \
  tests/unit/test_prevention_validation.py tests/unit/test_method_validation.py
.venv/bin/python -m ruff check tests/integration/test_software_export_edges.py
.venv/bin/python scripts/e2e_offline.py --output work/aarush-software-http.json
git diff --check
git diff --exit-code -- data/public data/sample_runs
```

All stores/record mutations are temporary synthetic test fixtures. No running-user
API/store, credentials, enable flags, hardware settings, calibration, thresholds,
frozen models, scientific code or public bytes are changed. Browser work belongs
to Megana: this audit makes no actual browser, physical-trial or live-provider claim.
The optional first-passage conservation audit in mathematical-audit section 11 is
omitted from this focused PR; no tolerance or physics change is proposed.

### Execution receipt — 17 October 2026

- Specified four-file focused command: **90 passed**, no skips (7.72 s).
- Related export, validation-receipt and mocked validation-Chalk tests together
  with those files: **158 passed**, no skips (51.87 s). The new suite contains
  30 cases. One existing Starlette/httpx deprecation warning remains.
- Ruff for the new file and the repository: passed. `pip check`: no broken
  requirements. `git diff --check` and public/sample fixture diff: clean.
- Guarded HTTP command: **122 PASS, 0 FAIL, 6 expected BLOCKED** (15.515 s).
  Camera-open, provider-HTTP, Photon-send and Photon-poll attempt counts: all zero.
  Physical validation and live-provider verification remain false.

The expanded run used a temporary working directory, `PYTHONPATH` pointing to the
checkout and `PYTHON_DOTENV_DISABLED=1`; the new fixture also disables dotenv
loading in its test process. No live application configuration was edited.
No browser execution occurred. CI on the PR commit remains a separate check;
local passes are not represented as a green PR check before CI finishes.
