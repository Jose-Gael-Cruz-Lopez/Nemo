# PacIOOS current-forced preview, version 1

This is real public **ROMS ocean-model output**, not a tracked waste object or
an accuracy benchmark. Tideward captured the bytes at **2026-10-17 17:02:30 UTC**,
before the three forecast valid times: **October 17 at 18:00 and 21:00, and
October 18 at 00:00 UTC**. The public FMRC *Best Dataset* aggregation does not
identify a separately verified, single issued model run. Its issue time remains
unknown; the receipt only establishes when these bytes were downloaded.

- Provider: PacIOOS / University of Hawaiʻi; NOAA IOOS support.
- Dataset: `roms_hiig`, Main Hawaiian Islands, nominal 4 km resolution.
- Variables: eastward `u` and northward `v`, metres per second.
- Surface depth: 0.25 m; three-hour model interval.
- Subset: 3 times × 29 latitude knots × 37 longitude knots; 2,997 finite paired
  samples and 222 masked samples. Missing data stay masked.
- Raw CSV SHA-256: `bb9dae3ae753b5cb1cf01304b7bbe14861c8e1b1ac0514c5947838eb711feeb5`.
- Reviewed manifest SHA-256: `c790652416e87de208e3b84dec808998a5a3919909808f47d854be6c74298790`.

The exact percent-encoded ERDDAP request, headers, retrieval time, source units,
licence and hashes are in `manifest.json`; unmodified provider metadata is in
`erddap-info.json`. [Official product metadata](https://www.pacioos.hawaii.edu/metadata/roms_hiig.html).
The provider permits free use and redistribution, with the accuracy/legal-use
limitations recorded verbatim in the manifest.

The preview uses a **hypothetical offshore release** at 21°N, 158°W. A bounded
RK4 integrator samples space- and time-varying currents using bilinear spatial
and linear temporal interpolation with local WGS84 metre/degree derivatives.
It compares this path with the same integration under the frozen initial
east/north current. The roughly 792 m difference after six hours is **a
difference between predictions, not measured error or evidence of improved
accuracy**. Display arrows are interpolated samples of this coarse model, not
new, finer-resolution observations. No windage, Stokes drift, diffusion,
retention, beaching or object-specific response is inferred.

API reads run offline against this immutable snapshot. They do not download
new data. After its valid window ends the UI labels it an archived forecast
snapshot. Acquisition is explicit with
`python scripts/acquire_current_forecast.py`; existing snapshots are never
overwritten. A new acquisition requires a new reviewed receipt and version.

This data lives outside `data/public` to preserve the already frozen GDP
drifter-study fixture inventory and exclusions. Ocean-forcing model data never
change those protocols, their scores or the centimetre-scale tank calibration.
