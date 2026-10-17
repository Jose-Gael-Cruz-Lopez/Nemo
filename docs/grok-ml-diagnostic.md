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
