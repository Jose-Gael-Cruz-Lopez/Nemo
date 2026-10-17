# Fresh NOAA GDP-ID motion study — v2

This is a bounded historical evaluation of six previously unscored GDP-ID groups, with known-WMO-alias exclusions. It is separate from the older four-drifter study and does not promote any model into the tank/source/prevention workflow.

## Why v2 exists

The unchanged v1 directory retains its actual failed attempt: two metadata body timeouts and one valid metadata response rejected because the new parser expected an empty `expno` unit instead of NOAA’s `count`. No v1 trajectory payload or model outcome existed. V2 is an explicit pre-outcome schema/transport amendment: same original 223 reserved IDs, three blocks, five fixed models and alias gates; corrected metadata units, 45-second per-request deadline and 300-second total wall budget. It is not an erased failure or an outcome-selected replacement cohort.

The global ID/WMO registry and origin-selection metadata are not motion-training data. The initial 28-fixture exclusion snapshot remains immutable; the v1/v2 registry lineage is exempt from being treated as an entire new exclusion universe. All future coordinates remained unavailable to model construction until the complete forecast receipt was written.

## Freeze and acquisition order

- V2 protocol frozen: `2026-10-17T14:55:59.497166+00:00`.
- Acquisition: `2026-10-17T14:58:53.865852+00:00` to `2026-10-17T14:59:15.152739+00:00`; 11 requests; 401,779 response bytes.
- Model/evaluator implementation receipt: `2026-10-17T15:02:47.765778+00:00`, before the first new model score.
- All 30 forecast tracks frozen before reading held coordinates: `2026-10-17T15:03:41.081532+00:00`.
- The coordinator pushed the design and implementation receipts to GitHub before the first score. These local timestamps/receipts document execution order; they are not third-party attestations.

The pipeline preserves source URLs, request-start/finish UTC, raw bytes and their SHA-256 sidecars; selection is rederived from the raw origin snapshots and global alias registry during replay. It never retries or changes endpoints inside an attempt. A real SIGALRM deadline bounds blocking CLI I/O as well as remaining HTTP timeouts. Acquisition is an explicit action; API/Data Lab replay cannot acquire more data.

## What was compared

One 24-hour trajectory per GDP ID. The first 18 hourly positions are allowed observation context; the next six positions are forecast without measurement resets. Each fixed algorithm estimates only its own prefix state/parameters. No global/shared model was trained and no held-out hyperparameter tuning occurred. The development/exclusion IDs never enter the new evaluation groups.

| Model | ADE, m | FDE at hour 6, m | Interval vector RMSE, m/s |
| --- | ---: | ---: | ---: |
| Stationary position persistence | 5010.201 | 8668.078 | 0.439076 |
| Last observed drift | 1573.423 | 3305.763 | 0.193552 |
| Mean observed drift | 2930.077 | 5004.445 | 0.257485 |
| Own-prefix ridge velocity AR(1) | 1772.130 | 3460.155 | 0.196928 |
| Fixed-noise constant-velocity Kalman | 1655.662 | 3410.802 | 0.197733 |

**The simple last-drift baseline has the lowest mean error here.** The prior viewed four-drifter result favored ridge; this fresh group evaluation does not repeat that ordering. Retaining this negative comparison is more informative than silently choosing new noise/ridge values. The study does not authorize automatic model selection or promotion.

All six groups and 180 model/hour outcomes were scored, with zero failed/unfilled cells. These reuse **36 distinct observed intervals**, not 180 independent experiments. Position errors use great-circle separation on the declared mean-radius sphere. Vectors use local projected metres divided by actual elapsed seconds. The Kalman first predicted interval starts at its filtered final prefix state; other models start at the raw last prefix position. All models run freely across the six-hour horizon.

## Alias and uncertainty limitations

The new candidate IDs and positive WMO mappings are unique in the frozen identity snapshot and exclude known reserved/selected WMOs. 10 old reserved IDs still have missing or ambiguous aliases: 12730, 12731, 27622, 27924, 27925, 8707978, 9624972, 9624974, 9712733, 9815211. Consequently `physical_alias_resolution_verified=false` and `statistical_independence=false`. The claim is new previously unscored **GDP-ID groups with known-alias exclusions**, not proven independent physical deployments or IDs never present in selection metadata.

Kalman position standard deviation remains the declared 100 m and acceleration spectral density remains 1e-6 m²/s³. They are not fitted sensor-error estimates. Observed-position ellipse hits use latent position covariance plus assumed measurement covariance `Pxy + R`; nominal 90% hits were 6/6, 6/6, 6/6, 6/6, 5/6, 3/6. These small correlated retrospective counts do not calibrate confidence or establish source probabilities.

NOAA GDP hourly positions are quality-controlled/interpolated historical estimates, potentially using later raw fixes upstream. `operational_causality=false`. Buoys are not observed plastic, matched ocean-current forcing was not acquired, and no physical tank validation, interception benefit, coral outcome, provider call or camera action is established by this study.

## Reproduce without acquisition

```sh
.venv/bin/python scripts/evaluate_fresh_drifter_study.py --output work/fresh-drifter-replay.json
.venv/bin/python -m pytest -q tests/unit/test_fresh_drifter*.py
```

The reader verifies protocol/exclusion/input/source hashes, the immutable metadata selection, both original model hashes and new evaluator receipt, then the frozen forecast and report. Missing or changed evidence never produces an invented passing score. Primary common-target metrics are withheld if any required target cell fails or is missing; per-group truth and explicit failures remain visible. The first-score function refuses to overwrite either forecast or report.

Primary sources: [NOAA GDP hourly product](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php), [dataset DOI](https://doi.org/10.25921/x46c-3620), [Elipot et al. hourly-data methodology](https://www.aoml.noaa.gov/phod/gdp/papers/Elipot_et_al-2016.pdf), [OpenCV Kalman operations](https://docs.opencv.org/4.13.0/dd/d6a/classcv_1_1KalmanFilter.html). Source access/license metadata and exact ERDDAP URLs are retained in the frozen artifacts.
