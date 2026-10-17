# Current-driven ocean prediction

Tideward now has two different forecasting questions. The frozen NOAA buoy study asks whether a model can extrapolate historical buoy positions. The new **Data Lab → Load current-driven prediction** asks how a hypothetical floating particle moves through a real, changing ocean-current forecast. The new preview does not alter the original scores, source rankings, tank flow, protected zone or prevention comparisons.

## Why the earlier forecast is straight

Last drift repeats the final observed velocity vector. Mean drift repeats an average vector. The constant-velocity Kalman model also forecasts a straight mean after its final measurement update, even though its uncertainty grows. Ridge AR(1) evolves velocity, but has no external ocean-current input. These are useful baselines; a visually curved path is not automatically more accurate.

Speed can vary along a straight path. Curvature requires a change in direction across location or time. A pump's volumetric rating in gallons/hour does not determine either the local water velocity in m/s or its spatial pattern.

## Real forcing acquired for this preview

- Product: [PacIOOS ROMS Main Hawaiian Islands](https://www.pacioos.hawaii.edu/metadata/roms_hiig.html), `roms_hiig`, eastward `u` and northward `v` in `meter second-1`.
- Public [ERDDAP metadata/API](https://pae-paha.pacioos.hawaii.edu/erddap/info/roms_hiig/index.html); no API key or paid account is required for this subset.
- Nominal source spacing: roughly **4 km**, three-hourly; selected depth **0.25 m**. The source is a forecast model, not a direct water measurement. See [the official regional modeling description](https://www.pacioos.hawaii.edu/currents/model-oahu/) for the nested Oʻahu model and its wider main-island boundary model.
- Captured on **17 October 2026 before the first valid time**. Exact retrieval UTC, HTTP metadata, requested bounds and checksums are in the pinned manifest.
- Three valid times: **17 October 18:00 / 21:00 UTC and 18 October 00:00 UTC**. The complete field is three times × 29 latitudes × 37 longitudes. Missing values remain masked.
- A deliberately hypothetical release starts at **21°N, 158°W** south of Oʻahu. No observation or waste identity is attached to it.

The API serves an FMRC best-time-series aggregation. It does not expose a separately verified single model issue time in the acquired subset. Retrieval before valid time is documented; strict operational availability/assimilation lineage is not established. After the valid window expires, Tideward labels the view an **archived forecast snapshot**. It is never silently called today's water conditions.

Raw CSV, provider metadata and manifest live in `data/current_fields/pacioos-current-forecast-v1`. They are separate from `data/public` because the original GDP study froze an inventory of that directory before acquisition. Adding this unrelated current product must not rewrite the frozen GDP exclusions or study history. The source receipt and raw bytes are hash checked before every local replay.

## What the solver does

For east/north current components `u` and `v`, the passive tracer satisfies:

```text
d(longitude)/dt = u(longitude, latitude, t) / WGS84_metres_per_longitude_degree(latitude)
d(latitude)/dt  = v(longitude, latitude, t) / WGS84_metres_per_latitude_degree(latitude)
```

`CurrentSampler` interpolates bilinearly across space and linearly between supplied times. `advect_current` integrates those changing derivatives with fourth-order Runge–Kutta, using a bounded step and horizon. It evaluates velocity at the particle's new position and time, rather than drawing a curve between a guessed endpoint and the release.

The comparison path uses the **same solver and geographic domain** with the initial current held fixed. Both are predictions. Their endpoint separation is model disagreement, **not prediction error**, an accuracy improvement or prevented pollution. ADE/FDE remain null because no independent observed object track is available.

Missing interpolation corners, invalid axes, masks, unsupported times, excessive speeds or a domain exit prevent an unsupported continuation. Status is `COMPLETED`, `PARTIAL` or `UNSUPPORTED`; only accepted points are drawn. There is no shore snapping, missing-value-to-zero conversion, field extrapolation, artificial wiggle or random curvature. The solver currently supports local nonpolar rectilinear geographic grids, not arbitrary curvilinear/dateline/polar domains.

The UI uses a separate approximate local projection only to draw the paths. Both axes use the same scale. The plot domain and arrow-speed scale remain fixed while checkboxes and valid-time controls change. The nine display arrows at each time are **interpolated samples**, not nine independent current measurements or finer physical resolution.

## API and Chalk contracts

`GET /api/v1/research/current-forecast` is public and offline: checked local bytes → current field → two predictions → finite JSON. It neither fetches fresh data nor writes an experiment.

`POST /api/v1/research/current-forecast/investigate` requires operator access and exactly:

```json
{
  "question": "Explain the current-driven prediction and its limits.",
  "snapshot_sha256": "hash returned by GET",
  "method_sha256": "hash returned by GET"
}
```

The request is bound to the clicked field/method. A stale request is rejected before provider access. Chalk reads one compact server-bound evidence summary, with `current-snapshot:` and `current-method:` citations, and can return only `REPORT` or `STOP`. A changed report during a slow response is rejected. Configuration, timeout, HTTP or contract failure leaves deterministic predictions available. Chalk cannot acquire currents, edit tank cases/trials, activate hardware or message Photon through this research tool.

## What remains before predicting real waste

1. Acquire a region-appropriate forecast with a pinned issue/run time and preserve every subsequent update as a new snapshot. The included script reproduces the fixed acquisition; it is not an automatic rolling forecast service.
2. Match independent object/drifter observations to the same location, depth and valid times. Evaluate complete common horizons and retain failed/missing outcomes before claiming better skill than persistence.
3. Evaluate debris wind response, buoyancy, Stokes drift, diffusion, beaching, entanglement and retention. Do not add tides/waves a second time if a future total-current product already includes them.
4. Use measured tank drift for the real experiment. Ocean grid cells are thousands of times larger than the bin. Timestamped, separately recorded calibration and validation runs are needed before a time-varying tank model is admitted; an ocean API cannot substitute for those measurements.

Analytic tests cover constant current, time-turning current, spatial shear, RK4 convergence, axes, masks and bounds. These verify implementation against known answers. The real snapshot verifies data transport, provenance and execution; neither establishes physical waste-prediction accuracy.

PacIOOS data are distributed free of charge without warranty under the provider's stated terms. Preserve its acknowledgment and follow its scientific-use/publication guidance. No provider key, xAI call, paid billing change or Photon message is needed for the numerical preview.
