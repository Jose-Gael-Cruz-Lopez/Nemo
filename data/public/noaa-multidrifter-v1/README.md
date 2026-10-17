# Frozen NOAA acquired-cohort study

This is a small retrospective motion study, not ocean-source attribution or tank
validation. Six metadata slots were planned across three ocean/time blocks.
The unchanged queries selected four previously unscored drifter IDs: `12730`,
`12731`, `300234063243480`, `300234063472530`. The Indian2010 metadata request
timed out; its two slots remain unfilled. No replacement query, replacement ID
or outcome-based selection occurred. Entire drifter `8707978` remains
development-only and is excluded from this evaluation.

The four acquired groups each provide 18 observed prefix positions and six
subsequent hourly targets. The same four fixed algorithms adapt on each allowed
prefix: stationary position, last displacement, mean drift, and ridge AR(1).
Fitting on an allowed observation prefix is distinct from tuning the global
protocol or inspecting future outcomes to choose settings.

## Freeze and replay chain

1. `protocol.json` and its detached SHA-256 were saved at
   `2026-10-17T05:40:21.798819Z`, before metadata acquisition and any forecast
   scores. They specify model settings, selection, origin, metrics and gates.
2. `selection.json` and its detached SHA-256 were saved at
   `2026-10-17T05:49:57.346894Z`, before any selected trajectory request or score.
   The selected IDs can be recomputed from the stored raw metadata snapshots.
3. `manifest.json` records original response bytes, exact URLs, retrieval times,
   sizes, hashes, licensing and whole-drifter group assignments. Its digest is
   stored outside those manifest bytes in `manifest.sha256`.
4. `implementation-receipt.json` binds the evaluator source to the frozen input
   hashes at `2026-10-17T05:55:21.490237Z`, before the first evaluation. The
   original receipt and evaluator source remain unchanged after scoring.
5. `replay-audit.json` is explicitly **post-evaluation**. It records the CSV
   parser SHA and Python/NumPy versions observed later. These observations are
   not retrospectively described as preregistered. Not all software/environment
   dependencies were fully pinned before outcomes. The receipts are local
   consistency records, not independently notarized signatures.

`raw/` contains the original official dataset metadata, successful selection
snapshots and four trajectory CSVs. There is no fabricated CSV for the timed-out
metadata request. No credentials or application state are required to replay.

```sh
.venv/bin/python scripts/evaluate_multidrifter_study.py --output work/multidrifter-replay.json
```

## Denominators and scope

The UI must lead with **4 acquired groups out of 6 target slots**: 96 declared
model/group/horizon outcomes versus the original target of 144. All 96 acquired
outcomes were scored in the first replay. Study status remains
`PARTIAL_COVERAGE`. Equal-drifter macro errors describe the acquired four-group
cohort, not the full planned six. Errors are first averaged within each
trajectory; six hourly targets are not six independent replicates.

Every declared group/model/horizon appears exactly once. Forecast/domain failures
keep their row, null error and reason. Any missing acquired outcome withholds
common-cohort macro errors and paired summaries. Individual losses remain in the
report. There is no significance test, calibrated probability, model selection,
automatic promotion or independence claim.

The inherited 50 km spherical-map cap is a computational approximation domain,
not an environmental quality threshold. Prefix failures remain attempted groups;
future truth is not filtered by distance or forecast error. The 24-hour window
simply supplies the fixed 18/6 experiment and is not an empirically established
ocean-memory timescale.

## Source and known limits

NOAA documents the [hourly QC/interpolated product](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php)
and its [official ERDDAP schema and CC BY 4.0 license](https://erddap.aoml.noaa.gov/gdp/erddap/info/drifter_hourly_qc/index.html).
Citation: Elipot et al. (2022), [DOI 10.25921/x46c-3620](https://doi.org/10.25921/x46c-3620).
Deployment date, experiment and location-type fields are descriptors, not proof
of independent ocean realizations. Nearby deployments within blocks may remain
dependent. Different IDs and sampling decades do not establish independence.

Upstream hourly interpolation may use later raw fixes. This is retrospective
product evaluation, not raw operational forecasting or floating-plastic behavior.
The shared ingestion parser requires finite velocity/uncertainty columns even
though the predictors do not use them. Missing ancillary fields would reject a
payload and retain all failed attempts; they would not become successes or
silently disappear. The four pinned payloads passed that gate. A future protocol
should explicitly distinguish position-only validity from complete-row validity
and specify per-horizon missing-truth handling before new acquisition.

Grok supplied static protocol/code-design assistance. Local implementation and
executed tests establish the reported software behavior; Grok did not execute
this study. The original public sample, 18/6 benchmark and training-only ablation
remain unchanged historical evidence.
