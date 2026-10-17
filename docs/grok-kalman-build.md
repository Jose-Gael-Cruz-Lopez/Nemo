# Tideward — Grok-assisted motion study

## Build record

This work continues the existing [Grok project and conversation](https://grok.com/project/709fdaeb-06db-41bd-843b-81f567b993da?tab=conversations&chat=139b9a9d-215a-47f0-9f1f-81db9103e724).
The public repository supplied to Grok is
<https://github.com/Jose-Gael-Cruz-Lopez/reeftrace>, starting from
`1a10cee07e4af8d515c7c66d143ee6da3be019cb`. No credentials, private camera
recordings, phone handles or evaluator release answers were supplied.

Grok is being used for algorithm proposals, implementation drafts and adversarial
review. Local code review and automated tests determine what is accepted. Grok's
web conversation did not execute the repository, commit files or establish model
accuracy. The implementation is a reviewed adaptation of its proposal.

1. A detailed prompt supplied the existing four-drifter results, the failed pooled
   transfer result, acquisition failures, data roles, actual units and tank limits.
   It requested three alternative mechanisms and an exact bounded NumPy Kalman
   implementation, with a fixed noise assumption before the first new score.
2. Grok compared irregular-time Kalman state estimation, spatial Gaussian-process
   drift and HF-radar advection with a learned residual. It correctly identified
   missing spatial tank coverage and missing matched current forcing for the latter
   two. It did not claim those inputs had been acquired.
3. Review caught a dimensionally invalid gain solve and repeated use of the second
   measurement during initialization. Those defects were returned to the same Grok
   conversation. Its corrected prose described a correlated two-position state at
   the second timestamp; its replacement code still transposed the solve's right
   hand side incorrectly. The local implementation corrects that remaining error.
4. Local numerical and leakage tests check the implementation, rather than relying
   on Grok's assurances. Every forecast must exist before held-out coordinates are
   read. The old benchmark algorithms and pinned reports are preserved.
5. The actual local implementation was returned to Grok for adversarial review.
   It found no remaining must-fix numerical defect under the declared contracts
   and highlighted the untested first-interval and IID-observation assumptions.
6. Actual locally computed results were returned to the same conversation. Review
   corrected Grok's claim that every Kalman position metric lost to last-drift:
   mean error was worse, but sixth-hour error was lower. Review also rejected
   applying an hourly ridge model or 100 m noise assumption to irregular camera
   frames in a centimetre-scale tank. The historical study remains unchanged.

## Actual first result

The [frozen study](../data/public/noaa-fixed-kalman-diagnostic-v1/README.md)
retains 120/120 acquired scores, 24 distinct observed intervals and 60 unfilled
model-hour slots from the original six-group acquisition target.

| Model | Mean position error / ADE, m | Sixth-hour error / FDE, m |
| --- | ---: | ---: |
| Stationary | 2911.30 | 4942.34 |
| Last drift | 1579.85 | 3323.65 |
| Mean drift | 1846.71 | 2883.49 |
| Own-prefix ridge | 729.37 | 1202.95 |
| Fixed Kalman | 1600.61 | 3231.05 |

Kalman did not beat ridge. It is retained as a transparent negative development
result and state-estimation comparison. Nominal 90% observation-ellipse hits were
6/6, 6/6, 6/6 and 1/6 by drifter; they do not establish calibration. Data Lab loads
the verified report explicitly and shows per-drifter forecasts, raw/filtered
anchors, score definitions and missing acquisition slots. Its route is
`GET /api/v1/research/kalman-diagnostic`; it does not contact any provider or alter
source/prevention evidence.

## What the model adds

The state is position and velocity in east/north metres and metres per second.
Each transition uses the actual elapsed seconds, rather than treating all webcam
frames as equally spaced. Prefix observations update the state; future forecasts
receive no position corrections. Prediction begins at the filtered final prefix
state, which is explicitly different from the last raw observation.

The new diagnostic freezes position standard deviation at **100 m** and continuous
white-acceleration spectral density at **1e-6 m²/s³**. Those are arbitrary declared
NOAA-study assumptions, not measured sensor noise or fitted hyperparameters.
They must not be copied into the centimetre-scale tank as calibrated settings.
The initialization assumes independent isotropic position errors and constant
velocity during the first interval. NOAA's interpolated product does not establish
those assumptions.

The model's covariance is uncalibrated spread. Comparing a noisy observed position
against an ellipse uses predicted position covariance plus the declared observation
variance. Per-drifter hit counts are descriptive; six dependent hours are not six
independent calibration experiments. Nothing changes source confidence, the trial
ledger or interception-layout selection automatically.

The comparison uses the **four already-reviewed buoy-days**, five models and six
horizons: 120 model/horizon attempts on only 24 distinct observed intervals. Two
of the original six acquisition targets remain missing. It is a post-hoc diagnostic,
not unseen evaluation, plastic-source validation or evidence of coral impact.
Failures remain visible and prevent a common aggregate from hiding missing scores.

## Next mechanisms and their evidence gates

| Mechanism | Useful question | Required evidence before implementation |
| --- | --- | --- |
| Irregular-time state estimation | Does smoothing the training state improve a free-running path under a declared motion model? | Existing positions suffice for a historical diagnostic. Camera deployment needs actual timestamps and independently measured development noise. |
| Spatial GP token drift | Where does a spatial drift estimate need more observations, and does it improve complete held-out paths? | Dense, disjoint development recordings per tank layout; predeclared kernel, length scale, noise, support mask and complete-run validation. |
| Observed currents plus learned residual | Does contemporaneous forcing improve motion predictions on genuinely new physical drifters? | Matched UTC/depth/coverage/QC current fields, physical-ID alias mapping, availability timestamps and an untouched whole-drifter holdout. |

The immediate tank value is a better diagnosis of missing measurements. A lower
historical buoy error alone does not establish a better interception decision.
Physical outcomes require new releases under the frozen layouts and protocol.

Primary references: [OpenCV Kalman operations](https://docs.opencv.org/4.13.0/dd/d6a/classcv_1_1KalmanFilter.html),
[FilterPy continuous-noise discretization](https://filterpy.readthedocs.io/en/latest/_modules/filterpy/common/discretization.html),
[NOAA hourly GDP product](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php),
[NOAA product paper](https://www.aoml.noaa.gov/phod/gdp/papers/Elipot_et_al-2016.pdf),
[IOOS HF-radar observations and applications](https://ioos.noaa.gov/project/hf-radar/).

## Sponsor capability boundaries

The supplied SpaceXAI challenge image requires building with Cursor and using Grok
Imagine or Voice API; Grok Bot planning/collaboration earns bonus consideration.
This conversation documents actual planning and review usage. It does not replace
the required live API use or prove Cursor development. The existing xAI speech
adapter is implemented and tested with mocks, but no funded live xAI key has been
commissioned. Confirm the organizer's interpretation of the specific voice API
before claiming eligibility. No billing is enabled by this study.

The user's confirmed automation preference is **only GitHub checks on each
push**. The existing CI workflow runs on every push and pull request, without a
scheduled trigger. Grok-assisted planning and code review continue when requested;
repository changes still need local review, isolated tests and an authenticated
push.

The daily research automation created before the cadence answer arrived has been
**paused**. The account's [Grok Automations page](https://grok.com/automations)
shows **Tideward — daily ML and physics research**, **Paused**; this state was
verified after reloading the page on 17 October 2026. Its retained 9:00 AM schedule
is inactive. The UI showed zero runs. No scheduled Grok research, autonomous
merges, messages, camera starts or physical actions are enabled by this study.
