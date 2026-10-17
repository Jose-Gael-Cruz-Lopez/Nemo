# Next data and model study: match the forcing to the observation

Historical proposal checkpoint: 17 October 2026. This note preserves the original
source-availability review and future-study design; it is not itself an executed
experiment. Subsequent work acquired matched NOAA GDP/HYCOM inputs in a separately
frozen [v2 compatibility amendment](matched-current-v2-results.md) and scored
**36/36** planned cells across two buoy groups. Current-only RK4 had larger mean
errors than last observed drift on that small retrospective sample; no model was
promoted. The preserved [v1 attempt](matched-current-results.md) remains **0/36**,
and the earlier six-group NOAA study is unchanged. Issue-time availability and
independence from assimilation remain unverified. The OSCAR, wind/leeway and
learned-residual candidates below remain proposals, not acquired or validated
additions to that comparison.

## Original research rationale

At this proposal's original checkpoint, the next useful empirical comparison was
a current-driven forecast against an independent object's later recorded motion
at the **same place and time**. Adding
a bigger learned model to unrelated currents and buoy positions would not test
that claim. The present PacIOOS forecast and historical GDP studies have different
locations/times; the UI correctly keeps them separate.

## Sources inspected and limits

| Candidate | Verified information | Development decision |
| --- | --- | --- |
| [NASA PO.DAAC OSCAR final v2](https://podaac.jpl.nasa.gov/dataset/OSCAR_L4_OC_FINAL_V2.0) | Satellite-informed, daily, 0.25-degree modeled currents averaged over an assumed upper 30 m; final/interim/NRT products have different latency. The product page links Earthdata-backed download/subsetting. | Candidate for matched historical ocean-scale development, not reef/tank-scale truth. Data access and an exact spatial/time subset must be verified before acquisition is called successful. |
| [NOAA ERDDAP `jplOscar` metadata](https://coastwatch.pfeg.noaa.gov/erddap/info/jplOscar/index.html) | Despite a “1992-present” title, the inspected instance reports only 117 times and actual coverage 2011-12-06 through 2014-09-26. It exposes 1/3-degree fields, an overlapping longitude range and a depth coordinate of 15 m. | Reject the title as proof of modern coverage. Do not silently substitute this older sparse mirror for OSCAR v2 or for the 2026 PacIOOS scenario. |
| [OpenDrift Leeway model](https://opendrift.github.io/autoapi/opendrift/models/leeway/index.html) | An existing object-drift approach; its documentation identifies a search-and-rescue leeway model with object-specific behavior. | Research comparator, not an installed Tideward component or a measured coefficient for our tokens/plastic. |
| [OceanParcels current-and-wind example](https://docs.oceanparcels.org/en/latest/user_guide/examples/tutorial_dt_integrators.html#writing-custom-kernels-with-higher-order-integrators) | Demonstrates adding a relative wind term to current velocity and integrating a custom right-hand side. | Candidate model structure only. The example coefficient is not a validated plastic parameter and must not be copied into a field-accuracy claim. |

OSCAR and PacIOOS are different products, resolutions, depths and processing
systems. A finer plotted line or a smaller RK4 step does not improve a source
product's observation support. A current model may also share upstream data with
an evaluated product; catalogue co-location is not proof of independent truth.

## Required design before a new score

1. Declare the scientific claim and object class. A GDP buoy, a floating tank
   token and flexible plastic do not have identical wind, wave or depth response.
2. Freeze a new cohort and known-identity exclusions before inspecting its future
   outcomes. Retain unresolved physical aliases, inaccessible slots and failed
   downloads in the planned denominator. Already-viewed groups can support only
   clearly labelled development diagnostics.
3. Freeze matched forcing product/version, geography, depth, valid times,
   interpolation, masks and as-of rules. Obtain and checksum only the bounded
   subset; reject missing cells and unsupported time instead of filling zeros.
   Record whether it is a forecast, reanalysis or retrospective composite.
4. Freeze simple baselines and physical candidates before scoring: stationary,
   last observed drift and current-only knot-aligned RK4 first. A current-plus-wind
   or learned residual candidate requires matched wind/track data and parameters
   estimated solely from training groups. Do not tune on the completed NOAA study.
5. Score all predeclared groups/horizons with the same future positions and
   denominator. Report path/interval error, coverage and failed outcomes. Compare
   matched errors without treating model repetitions as independent observations.
6. Keep numerical sensitivity separate from empirical skill. A stable RK4 result
   can still forecast the wrong physical object. Interception adds another test:
   real collection efficiency, retention, release controls and protected entries.

## What can be learned from the actual tank

The tank can supply its own matched forcing and object observations: calibrate
the water plane, collect disjoint drift recordings for each layout, freeze the
field and trial protocol, then compare predicted entries with independent releases.
That tests the controlled setup. It does not establish ocean-scale ecological
benefit or justify transferring tank coefficients into a satellite-current model.

No new credential, paid API, provider call, model promotion or physical result is
created by this research note. The current implementation and measured numerical
checks are described in [RK4 numerical quality](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/rk4-numerical-quality.md).
