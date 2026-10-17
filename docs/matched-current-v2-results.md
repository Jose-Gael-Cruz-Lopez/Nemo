# Matched-current v2: complete acquisition, a negative current-only result

Checkpoint: **17 October 2026**. The separately identified v2 compatibility
amendment was reviewed, committed, frozen and committed again before its one
bounded scientific acquisition. All six source requests downloaded, both planned
GDP trajectory payloads were retained, all six candidate tracks completed, and
**36/36 planned model-hour cells scored**. The first score was saved and exact
offline replay completed. The preserved [v1 attempt](matched-current-results.md)
still has **0/36 scored cells**; it was not overwritten or repaired.

On these **two buoy groups and twelve distinct later processed position
estimates**, last-observed drift has the lowest reported average and six-hour
endpoint errors. HYCOM current-only has larger errors than last drift, and larger
equal-ID macro errors than stationary. This is a useful negative result for the
declared current-only candidate on this small retrospective sample. It does not
select an operational winner, promote a model or demonstrate plastic/reef/tank
skill.

## 1. What was compared

| Contract | Actual fixed v2 comparison |
| --- | --- |
| Study ID | `matched-current-gdp-hycom-15m-v2` |
| Group 1 | GDP `300234066836710`, WMO `6202613` |
| Group 2 | GDP `300534061292930`, WMO `4102636` |
| Processed observations | NOAA hourly `drifter_hourly_qc`, actual endpoint metadata v2.01 |
| Context | 25 hourly fixes, **31 May 2022 00:00 UTC–1 June 2022 00:00 UTC**, inclusive |
| Origin | **1 June 2022 00:00 UTC** |
| Reserved later positions | **01:00–06:00 UTC**, six hourly targets per group |
| Stationary | Origin position only |
| Last observed drift | Final two context fixes, one hour apart; unchanged bounded origin-anchored mean-sphere log/exp propagation |
| Current-only | Origin position plus HYCOM GOFS 3.1 GLBy0.08/expt93.0 UV3Z 2022 currents at exactly 15 m |
| Forcing | Same actual subset for both groups; three UTC knots at **00:00, 03:00 and 06:00** |
| Solver | Existing knot-aligned RK4, maximum requested step 300 s, hourly outputs, six-hour horizon; 72 accepted steps per current-only track in this run |
| Denominator | Two groups × three candidates × six horizons = **36 cells**, reusing only **12** later processed position estimates |
| Score | Spherical great-circle position error in metres, radius 6,371,008.8 m; unchanged scoring method |

The 25 context fixes are not a learned training set. The first 23 are descriptive
QC, not inputs to these models or a whole-group quality exclusion. Stationary and
current-only use only the origin. Last drift uses only the final two context
positions. Neither model definitions nor parameters were changed after seeing
the outcome.

NOAA describes these as quality-controlled, interpolated hourly buoy data. They
are processed position estimates, not raw independent instantaneous observations
of plastic. A standard GDP drogue is centered around 15 m, but that does not make
a drogued buoy equivalent to loose surface debris.
[NOAA data](https://www.aoml.noaa.gov/phod/gdp/data.php),
[NOAA drogue explanation](https://www.aoml.noaa.gov/phod/gdp/faq.php).

## 2. Results and how to read them

**ADE** is the mean position miss across the six hourly targets, first calculated
within each GDP group and then averaged with equal group weight. **FDE** is the
six-hour endpoint miss, likewise averaged equally across the two groups. Lower
means closer to those saved processed buoy positions; it is not a calibrated
probability, pollution-source probability or predicted reef damage.

| Fixed candidate | Equal-ID macro ADE, m | Equal-ID macro FDE, m | Scored cells |
| --- | ---: | ---: | ---: |
| Stationary | 3,490.1188 | 6,069.3529 | 12/12 |
| Last observed drift | 1,510.2316 | 3,240.5762 | 12/12 |
| HYCOM current-only | 5,063.0203 | 9,151.6451 | 12/12 |

Primary complete-cohort summaries and all three primary pairwise comparisons are
available because **every one of the 36 cells scored**. Each pair compares the
same twelve group/hour targets. These are repeated uses of twelve processed
positions, not 36 independent scientific observations or three independent
cohorts. Rounding in the table is for reading; the saved JSON retains the values.

The group-level values make the heterogeneity visible:

| GDP group | Candidate | Six-hour ADE, m | Six-hour FDE, m |
| --- | --- | ---: | ---: |
| `300234066836710` | Stationary | 5,120.9983 | 8,121.7566 |
| `300234066836710` | Last observed drift | 1,929.6813 | 4,034.0989 |
| `300234066836710` | HYCOM current-only | 4,640.1953 | 8,270.5311 |
| `300534061292930` | Stationary | 1,859.2394 | 4,016.9491 |
| `300534061292930` | Last observed drift | 1,090.7819 | 2,447.0535 |
| `300534061292930` | HYCOM current-only | 5,485.8453 | 10,032.7590 |

Current-only's mean error is lower than stationary in the first group but higher
in the second, and it does not improve on last drift in either group's complete
six-hour summaries. That is not proof that HYCOM is generally inaccurate or that
last drift always wins. No statistical significance, general forecast skill or
causal reason for the error difference was established. Missing physics, object
response, processed observation error and coarse forcing support are possible
limitations to investigate, not diagnosed explanations from these scores.

The record keeps `automatic_winner_selected=false`,
`automatic_model_promotion=false`, `heldout_tuning=false` and
`global_training=false`. An empirical finding can be reported without replacing
the application's transport model or intervention decision.

## 3. The amendment and its exposure history

The frozen [v2 proposal](matched-current-v2-amendment.md) remains unchanged as a
pre-acquisition document. Its DRAFT and “not yet acquired” statements describe
that earlier checkpoint; this result guide records the later executed steps.

The amendment changed only two input-admission rules:

1. NOAA metadata allow exactly two equal, valid UTC history capture-time tokens
   to differ. The full remaining byte string must match the frozen seed-derived
   canonical hash. Raw bodies and their distinct raw hashes remain retained.
2. The study-specific HYCOM axis guard accepts declared native float32 label
   encoding inside double coordinate variables: exact rounded latitude lattice,
   longitude within one float32 ULP of the rounded nominal lattice, exact native
   west label 280, fixed counts/orientation/bounds and actual support retained.

The models, IDs, query URLs, context/target times, current depth/knots, raw
velocity decoding, masks, solver, metrics, all denominators and transport budgets
were unchanged. No coordinate was snapped, no nominal −65-degree east node was
added, and no missing current was filled with zero.

**This was pre-GDP-outcome, not entirely scientific-value-unseen.** v1 had no GDP
trajectory payload or score, but its HYCOM forcing had already been acquired and
decoded for compatibility diagnosis. That exposure was recorded before v2
freezing. The successful v2 is a new, explicitly identified attempt after review,
not a silent retry of v1 or an outcome-tuned tolerance change. The two attempts
must not be pooled as four new buoys or independent studies.

## 4. Committed chronology and source receipts

The saved protocol and acquisition record bind two separate pre-value commits:

| Event | Saved identity or UTC clock |
| --- | --- |
| Reviewed implementation checkpoint | [`c1e7c2503e141da9a95fc51be027c569cbda7cca`](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/commit/c1e7c2503e141da9a95fc51be027c569cbda7cca) |
| Protocol generated | **2026-10-17 22:02:41.391650 UTC** |
| Protocol/identity freeze committed; acquisition Git head | [`23de21c382f972f26e303870aafcadb0c91a7a3e`](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/commit/23de21c382f972f26e303870aafcadb0c91a7a3e) |
| Exclusive acquisition sentinel | **22:02:50.869312 UTC** |
| Manifest acquisition window | **22:02:50.890695–22:03:19.879635 UTC** |
| All fixed forecasts persisted | **22:03:47.184955 UTC** |
| First score saved | **22:03:47.186880 UTC** |

All times above are 17 October 2026. The local clock chain and committed source
checks preserve execution order; they are not an external attestation. CSV
structure, identity and exact times were checked while coordinate cells remained
strings. Numeric target decoding occurred only after all forecasts were saved
and read back. Later exact offline replay recomputed the fixed result and
matched the saved first score.

The attempt made **six requests**, all `DOWNLOADED`, with **754,986 received and
retained body bytes**. No fallback, retry or replacement followed the result.

| Source role | Body bytes | Raw SHA-256 |
| --- | ---: | --- |
| NOAA DAS metadata | 18,686 | `460853bbdcd165ebf8eff0a098cb4784a98a2eb3558136edb7583b8d3449ee68` |
| Origin identity/drogue CSV | 640 | `fe20f70d249e8e099ba63e97341ed52c3c1dff34f5055b6946a4438679b6a339` |
| HYCOM metadata XML | 159,404 | `741d5fcc5cd784415c9b8582394a05f4102f81f0d883821e8267a61ea698164d` |
| GDP `300234066836710` trajectory CSV | 1,828 | `d226154af32dcb59e6e21a069072cdbd4ed8094efe7f1fa63c9f8d6334a1b9a0` |
| GDP `300534061292930` trajectory CSV | 1,824 | `4fd7bbdbd85f54ee789c53a9c2f5dc031dbae32413bb6fe7c454999902a7bd7e` |
| HYCOM current NetCDF | 572,604 | `372b1fe68ac4e59a99899fa5c19dbe52ba6c2ee75550200e4ac0138d92dc3888` |

Preserved source URLs and per-request clocks are in the manifest. At acquisition,
metadata and CSV structural gates enforce their declared dependencies. Detailed
NetCDF depth/time/units/axis decoding happens **after acquisition** and controls
current-only prediction admission; it does not precede the earlier serial GDP
trajectory requests. A static review claiming all such guards fail before any
trajectory request would misdescribe this pipeline.

## 5. Actual current support, not an expanded nominal tile

The accepted array shape is **3 × 251 × 188** for time/latitude/longitude, with
**135,318 valid and 6,246 invalid samples**. Invalid cells remain masked. The
latitude support is **25–35 degrees**, and actual normalized longitude support
is **−80 to −65.03997802734375 degrees**. The requested nominal east edge is not
an additional observed node. Selected depth is exactly **15 m**, and retained
forcing times are midnight, three hours and six hours.

At the tile's middle latitude, approximate native spacing is **7.715–7.721 km
east–west** and **4.434 km north–south**. Grid spacing is not guaranteed effective
physical resolution. RK4 samples this prescribed field with bilinear space and
linear time interpolation; it neither solves new fluid dynamics nor learns
subgrid behavior. The [amendment's RK4 explanation](matched-current-v2-amendment.md#6-what-rk4-does-in-plain-language-and-equations)
describes the four-stage method and exact time-knot stops.

The generic decoder's `source_origin_verified=false` and
`issue_time_verified=false` remain deliberately distinct from transport receipts.
Local format/byte validation alone cannot establish origin or historical
forecast availability; the acquisition manifest separately records where the
bytes were fetched. Neither receipt proves assimilation independence.

## 6. Durable artifact identities and offline reproduction

All study artifacts are public under `data/research/matched-current-v2`. Keep the
trusted result identity separate from the original protocol identity.

| Artifact | Body bytes | SHA-256 |
| --- | ---: | --- |
| `protocol.json` | 14,096 | `fe19dd6f6979d40ccfc1821af218aa5c2494db04c3af53ae31f4ae4ed989e793` |
| `acquisition-start.json` | 402 | `779cd40cf7ded603256f2012b478fd5fb056e7c87dfd58c189d80da73d9d06df` |
| `manifest.json` | 5,597 | `352a25d9c6b10db51592d2595fa2f556c5f8813281e4e673c4d7c2b5c21e3fc0` |
| `forecasts.json` | 27,704 | `41b1b0f154a78f02e6c971a0b8233f3c938138628d22d69c83547e358faecfbf` |
| `evaluation.json` | 99,409 | `e330a9b25183b545288d35702ef1686329bd910116285827707947e7614e0347` |
| Trusted protocol identity module | — | `c7a883cc5a2f938809839d9785fa8477146c5bb26a21d68c1d730afda4543f07` |
| Trusted result identity module | — | `001b0f533b21550df22978abf1370a9d39a05b8929789b5be698ba93fb979caf` |

From the repository root, these are **read/replay commands**, not acquisition or
first-score commands:

```sh
PYTHONPATH=. .venv/bin/python scripts/evaluate_matched_current_v2_study.py \
  --directory data/research/matched-current-v2

PYTHONPATH=. .venv/bin/python -c 'import json; from apps.ocean.reeftrace_ocean.matched_current_result import load_frozen_matched_current_result; print(json.dumps(load_frozen_matched_current_result(study_version="v2"), indent=2))'
```

The first command is an actual numerical replay of fixed artifacts. The second
is a pure bounded reader: it verifies the externally pinned identity, lineage,
clock/shape/metric structure and exact snapshot, and returns
`numeric_replay_verified:false`. That flag must not be changed merely because a
separate replay was performed. Neither command fetches, re-freezes, repairs or
changes the saved study.

The byte-exact command passed on the acquisition machine but failed on Linux in [hosted run 39073934821](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/actions/runs/39073934821) after all 1,779 Python tests passed. A separate [post-outcome portability check](matched-current-v2-portable-verification.md) preserves all frozen evidence and discloses tiny computed-number differences under explicit absolute bounds. It neither changes the scientific protocol nor replaces the saved first score. Use `python -m scripts.verify_matched_current_v2_portable` for that distinctly labeled software verification.

## 7. Data Lab, Chalk and HTTP verification

In Data Lab, choose **Study version → v2 · compatibility amendment**, then
**Load matched-current study**. The preserved original attempt remains available
through the v1 selector. Loading reads saved evidence; it does not acquire or
perform a first score. The path checkboxes and selected-group/hour controls alter
what is visible, not the frozen axes or numerical denominator. Recorded paths
mean later processed buoy positions; the three other paths are the frozen
candidate predictions. Hourly displacement arrows connect saved hourly fixes;
they are not independent measurements of instantaneous water velocity.

The public GET endpoint is:

```text
/api/v1/research/matched-current?study_version=v2
```

Omitting the version preserves v1 API compatibility. Unknown versions return
422; missing trusted evidence returns 404; invalid or crossed identities return
409. The selected operator-protected Chalk request carries `study_version`,
`report_sha256` and `protocol_sha256`. The server binds the exact selected study
before a model turn and checks the full snapshot again afterward. Its sole
research tool reads the saved evidence and v2 exposure declaration. It cannot
acquire data, train, score, mutate a case, write a trial, open a camera, control a
pump or send a Photon message. REPORT must cite the exact selected report and
protocol. Provider availability and a meaningful explanation are separate from
the deterministic result.

The extended **disposable, provider-disabled HTTP run passed 174 checks, zero
failures and six expected external/physical scopes blocked**, in **16.851 s**.
It verified v1's unchanged 0/36 ledger, explicit v1 selection, v2's full envelope
against the authoritative pure reader, all 36 slots, selected version identity,
422 unknown versions, 401 missing operator access, and 409 cross-version/stale
report pins. Disabled v2 Chalk returned bounded `STOP / NOT_CONFIGURED` with
exactly the same evidence; an opaque digest proved the entire disposable SQLite
store unchanged. All four camera/provider/Photon-send/Photon-poll attempt guards
remained zero. The live application/store was untouched.

The local receipt is `work/tideward-matched-v2-offline-http.json`, **610,100 bytes**,
SHA-256 `6d690d9d6585c6b33e76fb445e65be5412f5a19ce1ca77fa00e87c1eea03daa0`,
with its adjacent `.log`, in the parent task workspace. This receipt proves a
software-only workflow, **not a live Chalk round trip or physical product**.
The six blocked isolated scopes stay blocked. Separately, the actual browser
showed both GDP groups, path toggles/hourly arrows, invariant scales/metrics,
a switch to v1's 0/36 and back to v2's 36/36. A live Chalk REPORT cited the exact
selected v2 report/protocol. Those are distinct live/browser checks, not a
provider call by the disposable harness.

The pre-acquisition checkpoint passed **1,770 Python / 331 focused subset /
225 frontend** checks. The final post-acquisition full suite passed **1,779
Python tests**, with one upstream dependency warning, alongside **225 frontend**
and the **174 / 0 failures / 6 blocked** HTTP result. Lint, types and production
build passed. The focused subset is not an additional independent scientific
sample. Exact-head hosted CI needs its own release evidence and remains pending
at this documentation checkpoint.

## 8. What remains unvalidated

The accepted current field is retrospective analysis with future valid times.
No historical origin-time issue receipt, assimilation exclusion, complete
physical-alias resolution, statistical independence or forecast-causality claim
was verified. Both selected objects are buoys, the horizon is six hours, and the
sample is too small to justify general model selection. The exact same groups
and repeated processed targets underlie every candidate comparison.

There was no learned fit, residual/windage/Stokes/diffusion tuning, plastic source
attribution, pollution interception experiment, tank calibration or reef-benefit
measurement. These ocean results must not calibrate a centimetre tank or turn
conditional modeled prevention into measured effectiveness. No physical release,
camera activation, new Photon message, xAI API use or paid billing was part of
this v2 HTTP verification. Independent field/tank trajectories and an explicitly
reviewed broader evaluation remain separate next steps.
