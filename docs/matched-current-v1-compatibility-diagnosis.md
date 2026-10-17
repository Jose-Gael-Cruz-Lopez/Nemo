# Matched-current v1: saved-byte compatibility diagnosis

Review date: **17 October 2026**. This review uses only already saved v1 files.
It makes **no new request, model run, numerical score, protocol freeze or code
amendment**. The machine-readable source identities and axis calculations are in
[the diagnosis receipt](research-evidence/matched-current-v1-compatibility-diagnosis.json).

## What happened

The immutable v1 attempt made four requests, retained 751,334 response bytes and
blocked both planned GDP trajectory requests. Its saved first score and replay
retain **all 36 planned model/horizon cells**, with **zero scored cells** and null
errors. It obtained no GDP trajectory payload and selected no model. The twelve
planned future position estimates remain unavailable.

Two compatibility guards caused the failure:

1. NOAA's metadata response differed from the seed in two request-history
   timestamps, so the exact raw-hash gate blocked both GDP trajectory requests.
2. The downloaded HYCOM file passed the unchanged generic reader, but the study
   wrapper rejected native coordinate spacings against an overly tight decimal
   lattice tolerance. The actual coordinate labels show float32 rounding even
   though the NetCDF coordinate variables are stored as float64.

The guards preserved their failures. This document proposes an explicit,
reviewable v2 compatibility amendment; it does not turn the v1 attempt into a
successful comparison or authorize a hidden retry.

## NOAA: exactly two volatile history timestamps

Both seed and acquired DAS files contain **18,686 bytes**. Their full hashes are:

| File | SHA256 |
| --- | --- |
| Metadata seed | `66cdd12aff149d25cfa03fbcbe2046fb5657e7aa31795f0bfa0c41c3527efd39` |
| Acquired v1 response | `9931c4a300bc37096103ad6d9091e8e2aa77e318de2bdaa9da6c55508b2ef7f3` |

Only lines **425–426** differ. In the `history` field, both capture timestamps
changed from `2026-10-17T19:34:52Z` to `2026-10-17T21:11:25Z`:

```diff
-2026-10-17T19:34:52Z (local files)
+2026-10-17T21:11:25Z (local files)
-2026-10-17T19:34:52Z https://erddap.aoml.noaa.gov/gdp/erddap/tabledap/drifter_hourly_qc.das";
+2026-10-17T21:11:25Z https://erddap.aoml.noaa.gov/gdp/erddap/tabledap/drifter_hourly_qc.das";
```

Replacing those exact two old capture-time tokens with the acquired tokens makes
the seed bytes identical to the acquired bytes. Every other byte is unchanged,
including the `Version v2.01` history line, schema, units and metadata text. This
is evidence of a volatile request-history field; it is not evidence that an
unexpected units, version or schema change should be accepted.

The acquired origin identity/drogue CSV is byte-identical to its **640-byte**
seed, SHA256
`fe20f70d249e8e099ba63e97341ed52c3c1dff34f5055b6946a4438679b6a339`.
The selected IDs and identity metadata did not change. Both trajectory requests
remain recorded as `BLOCKED / DEPENDENCY_UNAVAILABLE`, with no body and no
request attempt.

## HYCOM: coordinate encoding, not a changed current model

The acquired HYCOM metadata XML is byte-identical to its **159,404-byte** seed,
SHA256
`741d5fcc5cd784415c9b8582394a05f4102f81f0d883821e8267a61ea698164d`.
The current file contains **572,604 bytes**, SHA256
`7005d62128f100066c6d7120fc4e32c4a6c524814d1085dcc19996dfbc910065`.

The unchanged generic reader accepts its requested UTC knots at midnight, three
hours and six hours, and the declared fifteen-metre depth. The unchanged study
wrapper reports `HYCOM_REQUESTED_NATIVE_TILE_OR_STRIDE_CHANGED`. This review
exports no current-vector values and runs no advection or model comparison.

| Saved coordinate property | Latitude | Native longitude |
| --- | --- | --- |
| NetCDF variable dtype | float64 | float64 |
| Coordinate count | 251 | 188 |
| Actual first and last labels | 25 to 35° | 280 to 294.96002197265625° |
| Nominal increment | 0.04° | 0.08° |
| Smallest actual adjacent increment | 0.039997100830078125° | 0.0799560546875° |
| Largest actual adjacent increment | 0.04000091552734375° | 0.08001708984375° |
| Largest increment difference from nominal | 0.0000028991699218758° | 0.0000439453125° |
| Labels exactly representable as float32 | Every label | Every label |

The arrays are strictly increasing. Every saved float64 label equals an exact
float32 value promoted to float64. Against the predeclared decimal lattices
`25 + 0.04 × i` and `280 + 0.08 × i`, rounded to float32:

- All **251 latitude labels** match exactly.
- **98 longitude labels** match exactly; **44** are one float32 ULP lower and
  **46** are one ULP higher. One longitude ULP here is
  `0.000030517578125°`.

An ULP is one spacing between neighboring representable floating-point numbers.
These differences exceed the wrapper's `1e-9°` adjacent-spacing tolerance, but
remain at the observed coordinate encoding scale. This explains its rejection;
it does not establish current accuracy or forecast skill.

The actual normalized longitude support ends at **−65.03997802734375°**, starting
at **−80°**. A nominal **−65°/295°** edge must not be invented. Any accepted future
reader must interpolate on the actual saved coordinates and preserve domain
exits and masks.

## Proposed v2 review, before any GDP outcomes

A separately identified v2 amendment is scientifically defensible as a metadata
and coordinate-encoding correction, provided it is reviewed and frozen before
new GDP outcome acquisition. Preserve the entire v1 protocol, raw bodies,
failures, forecast receipt and zero-score report. Bind any v2 protocol to this
diagnosis and disclose the original failure.

The proposal has two narrowly bounded parts:

1. **Metadata history:** allowlist only the two valid UTC capture-time tokens
   attached to the exact `(local files)` line and exact DAS URL inside this
   history field. Preserve the version line, every other byte and every acquired
   raw hash. Reject units, schema, version, URL and other history changes. Removing
   the whole history field would be a broader change than this evidence supports.
2. **Coordinate representation:** explicitly review and declare native counts,
   monotonicity, nominal lattice and float32 encoding bounds. The saved evidence
   supports reviewing exact rounded-float32 latitude labels and a longitude
   allowance no greater than one float32 ULP from the rounded nominal lattice.
   Freeze the chosen rule and hostile synthetic tests before new GDP outcomes.
   Keep exact actual coordinates for sampling; never snap or expand support.

Keep the GDP/WMO identities, context and target windows, three candidate models,
six horizons, full denominators, source product, depth, tile, variables, stride,
current time knots and transport budgets unchanged. Do not fit a coefficient,
replace a drifter, select an easier tile, add a model or tune against outcomes.
Tests should reject changed units/version, a shifted or coarsened grid, unexpected
depth/time knots, nondeclared coordinate encodings and perturbations beyond the
reviewed encoding bound.

This would be a **pre-GDP-outcome amendment**, not an entirely scientific-value-
unseen first design: HYCOM forcing bytes were already acquired and decoded for
compatibility diagnosis. They have not produced a scored comparison or been used
to select model parameters. A later successful transport and score would still
be a retrospective buoy-motion diagnostic, with assimilation, processing,
independence and issue-time limitations. It would not validate loose plastic,
reef protection or the physical tank.
