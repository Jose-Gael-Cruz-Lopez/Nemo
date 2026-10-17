# ReefTrace learning plan: what to train, what to measure, and what error means

Research and source-code audit, 16 October 2026. This is a proposed development plan;
it does not claim the proposed model extensions or physical experiments are implemented.

## The decision

ReefTrace does not need a newly trained large language model to start working. Its scientific
problem is motion and uncertain source inference. Keep the numerical transport estimator
separate from the Chalk-hosted language model that calls tools and explains stored evidence.
There is already a small learned motion model in Data Lab. The next useful learning step is
better independent motion evaluation and then measured tank calibration, not a large neural
network trained on 24 rows.

The two scientific tasks must remain distinct:

1. **Forecasting:** given earlier observed positions, where will this object go next?
2. **Source inference:** which declared source could plausibly have produced this observation,
   after accounting for unknown age, transport uncertainty and retention?

A model can forecast well yet fail to distinguish sources whose pathways merge. Conversely,
a few distinctive upstream positions can identify a tank inlet despite an imperfect long-range
forecast. A lower forecast error alone does not validate plastic-origin attribution.

## What the current repository actually learns

### Real-data Data Lab

`apps/ocean/reeftrace_ocean/benchmark.py`, `_forecast` at line 113, fits a regularized
two-dimensional velocity autoregression. The 1,950-byte pinned NOAA CSV contains **24 hourly
positions for drifter 8707978 on 3 October 1987**. The first 18 positions supply 17 displacement
velocities and 16 consecutive velocity pairs. Six later positions are held out.

In local east/north metric coordinates, with an hourly time step:

\[
v_t=(x_t-x_{t-1})/\Delta t,\qquad
\hat v_{t+1}=\mu+(v_t-\mu)A,\qquad
\hat x_{t+1}=\hat x_t+\Delta t\hat v_{t+1}.
\]

This notation uses row vectors, matching the code. A common scalar training-only scale makes
the ridge penalty dimensionless. The 2×2 transition matrix is fitted as
`solve(Z.T @ Z + alpha*I, Z.T @ Y)` with fixed `alpha=1`; the two mean-velocity terms plus four
matrix entries comprise the six reported learned parameters. A fixed maximum spectral radius
of 0.98 limits unstable free-running growth. It is a small learned linear model, not a neural
network, physics-informed neural network, ocean-current model, or model trained on plastic.

The current reproducible results are:

| Model | Mean position miss / ADE | Position RMSE | Final-hour miss / FDE |
| --- | ---: | ---: | ---: |
| Stay at last observed position | 3,855.00 m | 4,323.82 m | **6,774.61 m** |
| Continue last measured displacement | 4,385.78 m | 5,432.98 m | 9,832.21 m |
| Learned ridge velocity AR(1) | **3,557.40 m** | **4,318.48 m** | 7,561.25 m |

The learned model's mean error is 7.72% lower than stationary persistence on this one test,
while its final-hour miss is 11.61% larger. Its RMSE improvement is only about 0.12%.
These are all relevant results. One selected day with six dependent test hours cannot establish
general superiority, and this test must not be reused to choose model settings.

The CSV, source URL, units, licence, row count and SHA-256 are verified before fitting.
`tests/unit/test_real_data.py` explicitly changes the held-out positions and the published NOAA
velocity/uncertainty columns, and checks that predictions and training error radii do not
change. Held-out positions change only evaluation errors. Those tests establish an important
code-level isolation property. They cannot undo future information that may have entered
NOAA's upstream interpolation. NOAA describes the product as quality-controlled,
mathematically interpolated data; evaluation here is retrospective product evaluation, not
raw operational forecasting. [NOAA endpoint metadata](https://erddap.aoml.noaa.gov/gdp/erddap/info/drifter_hourly_qc/index.html),
[NOAA product documentation](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php).

### Tank tracing

`apps/transport/reeftrace_transport/flow.py`, `fit_flow` at line 63, aggregates observed marker
drift by spatial cell and interpolates the median vectors using inverse-distance weighting
(IDW). This is data fitting. It reports training residuals, leave-one-node-out residuals,
spatial coverage and, when separately supplied, held-out validation velocity error.

`apps/transport/reeftrace_transport/simulation.py` propagates stochastic particles through
the measured drift field. `apps/estimation/reeftrace_estimation/estimator.py`, `estimate` at
line 318, compares forward simulations from candidate source polygons against the observed
path or retained endpoint. It integrates over an explicit release-age prior. Gates can return
Unknown or Invalid rather than force a source answer.

This is a model-based inverse problem. It is not currently a supervised source classifier.
The USB-camera tracker is deterministic color segmentation/association; it also does not
require training a detection network for the controlled colored-token demo.

## A useful model hierarchy

| Stage | Scientific model | Data needed | Promotion criterion |
| --- | --- | --- | --- |
| Current software demo | Synthetic drift + particle source comparison | Explicit synthetic fixtures | Analytic checks and refusal behavior; no physical claim |
| Current Data Lab | Persistence, last drift, ridge velocity AR(1) | Existing 24 NOAA rows | Reproducibility only; no promotion from this tiny test |
| First physical model | Measured IDW marker-drift field + dispersion | Tank calibration tracks, independent drift runs | Held-out velocity/path error, coverage, and blind-source trials |
| Small hybrid model | Physical/current baseline + regularized residual correction | Multiple independent tracks under supported conditions | Lower grouped held-out error without degrading source reliability |
| Later research | Time-dependent Gaussian process, small recurrent model, or other learned residual | Many independent trajectories, matched forcing and metadata | Independent deployment/time/region testing, calibrated uncertainty |

The hybrid idea has established research precedent: Aksamit, Sapsis and Haller learned a
recurrent correction to a reduced-order drifter model. Their work motivates testing a
physics-plus-residual formulation; it does not establish that a recurrent model is appropriate
for this tiny ReefTrace dataset. [Primary research paper](https://arxiv.org/abs/1909.12895).

## What can be trained before the hardware arrives

1. Keep the current fixed 24-row experiment as an immutable regression fixture. Do not alter
   it until a selected model wins. It already demonstrates training, free-running prediction,
   provenance and errors honestly.
2. Prepare a manifest for a larger **bounded** public trajectory cohort, chosen before looking
   at prediction outcomes. Each record needs deployment/track ID, UTC time, metric or
   geographic coordinates with units, quality, drifter type/drogue status and source provenance.
3. Evaluate position-only persistence and ridge baselines across multiple independent
   trajectories first. Train/validation/test must be selected by complete deployment and time,
   with an exclusion gap around nearby overlapping windows. Dense rows from the same path
   are correlated; they are not thousands of independent examples.
4. Add matched current, wind or wave forcing only after inspecting availability, publication
   timing, depth and definitions. The 1987 fixture is not presently paired with such forcing.
   A historical reanalysis evaluation must be called a hindcast; it does not prove the same
   information would have been available in real time.
5. Compare a regularized residual model to the same physical baseline on identical starts,
   horizons, forcing and numerical settings. Keep the unchanged physical model as a fallback
   when inputs are outside measured support or a correction has no demonstrated benefit.

Potential public cohorts are **researched, not downloaded by this audit**:

- [NOAA GDP](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php): selectable hourly trajectories
  with metadata. Drogued instruments respond primarily at about 15 m; use metadata and a
  suitable forcing depth instead of treating every GPS float as surface plastic.
  [NOAA explanation of drogue depth and loss](https://www.aoml.noaa.gov/proj/global-drifter-program/).
- [GLAD five-minute trajectory release](https://data.griidc.org/data/R1.x134.073%3A0032): 297
  near-surface CODE drifters, plus a companion set of ten flat drifters. The release is
  interpolated, contains deployment clusters and split abducted/re-released tracks, and is
  around 543 MB. Nearby triplets need grouping; processing and licence should be reviewed
  before retrieval. These are drifter trajectories, not litter-source labels.
- [Copernicus current-product quality documentation](https://documentation.marine.copernicus.eu/QUID/CMEMS-GLO-QUID-001-024.pdf):
  an example of trajectory-based current validation. Its SMOC `utotal` includes current,
  Stokes and tidal components; adding the same components again would double-count them.
  No authenticated Copernicus retrieval or field-matched hybrid fit has been completed here.

Underwater image datasets answer a different question: **is litter visible?** They do not
contain a verified release source or calibrate our overhead tank drift. They should not be
substituted for transport or source-validation data.

## The hybrid equations and what their symbols mean

For a future physical-field-plus-learning model, a useful hypothesis is

\[
dX_t = [u_{base}(X_t,t)+f_\theta(\phi_t)]dt+\sqrt{2D}\,dW_t.
\]

`u_base` is the declared transport baseline, `f_theta` a learned velocity discrepancy, and `D`
a nonnegative effective dispersion coefficient. Features `phi_t` must be available at the
prediction time: position, previous motion, properly aligned forcing, token class and known
configuration. Exact source labels, future positions and hidden release times are excluded.
In the tank, the existing measured marker-drift baseline already includes that token's drag,
immersion and any present air flow. Adding independent drag/wind terms without separating
their contributions can double-count motion.

A small residual target is

\[
y_i=\frac{x_{i+1}-x_i}{\Delta t_i}-u_{base}(x_i,t_i),\qquad
\hat\theta=\arg\min_\theta\sum_i\|y_i-f_\theta(\phi_i)\|^2
+\lambda\|\theta\|^2.
\]

Use ridge/low-order features first, trained only on the training partition. Free-run the
combined model on validation trajectories: a small one-step velocity error can accumulate
into a poor multi-step path. Compare to no correction; do not accept a correction solely
because its training loss is lower. Additional nonlinear complexity is justified by independent
validation, not by the word “AI.”

The existing constant-diffusivity model has increments

\[
\Delta X=(u+b)\Delta t+\sqrt{2D\Delta t}\,\xi,
\quad\xi\sim N(0,I_2),\quad
\operatorname{Var}(\Delta X_x)=\operatorname{Var}(\Delta X_y)=2D\Delta t.
\]

Repeated releases can estimate drift bias and dispersion from residual increments, but
camera noise, tracking mistakes, temporal correlation and changing flow also inflate those
residuals. For independent position noise with per-coordinate variance `sigma_z^2`, even a
noise-only difference has per-coordinate variance `2*sigma_z^2`. Ignoring that term overstates
dispersion. Estimate camera repeatability separately, use real elapsed time, and fit/validate
drift and dispersion on development runs. `D` is an effective model parameter, not a measured
molecular diffusion constant.

For ocean plastic, windage, wave-driven Stokes drift, settling and biofouling can matter.
Their inclusion requires the corresponding forcing and particle properties; ordinary buoy
positions do not identify every coefficient. [PlasticParcels physical-kernel documentation](https://plastic.oceanparcels.org/en/latest/physicskernels.html)
and [OpenDrift model selection](https://opendrift.github.io/choosing_a_model.html) show how
different processes and object classes are separated. Current ReefTrace does not implement
that full three-dimensional ocean physics.

Forward simulations conditioned on observations are a defensible route to source search.
They do not require naively reversing a stochastic path, particularly through irreversible
retention. This is established prior art, such as [BAKTRAK](https://arxiv.org/abs/1111.0756).
If two sources produce the same observed evidence, no learned model can recover unique
history from that evidence alone. More upstream observations or additional independent
measurements are needed; Unknown is the appropriate answer when they are unavailable.

## Error metrics: lower is better, but compare the same question

For held-out positions with equal time spacing, define metric position error
`e_h = distance(predicted_position_h, observed_position_h)`:

\[
\mathrm{ADE}=\frac1H\sum_{h=1}^{H}e_h,\quad
\mathrm{FDE}=e_H,\quad
\mathrm{RMSE}_{position}=\sqrt{\frac1H\sum_{h=1}^{H}e_h^2}.
\]

All are lower-is-better distances. For ocean tracks the current code uses spherical
great-circle metres; tank trials use centimetres. A tank centimetre error cannot be compared
numerically to an ocean metre error as if they were the same task. RMSE penalizes large misses
more heavily than ADE. Report horizons individually plus the aggregate; for irregular sampling
use a declared weighting/resampling policy instead of silently treating every row equally.

Velocity validation uses

\[
\mathrm{RMSE}_{velocity}=\sqrt{\frac1N\sum_i\|\hat v_i-v_i\|_2^2},
\]

in cm/s for the tank or m/s for ocean data. This vector RMSE differs from averaging separate
component RMSEs. Show support coverage alongside error; a model that only predicts easy
locations is not necessarily better.

Source evaluation needs **different metrics**: fraction ranked, accuracy among ranked cases,
wrong-ranking rate among all valid cases, Unknown rate, Invalid rate, and results by source
and observation mode. Always-Unknown is not a successful source estimator. The relative
support bars are conditional comparison scores, not calibrated source probabilities, so log
loss/Brier scores must not be applied as if calibration were already established.

For uncertainty, report actual held-out region coverage **and region size/sharpness**. An
enormous region covers everything but helps little. The current training-error radii use only
5–10 overlapping historical fits per horizon and explicitly are not 90% confidence regions.
Dependence-aware calibration needs more independent data and explicit assumptions; ordinary
exchangeable split-conformal guarantees do not automatically apply to correlated time series.
[Oliveira et al., JMLR 2024](https://jmlr.org/papers/v25/23-1553.html).

## Physical commissioning and ground truth once hardware arrives

Keep three separate datasets: (1) unlabeled drift-calibration runs to fit the field,
(2) labeled development releases to choose residual bands/dispersion/gates,
(3) untouched final known-source releases. Freeze code, profile and thresholds before final
evaluation. Do not split adjacent frames from one run across these partitions.

A practical pilot is 10 development releases per inlet and then 10 new blind releases per
inlet for A/B/C, plus deliberately ambiguous, unsupported, stale-calibration and manual-placement
controls. This is a suggested feasibility experiment, not a sample size that establishes field
reliability. If time permits fewer trials, report exact denominators and wider uncertainty rather
than invent a percentage. Repeat with camera and flow conditions that represent intended use.

Record `trial_id`, partition, configuration/profile hash, token class, calibration hash,
flow run IDs, actual frame timestamps and measured coordinates, observation mode, model
output, runtime and an **evaluation-only** source/release label. The person showing observations
to the estimator must conceal the initial release region and not pass labels to Chalk. Inlet
labels can be revealed afterward to the scoring script. Flow changes invalidate previously
fitted flow; do not mix pump positions or water levels without modeling configuration.

Source reasoning should be tested in at least two modes: a moving history and an endpoint
first observed already retained. Endpoint-only trials can be fundamentally ambiguous, so a
legitimate demo should show the system recognizing that limitation.

## What the language model is and is not being trained to do

No LLM fine-tuning is required. Chalk provides access to a pretrained model; ReefTrace supplies
bounded tools and the actual observation/evidence/profile identifiers. The model may retrieve
reports, ask for supported sensitivity checks and explain assumptions. It must not fabricate
better scores, infer the hidden release label, claim physical validation from a synthetic run,
or change transport settings until a preferred source wins.

Evaluate that agent separately from transport: evidence citations, correct interpretation of
Unknown/Invalid, distinction between relative support and probability, retention limitations,
and consistency with numeric reports. A correct sounding explanation is not an accuracy test
of the underlying source estimate.

## Evaluation policy to implement next

Split first, then fit transformations and models using only training data. Choose settings on
development/validation data; open the final test once. Group by independent deployment/run and
keep chronological forecast origins. Scikit-learn's primary documentation explains both
[preprocessing leakage](https://scikit-learn.org/stable/common_pitfalls) and
[time/group-aware validation](https://scikit-learn.org/stable/modules/cross_validation.html).

For comparisons across many tracks, compute paired errors on the same origins. Aggregate
per deployment before reporting confidence intervals; if bootstrapping, resample independent
deployment/experiment groups rather than adjacent frames. Report which regimes improve and
which get worse. Choose an explicit target (for example 1–6-hour ADE or blind-source reliability)
before optimization. A lower error on the already inspected 1987 day is not a new result.

The immediate software objective is a reproducible, inspectable evidence pipeline. The next
scientific objective is independent motion and source validation. Increasing model complexity
comes after those measurements identify an error that learning can actually reduce.
