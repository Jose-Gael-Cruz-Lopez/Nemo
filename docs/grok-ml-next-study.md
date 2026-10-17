# Grok-assisted ML checkpoint, 17 October 2026

The existing Grok project was reused for five sequential research/review prompts:
<https://grok.com/project/709fdaeb-06db-41bd-843b-81f567b993da?tab=conversations&chat=139b9a9d-215a-47f0-9f1f-81db9103e724>.
Grok supplied static review and interpretation. Local code performed acquisition,
forecasting and tests. Grok did not execute the repository or verify local clocks.

## What changed

1. A separately named Indian-basin acquisition extension was declared before its
   new query. All five previously viewed GDP IDs were excluded. Selection must be
   frozen before any trajectory request; failed selections cannot be replaced.
2. A bounded request failed with `ConnectTimeout`. No new IDs, trajectories or
   position rows were acquired. The failed attempt and immutable receipts are
   retained under `data/public/noaa-indian-extension-v1`. An earlier metadata-info
   request had failed before selection; a documented pre-outcome amendment reused
   an already pinned official NOAA metadata snapshot. This is explicitly an older
   snapshot, not a fresh metadata or license verification.
3. A new **post-hoc leave-one-GDP-ID-out diagnostic** was implemented and run on
   the four **already viewed** trajectories. This is useful transfer research,
   not a new independent test or evidence that generalization improved.
4. Dataset readiness is available through
   `apps.ocean.reeftrace_ocean.dataset_readiness.load_dataset_readiness()`.
   It reports the actual blocked acquisition and a sourced roadmap; it performs
   no network calls, training, provider calls, model promotion or writes.

## Exact new model and result

For each of four folds, only the other three drifters' first 18 positions fit a
shared 2×2 velocity-residual AR(1) matrix. Every training trajectory has its own
prefix mean velocity removed. There are 48 transition pairs, a common training-only
RMS residual scale, fixed ridge penalty 1, and a fixed spectral-radius cap of 0.98.
The held group's permitted prefix supplies its local frame, mean velocity, last
velocity and anchor, but never fits the shared transition matrix. Six predictions
free-run without future updates. The target's own mean is conditioning data, so
this is not prediction without an observation prefix.

All fold/model forecasts exist before the scoring stage reads future positions.
The common CSV parser first checks the complete pinned payload's schema, UTC,
identity and finite values; this validation is not feature construction or
parameter fitting. NOAA's upstream hourly interpolation remains a separate
future-information limitation.

Protocol and evaluator receipts were saved before the first *new pooled-model*
score. Earlier exposure to all four trajectories and original model results is
not undone by those local receipts. The implementation is therefore labeled
`POST_HOC_ALREADY_VIEWED_DRIFTERS_NOT_INDEPENDENT_TEST` throughout.

| Fixed algorithm | Mean six-hour trajectory error |
| --- | ---: |
| Stationary | 2,911.30 m |
| Last observed drift | 1,579.85 m |
| Mean prefix drift | 1,846.71 m |
| Own-prefix ridge AR(1) | 729.37 m |
| New pooled residual AR(1) | 1,711.20 m |

All 120 declared outcomes were scored: 4 folds × 5 models × 6 horizons. The new
pooled model lost to both own-prefix ridge and last drift on the aggregate. This
negative result is retained. There is no tuning, switching, automatic promotion,
significance claim, calibrated probability, source-attribution validation or reef
benefit claim. The old 4/6 study and its 96 outcomes remain unchanged and separate.
The table is a descriptive average over these four viewed groups, not a
population estimate.

Grok initially overinterpreted the loss as absence of transferable residual
structure. A follow-up corrected that claim: only this particular fixed estimator
lost under these settings; the result establishes neither a general absence of
transferable structure nor a causal explanation involving local dynamics.

The full report and protocol are in `data/public/noaa-lopo-diagnostic-v1`.
Replay with:

```python
from apps.ocean.reeftrace_ocean.lopo import run_lopo_diagnostic
report = run_lopo_diagnostic()
```

## Physical identity and leakage checks

`assert_disjoint_physical_groups(training_ids, evaluation_ids, physical_mapping)`
requires complete mappings and rejects held/training aliases of the same physical
buoy, as well as duplicate physical buoys within training. The current diagnostic
uses declared GDP logical IDs. It does **not** claim that a WMO-to-GDP mapping has
already been acquired or that statistical independence is established.

Meaningful regressions cover: aliases rejected before matrix fitting; missing
mapping rejected; future latitude/longitude access prohibited during every fold's
prediction generation; target-prefix perturbation cannot change its fold's shared
matrix or training scale; a six-horizon failure remains in 120 attempted outcomes
and suppresses all macro summaries; exact frozen report replay; original v1
report unchanged. Acquisition tests cover numeric selection after excluding all
five viewed IDs, pre-download selection receipts, no overwrite, immutable timeout
coverage and corrupt receipt/metadata rejection.

Verification: **38 tests passed** across `test_lopo.py`,
`test_dataset_readiness.py` and `test_multidrifter.py`; Ruff passed for the five
new/changed Python files in this handoff. These are focused tests, not a claim
that the entire application suite was rerun by this worker.

## Better data means matching the decision

* **Forecast causality:** [NOAA GTS/OSMC fixes](https://www.aoml.noaa.gov/phod/gdp/real-time_data.php)
  are the next candidate. NOAA documents that WMO IDs differ from GDP IDs and
  supplies a mapping. A future protocol must preserve actual as-of availability,
  verify timestamp semantics, handle irregular intervals without future-supported
  interpolation, and keep physical buoy aliases in one split. Such data have
  not been acquired here. They still describe buoy motion, not plastic origin.
* **Actual debris outcomes:** [NOAA MDMAP](https://marinedebris.noaa.gov/our-work/monitoring/marine-debris-monitoring-and-assessment-project)
  records standardized shoreline debris amounts and types and documents public
  export/API access. Retain survey effort, area, date and protocol metadata.
  Observational counts can contextualize prevention; they do not by themselves
  prove that a particular interception layout caused a reduction. No MDMAP data
  were downloaded or joined to tank outcomes in this work.
* **Ocean-current forcing:** [Copernicus GLORYS12](https://data.marine.copernicus.eu/product/GLOBAL_MULTIYEAR_PHY_001_030/description)
  provides daily/monthly gridded reanalysis currents at approximately 8 km. It is
  an assimilative model product, not independent plastic observations; it does
  not resolve a tank or an individual reef channel. Audit forcing availability
  and assimilation before any operational forecast claim. It is researched,
  not acquired or used as a feature here.

NOAA explains that the current [hourly GDP product](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php)
contains quality-controlled, interpolated positions and velocity estimates.
More samples from that product could improve coverage but would not remove its
upstream interpolation limitation.

## Next handoff, without post-hoc tuning

1. Acquire and pin causal GTS fixes plus the official identifier mapping. Freeze
   whole-physical-buoy groups and availability rules before computing errors.
2. Predeclare one forcing-aware candidate only after development-only work. Lock
   its feature sources, versions, preprocessing, parameters and causal lags; use
   a fresh unviewed evaluation cohort. Preserve all baseline losses and failures.
3. Evaluate interception with independent physical trials on frozen layouts and
   measured flow per layout. Keep tank outcomes and shoreline context in separate
   ledgers. Neither a lower buoy forecast error nor a synthetic trial is evidence
   that a real reef was protected.
