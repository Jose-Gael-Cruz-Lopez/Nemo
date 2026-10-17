# DRAFT: matched-current drifter feasibility study

Design checkpoint: **17 October 2026**. Status: **DRAFT — local reader, fixed-model
evaluator and bounded acquisition/replay infrastructure implemented and tested with
synthetic or mocked inputs; final source review and a formal, hashed protocol are
still required before scientific acquisition**.

This is a proposed six-hour, two-group feasibility comparison. It is not a frozen
experiment, an acquired trajectory/current dataset, a completed score, or a claim
of operational forecast skill. Only bounded public metadata were read. No new
trajectory positions, current-vector values, model fits, scores or physical trials
were acquired or run for this design.

The new `hycom.py`, `matched_current.py`, `matched_current_protocol.py` and the
three matched-current scripts are infrastructure, not a completed study. The
trusted `matched_current_identity.py` and the `data/public/matched-current-v1`
protocol/acquisition directory do not yet exist. Default evaluation is replay-only
and refuses an unscored study. No endpoint or Data Lab panel presents new study
scores. The first scientific request and first scoring operation remain separate,
explicit gates after a reviewed source freeze; existing NOAA results are unchanged.

## 1. Question and the improvement being tested

Does a time-varying, spatially varying current field at an approximately matched
object depth describe six hours of later GDP buoy motion better than stationary
and last-observed-drift baselines, for two predeclared historical groups?

This tests the **physical forcing against reserved later position estimates**,
subject to the independence/processing caveats below. It is a stronger empirical
question than whether a smaller RK4 step produces a numerically stable line.
Numerical precision remains a separate diagnostic. A better integrator can still
integrate the wrong current field or the wrong object-response model.

The candidate forcing is **HYCOM GOFS 3.1, GLBy0.08, experiment 93.0, UV3Z, 2022,
15 m**. Its explicit 15 m level is a closer match to the standard drogue-centered
GDP object than OSCAR's daily upper-30-m mean. This is a rationale for testing,
not a claim that HYCOM will outperform either baseline. A drogued buoy remains a
different object from loose surface plastic or a tank token.

## 2. What availability was actually verified

| Source | Verified metadata/access | Remaining boundary |
| --- | --- | --- |
| [NOAA hourly GDP dataset](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php) | Public ERDDAP schema/attributes and a fixed-origin identity/drogue query succeeded without credentials. The inspected endpoint identifies itself as **v2.01**, with actual time coverage ending **2022-10-31T00:00:00Z**. | The general webpage also describes release **v2.01.1**, with a different final-hour description. Do not silently call this endpoint v2.01.1. Pin the actual payload, metadata, DOI and retrieval date. No 31-position study track has been retrieved. |
| [HYCOM 2022 UV3Z catalogue](https://tds.hycom.org/thredds/catalogs/GLBy0.08/expt_93.0_uv3z.html?dataset=GLBy0.08-expt_93.0-uv3z-2022) | The catalogue lists freely available OPeNDAP and NCSS access. **NCSS dataset metadata returned successfully without credentials**. | OPeNDAP DDS/DAS attempts timed out; the first proposed data path is the verified NCSS service. A successful metadata response is not proof that a chosen current subset has valid wet cells or successful value transport. |
| [NOAA drifter construction/behavior](https://www.aoml.noaa.gov/phod/gdp/faq.php) | The standard drogue is centered around 15 m; losing it changes wind/wave response. | Retrospective drogue metadata are not a direct observation of the instantaneous drag depth or an operationally available status feed. |
| [HYCOM missing/substituted-days notice](https://www.hycom.org/faqs/477-did-you-know-there-are-missing-days-in-the-gofs-31-global-analysis) | Some dates are missing or substituted, and the provider disclaims guaranteed availability. The proposed May 31–June 1 window is not among the listed 2022 substitution dates. | The list is not proof of complete support. Verify the actual requested times, cell masks and run lineage; never fill missing currents with zero. |

Official supporting product specifications:
[HYCOM GOFS 3.1 analysis](https://www.hycom.org/dataserver/gofs-3pt1/analysis).
OSCAR is retained as a potential later comparator, not the selected first source:
[NASA OSCAR final v2](https://podaac.jpl.nasa.gov/dataset/OSCAR_L4_OC_FINAL_V2.0).

## 3. Proposed two identities and selection provenance

The metadata-only candidate query used a fixed origin **2022-06-01T00:00:00Z** and
the closed region **25–35°N, 80–65°W**. It requested identifiers, buoy class,
drogue-loss metadata and nominal drogue depth, **not position columns or later
motion**. Eleven identity rows were returned. Nine had loss dates preceding the
origin. Two had metadata compatible with an attached 15 m drogue at that origin:

| Proposed complete GDP group | WMO | Reported class/depth | Queried drogue-loss field | Interpretation for this draft |
| --- | --- | --- | --- | --- |
| `300234066836710` | `6202613` | SVPB / `15 m` | `2023-03-02T00:00:00Z` | Loss is after the proposed six-hour outcome window. |
| `300534061292930` | `4102636` | SVPB / `15 m` | Empty/fill | This endpoint documents fill as still attached; zero instead means uncertain from the beginning. Do not conflate those states. |

The two mappings occur once each in the project's saved identity registry; each
WMO maps back to one GDP ID there. Neither GDP ID nor its mapped WMO is in the
original 223-ID/known-alias exclusion set. Neither is among the six completed
fresh-study GDP groups. Identity-registry appearances and an earlier metadata-only
2021 candidate appearance for the first ID are disclosed; these are **not** claims
that the IDs have never been seen in metadata.

These checks use the existing saved registry/exclusions, not a newly complete
physical-identity audit. Preserve the previously disclosed unresolved historical
aliases. Set `physical_alias_resolution_verified=false` and
`statistical_independence=false` unless a later documented review establishes
otherwise. Future trajectories have not been inspected to establish row count,
finite observations, six-hour survival, spatial coverage or path difficulty.

The proposed two identities stay in the full planned denominator. Do not replace
one because a download, mask, prefix or future observation fails. The eleven-row
origin metadata frame is a selection-availability record, not eleven evaluated
trajectories. Formal review must accept or amend this rule before acquisition.

## 4. Proposed observation and forecast contract

| Item | Proposed fixed value |
| --- | --- |
| Context | **25 hourly positions**, 2022-05-31T00:00:00Z through 2022-06-01T00:00:00Z, inclusive. |
| Forecast origin | 2022-06-01T00:00:00Z. |
| Reserved outcomes | **Next six hourly positions**, 2022-06-01T01:00:00Z through 2022-06-01T06:00:00Z. |
| Forecast horizon | **21,600 seconds**, matching the existing `MAX_HORIZON_S`; no 24-hour forecast extension. |
| Context use | The 25 positions are context/QC, not a fitting dataset. Stationary and current-only initialize from the origin position alone. Last drift uses only its own final two context positions, at May 31T23Z and June 1T00Z, with their actual elapsed time. No common learned model or cross-group fitting. |
| Forcing support | Current-only receives exactly the declared tile at **June 1T00Z, 03Z and 06Z**, at 15 m. It receives no earlier current fields or later GDP positions. The model does not ingest the other 24 context positions. |
| Comparison outputs | Same six UTC horizons and same observed targets for every candidate; great-circle position error in metres, six-hour endpoint error, status and coverage. |
| Planned accounting | Two complete GDP groups × three candidates × six horizons = **36 planned model/horizon attempts**, using only **12 distinct later position estimates**. These are not 36 independent observations. |

Fixed candidates, subject to exact implementation/version review before freezing:

1. **Stationary:** remain at the origin position, without reading earlier context.
2. **Last observed drift:** extrapolate the final context displacement with its
   actual elapsed time; freeze the coordinate conversion and propagation method.
3. **Current-only:** start at that origin position alone and integrate the
   matched HYCOM 15 m field with the existing knot-aligned bounded advection
   implementation. Proposed solver maximum step 300 s, hourly output, and forced
   alignment with current-time knots; freeze the exact code revision and options.
   Only the origin, 03Z and 06Z forcing slices enter this run. Earlier current
   fields are unnecessary for these fixed candidates and are omitted from the
   proposed scientific-value request.

Do not train or introduce a learned residual, windage, Stokes coefficient, diffusion
coefficient, kernel or new noise tuning before formal design review. Do not tune
against these groups or the already completed NOAA studies. Any later candidate
needs a separately declared development design and untouched comparison groups.

## 5. Exact source paths and data-reader requirements

GDP base:
`https://erddap.aoml.noaa.gov/gdp/erddap/tabledap/drifter_hourly_qc`

Availability query, shown unescaped for readability:

```text
drifter_hourly_qc.csv?ID,WMO,typebuoy,drogue_lost_date,DrogueCenterDepth&time=2022-06-01T00:00:00Z&latitude>=25&latitude<=35&longitude>=-80&longitude<=-65&distinct()
```

This is the identity/drogue query already made, not a future acquisition command.
Any later 31-position query must constrain one exact selected ID and the declared
UTC window. Use the recorded positions as the target; GDP `ve`/`vn` are derived
from the same processed track and are not independent forcing truth.

HYCOM NCSS base:
`https://ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z/2022`

Verified metadata path: the base plus `/dataset.xml`.

The metadata report:

- Grid axes: 4,251 latitude values, −80 to 90°, nominal increment 0.04°; 4,500
  longitude values, 0 to 359.92°, nominal increment 0.08°.
- Time: **2,920** valid times, three-hour increment; units `hours since 2000-01-01
  00:00:00`, Gregorian calendar. The named 2022 aggregate spans **2022-01-01T12Z
  through 2023-01-01T09Z**. Do not infer bounds from the year in the URL alone.
- Forty fixed depths, positive downward in metres, including **15.0**.
- `water_u` and `water_v` use dimensions `time depth lat lon`, stored as short
  integers, units m/s, scale factor **0.001**, offset **0**, missing/fill **−30000**.

Proposed first scientific subset: only those two variables, the 15 m level, the
predeclared **25–35°N / 80–65°W** tile, native spatial resolution, and exactly
**2022-06-01T00Z, 03Z and 06Z**. This tile is approximately 0.6 MB of packed two-component data
for three times before format overhead; actual service dimensions/size must be
recorded rather than assumed. Freeze a bounded request and byte/time budget before
making it. Use one connection; checksum the exact returned bytes.

### Longitude, support and CF decoding contract

The reader's exact normalization is:

```python
normalized_lon = ((native_lon + 180.0) % 360.0) - 180.0
```

Pinned synthetic expectations: **280 → −80**, **281 → −79**, and
**359.92 → approximately −0.08** (absolute floating-point tolerance `1e-10`
degrees). This tolerance checks a synthetic representation conversion; it is not
a measured geographic error bound or a time-snapping rule.

For this western Atlantic tile the native source-longitude interval is 280–295°;
the normalized interval is −80 to −65°. Keep the velocity arrays aligned with
their coordinate indices. Reject non-finite, duplicate or non-monotonic axes,
an unexpected discontinuity/dateline-crossing tile, and any sample outside the
supported interval. Do not silently wrap an outside point, sort/reorder a changed
axis, shift the whole field, expand support, interpolate across a seam, or silently
substitute another product. A future dateline-capable reader would need its own
explicitly reviewed contract; it is outside this draft.

For both velocity components, compare the acquired variable's units, raw dtype,
fill/missing sentinels, scale, offset, dimensions and selected depth against the
pinned metadata. Expected values are raw short, m/s, `_FillValue` and
`missing_value` **−30000**, scale **0.001**, offset **0**, dimensions
`time depth lat lon`, and depth **15.0 m** positive downward. Reject an unexpected
encoding, unit or depth change as a recorded failure for the planned groups.
Do not adopt a new scale, unit conversion, fill value or nearest depth implicitly.

Use one explicit raw-decoding path: reject/mask the **raw integer −30000 before
scaling**, then multiply finite supported raw integers by **0.001 exactly once**.
If a library performs automatic CF mask/scale, disable it for this path or prove
the equivalent single-decoding behavior before freeze; never multiply an already
decoded value again. The raw sentinel must remain missing, not become −30 m/s or
zero. A raw `500` must become **0.5 m/s**, not 0.0005 m/s.

Preserve native UTC valid times and masks, reject unsupported wet-cell stencils
and retain domain/time exits. A missing or masked required knot must produce the
actual integrator status and completed prefix; no invented finite continuation
is allowed. Do not expand the tile or change the depth after observing an
unfavorable outcome. A preliminary transport probe, if approved, must have its own
predeclared tiny scope and must not become unreported cohort/model selection.

### Required synthetic reader/integration fixtures before freeze

These are **proposed tests using invented arrays**, not acquired HYCOM values,
executed test receipts or observations of either GDP group:

| Fixture | Exact input | Required assertion |
| --- | --- | --- |
| Conversion and scale-once | Native longitude `[280, 281]`, latitude `[-1, 1]`, one depth `15`, raw short `u=500`, `v=0`, scale `0.001`, fill `−30000`. | Longitude becomes `[-80, -79]`; the 359.92 edge also passes the separate conversion assertion; supported velocity is 0.5 m/s east. Raw sentinels are masked before scaling. Unexpected metadata/support changes fail explicitly. |
| Immediate unsupported | Times `[0, 3, 6]` h; start at **3 h**, longitude **−79.9°**, latitude **0°**; request 6 h; mask the whole 6 h velocity slice. | First positive-time interpolation lacks support: **UNSUPPORTED**, completed elapsed **0**. It is not a PARTIAL result merely because the initial point exists. |
| True partial prefix | Times `[0, 3, 6, 9]` h; same start at **3 h** and same location/constant velocity; request 6 h; mask only the whole 9 h velocity slice. | The 3→6 h interval completes, then the next interval fails with masked-current support: **PARTIAL**, completed elapsed **3 h**, east displacement **5,400 m** in the numerical frame within a declared floating-point test tolerance. Do not claim a completed six-hour path. |
| Accounting | Exercise the two synthetic group slots × three candidates × six future horizons, with the missing-current cases above. | Retain **all 36 planned cells** and all group/status records. Mark unsupported later horizons explicitly; do not turn an available prefix into a full score or drop missing cells from the denominator. |
| Context isolation | Change the first 23 synthetic context positions while preserving the final two, then separately change the penultimate position while preserving origin. | Last drift reads only the final two; stationary/current-only initialize only at origin. No fitted model, future GDP positions or context-era current slices enter current-only. |

The original review's longitudes `[0, 0.08]` did not exercise the intended western
Atlantic shift, and its masked-knot example incorrectly expected PARTIAL before
any positive interval completed. Those suggestions were rejected and corrected.
The corrected four-time fixture is required for a genuine partial-prefix case.
These reader tests must be implemented and verified before formal protocol freeze;
static review alone does not establish them as passing.

## 6. Issue-time, processing and independence limits

The inspected HYCOM metadata expose **Valid Time**; no verified run/issue timestamp
or historical publication-as-of record has been established. The catalogue calls
this an analysis/hindcast aggregate. Its future-valid current fields may contain
information unavailable at the drifter forecast origin. Consequently this first
comparison is a **retrospective forcing-supported motion diagnostic**, not a claim
of prospective six-hour forecasting skill. An operational study requires archived
run-specific forecasts, an issue cutoff and realistic delivery latency.

HYCOM includes data assimilation. Before calling the evaluated observations
independent, audit the product's actual assimilation inputs and whether the tested
GDP observations, derived products or closely related data entered the forcing.
Whole-ID holdout alone does not settle this. No assimilation-independence proof was
obtained by the catalogue inspection.

GDP hourly positions are quality-controlled processed/interpolated estimates,
not raw instantaneous ground truth. Endpoint metadata include retrospective drogue
information and processing/version inconsistencies; that also prevents an as-of
operational claim. The two nearby groups and six dependent future hours support
descriptive feasibility results only. Do not infer calibrated confidence,
statistical significance, source attribution, plastic skill or reef protection.

## 7. Preserve failures and report only supported comparisons

Retain all two groups and every planned candidate/horizon, including transport
failure, malformed/duplicate/missing rows, unresolved identity, missing current
cells, time limits and domain exits. Distinguish these reasons explicitly.
Never substitute zero currents, interpolate across unsupported masks or discard
a failed group to improve an average.

Any common-supported-prefix descriptive comparison must name its exact available
horizons and flag incompleteness; it must not silently stand in for the full
six-hour result. Report the planned two-group denominator, achieved per-candidate
coverage and all failures next to any errors. Do not label synthetic paths or a
fine numerical reference as observed outcomes.

## 8. Metadata receipts and the review gate

The following exact public metadata bodies are preserved under
`docs/research-evidence/matched-current-metadata/`, with a safe, derived
`receipt.json`. They were copied byte-for-byte from the original ignored local
receipts, without another external request. The derived receipt includes only
relative filenames, public URLs, retrieval times, curl outcomes, sizes and hashes;
it excludes machine home paths, credentials and private user data. They are
**metadata/design evidence, not acquired scientific-value fixtures or a frozen
study protocol**.

| Local receipt body | Retrieval start (UTC, 2026-10-17) | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| [gdp-hourly.dds](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/research-evidence/matched-current-metadata/gdp-hourly.dds) | 19:34:51.733619 | 1,312 | `758a543dd887ff35ed052ef1ac9ba57380c78fed570b004e4b5ae031b6a3f0ad` |
| [gdp-hourly.das](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/research-evidence/matched-current-metadata/gdp-hourly.das) | 19:34:51.897741 | 18,686 | `66cdd12aff149d25cfa03fbcbe2046fb5657e7aa31795f0bfa0c41c3527efd39` |
| [gdp-origin-identity-drogue.csv](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/research-evidence/matched-current-metadata/gdp-origin-identity-drogue.csv) | 19:34:52.198899 | 640 | `fe20f70d249e8e099ba63e97341ed52c3c1dff34f5055b6946a4438679b6a339` |
| [hycom-2022-ncss-dataset.xml](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/research-evidence/matched-current-metadata/hycom-2022-ncss-dataset.xml) | 19:34:54.925023 | 159,404 | `741d5fcc5cd784415c9b8582394a05f4102f81f0d883821e8267a61ea698164d` |

The [derived receipt](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/research-evidence/matched-current-metadata/receipt.json)
is 2,640 bytes, SHA-256
`56328dff9fe82945fe0756967e1334a55471a5735f9e846bae721a186e88c993`.
Repository links identify the intended durable source paths; no claim of a push
or Trov publication is created by this draft.

The `.dds`/`.das` URLs append those extensions to the GDP base; the candidate URL
is the availability query above with encoded comparison characters. All four
bounded curl requests completed with exit 0 using ordinary certificate
verification and no supplied authentication. These hashes refer to the specific
responses, not to every future response of those changing services.

Existing identity-check sources:

- `data/public/noaa-fresh-drifter-v2/raw/identity-aliases.csv`: 318,597 bytes,
  SHA-256 `a18a8568a93a4da3285ec6e2d2fb927a5d9f3f420deaf961f99b0421011fab82`.
- `data/public/noaa-fresh-drifter-v2/exclusions.json`: 10,625 bytes,
  SHA-256 `40601110d4ac510766c561f1534fc98d1e5221884cbd5c2e76ff73415d52d82e`.

## 9. Design review decisions and the remaining gate

Grok supplied an initial static design review and a correction after the local
review challenged its longitude fixture, immediate-unsupported/PARTIAL distinction
and leakage wording. Both initial advice and correction are retained as historical
review evidence in the project's Grok archive; this draft records the accepted
contracts rather than treating every model suggestion as correct or executed.

Accepted: origin-only current initialization, final-two-position last drift,
25-position QC context without fitting, exactly three current knots, explicit
longitude/CF/depth/metadata validation, and full planned accounting on failures.
Rejected: the blanket claim that using any past/context-era field would itself
necessarily constitute future leakage. Properly declared development or past-only
calibration can be scientifically legitimate. This feasibility draft deliberately
uses no such fitting or earlier forcing because the fixed candidate is simpler;
the actual unresolved operational issue is future-valid analysis/assimilation
information without verified origin-time availability.

**Next step:** implement and verify the synthetic reader contracts, review the
exact implementation and protocol locally, resolve or retain every limitation
above, then freeze a separate protocol and exact code/data hashes before requesting
scientific values. The review has not frozen the study. This draft authorizes no
automated acquisition, scoring, model promotion, tank operation or deployment.
Keep the existing completed NOAA results unchanged.

Related references: [next current-data study](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/next-current-data-study.md),
[fresh NOAA study](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/fresh-noaa-study.md),
and [RK4 numerical quality](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/rk4-numerical-quality.md).
