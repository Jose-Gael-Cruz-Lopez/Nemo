# ReefTrace data: what is evidence, what is a future input

Reviewed 16 October 2026. The working tabletop system needs its **own overhead-camera recordings and measured token drift**. Public ocean fields, drifter observations and trash photographs answer different questions. They are deliberately separated in `config/datasets.yaml` and `apps/ocean/reeftrace_ocean/`.

| Data | Actual job | Use in this build | Cannot establish |
|---|---|---|---|
| Own camera runs, release log, measured drift field | Tank detection, tracking, transport and source evaluation | Primary physical evidence | Ocean/reef performance or ecological benefit |
| NOAA GDP historical drifter trajectories | Observed buoy motion and real-data ingestion | One small, pinned public fixture | Plastic identity, polluter identity, or ocean forecast skill from one day |
| Copernicus SMOC currents | Geographic surface-transport model input | Optional local NetCDF reader; explicit user download | Tank flow, reef channels, actual past trajectory or certain source |
| TrashCan | Underwater debris detection/segmentation | Research catalog only | Surface transport, source labels or webcam domain validity |
| MARIDA | Satellite multispectral debris-feature segmentation | Research catalog only | Small individual litter, RGB webcam validity or attribution |

## 1. The primary dataset: record this experiment

For the red foam token, start with colour/shape segmentation and geometric calibration. An underwater neural detector is unnecessary for this controlled class. The evidence is a reproducible run recorded on the actual camera under the actual lighting and pump setting.

Save the original video/frame timestamps; homography and waterline; tank/pocket/pump geometry; token size/material; water depth; drift-calibration tracks; and settings. Log release source and time as evaluator-only truth. The estimator receives candidate sources and observations, **never the answer**. Example logical run manifest:

```json
{
  "run_id": "session02-heldout-04",
  "split": "test",
  "calibration_id": "session02-flow01",
  "coordinate_space": "tank_xy_centimetres",
  "velocity_units": "cm/s",
  "pump_setting": "manual-mark-1",
  "water_depth_cm": 7.5,
  "token_class": "red-foam-10mm",
  "video_path": "camera.mp4",
  "observations_path": "tracks.csv",
  "evaluator_only_truth_path": "truth.json"
}
```

Use complete held-out runs/sessions; random adjacent-frame splits leak nearly identical images and trajectories. Freeze thresholds and transport settings before the held-out evaluation. Include glare, missed detections, converging candidate plumes, releases outside the candidate set, invalid calibration, moving-to-retained transitions and first-seen-retained cases. Measure coverage and abstentions alongside correctness; report every attempted run. A last-clean frame bounds arrival/retention time, not necessarily release time. A set of 20 runs can be a disclosed demo evaluation; it is not broad scientific validation.

Synthetic uniform/vortex fields are useful for numerical tests with known answers. Label them synthetic. Rescaling an ocean current plot to fit the tank does not make it measured tank flow.

## 2. Verified, no-secret real fixture: NOAA Global Drifter Program

The [NOAA hourly data page](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php) describes quality-controlled, mathematically interpolated hourly buoy positions, east/north velocities, temperatures and uncertainty. It links public ERDDAP, NCEI and cloud access; the product DOI is [10.25921/x46c-3620](https://doi.org/10.25921/x46c-3620). These are sparse Lagrangian observations, rather than a complete gridded velocity field. Buoy response/depth and floating plastic dynamics can differ.

**Freshness:** the [specific AOML ERDDAP endpoint metadata](https://erddap.aoml.noaa.gov/gdp/erddap/info/drifter_hourly_qc/index.html) currently identifies release v2.01 and coverage ending 31 October 2022. Its intended quarterly updates have experienced delays. The endpoint declares **CC BY 4.0**; retain attribution and DOI. A current web-server timestamp does not make this historical dataset real-time.

We successfully retrieved **24 hourly rows for drifter `8707978`, 3 October 1987 UTC**, on 16 October 2026: **1,950 bytes**, SHA-256 `b503de924bbfe82fb18a705917e527faaf26e51688845adb4b57f0cb121c2fca`. This day was selected solely to exercise public access and ingestion, not to claim a representative test. The sample and manifest are committed in `data/public/`.

```bash
python scripts/fetch_public_sample.py --output-dir work/public-noaa-smoke
```

This command fetches only that fixed drifter-day, caps the response at 32 KB, validates the 24 rows and writes a hash/provenance manifest. It requires no account. The CSV includes its original units row: geographic latitude/longitude in degrees, `ve`/`vn` in **m/s**, and `err_ve`/`err_vn` uncertainty in m/s. The original endpoint calls those uncertainty columns 95% confidence intervals. No source labels are fabricated.

```python
from apps.ocean.reeftrace_ocean import load_drifter_csv

records = load_drifter_csv("data/public/noaa-gdp-8707978-19871003.csv")
print(records[0].time_utc, records[0].eastward_m_s)
```

A meaningful later field test would compare independent, held-out drifter trajectories with a contemporaneous transport model, accounting for drogue/object response. The bundled 1987 day is **not paired with SMOC's available modern archive**, so no such skill comparison has been performed.

## 3. Copernicus Marine: the best first future transport input

Use [Global Ocean Physics Analysis and Forecast](https://data.marine.copernicus.eu/product/GLOBAL_ANALYSISFORECAST_PHY_001_024/description), product `GLOBAL_ANALYSISFORECAST_PHY_001_024`, DOI [10.48670/moi-00016](https://doi.org/10.48670/moi-00016). The product is an assimilative numerical model on a roughly **0.083° grid**, often described as ~9 km; east/west physical spacing varies with latitude. The product page lists daily updates. Forecast-valid times beyond today are model predictions, not future observations.

The [July 2026 product manual](https://documentation.marine.copernicus.eu/PUM/CMEMS-GLO-PUM-001-024.pdf) specifies the hourly surface merged-current dataset `cmems_mod_glo_phy_anfc_merged-uv_PT1H-i` (**SMOC**). Read `utotal`, `vtotal` in m/s. The underlying components are Eulerian `uo`, `vo`; Stokes drift `vsdx`, `vsdy`; and tides `utide`, `vtide`. The total already combines those contributions: do not add the same tide/wave terms again. The manual describes daily 10-day forecasts and a rolling archive; inspect the live catalog for actual dataset availability/version before selecting historical dates.

**Limits:** one model cell is vastly larger than this tank and commonly larger than reef passages. Interpolation produces additional numerical points, not additional observed coastal detail. SMOC does not provide debris release histories, local retention/resuspension truth, object windage, reliable beaching rules or actual pollutant identity. A future local application needs appropriate coastal fields and independent field observations before any attribution claim. The [quality document](https://documentation.marine.copernicus.eu/QUID/CMEMS-GLO-QUID-001-024.pdf) should accompany any scientific use.

For long historical experiments, inspect the separate [Global Ocean Physics Reanalysis](https://data.marine.copernicus.eu/product/GLOBAL_MULTIYEAR_PHY_001_030/description), product DOI [10.48670/moi-00021](https://doi.org/10.48670/moi-00021). It is a distinct product, not an automatic interchangeable extension of SMOC: select and document its actual variables, time sampling and forcing limitations.

**Access and rights:** the [official Toolbox](https://help.marine.copernicus.eu/en/articles/7949409-copernicus-marine-toolbox-introduction) offers Python/CLI subsetting and requires a free account for data downloads. No Copernicus credentials were requested or used for this build. The [Copernicus Marine licence](https://marine.copernicus.eu/user-corner/service-commitments-and-licence) permits modification, derivative works and redistribution subject to its terms, including clear source/DOI credits and use-traceability records. It is its own licence; do not relabel it CC BY. Use the [official citation guidance](https://help.marine.copernicus.eu/en/articles/4444611-citing-copernicus-marine-products-and-services) for the final acknowledgement. Dataset IDs identify the extraction; the product DOI provides its persistent citation.

### A bounded, explicit user-run download

Install the optional extra, then authenticate interactively yourself. Never put credentials in a repo, command argument, screenshot or application log. `copernicusmarine login` stores a local credentials file; consult [login documentation](https://toolbox-docs.marine.copernicus.eu/en/stable/usage/login-usage.html) if that is unsuitable.

```bash
python -m pip install -e '.[ocean]'
copernicusmarine login
copernicusmarine describe --dataset-id cmems_mod_glo_phy_anfc_merged-uv_PT1H-i
```

Choose a small area/date relevant to the actual field experiment. The following is a **documented syntax example, not a downloaded or validated field trial**. It selects two variables, a quarter-degree box, seven hourly times and the near-surface level. Run the dry-run first; proceed only if catalog availability and estimated transfer fit your budget (suggested initial budget: ≤10 MB transfer and ≤250,000 selected space-time samples).

```bash
copernicusmarine subset \
  --dataset-id cmems_mod_glo_phy_anfc_merged-uv_PT1H-i \
  --variable utotal --variable vtotal \
  --minimum-longitude -79 --maximum-longitude -78.75 \
  --minimum-latitude 25 --maximum-latitude 25.25 \
  --start-datetime 2026-10-01T00:00:00 --end-datetime 2026-10-01T06:00:00 \
  --minimum-depth 0 --maximum-depth 1 \
  --output-directory work/ocean --output-filename smoc-small.nc --dry-run
```

Only after reviewing the result, repeat the same bounded command with `--dry-run` removed. Save requested bounds, selected dataset version, access time, licence, product DOI and the Toolbox response alongside the file. The [official CLI reference](https://toolbox-docs.marine.copernicus.eu/en/stable/command-line-interface.html) documents these options; [subsetting documentation](https://toolbox-docs.marine.copernicus.eu/en/stable/usage/subset-usage.html) explains coordinate selection. A tiny output can still require larger remote chunks to be transferred. This project never automatically requests a whole ocean.

### Offline ingestion and coordinate boundary

```bash
python -m apps.ocean.reeftrace_ocean work/ocean/smoc-small.nc
```

The optional reader accepts a local rectilinear NetCDF, enforces declared velocity/coordinate/depth units, checks selected size before loading velocity arrays, selects depth explicitly, preserves missing-value masks and emits dimensions, time interval, selected depth, source hash and approximate grid spacing. Default budgets are 50 MB local file / 250,000 selected space-time samples. It does **not** download data, interpolate a coastal forecast, run an ocean attribution experiment, or control the pump.

Ocean arrays stay `(time, latitude, longitude)` with velocities in m/s. Multiplying velocity by 100 converts **m/s to cm/s only**; longitude/latitude remain angles. Geographic advection requires WGS84 geodesy or an appropriate local metric projection, with dateline, poles, interpolation, boundaries and numerical errors handled. Never add m/s directly to degrees or pass an ocean field into tank-centimetre code. The reader's WGS84 grid-size calculation is a local metric approximation for disclosure, not an ocean trajectory solver.

## 4. Debris vision datasets: useful later, not source labels

**TrashCan:** the [University of Minnesota project page](https://irvlab.cs.umn.edu/resources/trashcan) describes 7,212 annotated underwater images from JAMSTEC's J-EDI ROV material, with instance masks and two class configurations. It is a 2020-era research benchmark, not a live feed or a sequence of known releases. Its domain differs from an overhead RGB camera observing floating red foam. The [lab resources index](https://irvlab.cs.umn.edu/resources) links a publisher `Dataset/Weights` record and states academic-research-only availability. The [primary repository record](https://conservancy.umn.edu/handle/11299/214865) returned HTTP 403 during this review; its file/weights licence could not be independently read. **Do not assume permissive commercial rights from a Kaggle/Hugging Face mirror. No weights or imagery are bundled or approved here.**

**MARIDA:** the [authors' Zenodo release](https://zenodo.org/records/5151941), DOI [10.5281/zenodo.5151941](https://doi.org/10.5281/zenodo.5151941), supplies 1,381 256×256 GeoTIFF patches with sparse class masks, confidence masks and supplied train/validation/test splits. Fifteen classes include debris, Sargassum, organic material, foam, waves and water types. Release 1.0.0 was published in 2021; this is a fixed benchmark, not current debris coverage. The [publisher metadata API](https://zenodo.org/api/records/5151941) and [dataset documentation](https://data.source.coop/ntua/marida/documentation.pdf) identify **CC BY 4.0**. The single archive is ~1.16 GB compressed; it was not downloaded.

The [primary paper](https://doi.org/10.1371/journal.pone.0262247) describes 11 Sentinel-2 bands processed to a 10 m output grid, excluding bands 9 and 10. These multi-spectral inputs and sparse annotations are unsuitable for direct RGB webcam training. A patch label cannot establish plastic chemistry, the exact releasing actor or coral health. Use its confounders to design future satellite experiments and respect its geographic/temporal splits. The [authors' code](https://github.com/marine-debris/marine-debris.github.io) provides research baselines with an older software environment; a data licence does not by itself license every model weight or dependency. No external weights are used by ReefTrace.

## 5. What counts as tested

- **Actually verified:** public NOAA access, schema parsing, row count, units, timestamps and content hash; offline ocean-reader numerical fixtures, masks and refusal paths.
- **Not yet verified:** Copernicus authenticated data retrieval; model-vs-drifter transport skill; real webcam/tank outcomes until hardware is connected; plastic source attribution; marine intervention effectiveness.
- **Not claimed:** real-reef validation, ecological benefit, identifying a polluter, or a probability conditional on candidate sites being a probability over all possible real-world sources.

Run `pytest -q tests/unit/test_ocean.py`. The xarray-dependent tests use explicitly synthetic fixtures; the NOAA test uses the actual small public CSV. Neither substitutes for the physical held-out experiment.
