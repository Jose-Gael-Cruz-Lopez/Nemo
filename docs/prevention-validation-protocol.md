# Offline prevention validation v1 — Lane 2

Base: `4ef5b50cef86da3df697b25229193a3214cff24e`. Lane 2 ownership and contract
checkpoint are recorded in [issue #1](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/issues/1).
The coordinator confirmed agreement in the implementation session. This document
and the JSON fixtures freeze the exact wire contract for Lane 3 integration;
no existing API, schema, numerical engine, database or public fixture is changed.

## Run without accounts or hardware

```sh
.venv/bin/python -m scripts.evaluate_prevention_validation \
  tests/fixtures/prevention_validation/unresolved_analysis_bundle_v1.json \
  --development-protocol development-prevention-v1 \
  --validation-protocol heldout-prevention-v1 \
  --output /tmp/prevention-validation.json
```

Validation is a pure computation. The CLI reads one local JSON file and atomically
writes one requested report; it never loads `.env`, opens a database/camera,
contacts an inference provider, downloads anything, or changes Photon settings.
Photon replies remain off. No training, detector fitting, outcome-driven model
selection, or reassignment of development data to a test split occurs.

The input and output budgets are two million UTF-8 bytes, one hundred trials,
one thousand identities per inventory, forty JSON nesting levels and one hundred
thousand JSON nodes. The existing numerical replay retains its profile, geometry,
source, scenario, horizon, particle and six-million-state limits. This is a bounded
local numerical workload, not a real-time service. Invalid files return exit 2;
existing output remains unchanged. Duplicate JSON keys and non-finite numbers are
refused. Input and output cannot be the same file.

## Pure interfaces for Lane 3

```python
from apps.estimation.reeftrace_estimation.prevention_validation import (
    ValidationReport, parse_validation_report, validate_bundle,
)

report: ValidationReport = validate_bundle(
    bundle,
    development_protocol_id="development-prevention-v1",
    validation_protocol_id="heldout-prevention-v1",
)
parsed = parse_validation_report(
    imported_report,
    input_bundle_hash=bundle["content_hash"],
    comparison_id=bundle["payload"]["comparison"]["id"],
    export_evaluation_hash=bundle["payload"]["evaluation"]["export_snapshot_hash"],
)
# An untrusted imported file is not an authoritative numerical result.
if parsed["content_hash"] != report["content_hash"]:
    raise ValueError("Imported report differs from local validation")
```

`ValidationReport` defines every required outer field. The fixture
`tests/fixtures/team_handoff/validation_report_v1.json` and its parser test freeze
nested names and quantities for rendering. The input example under
`tests/fixtures/prevention_validation/` is a Lane 2-owned **synthetic contract
fixture**, not Lane 3's export implementation or a physical experiment. Lane 3
owns `tests/fixtures/team_handoff/analysis_bundle_v1.json` and the exporter.

The shared report fixture matches `unresolved_analysis_bundle_v1.json`: source A
has favorable paired outcomes while source B remains unresolved. It requests a
new independent source-B pair rather than silently endorsing the predicted layout.
The separate `analysis_bundle_v1.json` fixture is the fully resolved positive control.
These are alternative synthetic outcomes for one contract, not independent
replications; never pool their reused trial identities.

Both interfaces raise `ValueError` on invalid contracts. The report parser checks
finite content, version, hash, forbidden claims and expected lineage; the pure
bundle validator must be rerun to establish the reported numerical quantities.
Neither a hash nor an import parser authenticates a malicious rewritten dataset.

## `analysis_bundle_v1` envelope

Canonical hashing is SHA-256 of UTF-8 JSON with sorted keys, compact separators,
and `allow_nan=False`. Array order is part of a payload commitment. Timestamps
are finite numbers with the same receipt meaning as the existing ledger.

| Field | Type and rule |
| --- | --- |
| `schema_version` | Exact string `analysis_bundle_v1` |
| `content_hash` | Lowercase SHA-256 of `payload` |
| `id` | `analysis-bundle-` plus first twenty hash characters |
| `payload` | Whitelisted object described below |
| `metadata` | Optional object containing only string `exported_at`; detached from hash and report |

Payload fields are `comparison`, `profiles`, `trials`, `evaluation_truth`,
`evaluation`, `protocols`, `trial_sessions`, and optional `field_manifest`.
Unknown outer fields, arbitrary notes, private credentials, absolute local paths
and unexpected numerical profile fields are rejected. The numerical profile
whitelist follows the frozen source/flow/transport/gate shapes on the base commit.
Full profiles with extra arbitrary metadata cannot be silently scrubbed while
retaining their old profile hash; this validator refuses such a mismatch.

- `comparison` preserves the existing immutable comparison fields, including its
  exact plan, numerical report, profile snapshots, case/evidence IDs and revision.
  `demo_fixture_key` is the sole optional comparison field. The plan's ID is
  recomputed with the existing `prevention-plan-` digest rule. Its quota, sequence,
  source/layout identities, horizon, units and frozen-before-trials flag must agree.
- `profiles` contains full frozen `baseline` and `intervention` numerical profiles.
  Their SHA-256/flow hashes, IDs and compact comparison snapshots must match. Both
  layouts must have compatible origins, bounds, token class, source geometry and
  declared scenarios. Measured profiles need distinct flow IDs and disjoint
  training/validation drift recording sets across both layouts. They retain their
  frozen calibration, frame-split and camera-session receipts. The existing
  `compare_layouts` engine replays the exact seed/settings; its entire numerical
  report must match, including first-event counts. Illustration paths are never
  used to recompute event order or unsupported-region locations.
- `trials` contains only `id`, `comparison_id`, `trial_key`, `layout`, `data_origin`,
  `outcome`, `entry_time_s`, `interception_time_s`, `token_accounted`,
  `physical_confirmed`, `horizon_completed`, `recording_id`, `ordinal`, `created_at`,
  and `request_hash`. There is no note or release-source field here. Trial IDs use
  the existing digest of `[comparison_id, trial_key]`. IDs/keys/ordinals must be
  unique, ordinals contiguous, and per-source/layout quotas cannot overflow.
  Event times cannot exceed the plan; existing `TrialInput` event, accounting and
  full-horizon gates are reused, with a constant internal scrubbed note.
- `evaluation_truth` is exactly `{scope, trial_sources}`. Scope is
  `EVALUATION_ONLY_NEVER_SOURCE_INFERENCE`; each label is `{trial_id, source_id}`.
  Labels join one-to-one with trial IDs and use declared sources. They are passed
  only to ledger evaluation, never source inference or numerical model selection.
- `protocols` contains `development` and `validation` objects, each with exactly
  `id`, `split`, `plan_hash`, `comparison_hash`, `trial_ids`, `recording_ids`,
  `session_ids`, `frozen_at`, `selected_layout`, and `selection_basis`. Split strings
  are `development` / `validation` (validation is the held-out test split).
  Caller-supplied IDs must match, and the IDs must differ. Hashes bind both splits
  to the same frozen comparison/plan, and selection must remain unchanged.
  Selection basis is `SIMULATION_ONLY` or `DEVELOPMENT_TRIALS`; the latter requires
  declared development trial IDs. Timeline is comparison creation ≤ development
  freeze ≤ validation freeze ≤ each validation trial receipt. Identity inventories
  are unique and disjoint across splits. Development inventories include all flow
  training/validation recordings and their camera sessions. Validation inventories
  exactly match new trial IDs, linked recording IDs and session receipts.
- `trial_sessions` supplies one `{trial_id, session_id}` exporter receipt per new
  trial. Reusing a session within validation is disclosed, not treated as extra
  independent replication. A recording ID cannot represent two releases. Distinct
  IDs or timestamps do not by themselves prove physical independence or footage.
- Optional `field_manifest` is null or a reference containing only
  `schema_version: field_manifest_v1`, `id`, and `content_hash`. Its reference is
  checked, but its physical commissioning is not independently certified here.

### Scrubbing and evaluation hashes

`evaluation` contains exactly `source_snapshot_hash`, `source_evaluation_id`,
`export_snapshot_hash`, and `by_origin`.

The existing private ledger hash covers full comparison/trial snapshots, including
notes. Exporting no notes means the original hash **cannot be recomputed** from
this scrubbed bundle. `source_snapshot_hash` is therefore an exporter receipt;
its ID must match `prevention-evaluation-` plus the first twenty hash characters.
Original trial `request_hash` values are likewise format-checked commitments, not
recomputed from fabricated substitute notes. `original_private_hash_verified`
is always false. Lane 3 must verify original receipts before scrubbing/exporting.

For independently checkable transport integrity, `export_snapshot_hash` uses the
existing evaluation snapshot algorithm on the exported comparison plus scrubbed
trials joined to `evaluation_truth`, sorted by trial ID. The existing
`PreventionService.evaluate` / `_stats` logic is reused through a store-free
service instance; no database is constructed. `by_origin` must exactly equal that
recomputed accounting. A stale hash or changed denominator is rejected even if
the outer bundle is rehashed.

The export contains **one origin cohort**. Mixed synthetic/physical ledgers must
be exported as separate cohort bundles; they cannot be pooled. Both existing
origin groups remain in each report, including the empty one. A synthetic
comparison cannot produce an operator-reported physical cohort.

## `validation_report_v1` meaning

The report includes input hash, comparison/plan/evaluation lineage, explicit
protocol IDs and inventories, dependence warnings, both origin groups and every
source/scenario/layout diagnostic. It has no generated timestamp. `content_hash`
covers all fields except itself and `id`; report ID is `prevention-validation-`
plus the first twenty hash characters. Identical input/config gives identical
finite JSON and hash; detached export timestamp changes do not alter the report.

Each diagnostic exposes model particle denominator, first-zone-entry fraction and
unsupported bounds, capture count/fraction, unresolved and unsupported counts;
observations expose planned slots, actual releases, missing slots, unresolved
outcomes, accounted/unaccounted tokens and the existing planned/released bounds.
Predicted fractions outside recorded outcome bounds are **descriptive disagreement**,
not a significance test or calibrated probability failure.

There is no observed `scenario_id` in the frozen trial schema. Each declared model
scenario is compared with the **same** source/layout observation bounds. The rows
are not additional releases and must never be summed as independent denominators.
Origin totals in `by_origin` remain authoritative.

The frozen selected layout is classified as `NO_NEW_TRIALS`,
`UNRESOLVED_ON_REPORTED_NEW_TRIALS`, `CONTRADICTED_BY_REPORTED_NEW_TRIALS`, or
`DESCRIPTIVELY_USEFUL_ON_REPORTED_NEW_TRIALS`, according to conservative per-source
planned effect bounds. Even the last classification is descriptive pilot evidence,
not causal validation. Source identification accuracy is explicitly unevaluated:
release labels group intervention outcomes; no classifier predictions are supplied.
`physical_validation` and causal/significance claims are always false, including
for operator-reported measured-input cohorts. Synthetic examples cannot claim
physical results.

## NEXT-MEASUREMENT rule

This is a transparent priority heuristic, not validated optimal active learning.

1. Any unsupported simulated path takes priority: request **independent
   layout-specific drift** for affected declared layouts/sources/scenarios. The
   saved aggregate/decimated report does not identify an authoritative useful
   region, so `region_identified=false`, `region_cm=null`, and
   `USEFUL_REGION_NOT_LOCALIZED_IN_SAVED_REPORT` are explicit. No region is invented.
2. Otherwise consider declared source/scenario rows where a nonzero-width
   observed or predicted effect interval can change the layout decision, or where
   prediction disagrees with observed bounds. Prioritize disagreement, then the
   widest observed planned effect interval, then lexical source/scenario IDs.
   Recommend one **independent paired baseline/intervention trial**, with separate
   recordings. A complete quota requires a new frozen plan, not an extra slot or
   retrospective edit to the original plan.
3. If the saved quantities identify no such useful source/scenario, return
   `NO_USEFUL_NEXT_MEASUREMENT_IDENTIFIED`; do not invent a location or promise
   that another image will resolve the decision.

Every recommendation requires fresh layout-specific drift validation before
moving a collector. Rewatching an already retained endpoint does not recover
missing history; cropping an existing full-frame recording is not a new sensor
observation. Pilot sessions, release dependence, perfect absorbing retention,
finite-step flow support and fixed-layout fields prevent significance, ocean
accuracy, coral survival or CO2 claims.

## Scoped verification

```sh
.venv/bin/python -m pytest -q tests/unit/test_prevention_validation.py tests/unit/test_prevention.py
.venv/bin/python -m ruff check \
  apps/estimation/reeftrace_estimation/prevention_validation.py \
  scripts/evaluate_prevention_validation.py tests/unit/test_prevention_validation.py
```

Tests use the known synthetic first-entry/capture ordering and adversarial
all-unresolved, incomplete/unbalanced, quota-overflow, contradictory held-out,
mixed-origin, duplicate trial/recording, stale/tampered hash, incompatible profile,
train/test recording/session leakage, absolute/private field, finite JSON and CLI
cases. A separate parser test binds the example report to current bundle/evaluation
lineage. Existing prevention tests remain unchanged; no numerical defect was found.
