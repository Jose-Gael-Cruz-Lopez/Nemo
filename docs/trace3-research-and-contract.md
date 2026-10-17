# Trace 3: defensible validation and product handoff

Research and proposed integration contract, 17 October 2026. This document does
not implement Aarush's validation lane, train a model, run a physical trial or
change the numerical transport engine. Follow the existing ownership rules in
`docs/team-handoff-prompts.md`; the export/report schemas agreed by their owners
take precedence over the suggested names below.

## The next useful result

Show three separate things: what the frozen transport model predicted; what
independent operators reported for new releases; and which missing measurement
would help the team decide. Keep source inference separate: an `UNKNOWN` source
can still anchor a conditional prevention comparison across every declared
source. Neither particle fractions nor trial outcomes identify a real polluter.

Existing implementation references:

- `apps/estimation/reeftrace_estimation/prevention.py`: first-entry comparison,
  declared scenarios, all-particle denominators and unsupported-flow withholding.
- `apps/api/reeftrace_api/services/prevention.py`: frozen plan, one-token ledger,
  retrospective/duplicate-recording rejection and descriptive outcome bounds.
- `apps/api/reeftrace_api/schemas/prevention.py`: explicit origin, first-event
  ordering, full-horizon attestation and token accounting.
- `docs/prevention-physics.md`: fixed flow, perfect retention, reflecting walls
  and a surface receiving-zone proxy. These assumptions need physical testing.

## Five research findings that change the build

**1. A release is the experimental unit.** Ten camera frames of one release are
not ten independent trials. For a useful baseline/intervention pilot, match the
source, token class, water level and declared horizon; run fresh releases in
time/session blocks, with recovery and settling between runs. Future randomized
layout order within blocks helps separate intervention effects from time drift.
The current counterbalanced sequence is not randomization. Pairing means matched
conditions for two different releases; it does not observe two counterfactual
outcomes of the same physical event. This is a ReefTrace adaptation of
[NIST's blocking and randomization guidance](https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm).
Moving the mesh requires the layout-specific drift validation already enforced.

**2. Hold out whole releases and sessions before tuning.** Fit drift, dispersion,
thresholds and mesh placement on development runs. Freeze those choices, then
evaluate new releases. Keep every point from one recording on one side of a
split; for a claim about new setups, hold out complete sessions/configurations.
Disjoint IDs are necessary but cannot prove physical independence or that a
human never inspected the test outcomes. Report missing protocol/session
evidence as unverified. These choices apply the official
[group-wise evaluation guidance](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data)
and [test-data leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage).

**3. More simulated particles reduce simulation noise, not physical uncertainty.**
With independent indicator draws, a model's estimated arrival fraction has
Monte Carlo standard error approximately `sqrt(p_hat*(1-p_hat)/N)`. That describes
integration under the frozen model; it does not account for wrong flow,
unmodeled escape or camera failure. Baseline and intervention simulations sharing
random numbers are correlated, so an independent-sample error formula cannot
automatically be used for their difference. Existing unsupported-outcome bounds
and scenario ranges are not confidence intervals. The distinction follows
[Owen's treatment of Monte Carlo means and error](https://artowen.su.domains/mc/Ch-intro.pdf)
and inspection of ReefTrace's simulator. Keep v1 descriptive; do not add a
confidence percentage to the model's recommendation.

**4. Five releases per cell are a pilot.** Under the additional assumptions of
independent, identically distributed Bernoulli outcomes and complete observation,
zero entries in five releases has a two-sided 95% exact binomial interval of
approximately `[0, 0.522]`; five entries in five gives `[0.478, 1]`. These were
computed locally with `scipy.stats.binomtest(...).proportion_ci(method="exact")`.
They illustrate how little five observations constrain a population rate; they
are not ReefTrace measurements. Unresolved outcomes cannot be silently omitted
to use this calculation. V1 should omit significance tests and confidence
intervals until its observation and independence assumptions are supported.
[SciPy documents the exact Clopper–Pearson method](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats._result_classes.BinomTestResult.proportion_ci.html).

**5. Conformal prediction is a later calibration project.** Standard split
conformal needs a frozen predictor and fresh exchangeable calibration examples;
its usual guarantee is marginal, not a guarantee for every source or tank
condition. For an unbounded scalar score, the corrected rank is
`ceil((n+1)*(1-alpha))`; with only five calibration releases, a 90% target asks
for rank six, beyond the observed scores, yielding the conservative whole-space
fallback. Frames cannot manufacture extra independent calibration releases.
Recalibration after changing pump/mesh conditions needs a justified distribution
assumption. These are consequences of the
[split-conformal construction](https://arxiv.org/html/2107.07511v6#S1.SS1);
[nonexchangeable extensions](https://arxiv.org/abs/2202.13415) require additional
methods and assumptions. Do not label existing scenario bounds conformal.

## Research design for the later independent validation method

The shipped Trace 3 API accepts a smaller strict split manifest and recomputes
accounting itself; it does not accept the suggested metric fields below. See
`docs/trace3-implementation.md` and the exact schemas before implementing a producer.
This section describes Aarush's later independent analysis, not the current import API.

### Suggested analysis report fields

Use a small deterministic report, not a new predictor. The producer should expose
an importable pure validation function plus its CLI so Trace 3 can recompute the
same result. Do not accept metrics merely because an uploaded JSON names the
current comparison. Suggested fields, subject to the shared fixture freeze:

| Field | Meaning and integration check |
| --- | --- |
| `schema_version`, `algorithm_version` | Fixed bounded strings; reject unknown versions. |
| `input_payload_sha256` | Exact public analysis-bundle payload hash, recomputed locally. |
| `comparison_id`, `plan_id`, `evaluation_snapshot_hash` | Must match the selected immutable export; the evaluation hash is an opaque provenance reference. |
| `protocol` | Declared development/validation protocol IDs and exact trial/recording partitions; evidence level `VERIFIED_REFERENCES` or `DECLARED_ONLY`. Do not claim behavioral independence from IDs alone. |
| `config_sha256`, `report_sha256` | Hash canonical configuration and report payload; exclude volatile metadata and the hash field itself. Hashes establish consistency, not authenticity or scientific validity. |
| `data_origin`, `outcome_origin` | Preserve `SYNTHETIC`/`MEASURED_TANK` inputs and `SYNTHETIC_DEMO`/`OPERATOR_REPORTED_PHYSICAL` outcomes separately. Never pool the two outcome groups. |
| `by_source` | Per source/layout counts, exact used trial IDs, planned/released/unresolved/missing counts, and both planned-slot and actual-release bounds. |
| `prediction_comparison` | Per source/scenario model fractions/bounds and observed bounds, with explicit denominators; discrepancies are descriptive, not significance or calibrated accuracy. |
| `next_measurement` | Bounded action, reason codes, existing source/layout/scenario IDs and `location_cm:null` when the export cannot locate an unsupported region. No actuation. |
| `limitations` | Fixed reason-code-derived text; include operator reporting, low sample size, unsupported paths, unverified split and tabletop scope when applicable. |
| `physical_validation`, `supports_causal_claim`, `calibrated_probability` | `false` in v1, including measured-input simulations and completed operator-reported pilots. |

For a cell with planned quota `Q`, released count `R`, confirmed entries `E`,
unresolved `U` and missing `M=Q-R`, recompute:

```text
planned entry bounds = [E/Q, (E+U+M)/Q]
observed entry bounds = [E/R, (E+U)/R] if R>0, otherwise [0,1]
descriptive benefit bounds = [baseline_lower-intervention_upper,
                              baseline_upper-intervention_lower]
```

These bound recorded/missing outcomes, not an unknown population parameter.
Accounted tokens and full-horizon observation remain explicit. Source scores
must never become averaging weights. Compare model and observed intervals
side by side; nonoverlap is a discrepancy flag, not a statistical rejection.

## Verify the report against the actual export

The export producer's schema is
`apps/api/reeftrace_api/schemas/evidence_export.py`. Its envelope is
`schema_version:"analysis_bundle_v1"` with `payload_sha256` covering canonical
`json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False)`.
Export time and current/archive metadata are outside that payload hash.
`payload_canonical_json` preserves the exact hashed bytes across JavaScript
round trips, which otherwise change numbers such as `1.0` to `1`. Verify its
UTF-8 digest, canonical form and agreement with the parsed payload; do not hash
a JavaScript reserialization and silently change the Python contract.
Inside the payload, identity references include `comparison`, `frozen_plan` and
the explicitly separated `evaluation_truth.trials`/`evaluation_truth.evaluation`.
Layout drift recording partitions are under `provenance.layouts.<layout>.flow`.
Use the producer's schema/fixture for remaining exact paths.

The original `evaluation.snapshot_hash` hashes private unredacted records;
do not try to reproduce it from the public redacted payload. Instead:

1. Strictly parse bounded finite JSON, reject duplicate keys/unknown versions,
   verify the payload hash, source/layout IDs and frozen plan identity.
2. Reject duplicate trial IDs/ordinals, duplicate nonempty recording IDs, incompatible
   origins, impossible event ordering and impossible count/denominator totals.
   Exclude recording IDs used to develop either flow/model from an independent
   validation partition. A missing reference is not proof of a clean split.
3. Run the same pure validation function locally on that exact export and declared
   config. Compare canonical report content, not only its self-supplied hash.
   Otherwise display the external report as **unverified** and do not use it for
   recommendations or Chalk's authoritative evidence.
4. A later trial changes the export/evaluation. Keep the old receipt readable,
   label it archival, and reject it as the current report. Recheck source-case
   revision and evaluation hash atomically before saving any Chalk receipt.
5. Give Chalk verified aggregate counts/bounds, IDs, status and reason codes.
   Raw release truth stays in evaluation and out of source-inference tools.

## A useful next-measurement rule

Use a deterministic priority list rather than calling it optimal active learning:

1. **Unsupported field:** request new independent layout-specific drift coverage
   for the named source/scenario. The redacted export may identify the affected
   source/layout but cannot necessarily locate the missing spatial region; say
   that explicitly instead of inventing coordinates. Refit/revalidate and freeze
   a new comparison before treating the new field as its prediction.
2. **Incomplete frozen plan:** take the next unfilled predeclared slot. Preserve
   its order, missing slots and all unresolved outcomes; do not adaptively collect
   favorable results until the displayed score improves.
3. **Completed but unresolved decision:** propose a *new* independent matched
   baseline/intervention block for a source whose observed uncertainty or model
   scenario disagreement changes the decision. Use a declared deterministic
   ordering to break ties; label the choice a heuristic. Adaptive follow-up data
   are development data unless a fresh confirmation protocol is frozen.
4. **No physical data or no verified split:** return that limitation and a concrete
   request for independent releases, not a winning-layout confidence score.

For the four-person team: one operator maintains pump/mesh configuration and
settling; one releases and recovers a single token; one observes first events
through the complete horizon; one records the ledger and checks IDs. Keep a
reviewer blind to the model's preferred layout where practical. This makes the
software evidence reproducible without claiming automatic physical verification,
ocean generalization, coral survival or measured avoided ecological harm.
