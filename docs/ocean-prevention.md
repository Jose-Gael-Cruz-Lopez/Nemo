# Ocean-mode prevention comparison

Tideward compares two interception layouts using the **same changing ocean currents and the same six hypothetical releases**. Its question is concrete: under this model scenario, which layout lets fewer particles reach an illustrative protected reef-area polygon? The ocean page is a read-only simulation. **Tank experiment & trial ledger** retains the separate camera-calibration workflow, frozen comparisons and recorded trial ledgers; physical commissioning remains incomplete.

## Run the software demonstration

1. Open **Prevention**. **Ocean · changing currents** is the default mode; no camera or operator token is needed to load its numerical comparison. **Data Lab** opens the same combined comparison; historical buoy tests are tucked under **Research details and historical buoy validation**.
2. Keep **Ocean scenario → Downstream corridor · illustrative what-if** and click **Compare ocean layouts**.
3. Read the two **Predicted reef entries** cards. Lower is preferable within this fixed model scenario. The no-interception count provides context below them.
4. Use the **Choose the layers to compare** checkboxes on the **single combined graph**. Layout A is blue; Layout B is dashed gold. No-interception paths, the orange reef proxy, interceptor geometry and current arrows are independently selectable. Initially both layout paths and geometry are visible; no-interception context and current arrows are hidden to reduce overlap.
5. Use **Inspect a release** to inspect one hypothetical release. This filters the drawing only: all six releases remain in the results. Turning a layer off never recomputes a trajectory, rescales the common axes or changes a count.
6. Enable current arrows to reveal their valid-time slider. It changes the displayed flow samples, while all complete six-hour predictions and the arrow-speed scale stay fixed. The arrows are interpolated model values, not finer measurements.
7. Connect local operator access, then click **Ask Chalk about these layouts** once. Its answer must cite this exact comparison and method. Inspect **Comparison evidence citations**. A disabled provider, timeout or rejected response leaves the deterministic result visible.
8. Change **Ocean scenario** to **Original proxy · no-entry model control**, then click **Compare ocean layouts** again. The selection clears the previous report and answer. This example correctly returns a tie.
9. Open **Scientific method, current source and full report** only when the audience needs provenance, equations, assumptions or the complete report.

No load or research review writes a tank case, records a physical release, moves hardware or sends a Photon message. To demonstrate immutable trial entry, deliberately choose **Tank experiment & trial ledger** and follow the [integrated demo](integrated-team-demo.txt).

## What the saved scenarios show

Both layouts use **2,000 m of idealized absorbing line**. Central coverage uses one central segment; flanking coverage divides the same total length between two outer segments. Releases, start time, six-hour horizon, current snapshot, numerical solver and first-contact rules are identical across layouts.

| Saved scenario | No-interception predicted reef entries | Central coverage | Flanking coverage | Supported conclusion |
| --- | ---: | ---: | ---: | --- |
| `downstream-corridor-v2` | 6 of 6 | 2 entries, 4 idealized captures | 4 entries, 2 idealized captures | Central has fewer predicted entries in this illustrative what-if |
| `initial-proxy-v1` | 0 of 6 | 0 entries, 4 idealized captures | 0 entries, 2 idealized captures | Tie for reef entries; different capture counts do not demonstrate protection of an area that no baseline particle reaches |

The downstream reef proxy was selected **after viewing the current preview**. Its report labels it `ILLUSTRATIVE_WHAT_IF_AFTER_VIEWING_PREVIEW` and discloses that it is **not independent performance evidence**. It is a transparent decision-workflow example, not a pre-registered success or an optimized deployment site. The original geometry is preserved as a no-entry model control. Neither polygon is a mapped real reef boundary; neither result is measured waste capture, coral survival or environmental benefit.

The counts are six modeled release alternatives. They are not six independently observed experiments, kilograms removed, calibrated protection probabilities or a complete model of marine litter.

## Current forcing and numerical method

The comparison replays the same checked [PacIOOS ROMS Main Hawaiian Islands](https://www.pacioos.hawaii.edu/metadata/roms_hiig.html) snapshot used by the [current-driven prediction](current-driven-prediction.md): three valid times from **17 October 2026 18:00 UTC through 18 October 00:00 UTC**, approximately **4 km** grid spacing, **3-hour** forcing and **0.25 m** selected depth. Eastward `u` and northward `v` are in **m/s**. Source CSV, metadata and manifest hashes are checked locally. A page load never fetches a newer forecast.

```text
d(longitude)/dt = u(longitude, latitude, t) / metres_per_longitude_degree(latitude)
d(latitude)/dt  = v(longitude, latitude, t) / metres_per_latitude_degree(latitude)
```

The solver uses WGS84 metric derivatives, bilinear spatial interpolation, linear time interpolation and RK4 integration. It samples flow at the moving particle's position and time. A changing speed alone can still produce a straight path; a bend follows a change in direction. No artificial curvature is added.

Each release is integrated **once**. The no-interception context and both layouts then inspect the same immutable path. Interception does not alter the current field. Collector contact and protected-polygon contact are located on supported **300-second output chords** in a fixed local east/north metre frame. The earliest event wins; reef entry wins an approximately simultaneous capture/entry tie within one microsecond. A release already inside the proxy is an immediate entry, even if no velocity is available. An idealized capture stops that layout's displayed path at contact.

The 300-second integration output is a numerical sampling interval, not 300-second source measurements. Sub-chord curvature or brief contacts can be missed. The roughly 4 km / 3-hour source cannot resolve individual reef eddies or establish the engineering effectiveness of 2 km interception lines. The selected geometry is a model illustration at finer scale than its forcing support.

## Outcomes, bounds and recommendation

Each release has exactly one outcome per layout:

| Outcome | Meaning |
| --- | --- |
| `ENTERED_PROTECTED_ZONE` | First supported contact reaches the closed proxy polygon before idealized capture |
| `IDEALIZED_INTERCEPTION` | First supported collector contact occurs before reef entry under perfect absorbing-line assumptions |
| `NO_ENTRY_WITHIN_HORIZON` | The full supported horizon completes without entry or capture; it says nothing about later arrival |
| `UNRESOLVED` | Missing or unsupported forcing prevents a complete no-entry determination |

Missing forcing is never zero-filled, extrapolated or counted as protection. A contact already resolved before a later forcing stop remains known under the ideal model; a partial path without a contact remains unresolved. Every summary retains all six fixed releases:

```text
entry_count_bounds = [known entries, known entries + unresolved releases]
entry_fraction_bounds = entry_count_bounds / all fixed releases
```

These are accounting bounds, not statistical confidence intervals. The recommendation is `BEST_LAYOUT` only when one layout's upper entry bound is strictly lower than the other's lower bound. Equal fully resolved entry counts return `TIE`; overlapping unresolved bounds return `INDETERMINATE`. Higher capture count alone does not override the reef-entry comparison.

Ocean result status is separately `COMPLETED`, `PARTIAL` or `UNSUPPORTED`, based on the common forcing paths. It is not a physical-trial status. Validation flags remain false, and measured entry/interception counts remain null.

## API and Chalk contract

`GET /api/v1/research/ocean-prevention?scenario_id=downstream-corridor-v2` is public, offline and read-only. The only supported presets are `downstream-corridor-v2` (default) and `initial-proxy-v1`; arbitrary release/reef/interceptor geometry cannot be supplied through this endpoint. Responses use `Cache-Control: no-store`.

`POST /api/v1/research/ocean-prevention/investigate` requires local operator authorization and exactly these fields, copied from the selected GET report:

```json
{
  "question": "Explain the layout comparison and what must be measured before claiming reef protection.",
  "scenario_id": "downstream-corridor-v2",
  "snapshot_sha256": "64 lowercase hexadecimal characters returned by GET",
  "method_sha256": "64 lowercase hexadecimal characters returned by GET",
  "scenario_sha256": "64 lowercase hexadecimal characters returned by GET",
  "report_sha256": "64 lowercase hexadecimal characters returned by GET"
}
```

The example hash strings are descriptions, not valid request values. The server validates the strict request, forcing/method/scenario/report identities, canonical scenario/report hashes, outcome accounting, conservative bounds and scientific scope before a provider call. It rechecks the complete report after the review; a changed snapshot or selector is rejected rather than attaching stale prose to new results.

Chalk can read only one compact `get_study_evidence` result containing provenance, scenario geometry, assumptions, all release outcomes, counts and bounds. Full plotted paths and vectors are omitted from that tool payload. The orchestration allows at most **one evidence read and two bounded model calls** and permits only `REPORT` or `STOP`. A `REPORT` cites exactly:

```text
ocean-comparison:<report_sha256>
ocean-method:<method_sha256>
```

Numerical results remain authoritative beside concise nonnumerical prose. The service rejects stale evidence, unrelated citations, unsupported named winners on tied/indeterminate comparisons and archival wording that conflicts with the saved forecast mode. Provider or contract failure returns a safe `STOP` and retains the report. The read-only tool has no case-edit, acquisition, training, trial-write, camera, pump or messaging authority.

After the valid-time window ends, the report becomes `archived_forecast_snapshot`; that display state is included in its full report identity. Before expiry it is `forecast_snapshot`, which may contain future valid times. Neither mode is a live measurement. The FMRC best-time-series aggregation does not supply a separately verified single model issue time here; retrieval before valid time does not establish complete operational forecast causality.

## What must be measured next

For real coastal use, choose a real mapped target area, defensible release scenarios and feasible collection geometry before evaluating held-out observations. Acquire region-appropriate, issue-time-pinned currents and independently observe debris or matched drifters over common horizons. Evaluate windage, waves/Stokes drift, buoyancy, diffusion, beaching, retention, capture efficiency and barrier-flow interactions. The current model establishes none of those effects.

For the team's tank, use the retained **Tank** workflow with independently measured camera mapping, drift training/validation and frozen layouts, then record new known-source physical trials. Ocean metres/m/s cannot calibrate tank centimetres/cm/s. The camera and pump can stay off for this entire ocean-mode software demonstration.
