# Grok-assisted motion-model ablation

This experiment answers a concrete ML question: does the learned velocity-memory
matrix improve a forecast beyond simply continuing recent or average motion?
It runs in Data Lab and through a local CLI. It cannot select or deploy a tank
model, identify a pollution source, or operate hardware.

## What was added

Four motion models use identical training prefixes and forecast horizons:

| Model | Rule |
| --- | --- |
| Stationary | Remain at the prefix's final position. |
| Last drift | Continue its most recent observed displacement. |
| Mean drift | Continue its average displacement from first to final prefix position. |
| Learned ridge | Fit the existing regularized velocity transition model. |

Mean drift estimates two average-velocity components. It is the zero-memory
special case of the existing model: set its two-by-two transition matrix to zero,
while retaining the fitted mean. That isolates the contribution of the matrix's
four learned coefficients. With evenly spaced observations the displacement
average telescopes to `(last_position-first_position)/(prefix_count-1)`.
The formula follows the authors' [drift-method baseline](https://otexts.com/fpp3/toolbox.html#drift-method).

The pinned NOAA sample has 24 hourly positions for buoy 8707978 on 3 October 1987.
This ablation fits prefixes of 8 through 12 positions, forecasts the next six
hours, and scores only positions inside the first 18. Every origin's four
forecasts are fixed before reading/projecting that origin's subsequent truth.
The final six held-out positions never enter this experiment. Whole-file identity
verification is separate from using positions for forecasts or scores.
This applies [rolling-origin evaluation](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation).

For each horizon, compare ridge with each of the three baselines on the exact same
five origins. Signed error difference is **ridge error minus baseline error**:
negative favors ridge, positive favors the baseline. The report includes mean,
median, minimum and maximum differences and lower/equal/higher counts. Relative
MAE skill is `1 - sum(ridge_errors)/sum(baseline_errors)`. It is a ratio of sums,
not an average of origin-wise ratios; if the baseline sum is zero, skill is
undefined and reported as null with `ZERO_BASELINE_ERROR`.

The fixed three-model 18/6 benchmark and old training diagnostic remain unchanged.
No hyperparameter search, statistical significance test, automatic winner or
model promotion is added. More complex models are permitted to perform worse.

## How Grok contributed

The existing [ReefTrace Grok conversation](https://grok.com/project/709fdaeb-06db-41bd-843b-81f567b993da?tab=conversations&chat=139b9a9d-215a-47f0-9f1f-81db9103e724)
received the exact public base commit `d3cda23398d57ac0918765e389164491d3378607`,
ownership boundaries, measured motivation, primary sources, mathematical contract,
file scope and regression requirements. Grok produced concrete Python forecast
and paired-summary functions plus prefix-isolation regression sketches. Local
implementation adapts their return fields and strengthens shape, count, finite
arithmetic and provenance checks. Generated code is reviewed and tested locally;
Grok's browser response is code assistance, not evidence of test execution.

A second prompt supplied the implemented module for static review. Grok found no
supported material defect; independent local checks remain the verification.

No private credentials, local records or personal files were sent to Grok. Its
code/design response is saved privately for the build audit; the public research
and code are represented by this document and the committed implementation.

## Running it

Start the existing local app, open **Data Lab → What does learning add?**, and
choose **Run motion ablation**. The read-only endpoint is
`GET /api/v1/research/motion-ablation`; it uses no operator or model-provider key.

```sh
.venv/bin/python scripts/evaluate_motion_ablation.py --output work/motion-ablation.json
.venv/bin/python scripts/e2e_motion_ablation.py
```

The first command writes a complete offline report, creating its output directory
if needed. The second checks the real loopback API, reconstructs expected contract
properties and verifies the research read leaves tank cases and status unchanged.
Neither opens a camera, calls an external provider, modifies a case or sends a message.

## Interpretation and remaining evidence

The recorded one-hour mean errors are 1,276.9 m for stationary, 13.7 m for last
drift, 1,013.6 m for mean drift and 860.3 m for ridge. Ridge loses to last drift at
all five one-hour origins. At six hours, ridge also exceeds mean drift by 84.4 m
on average. These losing results remain in the UI and report. They motivate
baseline checks, not a claim that a learned model is ready for deployment.

Verification includes 555 Python tests, 33 dashboard state tests, lint, types,
an isolated production build, an offline report and 25 actual loopback HTTP
checks. The browser's explicit run renders the same report. The frozen public
fixtures, original diagnostic and original held-out benchmark are unchanged.

The five origins overlap and come from one buoy-day; they are dependent. NOAA's
hourly positions are [quality controlled and interpolated](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php),
so code-level chronological isolation cannot undo upstream use of later raw fixes.
The comparison remains retrospective training research. It cannot establish raw
operational forecast accuracy, plastic transport, physical tank calibration,
calibrated probabilities or ecological improvement.

A useful next scientific step is independent recordings and sessions under frozen
protocols, followed by comparison with these simple baselines. The outcome of this
small training ablation must not be used to tune against or rewrite the existing
held-out result. Aarush's protected-zone validation module remains a separate lane.
