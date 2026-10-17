# ReefTrace: transport physics, learning, and defensible evaluation

Research review: 16 October 2026. This document separates current executable behavior from research recommendations. It does not establish field validation, a new physical law, patent novelty, or an environmental benefit measured in the ocean.

## The practical decision

Keep **tracing as forward-model comparison**: simulate many plausible releases from each declared inlet, compare their resulting paths with actual observations, and retain `Unknown` when the evidence does not distinguish them. The immediate scientific improvement is better independently measured motion and error calibration, followed by stronger held-out evaluation. Training a large neural network is not a prerequisite for this workflow.

The existing software already contains two different kinds of fitting:

1. **Tank motion fitting:** measured token displacement → velocity samples → spatially aggregated inverse-distance interpolation. This learns an empirical token-drift map. It is not a Navier–Stokes solver.
2. **Public-data motion forecasting:** a ridge autoregression fitted to the first 18 positions in a particular NOAA drifter day, then compared with six future positions and two naive baselines. It is an actual small learned model, separate from tank source attribution.

The Chalk LLM is the investigator and evidence interpreter. Its gateway connection does not train either motion model. The LLM should retrieve evidence, run registered numerical tools and explain limitations; source scores must remain reproducible numerical outputs.

## Current implementation map

Paths and line numbers below describe the inspected code at this review, rather than a claim that future changes are already present.

| Component | Current code | What is implemented |
|---|---|---|
| Measured token velocity | `apps/vision/reeftrace_vision/tracking.py:69` | Nonoverlapping finite differences from same-track observed positions with time-gap limits. |
| Drift fit | `apps/transport/reeftrace_transport/flow.py:63` | Median position/velocity in spatial cells; inverse-distance interpolation, support flags, training/leave-node-out/optional separate-validation RMSE. |
| Field query | `apps/transport/reeftrace_transport/flow.py:34` | Nearest-node weighted interpolation in **cm/s**, not an ocean-current query. |
| Transport | `apps/transport/reeftrace_transport/simulation.py:39` | Constant isotropic diffusion; constant optional discrepancy bias; rectangular reflection; absorbing trap intersections; bounded compute budgets. |
| Stochastic step | `apps/transport/reeftrace_transport/simulation.py:87` | Euler–Maruyama advection plus `sqrt(2 D dt)` Gaussian displacement. |
| Release-age uncertainty | `apps/estimation/reeftrace_estimation/estimator.py:61` | Declared discrete or uniform-quadrature age prior; not a hidden known release time. |
| Source scoring | `apps/estimation/reeftrace_estimation/estimator.py:138` | Correlated trajectory residual kernels, or retention-conditioned endpoint kernels averaged over all simulated particles and ages. |
| Unknown gates | `apps/estimation/reeftrace_estimation/estimator.py:284` | Coverage, absolute fit and ambiguity checks; calibration and retention gates are checked earlier. |
| Sensitivity | `apps/estimation/reeftrace_estimation/estimator.py:318` | Predeclared drift/diffusion/age/time-step variants; changed conclusions revoke ranking. |
| Public-data learning | `apps/ocean/reeftrace_ocean/benchmark.py:113` | Chronological-only ridge velocity AR(1), stationary and last-drift baselines; free-run geographic forecasts. |
| Geographic field ingestion | `apps/ocean/reeftrace_ocean/field.py:91` | Bounded local CF NetCDF ingestion with masks and unit/dimension checks. **Not** a geographic transport solver. |

The existing `docs/physics.md` is the full current numerical contract. It should remain the authority for input schemas, runtime limits and exact gates.

## 1. Position, velocity, and acceleration: measure the right quantity

For a token position `x` in centimetres observed at real times `t` in seconds:

\[
\widehat{\mathbf v}_{i+1/2}
=\frac{\mathbf x_{i+1}-\mathbf x_i}{t_{i+1}-t_i}
\quad[\mathrm{cm/s}].
\]

This estimates **the token's velocity**. A floating cap or foam fragment can slip relative to surrounding water because of immersion, shape, air drag, wave effects and contact. Calling this a direct measurement of water velocity would be stronger than the sensor supports. Use the same token class for drift calibration and source trials.

Under the illustrative assumption of independent position errors with per-coordinate variance `σ²`, a two-frame velocity estimate has per-coordinate error variance `2σ²/Δt²`. Decreasing the frame interval amplifies velocity noise. Conversely, a very large interval averages over changing motion. The actual camera has correlated errors, so estimate this tradeoff from independent stationary and moving trials rather than assuming the illustrative formula is the camera's measured covariance.

Do not multiply position likelihood by a velocity likelihood derived from those same positions as if they were independent measurements. That would count evidence twice. The current estimator uses positions with an explicitly declared temporal error model.

## 2. Bernoulli: useful for the pump, insufficient for source tracing

For a steady, incompressible, inviscid region along a streamline:

\[
p+\tfrac12\rho U^2+\rho g z=\mathrm{constant}.
\]

`p` is pressure in Pa, `ρ` density in kg/m³, `U` speed in m/s, `g` gravitational acceleration in m/s² and `z` elevation in m. All terms are energy per volume, equivalently Pa. It relates pressure, speed and elevation; it does not yield the complete unknown vector field throughout a tank from one pump's label. NASA derives this relation from energy conservation under its stated restrictions. [NASA Bernoulli explanation](https://www.grc.nasa.gov/www/k-12/airplane/bern.html).

For real tubing, the useful energy bookkeeping includes pump head and losses:

\[
\frac{p_1}{\rho g}+\frac{\alpha_1\bar U_1^2}{2g}+z_1+h_p
=\frac{p_2}{\rho g}+\frac{\alpha_2\bar U_2^2}{2g}+z_2+h_L.
\]

Every term has units of metres; `h_p` is energy added by the pump, `h_L≥0` is loss, and `α` corrects for the velocity profile. Pump performance, tube friction, bends and outlet conditions affect actual flow. The DOE handbook explicitly discusses extending Bernoulli to include pump work and head losses. [DOE fluid-flow handbook](https://www.energy.gov/documents/doe-hdbk-1012-92vol3).

For measured volume `V` collected in time `T`, `Q=V/T` in m³/s. For a filled tube, `\bar U=Q/A`, with tube area `A` in m². This is **cross-section mean speed in that tube**, not the speed everywhere around the coral. [USGS discharge measurement](https://www.usgs.gov/water-science-school/science/how-streamflow-measured?qt-science_center_objects=0).

**Recommendation:** record an actual volume/time flow check when hardware returns, then measure token drift across the tank. Do not add a fictitious “Bernoulli AI layer” or infer nozzle/tank velocities solely from a nominal gallons-per-hour rating. Bernoulli is established physics; the product can apply it without claiming to invent it.

## 3. Drag, response time, and the Reynolds-number check

An engineering representation of water drag on an object is

\[
\mathbf F_{D,w}=\tfrac12\rho_w C_{D,w}A_w
\lVert\mathbf u_w-\mathbf v\rVert(\mathbf u_w-\mathbf v).
\]

Force is N; `ρ_w` is kg/m³, `A_w` is a declared projected area in m², and the slip velocity `u_w−v` is m/s. `C_D` is dimensionless and depends on shape, orientation and regime; it is not a universal constant for all plastic. An analogous air-drag term can use emerged area and relative air velocity. NASA's drag treatment explains the coefficient/reference-area convention; applying the dimensional relation to water is our engineering interpretation. [NASA drag equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/drag-equation/).

Check the **particle** Reynolds number with slip speed and particle length:

\[
Re_p=\frac{\rho_w U_{\rm slip}d}{\mu_w}
=\frac{U_{\rm slip}d}{\nu_w}.
\]

This is distinct from a tank Reynolds number based on tank length and bulk flow. Here `μ` is dynamic viscosity in Pa·s and `ν=μ/ρ` is m²/s. Reynolds number compares inertia with viscous effects; the chosen speed and length must be documented. [NASA Reynolds number](https://www.grc.nasa.gov/WWW/K-12/airplane/reynolds.html).

**Illustrative calculation, not a measurement of our tank:** if `U_slip=0.05 m/s`, `d=0.02 m` and `ν=10⁻⁶ m²/s`, then `Re_p≈1000`. A centimetre-size token is not automatically in the `Re_p≪1` regime merely because the tank looks slow. Actual slip requires both token and water measurements; the token's total speed alone is not slip.

For a fully immersed isolated sphere in creeping flow, Stokes drag is

\[
\mathbf F_D=6\pi\mu a(\mathbf u-\mathbf v).
\]

Combining that drag with the deliberately simplified particle-only balance `m_p dv/dt=F_D` yields the diagnostic relaxation time

\[
\tau_p=\frac{m_p}{6\pi\mu a}
=\frac{\rho_p d^2}{18\mu},\qquad
St=\tau_p/T_{\rm flow}.
\]

`τ_p` is seconds. This derivation neglects added mass, history, lift, air drag and surface effects. It cannot be transferred unchanged to partially submerged irregular foam or caps. MIT's notes derive the low-Re sphere drag. [MIT low-Re lecture](https://ocw.mit.edu/courses/18-354j-nonlinear-dynamics-ii-continuum-systems-spring-2015/60add870d6e8194319e9e22943d6298d_MIT18_354JS15_Ch14.pdf).

Surface-floating dynamics are more complex: Beron-Vera and colleagues construct an air–sea Maxey–Riley framework with explicit assumptions about size, geometry, wind and fluid motion. Its existence is evidence against presenting a universal one-line drag coefficient as a solved plastic-transport model. [Primary paper](https://arxiv.org/abs/1906.01080).

**Recommendation:** the current token-class-specific empirical drift map is a practical choice. A future fitted response model `dv/dt=(u_target−v)/τ` is an approximation requiring independent data, parameter identifiability and a demonstrated held-out improvement. It is not currently implemented.

## 4. Advection, diffusion, and what the particle cloud means

The current forward model is

\[
d\mathbf X_t=[\mathbf u_{\rm token}(\mathbf X_t)+\mathbf b]dt
+\sqrt{2D}\,d\mathbf W_t.
\]

In the tank, `X` is cm, `u_token` and the declared discrepancy `b` are cm/s, and `D` is cm²/s. Its numerical step is

\[
\mathbf X_{k+1}=\mathbf X_k+(\mathbf u_{\rm token}+\mathbf b)\Delta t
+\sqrt{2D\Delta t}\,\boldsymbol\xi_k,
\quad\boldsymbol\xi_k\sim\mathcal N(0,I_2).
\]

Away from boundaries, pure diffusion has per-coordinate variance `2Dt` and two-coordinate mean squared radial displacement `4Dt`. The square root of time is essential; using noise proportional to `dt` changes diffusion when the integration step changes. Euler–Maruyama is a standard numerical method, not a newly invented equation. [Higham's primary numerical-method paper](https://epubs.siam.org/doi/10.1137/S0036144500378302).

For constant `D`, the associated density equation is

\[
\partial_t p=-\nabla\!\cdot[(\mathbf u+\mathbf b)p]+D\nabla^2p.
\]

If `D` varies with position, simply replacing the constant in the noise is generally not equivalent to Fickian diffusion. For an isotropic spatial diffusivity and the Itô interpretation, the corresponding drift includes `∇D`. The OceanParcels documentation derives this correction and discusses suitable kernels. The current ReefTrace API correctly restricts itself to constant `D`; anisotropic or spatially varying dispersion is future work. [OceanParcels diffusion documentation](https://docs.oceanparcels.org/en/latest/user_guide/examples/tutorial_diffusion.html).

The ensemble is a collection of alternative modeled histories. It is not hundreds of observed plastic pieces, and spread from `D` does not automatically cover error in pump state, field interpolation, source geometry or release age. Those uncertainties need separate sensitivity or fitted error models. NOAA similarly distinguishes turbulent dispersion from forcing uncertainty. [NOAA uncertainty documentation](https://gnome.orr.noaa.gov/doc/uncertainty.html).

### How to learn dispersion later

For independent development increments, define residual displacement

\[
\mathbf r_i=\Delta\mathbf x_i-\widehat{\mathbf u}(\mathbf x_i)\Delta t_i.
\]

For a fixed common lag `Δt`, ideal isotropic diffusion alone suggests `D≈E||r−E r||²/(4Δt)`. This is a **diagnostic derivation**, not a current ReefTrace fitting function. Camera error adds displacement variance; correlated motion, fitted-field error and walls/traps invalidate the simple identity. Fit using independent free-drift development runs, compare several lags, quantify stationary camera jitter, avoid training-residual optimism, and evaluate complete held-out runs. Never inflate `D` until every source looks plausible merely to reduce an error metric.

An established research path estimates mean drift, gradients and diffusivity from Lagrangian trajectories with explicit stochastic assumptions. It supports investigating parameter learning, rather than assuming residual variance uniquely measures turbulence. [Ying and colleagues' primary diffusion-inference paper](https://arxiv.org/abs/1812.04264).

## 5. Windage and waves: prevent double counting

A future geographically forced model might use

\[
\dot{\mathbf X}=\mathbf u_{\rm current}(\mathbf X,t)
+\alpha\mathbf U_{10}(\mathbf X,t)
+\mathbf u_{\rm Stokes}(\mathbf X,t)
+\mathbf u_{\rm residual}.
\]

All velocities would be m/s; `α` is dimensionless and object/model specific. `U_10` denotes wind at the stated reference height, not any arbitrary room-fan speed. Wave-induced Stokes drift is a mean transport effect and is different from Stokes' low-Re drag law.

Leeway coefficients can be *implicit*, absorbing wave drift and unresolved effects, or *explicit* with a separate wave term. OpenDrift's authors state that its Leeway coefficients already include Stokes drift implicitly, while other model choices represent it explicitly. Adding both without matching the calibration convention can double count waves. [OpenDrift model selection](https://opendrift.github.io/choosing_a_model.html), [Leeway source](https://opendrift.github.io/_modules/opendrift/models/leeway.html).

**Crucial current-code consequence:** ReefTrace fits `u_token` from the actual floating token. Existing room airflow, immersion and pump-induced surface effects are already folded into that measured drift under those conditions. Adding a drag-derived or windage velocity to it again would generally double count motion. Introduce separate forcing terms only after changing the model contract and collecting observations that can identify them.

NOAA's particle tracking documentation supports surface-current, wind and dispersion modeling but emphasizes object-dependent windage. Its defaults for fresh oil must not be transplanted as validated coefficients for our token or reef debris. [NOAA WebGNOME FAQ](https://gnome.orr.noaa.gov/doc/faq.html).

## 6. Why stuck plastic cannot reveal a unique history by itself

For candidate source `s`, a conceptual Bayesian inversion is

\[
P(s\mid z,\mathcal M)
\propto P(z\mid s,\mathcal M)\,P(s\mid\mathcal M),
\]

where `M` contains declared geometry, transport, release-age and candidate assumptions. A forward ensemble estimates how compatible `z` is with each source. Source attribution by Bayesian/Lagrangian modeling already exists in marine-plastic research; unknown age and source-release priors matter. [Pierard et al., 2022](https://www.frontiersin.org/journals/marine-science/articles/10.3389/fmars.2022.925437/full).

ReefTrace's current residual kernels and priors produce **relative support**, explicitly not empirically calibrated source probabilities. If two inlets feed the same pocket and produce indistinguishable available evidence, no LLM, extra particle count or neural network can recover the missing history. Earlier motion observations or another independent sensor can add information; an endpoint alone cannot manufacture it.

Retention is also a selection event. For an object observed stuck at a pocket, the likelihood must include both arrival at that location and being retained by the observation time. The current estimator averages the retention-weighted kernel over **all** particles; conditioning only on the successfully retained subset would discard modeled failures and overstate support.

Naively reversing current vectors does not reverse stochastic dispersion or irreversible state changes. BAKTRAK demonstrates an established alternative: use forward trajectories and select/refine histories compatible with the observation. ReefTrace uses the same broad forward-inverse principle, with a different bounded toy estimator. [BAKTRAK institutional publication and DOI](https://www.ffi.no/publikasjoner/arkiv/baktrak-backtracking-drifting-objects-using-an-iterative-algorithm-with-a-forward-trajectory-model).

## 7. Boundary conditions and tank-to-ocean translation

Current rectangle reflection prevents particles from leaving the modeled tank. It is not a no-slip Navier–Stokes wall solution, a measured wall response or an ocean coastline model. Absorbing polygon traps permanently retain particles once crossed; release, sinking, resuspension, collision dynamics, capillary attraction and three-dimensional coral flow are absent. A submerged decorative coral footprint is not automatically a surface trap.

Use retaining polygons only after real trials support the stated behavior for the specified token and experiment duration. If changing the pump, tank geometry, water depth or token class changes motion, record a new profile rather than silently retaining an old fitted field.

The current tank units cannot consume latitude/longitude: `1 cm=0.01 m`, `1 cm/s=0.01 m/s`, and `1 cm²/s=10⁻⁴ m²/s`, but degrees are angles and require a geographic projection or geodesic integrator. Geographic boundaries, wet/dry masks, timestamps and missing current cells need their own handling. A roughly kilometre-scale current grid cannot resolve centimetre tank motion or automatically resolve reef branches. The geographic field loader is a useful data boundary, not evidence that geographic particle transport exists.

## 8. What to build while hardware waits

1. **Retain the operational software path:** synthetic source cases → deterministic source-report generation → Chalk's tool-backed investigation → sensitivity explanation → explicit Unknown/Invalid cases. Label every synthetic source case as synthetic.
2. **Keep the NOAA experiment separate:** expose fit parameters, training split, free-run forecast and all baselines; never insert guessed release-inlet truth into a drifter dataset.
3. **Prepare independent trial records:** session ID, profile hash, calibration ID, token class, measured positions/times, pump/water-depth settings and evaluator-held source/release-time labels. The LLM and estimator must not read evaluation truth.
4. **Expand external validation deliberately:** many drifters, whole held-out trajectories/time blocks, documented drogue status and matched forcing. Similar timestamps do not establish matched physics, and a 1987 trajectory cannot be paired silently with a modern current product.
5. **Only then fit new physical parameters:** compare a fixed empirical drift baseline with a small residual/response model. Keep added parameters only if held-out motion error and source-decision behavior improve across independent conditions.

For a controlled red token, HSV segmentation is adequate to commission tracing. Underwater detection datasets can support a later detector task but do not supply inlet labels, flow fields or source histories. A neural detector trained now would not resolve the central physical attribution gap.

## 9. Lower error is better: choose the right score

For predicted and observed positions at `H` held-out times, let `e_h=||x̂_h−x_h||`, measured in cm for tank motion or geographic metres for the NOAA experiment:

\[
\mathrm{ADE}=\frac1H\sum_h e_h,\quad
\mathrm{RMSE}=\sqrt{\frac1H\sum_h e_h^2},\quad
\mathrm{FDE}=e_H.
\]

All three are **lower is better**; they answer different questions. RMSE penalizes large misses more strongly. ADE can improve while final error gets worse. Never relabel whichever metric happens to win as the sole success criterion.

For a fixed baseline and the same held-out cases, `skill=1−E_model/E_baseline` is an interpretable comparison when the baseline error is positive: positive skill is improvement, zero is a tie, negative is worse. Show absolute error alongside this ratio. Report per-horizon and per-session results; adjacent frames and overlapping forecast windows are dependent.

Source tracing is a classification/abstention task, not just a displacement task. Report separately:

- **Ranking coverage:** ranked valid trials / eligible valid trials.
- **Accuracy among ranked trials:** correct rankings / ranked trials.
- **Wrong rankings:** a separate count and rate.
- **Unknown and Invalid:** separate counts, with reasons.
- **Sensitivity failures:** conclusions changed by predeclared plausible assumptions.

A model that always says Unknown has no wrong rankings but no demonstrated attribution usefulness. Lower displacement error also need not improve source identification when pathways merge. Conversely, source-support percentages are not error values: a higher normalized bar is stronger relative fit under the model, not a guarantee of truth.

The reproducible current NOAA example illustrates the distinction: learned ADE is about **3,557 m** versus stationary **3,855 m**, while learned FDE is about **7,561 m** versus stationary **6,775 m**. That is a mixed result from one small drifter day, not general superiority. Exact parameters, split, limitations and values are in `docs/research-real-data.md` and the emitted benchmark JSON.

## The strongest defensible claim today

“ReefTrace combines measured motion, a transparent particle-transport model and an LLM investigator to compare declared possible entry points and explain when the evidence cannot distinguish them. The software has a separate reproducible NOAA motion-learning experiment; physical tank validation and real-reef source attribution remain future work.”
