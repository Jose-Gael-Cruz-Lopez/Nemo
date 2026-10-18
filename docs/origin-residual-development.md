# Nemo: current result and historical development design

**Current checkpoint — 17 October 2026:** the separately identified exploratory
candidate has been scored once after its exact methods were committed at
`744832594c6327459d3003291e08685d9d483bb0`. All **48/48 planned cells** scored on
**12 already-viewed processed GDP targets**. Equal-ID macro ADE/FDE are
**1,030.0495 m / 2,355.9582 m**, descriptively lower than the other three candidates
in this sample and in both groups' aggregates. No learned-model, unseen-test,
causal, tank/reef or promotion claim follows.

The **twelfth actual Grok review** now discusses that saved result; the archive
contains **12 rounds / 24 captures**. A separate local numerical replay matched
all four forecasts and scores exactly, with every saved artifact byte unchanged.
This is not a second first score or independent external attestation. The default
reader still correctly returns `numeric_replay_verified:false`: its own scope is
saved-byte/lineage verification rather than numerical execution.

The [dated local software checkpoint](research-evidence/nemo-origin-residual-20261017-local-checkpoint.json)
records **1,898 Python tests, 233 frontend tests, Ruff/ESLint and production build
passed**, plus **174 guarded HTTP passes / zero failures / six expected blocked
scopes**. The **49 new endpoint tests / 98 adjacent API regressions** use mocked or
disabled providers; they do not establish a live Chalk response and are not added
to the full-suite count. Hosted exact-commit, browser and physical validation
remain separate. Read the [result, tables, clocks and identities](origin-residual-results.md).

**The complete development text below is retained as a pre-score historical
capture.** Its “under review/no result scored” statements describe that earlier
checkpoint. Nemo is the current product name; historical Tideward/ReefTrace
names and exact captures remain unchanged. No new cohort has been frozen,
selected or acquired, and the one first-score directory must not be overwritten.

---

# Current plus initial observed motion: exploratory development

Checkpoint: 17 October 2026. **Implementation under review; no result for this
candidate has been scored.** The existing matched-current v2 first score remains
unchanged. This is a post-outcome development idea prompted by an already-viewed
two-group comparison, not a predeclared independent performance test.

## What this adds

The current-only model follows a supplied ocean velocity field. The proposed
diagnostic also uses the object's last observed motion. It asks whether keeping
that initial discrepancy while following later changes in the field produces a
useful descriptive comparison. This is a physics-based kinematic candidate with
no learned coefficient, fitted decay time or neural network.

With the final two context fixes exactly 3,600 seconds apart, define

\[
v_{last}=-\operatorname{Log}_{X_0}(X_{previous})/3600,
\qquad r_0=v_{last}-u(X_0,t_0).
\]

The log map is the existing last-drift model's origin-centred, mean-radius-sphere
map. Both velocity components are east/north metres per second. The candidate is

\[
u_{corrected}(X,t)=u(X,t)+r_0.
\]

The two components of `r0` are constant in the local east/north convention at each
sampled position. They are not a single vector parallel-transported over the globe.
The unchanged WGS84 integrator converts those velocities to geographic derivatives:

\[
\dot\phi_{degrees}=(v+r_{north})/m_{latitude}(\phi),\qquad
\dot\lambda_{degrees}=(u+r_{east})/m_{longitude}(\phi).
\]

RK4 samples the corrected field at the beginning, two intermediate stages and end
of each supported step. Splitting at forcing-time knots avoids crossing a temporal
interpolation break inside a step. RK4 still approximates the interpolated field;
it does not make stages, integrals, the underlying currents or the physical path
exact.

## Scientific limits and implementation contract

- The one-hour observed velocity is a processed interval estimate, not measured
  instantaneous water velocity. The residual can combine object response, forcing
  error, sampling and processing discrepancy; a lower error does not identify
  windage or current bias as its cause.
- The original last-drift model uses a mean-sphere log/exp map. The current solver
  uses WGS84 metrics. A constant corrected flow need not globally reproduce the
  last-drift position. A zero residual should reproduce the current-only track.
- A new derived field copies arrays and preserves actual axes, times and masks.
  Original raw data and all frozen source files stay unchanged. Unsupported
  cells remain unsupported. Values are not clipped, filled or extrapolated.
- Existing speed, geographic, time, sample and step budgets remain effective.
  A residual that makes the supported field exceed 10 m/s must fail explicitly.
- The candidate accepts context and forcing only. All four candidates' forecasts
  and failure rows must be saved and read back before numeric target decoding.
  The new diagnostic has 48 planned model/hour cells but still only 12 distinct,
  already-viewed future position estimates. Missing rows stay in the plan.
- A complete primary descriptive comparison requires all 48 cells. Partial
  common-support results must name their denominators. No automatic winner or
  operational model promotion follows from this diagnostic.
- A new metadata-selected and frozen cohort, excluding prior IDs and known
  aliases, is required for subsequent testing. The prior forcing exposure,
  retrospective interpolation and uncertain assimilation independence must remain
  explicit even then.

## Grok contribution and local review

The exact [design prompt](grok-evidence/grok-origin-residual-design-prompt.txt) and
[static response](grok-evidence/grok-origin-residual-design-response.txt) are
preserved. Grok gave a conditional GO, supported keeping the original result
immutable, required failure retention, and corrected its earlier claim of exact
RK4 stages. This is recorded advice, not execution or empirical validation.

One test recommendation needs refinement: integrating a spatially uniform
time-varying east/north velocity does not generally give an exact geographic
position by adding its component integrals to latitude/longitude. WGS84 metres
per degree change with latitude. Use an analytic east-only case at fixed latitude
and an independent high-accuracy geographic ODE reference for turning flow, with
explicit numerical bounds. Do not call the latter an exact physical oracle.

## Primary research references checked

- [OpenDrift model selection](https://opendrift.github.io/choosing_a_model.html)
  distinguishes currents, direct wind response, waves and object-specific models.
  Those components motivate model comparison; their example coefficients are not
  measured parameters for Tideward's tank tokens.
- [OceanParcels kernel reference](https://docs.oceanparcels.org/en/latest/reference/parcels/kernels/index.html)
  separates RK4, adaptive integration and stochastic advection/diffusion. Choosing
  a better integrator does not supply missing physical forcing or validate an
  object's response.
- [NOAA Global Drifter Program](https://www.aoml.noaa.gov/global-drifter-program/)
  describes the hourly QC/interpolated positions and the importance of the drogue
  centred near 15 m. These processed buoy records do not establish surface-plastic,
  tank-token or reef-interception accuracy.

No new API key, xAI API usage, paid billing, Photon message, camera activation or
physical trial is needed to develop this bounded offline diagnostic. It does not
change the app's commissioned evidence or the saved prevention comparison.
