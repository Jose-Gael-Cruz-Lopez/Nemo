# ReefTrace real-data experiment and ML decision

Reviewed 16 October 2026. The dashboard's Data lab evaluates a **real historical NOAA surface-buoy trajectory**, independently of the controlled tank source-tracing demonstration. This adds an executable learned motion model and an honest external-data benchmark. It supplies no missing plastic-release labels.

## Exactly what was collected

The checked-in `data/public/noaa-gdp-8707978-19871003.csv` contains 24 hourly observations from drifter `8707978`, 3 October 1987 UTC, covering 00:00 through 23:00. Its 1,950 original bytes have SHA-256:

```text
b503de924bbfe82fb18a705917e527faaf26e51688845adb4b57f0cb121c2fca
```

The adjacent provenance manifest records the selected ERDDAP request, original retrieval time, attribution, product DOI and CC BY 4.0 license. `run_real_data_example()` requires both the manifest and the pinned code digest to match, validates the CSV units/times and verifies the experiment identity. It opens no network connection and requires no account or key. The original ingestion-only purpose remains visible in provenance; the forecast experiment is a new use of that fixture, not a claim that it was originally selected as a representative evaluation set.

The [NOAA hourly product description](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php) documents positions and east/north velocities after quality control and hourly interpolation. The [author's processing paper](https://www.aoml.noaa.gov/phod/gdp/papers/Elipot_et_al-2016.pdf) explains the derivation. The [specific ERDDAP metadata](https://erddap.aoml.noaa.gov/gdp/erddap/info/drifter_hourly_qc/index.html) describes the columns and license; the persistent dataset citation is [10.25921/x46c-3620](https://doi.org/10.25921/x46c-3620). This day is historical, not a current environmental incident.

**Important measurement boundary:** these published hourly locations are interpolated estimates. Their upstream processing may incorporate raw fixes later than a chosen hourly timestamp. A chronological split here prevents additional look-ahead in our code, but cannot undo upstream processing or establish raw real-time forecast skill.

## Exact train/test protocol

1. Keep the original order. Use positions at 00:00–17:00 as 18 training samples.
2. Freeze the models and error-radius calibration at 17:00.
3. Forecast 18:00–23:00 in a single six-step free run, without inserting any observed test positions into the trajectory.
4. Only then compare predictions with those six heldout published positions.
5. Report every baseline and endpoint error, including failures to outperform a naive method. Do not select/promote a model on this small test.

The published `ve`, `vn`, `err_ve` and `err_vn` fields never enter the fits or predictions. No future current field is supplied. Tests change every heldout position and every velocity/uncertainty column and verify that all model parameters, predicted coordinates and training error radii stay unchanged.

Chronological evaluation follows the principle in the [official TimeSeriesSplit documentation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html). The implementation is small NumPy code, rather than a new scikit-learn dependency.

## The three models

| Model | Fit and forecast | Why include it |
|---|---|---|
| Stationary position persistence | Every future point equals the final training position. | The most basic motion-forecast baseline. |
| Last observed displacement | Repeats the final training position difference once per future hour. | Tests whether immediate drift extrapolation beats doing nothing. |
| Learned ridge velocity autoregression | Learns a 2×2 transition matrix and mean drift from training-only finite-difference velocities; recursively predicts six future velocities and integrates position. | An actual trainable, inspectable linear ML baseline, with six effective parameters. |

For the learned model, center velocities on the training mean and scale them by a shared training-only RMS scalar. With standardized consecutive velocity rows `X` and `Y`, solve:

```text
W = solve(XᵀX + αI, XᵀY),  α = 1.0
v_next = mean_v + (v_previous − mean_v) W
p_next = p_previous + 3600 v_next
```

The scalar scaling cancels when applying the learned raw-velocity map. If the fitted matrix's spectral radius exceeds 0.98, scale it to that fixed bound. Both `α = 1.0` and `0.98` were specified in code; no search against heldout outcomes occurs. This is a constrained ridge autoregression, not an off-the-shelf unmodified scikit-learn estimator. The underlying penalty is the ordinary ridge objective documented by [scikit-learn's authors](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html).

Model parameters are emitted in the API/JSON report, so the demonstration does not depend on an opaque neural checkpoint. Sixteen training velocity pairs are insufficient to establish that a deep model trained from scratch generalizes. We therefore keep this experiment's learned baseline small and inspectable; this does not rule out separately validated transfer learning on a much larger appropriate dataset.

## Geographic geometry and units

Latitude and longitude are angles. The example uses a declared **spherical azimuthal equidistant** log/exp map centered on the first training position to obtain east/north metres, with mean radius 6,371,008.8 m. It checks a 50 km local budget, handles dateline wrap, and tests round-trips near the pole. Free-run predictions are converted back to geographic coordinates. Final point errors use spherical great-circle distance, in metres.

This is a deliberate spherical approximation, **not WGS84 ellipsoidal accuracy**. Local hindcast radii use Euclidean separation in that local map. The small map/sphere approximation and Earth ellipsoid discrepancy are not treated as physical forecast uncertainty. An eventual coastal application should use a proper ellipsoidal geodesic or suitable projection, with a numerical error budget; [GeographicLib's primary documentation](https://geographiclib.sourceforge.io/html/python/geodesics.html) explains ellipsoidal inverse/direct geodesic problems. Nothing in this experiment is passed to the tank's centimetre-space estimator.

## Actual reproducible results

Run from the repository root:

```sh
.venv/bin/python scripts/evaluate_real_data.py --output work/real-data-example.json
.venv/bin/pytest -q tests/unit/test_real_data.py tests/unit/test_ocean.py
```

| Model | Mean position error over six heldout hours | RMS position error | Error at hour six |
|---|---:|---:|---:|
| Stationary position persistence | 3,855.0 m | 4,323.8 m | 6,774.6 m |
| Last observed displacement | 4,385.8 m | 5,433.0 m | 9,832.2 m |
| Learned ridge velocity autoregression | 3,557.4 m | 4,318.5 m | 7,561.2 m |

The learned model's mean error is about 7.7% lower on this selected day, but its final error is higher than the stationary baseline. These mixed results are visible in the UI and full export. This does not establish dependable ocean forecast skill. There are only six dependent test points, from one drifter-day selected earlier to exercise ingestion.

For each model/horizon, the example computes a training-only 90th-percentile error radius from expanding-origin hindcasts. There are only 10, 9, 8, 7, 6 and 5 overlapping errors for horizons one through six. The report displays how many test points lie inside those radii but **never calls them calibrated 90% probability/confidence regions**. NOAA velocity confidence intervals are not reused as our forecast uncertainty.

## API/UI integration contract

```python
from apps.ocean.reeftrace_ocean.benchmark import run_real_data_example

report = run_real_data_example()  # JSON-native dict, no secrets or network
```

The report includes:

- `data_origin = REAL_HISTORICAL_NOAA_DRIFTER` and pinned integrity/provenance;
- `training_track` and `heldout_track`, each with `time_utc`, `latitude_deg`, `longitude_deg`;
- `models`, containing parameters, free-run predictions, mean/RMS/endpoint errors and training error radii;
- chronological `split`, coordinate-system definition and explicit limitations;
- `source_attribution.status = NOT_SUPPORTED_BY_THIS_DATASET`.

The UI may draw geographic traces, display the complete baseline comparison and export the report. It must preserve those origin/limitation labels. It must not make a tank incident, assign a fictional release site, claim to have identified the plastic producer or describe this as a real-reef cleanup trial.

## What needs more data next

For **tank source tracing**, the required labels are still complete measured webcam sessions, independent drift runs and an evaluator-held release log. Split whole runs and pump/lighting sessions; avoid random neighboring frames. For the controlled red token, HSV segmentation remains the operational detector because it is measurable and needs no unrelated underwater-image labels.

For **ocean forecast research**, collect many drifters and separated trajectories/time blocks, document drogue status and object response, and use matched contemporaneous physical forcing with proper coastal boundaries. The existing [Copernicus research and bounded download instructions](datasets.md#3-copernicus-marine-the-best-first-future-transport-input) remain a future path. A roughly 9 km global field does not resolve this tabletop tank or guarantee reef-channel currents. This 1987 sample is not silently paired with a modern SMOC product.

For **debris recognition**, TrashCan's underwater images and MARIDA's multispectral satellite patches have different sensor domains and do not give source-release truth. The dataset rights/domain review is preserved in [datasets.md](datasets.md). No permissive license or pretrained-weight validity is inferred from a mirror. No external neural weights are downloaded by this experiment.

## Additional dataset research — 16 October 2026

**Immediate core: measured tank trials with known releases.** Record independent webcam sessions, measured drift calibration, pump/lighting settings and timestamps. Keep release site/time in an evaluator-only log that the estimator and LLM cannot read. Hold out complete runs or sessions, including ambiguous retention-pocket arrivals and releases outside the candidate set; report correct rankings, wrong rankings, abstentions and invalid runs. These observations are still needed to validate the physical tracing demonstration. Public debris images and ocean currents cannot supply this missing tank ground truth.

The following sources were researched, **not downloaded, trained on or integrated into ReefTrace**:

| Source | Useful next experiment | Limits and access evidence |
|---|---|---|
| [NOAA IOOS coastal HF radar currents](https://ioos.noaa.gov/data/access-ioos-data/), with the [live NOAA NDBC catalog](https://dods.ndbc.noaa.gov/thredds/catalog/hfradar.html) | Use a small coastal region/time window of measured surface-current vectors as transport input, then compare predicted motion with independent, contemporaneous drifter tracks. IOOS describes hourly or 25-hour averaged products at approximately 500 m–6 km resolution. | Geographic/current observations, not debris-source labels. Coverage and missing values vary; even a 500 m grid cannot resolve individual coral branches or many reef passages. A new adapter and geographic transport/evaluation path would be required; the tank estimator cannot consume these coordinates directly. |
| [GLAD drifter trajectories, GRIIDC DOI 10.7266/N7416V0M](https://data.griidc.org/data/R1.x134.073:0032) | Expand motion/dispersion testing to multiple held-out drifters and launch groups. The historical July–October 2012 experiment includes 297 CODE-style near-surface drifters and positions interpolated to five-minute intervals. | These are drifters, not tracked plastic or known polluters. Processing uses interpolation and outlier handling; neighbouring samples and jointly released drifters are dependent. The catalog lists four ASCII files totalling about 543 MB, so review access terms and select a bounded subset before retrieval. No general forecast or source-attribution skill follows from catalog availability. |
| [SeaClear Marine Debris Dataset primary paper](https://www.nature.com/articles/s41597-024-03759-2), [official authors' repository](https://github.com/adjuras/seaclear-dataset), and [4TU data record](https://data.4tu.nl/datasets/4f1dff25-e157-4399-a5d4-478055461689) | Evaluate future shallow-water debris detection/segmentation. Authors report 8,610 ROV images, 40 categories and multiple sites/cameras; their paper identifies the dataset as CC BY 4.0. | Images do not establish release histories, transport paths or source identity. Underwater ROV imagery differs from the overhead webcam; the paper demonstrates difficult cross-site/camera generalization. The direct 4TU page returned HTTP 403 during this review; dataset descriptions and licensing were verified through the primary paper and official repository, not a downloaded archive. |

Keep these three future experiments separate: **detecting an object**, **predicting its motion**, and **distinguishing its possible entry sites** require different evidence and evaluation labels. A dataset's availability does not establish any of the other two tasks.
