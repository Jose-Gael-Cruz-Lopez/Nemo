# Nemo: initial observed-motion residual — exploratory result

**Later Data Lab integration:** open **Data Lab → Research details and historical
buoy validation → Load drift-offset study** for the saved four-model table,
two-group plot, independent fixed-scale paths and bounded Chalk review. See
[the panel guide](origin-residual-datalab.md). The reader and browser are not a
new first score or live-provider verification. “Origin” in this model's name
means forecast start, not pollution release; [source inference remains the core
Investigations workflow](source-tracing-mission.md). Actual Grok web rounds
thirteen and fourteen, their complete captures and rejected advice now extend
the archive to **14 rounds / 28 captures**. No frozen scientific result changes.
Earlier unconnected-card wording below describes its original capture time.

**Current verification and review notice — 17 October 2026:** the twelfth actual
Grok web round now reviews this saved result; the additive archive totals
**12 rounds / 24 captures**. Separately, a local numerical replay reproduced all
four forecast outputs and scores exactly, with the eight saved artifact files
unchanged. That local execution is not a second first score, Grok execution,
independent replication or external scientific attestation. The bounded default
reader retains `numeric_replay_verified:false` because it verifies saved bytes
and lineage rather than recomputing the model.

The [sanitized dated local checkpoint](research-evidence/nemo-origin-residual-20261017-local-checkpoint.json)
records **1,898 Python / 233 frontend tests**, Ruff/ESLint and production build
passed, and **174 isolated HTTP passes / zero failures / six expected blocked
scopes**. Its **49 new endpoint tests / 98 adjacent API regressions** are mocked or
provider-disabled checks, not a live Chalk demonstration or extra full-suite
counts. New exact-commit hosted verification, browser integration and physical
validation require separate evidence. Proposed next-cohort selection/acquisition
has not occurred, and no active model is promoted.

**Historical first-result capture follows unchanged.** Its statements that no
result-review round or separate numerical replay had yet been asserted refer to
that earlier checkpoint; the current notice above supersedes those status claims.

---

Checkpoint: **17 October 2026**. Nemo is the current product name; the repository
and historical captures retain ReefTrace/Tideward names. One separately identified
origin-residual diagnostic now has a saved first result: **48/48 planned
model/hour cells scored**, reusing **12 already-viewed later processed buoy
positions**. The original matched-current v2 **36/36** result, preserved v1
**0/36** attempt and fresh six-group **180/180** study remain separate and unchanged.

On this development sample, the residual candidate has lower average and six-hour
endpoint error than stationary, last observed drift and current-only. The result
is **post-outcome exploratory**: this candidate was proposed after the original
two-group outcomes had already been seen. It is not a new untouched test, trained
model, independent skill estimate, identified physical cause or model promotion.

## What was compared

Study ID: `origin-residual-gdp-hycom-15m-exploratory-v1`.

The diagnostic retains the two GDP groups `300234066836710` and
`300534061292930`, the same origin **1 June 2022 00:00 UTC**, the same six later
hourly targets **01:00–06:00 UTC**, and the previously acquired HYCOM 15 m
00/03/06Z current subset. It adds no new scientific acquisition. The first three
candidate forecast definitions and outputs remain unchanged; a fourth candidate
adds the fixed initial observed-motion discrepancy to copied current arrays.

For each group, the final two permitted context fixes are exactly 3,600 seconds
apart. Their origin-tangent mean-sphere displacement supplies `v_last` in east/north
m/s. The model defines `r0 = v_last - u(origin, time_origin)` and integrates
`u_corrected(X,t) = u(X,t) + r0` with the existing knot-aligned WGS84 RK4 solver.
The constant local east/north components are an explicit convention, not global
vector parallel transport or an empirically identified windage coefficient.
Actual axes, times and masks are retained. No clipping, missing-cell fill,
extrapolation, decay tuning, neural network or fitted coefficient is introduced.

Each residual track completed its six-hour horizon with **72 accepted RK4 steps**.
A completed numerical track describes supported model integration; it does not
establish the correctness of the forcing or physical object response.

## Saved descriptive results

**ADE** averages the six hourly position errors within each group, then averages
the two groups equally. **FDE** is the six-hour endpoint error averaged equally
across the two groups. Both are in metres; lower means closer to the saved
processed GDP positions. Neither is a calibrated probability or ecological score.

| Fixed candidate | Equal-ID macro ADE, m | Equal-ID macro FDE, m | Scored cells |
| --- | ---: | ---: | ---: |
| Stationary | 3,490.1188 | 6,069.3529 | 12/12 |
| Last observed drift | 1,510.2316 | 3,240.5762 | 12/12 |
| HYCOM current-only | 5,063.0203 | 9,151.6451 | 12/12 |
| Current + initial observed-motion residual | 1,030.0495 | 2,355.9582 | 12/12 |

The complete primary comparison is available because **all 48 cells scored**.
Every one of the six pairwise comparisons contains the same **12/12 common
model-hour targets**. Four uses of the same twelve processed positions do not
create 48 independent observations. Table rounding is for reading; the saved JSON
retains the full values.

| GDP group | Candidate | Six-hour ADE, m | Six-hour FDE, m |
| --- | --- | ---: | ---: |
| `300234066836710` | Stationary | 5,120.9983 | 8,121.7566 |
| `300234066836710` | Last observed drift | 1,929.6813 | 4,034.0989 |
| `300234066836710` | HYCOM current-only | 4,640.1953 | 8,270.5311 |
| `300234066836710` | Current + initial observed-motion residual | 1,570.4495 | 3,327.6312 |
| `300534061292930` | Stationary | 1,859.2394 | 4,016.9491 |
| `300534061292930` | Last observed drift | 1,090.7819 | 2,447.0535 |
| `300534061292930` | HYCOM current-only | 5,485.8453 | 10,032.7590 |
| `300534061292930` | Current + initial observed-motion residual | 489.6494 | 1,384.2851 |

The residual candidate has lower group-level ADE **and** six-hour FDE than each
of the other three candidates in **both** groups. This statement concerns those
aggregate measures; it does not assert that every hourly prediction improves.
No significance, reliable transfer, operational winner or causal explanation
follows from two already-viewed groups.

## What the result means, and what remains unknown

The development result supports investigating a model that combines recent object
motion with later changes in a prescribed current field. It does not establish
why it helps here. The residual can combine object response, current-model error,
interval averaging, sampling and upstream processing effects. It is not an
isolated measurement of water bias, windage, waves or plastic behavior.

The one-hour context velocity uses a mean-sphere local construction; RK4 uses
WGS84 differential metrics. Those constructions are explicitly different.
HYCOM is retrospective 15 m model output with kilometre-scale support; hourly GDP
positions are QC/interpolated processed buoy estimates. Historical issue-time
availability, assimilation independence, physical/statistical independence and
surface-plastic validity remain unverified. The existing [v2 result guide](matched-current-v2-results.md)
records the source/depth/grid and earlier exposure limitations.

The saved flags keep `automatic_winner_selected=false`,
`automatic_model_promotion=false`, `operational_forecast_skill_verified=false`,
`statistical_independence=false`, `physical_validation=false`,
`global_training=false` and `heldout_tuning=false`. The latter does not turn this
post-outcome model choice into a predeclared evaluation: the explicit
`previously_viewed_target_outcomes=true` and `POST_OUTCOME_EXPLORATORY` scope
remain controlling.

A later metadata-selected, separately frozen whole-ID cohort excluding previously
viewed groups and known aliases is needed to test transfer. Candidate equations,
parameters, failure/selection rules, matched forcing, horizons and denominators
must be fixed before its outcomes are inspected. Even new trajectories do not
remove the already-viewed forcing, availability and assimilation limitations.

No tank, camera, interception or reef claim follows. The physical experiment
still needs a measured water-plane mapping, independently validated layout-specific
drift fields, a frozen release protocol and new accounted token outcomes. These
ocean metre-scale errors cannot be relabeled as tank centimetre accuracy or
predicted-versus-measured reef protection.

## Execution chronology and identities

The exact three reviewed method files were committed at
[`744832594c6327459d3003291e08685d9d483bb0`](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/commit/744832594c6327459d3003291e08685d9d483bb0)
before the first-score action. Their hashes in the saved method receipt still
match the source files. The recorded local UTC clocks are:

| Event | UTC, 17 October 2026 |
| --- | --- |
| Exploratory method contract saved | **23:10:44.279528** |
| All four candidates' forecasts saved | **23:10:44.298723** |
| First score saved | **23:10:44.300622** |

All forecasts were saved and read back before this diagnostic decoded numeric
target coordinates. That ordering prevents future access in this execution; it
does not erase the prior viewing of those same outcomes. These are local
execution receipts, not external attestation or independent replication.

| Artifact in `data/research/origin-residual-v1` | Body bytes | SHA-256 |
| --- | ---: | --- |
| `protocol.json` | 2,407 | `e1073f84e83b2ea078d0890972659e778f87238c417287d8adf70e3649587163` |
| `forecasts.json` | 44,610 | `727e2ce329148c31194bd6fc7b17c39da8b83923439140b9eef5c378376cc0d1` |
| `evaluation.json` | 55,351 | `801d7192ba138817f242401ae6706562f2b8c5c34306219ee37e04a2af2299c8` |
| `identity.json` | 468 | `d36bb0dcfb47db4c668215fa4f9f59db0ceea01917a360f14a04e1e5feda3f27` |

| Reviewed method source | Saved SHA-256 |
| --- | --- |
| `apps/ocean/reeftrace_ocean/origin_residual.py` | `37b84b13bb085651ae2b5b1140b6bc43d8ad5897719eb34b7b525cd8709fa02e` |
| `scripts/evaluate_origin_residual_diagnostic.py` | `961a5f75b0dcbec7287f7815260c010ef53a0a0f9ad26447d2265e80881a84d9` |
| `tests/unit/test_origin_residual.py` | `d0ff8188f9d17c89700968cd4e40a951f5980aacf73351aa5f7bce2c9d9b0de1` |

The original v2 source artifact pins are unchanged:

- Source evaluation: `e330a9b25183b545288d35702ef1686329bd910116285827707947e7614e0347`.
- Source forecast file: `41b1b0f154a78f02e6c971a0b8233f3c938138628d22d69c83547e358faecfbf`.
- Source manifest: `352a25d9c6b10db51592d2595fa2f556c5f8813281e4e673c4d7c2b5c21e3fc0`.

The exact identity above is distinct from the three colocated artifact hashes.
A public integration must use its separately reviewed external identity pin;
self-consistent detached files alone are not an external trust anchor.

## Read the saved result without running another experiment

From the repository root, the default command verifies saved bytes, method/source
lineage and chronology. It **does not generate forecasts or recompute scores**:

```sh
.venv/bin/python -m scripts.evaluate_origin_residual_diagnostic
```

For the separately reviewed result identity:

```sh
.venv/bin/python -m scripts.evaluate_origin_residual_diagnostic \
  --expected-identity-sha256 d36bb0dcfb47db4c668215fa4f9f59db0ceea01917a360f14a04e1e5feda3f27
```

The reader returns `numeric_replay_verified:false`. That flag must remain false
unless a distinctly implemented and executed numerical replay establishes more;
no numerical replay of this new diagnostic is asserted here. A saved first score,
a bounded reader, synthetic tests and a hosted workflow are different checks.

The CLI's **`--first-score` is an explicit creation action**, not a replay command.
Its default output directory now exists, so another first-score call targeting
`data/research/origin-residual-v1` is refused before replacement. Do not delete,
rename, edit or create an alternate output to rerun until it looks favorable.
The original files and this one result must remain identifiable.

## Grok and verification scope

Eleven actual Grok web review rounds/twenty-two captures are preserved in the
[contribution ledger](grok-contribution-ledger.md) and additive archive. The two
latest rounds reviewed this candidate's design and complete source **before its
first score**. Their unscored wording is historical and remains unchanged. There
has been **no new Grok result-review round** at this checkpoint. Python performed
the local first scoring; Grok web did not execute it or establish its accuracy.

The **40 focused synthetic contract tests** and Ruff result covered implementation
contracts, including independent numerical oracles, source immutability, support
failures, fixed denominators and target isolation. They are not real trajectory
measurements or a new full-suite/hosted count. Historical main `33280da7` passed
1,809 Python/225 frontend/174 HTTP checks with six blocked scopes; that earlier
CI does not prove verification of this later source/result commit. Use the actual
exact-commit CI receipt for subsequent release claims.

This result used existing local public data, no new acquisition/provider call,
no xAI API credits or paid billing, no Photon message, no camera or pump action.
