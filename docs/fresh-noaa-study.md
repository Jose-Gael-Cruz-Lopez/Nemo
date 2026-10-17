# Tideward: fresh-to-project NOAA motion comparison

This study asks a small, concrete question: after observing part of a historical
buoy trajectory, how accurately do five fixed motion algorithms predict its next
six hours on GDP identifier groups the project has not previously scored?

It is separate from the tabletop source estimator and intervention experiment.
Lower buoy motion error does not establish a plastic release source, a better
interception layout, or reef protection. The camera experiment still needs its
own measured flow and independent token releases.

## Team checkpoint

Aarush's [PR 5](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/pull/5) was already
merged at `8737a02` before this study started. It adds the independent pilot
protocol, evaluator run-log template and four synthetic validation scenarios.
It preserves missing/unresolved outcomes and includes adverse outcomes instead
of assuming that the intervention succeeds. It adds no physical trial results
or changes to the transport equations. His earlier prevention validator is also
merged. The new study builds on these contracts rather than replacing them.

## Freeze before acquisition, predict before scoring

The current artifact directory is `data/public/noaa-fresh-drifter-v2/`.
The protocol and its detached SHA-256 identify the selection rule, exclusions,
requested time/region blocks, exact models, coordinate system, budgets and failure
policy. Selection uses only declared metadata and is saved before trajectory
requests. A failed download is retained; no better-looking substitute is chosen.

The first protocol was pushed at `4de5fa6` before its requests. Its attempt had
two metadata timeouts and a local parser bug: NOAA declares the experiment-number
unit as `count`, whereas the new reader expected an empty token. It selected no
groups and requested no trajectories. All original receipts remain in
`noaa-fresh-drifter-v1/`.

Before any trajectory outcome existed, a second protocol explicitly corrected
the metadata units and increased transport timeouts. That amendment and the
first attempt's receipts were pushed at `086942c` before the second attempt.
The dates, five algorithms, parameter settings, 223 pre-study exclusions and
known-alias rules did not change. The global alias catalog is identity metadata,
not a training cohort; origin snapshot metadata is selection context, not a
held-out forecast result. This is a disclosed pre-outcome acquisition amendment,
not an outcome-based parameter change or replacement of a failed selected buoy.

The scope is new-to-project historical GDP groups, with known alias exclusions.
Unresolved aliases are disclosed. A logical-ID holdout is not proof of physical
or statistical independence. Nearby drifters and observations within one track
can be correlated. Each evaluation group supplies its own allowed observation
prefix to the fixed algorithm; this is not a claim of prediction without context
or of one globally trained model transferring with no adaptation.

All model tracks are generated from permitted prefixes before held-out positions
are scored. Forecasts free-run from their own previous prediction. They never
reset to the next observed point. The training-prefix parser and the NOAA
retrospective hourly product's upstream interpolation are different issues:
our own future-access guard does not remove NOAA's upstream processing.

## What the five algorithms do

| Model | Fixed behavior | Learned from the permitted prefix |
| --- | --- | --- |
| Stationary | Keep the final observed position unchanged. | Final position only. |
| Last drift | Continue the most recent displacement velocity. | Final position and last velocity. |
| Mean drift | Continue net displacement divided by prefix duration. | Final position and mean velocity. |
| Ridge velocity AR(1) | Recur prefix-centered velocity with fixed ridge penalty and stability cap. | Local mean, scale and velocity-memory matrix. |
| Constant-velocity Kalman | Update position/velocity state on prefix measurements, then predict without future corrections. | Filtered state; noise settings remain fixed. |

All coordinates used by the motion algorithms are metres in the declared local
spherical frame; vector velocities are metres per second. Great-circle distance
scores geographical positions on the same declared mean-radius sphere.

The Kalman position-noise standard deviation and acceleration spectral density
are assumptions, not measured NOAA uncertainty or fitted tank noise. NOAA's
east/north velocity uncertainty columns are not position covariance. A centimetre
scale tank needs a separate development-only timestamp/noise protocol; these
hourly ocean settings must not be copied into its camera tracker.

## Reading the results

- **ADE (m):** average of the six future position errors for a drifter. Smaller
  means a closer predicted path over that horizon.
- **FDE (m):** position error at the sixth future hour. It can improve even if
  ADE becomes worse; compare each metric separately.
- **Vector RMSE (m/s):** root mean squared magnitude of the difference between
  predicted and observed interval displacement velocities. It checks direction
  and speed, and uses each model's own previous predicted position.
- **Coverage:** requested groups, selected/downloaded groups, scored model-hour
  outcomes and unique observed intervals have different denominators. Reusing a
  measurement for five algorithms does not create five independent experiments.
- **Withheld aggregate:** missing required groups or failed model tracks prevent
  a complete-target macro comparison. Individual available results and reasons
  remain inspectable; missing data is not a zero error.
- **Kalman ellipses:** model-assumption diagnostics only. Observed ellipse hits
  are not calibrated source probabilities or established confidence coverage.

An apparent lowest error on this small cohort is a descriptive result, not
automatic selection or deployment of a model. Keep all losses and numerical or
acquisition failures visible. Do not tune parameters against these outcomes and
continue calling the same cohort untouched.

## Actual first frozen result

The amended acquisition retrieved all six selected trajectories. The reviewed
evaluator and its implementation receipt were pushed at `cc1f7fa` before the first
real score. The forecast receipt was saved before scoring future positions.
All **180/180 model-hour outcomes** scored, with **36 unique later observation
intervals**, zero failed outcomes and zero unfilled slots.

| Fixed algorithm | ADE (m) | FDE (m) | Vector RMSE (m/s) |
| --- | ---: | ---: | ---: |
| Stationary | 5,010.201 | 8,668.078 | 0.439076 |
| Last observed drift | 1,573.423 | 3,305.763 | 0.193552 |
| Mean prefix drift | 2,930.077 | 5,004.445 | 0.257485 |
| Own-prefix ridge AR(1) | 1,772.130 | 3,460.155 | 0.196928 |
| Fixed constant-velocity Kalman | 1,655.662 | 3,410.802 | 0.197733 |

Last drift has the lowest aggregate error in all three declared metrics on this
small cohort. Ridge's better result on the earlier viewed cohort did not carry
over. This is retained as a negative result for the more complex algorithms,
without retuning or automatic promotion. It does not establish a universal
winner, a statistically significant difference or a cause of the performance gap.

The six GDP-ID days are `300234062321360` and `300234062953270` (Atlantic, June
2021), `300234060609830` and `300234063435990` (Indian, June 2021), and
`300234063123200` and `300234065385690` (North Pacific, June 2022). All are outside
the frozen 223 pre-study exclusions and have distinct positive selected WMOs.
Ten pre-study IDs still have missing or ambiguous aliases, so full physical-alias
resolution and statistical independence remain false. Kalman's nominal
ninety-percent ellipse hits range from three to six of six per group; these
assumption-based counts are not calibrated coverage.

Protocol SHA-256:
`0f34c38c8cb02a6934de6764d6ec958042eccacdf6b0081d7ec71bbffb570d3d`.
Forecast receipt SHA-256:
`11d0bbc893275d211d95cba902ce30822d5d5c12c475b46d0792b0b4f746667f`.
Reference report file SHA-256:
`aaf4cae5ce507f36290b133615a2ca61b033c27262971005864674e03d27888b`.
The API's canonical JSON snapshot digest is a different serialization hash and
is deliberately named separately in Chalk citations.

The useful next physical measurement is a separate development-only set of
timestamped token tracks passing near the proposed interceptor and protected-zone
boundaries, with whole runs withheld from fitting. Inspect path and event errors
there before freezing the pilot layouts. Neither this ocean cohort nor lower
motion error supplies the missing physical capture/zone-entry outcomes.

## Data Lab and Chalk

Data Lab reads a verified frozen study; opening the page does not download NOAA
data, refit parameters against new targets, open cameras or send messages. The
deterministic coverage, trajectories and metrics remain visible independently of
Chalk availability.

Chalk gets a separate read-only research evidence tool. Its explanation must cite
the exact saved study lineage and preserve uncertainty. It cannot acquire data,
choose new hyperparameters, change source scores, log physical outcomes or
authorize an intervention. A failed provider request remains a failed request,
with the numerical report still available.

## Reproduce and verify

From the repository root, after the frozen artifacts are present:

```sh
.venv/bin/python scripts/evaluate_fresh_drifter_study.py --output work/fresh-noaa-replay.json
.venv/bin/python scripts/e2e_offline.py --output work/fresh-study-http-audit.json
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check apps adapters scripts tests
```

Acquisition is a separate explicit command and never occurs in CI or ordinary
page requests. A replay must verify raw bytes, selection, implementation and
reference results; changing an old protocol to make a check pass is not a repair.

GitHub checks run on pushes and pull requests. The Grok research schedule remains
paused at the user's request; Grok is used interactively for planning and review.
Its chat output does not itself execute repository code or establish test passage.

## Primary sources

- [NOAA AOML hourly GDP data](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php):
  quality-controlled hourly positions/velocities, release history and access.
- [Dataset DOI](https://doi.org/10.25921/x46c-3620): Elipot et al., hourly location,
  current velocity and temperature from Global Drifter Program drifters.
- [NOAA real-time data and identifier distinction](https://www.aoml.noaa.gov/phod/gdp/real-time_data.php)
  and [WMO/GDP table](https://www.aoml.noaa.gov/phod/dac/wmoid.html): operational
  fixes and logical identifiers must not be silently mixed.
- [Elipot et al. 2016](https://doi.org/10.1002/2016JC011716): derivation of the
  retrospective hourly position/velocity product.
- [OpenCV Kalman filter](https://docs.opencv.org/4.13.0/dd/d6a/classcv_1_1KalmanFilter.html):
  prediction and measurement correction are separate operations; our numerical
  implementation is reviewed and tested locally.

Sources checked 17 October 2026. The project is not endorsed by NOAA.
