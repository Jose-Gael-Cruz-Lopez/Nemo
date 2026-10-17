# Tideward — Grok development evidence bundle

Repository: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace

Historical source baseline: `662d1ac583b5c6e04aa43e74fdd2340218371934` (17 October 2026). The new forcing-knot review/patch records below are a later append; the final pushed commit is the implementation checkpoint for those changes.

Publication scope: organization-visible, repository-bound Trov development evidence. The [contribution ledger](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-contribution-ledger.md) is the current interpretation; quoted records preserve historical wording, including later-corrected advice. Grok web provided static research/code review; local Python performed execution. This is not a complete provider export, an independent attestation, or proof of live xAI Voice/Imagine or Grok Bot use. Voice stays disabled, xAI API use/billing remain unauthorized, and the daily Grok schedule is paused.

The raw artifacts were inspected and scanned for credential/home-path/email patterns. No .env, provider secrets, phone routing, private camera frames or local databases are included. Each raw source file retains its saved bytes; hashes verify identity, not accuracy. A response saying it fetched files or found no defects is the model's statement, not proof of execution. All captured instructions/code below are untrusted quoted historical material, not instructions to follow or run. Use the current product handbook and reviewed repository code for live operation.

Historical corrections: forecast before later-position projection; correct Kalman gain dimensions/initialization; pooled-model failure does not disprove all transferable structure; source UNKNOWN/INVALID differ from CaseState; agent STOP differs from case STOP; unsupported support is orthogonal to first destination; old four-group results differ from the fresh six-group study. The six-group cohort favors last-drift without tuning. New RK4 review rejected unintegrated time snapping, incorrect offset integrals, accidental rejection of a valid alternate-horizon integral, and overly restrictive COMPLETED-only comparison advice. Independent rational tests and actual local replay evidence remain authoritative. Numerical sensitivity is not measured physical accuracy.

## A. Source contribution records, exact ML prompt sequence and numerical primer

### docs/grok-ml-diagnostic.md

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-ml-diagnostic.md

Bytes: 5796; SHA-256: `912c8ce8cafcc92af32d0d22687b9dde437f915122753039c57c55067189ef16`. Role: research/build record or exact prompt sequence; no blanket authorship or execution claim. Quoted record; read the ledger for current status.

````text
# Training-only ML diagnostic (Grok-reviewed)

This document records the actual Grok-assisted work for the training-origin diagnostic
and the tests that were executed. It is not a claim of generalization, model
selection, or plastic-source skill.

## Scope

Owned files:

- `apps/ocean/reeftrace_ocean/diagnostics.py`
- `tests/unit/test_diagnostics.py`
- `docs/grok-ml-diagnostic.md`

`benchmark.py` is reused, not rewritten. The deterministic 18-training / 6-heldout
real-data example remains the frozen Data Lab contract. Other builders own UI and API
wiring. This change did not commit, push, install packages, read `.env` / `work/` /
`data/local`, call provider APIs, send messages, or touch billing/hardware.

## What was implemented

`training_origin_diagnostic(records, horizons=6, training_count=18, min_prefix=8)`
validates explicit Python integers (rejecting `bool` and `float`), `horizons` in 1..6,
`min_prefix >= MIN_FIT_COUNT`, `min_prefix + horizons <= training_count <= 18`, at most
100 records, and enough records to fill `training_count`. It then uses only
`records[:training_count]`.

On that training window it requires one drifter, timezone-aware UTC timestamps, and
regular hourly cadence. Cadence checks may read training timestamps before any forecast.
Prefix lat/lon are projected with `SphericalLocalFrame.to_xy` only as
`training[:prefix_count]` immediately before that origin's three `_forecast` calls.
That origin's later positions are finite/50 km-checked and scored only after those
forecasts exist. After all origin forecasts, the full training window is projected
again so leftover training positions still face the 50 km budget. Default prefixes
8..12 produce five overlapping origins and six horizons. Aggregates report mean, RMSE,
max and count per model/horizon, plus an exact
`per_horizon_error_lower_than_stationary_count`. The JSON payload is finite. `kind` is
`TRAINING_ONLY_RETROSPECTIVE_DIAGNOSTIC`.

`run_training_diagnostic()` reads the CSV bytes once, checks the code-pinned digest and
reviewed manifest identity/count/time/rights fields, and parses that verified payload.
It passes only the first eighteen positions to the diagnostic. It does not call the
full 18/6 benchmark or forecast/score the held-out six hours. Reading the full pinned
artifact for identity verification is distinct from using held-out positions in the
diagnostic. The report sets `test_data_used=false` and `model_selection_performed=false`.

The work does not tune hyperparameters, pick a winner, or treat overlapping training
windows as independent evidence. Passing tests do not require the learned model to beat
the stationary baseline. Limitations disclose dependent windows and NOAA's upstream
interpolation of hourly positions.

## Grok review

Implementation used Cursor Grok 4.6 in this repository.

The Web Grok review referenced by the builders is:

https://grok.com/project/709fdaeb-06db-41bd-843b-81f567b993da?tab=conversations&chat=139b9a9d-215a-47f0-9f1f-81db9103e724

That conversation was not re-fetched or re-run from this session. The builders' correction
of it is implemented here:

1. **`min_prefix` is validated.** The first review missed an explicit integer
   `min_prefix` bound. This code rejects non-ints and values below `MIN_FIT_COUNT`, and
   requires `training_count >= min_prefix + horizons`.
2. **No absolute leakage-proof claim.** Code never reads records after
   `training_count`, and each prefix is forecast before that origin is scored. That is
   not proof against NOAA's already interpolated product, and the five default origins
   share overlapping dependent hours. The report says so.

A later review correction is also implemented: the first draft projected every training
lat/lon into local xy before the first prefix forecast. That is no longer done. A
second-read SHA-256 check closes the gap where `run_real_data_example()` verified one
file and the diagnostic then parsed a replaced CSV.

## Tests executed

From the repository root, using the existing project virtualenv (no package install in
this change):

```text
$ .venv/bin/python -m pytest tests/unit/test_diagnostics.py tests/unit/test_real_data.py -q --strict-config
....................                                                     [100%]
20 passed in 0.18s

$ .venv/bin/python -m ruff check apps/ocean/reeftrace_ocean/diagnostics.py tests/unit/test_diagnostics.py
All checks passed!
```

`tests/unit/test_diagnostics.py` covers default schema and the five origin counts;
reconstructed mean/RMSE/max/count and stationary-comparison counts; `to_xy` of later
training positions only after the first prefix's three forecasts; second-read CSV
tampering rejected against verified SHA-256; sentinel objects after index 18; mutating
later training truth while earlier predicted coordinates stay fixed; unused NOAA
velocity columns; rejection of bool/float/bounds/non-finite positions/non-UTC/irregular
cadence/multiple drifters; and exact JSON equality of the existing 18/6
`run_real_data_example()` output before and after the diagnostic.
`tests/unit/test_real_data.py` was re-run in the same command (11 additional passing
tests) so the frozen held-out benchmark was not silently changed.

The command log above records Cursor's implementation runs. Root review subsequently
replaced the wrapper's full-benchmark call with direct pinned verification, added a
regression proving only prefix lengths eight through twelve reach its forecast calls,
and verified the API integration. The combined diagnostic, unchanged benchmark and API
suite passed **28 tests**. No live Grok Voice request was made. Cursor reached its
account usage limit after its two implementation turns; no paid upgrade was enabled.
Root completed the final correction and the broader verification.
````

### docs/grok-motion-ablation.md

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-motion-ablation.md

Bytes: 6028; SHA-256: `dc213fb25261937601e890cca05fd6a57d78b5bf5d2e6b68737d2ce46673b848`. Role: research/build record or exact prompt sequence; no blanket authorship or execution claim. Quoted record; read the ledger for current status.

````text
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
````

### docs/grok-ml-next-study.md

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-ml-next-study.md

Bytes: 8119; SHA-256: `4dfb63c5193c8619b4059c5513279ce4e72bb4af983d65fef96619f01941150e`. Role: research/build record or exact prompt sequence; no blanket authorship or execution claim. Quoted record; read the ledger for current status.

````text
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
````

### docs/grok-ml-next-prompts.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-ml-next-prompts.txt

Bytes: 8675; SHA-256: `ff7f0843b915bf2cdb35a5a4a640607d533835ec6d78c566c0ec1e91e09a7282`. Role: research/build record or exact prompt sequence; no blanket authorship or execution claim. Quoted record; read the ledger for current status.

````text
PROMPT 1
Continue in THIS existing ReefTrace project; the user requests deeper Grok-assisted ML and better datasets while another engineer redesigns the UI. Static scientific/code assistance only; never claim execution. Current frozen v1 study has four acquired IDs (12730,12731,300234063243480,300234063472530), plus development-only 8707978; all five entire IDs have now been inspected and must be excluded from genuinely new evaluation. v1 missing Indian2010 metadata was a timeout and its immutable PARTIAL_COVERAGE result stays untouched. Propose a separately named prospective Indian-basin extension: same predeclared 2010-06-01T00:00Z Indian metadata region (-40..20lat,40..100lon), numeric-sort first2 distinct IDs excluding all5 viewedIDs, freeze selected IDs/metadata hashes BEFORE downloading 24h trajectories, no replacements after failure, fixed original four algorithms and original code hashes. Exact18prefix,6hour free-run, one origin per entire drifter. Report extension separately, no pooling into old4group means, no tuning/model promotion, no independence or plastic/coral-source claims. We're writing/fixing the acquisition+replay locally and will send real bytes/results later. Primary NOAA GDP docs say hourly positions are quality-controlled/interpolated, so extending same product expands spatial coverage but is not a better independent ground truth or operational forecast validation. Also evaluate future datasets: NOAA raw/GTS irregular fixes for causal real-time validation; NOAA MDMAP shoreline debris outcomes for actual prevention evaluation; Copernicus GLORYS12 currents for retrospective forcing (assimilation leakage/confounding; not independent truth). Give (1) up to3 concrete scientific pitfalls in the proposed extension, (2) small exact pseudocode for fail-closed exclusion of ALL previously seen IDs with detached manifest hashes and all-model/group/horizon outcomes, (3) which future dataset best answers ReefTrace's real decision 'does upstream interception reduce debris reaching a protected area?' and what it cannot prove alone. Do not invent downloaded data, citations, numerical results, keys, or code execution. No UI/hardware/provider/Photon/account actions.

PROMPT 2
Actual local execution checkpoint: the bounded new Indian metadata query failed with ConnectTimeout; 0 selected groups,0 trajectory payloads,0 position rows,0 scored outcomes. We retained exact frozen selection/manifest+detached SHA receipts; original v1 remains unchanged4/6,96/144. First dataset-info fetch failed before selection; a documented pre-outcome amendment reused older pinned NOAA official license/DOI metadata (retrieved05:48UTC), NOT freshly verified metadata. Final extension protocol e07c5acef71c08ae0bb4e39fa94e904cd9d5a7bea9b7fab5c7e785d6ae6ce2f2; selection857e907f6a66f7b97dbe2aaee8c9f214774010005b5f17949f45c5591a5e440c; manifestcb14170dc4939c2b5c48afaa1db4e0add05361e65f66100784c3642f931828a7. All5viewedIDs excluded. Added read-only DATASET_READINESS_REPORT with ACQUISITION_BLOCKED, no model claims, explicit planned48/scored0, metadatafresh=false, and primary-source next-data roadmap. Synthetic transport tests prove selectedIDs are numerically sorted AFTER excludingall5; selectionfileanddetachedhash exist BEFORE mock trajectoryrequest; timeoutretains0groups; nooverwrite; corruptprotocol/selection/manifest/metadatabytes failclosed. Actual32localtests pass including unchangedv1regressions; Grok did not execute them. Primary research: NOAA real-time page https://www.aoml.noaa.gov/phod/gdp/real-time_data.php says OSMC uses WMO identification, different from GDP ID, with mappingfile. AnyfutureGTSsplit MUSTexclude same physicaldrifters acrossmappedidentifieraliases and honor as-ofreceipt/publicationlatency, not simplydifferentstringIDs. NOAA MDMAP page supports standardizedshorelineamount/typecounts and export/API; do NOT assert allMDMAPrecords lackbeforeafterdesign, because that isn'testablished. Stateobservationalcountsalonecannotprovelayoutcausality; require effort/area/protocolcontrols and validinterventiondesign. CopernicusGLOBAL_MULTIYEAR_PHY_001_030is daily/monthlyassimilativereanalysis~8km; no claimitobservesplastic orresolvestank/reefchannel. Withnetworkunavailable,wewillnotfabricatedatamodeltrainingorimprovement. Nowgive a practical nextMLarchitecturehandoffwith exactlyTHREEsteps: (1) causalirregular-timeGTSingestion+alias-safeholdout, (2) preregisteroneadditionalmodel capableofcurrentforcing only aftertraining-onlycalibration andfreeze, (3) independentinterceptionvalidationwithrealphysicaltrials/MDMAPcontext. For eachgive input,output,andminimalfailuretest. Identify any unsupported claim in these conclusions; otherwise saynone. Keepitscientificandconcrete, notproducthype. No account/provider/Photon/UIactions.

PROMPT 3
NEXT CONCRETE POST-HOC DIAGNOSTIC, already-viewed data explicitly not independent new evaluation. We have4pinnedGDPIDs with24hours each; originalstudyremainsunchanged. Beforecomputingnewpooled-modelerrors,wepredeclareleave-one-GDP-ID-out: for eachfolduseONLY18positionprefixes ofother3IDs to fit one sharedvelocity-residualAR1matrix. Eachtrainingtrajectory's17hourlyENUvelocitiesarecenteredbyitsOWNprefixmean; pooled48transitionpairs, commonRMSscaleontrainingresidualsonly, ridgealpha1,spectralradiusmax.98 sameasoriginal. No intercept beyond pertrajectorymean. Heldgroup usesONLYown18prefixpositionsforframe/meanvelocity/lastvelocity/anchor, nevertofitsharedmatrix. Sixhourfree-run vnext=heldprefixmean+(v-heldprefixmean)@A, integratepositionhourly. Compareagainstoriginal4ownprefixalgorithms stationary,lastdrift,meandrift,ridgeAR1; complete4folds*5models*6h=120outcomesincludingfailures. GenerateALLfold/modelpredictions before readingfuturepositiontruth; nofutureupdates. Macrodescriptiveequalgroupmeanswithheldifanyrequiredoutcomefails. Holdoutsarealreadyviewed, newmodelis posthoc diagnostic not pre-registeredindependenttest; no tuningorpromotionoroperational/plasticclaims. Newaliasdisjointvalidator requires fullcanonicalphysicalmapping; if trainrawID andheldrawID mapto samephysicalIDreject. ForcurrentGDP-onlydata identitymapisdeclaredGDPlogicalIDs, NOTverifiedWMOaliasresolution. Is residualsharedmemory a defensiblesmalltransfer-diagnostic ratherthan physicaloceanmodel? Give atmostTWOconcreterejectionissuesorminimalregressiontests. Noexecutionclaim. Wearefreezingthisspec andlocalcodebeforefirstnewscore, butthatcannotundoearlierexposure.

PROMPT 4
ACTUAL LOCAL RESULTS for static interpretation only. Completed new frozen post-hoc LOPOdiagnostic on the4ALREADYVIEWEDdrifters:4folds*5models*6h=120/120scored,0failures. Equaldriftermean6hourpositionerrors:stationary2911.298073m,lastdrift1579.850431m,meandrift1846.712592m,ownprefixridge729.365075m,pooledresidualAR11711.199878m. The newsharedmodel LOSES to ownprefixridge AND lastdrift. No tuning/switch/promotion occurred; retainnegative result. Frozenprotocol SHA198ebac9e216298cbd7d60ada7bcc18b1ac30bac837f4f7e94a1e402bef3a2e6, implementationreceiptcreatedbeforefirstnewscore, all4alreadyviewedexplicit. Local38testsPASS (6newLOPO tests+datasetreadiness+unchangedv1tests), lintPASS; GrokdidNOTexecute. Regressiontests actually guardfuturelat/lonproperties and prove diagnostic_predictions producesall20fold-modelarrayswithoutreadinganyfuturepositions; modifyheldprefixdoesnotchangeheldfold'ssharedA/scale; aliasoverlaprejectsbeforematrixfit; missingmaprejects; injectone6hforecastfailurekeeps120attempts,6nullerrorsandwithholdsALLmacros; pinnedreportreplayequalsandoriginalv1reportunchanged. ActualnewNOAAdownloadremains0becauseboundedIndianrequestConnectTimeout. Newreadinessroadmap showsGTS/MDMAP/GLORYSresearchednotacquired. Pleaseexplainin150wordswhatthisnegativeresultteaches,thelegitimateincrementalvalueoftheLOPOdiagnostic,andwhynowinordatasetimprovementclaimisjustified. Name2nextpredeclaredexperimentchoicesasFUTUREONLYratherthanposthocparametersearch. Noexecutionorindependenceclaim.

PROMPT 5
One scientific correction before we finalize: this single pooled model's higher four-group mean does NOT establish the absence of transferable residual structure, nor prove local dynamics are the mechanism. It establishes only that this particular fixed pooled estimator performed worse on this already-viewed, four-group diagnostic under these settings. Other estimators, data quality, sampling dependence, and uncertainty remain unresolved. We will retain the negative result without a mechanistic or general impossibility claim. Please acknowledge this correction in two clear sentences; no new experiment or parameter search. We are publishing the local report with that narrower interpretation.
````

### docs/grok-kalman-build.md

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-kalman-build.md

Bytes: 8583; SHA-256: `3d5072843526e2d33e1b4f38875c26cbba6c8060964ae369d69a7c820a7b070c`. Role: research/build record or exact prompt sequence; no blanket authorship or execution claim. Quoted record; read the ledger for current status.

````text
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
````

### docs/grok-fresh-build.md

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-fresh-build.md

Bytes: 6639; SHA-256: `bb2cf0c19e85b2ba858e32e18a36522b16ffb3c7c8dee17d0cda248c991b4aa3`. Role: research/build record or exact prompt sequence; no blanket authorship or execution claim. Quoted record; read the ledger for current status.

````text
# Grok-assisted fresh NOAA study and demo review

Checkpoint: 17 October 2026. The existing [Grok project conversation](https://grok.com/project/709fdaeb-06db-41bd-843b-81f567b993da?chat=139b9a9d-215a-47f0-9f1f-81db9103e724) was used interactively for methodology, code and presentation review. Local implementation, execution, browser checks and Git commits were performed in the ReefTrace workspace. A Grok answer is review input, not evidence that Grok executed the repository.

## What the review changed

1. **Selection before outcomes.** The first prompt challenged reuse of already-viewed drifters and model-selection leakage. Protocol v1 and the 223-ID exclusion list were pushed in `4de5fa6` before acquisition. The fixed five models use each selected drifter's own 18-position context; no shared model is fitted to the six future positions.
2. **Preserve failed acquisition.** The first attempt obtained registry/metadata but selected no trajectories. It encountered bounded timeouts and a local parser's incorrect expectation for the official metadata units row. The failed receipts were retained. A disclosed v2 schema/transport amendment was pushed in `086942c` before new acquisition or any outcome score. No replacement group was selected after seeing errors.
3. **Review the actual evaluator.** Grok reviewed the permitted-prefix preparation and forecast/scoring code before scoring. An independent local audit verified raw future coordinate strings were not projected during preparation. All model forecasts are built before future coordinate access. The evaluator, protocol helper, acquisition script and implementation receipt were frozen in `cc1f7fa` before first scoring.
4. **Reject weak suggested code.** A proposed CSV/deadline sketch was insufficient: checking elapsed time only at parser entry does not bound a stalled body read, and malformed CSV must become a preserved failed acquisition. The implemented fetcher has an absolute request alarm plus a total budget, restores its signal handler, retains partial bytes and normalizes decoding/CSV failures. Boundary tests cover those cases.
5. **Keep the negative result.** The six acquired GDP-ID days produced 180/180 scored model outcomes. Last drift had lower aggregate errors than ridge and Kalman. Grok was asked to interpret that result without retuning, changing the cohort or promoting a complex model. The table in [the study guide](fresh-noaa-study.md) remains authoritative.
6. **Separate scientific and application states.** The math review covered `[x,y,vx,vy]`, continuous white-acceleration process noise, `R=(100 m)^2 I`, correlated two-fix initialization, Joseph covariance and observation ellipses using `P_position+R`. We corrected review prose that conflated SourceReport `unknown`/`invalid` with CaseState, treated Chalk STOP as case stop, implied API-enforced trial order, or described metre X/Y plots as time axes. The [code-grounded contract audit](algorithm-contract-audit.md) records the actual behavior.
7. **Make the demo readable.** The UI review proposed a trace → compare → explain story, clear recorded/predicted line styles, and details disclosures. Source and prevention's stock demos are explicitly separate synthetic examples. NOAA is separate real historical research. Physical counts and missing/unresolved limitations remain visible.
8. **Bound the next experiment.** Grok proposed a synthetic-only first-passage bookkeeping audit: deterministic replay, absorbing outcomes, earliest time-node entry and retained unsupported particles. Any implementation must first use the actual outcome partition, including unsupported mass, rather than assuming every trajectory remains free or captured. This is a development-fixture audit, not permission to modify frozen equations or create a new successful physical result.

The final browser pass also reproduced a provider reliability defect: an immediate model STOP claimed the evidence tool was unavailable without reading it. The bounded research orchestrator now performs its one required server-bound read before accepting a conclusion, records whether the model requested it or the server enforced it, and supplies the verified result to the existing final model call. The two-call/one-read limit, byte/deadline budgets and stale-snapshot checks remain enforced. Regression tests cover the exact premature-STOP response, a failed read, grounded STOP and the actual saved study through both read paths. A further live review produced valid JSON/citations but exceeded the hard 1,200-character explanation gate. The prompt now explicitly targets at most 800 characters; the hard limit is unchanged and the actual overlength response is a rejection regression. These repairs change agent orchestration and presentation, not any frozen numerical outcome.

## Result and evidence boundary

The new study contains six selected GDP IDs, five fixed algorithms, six forecast hours per group, 180 scored outcomes, and 36 unique observed later intervals. The first 18 hourly positions are context; the last six are evaluation truth. Historical QC/interpolation may use later raw fixes upstream, so this is not an operational-causality test. Distinct IDs/selected WMOs do not prove independence; ten older aliases remain unresolved.

Last-drift ADE is **1,573.423 m**, Kalman **1,655.662 m**, ridge **1,772.130 m**. These numbers do not validate a plastic source, interception layout or reef benefit. No frozen model was retuned after scoring. A separate live Chalk research REPORT was verified against the canonical study hash and protocol citation; deterministic results remain available when providers fail.

See [fresh NOAA study](fresh-noaa-study.md), [algorithm contracts](algorithm-contract-audit.md), [current README](../README.md), and [software-only teammate prompts](software-handoffs.md) for reproducible commands and remaining work.

## Capabilities and automation

Grok is used interactively for planning and adversarial review. Its recurring research automation remains **paused**. GitHub checks run on pushes and pull requests; no new scheduled prompt or autonomous merge was enabled. No Photon message was sent as part of this work and its existing authorized configuration was preserved.

Using this Grok conversation does not establish a live Grok Voice/Imagine API integration or challenge eligibility. The server-side Voice adapter and deterministic evidence briefing are implemented, but live funded xAI Voice verification remains unavailable. Credentials, private contacts and local operator tokens were not included in research prompts or committed artifacts.
````

### docs/grok-space-context.md

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-space-context.md

Bytes: 8765; SHA-256: `c30d5f24bea0d538b252d4d488e0e3f944c862cf31174a3a52a3f5146bb0645f`. Role: research/build record or exact prompt sequence; no blanket authorship or execution claim. Quoted record; read the ledger for current status.

````text
# ReefTrace: satellite context and an evidence-grounded voice briefing

This feature preserves source tracing as the core. It joins two explicitly separate views: a frozen tabletop source report and a real historical satellite-derived reef thermal-stress series. A user can read or listen to the same short, deterministic briefing. Satellite heat context never changes source scores, release ages, priors or a confidence gate.

## Exact implemented contracts

```python
from apps.ocean.reeftrace_ocean.satellite import load_satellite_context
from adapters.grok import GrokVoiceSettings, build_briefing, synthesize_briefing

context = load_satellite_context()          # Offline; verifies reviewed bytes and provenance.
briefing = build_briefing(frozen_source_report, context)
settings = GrokVoiceSettings(enabled=False) # Default: no provider requests.
result = await synthesize_briefing(briefing, settings)
```

These modules do not read `.env`, launch workers, send phone messages, invoke Photon, change Chalk, start cameras or actuate hardware. The application supplies settings and the authorized, saved numerical report. A success contains `audio_bytes` for an `audio/mpeg` HTTP response; the whole result is not JSON serializable. A failure contains a safe `failure_code`, optional upstream status and no audio, key, response body or exception string.

**Application integration requirements:** bind the click endpoint to the authorized case; generate its briefing on the server from the saved report; recheck the case revision and stopped state before returning audio. Do not accept arbitrary narration, a client-supplied source report or a script hash as authorization. Hashes identify frozen inputs and detect changes; they are not signatures. The audio endpoint is an explicit user action with no automatic retries or preloading. Display the written text even when voice is unavailable.

`build_briefing` preserves ranked/Unknown/Invalid, labels synthetic observations, retains “relative support is not probability,” rejects contradictory source support, and requires any supplied satellite context to equal the verified offline record. It does not use arbitrary notes or LLM narration. The speech provider therefore does not generate a new source conclusion or invent a heat value.

## The real space-data artifact

Provider: NOAA Coral Reef Watch. Product: daily global 5 km satellite-derived Degree Heating Week (DHW), version 3.1. Dataset ID: `noaacrwdhwDaily`. Variable: `degree_heating_week`, units `degree_Celsius_weeks`. Coordinates: **24.575° N, 81.525° W**, one ocean grid cell in the Florida Keys area. Dates: **1–7 July 2023, 12:00 UTC daily**. The dataset is derived from a Level 4 satellite sea-surface-temperature analysis; the metadata lists satellite and in situ source instruments, so this is an analyzed satellite-derived product rather than seven raw satellite images. [NOAA metadata](https://coastwatch.noaa.gov/erddap/info/noaacrwdhwDaily/index.html).

Verified raw CSV: `data/public/noaa-coral-context/noaa-crw-dhw-florida-keys-20230701-20230707.csv`, **383 bytes**, seven rows. SHA-256:

```text
5e3248ce6247aece0d5736678bba36010cb4b0a2053c40e1ba7b69bba125c101
```

The matching `.provenance.json` records the exact HTTPS request, retrieval UTC time, units, attribution and digest. The loader checks both bytes against a code-pinned digest and every reviewed manifest field. It rejects missing units, wrong coordinates, timestamps, extra rows, missing values and inconsistent provenance. A data hash cannot establish that NOAA's physical analysis is error-free; it ensures the reproducible fixture is the reviewed source artifact.

| Date in July 2023 | DHW, °C-weeks |
|---|---:|
| 1 | 2.96 |
| 2 | 3.18 |
| 3 | 3.43 |
| 4 | 3.72 |
| 5 | 3.99 |
| 6 | 4.24 |
| 7 | 4.53 |

DHW accumulates heat stress over the previous twelve weeks. NOAA associates **4 °C-weeks with bleaching risk**; a displayed value is not direct confirmation that coral bleached. This seven-day excerpt reads NOAA's already computed DHW rather than attempting to reconstruct twelve weeks from seven days. The fixed historical cell is not current conditions, a measurement of the tank, a current field, a plastic detector or source-attribution ground truth. [NOAA DHW explanation](https://coralreefwatch.noaa.gov/product/5km/index_5km_dhw.php).

NOAA metadata permits unrestricted use of CRW data while requesting source attribution/citation. Preserve NOAA credit and the product/version/source links. A separately designed future operational triage policy could combine an actual geolocated debris observation and contemporaneous heat context; the present demo does not validate such a policy or measure a cleanup benefit.

Reproduce the source fetch, without an account or credential:

```sh
.venv/bin/python scripts/fetch_satellite_context.py
```

The script refuses an existing fixture unless `--force` is supplied. Even with `--force`, changed source bytes fail the reviewed hash rather than silently redefining the demonstration. Network retrieval is capped at sixteen kilobytes, has a thirty-second timeout and refuses redirects. Ordinary dashboard reads load the local fixture, with no NOAA network dependency. The date and location are deliberately fixed for reproducibility; the UI must not call the result live.

## xAI Voice implementation

The minimal operation is server-side **POST `https://api.x.ai/v1/tts`**, using `Authorization: Bearer <XAI_API_KEY>` and JSON `{text, voice_id:"eve", language:"en"}`. The documented default response is raw MP3 audio. The basic request has no model field; do not invent a `grok-*` text-model ID for this TTS endpoint. [Official Text to Speech documentation](https://docs.x.ai/developers/model-capabilities/audio/text-to-speech).

`GrokVoiceSettings` defaults to disabled, hides the key from its representation, limits requests to twenty seconds by default and output to two megabytes. `synthesize_briefing` validates the frozen script hash, requests the fixed HTTPS endpoint, rejects redirects, does not retry, requires MP3 content type, and enforces declared and streamed audio-size limits. Provider errors return sanitized status only. The permanent API key stays in the server; never place it in browser code or a public environment variable. A valid account/key and usable quota are still needed; offline mock tests are not live provider commissioning.

## If the challenge specifically requires interactive Grok Voice

Text to Speech is documented under xAI's Voice APIs. Challenge interpretation belongs to the organizers; do not claim this automatically satisfies a narrower requirement for a conversational voice agent. The documented interactive route is **`wss://api.x.ai/v1/realtime?model=grok-voice-3.0`**. Currently `grok-voice-latest` aliases that version. Configure with `session.update`, send a text message with `conversation.item.create` and `input_text`, then request `response.create`. Receive `response.output_audio.delta` and `response.done`. Versioned model selection avoids an alias changing during a demo. [Speech to Speech documentation](https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech).

A browser may use a short-lived token issued by a server POST to **`https://api.x.ai/v1/realtime/client_secrets`**, with an `expires_after.seconds` value such as 300. Use browser WebSocket protocol `xai-client-secret.<ephemeral-token>`; never expose the permanent API key. The token endpoint must itself be authenticated and bounded. This is a future extension, not part of the implemented TTS adapter. [Official ephemeral tokens](https://docs.x.ai/developers/model-capabilities/audio/ephemeral-tokens).

The current requirements mentioned by the team also include Cursor and real space data. This module supplies real satellite-derived context and an xAI speech integration path; code running in another editor is not evidence of Cursor use. Preserve real build evidence and verify the event's precise submission requirements without inventing sponsor eligibility.

## Verification

```sh
.venv/bin/python -m pytest tests/test_grok.py tests/unit/test_satellite.py -q
.venv/bin/ruff check adapters/grok apps/ocean/reeftrace_ocean/satellite.py \
  scripts/fetch_satellite_context.py tests/test_grok.py tests/unit/test_satellite.py
```

The tests are offline. They cover provenance tampering, dimensional/date/location errors, frozen briefing semantics, Unknown/Invalid preservation, unsupported input, disabled/no-key behavior, exact outgoing TTS contract, no redirect/retry, timeout, size/content failures and secret-safe errors. Physical tracing validation, a successful paid-provider call, and challenge submission remain distinct from these software checks.
````

### docs/rk4-numerical-quality.md

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/rk4-numerical-quality.md

Bytes: 6177; SHA-256: `8b320c22cfb0cae42f6e8db3165bf67337897ff6217d9e9afa8e0bccf5929675`. Role: research/build record or exact prompt sequence; no blanket authorship or execution claim. Quoted record; read the ledger for current status.

````text
# RK4 and numerical quality in Tideward

Development checkpoint: 17 October 2026. This is a numerical-method improvement
and sensitivity experiment on the existing pinned PacIOOS field. It is not a new
NOAA buoy skill study, a trained plastic detector, or a physical tank result.

## What RK4 means

The ocean model supplies eastward and northward water velocity at grid locations
and times. Tideward follows a hypothetical passive particle through that field:
`dX/dt = u(X,t)`. RK4 samples the current at the start, at two estimated midpoint
positions, and at an estimated endpoint, then uses their weighted average to
advance the particle. It samples again at the new position and time on the next
step; a change in speed alone need not bend the path.

For state `z=(latitude,longitude)` in degrees and elapsed seconds `t`, the
derivative is `f(z,t)=(northward/m_latitude, eastward/m_longitude)`, using the
latitude-dependent WGS84 metres-per-degree factors. The four stages are:

```text
k1 = f(z, t)
k2 = f(z + h*k1/2, t + h/2)
k3 = f(z + h*k2/2, t + h/2)
k4 = f(z + h*k3,   t + h)
z_next = z + h*(k1 + 2*k2 + 2*k3 + k4)/6
```

East/north m/s are never added directly to geographic degrees. The tank uses
separately measured cm and cm/s; ocean currents do not calibrate it.

## The issue that was fixed

Linear interpolation between supplied current timestamps changes slope at each
timestamp. An RK4 step crossing that break can introduce a numerical inconsistency.
The solver now ends steps at forcing timestamps, as well as output times, the
requested horizon and its existing speed/cell/maximum-step limit. It uses all
supported time through the final current timestamp before reporting an unsupported
remainder. Positive time is always accompanied by integration of position; there
is no time-only snap. Unrepresentable progress fails explicitly, and extra knot
splits count toward the bounded step budget.

Only contributing interpolation corners may be read. Missing masks, unsupported
geography and unavailable time still stop the path. An exactly valid timestamp
does not authorize interpolation into a masked future interval.

The independently derived regression uses uniform eastward velocities
`[0,1,0] m/s` at absolute times `[0,650,1400] s`, at the equator. Integrating the
piecewise-linear current from zero to 1,000 seconds gives `1780/3 m`, approximately
593.333 m. The old unsplit calculation returned approximately 589.744 m. A request
continuing to 1,800 seconds now retains the supported prefix through 1,400 seconds;
the previous implementation stopped at 1,200 seconds. Exact rational trapezoid
areas generate the test expectations, including different start offsets and
horizon meanings.

The original snapshot has three-hour forcing knots aligned with its five-minute
default steps. Its six track arrays and every release outcome in both scenarios
were checked against a saved pre-patch reference and remained exactly unchanged.
Method hashes change with source bytes; historical receipts are not relabelled.

## Two different sensitivity checks

**Integration sensitivity** reruns the fixed releases with maximum solver steps of
300, 150 and 75 seconds, with the same 300-second output schedule. Position
separations are compared only at shared supported positive times against the
75-second numerical run. Missing common times, partial paths and changed forcing
statuses remain explicit. The finest run is a numerical reference, not truth.

**Contact-interval sensitivity** integrates one finest path with 75-second solver
and output intervals, then derives 300-, 150- and 75-second contact chords by
downsampling that same path. A terminal partial point is retained. The existing
first-contact geometry evaluates each representation. This isolates contact
localization from independently changing the integrated trajectory. Event types,
collector identities, unresolved outcomes, counts, recommendations and comparable
event-time differences are retained for all releases.

The main decision still evaluates all layouts against one common default path
per release. Additional diagnostic reruns are separate and never promote a model,
retune a completed study or replace the default decision.

## What this proves and what it does not

Agreement across these settings is evidence of stability under those particular
numerical choices. It is not a calibrated uncertainty band, independent truth,
observed fourth-order convergence, or proof that waste follows the current. A
small solver difference cannot resolve errors in the underlying roughly 4 km,
three-hour current field, collector efficiency, windage, waves, object response
or real protected-area geometry.

The same hash-bound comparison and compact numerical summary are available to
Chalk. Its explanation must retain those distinctions. Data Lab and Prevention
show the check behind a closed disclosure, keeping the main combined trajectory
plot and conditional layout comparison concise. Older exported reports without
the optional numerical field remain readable as historical snapshots.

## Primary guidance and implementation evidence

- [Nordam and Duran, Numerical integrators for Lagrangian oceanography](https://gmd.copernicus.org/articles/13/5935/2020/index.html): time-cell boundaries and interpolation affect numerical integration; stopping at known temporal boundaries can avoid crossing a derivative break.
- [OceanParcels timestep/integrator tutorial](https://docs.oceanparcels.org/en/latest/user_guide/examples/tutorial_dt_integrators.html): compares timestep choices and integrators; a finer numerical reference is distinct from an exact trajectory.
- [Current solver](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/apps/ocean/reeftrace_ocean/advection.py) and [analytic forcing-knot regressions](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/tests/unit/test_advection_time_knots.py).
- [Grok contribution and correction ledger](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-contribution-ledger.md): actual prompts, static responses, rejected arithmetic/time snapping and local verification are preserved separately.
````

### docs/next-current-data-study.md

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/next-current-data-study.md

Bytes: 5214; SHA-256: `8526b3c0cfe74185a50d5aa5596a90d5ea6155d5f64cadb8c64dccd803c82165`. Role: research/build record or exact prompt sequence; no blanket authorship or execution claim. Quoted record; read the ledger for current status.

````text
# Next data and model study: match the forcing to the observation

Research checkpoint: 17 October 2026. This is a proposal and source-availability
review, **not a frozen completed experiment or a new acquired trajectory dataset**.
The existing NOAA studies and their negative results remain unchanged.

The next useful empirical comparison is a current-driven forecast against an
independent object's later recorded motion at the **same place and time**. Adding
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
````

## B. Exact saved historical and new RK4 prompt, response and local-receipt sources

The first fourteen numbered files are the original inspected archive. The later RK4 files preserve four actual new prompt/response rounds and the separate local execution receipt. Source file hashes below match the raw archive manifest.

### docs/grok-evidence/01-initial-build-prompt.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/01-initial-build-prompt.txt

Bytes: 35255; SHA-256: `dcc024de26cababad49055d0d91cd03026ef75c4c3252a25f9d86b8bc047945e`. Role: saved prompt prepared for the existing Grok project. Quoted record; read the ledger for current status.

````text
ReefTrace implementation task 1: scientific ML audit and reviewable code.

We are a four-person HackHarvard team, building a sustainability project with basic hardware in 36 hours. Preserve tracing as the core. Repository: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace . Active local branch codex/software-execution. IMPORTANT: GitHub currently has an old starter scaffold; our checked-in update is being prepared. The exact working source excerpts below are authoritative for this task. Do not claim you cloned, executed, committed, or trained anything unless you actually did. If web Grok cannot modify our local repository, provide precise patches for us to review and apply.

Actual product:
- Overhead USB webcam tracks red floating tokens in a controlled 2D tabletop tank. Homography maps water-plane pixels to centimetres. Median-cell + IDW token-drift field is independently validated. A bounded stochastic forward particle model simulates entry points A/B/C and release ages, compares paths or retained endpoints, reports relative support, Unknown or Invalid. Tank is not an ocean simulator. The LLM retrieves immutable evidence, never invents source numbers or infers a culprit from satellite pixels. Manual net recovery only. No automatic robot or pump control.
- FastAPI/Python backend, Next.js 16 dashboard, local SQLite evidence. Chalk Model Gateway investigator currently being connected to existing Google Gemini free-tier connection. Photon paired but PHOTON_ENABLED=false: do not send messages or enable replies.
- Data Lab: real NOAA GDP buoy 8707978 on 1987-10-03, 24 hourly positions. Chronological first 18 train, final 6 held out. Stationary/last drift/ridge AR1 compare mean, RMSE and final errors. Existing result: ridge mean error3557m vs stationary3855m (7.72% better) but final7561m vs6775m (11.61% worse). This one day proves neither general superiority nor plastic source attribution. Published NOAA future velocities are not model input. No GPU/deep learning is justified by this tiny sample.

New sponsor track exact requirements from https://hhuh.io/#challenges: SpaceXAI Make It Legendary: use real space data; built with Cursor; Grok Imagine OR Voice API; bonus Grok Bot planning. Grok web chat is not proof of Voice API use. We are adding independently labelled historical satellite-derived NOAA Coral Reef Watch DHW context, not mixing it with tank source likelihoods, plus user-triggered spoken frozen-evidence briefing through xAI TTS https://api.x.ai/v1/tts (official docs https://docs.x.ai/developers/model-capabilities/audio/text-to-speech). Verify current primary docs yourself. Do not claim eligibility just from this chat.

Task: deeply inspect the supplied actual benchmark source and propose ONE small implementation that improves scientific reliability and can land today. Prefer a leakage-proof chronological rolling-origin diagnostic on the fixed real NOAA day: each origin uses only prefix positions; compare the existing three models on the same horizons; no tuning or model selection on evaluation outputs; report per-origin errors and aggregate counts; explicitly overlapping dependent windows and a single drifter/day cannot establish generalization. Preserve the existing untouched 18/6 report. Do not train a neural net or hide the worsening endpoint error. If a better narrow implementation exists, explain evidence and scope first.

Deliver:
1. Concrete audit findings with actual file/function names and any mathematical errors you can establish, not guesses.
2. Exact unified patch for one new function/module and meaningful tests; no imaginary repository file APIs. Reuse existing forecast/projection/distance functions correctly. Bound horizons/sample counts and validate finite data.
3. Explicit expected schema and UI display plan; label diagnostic, not new independent test. Do not calculate better scores or assert tests pass without execution.
4. A 4-person remaining build breakdown: tracing/measurement, scientific validation, satellite+Voice, UI/demo. A two-minute demo sequence that separates synthetic tank proof from real satellite context and real drifter benchmark.
5. Cite official primary sources for any new external factual claims. End with a short acceptance checklist.

Safety and scope: no keys or credential files, no billing/subscriptions, no secret logging, no human messaging, no hardware actuation, no public-upload changes. Your role is reviewer and patch author; we execute locally after review. Ask no broad exploratory questions; work from provided evidence and state any necessary unknowns.

AUTHORITATIVE WORKING SOURCE EXCERPTS FOLLOW:

===== apps/ocean/reeftrace_ocean/benchmark.py =====
"""Small reproducible geographic forecast experiment on an authentic NOAA drifter day.

This is a retrospective buoy-motion benchmark, never plastic-source attribution.
Only chronological training positions enter a model. NOAA's published velocities
and uncertainty columns are retained for inspection but never used as labels or
future forcing. All calculations run offline against a content-pinned CSV.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from .data import DrifterRecord, parse_drifter_csv

ROOT = Path(__file__).resolve().parents[3]
SAMPLE_NAME = "noaa-gdp-8707978-19871003.csv"
SAMPLE_SHA256 = "b503de924bbfe82fb18a705917e527faaf26e51688845adb4b57f0cb121c2fca"
EXPECTED_PROVENANCE = {
    "source_url": (
        "https://erddap.aoml.noaa.gov/gdp/erddap/tabledap/drifter_hourly_qc.csv?"
        "ID,time,latitude,longitude,ve,vn,err_ve,err_vn&ID=%228707978%22&"
        "time%3E=1987-10-03T00%3A00%3A00Z&time%3C=1987-10-03T23%3A00%3A00Z"
    ),
    "metadata_url": "https://erddap.aoml.noaa.gov/gdp/erddap/info/drifter_hourly_qc/index.html",
    "provider": "NOAA AOML Global Drifter Program",
    "dataset_id": "drifter_hourly_qc",
    "product_doi": "10.25921/x46c-3620",
    "license_from_endpoint_metadata": "CC-BY-4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "drifter_id": "8707978",
}
EARTH_MEAN_RADIUS_M = 6_371_008.8
MAX_LOCAL_DISTANCE_M = 50_000.0
TRAIN_COUNT = 18
MIN_FIT_COUNT = 8
RIDGE_ALPHA = 1.0  # Fixed dimensionless penalty; never selected on the holdout.
MAX_AR_SPECTRAL_RADIUS = 0.98  # Fixed stability constraint, not a post-test correction.
MODEL_IDS = ("stationary", "last_drift", "ridge_ar1")
ModelID = Literal["stationary", "last_drift", "ridge_ar1"]


@dataclass(frozen=True)
class SphericalLocalFrame:
    """Azimuthal equidistant log/exp map on a declared mean-radius sphere.

    East/north metres relative to the first training position. This is an exact
    spherical map, not WGS84 geodesy; the 50 km budget limits distortion. Distance
    errors are reported using great-circle separation on the same sphere. The
    ellipsoid-vs-sphere discrepancy can approach ~0.6%, which this example does
    not interpret as measured forecast uncertainty.
    """

    latitude_deg: float
    longitude_deg: float

    def to_xy(self, latitude_deg: float, longitude_deg: float) -> np.ndarray:
        if not all(math.isfinite(v) for v in (latitude_deg, longitude_deg)):
            raise ValueError("Finite geographic coordinates required")
        if not -90 <= latitude_deg <= 90 or not -180 <= longitude_deg <= 180:
            raise ValueError("Geographic coordinates outside latitude/longitude limits")
        lat0, lon0, lat, lon = map(
            math.radians,
            (self.latitude_deg, self.longitude_deg, latitude_deg, longitude_deg),
        )
        dlon = math.atan2(math.sin(lon - lon0), math.cos(lon - lon0))
        east = math.cos(lat) * math.sin(dlon)
        north = math.cos(lat0) * math.sin(lat) - math.sin(lat0) * math.cos(lat) * math.cos(dlon)
        dot = math.sin(lat0) * math.sin(lat) + math.cos(lat0) * math.cos(lat) * math.cos(dlon)
        angle = math.atan2(math.hypot(east, north), dot)
        distance = angle * EARTH_MEAN_RADIUS_M
        if distance > MAX_LOCAL_DISTANCE_M:
            raise ValueError("Drifter example exceeds its 50 km local-geometry budget")
        if distance < 1e-9:
            return np.zeros(2)
        return np.array([east, north]) * distance / math.hypot(east, north)

    def to_latlon(self, xy_m: np.ndarray) -> tuple[float, float]:
        east, north = np.asarray(xy_m, dtype=float)
        distance = math.hypot(east, north)
        if not math.isfinite(distance) or distance > MAX_LOCAL_DISTANCE_M:
            raise ValueError("Forecast exceeds its finite 50 km local-geometry budget")
        if distance < 1e-9:
            return self.latitude_deg, self.longitude_deg
        lat0, lon0 = map(math.radians, (self.latitude_deg, self.longitude_deg))
        angle = distance / EARTH_MEAN_RADIUS_M
        lat = math.asin(
            math.cos(angle) * math.sin(lat0) + north / distance * math.sin(angle) * math.cos(lat0)
        )
        lon = lon0 + math.atan2(
            east / distance * math.sin(angle),
            math.cos(lat0) * math.cos(angle) - north / distance * math.sin(lat0) * math.sin(angle),
        )
        return math.degrees(lat), (math.degrees(lon) + 180.0) % 360.0 - 180.0


def great_circle_distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Stable haversine separation for (latitude, longitude) tuples, in metres."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    sin2 = math.sin((lat2 - lat1) / 2) ** 2 + (
        math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_MEAN_RADIUS_M * math.asin(math.sqrt(min(1.0, max(0.0, sin2))))


def _forecast(training_xy: np.ndarray, steps: int, step_s: float, model: ModelID) -> tuple:
    """Free-run predictions anchored at the final TRAINING location only."""
    if len(training_xy) < MIN_FIT_COUNT or not 1 <= steps <= 12:
        raise ValueError("Forecast requires >=8 training points and 1..12 horizons")
    velocities = np.diff(training_xy, axis=0) / step_s
    anchor = training_xy[-1].copy()
    if model == "stationary":
        return np.repeat(anchor[None, :], steps, axis=0), {"learned_parameters": 0}
    if model == "last_drift":
        velocity = velocities[-1]
        return anchor + np.arange(1, steps + 1)[:, None] * step_s * velocity, {
            "last_observed_velocity_m_s": velocity.tolist(),
            "learned_parameters": 0,
        }
    if model != "ridge_ar1":
        raise ValueError("Unknown forecast model")
    mean_velocity = velocities.mean(axis=0)
    # A common scalar scale makes the regularizer dimensionless and isotropic.
    scale = float(np.sqrt(np.mean((velocities - mean_velocity) ** 2)))
    scale = max(scale, 1e-9)
    features = (velocities[:-1] - mean_velocity) / scale
    target = (velocities[1:] - mean_velocity) / scale
    matrix = np.linalg.solve(features.T @ features + RIDGE_ALPHA * np.eye(2), features.T @ target)
    radius_before = float(np.max(np.abs(np.linalg.eigvals(matrix))))
    if radius_before > MAX_AR_SPECTRAL_RADIUS:
        matrix *= MAX_AR_SPECTRAL_RADIUS / radius_before
    velocity = velocities[-1]
    predictions = []
    for _ in range(steps):
        velocity = mean_velocity + (velocity - mean_velocity) @ matrix
        anchor = anchor + step_s * velocity
        predictions.append(anchor.copy())
    return np.asarray(predictions), {
        "learned_parameters": 6,
        "training_velocity_pairs": len(features),
        "mean_velocity_m_s": mean_velocity.tolist(),
        "velocity_transition_matrix_row_vector_convention": matrix.tolist(),
        "ridge_alpha": RIDGE_ALPHA,
        "spectral_radius_before_constraint": radius_before,
        "maximum_spectral_radius": MAX_AR_SPECTRAL_RADIUS,
        "constraint_applied": radius_before > MAX_AR_SPECTRAL_RADIUS,
        "hyperparameters_selected_on_holdout": False,
    }


def _training_error_radii(
    training_xy: np.ndarray, horizons: int, step_s: float, model: ModelID
) -> list[dict]:
    """Training-only expanding-origin error radii, not calibrated probabilities.

    Each fit sees its prefix only; the later points used to score that prefix
    still precede the final train/test cutoff. Overlapping forecast errors are
    dependent, and this tiny sample does not establish nominal 90% coverage.
    """
    result = []
    for horizon in range(1, horizons + 1):
        errors = []
        for prefix_count in range(MIN_FIT_COUNT, len(training_xy) - horizon + 1):
            predicted, _ = _forecast(training_xy[:prefix_count], horizon, step_s, model)
            errors.append(
                float(np.linalg.norm(predicted[-1] - training_xy[prefix_count + horizon - 1]))
            )
        result.append(
            {
                "horizon_hours": horizon * step_s / 3600,
                "radius_m": float(np.quantile(errors, 0.9, method="higher")),
                "training_hindcast_count": len(errors),
                "nominal_quantile": 0.9,
                "calibrated_probability": False,
            }
        )
    return result


def _point(record: DrifterRecord) -> dict:
    return {
        "time_utc": record.time_utc.isoformat().replace("+00:00", "Z"),
        "latitude_deg": record.latitude_deg,
        "longitude_deg": record.longitude_deg,
    }


def benchmark_drifter_records(
    records: list[DrifterRecord], *, train_count: int = TRAIN_COUNT
) -> dict:
    """Chronological, deterministic retrospective experiment; no external calls.

    NOAA's hourly positions are already interpolated/smoothed. Splitting this
    published product avoids additional code-level future leakage, but cannot
    undo possible future support in NOAA's upstream interpolation. It therefore
    cannot establish raw real-time operational skill.
    """
    if not MIN_FIT_COUNT + 1 <= train_count < len(records) <= 100:
        raise ValueError("Require 9..99 training observations, <=100 total and heldout data")
    if len(records) - train_count > 12 or len({r.drifter_id for r in records}) != 1:
        raise ValueError("Require one drifter and <=12 heldout hours")
    step_s = (records[1].time_utc - records[0].time_utc).total_seconds()
    if step_s != 3600 or any(
        (b.time_utc - a.time_utc).total_seconds() != step_s for a, b in itertools.pairwise(records)
    ):
        raise ValueError("This bounded benchmark requires regular hourly UTC records")
    training = records[:train_count]
    heldout = records[train_count:]
    frame = SphericalLocalFrame(training[0].latitude_deg, training[0].longitude_deg)
    xy = np.asarray([frame.to_xy(r.latitude_deg, r.longitude_deg) for r in training])
    # Heldout positions are intentionally absent from fitting and error-radius calibration.
    models = []
    for model_id in MODEL_IDS:
        forecast, parameters = _forecast(xy, len(heldout), step_s, model_id)
        radius_rows = _training_error_radii(xy, len(heldout), step_s, model_id)
        predictions = []
        errors = []
        for index, (prediction, truth, radius) in enumerate(
            zip(forecast, heldout, radius_rows, strict=True), 1
        ):
            lat, lon = frame.to_latlon(prediction)
            error = great_circle_distance_m((lat, lon), (truth.latitude_deg, truth.longitude_deg))
            errors.append(error)
            predictions.append(
                {
                    "time_utc": _point(truth)["time_utc"],
                    "horizon_hours": index,
                    "latitude_deg": lat,
                    "longitude_deg": lon,
                    "error_m": error,
                    "training_error_radius_m": radius["radius_m"],
                    "training_hindcast_count": radius["training_hindcast_count"],
                    "within_training_error_radius": error <= radius["radius_m"],
                }
            )
        models.append(
            {
                "id": model_id,
                "label": {
                    "stationary": "Stationary position persistence",
                    "last_drift": "Last observed displacement",
                    "ridge_ar1": "Learned ridge velocity autoregression",
                }[model_id],
                "kind": "LEARNED_LINEAR_MODEL" if model_id == "ridge_ar1" else "NAIVE_BASELINE",
                "fit_uses": "training_positions_only",
                "free_run_without_heldout_updates": True,
                "parameters": parameters,
                "predictions": predictions,
                "metrics": {
                    "heldout_count": len(errors),
                    "mean_error_m": float(np.mean(errors)),
                    "rmse_error_m": float(np.sqrt(np.mean(np.square(errors)))),
                    "endpoint_error_m": errors[-1],
                    "max_error_m": max(errors),
                    "within_training_error_radius_count": sum(
                        point["within_training_error_radius"] for point in predictions
                    ),
                    "uncertainty_is_calibrated": False,
                },
                "training_error_radii": radius_rows,
            }
        )
    stationary_error = models[0]["metrics"]["mean_error_m"]
    for model in models:
        model["metrics"]["mae_skill_vs_stationary"] = (
            1 - model["metrics"]["mean_error_m"] / stationary_error
            if stationary_error > 0
            else None
        )
    return {
        "schema_version": 1,
        "experiment_id": "noaa-gdp-8707978-19871003-chronological-v1",
        "status": "COMPLETED",
        "data_origin": "REAL_HISTORICAL_NOAA_DRIFTER",
        "title": "Real NOAA drifter: six-hour heldout motion forecast",
        "split": {
            "method": "chronological_free_run_no_random_split",
            "training_count": len(training),
            "heldout_count": len(heldout),
            "training_end_utc": _point(training[-1])["time_utc"],
            "heldout_start_utc": _point(heldout[0])["time_utc"],
            "step_seconds": step_s,
            "test_values_used_for_model_selection": False,
        },
        "coordinate_system": {
            "input": "geographic_latitude_longitude_degrees",
            "fit": "spherical_azimuthal_equidistant_east_north_metres",
            "error": "spherical_great_circle_metres",
            "earth_mean_radius_m": EARTH_MEAN_RADIUS_M,
            "origin_latitude_deg": frame.latitude_deg,
            "origin_longitude_deg": frame.longitude_deg,
            "maximum_local_distance_m": MAX_LOCAL_DISTANCE_M,
            "sphere_not_wgs84_ellipsoid": True,
            "approximate_maximum_ellipsoid_discrepancy_fraction": 0.006,
        },
        "training_track": [_point(r) for r in training],
        "heldout_track": [_point(r) for r in heldout],
        "models": models,
        "source_attribution": {
            "status": "NOT_SUPPORTED_BY_THIS_DATASET",
            "reason": "These are buoy locations, not plastic releases, coral health or polluter labels.",
        },
        "uncertainty_method": {
            "kind": "training_only_expanding_origin_90th_percentile_error_radius",
            "probability_claim": None,
            "note": "Few overlapping hindcasts; empirical radii are not calibrated 90% confidence regions.",
            "published_noaa_velocity_intervals_used_as_forecast_uncertainty": False,
        },
        "limitations": [
            "One historically selected drifter-day and six dependent heldout hours cannot establish general forecast skill.",
            "Hourly NOAA locations are quality-controlled/interpolated; upstream processing may use later raw fixes. This is retrospective product evaluation, not raw operational validation.",
            "Only positions before the split enter each fit; neither heldout positions nor published velocity columns enter prediction.",
            "The regression penalty and stability bound are fixed; no model is promoted on this tiny test.",
            "Training error radii use very few overlapping hindcasts and are not calibrated probabilities.",
            "A sphere approximates the Earth; geographic degrees never enter the tank-centimetre estimator.",
            "Buoy drift is not floating-plastic behavior. No plastic source, human actor or ecological impact is inferred.",
            "No Copernicus field is paired to this historical sample; this is not a physics-model-versus-buoy validation.",
        ],
    }


def run_real_data_example() -> dict:
    """API/CLI entrypoint. Verify pinned local bytes and provenance before fitting."""
    source = ROOT / "data/public" / SAMPLE_NAME
    payload = source.read_bytes()
    if len(payload) > 100_000:
        raise ValueError("Public example exceeds its 100 KB budget")
    digest = hashlib.sha256(payload).hexdigest()
    manifest = json.loads(source.with_suffix(".provenance.json").read_text(encoding="utf-8"))
    if digest != SAMPLE_SHA256 or digest != manifest.get("sha256"):
        raise ValueError("Public NOAA sample hash does not match pinned provenance")
    if any(manifest.get(key) != value for key, value in EXPECTED_PROVENANCE.items()):
        raise ValueError("Public NOAA provenance differs from the reviewed official-source record")
    records = parse_drifter_csv(payload.decode("utf-8"))
    if (
        len(records) != 24
        or manifest.get("row_count") != 24
        or manifest.get("bytes") != len(payload)
        or {r.drifter_id for r in records} != {"8707978"}
        or _point(records[0])["time_utc"] != "1987-10-03T00:00:00Z"
        or _point(records[-1])["time_utc"] != "1987-10-03T23:00:00Z"
    ):
        raise ValueError("Public NOAA sample identity/count/time differs from pinned experiment")
    report = benchmark_drifter_records(records)
    report["provenance"] = {
        "provider": manifest["provider"],
        "source_url": manifest["source_url"],
        "metadata_url": manifest["metadata_url"],
        "product_doi": manifest["product_doi"],
        "license": manifest["license_from_endpoint_metadata"],
        "license_url": manifest["license_url"],
        "attribution": manifest["attribution"],
        "retrieved_at_utc": manifest["retrieved_at_utc"],
        "csv_relative_path": "data/public/" + SAMPLE_NAME,
        "sha256": digest,
        "integrity_verified": True,
        "bytes": len(payload),
        "row_count": len(records),
        "drifter_id": records[0].drifter_id,
        "upstream_manifest_purpose": manifest["purpose"],
        "benchmark_scope": "retrospective_tiny_heldout_forecast_extension_of_ingestion_fixture",
    }
    # Reject accidental numpy scalars/NaN before it reaches the API or exported report.
    json.dumps(report, allow_nan=False)
    return report

===== tests/unit/test_real_data.py =====
"""The public-data demo must be real, chronological, bounded and scientifically honest."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import timedelta

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import benchmark
from apps.ocean.reeftrace_ocean.benchmark import (
    ROOT,
    SAMPLE_NAME,
    SphericalLocalFrame,
    benchmark_drifter_records,
    great_circle_distance_m,
    run_real_data_example,
)
from apps.ocean.reeftrace_ocean.data import load_drifter_csv


def records():
    return load_drifter_csv(ROOT / "data/public" / SAMPLE_NAME)


def test_real_report_verifies_bytes_and_discloses_exact_experiment():
    report = run_real_data_example()
    assert report["data_origin"] == "REAL_HISTORICAL_NOAA_DRIFTER"
    assert report["provenance"]["integrity_verified"] is True
    assert report["provenance"]["bytes"] == 1950
    assert report["provenance"]["row_count"] == 24
    assert report["provenance"]["sha256"] == benchmark.SAMPLE_SHA256
    assert report["provenance"]["license"] == "CC-BY-4.0"
    assert report["split"]["training_count"] == 18
    assert report["split"]["heldout_count"] == 6
    assert report["training_track"][-1]["time_utc"] == "1987-10-03T17:00:00Z"
    assert report["heldout_track"][0]["time_utc"] == "1987-10-03T18:00:00Z"
    assert report["source_attribution"]["status"] == "NOT_SUPPORTED_BY_THIS_DATASET"
    assert report["uncertainty_method"]["probability_claim"] is None
    assert len(report["models"]) == 3
    json.dumps(report, allow_nan=False)


def test_real_metrics_match_reported_predictions_and_include_worse_results():
    report = run_real_data_example()
    for model in report["models"]:
        errors = [p["error_m"] for p in model["predictions"]]
        assert model["metrics"]["mean_error_m"] == pytest.approx(np.mean(errors))
        assert model["metrics"]["rmse_error_m"] == pytest.approx(
            np.sqrt(np.mean(np.square(errors)))
        )
        assert model["metrics"]["endpoint_error_m"] == errors[-1]
        assert model["free_run_without_heldout_updates"] is True
        assert model["metrics"]["uncertainty_is_calibrated"] is False
        assert [r["training_hindcast_count"] for r in model["training_error_radii"]] == [
            10,
            9,
            8,
            7,
            6,
            5,
        ]
    persistence, last_drift, learned = report["models"]
    # Pin the behavior, not an artificially favorable summary: learned mean
    # error is lower on this day, but its final error is WORSE than stationary.
    assert persistence["metrics"]["mean_error_m"] == pytest.approx(3855.003585, abs=0.01)
    assert last_drift["metrics"]["mae_skill_vs_stationary"] < 0
    assert learned["metrics"]["mean_error_m"] < persistence["metrics"]["mean_error_m"]
    assert learned["metrics"]["endpoint_error_m"] > persistence["metrics"]["endpoint_error_m"]


def test_no_heldout_position_or_velocity_leaks_into_predictions_or_radii():
    original = records()
    changed = [
        replace(r, latitude_deg=r.latitude_deg + 0.08, longitude_deg=r.longitude_deg - 0.04)
        if i >= 18
        else r
        for i, r in enumerate(original)
    ]
    changed = [
        replace(
            r,
            eastward_m_s=1000 + i,
            northward_m_s=-999 - i,
            eastward_uncertainty_m_s=500,
            northward_uncertainty_m_s=500,
        )
        for i, r in enumerate(changed)
    ]
    baseline = benchmark_drifter_records(original)
    alternative = benchmark_drifter_records(changed)
    for first, second in zip(baseline["models"], alternative["models"], strict=True):
        assert first["parameters"] == second["parameters"]
        assert first["training_error_radii"] == second["training_error_radii"]
        for a, b in zip(first["predictions"], second["predictions"], strict=True):
            assert a["latitude_deg"] == b["latitude_deg"]
            assert a["longitude_deg"] == b["longitude_deg"]
        assert first["metrics"]["mean_error_m"] != second["metrics"]["mean_error_m"]


@pytest.mark.parametrize(
    ("origin", "location"),
    [((46.4, -137.7), (46.46, -137.62)), ((0, 179.9), (0.1, -179.9)), ((89.9, 20), (89.9, 50))],
)
def test_spherical_log_exp_roundtrip_handles_dateline_and_near_pole(origin, location):
    frame = SphericalLocalFrame(*origin)
    xy = frame.to_xy(*location)
    reconstructed = frame.to_latlon(xy)
    assert great_circle_distance_m(location, reconstructed) < 1e-5
    assert np.linalg.norm(xy) == pytest.approx(great_circle_distance_m(origin, location))


def test_spherical_geometry_units_and_bounds():
    assert great_circle_distance_m((0, 0), (0, 1)) == pytest.approx(111_195.08023, abs=0.01)
    frame = SphericalLocalFrame(0, 0)
    assert frame.to_xy(0, 0).tolist() == [0, 0]
    assert frame.to_latlon(np.zeros(2)) == (0, 0)
    assert frame.to_xy(0, 0.1)[0] == pytest.approx(11_119.50802, abs=0.01)
    assert frame.to_xy(0.1, 0)[1] == pytest.approx(11_119.50802, abs=0.01)
    with pytest.raises(ValueError, match="50 km"):
        frame.to_xy(1, 0)
    with pytest.raises(ValueError, match="50 km"):
        frame.to_latlon(np.array([50_001, 0]))
    with pytest.raises(ValueError, match="Finite"):
        frame.to_xy(float("nan"), 0)
    with pytest.raises(ValueError, match="limits"):
        frame.to_xy(91, 0)


def test_constant_drift_learned_model_preserves_motion_without_future_data():
    base = records()[0]
    frame = SphericalLocalFrame(base.latitude_deg, base.longitude_deg)
    straight = []
    for i in range(24):
        lat, lon = frame.to_latlon(np.array([i * 100, i * 200]))
        straight.append(
            replace(
                base,
                time_utc=base.time_utc + timedelta(hours=i),
                latitude_deg=lat,
                longitude_deg=lon,
            )
        )
    result = benchmark_drifter_records(straight)
    assert result["models"][1]["metrics"]["mean_error_m"] < 1e-5
    assert result["models"][2]["metrics"]["mean_error_m"] < 1e-5
    assert result["models"][0]["metrics"]["mean_error_m"] > 700


def test_bad_cadence_multiple_drifters_and_excess_forecast_are_rejected():
    original = records()
    changed = original.copy()
    changed[4] = replace(changed[4], time_utc=changed[4].time_utc + timedelta(minutes=1))
    with pytest.raises(ValueError, match="hourly"):
        benchmark_drifter_records(changed)
    changed[4] = replace(original[4], drifter_id="another-buoy")
    with pytest.raises(ValueError, match="one drifter"):
        benchmark_drifter_records(changed)
    with pytest.raises(ValueError, match="training"):
        benchmark_drifter_records(original, train_count=8)
    with pytest.raises(ValueError, match="12 heldout"):
        benchmark_drifter_records(original, train_count=9)


def test_pinned_hash_protects_actual_data_even_if_manifest_is_changed(tmp_path, monkeypatch):
    target = tmp_path / "data/public"
    target.mkdir(parents=True)
    original = ROOT / "data/public" / SAMPLE_NAME
    payload = original.read_bytes().replace(b"-0.0736", b"-0.0735", 1)
    (target / SAMPLE_NAME).write_bytes(payload)
    manifest = json.loads(original.with_suffix(".provenance.json").read_text())
    import hashlib

    manifest["sha256"] = hashlib.sha256(payload).hexdigest()
    (target / SAMPLE_NAME).with_suffix(".provenance.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(benchmark, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="hash"):
        run_real_data_example()


def test_source_and_rights_provenance_cannot_be_replaced_by_unreviewed_links(tmp_path, monkeypatch):
    target = tmp_path / "data/public"
    target.mkdir(parents=True)
    original = ROOT / "data/public" / SAMPLE_NAME
    (target / SAMPLE_NAME).write_bytes(original.read_bytes())
    manifest = json.loads(original.with_suffix(".provenance.json").read_text())
    manifest["source_url"] = "https://example.com/not-noaa"
    (target / SAMPLE_NAME).with_suffix(".provenance.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(benchmark, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="official-source"):
        run_real_data_example()

===== apps/ocean/reeftrace_ocean/data.py =====
"""NOAA ERDDAP CSV reader. These are observations of buoys, not plastic sources."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

NOAA_COLUMNS = ("ID", "time", "latitude", "longitude", "ve", "vn", "err_ve", "err_vn")
NOAA_UNITS = ("", "UTC", "degrees_north", "degrees_east", "m/s", "m/s", "m/s", "m/s")


def metres_per_second_to_cm_per_second(values):
    """Convert velocity units only. This does not turn longitude/latitude into tank XY."""
    return np.asarray(values, dtype=float) * 100.0


@dataclass(frozen=True)
class DrifterRecord:
    drifter_id: str
    time_utc: datetime
    latitude_deg: float
    longitude_deg: float
    eastward_m_s: float
    northward_m_s: float
    eastward_uncertainty_m_s: float
    northward_uncertainty_m_s: float


def parse_drifter_csv(text: str) -> list[DrifterRecord]:
    """Require the declared ERDDAP schema, unit row, UTC times and finite data.

    No random train/test split, interpolation, clipping, source labels or claimed
    prediction validation is performed here. NOAA uncertainty columns are retained.
    """
    rows = csv.reader(io.StringIO(text))
    if tuple(next(rows, [])) != NOAA_COLUMNS or tuple(next(rows, [])) != NOAA_UNITS:
        raise ValueError("Expected NOAA GDP columns and ERDDAP units row")
    records = []
    last_time_by_id: dict[str, datetime] = {}
    for row in rows:
        if not row:
            continue
        if len(row) != len(NOAA_COLUMNS):
            raise ValueError("Unexpected NOAA GDP CSV row length")
        try:
            when = datetime.fromisoformat(row[1])
            numeric = np.asarray(row[2:], dtype=float)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid NOAA GDP timestamp or numeric value") from exc
        if when.utcoffset() != UTC.utcoffset(when):
            raise ValueError("NOAA time must be timezone-aware UTC")
        if (
            not np.isfinite(numeric).all()
            or (np.abs(numeric) >= 1e20).any()
            or (numeric == -999999.0).any()
        ):
            raise ValueError("NOAA GDP missing/non-finite values require explicit handling")
        lat, lon, east, north, err_east, err_north = numeric.tolist()
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Geographic coordinates out of range")
        if min(err_east, err_north) < 0:
            raise ValueError("Negative uncertainty or missing-value sentinel")
        if not row[0] or when <= last_time_by_id.get(row[0], datetime.min.replace(tzinfo=UTC)):
            raise ValueError("Each drifter needs an ID and strictly increasing timestamps")
        last_time_by_id[row[0]] = when
        records.append(DrifterRecord(row[0], when, lat, lon, east, north, err_east, err_north))
    if not records:
        raise ValueError("No drifter records")
    return records


def load_drifter_csv(path: str | Path) -> list[DrifterRecord]:
    return parse_drifter_csv(Path(path).read_text(encoding="utf-8"))

===== pyproject.toml =====
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "reeftrace"
version = "0.1.0"
description = "Controlled source-intelligence proof of concept for floating debris"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115,<1.0",
  "uvicorn[standard]>=0.30,<1.0",
  "pydantic-settings>=2.4,<3.0",
  "numpy>=2.0,<3.0",
  "scipy>=1.14,<2.0",
  "opencv-python-headless>=4.10,<5.0",
  "httpx>=0.27,<1.0",
  "pyyaml>=6.0,<7.0",
]

[project.optional-dependencies]
sponsors = ["photonhq-api==0.5.0"]
evaluations = ["chalkcompute==2.13.7", "pyarrow==26.0.0"]
ocean = ["xarray>=2025.1", "netcdf4>=1.7", "copernicusmarine>=2.0,<3.0"]
dev = [
  "pytest>=8.3,<9.0",
  "httpx>=0.27,<1.0",
  "ruff>=0.6,<1.0",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["apps*", "adapters*"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"
````

### docs/grok-evidence/02-source-static-review.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/02-source-static-review.txt

Bytes: 4169; SHA-256: `130d64490933ade4faa56022a5e3049404c2c96baf47eaa122a7f93601a010cf`. Role: saved Grok static review output; execution assertions are not independently attested here. Quoted record; read the ledger for current status.

````text
Review generated in Grok web. Static review, not independent test execution.

Read-only review of codex/software-execution (commit 944e94c / CI 3e068c1)

I fetched and inspected the exact raw files requested (diagnostics.py, adapters/grok/voice.py, apps/api/reeftrace_api/services/runtime.py, apps/api/reeftrace_api/main.py) plus the corresponding unit tests (tests/unit/test_diagnostics.py, tests/test_grok.py) and docs/grok-ml-diagnostic.md. This is a static code review only; I did not execute tests, start the API, or access the repository beyond public raw content.

Findings

No demonstrable defects were identified in the focused areas (training/holdout separation, provenance/hash checks, dimensions, frozen-report narration, STOP/revision races, operator authorization, secret exposure, bounded external requests, or honest sponsor eligibility).

Training/holdout: training_origin_diagnostic (diagnostics.py L111–210) and run_training_diagnostic (L213–249) slice exclusively to records[:TRAIN_COUNT] / training = records[:training_count]. Prefix XY is projected and _forecast is called before any later-training truth is read or projected (L133–142). Final held-out records are never indexed. Tests confirm this with a sentinel object, prefix-length assertions, and byte-for-byte equality of the existing 18/6 run_real_data_example output.
Provenance: Independent SHA-256 + manifest + identity/count/time checks occur before any diagnostic call (L216–233); tamper tests reject changed CSV even with updated manifest.
Frozen narration: build_briefing (voice.py L64–148) snapshots and validates the exact source report (status, support table summing to 1, uncalibrated interpretation, safe IDs) and requires the satellite context to match the pinned offline load exactly. Speech text is a deterministic template; satellite is explicitly separated.
Races / authorization: speak_briefing (runtime.py L49–68) holds the case lock, rechecks revision / evidence_id / STOPPED|RECOVERING state after synthesis, and discards on mismatch. Mutating endpoints including /briefing/audio require the operator dependency (main.py L79–84, L117), which uses hmac.compare_digest. GET briefing is read-only.
Secrets / bounds: API key is repr=False; failure paths omit upstream bodies; TTS uses a single non-retrying stream with timeout, size limit, and follow_redirects=False (voice.py L162–218). Default is disabled; readiness reports missing key. No live TTS is claimed.
Eligibility: Code and docs correctly state TTS is wired but disabled (funded credits required) and that Cursor usage is limited; Photon remains off.

The implementation is consistent with the previously reviewed requirements and the published tests.

Short future dataset-expansion plan

Keep the existing single-day 18/6 free-run and the five-origin training-only diagnostic frozen as historical fixtures. For any expansion:

Select additional NOAA GDP hourly QC drifter-days that are temporally and geographically disjoint from 1987-10-03 (and from each other).
Pre-declare a development set of days and a held-out test set of days before any model comparison.
Fit or inspect only on development days; evaluate the same three fixed models (stationary, last-drift, ridge AR1) on the untouched test days using chronological free-runs or rolling origins that stay inside each day’s own prefix.
Report per-day and aggregate metrics without selecting, promoting, or re-tuning any model on the basis of lower errors.
Retain the same provenance pinning, upstream-interpolation disclaimer, and “single-day / dependent windows do not establish generalization” language.

Official primary sources: NOAA AOML GDP hourly QC dataset drifter_hourly_qc (DOI 10.25921/x46c-3620, ERDDAP metadata at https://erddap.aoml.noaa.gov/gdp/erddap/info/drifter_hourly_qc/index.html); NOAA Coral Reef Watch daily global 5 km DHW product version 3.1 (https://coralreefwatch.noaa.gov/product/5km/index_5km_dhw.php and related product pages); xAI TTS endpoint POST https://api.x.ai/v1/tts (https://docs.x.ai/developers/model-capabilities/audio/text-to-speech).

No repository modifications or messages were sent.

````

### docs/grok-evidence/03-case-and-chalk-static-review.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/03-case-and-chalk-static-review.txt

Bytes: 1769; SHA-256: `f568768f3c49c2759dc7a807a3c2b97014c6f07cc40149a848fd59d269cf4ed0`. Role: saved Grok static review output for commit 3a99477. Quoted record; read the ledger for current status.

````text
Grok
Worked for 18s

Final static review of commit 3a99477b3cb0ede58223f5fe80455472b38b461b

Fetched and inspected only the changed files: adapters/chalk/agent.py, apps/api/reeftrace_api/main.py, dashboard/app/page.tsx, dashboard/app/components/evidence-state.ts, and scripts/e2e_demo.py. This is a read-only static review; no tests were executed here and the in-progress hosted CI run is not claimed to have passed.

No supported new correctness defect.

investigate in adapters/chalk/agent.py now computes request_budget = min(settings.request_timeout_s, remaining turn time) (default 25 s) inside the outer asyncio.timeout_at 60 s deadline, still caps the loop at 9 calls, adds only diagnostic fields on TIMEOUT (timeout_stage, timeout_scope, model_calls_attempted, tools_completed), and performs no retries. Tool/evidence gates in _finish are unchanged.
create_app in apps/api/reeftrace_api/main.py restricts private-network CORS preflights to the exact origins http://localhost:3000 and http://127.0.0.1:3000 while preserving the existing operator HMAC dependency on mutating routes.
currentSourceEvidence and canReloadSourceEvidence in dashboard/app/components/evidence-state.ts, used by page.tsx, expose a report or the GET-only “Reload source report” action only when both case_id and evidence_id match the currently selected case; late or mismatched results are discarded. setEvidence clears case-bound answer and analysis.
audit in scripts/e2e_demo.py fails fast before mutation if Photon is enabled or the camera is running, then verifies the training diagnostic (five origins, test_data_used: false), satellite context, frozen briefing text/hashes, and disabled Voice (no audio request).

The next scientific priority remains blind physical tank trials.
````

### docs/grok-evidence/04-initial-build-handoff.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/04-initial-build-handoff.txt

Bytes: 3038; SHA-256: `54f5b0b7ebcdc06383fc1e08d0ba913507b905eb3d725ef4601c7c77708b1d35`. Role: historical local handoff, not a Grok-authored response. Quoted record; read the ledger for current status.

````text
ReefTrace — Grok build handoff

Current repository branch:
https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/tree/codex/software-execution
Commit: 3e068c1de81515f04279d0760022fcbfcb144fce

Grok project and review conversation:
https://grok.com/project/709fdaeb-06db-41bd-843b-81f567b993da?tab=conversations&chat=139b9a9d-215a-47f0-9f1f-81db9103e724

Automation:
GitHub Actions runs Python tests, Ruff, the pinned NOAA replay, dashboard lint,
type checks and production build on every push and pull request. It needs no
provider keys, has no hardware access, and disables all sponsor transports.
The hosted run passed both jobs:
https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/actions/runs/38994984931

What was actually built with Grok:
Grok web reviewed real benchmark source and authored a diagnostic proposal.
Cursor with its Grok model implemented and tested the new diagnostic in two turns.
Root review corrected validation, prediction-before-truth access and the wrapper's
pinned verification. The live Data Lab now shows five dependent training origins
alongside the unchanged 18-training/6-heldout benchmark.
A real NOAA satellite-derived historical reef heat-stress fixture, chart, provenance,
and deterministic frozen-evidence briefing are integrated into investigations.
The server-side xAI TTS client is connected to explicit operator controls, preserves
case/evidence binding, guards STOP and limits time/audio size.

Local validation:
305 Python tests passed. Ruff, Next route types, TypeScript, lint and isolated
production build passed. Browser clicks verified the real NOAA replay, new training
diagnostic, satellite context, briefing text and disabled-voice fallback.
A live Chalk/Gemini investigation returned REPORT grounded in the unchanged source
report. External model timeouts/503 responses can still occur and fail safely.

Current boundaries:
Grok Voice remains disabled: user chose finishing without a live xAI key.
No live TTS request or completed Voice-API challenge eligibility is claimed.
Cursor reached its existing usage limit; no paid upgrade or API billing was enabled.
Photon remains disabled. No test messages or automatic replies were sent.
Camera/tank physical commissioning remains separate from software verification.

Run locally from the reeftrace folder:
.venv/bin/python scripts/dev.py
Then open http://127.0.0.1:3000/ and use Data lab.
Investigations has Load satellite context and Read briefing text.
Never upload .env, work/, data/local/, recordings or private route data to Grok.
Use the sanitized source ZIP/context file or exact public branch instead.

Next useful Grok task:
Review the existing dataset plan and propose predeclared additional NOAA drifter days
with disjoint development and test groups. Keep the current historical fixtures frozen;
report all tested days, do not tune on heldout errors, and never label buoy forecasts
as plastic-source ground truth. Deliver reviewable patches and meaningful tests;
state clearly which code was executed and which is only proposed.
````

### docs/grok-evidence/05-initial-local-verification.json

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/05-initial-local-verification.json

Bytes: 984; SHA-256: `c01e43c1d031534ad93277115dcf89f3da18bacd49504a5304028447db07e0b6`. Role: historical local execution receipt, not Grok execution. Quoted record; read the ledger for current status.

````json
{
  "commit": "3e068c1de81515f04279d0760022fcbfcb144fce",
  "local_python_tests_passed": 305,
  "ruff": "PASS",
  "dashboard_lint": "PASS",
  "dashboard_types": "PASS",
  "dashboard_production_build": "PASS",
  "github_ci": "PASS",
  "github_ci_url": "https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/actions/runs/38994984931",
  "browser_flows": {
    "noaa_fixed_holdout_replay": "PASS",
    "grok_training_diagnostic": "PASS",
    "satellite_context": "PASS",
    "frozen_briefing_text": "PASS",
    "voice_without_key_fallback": "PASS"
  },
  "chalk_live_investigation": "REPORT_WITH_FROZEN_EVIDENCE",
  "external_model_latency": "Transient 503/timeout failures observed; safe STOP fallback retained.",
  "grok_voice_live_call": "NOT_RUN_USER_SELECTED_NO_KEY",
  "cursor_build": "Two Grok implementation turns completed; subsequent usage cap",
  "photon_enabled": false,
  "messages_sent": 0,
  "billing_changed": false,
  "hardware_actuation": false,
  "git_worktree": "CLEAN"
}
````

### docs/grok-evidence/06-initial-source-bundle-verification.json

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/06-initial-source-bundle-verification.json

Bytes: 274; SHA-256: `6fa2e6c95ff012493288453752d32354c9b6668fbcf1d52b28202416eccb531b`. Role: historical local source-bundle receipt. Quoted record; read the ledger for current status.

````json
{
  "commit": "3e068c1de81515f04279d0760022fcbfcb144fce",
  "files": 138,
  "private_value_scan": "PASS",
  "token_pattern_scan": "PASS",
  "zip_bytes": 1477989,
  "context_bytes": 1053899,
  "zip_sha256": "72c7a455c308002ca09fc88fd31d771fa125dd74c83ebf9b7897adf67ed5ad2a"
}
````

### docs/grok-evidence/07-kalman-build-prompt.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/07-kalman-build-prompt.txt

Bytes: 6573; SHA-256: `0530c94f4eeadadd57c2395d51d96c510369c8e5e631295e21a22740dd66c067`. Role: saved prompt prepared for the existing Grok project. Quoted record; read the ledger for current status.

````text
Continue this SAME project and conversation. We are now calling the product Tideward; the repository and API remain reeftrace: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace . Current pushed commit 1a10cee07e4af8d515c7c66d143ee6da3be019cb. Do not create another project or claim you executed local code.

BUILD REQUEST: propose and specify a genuinely useful NEXT modeling experiment, with the physical tank as the intended eventual application. Here the UI/UX is being edited separately; your scope is modeling, experimental design, and reviewable implementation. No account/billing/Photon actions.

Verified current state: four already-viewed NOAA GDP buoy-days, each 24 hourly positions. Models fit the first18 and free-run six hours. Original study: 4 acquired of6 target,96 scored of144 planned model intervals,24 unique observed intervals reused across four models. Existing equal-buoy six-hour mean position errors: stationary2911.298m,lastdrift1579.850m,mean1846.713m,own-prefix ridge729.365m. A separate post-hoc pooled residual AR1 LOPO experiment scored120/120 but got1711.200m; it lost to ridge and lastdrift. This does NOT show absence of transferable structure. No improvement claim or promotion is justified. No new trajectories were acquired in the failed Indian extension. The NOAA hourly product may use later fixes during interpolation. All current drifters have been inspected already.

New software already implemented locally: read-only recorded tank trajectory replay starts from the first observation only, predicts at actual saved host-receipt offsets, forecasts all required runs before scoring later XY, fixed Euler<=0.05s, reflecting tank rectangle, no traps/diffusion. Unsupported interiors and reflected subsegments withhold whole runs; gaps stay missing. Recorded drift fits now reject reused recording/frame IDs. These are reviewed saved-recording diagnostics, NOT physical proof. The real USB camera/pump rig is not assembled; zero physical trials. Current tank flow is empirical token drift, not pure water current.

First compare THREE clearly different modeling mechanisms: (a) irregular-time constant-velocity Kalman state estimation, (b) spatial Gaussian-process drift with a support/uncertainty mask, (c) advection with observed HF-radar currents plus a learned residual. State what actual evidence each needs and why the other two should not be implemented on fictitious inputs today. NOAA's official IOOS current catalog is reachable, but no matched forcing field has been acquired. The tank needs new independent recordings, not a coastal API.

Then deliver an EXACT minimal specification for (a) as a new isolated post-hoc diagnostic, preserving every existing benchmark, pinned hash, report and source/prevention algorithm. Use NumPy, no new library/provider. SI state [x,y,vx,vy], actual irregular dt, H selects position. Choose and state ONE continuous-white-acceleration covariance convention with dimensionally correct Q(dt). Use Joseph covariance update and solves, not raw matrix inverse. Require finite strictly increasing prefix/forecast times, at least8 prefix points, all future times later than prefix end, bounded count/time/domain. Initialize from the first two prefix positions without using any later/future observation prematurely; all prefix observations may subsequently filter in chronological order.

For this first diagnostic FREEZE assumed position_std_m=100 and acceleration_spectral_density_m2_s3=1e-6 BEFORE its first new score; these are arbitrary declared modeling assumptions, NOT NOAA measurement uncertainties and NOT hyperparameters tuned to improve this viewed cohort. CSV err_ve/err_vn are velocity uncertainty columns (m/s), not position R and not automatically one-sigma. During forecasting, NO correction/update with held-out observations. Return means and finite symmetric PSD 2x2 position covariances; they are model-implied spread, not calibrated confidence or source probabilities. Explain whether forecast starts at filtered last training state or raw last observed position; keep it explicit.

New study planned denominator4groups*5models*6h=120 model/horizon outcomes. Compare fixed Kalman against the original stationary,last,mean,ridge models. Build ALL forecasts before reading any future lat/lon for scoring. Retain failures/null errors and withhold common aggregate if any required forecast fails. Previously viewed data must stay labeled POST_HOC_ALREADY_VIEWED, no independent/unseen/generalization/reef-impact claim. A separate synthetic irregular-camera-timing test proves numerical dt behavior but is never a physical measurement.

Return: 1) the three-way mechanism comparison; 2) exact algorithm and API function signature, assumptions/units/shape/budget contracts; 3) copyable minimal NumPy implementation for the standalone fit-and-forecast function; 4) six meaningful failure/leakage tests; 5) how to evaluate whether uncertainty is overconfident without calling six dependent points independent. Do not fabricate scores, datasets, a new training success or local execution. If the proposed freeze has a scientific flaw, state it concretely before code. We will execute/review code locally and return actual results to this same conversation.

REVIEW FOLLOW-UP
Static code review: your solve is dimensionally invalid: S is 2x2 but (H@P).T is 4x2. Correct K = np.linalg.solve(S, H@P).T. More importantly, initialization at t0 uses z1 to form velocity and then processes z1 as an independent observation: it double-uses that measurement and ignores position/velocity correlation. Please fix by defining state at t1 with p=z1, v=(z1-z0)/dt0; under independent isotropic measurement variance r, use Ppp=rI, Ppv=r/dt0 I, Pvv=2r/dt0^2 I (and clearly identify the assumption), then filter i=2 onward. No extra arbitrary1m/s prior. Include complete bounds actually enforced: prefix8..100, future1..12, finite1Dtimes and2Dpositions, forecast horizon<=24h, prefix duration<=7days, coordinates within50km, all predicted means within50km, positive finite noise values and each dt>=1e-6s. Empty tf must raise ValueError before indexing. Check all finite/symmetric/PSD intermediate covariances. Six tests should include actual guarded future properties that throw on access during prediction generation; mutating data after return proves nothing about leakage. Our q/r freeze stays100m,1e-6m²/s³, no tuning. Return corrected minimal function and exact test design. We will locally execute and report actual results; you are not executing. Preserve original frozen benchmark files.
````

### docs/grok-evidence/08-kalman-static-review.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/08-kalman-static-review.txt

Bytes: 22606; SHA-256: `95b1f47214b9dcd23f3b27c4ee6e85084a7c3676021463856457992140372899`. Role: saved Grok review/conversation capture; includes historical drafts and corrections. Quoted record; read the ledger for current status.

````text
Skip to main content
Toggle Sidebar
Chat
⌘J
Imagine
Library
Automations
Bots
Create a bot
Chats
Projects
ReefTrace — tracing, satellite context & ML
ReefTrace NOAA Drifter Benchmark Audit and Rolling-Origin Patch
Plugins
Jose C.
Grok
Worked for 4s

Static interpretation only. The pooled residual AR(1) mean error (1711 m) is higher than both the own-prefix ridge (729 m) and last-drift (1580 m) on the same four already-viewed drifters. The negative result shows that a single velocity-residual transition matrix estimated from the other three prefixes does not transfer usefully to the held prefix under the frozen protocol. Local residual dynamics, or simply the own-prefix mean and last velocity, already capture more of the six-hour motion than the shared residual memory.

The legitimate incremental value of the LOPO diagnostic is that it supplies a controlled, leakage-checked contrast—shared residual matrix versus the four original own-prefix algorithms—on data that had already been inspected. It quantifies the absence of transferable residual structure without promoting a model or rewriting the original 4/6 study. Because every trajectory was previously viewed, the exercise remains a post-hoc diagnostic, not an independent evaluation.

No dataset-improvement claim is justified. The Indian metadata request still returned zero trajectories, and the GTS, MDMAP and GLORYS sources remain researched but unacquired. Expanding spatial coverage inside the same interpolated hourly product, or adding an untested forcing field, would not convert this negative transfer result into evidence of better generalization or of interception benefit.

Future-only predeclared choices (not post-hoc search):

Alias-safe irregular-time GTS holdout with as-of receipt latency, excluding all physical-drifter aliases of the five viewed IDs.
One additional model allowed contemporaneous current forcing, with all hyperparameters and the forcing product version frozen on development data before any evaluation score.
You

One scientific correction before we finalize: this single pooled model's higher four-group mean does NOT establish the absence of transferable residual structure, nor prove local dynamics are the mechanism. It establishes only that this particular fixed pooled estimator performed worse on this already-viewed, four-group diagnostic under these settings. Other estimators, data quality, sampling dependence, and uncertainty remain unresolved. We will retain the negative result without a mechanistic or general impossibility claim. Please acknowledge this correction in two clear sentences; no new experiment or parameter search. We are publishing the local report with that narrower interpretation.

Grok

This single pooled residual AR(1) estimator’s higher four-group mean error shows only that this particular fixed model performed worse than the own-prefix ridge and last-drift baselines on this already-viewed four-group diagnostic under the frozen settings. It does not establish the absence of transferable residual structure, does not identify local dynamics as the mechanism, and leaves other estimators, data quality, sampling dependence and uncertainty unresolved.

You

Continue this SAME project and conversation. We are now calling the product Tideward; the repository and API remain reeftrace: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace . Current pushed commit 1a10cee07e4af8d515c7c66d143ee6da3be019cb. Do not create another project or claim you executed local code.  BUILD REQUEST: propose and specify a genuinely useful NEXT modeling experiment, with the physical tank as the intended eventual application. Here the UI/UX is being edited separately; your scope is modeling, experimental design, and reviewable implementation. No account/billing/Photon actions.  Verified current state: four already-viewed NOAA GDP buoy-days, each 24 hourly positions. Models fit the first18 and free-run six hours. Original study: 4 acquired of6 target,96 scored of144 planned model intervals,24 unique observed intervals reused across four models. Existing equal-buoy six-hour mean position errors: stationary2911.298m,lastdrift1579.850m,mean1846.713m,own-prefix ridge729.365m. A separate post-hoc pooled residual AR1 LOPO experiment scored120/120 but got1711.200m; it lost to ridge and lastdrift. This does NOT show absence of transferable structure. No improvement claim or promotion is justified. No new trajectories were acquired in the failed Indian extension. The NOAA hourly product may use later fixes during interpolation. All current drifters have been inspected already.  New software already implemented locally: read-only recorded tank trajectory replay starts from the first observation only, predicts at actual saved host-receipt offsets, forecasts all required runs before scoring later XY, fixed Euler<=0.05s, reflecting tank rectangle, no traps/diffusion. Unsupported interiors and reflected subsegments withhold whole runs; gaps stay missing. Recorded drift fits now reject reused recording/frame IDs. These are reviewed saved-recording diagnostics, NOT physical proof. The real USB camera/pump rig is not assembled; zero physical trials. Current tank flow is empirical token drift, not pure water current.  First compare THREE clearly different modeling mechanisms: (a) irregular-time constant-velocity Kalman state estimation, (b) spatial Gaussian-process drift with a support/uncertainty mask, (c) advection with observed HF-radar currents plus a learned residual. State what actual evidence each needs and why the other two should not be implemented on fictitious inputs today. NOAA's official IOOS current catalog is reachable, but no matched forcing field has been acquired. The tank needs new independent recordings, not a coastal API.  Then deliver an EXACT minimal specification for (a) as a new isolated post-hoc diagnostic, preserving every existing benchmark, pinned hash, report and source/prevention algorithm. Use NumPy, no new library/provider. SI state [x,y,vx,vy], actual irregular dt, H selects position. Choose and state ONE continuous-white-acceleration covariance convention with dimensionally correct Q(dt). Use Joseph covariance update and solves, not raw matrix inverse. Require finite strictly increasing prefix/forecast times, at least8 prefix points, all future times later than prefix end, bounded count/time/domain. Initialize from the first two prefix positions without using any later/future observation prematurely; all prefix observations may subsequently filter in chronological order.  For this first diagnostic FREEZE assumed position_std_m=100 and acceleration_spectral_density_m2_s3=1e-6 BEFORE its first new score; these are arbitrary declared modeling assumptions, NOT NOAA measurement uncertainties and NOT hyperparameters tuned to improve this viewed cohort. CSV err_ve/err_vn are velocity uncertainty columns (m/s), not position R and not automatically one-sigma. During forecasting, NO correction/update with held-out observations. Return means and finite symmetric PSD 2x2 position covariances; they are model-implied spread, not calibrated confidence or source probabilities. Explain whether forecast starts at filtered last training state or raw last observed position; keep it explicit.  New study planned denominator4groups*5models*6h=120 model/horizon outcomes. Compare fixed Kalman against the original stationary,last,mean,ridge models. Build ALL forecasts before reading any future lat/lon for scoring. Retain failures/null errors and withhold common aggregate if any required forecast fails. Previously viewed data must stay labeled POST_HOC_ALREADY_VIEWED, no independent/unseen/generalization/reef-impact claim. A separate synthetic irregular-camera-timing test proves numerical dt behavior but is never a physical measurement.  Return: 1) the three-way mechanism comparison; 2) exact algorithm and API function signature, assumptions/units/shape/budget contracts; 3) copyable minimal NumPy implementation for the standalone fit-and-forecast function; 4) six meaningful failure/leakage tests; 5) how to evaluate whether uncertainty is overconfident without calling six dependent points independent. Do not fabricate scores, datasets, a new training success or local execution. If the proposed freeze has a scientific flaw, state it concretely before code. We will execute/review code locally and return actual results to this same conversation.

Grok
Worked for 17s

Static specification only. No scores, datasets or execution are claimed. Existing benchmarks, hashes, reports and source/prevention algorithms stay untouched.

Scientific note on the freeze

Freezing position_std_m=100 and acceleration_spectral_density_m2_s3=1e-6 before the first score is acceptable only as an arbitrary declared process/measurement assumption for a post-hoc diagnostic. These values are not NOAA position uncertainties (err_ve/err_vn are velocity uncertainties in m/s and must not be used as 
𝑅
R), are not tuned, and produce model-implied covariances that are not calibrated confidence. The continuous-white-acceleration model can be misspecified for curved or biased motion; a worse mean error than own-prefix ridge would not prove absence of transferable structure.

1. Three-way mechanism comparison
(a) Irregular-time constant-velocity Kalman. Needs only the trajectory’s own irregular position times and coordinates. Useful as a post-hoc diagnostic on the already-viewed buoy-days and, later, on tank recordings. Implementable today with NumPy on existing data.
(b) Spatial Gaussian-process drift with support mask. Needs a dense set of independent drift observations that cover the domain of interest and a justified length-scale. The current tank has only empirical token-drift recordings; no new independent spatial samples exist. Do not implement on fictitious inputs.
(c) Advection by observed HF-radar currents plus learned residual. Needs a forcing field matched in space and time to the trajectory. NOAA IOOS catalogs are reachable, but no matched product has been acquired. Do not implement on fictitious currents.

Only (a) is specified below.

2. Exact algorithm and contracts

State 
𝑥
=
[
𝑥
,
𝑦
,
𝑣
𝑥
,
𝑣
𝑦
]
⊤
x=[x,y,v
x
	​

,v
y
	​

]
⊤
 (metres, m/s).

Transition 
𝐹
(
Δ
𝑡
)
=
[
𝐼
2
	
Δ
𝑡
 
𝐼
2


0
	
𝐼
2
]
F(Δt)=[
I
2
	​

0
	​

ΔtI
2
	​

I
2
	​

	​

].

Process noise (continuous white acceleration, spectral density 
𝑞
q):

𝑄
(
Δ
𝑡
)
=
𝑞
[
(
Δ
𝑡
)
3
/
3
	
(
Δ
𝑡
)
2
/
2


(
Δ
𝑡
)
2
/
2
	
Δ
𝑡
]
⊗
𝐼
2
.
Q(Δt)=q[
(Δt)
3
/3
(Δt)
2
/2
	​

(Δt)
2
/2
Δt
	​

]⊗I
2
	​

.

Measurement 
𝐻
=
[
𝐼
2
 
0
]
H=[I
2
	​

 0], 
𝑅
=
𝜎
𝑝
2
𝐼
2
R=σ
p
2
	​

I
2
	​

 with frozen 
𝜎
𝑝
=
100
 
m
σ
p
	​

=100m.

Update Joseph form; gain via solve on the innovation covariance, never raw inverse.

Initialization from the first two prefix positions only (velocity = 
Δ
𝑝
/
Δ
𝑡
Δp/Δt); all later prefix observations are then filtered in chronological order.

Forecast start explicit: free-run begins at the filtered state at the last prefix time (after all prefix updates), not at the raw last observation. No measurement update is applied to any future time.

Signature

Python
Copy
Copied
def kalman_cv_forecast(
    prefix_times_s: np.ndarray,   # (n,) strictly increasing, n>=8
    prefix_xy_m: np.ndarray,      # (n,2)
    forecast_times_s: np.ndarray, # (h,) strictly increasing, all > prefix_times_s[-1]
    *, position_std_m: float = 100.0,
    acceleration_spectral_density_m2_s3: float = 1e-6,
) -> tuple[np.ndarray, np.ndarray]:
    """Returns means (h,2) and position covariances (h,2,2), finite symmetric PSD."""

Budgets: 
8
≤
𝑛
≤
100
8≤n≤100, 
1
≤
ℎ
≤
12
1≤h≤12, times finite and inside a declared domain, positions inside the existing 50 km local budget.

3. Minimal NumPy implementation
Python
Copy
Copied
import numpy as np

def kalman_cv_forecast(prefix_times_s, prefix_xy_m, forecast_times_s, *,
                       position_std_m=100.0, acceleration_spectral_density_m2_s3=1e-6):
    t = np.asarray(prefix_times_s, float)
    z = np.asarray(prefix_xy_m, float)
    tf = np.asarray(forecast_times_s, float)
    if t.ndim != 1 or z.shape != (len(t), 2) or len(t) < 8:
        raise ValueError("prefix requires >=8 finite increasing times and (n,2) positions")
    if not (np.all(np.diff(t) > 0) and np.all(np.diff(tf) > 0) and tf[0] > t[-1]):
        raise ValueError("times must be strictly increasing; forecasts after prefix")
    if not np.isfinite(t).all() or not np.isfinite(z).all() or not np.isfinite(tf).all():
        raise ValueError("non-finite input")
    q, r = float(acceleration_spectral_density_m2_s3), float(position_std_m)**2
    # init from first two only
    dt0 = t[1] - t[0]
    x = np.array([z[0,0], z[0,1], (z[1,0]-z[0,0])/dt0, (z[1,1]-z[0,1])/dt0])
    P = np.diag([r, r, 1.0, 1.0])  # arbitrary initial velocity variance; not tuned
    H = np.array([[1,0,0,0],[0,1,0,0]])
    R = r * np.eye(2)
    def FQ(dt):
        F = np.eye(4); F[0,2] = F[1,3] = dt
        a, b, c = dt**3/3, dt**2/2, dt
        Q = q * np.block([[a*np.eye(2), b*np.eye(2)],[b*np.eye(2), c*np.eye(2)]])
        return F, Q
    # filter remaining prefix chronologically
    for i in range(1, len(t)):
        F, Q = FQ(t[i]-t[i-1])
        x = F @ x
        P = F @ P @ F.T + Q
        S = H @ P @ H.T + R
        K = np.linalg.solve(S, (H @ P).T).T          # solve, not inverse
        IKH = np.eye(4) - K @ H
        P = IKH @ P @ IKH.T + K @ R @ K.T             # Joseph
        x = x + K @ (z[i] - H @ x)
    # free-run from filtered last state; no future updates
    means, covs = [], []
    t_cur, x_cur, P_cur = t[-1], x.copy(), P.copy()
    for t_next in tf:
        F, Q = FQ(t_next - t_cur)
        x_cur = F @ x_cur
        P_cur = F @ P_cur @ F.T + Q
        means.append(x_cur[:2].copy())
        covs.append(0.5 * (P_cur[:2,:2] + P_cur[:2,:2].T))  # symmetrize
        t_cur = t_next
    return np.asarray(means), np.asarray(covs)
4. Six failure / leakage tests
Non-monotonic or non-finite prefix time raises before any state is formed.
Forecast time 
≤
≤ last prefix time raises.
Fewer than 8 prefix points raises.
Mutating a future lat/lon after the call returns does not change the returned means (forecasts were built without them).
Mutating a prefix position after index 1 changes the filtered state; mutating only the first two positions changes the initialization.
A singular or non-finite intermediate 
𝑆
S raises; the function never returns a non-symmetric or non-finite covariance.
5. Overconfidence check without treating dependent points as independent

Compute, per drifter, the fraction of the six forecast hours whose true position lies inside the model’s 50 % and 90 % position ellipses (Mahalanobis distance on the returned 2×2 covariance). Report the four drifter-level fractions and their min/max; do not average the 24 dependent point-wise indicators into a single coverage probability or claim calibration. A systematic shortfall (e.g., all four drifters below nominal 50 % coverage) indicates overconfidence of this frozen noise model on the viewed cohort; it does not establish a calibrated uncertainty or a transferable result.

You

Static code review: your solve is dimensionally invalid: S is 2x2 but (H@P).T is 4x2. Correct K = np.linalg.solve(S, H@P).T. More importantly, initialization at t0 uses z1 to form velocity and then processes z1 as an independent observation: it double-uses that measurement and ignores position/velocity correlation. Please fix by defining state at t1 with p=z1, v=(z1-z0)/dt0; under independent isotropic measurement variance r, use Ppp=rI, Ppv=r/dt0 I, Pvv=2r/dt0^2 I (and clearly identify the assumption), then filter i=2 onward. No extra arbitrary1m/s prior. Include complete bounds actually enforced: prefix8..100, future1..12, finite1Dtimes and2Dpositions, forecast horizon<=24h, prefix duration<=7days, coordinates within50km, all predicted means within50km, positive finite noise values and each dt>=1e-6s. Empty tf must raise ValueError before indexing. Check all finite/symmetric/PSD intermediate covariances. Six tests should include actual guarded future properties that throw on access during prediction generation; mutating data after return proves nothing about leakage. Our q/r freeze stays100m,1e-6m²/s³, no tuning. Return corrected minimal function and exact test design. We will locally execute and report actual results; you are not executing. Preserve original frozen benchmark files.

Grok
Worked for 4s

Static correction only. No execution is claimed. Original frozen benchmark files stay untouched. The declared freeze remains position_std_m=100, acceleration_spectral_density_m2_s3=1e-6.

Corrected initialization and solve

State is defined at 
𝑡
1
t
1
	​

: 
𝑝
=
𝑧
1
p=z
1
	​

, 
𝑣
=
(
𝑧
1
−
𝑧
0
)
/
Δ
𝑡
0
v=(z
1
	​

−z
0
	​

)/Δt
0
	​

.

Under the assumption of independent isotropic measurement variance 
𝑟
r on the two positions used for initialization:

𝑃
𝑝
𝑝
=
𝑟
𝐼
,
𝑃
𝑝
𝑣
=
(
𝑟
/
Δ
𝑡
0
)
𝐼
,
𝑃
𝑣
𝑣
=
(
2
𝑟
/
Δ
𝑡
0
2
)
𝐼
.
P
pp
	​

=rI,P
pv
	​

=(r/Δt
0
	​

)I,P
vv
	​

=(2r/Δt
0
2
	​

)I.

No extra velocity prior is introduced. Filtering then proceeds from index 2 onward.

Gain uses the dimensionally valid solve 
𝐾
=
np.linalg.solve
(
𝑆
,
𝐻
@
𝑃
)
.
𝑇
K=np.linalg.solve(S,H@P).T.

Corrected function
Python
Copy
Copied
import numpy as np

_MAX_LOCAL_M = 50_000.0
_MIN_DT_S = 1e-6
_MAX_PREFIX_S = 7 * 86400
_MAX_HORIZON_S = 24 * 3600

def _check_cov(P, name):
    if P.shape != (4, 4) or not np.isfinite(P).all():
        raise ValueError(f"{name} non-finite")
    if not np.allclose(P, P.T, atol=1e-8):
        raise ValueError(f"{name} not symmetric")
    # PSD via eigenvalues of symmetrized matrix
    ev = np.linalg.eigvalsh(0.5 * (P + P.T))
    if np.any(ev < -1e-8):
        raise ValueError(f"{name} not PSD")

def kalman_cv_forecast(prefix_times_s, prefix_xy_m, forecast_times_s, *,
                       position_std_m=100.0, acceleration_spectral_density_m2_s3=1e-6):
    t = np.asarray(prefix_times_s, float)
    z = np.asarray(prefix_xy_m, float)
    tf = np.asarray(forecast_times_s, float)
    if t.ndim != 1 or not 8 <= len(t) <= 100 or z.shape != (len(t), 2):
        raise ValueError("prefix requires 8..100 finite times and matching (n,2) positions")
    if tf.ndim != 1 or not 1 <= len(tf) <= 12:
        raise ValueError("forecast_times requires 1..12 entries; empty is invalid")
    if not np.isfinite(t).all() or not np.isfinite(z).all() or not np.isfinite(tf).all():
        raise ValueError("non-finite input")
    if not (np.all(np.diff(t) >= _MIN_DT_S) and np.all(np.diff(tf) >= _MIN_DT_S) and tf[0] > t[-1]):
        raise ValueError("times must be strictly increasing by >=1e-6 s; forecasts after prefix")
    if t[-1] - t[0] > _MAX_PREFIX_S or tf[-1] - t[-1] > _MAX_HORIZON_S:
        raise ValueError("prefix duration >7 d or forecast horizon >24 h")
    if np.linalg.norm(z, axis=1).max() > _MAX_LOCAL_M:
        raise ValueError("prefix positions exceed 50 km")
    q = float(acceleration_spectral_density_m2_s3)
    sig = float(position_std_m)
    if not (np.isfinite(q) and q > 0 and np.isfinite(sig) and sig > 0):
        raise ValueError("noise parameters must be positive finite")
    r = sig ** 2
    # state at t1 from first two observations only
    dt0 = t[1] - t[0]
    v0 = (z[1] - z[0]) / dt0
    x = np.array([z[1, 0], z[1, 1], v0[0], v0[1]])
    P = np.block([
        [r * np.eye(2), (r / dt0) * np.eye(2)],
        [(r / dt0) * np.eye(2), (2 * r / dt0**2) * np.eye(2)],
    ])
    _check_cov(P, "P_init")
    H = np.array([[1., 0, 0, 0], [0, 1, 0, 0]])
    R = r * np.eye(2)
    def FQ(dt):
        F = np.eye(4)
        F[0, 2] = F[1, 3] = dt
        a, b, c = dt**3 / 3, dt**2 / 2, dt
        Q = q * np.block([[a*np.eye(2), b*np.eye(2)], [b*np.eye(2), c*np.eye(2)]])
        return F, Q
    # filter i=2 onward
    for i in range(2, len(t)):
        F, Q = FQ(t[i] - t[i-1])
        x = F @ x
        P = F @ P @ F.T + Q
        _check_cov(P, "P_pred")
        S = H @ P @ H.T + R
        K = np.linalg.solve(S.T, (H @ P).T).T   # K = solve(S, H@P).T
        IKH = np.eye(4) - K @ H
        P = IKH @ P @ IKH.T + K @ R @ K.T
        _check_cov(P, "P_upd")
        x = x + K @ (z[i] - H @ x)
    # free-run from filtered state at last prefix time; no future updates
    means, covs = [], []
    t_cur, x_cur, P_cur = t[-1], x.copy(), P.copy()
    for t_next in tf:
        F, Q = FQ(t_next - t_cur)
        x_cur = F @ x_cur
        P_cur = F @ P_cur @ F.T + Q
        _check_cov(P_cur, "P_forecast")
        mean = x_cur[:2].copy()
        if np.linalg.norm(mean) > _MAX_LOCAL_M:
            raise ValueError("predicted mean exceeds 50 km")
        means.append(mean)
        c = P_cur[:2, :2]
        covs.append(0.5 * (c + c.T))
        t_cur = t_next
    return np.asarray(means), np.asarray(covs)
Exact test design (six cases)
Empty / short future. forecast_times_s=np.array([]) or length 0 raises ValueError before any indexing of tf[0].
Guarded future access. Wrap future lat/lon arrays in a property that raises on __getitem__ or __array__. Call the function with only prefix data; the property must not be touched during prediction generation.
Held-prefix isolation. Fit on prefixes of three drifters; mutate a coordinate inside the held prefix after the shared matrix (here the filter state) is frozen; the already-returned forecast means stay identical.
Initialization uses only first two. Mutate z[2] before the call; the initial state (before the loop) depends only on z[0], z[1]. Mutate z[0] or z[1] and the initial velocity changes.
Bound enforcement. Prefix length 7, a dt<1e-6, a coordinate at 50 km+1 m, or a noise value ≤0 each raise before any forecast is returned.
Covariance contract. Inject a non-finite intermediate by extreme but legal inputs; _check_cov raises. On success every returned 2×2 block is finite, symmetric and PSD.

These tests guard access and contracts; post-return mutation of caller arrays is not used as a leakage proof.

Return complete corrected file with tests in Python
Show the corrected initialization code
Give me the full corrected function




Fast
Type a message to send
Attach to message
Drop here to add files to your message
Grok finished responding
````

### docs/grok-evidence/09-kalman-draft-code.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/09-kalman-draft-code.txt

Bytes: 3533; SHA-256: `3211491b5637ec173f4206042df41672a6d4e9b7d42072e1b015a589cf4179c5`. Role: saved draft; not the authoritative current implementation. Quoted record; read the ledger for current status.

````text
import numpy as np

_MAX_LOCAL_M = 50_000.0
_MIN_DT_S = 1e-6
_MAX_PREFIX_S = 7 * 86400
_MAX_HORIZON_S = 24 * 3600

def _check_cov(P, name):
    if P.shape != (4, 4) or not np.isfinite(P).all():
        raise ValueError(f"{name} non-finite")
    if not np.allclose(P, P.T, atol=1e-8):
        raise ValueError(f"{name} not symmetric")
    # PSD via eigenvalues of symmetrized matrix
    ev = np.linalg.eigvalsh(0.5 * (P + P.T))
    if np.any(ev < -1e-8):
        raise ValueError(f"{name} not PSD")

def kalman_cv_forecast(prefix_times_s, prefix_xy_m, forecast_times_s, *,
                       position_std_m=100.0, acceleration_spectral_density_m2_s3=1e-6):
    t = np.asarray(prefix_times_s, float)
    z = np.asarray(prefix_xy_m, float)
    tf = np.asarray(forecast_times_s, float)
    if t.ndim != 1 or not 8 <= len(t) <= 100 or z.shape != (len(t), 2):
        raise ValueError("prefix requires 8..100 finite times and matching (n,2) positions")
    if tf.ndim != 1 or not 1 <= len(tf) <= 12:
        raise ValueError("forecast_times requires 1..12 entries; empty is invalid")
    if not np.isfinite(t).all() or not np.isfinite(z).all() or not np.isfinite(tf).all():
        raise ValueError("non-finite input")
    if not (np.all(np.diff(t) >= _MIN_DT_S) and np.all(np.diff(tf) >= _MIN_DT_S) and tf[0] > t[-1]):
        raise ValueError("times must be strictly increasing by >=1e-6 s; forecasts after prefix")
    if t[-1] - t[0] > _MAX_PREFIX_S or tf[-1] - t[-1] > _MAX_HORIZON_S:
        raise ValueError("prefix duration >7 d or forecast horizon >24 h")
    if np.linalg.norm(z, axis=1).max() > _MAX_LOCAL_M:
        raise ValueError("prefix positions exceed 50 km")
    q = float(acceleration_spectral_density_m2_s3)
    sig = float(position_std_m)
    if not (np.isfinite(q) and q > 0 and np.isfinite(sig) and sig > 0):
        raise ValueError("noise parameters must be positive finite")
    r = sig ** 2
    # state at t1 from first two observations only
    dt0 = t[1] - t[0]
    v0 = (z[1] - z[0]) / dt0
    x = np.array([z[1, 0], z[1, 1], v0[0], v0[1]])
    P = np.block([
        [r * np.eye(2), (r / dt0) * np.eye(2)],
        [(r / dt0) * np.eye(2), (2 * r / dt0**2) * np.eye(2)],
    ])
    _check_cov(P, "P_init")
    H = np.array([[1., 0, 0, 0], [0, 1, 0, 0]])
    R = r * np.eye(2)
    def FQ(dt):
        F = np.eye(4)
        F[0, 2] = F[1, 3] = dt
        a, b, c = dt**3 / 3, dt**2 / 2, dt
        Q = q * np.block([[a*np.eye(2), b*np.eye(2)], [b*np.eye(2), c*np.eye(2)]])
        return F, Q
    # filter i=2 onward
    for i in range(2, len(t)):
        F, Q = FQ(t[i] - t[i-1])
        x = F @ x
        P = F @ P @ F.T + Q
        _check_cov(P, "P_pred")
        S = H @ P @ H.T + R
        K = np.linalg.solve(S.T, (H @ P).T).T   # K = solve(S, H@P).T
        IKH = np.eye(4) - K @ H
        P = IKH @ P @ IKH.T + K @ R @ K.T
        _check_cov(P, "P_upd")
        x = x + K @ (z[i] - H @ x)
    # free-run from filtered state at last prefix time; no future updates
    means, covs = [], []
    t_cur, x_cur, P_cur = t[-1], x.copy(), P.copy()
    for t_next in tf:
        F, Q = FQ(t_next - t_cur)
        x_cur = F @ x_cur
        P_cur = F @ P_cur @ F.T + Q
        _check_cov(P_cur, "P_forecast")
        mean = x_cur[:2].copy()
        if np.linalg.norm(mean) > _MAX_LOCAL_M:
            raise ValueError("predicted mean exceeds 50 km")
        means.append(mean)
        c = P_cur[:2, :2]
        covs.append(0.5 * (c + c.T))
        t_cur = t_next
    return np.asarray(means), np.asarray(covs)
````

### docs/grok-evidence/10-fresh-protocol-static-review.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/10-fresh-protocol-static-review.txt

Bytes: 2537; SHA-256: `17d3d375fb15e302d9a95c0dfc648ebc7738ef58b02077110bc1c55686b44164`. Role: saved Grok static protocol review output. Quoted record; read the ledger for current status.

````text
Grok
Worked for 20s

Must-fix issues before acquisition (static). No execution claimed.

Pin the global ID↔WMO identity snapshot. The protocol requires “one positive canonical WMO per ID” and exclusion of every known reserved WMO, yet it only hashes exclusions.json. Without a separate frozen, hashed global ID,WMO&distinct() payload (and its detached SHA-256) written before any per-block metadata query, “known positive reserved WMO” and “candidate snapshot WMO must agree” cannot be re-derived deterministically.
Treat unresolved reserved aliases as reported, not silently ignored. Keep the stated policy (do not block solely because old aliases are unresolved), but the selection receipt must list every reserved GDP ID whose WMO is missing or ambiguous and set physical_alias_resolution_verified=false. Omitting that list would over-claim alias completeness.

No other must-fix is required for the frozen model set, budgets, no-replacement rule, or 180-cell failure policy.

Minimal pseudocode

Python
Copy
Copied
def rederive_selection(exclusions, identity_bytes, block_metadata_bytes):
    if sha256(identity_bytes) != PINNED_IDENTITY_SHA:
        raise ValueError("identity snapshot mismatch")
    reserved_gdp = set(exclusions["gdp_ids"])
    reserved_wmo = {row["WMO"] for row in parse(identity_bytes)
                    if row["ID"] in reserved_gdp and row["WMO"]}
    unresolved = [i for i in reserved_gdp if not any(
        r["ID"] == i and r["WMO"] for r in parse(identity_bytes))]
    selected = []
    for block in BLOCKS:  # ordered
        rows = parse(block_metadata_bytes[block["id"]])
        eligible = []
        for row in rows:
            if (row["ID"] in reserved_gdp or row["WMO"] in reserved_wmo
                    or row["ID"] in {s["ID"] for s in selected}
                    or not is_positive_unambiguous(row["WMO"], identity_bytes)):
                continue
            eligible.append(row["ID"])
        selected.extend(sorted(set(eligible), key=int)[:2])
    return selected, unresolved  # freeze these + hashes BEFORE any trajectory request

def forecasts_before_truth(prefix, models):
    forecasts = {m: model_forecast(prefix, m) for m in models}  # no future access
    return forecasts  # truth read only after this returns

def account(outcomes, target=180):
    if len(outcomes) != target or any(o["status"] != "SCORED" for o in outcomes):
        return {"macro": None, "reason": "INCOMPLETE"}  # per-group rows stay visible
    return {"macro": equal_group_means(outcomes)}
````

### docs/grok-evidence/11-fresh-schema-static-review.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/11-fresh-schema-static-review.txt

Bytes: 2501; SHA-256: `ea3e9ca9a9a3542b7bf3db62dd69ddcd50731d38d3c85bbb7f1c25bc32ef7638`. Role: saved Grok static schema/amendment review output. Quoted record; read the ledger for current status.

````text
Grok
Worked for 4s

Static review only. No trajectories or model outcomes were acquired; v1 selected zero groups. The amendment does not induce outcome-based tuning: no scores exist, the 223 exclusions, three blocks, five models and no-replacement rule are unchanged, and the edits are limited to a pre-outcome schema/transport correction (unit-row token, timeouts). The v1 global alias catalog is a registry, not a training cohort.

CSV reader fix (unit row, oversized field, invalid UTF-8, absolute deadline)

Python
Copy
Copied
import csv, time
from io import StringIO

def read_metadata_csv(payload: bytes, *, max_bytes: int, deadline: float):
    if time.monotonic() > deadline:
        raise TimeoutError("absolute acquisition deadline exceeded")
    if len(payload) > max_bytes:
        raise ValueError("metadata exceeds byte budget")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("invalid UTF-8 in metadata") from exc
    # NOAA ERDDAP: row 0 = names, row 1 = units (expno unit is "count", not "")
    rows = list(csv.reader(StringIO(text)))
    if len(rows) < 2 or rows[0] != EXPECTED_COLUMNS:
        raise ValueError("metadata header mismatch")
    if rows[1][rows[0].index("expno")] != "count":
        raise ValueError("expno unit must be count")
    return rows[2:]  # data only

Tests

Python
Copy
Copied
def test_unit_row_accepts_count():
    payload = b"ID,time,latitude,longitude,WMO,expno,location_type\n,,degrees_north,degrees_east,,count,\n1,..."
    assert read_metadata_csv(payload, max_bytes=300_000, deadline=time.monotonic()+10)

def test_oversized_and_bad_utf8():
    with pytest.raises(ValueError, match="byte budget"):
        read_metadata_csv(b"x"*300_001, max_bytes=300_000, deadline=time.monotonic()+10)
    with pytest.raises(ValueError, match="UTF-8"):
        read_metadata_csv(b"\xff", max_bytes=300_000, deadline=time.monotonic()+10)

def test_deadline():
    with pytest.raises(TimeoutError):
        read_metadata_csv(b"ID,...\n", max_bytes=300_000, deadline=time.monotonic()-1)

Adversarial note. Because v1 produced zero selections and zero scores, lengthening timeouts and accepting the official count unit cannot be outcome-driven. Freeze the new protocol hash and the corrected reader hash before any v2 request; any later change after a score appears must fail closed. The honest claim remains previously unscored GDP-ID groups with held future positions, not proven physical independence.
````

### docs/grok-evidence/12-fresh-forecast-static-review.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/12-fresh-forecast-static-review.txt

Bytes: 1514; SHA-256: `d309cba3606ad9370caf764e3ae2961e5890dd835d084cb6fa116925e451e8c8`. Role: saved Grok static evaluator review output. Quoted record; read the ledger for current status.

````text
Grok
Worked for 33s

Static review only. No execution or accuracy claim.

No must-fix numerical or causality bug.

Forecasts before future coordinates. _prepare builds every model track from the 18-point prefix (xy, times) and future times only. Future latitude_deg/longitude_deg properties are read only later in _score via _point(..., limited=False). All 30 tracks (6 groups × 5 models) are therefore materialized before any future position access.
Free-running vectors. Velocity residuals start from forecast_anchor (filtered state for Kalman, raw last prefix position otherwise) and then step with predicted versus observed displacements. No reset to truth.
Invalid future truth. Any unavailable held-out point sets full_truth=False, withholds the whole model track, stores nullable points, and leaves the 6 cells failed. Far future truth uses limited=False and is not rejected by the 50 km forecast-domain cap; forecast means still pass through frame.to_latlon (50 km enforced).
Failure accounting. scored counts only complete scored rows; failed_outcomes = attempted - scored; common-target metrics and COMPLETED are emitted only when scored==180. Per-group rows remain visible on partial failure.
Intervals. Schema enforcement of exact hourly UTC windows makes adjacent intervals unique by construction; no additional silent filter is applied.

The implementation matches the frozen protocol’s causality and accounting rules. No change is required before the local leakage tests and the pre-score freeze.
````

### docs/grok-evidence/13-algorithm-and-demo-static-review.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/13-algorithm-and-demo-static-review.txt

Bytes: 4628; SHA-256: `46055e3c673caf64cb6b1bb2e81c637ecd1de5092d2c0b4cb69eea88e6d665b4`. Role: saved Grok static algorithm/demo review; later corrected in item 14. Quoted record; read the ledger for current status.

````text
Grok

State and transition audit (static). The displayed contracts match the frozen implementation. State is 
[
𝑥
,
𝑦
,
𝑣
𝑥
,
𝑣
𝑦
]
⊤
[x,y,v
x
	​

,v
y
	​

]
⊤
 (m, m/s).

𝐹
(
Δ
𝑡
)
=
[
𝐼
2
	
Δ
𝑡
 
𝐼
2


0
	
𝐼
2
]
,
𝑄
(
Δ
𝑡
)
=
𝑞
[
(
Δ
𝑡
)
3
/
3
	
(
Δ
𝑡
)
2
/
2


(
Δ
𝑡
)
2
/
2
	
Δ
𝑡
]
⊗
𝐼
2
F(Δt)=[
I
2
	​

0
	​

ΔtI
2
	​

I
2
	​

	​

],Q(Δt)=q[
(Δt)
3
/3
(Δt)
2
/2
	​

(Δt)
2
/2
Δt
	​

]⊗I
2
	​


with 
𝑞
=
1
×
10
−
6
 
m
2
/
s
3
q=1×10
−6
m
2
/s
3
. 
𝐻
=
[
𝐼
2
 
0
]
H=[I
2
	​

 0], 
𝑅
=
(
100
 
m
)
2
𝐼
2
=
10000
 
m
2
𝐼
2
R=(100m)
2
I
2
	​

=10000m
2
I
2
	​

 (not 
100
 
m
2
100m
2
). Initialization at the second prefix position uses the first-difference velocity and the correlated 
𝑃
𝑝
𝑝
=
𝑟
𝐼
P
pp
	​

=rI, 
𝑃
𝑝
𝑣
=
(
𝑟
/
Δ
𝑡
)
𝐼
P
pv
	​

=(r/Δt)I, 
𝑃
𝑣
𝑣
=
(
2
𝑟
/
Δ
𝑡
2
)
𝐼
P
vv
	​

=(2r/Δt
2
)I. Later updates use 
𝐾
=
s
o
l
v
e
(
𝑆
,
𝐻
@
𝑃
)
⊤
K=solve(S,H@P)
⊤
 and the Joseph form. The six-hour free-run applies no future measurement update. Ellipse hits compare the observation residual to 
𝑃
𝑥
𝑦
+
𝑅
P
xy
	​

+R, not to latent 
𝑃
P alone. Ridge uses fixed 
𝛼
=
1
α=1 and spectral-radius cap 0.98 on its own 18-position prefix. NOAA metre results and tank centimetre work remain distinct; the 100 m noise is not transferable.

Failure modes that must stay visible. Incomplete prefix, non-monotonic or sub-microsecond 
Δ
𝑡
Δt, non-finite or out-of-domain (50 km) forecast mean, singular innovation covariance, and any missing held-out truth all produce explicit failed cells. Common-cohort ADE/FDE/vector-RMSE are withheld unless all 180 cells score. Nominal ellipse-hit counts are labeled non-calibrated. The ten unresolved old aliases and physical_alias_resolution_verified=false remain displayed. No parameter is changed to hide these.

Kalman state versus application case state. The Kalman vector is a latent motion estimate inside one prefix. Application UNKNOWN means the source estimator could not rank candidates; INVALID means calibration or association failed; STOP freezes a case against further mutation; a revision or archived plan means the bound evidence ID no longer matches. These are orthogonal. Source relative support is a conditional score on a declared candidate set, not a calibrated probability. Tank diffusion and first trap entry are a separate particle comparison on measured layouts; they do not inherit NOAA buoy parameters.

Demo-first three-step story.

Observe and trace: load the synthetic trajectory, compute source support, show Ranked / Unknown / Invalid.
Compare two interception layouts: freeze baseline and intervention, display first zone entry versus capture-before-entry with unsupported paths kept in the denominator.
Explain and verify: open the frozen evidence IDs, read the deterministic briefing, and confirm satellite context did not alter the source ranking.

Graph legends: solid line = recorded path, dashed line = free-run forecast, filled dot = start, axes in hours and equal metres. No caption may imply measured currents or a plastic source. Protocol hashes, noise assumptions and full receipts move to a details drawer; synthetic / physical / unresolved flags stay on the main card.

Correction of prior claim. One complete held-out tank track does not authorize a layout decision. The application requires independently measured flow fields per layout, spatial and path-coverage gates, rig revalidation, a frozen comparison plan, and independent releases whose truth is stored only in the evaluation ledger. Three exploratory tracks may fail those gates; negative or incomplete results remain visible.

Bounded primary-source proposals. Continue to cite only the NOAA AOML GDP hourly and real-time pages for interpolation and WMO-mapping caveats, and the Copernicus multi-year physics product page for assimilation limits. No new acquisition or score is requested in this study.

Software-only handoff prompts.

Megana: verify the three-step demo path, legend clarity, and that synthetic/physical/unresolved flags survive browser zoom and screen-reader traversal; no hardware changes.
Aarush: add export/validator tests that an archived plan cannot explain current evidence, that trial-key replay is idempotent, and that a missing outcome cell withholds the common macro while preserving the failed row.

No frozen algorithm, noise value, provider credential, Photon message or automation change is in scope.
````

### docs/grok-evidence/14-final-accounting-conversation-capture.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/14-final-accounting-conversation-capture.txt

Bytes: 9530; SHA-256: `a5062e2d165c066f8c18afdb7104cdc0cccf4119bd6367e325a1446495f3b151`. Role: saved browser accessibility-text capture, including repeated/corrected historical messages. Quoted record; read the ledger for current status.

````text
 for 7s":
        - generic: Worked for 7s
      - paragraph:
        - strong: Acknowledged corrections.
        - text: UNKNOWN and INVALID are scientific SourceReport statuses, not values of the stored CaseState enum; a case may remain INVESTIGATE while its source report is invalid. Chalk finish(action=STOP) ends only the bounded model turn and does not call Store.stop_case. An explicit case stop increments revision, cancels proposed or awaiting-human tasks, and archives comparisons by lineage. The trial API accepts an out-of-plan release order but records order_followed=false; it rejects duplicate or conflicting trial keys and quota violations, so order is not server-enforced. Stock source “Load demo” and stock prevention “Load demo” use separate synthetic case fixtures; a guide must not imply one case continues through both. Trajectory plots use metre axes for both X and Y, with hours as point labels; they are not time-versus-position charts.
      - paragraph:
        - strong: One software-only next mathematical audit (Aarush handoff, synthetic fixtures only).
        - text: Audit discrete probability-mass and first-passage conservation on the existing synthetic particle fixtures, without altering any frozen model, noise value, physics threshold or completed NOAA study.
      - paragraph:
        - strong: Invariants.
      - list:
        - text: After every time step the sum of probability mass on free particles, absorbed protected-zone particles and absorbed collector particles equals 1 within
        - math:
          - generic: "10"
          - generic: −
          - generic: "12"
        - text: "1"
        - text: "0"
        - generic: −12
        - text: .
        - text: A particle that has entered the protected zone or a collector at step
        - math:
          - generic: k
        - generic: k
        - text: remains in that absorbing set for all later steps.
        - listitem: The reported first-passage time equals the earliest step at which the particle’s position lies inside the corresponding polygon, using the same seeded time nodes as the production stepper.
        - listitem: Unsupported or out-of-domain particles are counted in the denominator and never dropped.
      - paragraph:
        - strong: Failure cases.
      - list:
        - listitem: Inject a single particle that should be absorbed at a known step; assert mass is conserved and the first-passage index matches.
        - listitem: Force one particle outside the domain; assert it is retained as unsupported and the robust-recommendation flag is withheld.
        - listitem: Replay the identical fixture twice; assert identical mass vectors and passage times (idempotent under fixed seed).
      - paragraph: No equation, threshold or NOAA artifact is modified.
    - group "Grok":
      - button "Copy response":
      - button "Like":
      - button "Dislike":
      - button "Regenerate":
      - button "More actions":
    - article "You":
      - heading "You" [level=2]
      - paragraph: "Code-grounded correction for your proposed audit: destination categories are Z=protected-zone first competing absorption, T=any configured non-zone retention trap, F=no event by horizon; Z+T+F=N exactly. Support S is orthogonal, giving six disjoint cells Z&S, Z&~S, T&S, T&~S, F&S, F&~S. Unsupported_count cannot be added as a fourth destination. Equal 1/N particle weights; no source/age priors here. Overlapping/touching/nonfinite profiles rejected at config validation, not dropped particles. Admitted initially unsupported particles retain N. Production checks finite seeded nodes and reflected segments for event ordering; do not promise exact continuous flow or invent 1e-12. Independent six-cell synthetic example all counts 1, unsupported 3 gives zone bounds 1/6..4/6. Review these invariants for conceptual error and describe in <=250 words how a judge should read the two layout maps and uncertainty bounds without believing it proves tank benefit. All current 180 NOAA outcomes frozen, last drift best, no parameter/code/data changes requested. Existing Grok research automation paused and only push CI."
    - button "Edit":
    - group "You":
      - button "Edit":
      - button "Copy":
      - button "Save":
    - article "Grok":
      - heading "Grok" [level=2]
      - button "Worked for 6s":
        - generic: Worked for 6s
      - paragraph:
        - strong: Invariant review.
        - text: "The corrected partition is conceptually sound. Destinations are mutually exclusive and exhaustive: Z (protected-zone first competing absorption), T (any configured non-zone retention trap), and F (no event by horizon) satisfy"
        - math:
          - generic: Z
          - generic: +
          - generic: T
          - generic: +
          - generic: F
          - generic: =
          - generic: "N"
        - generic: Z +
        - generic: T +
        - generic: F =
        - generic: "N"
        - text: exactly. Support
        - math:
          - generic: S
        - generic: S
        - text: is an orthogonal attribute, yielding the six disjoint cells
        - math:
          - generic: Z
          - generic: "&"
          - generic: S
        - generic: Z&S
        - text: ","
        - math:
          - generic: Z
          - generic: "&"
          - generic: ∼
          - generic: S
        - generic: Z& ∼
        - generic: S
        - text: ","
        - math:
          - generic: T
          - generic: "&"
          - generic: S
        - generic: T&S
        - text: ","
        - math:
          - generic: T
          - generic: "&"
          - generic: ∼
          - generic: S
        - generic: T& ∼
        - generic: S
        - text: ","
        - math:
          - generic: F
          - generic: "&"
          - generic: S
        - generic: F&S
        - text: ","
        - math:
          - generic: F
          - generic: "&"
          - generic: ∼
          - generic: S
        - generic: F& ∼
        - generic: S
        - text: . Unsupported count is therefore not a fourth destination and must not be added to
        - math:
          - generic: Z
          - generic: +
          - generic: T
          - generic: +
          - generic: F
        - generic: Z +
        - generic: T +
        - generic: F
        - text: . Equal
        - math:
          - generic: "1"
          - generic: /
          - generic: "N"
        - generic: 1/N
        - text: particle weights with no source or age priors are consistent with the existing unweighted first-passage design. Overlapping, touching or non-finite profiles are rejected at configuration validation rather than by dropping particles, and initially unsupported but admitted particles remain inside
        - math:
          - generic: "N"
        - generic: "N"
        - text: . Production ordering uses finite seeded nodes and reflected segments; no claim of exact continuous-flow integration or a specific floating-point tolerance is required.
      - paragraph:
        - strong: How a judge should read the maps and bounds.
        - text: Each layout map shows the same declared particle set under one frozen flow and one frozen collector arrangement. A particle is counted in Z only if the protected-zone polygon is the first absorbing set it meets, in T if a non-zone trap absorbs it first, and in F if neither occurs by the horizon. The six-cell split further marks whether that particle’s prefix was supported. The reported zone bounds (for example 1/6 to 4/6 when three of six cells are unsupported) are the minimum and maximum fraction of the fixed
        - math:
          - generic: "N"
        - generic: "N"
        - text: that can be placed in Z once unsupported particles are assigned entirely against or entirely for the zone. These bounds are accounting statements about the synthetic particle set under the declared polygons and seeded steps. They do not measure a physical tank current, do not incorporate release-rate or effort controls, and do not demonstrate that either layout reduces debris reaching a protected area. A lower upper bound on one layout is a numerical comparison only; it becomes evidence of benefit solely after independent physical trials with measured per-layout flows, pre-registered releases, and an evaluation ledger that keeps truth separate from the prediction path. All 180 NOAA outcomes remain frozen, last-drift remains the lowest descriptive aggregate, and no parameter, code or data change is proposed.
    - group "Grok":
      - button "Copy response":
      - button "Like":
      - button "Dislike":
      - button "Regenerate":
      - button "More actions":
    - button "Rewrite for judge clarity and add uncertainty bounds":
      - generic: Rewrite for judge clarity and add uncertainty bounds
    - button "Explain the six disjoint cells":
      - generic: Explain the six disjoint cells
    - button "Draft a short summary in simpler terms":
      - generic: Draft a short summary in simpler terms
  - textbox "Ask Grok anything" [active]:
    - paragraph: Ask anything
  - button "Attach":
  - 'button "Model: Fast"':
    - generic: Fast
  - button "Dictation (⌃D)":
  - button "Submit" [disabled]:
    - generic: Type a message to send
  - generic: Attach to message
  - generic: Drop here to add files to your message
- region "Notifications alt+T"
- status: Grok finished responding
- alert
- alert: ReefTrace NOAA Drifter Benchmark Audit and Rolling-Origin Patch - Grok
````

### docs/grok-evidence/rk4-knot-review-prompt.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/rk4-knot-review-prompt.txt

Bytes: 18615; SHA-256: `0d9f7638b60aca4994d09e4461aafe16afe71fa524a68ea190a0ce32f109261d`. Role: actual outbound Grok web prompt: initial forcing-knot and expiry review. Quoted record; read the ledger for current status.

````text
Tideward / ReefTrace numerical-method development review, 17 October 2026.
Use this existing project and conversation. Repository: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace at checkpoint 662d1ac583b5c6e04aa43e74fdd2340218371934.

You are reviewing an actual bounded RK4 implementation; do not claim repository execution or make changes remotely. We will implement and run the approved patch locally, then return real results for adversarial review. No sponsor API calls, credentials, billing, Photon messages, tank measurements or model/holdout retuning are authorized. The completed NOAA GDP study stays frozen; last drift beat ridge and Kalman descriptively. This work improves numerical reliability, not measured plastic-prediction skill.

Current code uses a real pinned PacIOOS ROMS 4 km/3-hour surface u/v snapshot, bilinear spatial interpolation and linear temporal interpolation. RK4 samples at changing latitude, longitude and time, converts east/north m/s to geographic derivatives using WGS84 metric factors, and stops on unsupported masks/domain/time. Every layout uses the same six hypothetical paths and equal 2,000 m ideal absorbing line; geometry is a reef proxy, not an engineered real deployment. Default downstream counts are baseline 6, central 2, flanking 4; the original no-entry control ties at zero. The downstream proxy was chosen after preview, so it remains exploratory.

Local source audit found two generic irregular-forcing problems:
1. With spatially uniform eastward u=[0,1,0] m/s at forcing times [0,650,1400] seconds, northward v=0, latitude=0, step=300 s, output/horizon=1000 s, current output displacement is 589.743589744 m. Exact integration of that piecewise-linear forcing is 593.333333333 m. An RK4 step crossing the 650 s derivative break causes the discrepancy. Split at the forcing knot and the piecewise-linear time-only integral is recovered.
2. With last forcing time 1400 s, requested horizon 1800 s, step=300 s and output=900 s, the current code discards a step crossing the end and reports only 1200 s. It should retain the still-supported path through 1400 s, then report PARTIAL / OUTSIDE_FORCING_TIME for the unmet remainder. It must never extrapolate or zero-fill.

Proposed exact scope:
- Bound each accepted dt by the next strictly future forcing knot, the existing speed/cell/max-step limit, next output and requested horizon, relative to arbitrary start offset.
- Handle exact final time, irregular times, arbitrary offset, precision/zero-length dt, missing future mask corners and MAX_STEPS accounting explicitly. Stop deterministically if no supported positive step remains.
- Preserve the RK4 formula, WGS84 axes, strict contributing-corner mask policy, six releases, geometry, scoring and immutable raw dataset. Default snapshot knots are already aligned at 10,800 s intervals, so paths/counts should remain numerically unchanged. The method hash must change because source changes; do not reuse old hashes or overwrite historical receipts.
- Tests must reproduce both current failures with independently derived analytic expectations, nonzero start offset, exact-knot masked future, forcing-end retention, budget bounds and unchanged pinned-snapshot result/control. Existing frozen NOAA/tank results must not be rerun or retuned as if new evidence.

Please provide (A) any conceptual flaw in this patch contract, especially zero/tiny steps and masked-knot semantics, (B) a concise concrete code-level patch plan grounded in the actual code below, (C) independent analytic regression cases with expected answers, and (D) how to explain RK4 and this fix in plain words without implying numerical precision equals ocean accuracy. Also assess a separate development diagnostic using solver steps [300,150,75] s on COMMON 300 s output times, with separate event-chord refinement on the SAME finest path. Comparing reference numerics is not independent truth, error bars or universal observed fourth-order convergence on interpolated currents. Primary references to consult if useful: https://gmd.copernicus.org/articles/13/5935/2020/index.html and https://docs.oceanparcels.org/en/latest/user_guide/examples/tutorial_dt_integrators.html.

The following is the actual pre-patch advection.py, not pseudocode:

```python
"""Bounded, deterministic passive-tracer advection through geographic currents.

OceanField velocities are east/north metres per second. This module never uses
buoy holdout positions, estimates tank flow, extrapolates a current field or
manufactures curvature. WGS84 metric derivatives and RK4 integrate the supplied
field; the result remains model output rather than observed waste motion.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from numbers import Real

import numpy as np

from .field import OceanField, _wgs84_metres_per_degree

MAX_HORIZON_S = 6 * 3600.0
MAX_STEPS = 2048
MAX_SAMPLES = 250_000
MAX_SPEED_M_S = 10.0
MAX_ABS_LATITUDE_DEG = 85.0


class _Unsupported(ValueError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _positive(value, name: str, maximum: float) -> float:
    if (isinstance(value, (bool, np.bool_)) or not isinstance(value, Real)
            or not math.isfinite(value) or not 0 < value <= maximum):
        raise ValueError(f"{name} must be positive and within {maximum}")
    return float(value)


def _start(value) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError("start_time_utc requires a timezone-aware timestamp") from error
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("start_time_utc requires a timezone-aware timestamp")
    result = value.astimezone(UTC)
    if not 1900 <= result.year <= 2100:
        raise ValueError("start_time_utc is outside the bounded calendar")
    return result


def _bracket(axis: np.ndarray, value: float, reason: str) -> list[tuple[int, float]]:
    """Contributing knots only; never clamp or bridge missing coordinates."""
    if value < axis[0] or value > axis[-1]:
        raise _Unsupported(reason)
    index = int(np.searchsorted(axis, value, side="left"))
    if index < len(axis) and axis[index] == value:
        return [(index, 1.0)]
    if not 0 < index < len(axis):
        raise _Unsupported(reason)
    fraction = float((value - axis[index - 1]) / (axis[index] - axis[index - 1]))
    return [(index - 1, 1 - fraction), (index, fraction)]


class CurrentSampler:
    """Bilinear space/linear time interpolation with explicit missing-data stops.

    Rectilinear ascending or descending spatial axes are supported. A local
    0..360 longitude field is converted to -180..180. Fields crossing the
    antimeridian, spanning more than 180 degrees or entering polar latitudes
    are rejected rather than stitched or extrapolated.
    """

    def __init__(self, field: OceanField):
        if not isinstance(field, OceanField):
            raise TypeError("An OceanField with geographic coordinates and m/s velocities is required")
        self.field = field
        self.latitude = np.asarray(field.latitude_deg, dtype=float)
        longitude = np.asarray(field.longitude_deg, dtype=float)
        when = np.asarray(field.time_utc)
        if (self.latitude.ndim != 1 or longitude.ndim != 1 or when.ndim != 1
                or min(len(self.latitude), len(longitude), len(when)) < 1
                or not np.isfinite(self.latitude).all() or not np.isfinite(longitude).all()
                or np.abs(self.latitude).max() > MAX_ABS_LATITUDE_DEG
                or longitude.min() < -180 or longitude.max() > 360):
            raise ValueError("Current axes require finite nonpolar geographic coordinates")
        if not np.issubdtype(when.dtype, np.datetime64) or np.isnat(when).any():
            raise ValueError("Current times require decoded UTC-compatible datetime64 values")
        if np.any(when < np.datetime64("1900-01-01")) or np.any(when >= np.datetime64("2101-01-01")):
            raise ValueError("Current times are outside the bounded calendar")
        if len(when) < 2 or np.any(np.diff(when) <= np.timedelta64(0, "s")):
            raise ValueError("Current forcing needs at least two strictly increasing times")
        self.epoch = when[0]
        self.times = np.asarray((when - self.epoch) / np.timedelta64(1, "s"), dtype=float)
        if not np.isfinite(self.times).all():
            raise ValueError("Current time coordinates exceed the finite representation")
        self.longitude = (longitude + 180.0) % 360.0 - 180.0
        for axis, name in ((self.latitude, "latitude"), (self.longitude, "longitude")):
            if len(axis) > 1 and not (np.all(np.diff(axis) > 0) or np.all(np.diff(axis) < 0)):
                raise ValueError(f"Current {name} must be monotonic without a dateline crossing")
        if np.ptp(self.longitude) >= 180 or np.ptp(longitude) >= 180:
            raise ValueError("Current longitude span must remain local and avoid the dateline")
        shape = (len(when), len(self.latitude), len(self.longitude))
        if math.prod(shape) > MAX_SAMPLES:
            raise ValueError("Current field exceeds the sample budget")
        self.u = np.asarray(field.eastward_m_s, dtype=float)
        self.v = np.asarray(field.northward_m_s, dtype=float)
        self.mask = np.asarray(field.valid_mask)
        if (self.u.shape != shape or self.v.shape != shape or self.mask.shape != shape
                or self.mask.dtype != np.dtype(bool)):
            raise ValueError("Current values and boolean mask require (time, latitude, longitude)")
        if (not np.isfinite(self.u[self.mask]).all() or not np.isfinite(self.v[self.mask]).all()
                or not self.mask.any()):
            raise ValueError("Valid current samples must be finite and nonempty")
        speed = np.hypot(self.u[self.mask], self.v[self.mask])
        if float(speed.max()) > MAX_SPEED_M_S:
            raise ValueError("Current speed exceeds the declared m/s safety budget")
        if not isinstance(field.metadata, dict):
            raise TypeError("Current provenance must be a metadata object")
        declared_units = field.metadata.get("velocity_units", "m/s")
        if declared_units != "m/s":
            raise ValueError("OceanField velocities must be in m/s")
        if field.selected_depth_m is not None and (
            not isinstance(field.selected_depth_m, Real)
            or isinstance(field.selected_depth_m, (bool, np.bool_))
            or not math.isfinite(field.selected_depth_m) or field.selected_depth_m < 0
        ):
            raise ValueError("Selected current depth must be finite nonnegative metres")
        if len(self.latitude) > 1 and self.latitude[0] > self.latitude[-1]:
            self.latitude = self.latitude[::-1]
            self.u, self.v, self.mask = (item[:, ::-1, :] for item in (self.u, self.v, self.mask))
        if len(self.longitude) > 1 and self.longitude[0] > self.longitude[-1]:
            self.longitude = self.longitude[::-1]
            self.u, self.v, self.mask = (item[:, :, ::-1] for item in (self.u, self.v, self.mask))
        # At most a quarter of the smallest cell per accepted step and half the
        # shortest forcing interval. This is a numerical limit, not uncertainty.
        cells = []
        if len(self.latitude) > 1:
            cells.append(float(np.diff(self.latitude).min()) * min(
                _wgs84_metres_per_degree(float(lat))[1] for lat in self.latitude))
        if len(self.longitude) > 1:
            cells.append(float(np.diff(self.longitude).min()) * min(
                _wgs84_metres_per_degree(float(lat))[0] for lat in self.latitude))
        self.step_limit_s = float(np.diff(self.times).min()) / 2
        if cells and speed.max() > 0:
            self.step_limit_s = min(self.step_limit_s, min(cells) / (4 * float(speed.max())))

    def sample(self, latitude_deg: float, longitude_deg: float, seconds: float) -> tuple[float, float]:
        if (not np.isfinite([latitude_deg, longitude_deg, seconds]).all()
                or abs(latitude_deg) > MAX_ABS_LATITUDE_DEG
                or not -180 <= longitude_deg < 180):
            raise _Unsupported("UNSUPPORTED_GEOGRAPHY")
        ti = _bracket(self.times, seconds, "OUTSIDE_FORCING_TIME")
        yi = _bracket(self.latitude, latitude_deg, "OUTSIDE_CURRENT_DOMAIN")
        xi = _bracket(self.longitude, longitude_deg, "OUTSIDE_CURRENT_DOMAIN")
        east = north = 0.0
        for t, tw in ti:
            for y, yw in yi:
                for x, xw in xi:
                    if not self.mask[t, y, x]:
                        raise _Unsupported("MASKED_CURRENT_CELL")
                    weight = tw * yw * xw
                    east += weight * self.u[t, y, x]
                    north += weight * self.v[t, y, x]
        return float(east), float(north)


def advect_current(field: OceanField, *, latitude_deg: float, longitude_deg: float,
                   start_time_utc: str | datetime, horizon_s: float = MAX_HORIZON_S,
                   step_s: float = 300, output_step_s: float = 900) -> dict:
    """Integrate a passive surface tracer; retain only fully supported RK4 steps.

    This bounded ocean diagnostic never changes source/prevention tank evidence.
    Invalid configuration raises ValueError. Missing forcing stops with an
    explicit UNSUPPORTED/PARTIAL report and the last valid accepted position.
    No extrapolation, zero-filled masks, clipping or stochastic wiggles occur.
    """
    horizon = _positive(horizon_s, "horizon_s", MAX_HORIZON_S)
    step = _positive(step_s, "step_s", 3600)
    output_step = _positive(output_step_s, "output_step_s", MAX_HORIZON_S)
    for value in (latitude_deg, longitude_deg):
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not math.isfinite(value):
            raise ValueError("Starting coordinates require finite real geographic degrees")
    if abs(latitude_deg) > MAX_ABS_LATITUDE_DEG or not -180 <= longitude_deg <= 360:
        raise ValueError("Starting coordinates must be nonpolar geographic degrees")
    longitude = (float(longitude_deg) + 180) % 360 - 180
    start = _start(start_time_utc)
    sampler = CurrentSampler(field)
    start64 = np.datetime64(start.replace(tzinfo=None), "us")
    offset = float((start64 - sampler.epoch) / np.timedelta64(1, "s"))
    step = min(step, sampler.step_limit_s, output_step)
    if not math.isfinite(step) or step <= 0 or math.ceil(horizon / step) + math.ceil(horizon / output_step) > MAX_STEPS:
        raise ValueError("Advection would exceed its bounded step budget")
    state = np.array([float(latitude_deg), longitude])
    elapsed = 0.0
    track = []
    reason = None
    accepted_steps = 0

    def point(t: float, position: np.ndarray) -> dict:
        u, v = sampler.sample(float(position[0]), float(position[1]), offset + t)
        return {"time_utc": (start + timedelta(seconds=t)).isoformat().replace("+00:00", "Z"),
                "elapsed_s": t, "latitude_deg": float(position[0]),
                "longitude_deg": float(position[1]), "eastward_m_s": u,
                "northward_m_s": v, "speed_m_s": math.hypot(u, v)}

    def derivative(t: float, position: np.ndarray) -> np.ndarray:
        u, v = sampler.sample(float(position[0]), float(position[1]), offset + t)
        metres_lon, metres_lat = _wgs84_metres_per_degree(float(position[0]))
        return np.array([v / metres_lat, u / metres_lon])

    try:
        track.append(point(0.0, state))
        next_output = min(output_step, horizon)
        while elapsed < horizon:
            if accepted_steps >= MAX_STEPS:
                raise _Unsupported("STEP_BUDGET_EXCEEDED")
            dt = min(step, horizon - elapsed, next_output - elapsed)
            k1 = derivative(elapsed, state)
            k2 = derivative(elapsed + dt / 2, state + dt * k1 / 2)
            k3 = derivative(elapsed + dt / 2, state + dt * k2 / 2)
            k4 = derivative(elapsed + dt, state + dt * k3)
            candidate = state + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6
            accepted_point = point(elapsed + dt, candidate)
            state = candidate
            elapsed += dt
            accepted_steps += 1
            if elapsed >= next_output:
                track.append(accepted_point)
                next_output = min(horizon, next_output + output_step)
        status = "COMPLETED"
    except _Unsupported as error:
        reason = error.reason
        status = "PARTIAL" if elapsed > 0 else "UNSUPPORTED"
        if elapsed > 0 and track[-1]["elapsed_s"] != elapsed:
            track.append(point(elapsed, state))
    return {
        "schema_version": 1, "kind": "CURRENT_FORCED_PASSIVE_TRACER",
        "status": status, "reason_code": reason,
        "requested_horizon_s": horizon, "completed_horizon_s": elapsed,
        "track": track, "accepted_steps": accepted_steps,
        "solver": {"method": "RK4_WGS84_METRIC_DERIVATIVES", "maximum_step_s": step,
                   "output_step_s": output_step, "spatial_interpolation": "bilinear",
                   "temporal_interpolation": "linear", "velocity_units": "m/s",
                   "position_units": "geographic_degrees", "maximum_steps": MAX_STEPS},
        "forcing": {"time_start_utc": str(field.time_utc[0]) + "Z",
                    "time_end_utc": str(field.time_utc[-1]) + "Z",
                    "selected_depth_m": field.selected_depth_m,
                    "shape": list(sampler.u.shape),
                    "provenance": {key: field.metadata[key] for key in (
                        "product", "dataset", "title", "u_variable", "v_variable", "sha256",
                        "source_url", "issued_at_utc", "retrieved_at_utc", "license", "data_kind"
                    ) if key in field.metadata}},
        "physical_validation": False, "plastic_motion_validated": False,
        "tank_flow_used": False, "heldout_buoy_positions_used": False,
        "limitations": [
            "The supplied current field is model output, not measured waste motion.",
            "No windage, object response, beaching, retention or diffusion is inferred.",
            "Missing cells and unavailable times stop the track; no extrapolation is used.",
            "Forecast causality requires a separately verified issue-time/as-of receipt.",
            "Ocean currents do not calibrate the centimetre-scale tank experiment.",
        ],
    }

```
````

### docs/grok-evidence/rk4-knot-review-initial-response.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/rk4-knot-review-initial-response.txt

Bytes: 5395; SHA-256: `eafe86340f63c6506a0be566922373448c45f47c4248c597c2ab882ede2dde0e`. Role: saved Grok static response: includes rejected arithmetic and time-only snap. Quoted record; read the ledger for current status.

````text
Historical Grok web static-review output, retrieved 17 October 2026. Not repository execution. This response includes incorrect arithmetic and a rejected time-snapping proposal; see subsequent correction before interpreting it.

GrokWorked for 18sStatic review only. No repository execution or remote change is claimed. The completed NOAA study stays frozen.
(A) Conceptual flaws / edge semantics
The contract is sound on the two reported failures, with two clarifications required.

Zero/tiny steps. Bounding dt by the next strictly future knot can yield a sub-normal or zero step when offset + elapsed lands within floating-point noise of a knot, or when the remaining time is smaller than ~1e-9 s. The loop must treat any dt < 1e-6 s (the existing minimum used elsewhere) as exact arrival at that knot: advance elapsed to the knot, accept the point if the sample at that exact time is supported, and do not issue an RK4 stage. Otherwise MAX_STEPS can be exhausted by vanishing steps.
Masked-knot semantics. A step that is shortened to land exactly on a forcing knot must still run the existing strict contributing-corner mask check at the arrival location and time. If any corner is masked, stop with MASKED_CURRENT_CELL and retain the last fully supported position; do not accept the knot sample or continue. “Retain through the forcing end” applies only when the sample at the final forcing time is supported.

No other conceptual flaw is apparent: the RK4 weights, WGS84 metric conversion, bilinear/linear interpolation, and refusal to extrapolate or zero-fill remain correct.
(B) Code-level patch plan (grounded in the supplied advect_current)
Inside the while elapsed < horizon loop, replace the single dt = min(step, horizon - elapsed, next_output - elapsed) with:

Compute t_now = offset + elapsed.
Find the smallest forcing time strictly greater than t_now (binary search on sampler.times). If none exists, break with OUTSIDE_FORCING_TIME after ensuring the track contains the point at current elapsed (already accepted).
Setdt = min(step, horizon - elapsed, next_output - elapsed, next_knot - t_now).
If dt < 1e-6, snap: set elapsed to the knot (or horizon/output), sample once at the exact time, accept if supported, and continue. Do not call the four derivative stages.
Otherwise execute the existing RK4 stages (all samples now lie inside a single forcing interval) and accept as today.
On any _Unsupported from a stage or from the arrival sample, keep the same PARTIAL/UNSUPPORTED logic already present; never extrapolate.

Leave CurrentSampler.sample, _bracket, the RK4 formula, WGS84 conversion, mask policy, geometry and scoring untouched. Update the method identifier string so the hash changes; do not reuse prior receipts.
(C) Independent analytic regression cases

Knot-crossing recovery. Uniform u = [0, 1, 0] m/s at t = [0, 650, 1400], v = 0, lat = 0, step = 300 s, output/horizon = 1000 s. Exact piecewise-linear integral = 0⋅650+1⋅350=3500\cdot650 + 1\cdot350 = 3500⋅650+1⋅350=350 m east, plus the linear ramp: displacement = 593.3‾593.\overline{3}593.3 m. After the split, the numerical result must match this value within 1e-6 m relative.
Forcing-end retention. Last forcing time 1400 s, horizon 1800 s, step 300 s, output 900 s. Must accept the supported path through exactly 1400 s, then return PARTIAL / OUTSIDE_FORCING_TIME with completed_horizon_s == 1400. Must not report 1200 s and must not extrapolate.
Nonzero offset. Same uniform field, start offset = 100 s. Integral from 100 s to 1000 s of the piecewise-linear u equals 540540540 m. Recover within tolerance.
Exact-knot masked future. Place a masked corner at the spatial location reached at a forcing knot. The step that would land on that knot must raise MASKED_CURRENT_CELL and leave completed_horizon_s at the previous accepted time.
Pinned snapshot unchanged. On the default PacIOOS field (knots every 10 800 s) the track latitudes, longitudes and status must be identical to the pre-patch result for the six releases; only the method hash differs.

(D) Plain-words explanation and diagnostic assessment
RK4 estimates the next position by sampling the current at the start, two midpoints and the end of a short step, then taking a weighted average. When the supplied current changes slope abruptly at a forcing time, a step that straddles that instant mixes two different slopes and drifts from the true integral. Splitting every step at the next forcing time keeps each RK4 sample inside one linear piece, so the integrator follows the supplied field more faithfully. This removes a numerical inconsistency; it does not make the current field itself more accurate, nor does it turn model output into observed plastic motion.
A separate development diagnostic that re-runs the same path at 300 s, 150 s and 75 s steps, reporting positions only on the common 300 s output times, plus a chord-refinement check on the finest path, is useful for exposing step-size sensitivity. Because the interpolated field is merely continuous (not smooth) at knots and the spatial interpolant is bilinear, the comparison does not constitute independent truth, an error bar, or evidence of universal fourth-order convergence.
Primary references for integrator practice remain the GMD Parcels paper and the OceanParcels time-step tutorial; neither supplies a plastic-validation claim for this diagnostic.
````

### docs/grok-evidence/rk4-knot-correction-prompt.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/rk4-knot-correction-prompt.txt

Bytes: 2366; SHA-256: `74558363dfd41520e9bb08707e9d38ffc72dda93e9b68d972099b49758debfc8`. Role: actual outbound Grok web prompt: no-snap contract and arithmetic correction. Quoted record; read the ledger for current status.

````text
Two code/mathematics corrections before any patch is accepted:

1. The supplied advection code has NO existing 1e-6-second minimum. A minimum from a separate Kalman/tank module cannot be imported into this ocean integrator. Advancing elapsed time across any positive interval without integrating the position silently invents a stationary displacement. Reject that snap proposal. Keep positive representable steps, explicitly guard finite dt>0 and elapsed+dt>elapsed; if meaningful progress is not representable, fail closed with an explicit reason instead of advancing an unchanged position. Time-boundary scheduling should use deterministic target times and strict search, with no arbitrary unintegrated time jump. All RK4 arrival samples retain normal strict support checks.

2. Your nonzero-offset answer 540 m is wrong. For u(t)=t/650 on [0,650], u(t)=(1400-t)/750 on [650,1400], the 0->1000 integral is 325 + 350*(1+400/750)/2 = 593.333333333333 m. The 0->100 integral is 100^2/(2*650)=7.692307692308 m. Therefore 100->1000 is 585.641025641026 m. State horizon unambiguously: a start at absolute t=100 with horizon=900 ends at absolute t=1000. A horizon of1000 would instead end at1100 and have a different integral. Please recompute both with explicit area terms.

Source-byte hashing already changes method_sha256 when advection.py changes. The method remains RK4/WGS84; there is no need to rename the algorithm to pretend a different solver was added. A new additive solver metadata flag for knot-aligned stepping can describe the behavior. Old study receipts remain historical.

Return a corrected concise patch contract and independent exact expected answers (0->1000,100->1000,100->1100), including what a strict exact-knot mask means: only contributing interpolation corners are required, while interpolation into a masked future interval must fail; no epsilon may bridge it. Preserve existing public snapshot geometry/counts and frozen NOAA studies. Then give a careful implementation outline for a SEPARATE numerical-sensitivity report: solver steps300/150/75, common300s output for integration-only difference; same75s finest path downsampled to event chords300/150/75 for event-only difference. Use common-time comparisons and explicit status/censoring changes, no numerical-precision-as-physical-accuracy claim. Do not claim you executed any code.
````

### docs/grok-evidence/rk4-knot-corrected-response.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/rk4-knot-corrected-response.txt

Bytes: 3851; SHA-256: `9ba237abcd174f45d9a9ad0c637a443ad8259de707c3a5e76bfa89cdf3092048`. Role: saved Grok static response: retains an integral error corrected subsequently. Quoted record; read the ledger for current status.

````text
Historical Grok web static-review output, retrieved 17 October 2026. Not repository execution. The no-snap contract is accepted in principle; the final 100->1100 integral in this response is WRONG and is corrected by the next prompt.

GrokWorked for 4sCorrected patch contract (static). No code was executed.
Time-boundary rule. Do not import any 1e-6 s floor and do not advance elapsed across a positive interval without integrating the position. Schedule every candidate step to a deterministic target (next strictly future forcing knot, next output, horizon, or the existing speed/cell/max-step limit) using strict search on the forcing times. Require dt finite and dt > 0 and elapsed + dt > elapsed. If floating-point resolution cannot represent a positive step that makes progress, fail closed with an explicit reason (for example TIME_RESOLUTION_EXHAUSTED) and retain the last fully supported position. Every RK4 arrival sample continues to use the existing strict contributing-corner mask check. A new additive solver-metadata flag may record that steps are knot-aligned; the method name remains RK4/WGS84. Source-byte hashing already updates method_sha256. Old receipts stay historical.
Exact-knot mask. Only the corners that actually contribute to the interpolation at the arrival location and exact knot time are required to be valid. If the arrival lies strictly inside a later forcing interval whose contributing corners include a masked cell, the sample fails with MASKED_CURRENT_CELL. No epsilon may bridge into that interval.
Independent exact integrals (piecewise-linear u(t)=t/650u(t)=t/650u(t)=t/650 on [0,650][0,650][0,650], u(t)=(1400−t)/750u(t)=(1400-t)/750u(t)=(1400−t)/750 on [650,1400][650,1400][650,1400], v=0v=0v=0):

0→10000\to10000→1000: ∫0650t/650 dt+∫6501000(1400−t)/750 dt=325+350⋅(1+400/750)/2=593.3‾\int_0^{650}t/650\,dt + \int_{650}^{1000}(1400-t)/750\,dt = 325 + 350\cdot(1+400/750)/2 = 593.\overline{3}∫0650​t/650dt+∫6501000​(1400−t)/750dt=325+350⋅(1+400/750)/2=593.3 m.
0→1000\to1000→100: ∫0100t/650 dt=1002/(2⋅650)=7.692307692308\int_0^{100}t/650\,dt = 100^2/(2\cdot650) = 7.692307692308∫0100​t/650dt=1002/(2⋅650)=7.692307692308 m.
100→1000100\to1000100→1000 (start at absolute t=100t=100t=100, horizon =900=900=900): 593.3‾−7.692307692308=585.641025641026593.\overline{3}-7.692307692308 = 585.641025641026593.3−7.692307692308=585.641025641026 m.
100→1100100\to1100100→1100 (start at absolute t=100t=100t=100, horizon =1000=1000=1000):∫100650t/650 dt+∫6501100(1400−t)/750 dt=(6502−1002)/(2⋅650)+∫0450(750−s)/750 ds=317.307692307692+292.5=609.807692307692\int_{100}^{650}t/650\,dt + \int_{650}^{1100}(1400-t)/750\,dt = (650^2-100^2)/(2\cdot650) + \int_0^{450}(750-s)/750\,ds = 317.307692307692 + 292.5 = 609.807692307692∫100650​t/650dt+∫6501100​(1400−t)/750dt=(6502−1002)/(2⋅650)+∫0450​(750−s)/750ds=317.307692307692+292.5=609.807692307692 m.

Separate numerical-sensitivity report (outline only).
Re-integrate the same six releases at solver steps 300 s, 150 s and 75 s. Emit positions only on the common 300 s output times that all three runs reached with status COMPLETED; record any run that becomes PARTIAL or changes reason code as a censored difference, not as a numeric delta. On the single 75 s path, also downsample the accepted event chords to 300 s and 150 s widths and compare those chord endpoints with the native 300 s and 150 s integrations at the same absolute times. Report integration-only and event-only differences separately. The comparison exposes step-size sensitivity of the knot-aligned RK4 on the interpolated field; it is not independent truth, an error bar, or observed fourth-order convergence, and it does not alter the frozen NOAA studies or the public snapshot geometry/counts.
````

### docs/grok-evidence/rk4-final-math-and-code-prompt.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/rk4-final-math-and-code-prompt.txt

Bytes: 1977; SHA-256: `8cdc935af43c5ef65eec28c81f9137dba9c579fef6176ff5a553a7bee12f7cdf`. Role: actual outbound Grok web prompt: independent integrals and sensitivity contract. Quoted record; read the ledger for current status.

````text
Your no-snap, strict-support patch contract is accepted in principle for local implementation. One more arithmetic error must be corrected before publication: the integral from650to1100 is 450*(1+300/750)/2=315m, NOT292.5m. Equivalently450-450^2/1500=315. Therefore100->1100 equals(650^2-100^2)/1300+315=632.307692307692m. Our tests will derive these integrals using exact rational arithmetic independently of your numbers. Preserve both erroneous historical responses as rejected arithmetic; do not say they verified the implementation.

Please now draft a small precise Python helper/pseudocode for scheduling an RK4 step using absolute forcing times and elapsed targets, strict searchsorted(side='right'), positive representable progress, final-time handling, and runtimeMAX_STEPS. Highlight any start-offset cancellation and floating endpoint issue instead of silently snapping elapsed without motion. No tolerance may admit masked/extrapolated support. The implementation agent is working locally against the accepted contract; this draft is static review input and will be compared with actual source/tests.

For the separate diagnostic, clarify a flaw in your prior outline: event-only sensitivity must NOT compare against independently integrated native300/150paths. Use ONE finest75s path with points every75s; derive300/150/75chords by downsampling that same path, retaining any terminal partial point, and evaluate all three geometries. Compare status/eventkind/eventidentity/eventtime by release/layout. Separately, integration-only sensitivity runs allthree solversteps with COMMON300s output; numeric separations use only commonvalidtimestamps while missingcoverage/statuschanges remain explicit. Do not drop partialpaths or their denominators. Neither experiment creates physical truth or a statisticalconfidenceinterval; no retuning completedNOAAresults. Return compactcode-orientedreview, correctintegrals, andUIwording that says what thischeckactuallyproves.
````

### docs/grok-evidence/rk4-final-code-review-response.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/rk4-final-code-review-response.txt

Bytes: 2828; SHA-256: `3b1cc7ee964e5ece4ae6ed3e029e549ddec1c8fab581ff3e12a22a3563da1d49`. Role: saved Grok static response: accidental rejection of valid alternate-horizon integral and restrictive comparison advice not adopted. Quoted record; read the ledger for current status.

````text
Grok web static-review output, retrieved 17 October 2026. Not repository execution. This advice is reviewed against actual local implementation/tests, not copied blindly.

GrokWorked for 4sCorrected integrals (prior arithmetic rejected).
The 650→1100 piece is 450⋅(1+300/750)/2=315450\cdot(1+300/750)/2=315450⋅(1+300/750)/2=315 m, equivalently 450−4502/1500=315450-450^2/1500=315450−4502/1500=315 m.
Thus
100→1100=6502−10021300+315=632.307692307692 m.100\to1100=\frac{650^2-100^2}{1300}+315=632.307692307692\,\mathrm{m}.100→1100=13006502−1002​+315=632.307692307692m.
Earlier figures 540 m, 585.641… m and 609.807… m are rejected arithmetic and did not verify any implementation. Tests will recompute the same integrals in exact rational arithmetic.
Scheduling helper (static draft).
PythonCopyCopieddef next_step(elapsed, offset, horizon, output_times, forcing_times, step_cap, accepted):
    """Return a positive representable dt or raise. Never advance time without motion."""
    if accepted >= MAX_STEPS:
        raise _Unsupported("STEP_BUDGET_EXCEEDED")
    t_abs = offset + elapsed                     # highlight: large offset + small elapsed
    # strict future knot
    idx = np.searchsorted(forcing_times, t_abs, side="right")
    if idx >= len(forcing_times):
        raise _Unsupported("OUTSIDE_FORCING_TIME")
    targets = [forcing_times[idx] - offset, horizon]
    targets += [t for t in output_times if t > elapsed]
    target = min(targets)
    dt = min(step_cap, target - elapsed)
    if not math.isfinite(dt) or dt <= 0 or elapsed + dt <= elapsed:
        raise _Unsupported("TIME_RESOLUTION_EXHAUSTED")  # no silent snap
    return dt
Arrival sampling at elapsed+dt retains the existing strict contributing-corner check; a masked corner or an out-of-range time fails closed with no epsilon bridge.
Diagnostic clarification.
Event-only sensitivity uses one finest 75 s path. Derive 300 s, 150 s and 75 s chords by downsampling that same path (retain any terminal partial point) and compare status, event kind, event identity and event time across the three geometries of the identical trajectory. Do not compare against independently integrated native 300/150 paths.
Integration-only sensitivity runs the three solver steps separately, emits positions only on common 300 s output times, and records numeric separations solely at timestamps reached by all three with COMPLETED; missing coverage or status changes stay explicit and partial paths remain in the denominator.
UI wording.
“Knot-aligned RK4 removes steps that straddle forcing-time slope breaks and retains the last supported position at the forcing end. On this field the check shows numerical sensitivity to step size; it does not supply physical truth, a confidence interval, or a change to the frozen NOAA results.”
````

### docs/grok-evidence/rk4-actual-patch-review-prompt.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/rk4-actual-patch-review-prompt.txt

Bytes: 24590; SHA-256: `b228ee43f706b0394430676d8d265720fb60c6a762a7e00f98be2995c3d004a9`. Role: actual outbound Grok web prompt: actual local scheduling patch and regressions. Quoted record; read the ledger for current status.

````text
Actual local patch review, 17 October 2026. No repository execution by you is claimed. The knot/end fix now passes 87 numerical tests and 99 related API tests locally, including exact Fraction trapezoid areas, strict masks, representable sub-microsecond steps and fail-closed unrepresentable time. All six pinned-snapshot track arrays and every outcome in both scenarios match the pre-patch reference exactly. No NOAA parameter, forecast, holdout or data changed. Only source hashes honestly change. Your last response accidentally rejected 585.641...m, which is CORRECT for absolute100->1000, while632.307692...m is correct100->1100. Our rational tests are authoritative, so do not restate or round new arithmetic.

Review actual code and regressions below for an actionable logic defect, especially fractional time knots/start offsets, precision/strict mask semantics, preflight/runtime step budgets, and truthful completion at forcing expiry. Also review the next separate sensitivity experiment contract: fixed300/150/75steps with common300s output for integration sensitivity; one75/75track downsampled300/150/75 for event-only sensitivity, terminalpartialpoint retained, changed event identities and missing/censored paths reported. No numerical-reference-as-truth, ML tuning or physical benefit claims. Return concrete findings with counterexamples or state what you could not verify. No advice that merely renames RK4, adds curvature, skips positive time or silently discards unsupported releases. This is static adversarial review; local code/tests decide acceptance.

FILE: apps/ocean/reeftrace_ocean/advection.py
```python
"""Bounded, deterministic passive-tracer advection through geographic currents.

OceanField velocities are east/north metres per second. This module never uses
buoy holdout positions, estimates tank flow, extrapolates a current field or
manufactures curvature. WGS84 metric derivatives and RK4 integrate the supplied
field; the result remains model output rather than observed waste motion.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from numbers import Real

import numpy as np

from .field import OceanField, _wgs84_metres_per_degree

MAX_HORIZON_S = 6 * 3600.0
MAX_STEPS = 2048
MAX_SAMPLES = 250_000
MAX_SPEED_M_S = 10.0
MAX_ABS_LATITUDE_DEG = 85.0


class _Unsupported(ValueError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _positive(value, name: str, maximum: float) -> float:
    if (isinstance(value, (bool, np.bool_)) or not isinstance(value, Real)
            or not math.isfinite(value) or not 0 < value <= maximum):
        raise ValueError(f"{name} must be positive and within {maximum}")
    return float(value)


def _start(value) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError("start_time_utc requires a timezone-aware timestamp") from error
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("start_time_utc requires a timezone-aware timestamp")
    result = value.astimezone(UTC)
    if not 1900 <= result.year <= 2100:
        raise ValueError("start_time_utc is outside the bounded calendar")
    return result


def _bracket(axis: np.ndarray, value: float, reason: str) -> list[tuple[int, float]]:
    """Contributing knots only; never clamp or bridge missing coordinates."""
    if value < axis[0] or value > axis[-1]:
        raise _Unsupported(reason)
    index = int(np.searchsorted(axis, value, side="left"))
    if index < len(axis) and axis[index] == value:
        return [(index, 1.0)]
    if not 0 < index < len(axis):
        raise _Unsupported(reason)
    fraction = float((value - axis[index - 1]) / (axis[index] - axis[index - 1]))
    return [(index - 1, 1 - fraction), (index, fraction)]


class CurrentSampler:
    """Bilinear space/linear time interpolation with explicit missing-data stops.

    Rectilinear ascending or descending spatial axes are supported. A local
    0..360 longitude field is converted to -180..180. Fields crossing the
    antimeridian, spanning more than 180 degrees or entering polar latitudes
    are rejected rather than stitched or extrapolated.
    """

    def __init__(self, field: OceanField):
        if not isinstance(field, OceanField):
            raise TypeError("An OceanField with geographic coordinates and m/s velocities is required")
        self.field = field
        self.latitude = np.asarray(field.latitude_deg, dtype=float)
        longitude = np.asarray(field.longitude_deg, dtype=float)
        when = np.asarray(field.time_utc)
        if (self.latitude.ndim != 1 or longitude.ndim != 1 or when.ndim != 1
                or min(len(self.latitude), len(longitude), len(when)) < 1
                or not np.isfinite(self.latitude).all() or not np.isfinite(longitude).all()
                or np.abs(self.latitude).max() > MAX_ABS_LATITUDE_DEG
                or longitude.min() < -180 or longitude.max() > 360):
            raise ValueError("Current axes require finite nonpolar geographic coordinates")
        if not np.issubdtype(when.dtype, np.datetime64) or np.isnat(when).any():
            raise ValueError("Current times require decoded UTC-compatible datetime64 values")
        if np.any(when < np.datetime64("1900-01-01")) or np.any(when >= np.datetime64("2101-01-01")):
            raise ValueError("Current times are outside the bounded calendar")
        if len(when) < 2 or np.any(np.diff(when) <= np.timedelta64(0, "s")):
            raise ValueError("Current forcing needs at least two strictly increasing times")
        self.epoch = when[0]
        self.times = np.asarray((when - self.epoch) / np.timedelta64(1, "s"), dtype=float)
        if not np.isfinite(self.times).all():
            raise ValueError("Current time coordinates exceed the finite representation")
        self.longitude = (longitude + 180.0) % 360.0 - 180.0
        for axis, name in ((self.latitude, "latitude"), (self.longitude, "longitude")):
            if len(axis) > 1 and not (np.all(np.diff(axis) > 0) or np.all(np.diff(axis) < 0)):
                raise ValueError(f"Current {name} must be monotonic without a dateline crossing")
        if np.ptp(self.longitude) >= 180 or np.ptp(longitude) >= 180:
            raise ValueError("Current longitude span must remain local and avoid the dateline")
        shape = (len(when), len(self.latitude), len(self.longitude))
        if math.prod(shape) > MAX_SAMPLES:
            raise ValueError("Current field exceeds the sample budget")
        self.u = np.asarray(field.eastward_m_s, dtype=float)
        self.v = np.asarray(field.northward_m_s, dtype=float)
        self.mask = np.asarray(field.valid_mask)
        if (self.u.shape != shape or self.v.shape != shape or self.mask.shape != shape
                or self.mask.dtype != np.dtype(bool)):
            raise ValueError("Current values and boolean mask require (time, latitude, longitude)")
        if (not np.isfinite(self.u[self.mask]).all() or not np.isfinite(self.v[self.mask]).all()
                or not self.mask.any()):
            raise ValueError("Valid current samples must be finite and nonempty")
        speed = np.hypot(self.u[self.mask], self.v[self.mask])
        if float(speed.max()) > MAX_SPEED_M_S:
            raise ValueError("Current speed exceeds the declared m/s safety budget")
        if not isinstance(field.metadata, dict):
            raise TypeError("Current provenance must be a metadata object")
        declared_units = field.metadata.get("velocity_units", "m/s")
        if declared_units != "m/s":
            raise ValueError("OceanField velocities must be in m/s")
        if field.selected_depth_m is not None and (
            not isinstance(field.selected_depth_m, Real)
            or isinstance(field.selected_depth_m, (bool, np.bool_))
            or not math.isfinite(field.selected_depth_m) or field.selected_depth_m < 0
        ):
            raise ValueError("Selected current depth must be finite nonnegative metres")
        if len(self.latitude) > 1 and self.latitude[0] > self.latitude[-1]:
            self.latitude = self.latitude[::-1]
            self.u, self.v, self.mask = (item[:, ::-1, :] for item in (self.u, self.v, self.mask))
        if len(self.longitude) > 1 and self.longitude[0] > self.longitude[-1]:
            self.longitude = self.longitude[::-1]
            self.u, self.v, self.mask = (item[:, :, ::-1] for item in (self.u, self.v, self.mask))
        # At most a quarter of the smallest cell per accepted step and half the
        # shortest forcing interval. This is a numerical limit, not uncertainty.
        cells = []
        if len(self.latitude) > 1:
            cells.append(float(np.diff(self.latitude).min()) * min(
                _wgs84_metres_per_degree(float(lat))[1] for lat in self.latitude))
        if len(self.longitude) > 1:
            cells.append(float(np.diff(self.longitude).min()) * min(
                _wgs84_metres_per_degree(float(lat))[0] for lat in self.latitude))
        self.step_limit_s = float(np.diff(self.times).min()) / 2
        if cells and speed.max() > 0:
            self.step_limit_s = min(self.step_limit_s, min(cells) / (4 * float(speed.max())))

    def sample(self, latitude_deg: float, longitude_deg: float, seconds: float) -> tuple[float, float]:
        if (not np.isfinite([latitude_deg, longitude_deg, seconds]).all()
                or abs(latitude_deg) > MAX_ABS_LATITUDE_DEG
                or not -180 <= longitude_deg < 180):
            raise _Unsupported("UNSUPPORTED_GEOGRAPHY")
        ti = _bracket(self.times, seconds, "OUTSIDE_FORCING_TIME")
        yi = _bracket(self.latitude, latitude_deg, "OUTSIDE_CURRENT_DOMAIN")
        xi = _bracket(self.longitude, longitude_deg, "OUTSIDE_CURRENT_DOMAIN")
        east = north = 0.0
        for t, tw in ti:
            for y, yw in yi:
                for x, xw in xi:
                    if not self.mask[t, y, x]:
                        raise _Unsupported("MASKED_CURRENT_CELL")
                    weight = tw * yw * xw
                    east += weight * self.u[t, y, x]
                    north += weight * self.v[t, y, x]
        return float(east), float(north)


def advect_current(field: OceanField, *, latitude_deg: float, longitude_deg: float,
                   start_time_utc: str | datetime, horizon_s: float = MAX_HORIZON_S,
                   step_s: float = 300, output_step_s: float = 900) -> dict:
    """Integrate a passive surface tracer; retain only fully supported RK4 steps.

    This bounded ocean diagnostic never changes source/prevention tank evidence.
    Invalid configuration raises ValueError. Missing forcing stops with an
    explicit UNSUPPORTED/PARTIAL report and the last valid accepted position.
    Steps end at forcing-time knots so no RK4 stage spans a time-interpolation
    derivative break. No extrapolation, zero-filled masks or stochastic wiggles
    occur, and positive intervals are never skipped by advancing time alone.
    """
    horizon = _positive(horizon_s, "horizon_s", MAX_HORIZON_S)
    step = _positive(step_s, "step_s", 3600)
    output_step = _positive(output_step_s, "output_step_s", MAX_HORIZON_S)
    for value in (latitude_deg, longitude_deg):
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not math.isfinite(value):
            raise ValueError("Starting coordinates require finite real geographic degrees")
    if abs(latitude_deg) > MAX_ABS_LATITUDE_DEG or not -180 <= longitude_deg <= 360:
        raise ValueError("Starting coordinates must be nonpolar geographic degrees")
    longitude = (float(longitude_deg) + 180) % 360 - 180
    start = _start(start_time_utc)
    sampler = CurrentSampler(field)
    start64 = np.datetime64(start.replace(tzinfo=None), "us")
    offset = float((start64 - sampler.epoch) / np.timedelta64(1, "s"))
    step = min(step, sampler.step_limit_s, output_step)
    forcing_elapsed = sampler.times - offset
    knot_splits = int(np.count_nonzero((forcing_elapsed > 0) & (forcing_elapsed < horizon)))
    if (not math.isfinite(step) or step <= 0
            or math.ceil(horizon / step) + math.ceil(horizon / output_step)
            + knot_splits > MAX_STEPS):
        raise ValueError("Advection would exceed its bounded step budget")
    state = np.array([float(latitude_deg), longitude])
    elapsed = 0.0
    track = []
    reason = None
    accepted_steps = 0

    def point(t: float, position: np.ndarray) -> dict:
        u, v = sampler.sample(float(position[0]), float(position[1]), offset + t)
        return {"time_utc": (start + timedelta(seconds=t)).isoformat().replace("+00:00", "Z"),
                "elapsed_s": t, "latitude_deg": float(position[0]),
                "longitude_deg": float(position[1]), "eastward_m_s": u,
                "northward_m_s": v, "speed_m_s": math.hypot(u, v)}

    def derivative(t: float, position: np.ndarray) -> np.ndarray:
        u, v = sampler.sample(float(position[0]), float(position[1]), offset + t)
        metres_lon, metres_lat = _wgs84_metres_per_degree(float(position[0]))
        return np.array([v / metres_lat, u / metres_lon])

    try:
        track.append(point(0.0, state))
        next_output = min(output_step, horizon)
        while elapsed < horizon:
            if accepted_steps >= MAX_STEPS:
                raise _Unsupported("STEP_BUDGET_EXCEEDED")
            knot_index = int(np.searchsorted(forcing_elapsed, elapsed, side="right"))
            if knot_index >= len(forcing_elapsed):
                raise _Unsupported("OUTSIDE_FORCING_TIME")
            target = min(elapsed + step, horizon, next_output,
                         float(forcing_elapsed[knot_index]))
            dt = target - elapsed
            if (not math.isfinite(dt) or dt <= 0 or target <= elapsed
                    or offset + target <= offset + elapsed):
                raise _Unsupported("TIME_STEP_NOT_REPRESENTABLE")
            k1 = derivative(elapsed, state)
            k2 = derivative(elapsed + dt / 2, state + dt * k1 / 2)
            k3 = derivative(elapsed + dt / 2, state + dt * k2 / 2)
            k4 = derivative(target, state + dt * k3)
            candidate = state + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6
            accepted_point = point(target, candidate)
            state = candidate
            elapsed = target
            accepted_steps += 1
            if elapsed >= next_output:
                track.append(accepted_point)
                next_output = min(horizon, next_output + output_step)
        status = "COMPLETED"
    except _Unsupported as error:
        reason = error.reason
        status = "PARTIAL" if elapsed > 0 else "UNSUPPORTED"
        if elapsed > 0 and track[-1]["elapsed_s"] != elapsed:
            track.append(point(elapsed, state))
    return {
        "schema_version": 1, "kind": "CURRENT_FORCED_PASSIVE_TRACER",
        "status": status, "reason_code": reason,
        "requested_horizon_s": horizon, "completed_horizon_s": elapsed,
        "track": track, "accepted_steps": accepted_steps,
        "solver": {"method": "RK4_WGS84_METRIC_DERIVATIVES", "maximum_step_s": step,
                   "output_step_s": output_step, "spatial_interpolation": "bilinear",
                   "temporal_interpolation": "linear", "velocity_units": "m/s",
                   "forcing_time_knots_aligned": True,
                   "position_units": "geographic_degrees", "maximum_steps": MAX_STEPS},
        "forcing": {"time_start_utc": str(field.time_utc[0]) + "Z",
                    "time_end_utc": str(field.time_utc[-1]) + "Z",
                    "selected_depth_m": field.selected_depth_m,
                    "shape": list(sampler.u.shape),
                    "provenance": {key: field.metadata[key] for key in (
                        "product", "dataset", "title", "u_variable", "v_variable", "sha256",
                        "source_url", "issued_at_utc", "retrieved_at_utc", "license", "data_kind"
                    ) if key in field.metadata}},
        "physical_validation": False, "plastic_motion_validated": False,
        "tank_flow_used": False, "heldout_buoy_positions_used": False,
        "limitations": [
            "The supplied current field is model output, not measured waste motion.",
            "No windage, object response, beaching, retention or diffusion is inferred.",
            "Missing cells and unavailable times stop the track; no extrapolation is used.",
            "Forecast causality requires a separately verified issue-time/as-of receipt.",
            "Ocean currents do not calibrate the centimetre-scale tank experiment.",
        ],
    }

```

FILE: tests/unit/test_advection_time_knots.py
```python
"""Numerical regressions for irregular forcing times, never new field evidence."""

from datetime import UTC, datetime, timedelta
from fractions import Fraction

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import advection
from apps.ocean.reeftrace_ocean.field import OceanField, _wgs84_metres_per_degree

EPOCH = datetime(2026, 10, 17, tzinfo=UTC)
METRES_LON, _ = _wgs84_metres_per_degree(0)


def forcing(times=(0, 650, 1400), speeds=(0, 1, 0)):
    seconds = np.asarray(times, dtype=float)
    shape = (len(times), 2, 2)
    return OceanField(
        np.datetime64("2026-10-17T00:00:00", "ns")
        + np.rint(seconds * 1_000_000_000).astype("timedelta64[ns]"),
        np.array([-1.0, 1.0]), np.array([-1.0, 1.0]),
        np.broadcast_to(np.asarray(speeds, dtype=float)[:, None, None], shape).copy(),
        np.zeros(shape), np.ones(shape, dtype=bool), 0.25,
        {"velocity_units": "m/s", "product": "SYNTHETIC_TIME_KNOT_REGRESSION"},
    )


def exact_integral(times, speeds, start, end):
    """Exact trapezoid areas of the declared piecewise-linear time function."""
    start, end = Fraction(str(start)), Fraction(str(end))
    area = Fraction(0)
    for a, b, u0, u1 in zip(times[:-1], times[1:], speeds[:-1], speeds[1:], strict=True):
        a, b, u0, u1 = (Fraction(str(value)) for value in (a, b, u0, u1))
        left, right = max(a, start), min(b, end)
        if right > left:
            slope = (u1 - u0) / (b - a)
            left_u, right_u = u0 + slope * (left - a), u0 + slope * (right - a)
            area += (right - left) * (left_u + right_u) / 2
    return area


def integrate(source=None, *, start=0, horizon=1000, step=300, output=1000):
    return advection.advect_current(
        source or forcing(), latitude_deg=0, longitude_deg=0,
        start_time_utc=EPOCH + timedelta(seconds=start),
        horizon_s=horizon, step_s=step, output_step_s=output,
    )


@pytest.mark.parametrize("start,horizon,area", [
    (0, 1000, Fraction(1780, 3)),
    (100, 900, Fraction(22840, 39)),
    (100, 1000, Fraction(8220, 13)),
    (650, 450, Fraction(315)),
])
def test_rk4_integrates_each_linear_time_piece_with_arbitrary_start(start, horizon, area):
    # These exact areas independently verify both the equation and horizon meaning:
    # a 900-second horizon from t=100 ends at t=1000, not t=900 or t=1100.
    assert exact_integral((0, 650, 1400), (0, 1, 0), start, start + horizon) == area
    result = integrate(start=start, horizon=horizon)
    assert result["status"] == "COMPLETED"
    assert result["completed_horizon_s"] == horizon
    assert result["track"][-1]["longitude_deg"] * METRES_LON == pytest.approx(
        float(area), abs=1e-9,
    )
    assert result["solver"]["forcing_time_knots_aligned"] is True
    assert result["solver"]["method"] == "RK4_WGS84_METRIC_DERIVATIVES"


def test_several_irregular_knots_and_output_boundaries_preserve_exact_time_integral():
    times, speeds = (0, 650, 1400, 1800), (0.2, 1, 0.1, 0.8)
    result = integrate(forcing(times, speeds), start=123, horizon=1500, output=479)
    assert result["status"] == "COMPLETED"
    assert [point["elapsed_s"] for point in result["track"]] == [0, 479, 958, 1437, 1500]
    for point in result["track"]:
        area = exact_integral(times, speeds, 123, 123 + point["elapsed_s"])
        assert point["longitude_deg"] * METRES_LON == pytest.approx(float(area), abs=1e-9)


@pytest.mark.parametrize("start,horizon,completed", [(0, 1800, 1400), (100, 1800, 1300)])
def test_unaligned_forcing_end_retains_the_entire_supported_prefix(start, horizon, completed):
    result = integrate(start=start, horizon=horizon, output=900)
    assert result["status"] == "PARTIAL"
    assert result["reason_code"] == "OUTSIDE_FORCING_TIME"
    assert result["completed_horizon_s"] == completed
    assert result["track"][-1]["elapsed_s"] == completed
    assert result["track"][-1]["time_utc"] == "2026-10-17T00:23:20Z"
    assert result["track"][-1]["longitude_deg"] * METRES_LON == pytest.approx(
        float(exact_integral((0, 650, 1400), (0, 1, 0), start, 1400)), abs=1e-9,
    )


def test_request_ending_exactly_at_last_forcing_time_is_completed():
    result = integrate(horizon=1400, output=900)
    assert result["status"] == "COMPLETED"
    assert result["reason_code"] is None
    assert result["completed_horizon_s"] == 1400
    assert result["track"][-1]["longitude_deg"] * METRES_LON == pytest.approx(700)


def test_request_starting_at_forcing_end_has_no_invented_future():
    result = integrate(start=1400, horizon=100)
    assert result["status"] == "UNSUPPORTED"
    assert result["reason_code"] == "OUTSIDE_FORCING_TIME"
    assert result["completed_horizon_s"] == result["accepted_steps"] == 0
    assert len(result["track"]) == 1
    assert result["track"][0]["elapsed_s"] == result["track"][0]["longitude_deg"] == 0


def test_exact_valid_knot_is_allowed_but_does_not_bridge_a_masked_future_interval():
    source = forcing()
    source.valid_mask[-1] = False
    source.eastward_m_s[-1] = np.nan
    at_knot = integrate(source, horizon=650)
    after_knot = integrate(source, horizon=1000)
    assert at_knot["status"] == "COMPLETED"
    assert at_knot["completed_horizon_s"] == 650
    assert after_knot["status"] == "PARTIAL"
    assert after_knot["reason_code"] == "MASKED_CURRENT_CELL"
    assert after_knot["completed_horizon_s"] == 650
    assert after_knot["track"][-1] == at_knot["track"][-1]


def test_masked_arrival_knot_never_accepts_the_future_position():
    source = forcing()
    source.valid_mask[1] = False
    source.eastward_m_s[1] = np.nan
    result = integrate(source, horizon=650)
    # Every t>0 interpolation needs the masked t=650 sample, even before arrival.
    assert result["status"] == "UNSUPPORTED"
    assert result["reason_code"] == "MASKED_CURRENT_CELL"
    assert result["completed_horizon_s"] == result["accepted_steps"] == 0
    assert len(result["track"]) == 1


def test_positive_submicrosecond_steps_integrate_position_instead_of_skipping_time():
    result = integrate(forcing((0, 0.000001, 0.000002), (1, 1, 1)),
                       horizon=0.000002, output=0.000002)
    assert result["status"] == "COMPLETED"
    assert result["completed_horizon_s"] == 0.000002
    assert result["accepted_steps"] == 4
    assert result["track"][-1]["longitude_deg"] * METRES_LON == pytest.approx(
        0.000002, abs=1e-18,
    )


def test_unrepresentable_absolute_time_progress_fails_closed_without_advancing():
    source = forcing((0, 1), (1, 1))
    # Float seconds from a distant epoch cannot distinguish a nanosecond increment
    # at this start. Do not advance elapsed time while sampling one unchanged time.
    source = OceanField(
        np.array(["1900-01-01", "2090-01-01"], dtype="datetime64[ns]"),
        source.longitude_deg, source.latitude_deg, source.eastward_m_s,
        source.northward_m_s, source.valid_mask, source.selected_depth_m, source.metadata,
    )
    result = integrate(source, horizon=1e-9, output=1e-9)
    assert result["status"] == "UNSUPPORTED"
    assert result["reason_code"] == "TIME_STEP_NOT_REPRESENTABLE"
    assert result["completed_horizon_s"] == result["accepted_steps"] == 0
    assert len(result["track"]) == 1
    assert result["track"][0]["longitude_deg"] == 0


def test_forcing_knot_splits_are_included_in_conservative_preflight_budget(monkeypatch):
    # Four max-size intervals plus one output bound alone would fit this limit;
    # the additional forcing-knot split must be accounted for before integration.
    monkeypatch.setattr(advection, "MAX_STEPS", 5)
    with pytest.raises(ValueError, match="bounded step budget"):
        integrate()

```
````

### docs/grok-evidence/rk4-actual-patch-review-response.txt

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/rk4-actual-patch-review-response.txt

Bytes: 3017; SHA-256: `109fa54c04053751239ef47b0959d4623d995b9a3a1893ec9adeda16ded5b76b`. Role: saved Grok static adversarial response: no actionable defect found, not execution; restrictive COMPLETED-only advice not adopted. Quoted record; read the ledger for current status.

````text
Grok web static adversarial review, retrieved 17 October 2026. No repository execution. Any finding is checked locally before acceptance; local regression evidence is separate.

GrokWorked for 20sStatic adversarial review. No execution is claimed. Prior rejected arithmetic is left rejected; the rational tests remain authoritative, and 585.641… m (absolute 100→1000) and 632.307… m (absolute 100→1100) are not restated as new derivations.
No actionable logic defect found in the supplied advect_current scheduling, mask handling, budget or completion logic.

Knot / offset scheduling. searchsorted(..., side="right") on forcing_elapsed followed by target = min(elapsed+step, horizon, next_output, knot) and the triple guard dt>0, target>elapsed, offset+target>offset+elapsed prevent both knot-straddling stages and silent time advance. Exact landing on a forcing time is accepted when the arrival sample succeeds; the next iteration then raises OUTSIDE_FORCING_TIME if the horizon continues, retaining completed_horizon_s at the last supported knot. This matches the forcing-end and exact-end tests.
Strict mask. _bracket plus the per-corner mask check inside sample still reject any contributing masked corner. The two mask tests confirm that an exact valid knot is allowed while a subsequent interval that requires a masked corner fails with MASKED_CURRENT_CELL and does not accept a future position, and that a masked arrival knot fails before any positive step.
Budgets. The preflight adds the count of knots strictly inside (0, horizon) to the ceiling terms and raises before integration; the runtime check remains accepted_steps >= MAX_STEPS. The monkey-patched test shows the knot term is necessary.
Completion. A request that ends exactly at the last forcing time returns COMPLETED; a start at the forcing end returns UNSUPPORTED with a single zero-elapsed point. No extrapolation path exists.

What could not be verified from the pasted source alone. Floating-point cancellation when offset is within a few ulps of a knot (beyond the distant-epoch unrepresentable test), and the precise interleaving count when step_limit_s is much smaller than the requested step on a non-uniform spatial field. Both are residual precision concerns already bounded by the fail-closed guard; they do not alter the reviewed control flow.
Sensitivity-experiment contract. Integration-only sensitivity correctly runs the three solver steps independently and compares numeric positions only at common 300 s timestamps reached with COMPLETED, while missing coverage and status changes stay explicit and partial paths remain in the denominator. Event-only sensitivity correctly uses one 75 s path, down-samples it to 300/150/75 chords (terminal partial point retained), and compares status/event identity/time on that single trajectory; it must not be compared with independently integrated native 300/150 paths. Neither experiment supplies physical truth, a confidence interval, or a reason to retune frozen NOAA results.
````

### docs/grok-evidence/rk4-patch-local-verification.json

Source: https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence/rk4-patch-local-verification.json

Bytes: 5722; SHA-256: `ba297bd96e15eb00397db452c3e650713648ccc356cae8ff2c475df484356208`. Role: local Python patch regression and exact pre-patch replay receipt, not Grok execution or new field evidence. Quoted record; read the ledger for current status.

````json
{
  "current_advection_sha256": "7ad3539b48290244abd7d1de382855f5c242e23b79af2bf15813455951888f9f",
  "kind": "LOCAL_PATCH_REGRESSION_NOT_NEW_FIELD_EVIDENCE",
  "new_metadata_only": {
    "forcing_time_knots_aligned": true
  },
  "reference_file": "rk4-prepatch-current-reference.json",
  "reference_sha256": "953ea1db0f70d920729f3136b75258cafede2dc0fbd361a39699dc64e85ad6b2",
  "releases": [
    {
      "accepted_steps": 72,
      "exact_track_match": true,
      "release_id": "release-1",
      "status": "COMPLETED",
      "track_point_count": 73
    },
    {
      "accepted_steps": 72,
      "exact_track_match": true,
      "release_id": "release-2",
      "status": "COMPLETED",
      "track_point_count": 73
    },
    {
      "accepted_steps": 72,
      "exact_track_match": true,
      "release_id": "release-3",
      "status": "COMPLETED",
      "track_point_count": 73
    },
    {
      "accepted_steps": 72,
      "exact_track_match": true,
      "release_id": "release-4",
      "status": "COMPLETED",
      "track_point_count": 73
    },
    {
      "accepted_steps": 72,
      "exact_track_match": true,
      "release_id": "release-5",
      "status": "COMPLETED",
      "track_point_count": 73
    },
    {
      "accepted_steps": 72,
      "exact_track_match": true,
      "release_id": "release-6",
      "status": "COMPLETED",
      "track_point_count": 73
    }
  ],
  "scenarios": {
    "downstream-corridor-v2": {
      "all_release_outcomes_exact_match": true,
      "baseline_summary": {
        "denominator_policy": "all_fixed_releases_including_missing_forcing_and_partial_paths",
        "entered_count": 6,
        "intercepted_count": 0,
        "no_entry_count": 0,
        "protected_entry_count_bounds": [
          6,
          6
        ],
        "protected_entry_fraction_bounds": [
          1.0,
          1.0
        ],
        "release_count": 6,
        "unresolved_count": 0
      },
      "layouts": [
        {
          "id": "central",
          "label": "Central coverage",
          "summary": {
            "denominator_policy": "all_fixed_releases_including_missing_forcing_and_partial_paths",
            "entered_count": 2,
            "intercepted_count": 4,
            "no_entry_count": 0,
            "protected_entry_count_bounds": [
              2,
              2
            ],
            "protected_entry_fraction_bounds": [
              0.3333333333333333,
              0.3333333333333333
            ],
            "release_count": 6,
            "unresolved_count": 0
          }
        },
        {
          "id": "flanking",
          "label": "Flanking coverage",
          "summary": {
            "denominator_policy": "all_fixed_releases_including_missing_forcing_and_partial_paths",
            "entered_count": 4,
            "intercepted_count": 2,
            "no_entry_count": 0,
            "protected_entry_count_bounds": [
              4,
              4
            ],
            "protected_entry_fraction_bounds": [
              0.6666666666666666,
              0.6666666666666666
            ],
            "release_count": 6,
            "unresolved_count": 0
          }
        }
      ],
      "recommendation": {
        "best_layout_id": "central",
        "comparison_basis": "strict_nonoverlap_of_model_protected_entry_count_bounds",
        "reason": "Central coverage has a strictly lower modeled entry range for this frozen scenario.",
        "status": "BEST_LAYOUT"
      }
    },
    "initial-proxy-v1": {
      "all_release_outcomes_exact_match": true,
      "baseline_summary": {
        "denominator_policy": "all_fixed_releases_including_missing_forcing_and_partial_paths",
        "entered_count": 0,
        "intercepted_count": 0,
        "no_entry_count": 6,
        "protected_entry_count_bounds": [
          0,
          0
        ],
        "protected_entry_fraction_bounds": [
          0.0,
          0.0
        ],
        "release_count": 6,
        "unresolved_count": 0
      },
      "layouts": [
        {
          "id": "central",
          "label": "Central coverage",
          "summary": {
            "denominator_policy": "all_fixed_releases_including_missing_forcing_and_partial_paths",
            "entered_count": 0,
            "intercepted_count": 4,
            "no_entry_count": 2,
            "protected_entry_count_bounds": [
              0,
              0
            ],
            "protected_entry_fraction_bounds": [
              0.0,
              0.0
            ],
            "release_count": 6,
            "unresolved_count": 0
          }
        },
        {
          "id": "flanking",
          "label": "Flanking coverage",
          "summary": {
            "denominator_policy": "all_fixed_releases_including_missing_forcing_and_partial_paths",
            "entered_count": 0,
            "intercepted_count": 2,
            "no_entry_count": 4,
            "protected_entry_count_bounds": [
              0,
              0
            ],
            "protected_entry_fraction_bounds": [
              0.0,
              0.0
            ],
            "release_count": 6,
            "unresolved_count": 0
          }
        }
      ],
      "recommendation": {
        "best_layout_id": null,
        "comparison_basis": "strict_nonoverlap_of_model_protected_entry_count_bounds",
        "reason": "Both hypothetical layouts have the same fully resolved model entry count.",
        "status": "TIE"
      }
    }
  },
  "snapshot_sha256": "bb9dae3ae753b5cb1cf01304b7bbe14861c8e1b1ac0514c5947838eb711feeb5",
  "tests": {
    "advection_prevention_and_new_knot_regressions": 87,
    "related_current_and_ocean_api_tests": 99,
    "ruff": "passed"
  }
}
````

## C. Bundle inventory

The inventory lists embedded source files, not independent experiments. Hashes identify bytes; they are not signed attestations or claims of execution.

````json
[
  {
    "file": "docs/grok-ml-diagnostic.md",
    "bytes": 5796,
    "sha256": "912c8ce8cafcc92af32d0d22687b9dde437f915122753039c57c55067189ef16",
    "type": "research/build record or exact prompt sequence; no blanket authorship or execution claim"
  },
  {
    "file": "docs/grok-motion-ablation.md",
    "bytes": 6028,
    "sha256": "dc213fb25261937601e890cca05fd6a57d78b5bf5d2e6b68737d2ce46673b848",
    "type": "research/build record or exact prompt sequence; no blanket authorship or execution claim"
  },
  {
    "file": "docs/grok-ml-next-study.md",
    "bytes": 8119,
    "sha256": "4dfb63c5193c8619b4059c5513279ce4e72bb4af983d65fef96619f01941150e",
    "type": "research/build record or exact prompt sequence; no blanket authorship or execution claim"
  },
  {
    "file": "docs/grok-ml-next-prompts.txt",
    "bytes": 8675,
    "sha256": "ff7f0843b915bf2cdb35a5a4a640607d533835ec6d78c566c0ec1e91e09a7282",
    "type": "research/build record or exact prompt sequence; no blanket authorship or execution claim"
  },
  {
    "file": "docs/grok-kalman-build.md",
    "bytes": 8583,
    "sha256": "3d5072843526e2d33e1b4f38875c26cbba6c8060964ae369d69a7c820a7b070c",
    "type": "research/build record or exact prompt sequence; no blanket authorship or execution claim"
  },
  {
    "file": "docs/grok-fresh-build.md",
    "bytes": 6639,
    "sha256": "bb2cf0c19e85b2ba858e32e18a36522b16ffb3c7c8dee17d0cda248c991b4aa3",
    "type": "research/build record or exact prompt sequence; no blanket authorship or execution claim"
  },
  {
    "file": "docs/grok-space-context.md",
    "bytes": 8765,
    "sha256": "c30d5f24bea0d538b252d4d488e0e3f944c862cf31174a3a52a3f5146bb0645f",
    "type": "research/build record or exact prompt sequence; no blanket authorship or execution claim"
  },
  {
    "file": "docs/rk4-numerical-quality.md",
    "bytes": 6177,
    "sha256": "8b320c22cfb0cae42f6e8db3165bf67337897ff6217d9e9afa8e0bccf5929675",
    "type": "research/build record or exact prompt sequence; no blanket authorship or execution claim"
  },
  {
    "file": "docs/next-current-data-study.md",
    "bytes": 5214,
    "sha256": "8526b3c0cfe74185a50d5aa5596a90d5ea6155d5f64cadb8c64dccd803c82165",
    "type": "research/build record or exact prompt sequence; no blanket authorship or execution claim"
  },
  {
    "file": "docs/grok-evidence/01-initial-build-prompt.txt",
    "bytes": 35255,
    "sha256": "dcc024de26cababad49055d0d91cd03026ef75c4c3252a25f9d86b8bc047945e",
    "type": "saved prompt prepared for the existing Grok project"
  },
  {
    "file": "docs/grok-evidence/02-source-static-review.txt",
    "bytes": 4169,
    "sha256": "130d64490933ade4faa56022a5e3049404c2c96baf47eaa122a7f93601a010cf",
    "type": "saved Grok static review output; execution assertions are not independently attested here"
  },
  {
    "file": "docs/grok-evidence/03-case-and-chalk-static-review.txt",
    "bytes": 1769,
    "sha256": "f568768f3c49c2759dc7a807a3c2b97014c6f07cc40149a848fd59d269cf4ed0",
    "type": "saved Grok static review output for commit 3a99477"
  },
  {
    "file": "docs/grok-evidence/04-initial-build-handoff.txt",
    "bytes": 3038,
    "sha256": "54f5b0b7ebcdc06383fc1e08d0ba913507b905eb3d725ef4601c7c77708b1d35",
    "type": "historical local handoff, not a Grok-authored response"
  },
  {
    "file": "docs/grok-evidence/05-initial-local-verification.json",
    "bytes": 984,
    "sha256": "c01e43c1d031534ad93277115dcf89f3da18bacd49504a5304028447db07e0b6",
    "type": "historical local execution receipt, not Grok execution"
  },
  {
    "file": "docs/grok-evidence/06-initial-source-bundle-verification.json",
    "bytes": 274,
    "sha256": "6fa2e6c95ff012493288453752d32354c9b6668fbcf1d52b28202416eccb531b",
    "type": "historical local source-bundle receipt"
  },
  {
    "file": "docs/grok-evidence/07-kalman-build-prompt.txt",
    "bytes": 6573,
    "sha256": "0530c94f4eeadadd57c2395d51d96c510369c8e5e631295e21a22740dd66c067",
    "type": "saved prompt prepared for the existing Grok project"
  },
  {
    "file": "docs/grok-evidence/08-kalman-static-review.txt",
    "bytes": 22606,
    "sha256": "95b1f47214b9dcd23f3b27c4ee6e85084a7c3676021463856457992140372899",
    "type": "saved Grok review/conversation capture; includes historical drafts and corrections"
  },
  {
    "file": "docs/grok-evidence/09-kalman-draft-code.txt",
    "bytes": 3533,
    "sha256": "3211491b5637ec173f4206042df41672a6d4e9b7d42072e1b015a589cf4179c5",
    "type": "saved draft; not the authoritative current implementation"
  },
  {
    "file": "docs/grok-evidence/10-fresh-protocol-static-review.txt",
    "bytes": 2537,
    "sha256": "17d3d375fb15e302d9a95c0dfc648ebc7738ef58b02077110bc1c55686b44164",
    "type": "saved Grok static protocol review output"
  },
  {
    "file": "docs/grok-evidence/11-fresh-schema-static-review.txt",
    "bytes": 2501,
    "sha256": "ea3e9ca9a9a3542b7bf3db62dd69ddcd50731d38d3c85bbb7f1c25bc32ef7638",
    "type": "saved Grok static schema/amendment review output"
  },
  {
    "file": "docs/grok-evidence/12-fresh-forecast-static-review.txt",
    "bytes": 1514,
    "sha256": "d309cba3606ad9370caf764e3ae2961e5890dd835d084cb6fa116925e451e8c8",
    "type": "saved Grok static evaluator review output"
  },
  {
    "file": "docs/grok-evidence/13-algorithm-and-demo-static-review.txt",
    "bytes": 4628,
    "sha256": "46055e3c673caf64cb6b1bb2e81c637ecd1de5092d2c0b4cb69eea88e6d665b4",
    "type": "saved Grok static algorithm/demo review; later corrected in item 14"
  },
  {
    "file": "docs/grok-evidence/14-final-accounting-conversation-capture.txt",
    "bytes": 9530,
    "sha256": "a5062e2d165c066f8c18afdb7104cdc0cccf4119bd6367e325a1446495f3b151",
    "type": "saved browser accessibility-text capture, including repeated/corrected historical messages"
  },
  {
    "file": "docs/grok-evidence/rk4-knot-review-prompt.txt",
    "bytes": 18615,
    "sha256": "0d9f7638b60aca4994d09e4461aafe16afe71fa524a68ea190a0ce32f109261d",
    "type": "actual outbound Grok web prompt: initial forcing-knot and expiry review"
  },
  {
    "file": "docs/grok-evidence/rk4-knot-review-initial-response.txt",
    "bytes": 5395,
    "sha256": "eafe86340f63c6506a0be566922373448c45f47c4248c597c2ab882ede2dde0e",
    "type": "saved Grok static response: includes rejected arithmetic and time-only snap"
  },
  {
    "file": "docs/grok-evidence/rk4-knot-correction-prompt.txt",
    "bytes": 2366,
    "sha256": "74558363dfd41520e9bb08707e9d38ffc72dda93e9b68d972099b49758debfc8",
    "type": "actual outbound Grok web prompt: no-snap contract and arithmetic correction"
  },
  {
    "file": "docs/grok-evidence/rk4-knot-corrected-response.txt",
    "bytes": 3851,
    "sha256": "9ba237abcd174f45d9a9ad0c637a443ad8259de707c3a5e76bfa89cdf3092048",
    "type": "saved Grok static response: retains an integral error corrected subsequently"
  },
  {
    "file": "docs/grok-evidence/rk4-final-math-and-code-prompt.txt",
    "bytes": 1977,
    "sha256": "8cdc935af43c5ef65eec28c81f9137dba9c579fef6176ff5a553a7bee12f7cdf",
    "type": "actual outbound Grok web prompt: independent integrals and sensitivity contract"
  },
  {
    "file": "docs/grok-evidence/rk4-final-code-review-response.txt",
    "bytes": 2828,
    "sha256": "3b1cc7ee964e5ece4ae6ed3e029e549ddec1c8fab581ff3e12a22a3563da1d49",
    "type": "saved Grok static response: accidental rejection of valid alternate-horizon integral and restrictive comparison advice not adopted"
  },
  {
    "file": "docs/grok-evidence/rk4-actual-patch-review-prompt.txt",
    "bytes": 24590,
    "sha256": "b228ee43f706b0394430676d8d265720fb60c6a762a7e00f98be2995c3d004a9",
    "type": "actual outbound Grok web prompt: actual local scheduling patch and regressions"
  },
  {
    "file": "docs/grok-evidence/rk4-actual-patch-review-response.txt",
    "bytes": 3017,
    "sha256": "109fa54c04053751239ef47b0959d4623d995b9a3a1893ec9adeda16ded5b76b",
    "type": "saved Grok static adversarial response: no actionable defect found, not execution; restrictive COMPLETED-only advice not adopted"
  },
  {
    "file": "docs/grok-evidence/rk4-patch-local-verification.json",
    "bytes": 5722,
    "sha256": "ba297bd96e15eb00397db452c3e650713648ccc356cae8ff2c475df484356208",
    "type": "local Python patch regression and exact pre-patch replay receipt, not Grok execution or new field evidence"
  }
]
````
