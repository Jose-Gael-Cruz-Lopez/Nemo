# ReefTrace transport and source inference

This is a controlled **two-dimensional floating-token tank model**, in centimetres and seconds.
It is not an ocean circulation model, a water-quality measurement, a geographic-polluter detector,
or a claim of validated environmental benefit. The included demo is visibly `SYNTHETIC`.
`physical_validation: false` in a numerical report means that a software result alone does not
certify a physical experiment. Physical evaluation belongs in a separate trial record.

## Public software contracts

```python
from apps.transport.reeftrace_transport import fit_flow, FlowField, simulate
from apps.estimation.reeftrace_estimation import estimate

flow = fit_flow(samples, bounds, cell_size_cm=5.0, coverage_radius_cm=10.0,
                neighbors=8, power=2.0, validation_samples=None,
                data_origin="MEASURED_TANK")
report = estimate(profile, observation, seed=7)
```

`fit_flow` returns a JSON-serializable field or raises `ValueError` for unsupported inputs.
Each sample contains `x_cm, y_cm, vx_cm_s, vy_cm_s`. These are actual measured marker drift
velocities: for a correctly associated pair separated by real elapsed time,
`v = (p1 - p0)/(t1-t0)`, at the segment midpoint. Exclude inferred/interpolated points, camera
gaps, different token classes, and response-disturbed frames before fitting. Repeated adjacent
segments share error and are not independent validation samples.

Bounds are `{x_min_cm, x_max_cm, y_min_cm, y_max_cm}`. The field document includes `kind: idw`,
measured node positions and velocities, a `coverage_radius_cm`, units and diagnostics. Median
drift vectors and coordinates are aggregated per spatial cell; inverse-distance weighting
interpolates at most eight nearby nodes by default. The field remains a marker-drift fit,
including the marker's drag/immersion, rather than a direct Eulerian fluid-velocity measurement.
No incompressibility, turbulence spectrum or three-dimensional obstacle physics is inferred.

Diagnostics distinguish training residual RMSE, leave-one-node-out RMSE, and optional
**separate supplied validation-sample** RMSE, in cm/s. Leave-one-out diagnostics are not untouched
physical validation. The 21×21 support-grid fraction is a spatial diagnostic. Every query also
returns a support flag: outside the tank or farther than the stated radius from all measured
nodes is unsupported. Numerical extrapolation is retained only to expose coverage limitations,
not to treat an unmeasured candidate pathway as evidence against that source.

Profile shape (see `data/sample_runs/synthetic_profile.json` for a complete runnable example):

```json
{
  "id": "profile-id", "calibration_id": "cal-id", "valid": true,
  "data_origin": "MEASURED_TANK", "token_class": "standard-float",
  "bounds": {"x_min_cm":0,"x_max_cm":40,"y_min_cm":0,"y_max_cm":30},
  "flow": "replace with the actual fit_flow object",
  "sources": [{"id":"A","polygon_cm":[[0,1],[1,1],[1,2],[0,2]],"prior":0.333333}],
  "traps": [{"id":"T","polygon_cm":[[25,0],[27,0],[27,30],[25,30]],
             "retention":"absorbing","validated":true}],
  "transport": {"particles_per_source":500,"dt_s":0.1,"max_age_s":60,
    "diffusivity_cm2_s":0.05,"drift_bias_cm_s":[0,0],
    "age_prior":{"min_s":0,"max_s":30,"count":16}},
  "gates": {"position_sigma_cm":0.7,"model_error_cm":0.3,
    "correlation_time_s":0.8,"min_absolute_fit":0.02,"min_margin":0.2,
    "min_likelihood_margin":0.1,"min_observation_coverage":1.0,"min_path_coverage":0.9}
}
```

The example source list above is abbreviated; the implementation compares **2–8** unique
candidate sources. Each polygon is a simple positive-area polygon inside the tank; convex and
concave source polygons are supported through uniform-area rejection sampling. Self-intersecting
or degenerate polygons are rejected. Supply only water-surface retention polygons that genuinely
contact the floating token. A submerged decorative coral footprint is not a surface trap.

Observation shape:

```json
{
  "case_id":"case-id","calibration_id":"cal-id","token_class":"standard-float",
  "association_valid":true,"stale":false,
  "points":[{"t_s":0,"x_cm":8,"y_cm":15,"quality":1,"observed":true},
            {"t_s":1,"x_cm":9,"y_cm":15,"quality":1,"observed":true},
            {"t_s":2,"x_cm":10,"y_cm":15,"quality":1,"observed":true}],
  "evidence_frame_ids":["frame-1","frame-2","frame-3"]
}
```

For an object **first observed already retained**, omit earlier `points` and provide
`endpoint: {x_cm, y_cm, retained: true, quality: 1}`. Available measured history takes precedence
over a current-motion mode hint; becoming stationary does not erase a useful previous track.
Only `observed: true` positions are used. Times must increase strictly. At least three points
spanning 0.5 s are required by the default trajectory gate. The implementation subsamples to at
most 20 measured positions and models temporal error correlation. The API must independently
check real camera freshness/configuration validity; the numerical function honors the explicit
`valid`, calibration ID, token-class and `stale` inputs and does not invent them from wall time.

Truth labels, inlet-release video, source-colored labels, and exact hidden release times must
never enter the observation or agent context. A declared release-age prior is allowed context;
it must be chosen before reading final-test labels, not narrowed until the desired source wins.

## One forward engine

For source `s`, particles start uniformly in its polygon and obey the model

\[
dX_t = (u(X_t)+b)dt + \sqrt{2D}\,dW_t.
\]

Here `u` is measured surface drift in cm/s, `b` a declared constant drift discrepancy in cm/s,
and `D >= 0` a **constant** isotropic dispersion coefficient in cm²/s. Euler–Maruyama gives

\[
X_{k+1}=X_k+(u(X_k)+b)\Delta t+\sqrt{2D\Delta t}\,\xi_k,
\quad \xi_k\sim N(0,I_2).
\]

Thus each free diffusion coordinate has variance `2 D t`; the tests check that analytic
invariant. This scaling follows the standard Euler–Maruyama construction described by
[Higham (2001), SIAM Review](https://epubs.siam.org/doi/10.1137/S0036144500378302).
Away from boundaries it corresponds to
`∂p/∂t = -∇·[(u+b)p] + D ∇²p` for constant `D`. Spatially variable diffusivity would require a
different drift/interpretation treatment and is not supported by this API.

The outer rectangle reflects each proposed displacement at wall intersections. This is a
finite-step reflecting-diffusion approximation, not fluid-wall hydrodynamics or persistent
billiard momentum. Trap entry is found by **segment–polygon intersection**, preventing a particle
from jumping across a thin trap merely because its step endpoint is outside. Reflection paths
are subdivided at wall collisions and checked for subsequent trap intersections. Once trapped,
a particle stays fixed. Escape, resuspension, sinking and submerged collisions are not modeled.
An absorbing trap is only physically justified after retention tests support it over the stated
trial duration; unvalidated traps revoke ranking.

The step is halved until `v_max dt + 3 sqrt(2Ddt)` resolves half the narrowest rectangle/trap
bounding-box feature. A three-sigma rule is a conservative **numerical heuristic**, not a bound
on unbounded Gaussian increments or a convergence proof. Explicit intersection/reflection
handling remains necessary. There is a 12-collision-per-step cap, 4,000-step cap, 5,000-particle
cap per source, 3,000,000 particle-time-state cap per source, 180-second horizon cap and eight
source cap. Budget failure is invalid configuration, never evidence favoring a source.
The likelihood calculation additionally caps `number_of_ages × particles × observed_points`
at 1,000,000 per source. Input flow fits are limited to 20,000 marker samples and 512 aggregate
nodes, with 1–64 integer interpolation neighbors and IDW power in (0,8]. Polygons have at most
64 vertices and no zero-length edges. These are prototype resource limits, not physics claims.
Default-scale runtime should be measured on the actual laptop. Compare smaller `dt` and larger
ensembles on development data; seeded reproducibility is not accuracy or Monte Carlo certainty.

The same seed is used across candidate sources as common random numbers, reducing numerical
differences when source polygons are identical. Changing source-list order does not change a
candidate's ensemble. Different actual source geometries and all other model assumptions remain
explicit. No particle path is inverted to claim a reverse-time posterior. Forward-model inverse
search is established prior art, for example [BAKTRAK (Breivik et al.)](https://arxiv.org/abs/1111.0756).

## Explicit source and release-age priors

Each source has a strictly positive prior, normalized and returned in `assumptions`.
Omitted priors default to equal candidate priors and are still recorded. They are not learned
from previous predicted labels. Zero prior is rejected to avoid silently excluding a candidate.
For retained-endpoint inference these are **release-source priors before conditioning on
retention**, because retention probability is already included in the likelihood. Do not feed
priors estimated only among trapped objects without modeling that sampling selection.

Unknown release age is marginalized using either a midpoint quadrature over a declared uniform
interval (`min_s,max_s,count`) or explicit discrete `values_s,weights`. Nonnegative weights are
normalized; zero-weight age entries are discarded. For trajectories, age is measured at the
**first observed point**, not at the end of the track. For endpoints it is age at observation.
The complete age-plus-track horizon must fit `max_age_s`; the function refuses to silently trim
the age prior. Substep positions are linearly interpolated; retention is conservatively asserted
only after a discrete retained time node. Resolve the step further when this approximation matters.

Forward source likelihoods, explicit priors, particle ages and beaching states have a direct
precedent in [Pierard et al. (2022)](https://www.frontiersin.org/journals/marine-science/articles/10.3389/fmars.2022.925437/full).
ReefTrace's tank geometry, IDW field, residual kernel and gates are prototype design choices,
not parameters or validation transferred from that ocean study.

## Trajectory likelihood

For observed positions `z_i`, simulation `X_s,n(a+t_i)` and residuals `r_i`, use

\[
Q_{sna}=\sum_{d=x,y}r_d^T R^{-1}r_d,\qquad
L_s=\sum_a w_a\,\frac1N\sum_n\exp(-Q_{sna}/2).
\]

The time-origin of `t_i` is the first measured point. The covariance used identically for all
sources is

\[
R_{ij}=\frac{\sigma_z^2 e^{-|t_i-t_j|/\tau}}{\sqrt{q_iq_j}}
+\sigma_m^2+\mathbf1_{i=j}\frac{0.05\sigma_z^2}{q_i}.
\]

`q_i` is the declared observation quality in (0,1], `σ_z` the positional bandwidth, `σ_m` a shared
mapping/model-offset bandwidth, and `τ` a temporal correlation scale. This declared residual
model prevents treating every nearby frame as independent and prevents a shared offset from
being averaged away. It is an approximation to be fitted on development residuals, not an
empirically established camera covariance. Velocities derived from these positions are **not**
multiplied in as independent evidence. Gaussian normalization factors common to sources cancel
in the relative comparison; the scores are kernels rather than calibrated data densities.

## Retained endpoint likelihood

For an endpoint `z` with no observed earlier history,

\[
L_s=\sum_a w_a\frac1N\sum_n
\mathbf1\{n\text{ retained at age }a\}
\exp[-\|z-X_{sn}(a)\|^2/(2\sigma^2)].
\]

Here `σ²=σ_z²/q+σ_m²`. A particle that passed the endpoint, or may arrive later, does not count
as retained at observation. The indicator is averaged over **all** particles, not renormalized
over retained particles: rare retention should not look certain by discarding every failure.
The observed endpoint must fall within a configured validated surface trap. This does not prove
the object's actual unobserved journey or distinguish hand placement at the same supported point.

## Stable scores and honest Unknown

Likelihood aggregation and prior normalization use `logsumexp`:

\[
S_s=\exp[\log L_s+\log\pi_s-\operatorname{LSE}_j(\log L_j+\log\pi_j)].
\]

The output explicitly calls these `relative_support_not_probability`. All-zero retained support
returns zero scores rather than fabricating a uniform posterior. Extremely small finite
likelihoods can still be compared stably, while the absolute-fit gate rejects their poor fit.
No NaN or infinity is serialized; nonfinite log-likelihoods are represented as `null` diagnostics.

`absolute_fit` is `exp(log(L_leader)/m)` for a trajectory of `m` selected positions, and
`exp(log(L_leader))` for an endpoint, evaluated for the candidate leading after priors.
`best_absolute_fit` separately reports the maximum across candidates. A leading candidate
must pass its own absolute-fit gate; an extreme prior cannot borrow another candidate's good fit.
This length-normalized mean kernel is in [0,1] and needs
mode-specific development assessment. It is **not a probability, p-value or physical calibration**.
`best_path_rmse_cm` is an additional diagnostic, not substituted for ensemble support.

Ranking requires all gates to pass:

- Correct declared profile/calibration/token class; finite in-domain data and positive numerical settings.
- Sufficient actual observations, timing and association quality.
- Observation support and minimum mean simulated-path coverage across **every** candidate source.
  Missing spatial coverage is an unresolved model limitation, never a low source likelihood.
- Adequate absolute fit; the best of three bad fits remains Unknown.
- Adequate first–second conditional support margin **and** likelihood-only margin. A strong prior
  alone cannot make identical observational source distributions identifiable.
- Supported and validated retention where used.
- Stability under supplied, predeclared `sensitivity_variants`.

Profile `sensitivity_variants` is a list of `{id, transport:{...}}`, maximum eight. Overrides are
limited to diffusivity, drift bias, age prior and time step. Every alternative report is returned;
a changed leader or ranked/unknown/invalid conclusion revokes ranking with
`ASSUMPTION_SENSITIVE`. The agent may select only a registered preset; it must not provide
arbitrary field values or choose only its preferred result. Absence of a sensitivity set is
reported by an empty result list, not proof of assumption robustness. API-side preset services
must preserve all results and apply the same policy if they run variants outside `estimate`.

Important reason codes are `CALIBRATION_INVALID`, `UNSUPPORTED_TOKEN_CLASS`,
`INSUFFICIENT_OBSERVATION`, `LOW_OBSERVATION_QUALITY`, `MODEL_MISMATCH`,
`AMBIGUOUS_SOURCES`, `RETENTION_UNSUPPORTED`, `RETENTION_UNVALIDATED`,
`ASSUMPTION_SENSITIVE`, and `INVALID_INPUT`. `ranked_source` is populated only for `status:ranked`;
`leading_source` is a diagnostic conditional leader even when the scientific conclusion is Unknown.

No observation can distinguish two hidden histories that produce identical available evidence.
Merged pathways or a shared accumulation pocket may erase inlet information. A manually placed
token at the exact same supported endpoint can be observationally identical to a genuine arrival;
there is no universal “detect manual placement” gate. An unsupported point or incompatible
trajectory may be rejected, but conditional support among A/B/C never proves that the true source
was one of A/B/C. These are identifiability constraints, not problems an LLM or larger particle
count automatically solves.

## Reproduction and validation separation

```sh
.venv/bin/python scripts/generate_demo.py
.venv/bin/python -m pytest tests/unit/test_transport.py tests/unit/test_estimation.py -q
```

The generator uses fixed seed 7. `synthetic_profile.json`, `synthetic_flow_samples.json` and
`synthetic_observations.json` are computational demo inputs. `evaluation_truth.json` holds source
and release-age labels separately and must not be exposed to inference tools or agent context.
The converging synthetic drift produces an informative upstream trajectory, an ambiguous
retained endpoint and an invalid stale-calibration case. Trap `validated:true` in this fixture
means validated **inside the synthetic model only**, explicitly labeled in that trap's metadata.
No real camera, tank flow, retention mechanism or environmental impact was validated by generating it.

Unit tests check analytic advection, diffusion variance `2Dt`, confinement, thin-trap segment
capture, persistence of retention, reproducible seeding, coverage/holdout error, absolute mismatch,
identical-source ambiguity even under unequal priors, release-age limits, retained-at-observation
gating, old calibration, malformed settings, and sensitivity revocation. These computational checks
do not replace real labeled trials. Fit flow on unlabeled markers, tune bandwidths/gates/priors
on development releases, then freeze hashes before independent final trials. Hide the inlet
release segment, report results by inlet and evidence mode, and publish **coverage plus accuracy
among ranked cases**, wrong rankings and abstentions separately. “Correct OR Unknown” accuracy
would reward an estimator that always abstains and is not an acceptable success measure.
