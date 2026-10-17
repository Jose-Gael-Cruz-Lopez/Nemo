# Matched-current v1: an honest blocked study and its product integration

Checkpoint: **17 October 2026**. The v1 design was formally frozen, one bounded
acquisition was attempted, all fixed forecast slots were saved, an explicit first
score was preserved and offline replay was checked. The scientific result is
**0 of 36 model-hour cells scored**. There is no supported model ranking or motion
path in this attempt. This is a compatibility/acquisition failure, not evidence
that a current-driven model performs poorly.

The artifact reader, API, Data Lab card and separate read-only Chalk workflow are
implemented. The [complete local software verification](complete-software-verification-20261017.md)
passed **1,641 Python tests, 223 frontend tests and 153 isolated real-HTTP checks**,
with zero failures and six expected external/physical HTTP blockers. A
**105-test** fresh-process reader/API/replay check is a subset, not an additional
independent scientific sample. Browser checks and separate live Chalk REPORT
investigations completed, including the matched-current evidence explanation.
Ruff, ESLint, route generation, TypeScript, build and dependency checks passed.
Final integration commit and exact-new-head hosted CI remain separate release
checks; the previous successful `06a5cfd7` CI belongs to the earlier 3D build.

## The question and the fixed plan

The study asks whether matched-depth model currents describe the later motion of
two historical NOAA Global Drifter Program buoy groups more closely than two
simple motion baselines. It does not test observed plastic, a polluter's identity,
reef benefit or the physical tank.

| Item | Frozen v1 choice |
| --- | --- |
| GDP groups | `300234066836710` / WMO `6202613`; `300534061292930` / WMO `4102636` |
| Context | 25 hourly positions from 31 May 2022 00:00 UTC through 1 June 00:00 UTC; descriptive QC, not a fitted training dataset |
| Origin | 1 June 2022 00:00 UTC |
| Targets | Six later hourly positions, 01:00–06:00 UTC |
| Candidates | Stationary; last observed drift using the final two context fixes; current-only using the origin position |
| Current source | HYCOM GOFS 3.1, GLBy0.08/expt93.0 UV3Z 2022, `water_u`/`water_v` at exactly 15 m |
| Forcing times | 00:00, 03:00 and 06:00 UTC |
| Accounting | Two groups × three candidates × six horizons = **36 planned cells**, reusing only **12 distinct later processed position estimates** |
| Primary comparison | Equal-ID macro ADE/FDE, only if **all 36 cells score** |
| Scientific boundary | Retrospective future-valid analysis; no verified historical issue-time cutoff, assimilation independence, physical alias completeness or statistical independence |

No learned residual, windage coefficient or globally trained model was added.
These numerical choices were frozen before the attempt and were not changed to
rescue the outcome. The original design/review documents remain historical records.

## What actually happened

The immutable attempt made **four requests**, retained **751,334 response bytes**,
and blocked both planned trajectory requests. It acquired no GDP trajectory body.
The forecast receipt preserves all six candidate tracks as explicit unavailable
slots; the score keeps every planned cell, null error and reason. Primary results
and primary paired comparisons remain null.

Two guards stopped useful comparison:

1. **NOAA metadata:** `PINNED_METADATA_CHANGED`. The raw DAS hash differed from the
   metadata seed, so both GDP trajectory requests stayed
   `BLOCKED / DEPENDENCY_UNAVAILABLE`. The saved-byte diagnosis found exactly two
   volatile request-history capture timestamps; all other metadata bytes were
   unchanged. That later diagnosis does not override the frozen v1 failure.
2. **HYCOM coordinate compatibility:** the **572,604-byte** NetCDF file passed the
   unchanged generic format reader, but the study wrapper returned
   `HYCOM_REQUESTED_NATIVE_TILE_OR_STRIDE_CHANGED`. The coordinate variables are
   float64 while their labels show promoted-float32 rounding, exceeding v1's
   adjacent-spacing tolerance. The study therefore exposes `current_field: null`,
   not an accepted forcing field or a tested current-only trajectory.

The detailed [saved-byte compatibility diagnosis](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/matched-current-v1-compatibility-diagnosis.md)
and its [machine receipt](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/research-evidence/matched-current-v1-compatibility-diagnosis.json)
record the exact timestamp and native-axis evidence. They contain no new model
score and do not authorize a hidden retry, replacement group or expanded tile.

## Where the immutable archive lives

Current location: **`data/research/matched-current-v1`** in the public repository.
It was moved after acquisition from `data/public/matched-current-v1` without
changing any of its **18 original files**. The protocol, raw bodies, detached
hashes, forecast receipt and first-score report are byte-identical; neither the
acquisition nor scoring was repeated by this move.

The [archive-location receipt](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/research-evidence/matched-current-v1-archive-location.json)
records every original file hash, the original `c62e745` freeze history and the
reason for the location change. The old completed fresh-study replay checks an
exact historical `data/public` fixture inventory. Adding a later study there
caused a replay compatibility failure; moving only the new archive restored the
historical **180/180** comparison without editing its frozen code, inputs,
receipts, predictions or scores.

**`data/research` is not private access.** Its contents remain public repository
research evidence. Future exposure inventories must include this later archive
explicitly. Older raw diagnosis records retain the original path as capture
history; use the current location above when running replay.

## Exact scientific identities

| Artifact | SHA-256 |
| --- | --- |
| Frozen protocol | `210367efb31319285ddaff2018e8a64f330c68652cd9feb51aaade1df86ef5f6` |
| Acquisition manifest | `4da5bb7780334a4a4e6e64080b406f90362f179f81b40d3e2927a6bbcce3ce9e` |
| Forecast file | `4818e8acdb6fc51dda5967a51b7274c93ee0475edb992afa51c36ed7a246565f` |
| Evaluation file | `354a167f13809c11d965315eb440e2cdd22bb946a85ccbed2dc0ba5561614db7` |
| Current NetCDF body | `7005d62128f100066c6d7120fc4e32c4a6c524814d1085dcc19996dfbc910065` |

The current result is
[`data/research/matched-current-v1/evaluation.json`](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/data/research/matched-current-v1/evaluation.json).
A hash identifies bytes; it does not establish physical accuracy. The numerical
first-score/replay record and public reader's structural verification are separate.

## How to use the Data Lab card

1. Open **Data Lab → Research details and historical buoy validation**.
2. Select **Load matched-current study** in **Do matched currents explain the
   buoy's motion?** This reads saved artifacts; it does not acquire data or score.
3. Read the **0 / 36** coverage and withheld primary table. Both groups and all
   candidates remain selectable. There is no supported path to draw, so the UI
   states that no synthetic route will be substituted.
4. Expand **Coverage, missing paths and scientific lineage** to inspect candidate
   reasons, per-group coverage, secondary common supports, exact hashes and the
   full saved envelope.
5. With local operator access connected, select **Ask Chalk about matched
   currents** to request a bounded explanation of this exact result and protocol.
   The saved result remains visible if the provider is unavailable.

For a future valid result, the card's recorded/model checkboxes keep a fixed plot
scale. It joins only adjacent available hourly positions, leaves gaps open, and
can display **Hourly displacement arrows** for a selected saved hour. Those arrows
represent differences between saved hourly endpoints, not native HYCOM grid
velocity samples. Display projection does not compute the stored great-circle
errors. These implemented controls do not make an unavailable v1 path appear.

The compact primary table withholds overall ADE/FDE unless all 36 cells score.
Research details label each model's own available-cell support and each pair's
common support separately; a successful subset cannot become the full comparison.
Missing errors stay null, not zero. No automatic winner or deployment promotion
is selected, even for a later complete comparison.

## Read-only reader and API contract

`load_frozen_matched_current_result()` reads the archive at its current research
location. Its default requires a literal trusted result identity. It verifies the
protocol/acquisition helpers, detached and trusted file hashes, acquisition →
forecast → score clocks, exact groups/models/horizons, shared targets, support and
aggregate arithmetic, and scientific flags. It rereads identities to detect a
concurrent replacement. It performs no model execution, scoring, acquisition,
freeze, provider request or write.

The return value has two separate objects:

- `report`: the whitelisted saved `MATCHED_CURRENT_RETROSPECTIVE_DIAGNOSTIC`.
- `artifact_identity`: exact file/protocol/manifest identities,
  `result_pin_verified: true`, and
  `verification_scope: FROZEN_ARTIFACT_LINEAGE_AND_STRUCTURE_NOT_NUMERIC_REPLAY`.

`numeric_replay_verified` is **false** in this reader envelope. The independent
CLI replay was performed separately; the API must not claim it reran that work.
Unpinned local-test mode is explicitly labeled and rejected by the public service.

```text
GET /api/v1/research/matched-current

POST /api/v1/research/matched-current/investigate
{
  "question": "What do the missing results support?",
  "report_sha256": "<the selected report hash>",
  "protocol_sha256": "<the selected protocol hash>"
}
```

GET is a public, no-store artifact read. POST requires existing local operator
authentication. Missing pinned evidence returns 404; invalid/stale evidence 409;
an unreadable local reader 503. A stale clicked identity is rejected before a
provider turn, and the server checks identity again when that bounded turn ends.
No API route accepts an acquisition URL or arbitrary filesystem path.

## Chalk's job for this result

Chalk explains the failure ledger and its scientific limits. It does not turn a
null result into model skill. The matched-current workflow is separate from the
source-investigation action agent and has just one evidence tool:
**`get_study_evidence({})`**. It provides the fixed study summary, own/common
supports, blockers, provenance and scientific flags from the selected snapshot.

The two evidence IDs are:

```text
matched-current-report:<evaluation-file SHA-256>
matched-current-protocol:<frozen-protocol SHA-256>
```

A grounded `REPORT` must cite both. `STOP` and provider failures retain the existing
bounded-research contracts. There is at most one evidence read and two model calls,
with configured request/turn deadlines. The explanation is concise nonnumerical
prose beside the authoritative numeric report; it cannot train, acquire data,
change a case or ledger, start a camera, operate a pump or send Photon messages.
The isolated HTTP check used disabled providers and is not a live Chalk proof. The [separate live verification](complete-software-verification-20261017.md) returned REPORT for the saved matched-current result, with its exact report/protocol citations; it did not acquire new trajectories or operate a device.

## Reproduce the saved attempt without repeating it

The frozen command-line modules retain their original default archive path as
part of the frozen source. **Pass the relocated directory explicitly.** Run only
offline replay here, with an unused output filename:

```sh
.venv/bin/python -m scripts.evaluate_matched_current_study \
  --directory data/research/matched-current-v1 \
  --output work/matched-current-v1-replay.json
```

The default command refuses to perform a first score when no saved result exists;
`--output` refuses to overwrite an existing file. Do not add `--first-score`, run
acquisition again or rewrite the archived failure to obtain a nicer result.

To read the verified local artifact view without running a model:

```sh
.venv/bin/python -c 'from apps.ocean.reeftrace_ocean.matched_current_result import load_frozen_matched_current_result; print(load_frozen_matched_current_result()["artifact_identity"])'
```

The original historical fresh-study comparison and the earlier tank/ocean modes
retain their separate meanings and data. This attempt does not add tracks to an
unrelated ocean map or validate centimetre-scale tank transport.

## Next reviewed step: a distinct v2 proposal, not an implemented result

A proposed v2 would preserve v1 and its failure history, then review and freeze
only two bounded compatibility corrections before any new GDP outcome request:
allowlisting the exact two valid metadata capture-time tokens, and declaring the
observed native coordinate encoding/lattice bounds. It must keep actual saved
coordinates and masks, including the real eastern edge near −65.04°, with no
snapping or expansion to −65°. Units, version, URL, depth, groups, time windows,
models, source product, tile, stride, budgets and no-tuning/no-replacement rules
remain protected.

This is **pre-GDP-outcome**, not an entirely scientific-value-unseen first design:
HYCOM forcing bytes were already acquired and decoded for compatibility diagnosis.
No v2 implementation, freeze, acquisition, score or success is claimed here. A
future reviewed correction must have its own identity and explicit exposure
history. It would still be a small retrospective buoy-motion study, not validated
surface-plastic forecasting, reef protection or a completed physical experiment.
