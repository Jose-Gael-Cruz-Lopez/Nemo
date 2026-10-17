# V2 numerical portability verification

The v2 first-score artifacts, protocol, source hashes and original evaluator
remain unchanged. This is a **post-outcome software portability check**, not a
predeclared scientific tolerance or amendment to the frozen method. The same
immutable saved result is served by Data Lab and
Chalk. No new forecast is substituted for it and no model is tuned or promoted.

## Actual CI failure

[Run 39073934821, commit f493c5d](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/actions/runs/39073934821)
passed all 1,779 Python tests, the dashboard checks/build and isolated HTTP
workflow. Its additional v2 exact-float replay step failed. That failure is
preserved; this change does not relabel that run as successful.

A separate Linux x86_64 container using Python 3.12.15, NumPy 2.5.4, SciPy
1.18.1 and netCDF4 1.7.5 reproduced the discrepancy. Compared with the frozen
macOS first score, the first buoy's last-drift model differed in six latitude
values and one northward velocity component. Stationary and RK4 current-only
forecasts were identical. The last-drift differences are consistent with tiny
platform math-library roundoff in the spherical coordinate calculation.

| Computed quantity | Largest observed absolute difference | Explicit portability bound |
| --- | ---: | ---: |
| Latitude/longitude | 1.7763568394002505 × 10⁻¹⁴ degrees | 1 × 10⁻¹¹ degrees |
| Velocity | 9.825473767932635 × 10⁻¹⁴ m/s | 1 × 10⁻¹² m/s |
| Recomputed error/aggregate | 1.9726940081454813 × 10⁻⁹ m | 1 × 10⁻⁶ m |

These are **software numerical comparison bounds**. They do not represent
measurement precision, model uncertainty, physical validity or forecasting
skill. The degree bound is approximately one micrometre at the equator; the
metric bound is one micrometre. There is no relative tolerance.

## Separate verifier

```sh
.venv/bin/python -m scripts.verify_matched_current_v2_portable \
  --output /tmp/tideward-matched-v2-portable.json
```

The verifier:

1. Uses the unchanged frozen implementation to construct every forecast from
   context only, before reserved target coordinates are decoded for scoring.
2. Requires the trusted result identity, protocol/source/raw-byte hashes,
   detached hashes, chronology, schemas, groups, candidate order, statuses,
   counts, times, solver settings, units and provenance to match exactly.
3. Verifies each saved and recomputed forecast content hash against its own
   complete numbers. Different runtime hashes are disclosed, never substituted
   for the immutable saved pin.
4. Allows the bounds above only at an explicit set of computed-coordinate,
   computed-velocity and computed-error paths. CSV target/origin coordinates,
   configuration, input timing and arbitrary new fields receive no tolerance.
5. Recomputes the original score calculation and compares it with the fixed
   saved result. It records every accepted numeric difference, unit, bound,
   platform and whether forecasts/scores were bit-exact.
6. Revalidates the frozen artifacts afterward to reject a concurrent generation
   change. The result is a **verification receipt**, not a new first-score
   artifact. It never acquires data, calls providers or rewrites study files.

On the reproduced Linux run, 84 numeric leaves differed because the same
seven underlying last-drift differences appear in both the forecast and nested
score reports, and the affected errors appear in several aggregate views. These
are not 84 independent model observations. The maximum metric difference was
about two nanometres. The relative model ranking and negative current-only
result remain the same.

CI now runs this clearly named bounded verifier on Ubuntu. The stricter original
command remains available and unchanged:

```sh
.venv/bin/python -m scripts.evaluate_matched_current_v2_study \
  --output /tmp/tideward-matched-v2-exact.json
```

The exact command may reject an otherwise numerically equivalent result across
platforms; it must not be described as a cross-platform bit-exact guarantee.
The portable verifier does not claim that property either.

## Regression checks

Tests distinguish accepted tiny computed-number changes from rejected changes
to motion beyond the declared bound, metric errors above one micrometre,
statuses, counts, types, keys, times, origins, target coordinates, nonfinite
values, stale inner hashes and rehashed saved-artifact tampering. A modified
saved artifact remains invalid even if its change is within a float bound,
because its literal trusted file hash must still match.

The original v1 failure and all v1/v2 data and frozen numerical sources are
preserved. This software portability check does not alter the study's
retrospective status, two-buoy scope, prior forcing exposure, unresolved
assimilation/alias independence or absence of physical tank validation.
