# Fixed-noise Kalman motion diagnostic

This is a separate, reproducible comparison on **four already viewed NOAA buoy-days**. It adds a constant-velocity Kalman state estimator beside the unchanged stationary, last-drift, mean-drift, and own-prefix ridge algorithms. It does not replace or re-score the identity of the original frozen study, and it does not promote a model into the tank experiment.

## Freeze and replay

- `protocol.json` and its detached SHA-256 fix the model IDs, acquired drifter IDs, 18-position prefix, six forecast times, noise assumptions, metrics, failure policy, and scientific limitations.
- `implementation-receipt.json` was written before the first new real-data Kalman score. It binds both new Python modules and the protocol. Its UTC timestamp is `2026-10-17T09:29:35.181999+00:00`; the first scored report was saved at `2026-10-17T09:29:42.550092+00:00`.
- `report.json` and its detached SHA-256 contain the first full result, not a hand-entered summary. The runtime checks the old study's pinned input lineage, both new module hashes, and the new reference report. Discrete values must match exactly. Floating replay allows relative `1e-10` or absolute `1e-8` roundoff only.
- The timestamps record our execution order; they are not an independent third-party attestation. Freezing this new design before its first score does **not** make the previously viewed drifters an unseen test.

Recompute without network, camera, provider, or application-store writes:

```sh
.venv/bin/python -c 'from apps.ocean.reeftrace_ocean.kalman_diagnostic import run_kalman_diagnostic; import json; print(json.dumps(run_kalman_diagnostic(), allow_nan=False))'
.venv/bin/python -m pytest tests/unit/test_kalman.py tests/unit/test_kalman_diagnostic.py tests/unit/test_kalman_replay.py -q
```

## What is estimated

The state is local position and velocity, `[x, y, vx, vy]`. Measurement covariance is assumed to be `10000 I m²`, equivalent to a 100 m position standard deviation. Continuous white acceleration uses fixed spectral density `q = 1e-6 m²/s³` and the actual elapsed seconds. Neither noise hyperparameter is fitted. The state is estimated on the permitted prefix; the baseline algorithms can also adapt parameters on their own permitted prefixes. The report's `parameter_fitting_performed: false` flag therefore has the explicit scope `KALMAN_NOISE_HYPERPARAMETERS_ONLY`.

Initialization is at the second fix: position is the second measurement, velocity is the first difference, and their covariance includes the shared second-fix error. It assumes constant first-interval velocity and independent, identically distributed isotropic position errors. Subsequent measurements update the prefix state with a Joseph covariance update. Forecasts start at the **filtered** final prefix state, with no future measurement corrections.

All 20 model tracks are prepared before any of the six future coordinates are accessed. Future identity and timestamps can be checked before that gate. Each model keeps all six outcomes on failure; any acquired failure withholds every common aggregate. This avoids ranking models on selectively successful subsets.

## First recorded result

All 120 acquired model/horizon outcomes were scored. These reuse **24 observed intervals**, not 120 independent trials. The original plan targeted six groups; only four were acquired, leaving two slots missing.

| Model | Mean position error, m | Sixth-hour error, m | Interval velocity RMSE, m/s |
| --- | ---: | ---: | ---: |
| Stationary | 2911.30 | 4942.34 | 0.2781 |
| Last drift | 1579.85 | 3323.65 | 0.2271 |
| Mean drift | 1846.71 | 2883.49 | 0.2125 |
| Own-prefix ridge AR(1) | 729.37 | 1202.95 | 0.1177 |
| Fixed-noise Kalman CV | 1600.61 | 3231.05 | 0.2279 |

The Kalman candidate is worse than ridge on these viewed groups. Its value here is a transparent state/covariance workflow to investigate, not a claim of better forecast skill.

The reported latent position covariance is distinct from future-observation covariance. Ellipse hit calculations compare observed NOAA positions against `P_position + R`, not `P_position` alone. Nominal 90% ellipse hits were 6/6, 6/6, 6/6, and 1/6 across the four groups. These small, dependent, retrospective hit fractions are **uncalibrated diagnostics**, not validated confidence levels or source probabilities.

## Scientific boundaries and possible physical transfer

NOAA hourly positions are QC/interpolated products and may use later raw fixes upstream. The CSV's velocity uncertainty columns are not used and do not determine the assumed position covariance. Buoys are not observed plastic, no matched ocean-current forcing was added, and neither a pollution source nor reef benefit is inferred.

A later camera experiment could use the same state-estimation equations with tank centimetres and actual frame times. It would require an independently measured camera-position error, a new physical process-noise protocol, wall/retention handling, and held-out real trials. The NOAA 100 m/noise values must not be copied into centimetre-scale hardware. Missing observations should trigger prediction without a fabricated measurement; future camera measurements must not update a frozen forecast being scored.

Primary references: [OpenCV Kalman filter](https://docs.opencv.org/4.13.0/dd/d6a/classcv_1_1KalmanFilter.html), [continuous white-noise discretization](https://filterpy.readthedocs.io/en/latest/_modules/filterpy/common/discretization.html), [NOAA hourly GDP product](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php), and [Elipot et al. hourly drifter methodology](https://www.aoml.noaa.gov/phod/gdp/papers/Elipot_et_al-2016.pdf).
