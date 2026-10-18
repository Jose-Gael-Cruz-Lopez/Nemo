# Nemo scientific workspace and concise demo

This guide describes the current local UI. The newest presentation changes are
not yet a verified hosted release. The project starts with **where observed
pollution could have come from**. Investigations compares declared candidate
entry regions under a frozen flow model. Prevention extends that source-tracing
question into a decision about interception; it does not replace it. Both still
need independent real trials. See [the source-tracing scope and validation
plan](source-tracing-mission.md).

## A quiet starting point

The light-blue workspace uses square corners, thin rules, flat research panels
and a full-height desktop shell with a **220 px** sidebar. Navigation narrows or
reflows on smaller screens. Duplicate team controls and the four-builder badge
are removed. The first page is **Experiment overview**, with one primary
**Start software demo** action and three short steps:

1. **Source tracing** — open an observed path and its candidate-source support.
2. **Layout comparison** — compare two layouts under the same model conditions.
3. **Evidence review** — ask Chalk to explain the saved report and uncertainty.

Setup counts and recent observations remain under **Setup and saved
observations**, closed initially. The three-step guide opens features; its
**Ask Chalk** shortcut does not itself call a provider. Authentication, error
handling, software stop and scientific details remain available.

## Light-blue Glyph Trail background

The backdrop adapts the actual supplied **Glyph Trail** component credited to
[Justyna](https://justbuilt.it). Its [source receipt](research-evidence/glyph-trail-source/provenance.json)
retains the full **15,078-byte** source, upstream URLs and SHA-256
`09092a4b69ad5321dd6c7f5a54ada9f248f468f2be74eb3164197e5922337a89`.
The original Bayer matrices, glyph masks, procedural sine field, ordered
multi-level draw, continuous max-stamp brush and diffusion/decay math are retained.
Framer editor controls are removed; no Framer runtime package is required.

The background uses pale blue `#edf7fe`, ink `#dbeaf4` and trail `#c7e1f1`.
It is `aria-hidden` and **`pointer-events: none`**: it cannot block clicks,
selection or keyboard focus. A passive pointer listener supplies decorative
motion without changing application state. The effect is not a motion-vector
plot, token track, current field or experiment result.

Rendering is bounded at **24 fps**, **600,000 backing pixels**, a **1,600 px**
maximum dimension and **192 brush stamps** per step. Reduced-motion, hidden-tab
and off-screen states stop animation; a static light-blue fallback remains.
Cleanup cancels frames, disconnects observers, removes listeners and releases
canvas/field buffers. The source receipt records attribution and the absence of
an explicit component-license header without claiming a new license grant.

## Software-only demonstration

Use the already running local service. If a fresh start is needed, run
`.venv/bin/python scripts/dev.py` from the repository. Do not enable Photon or
open the camera just to present this flow. Operator access uses the existing
local token privately; provider credentials remain server-side.

**1. Load and inspect.** Choose **Start software demo**, then **Open source
trace**. Use the selected moving-trajectory example and its saved source report.
The map is a tank water-plane view in centimetres. Candidate regions are allowed
entry locations; the path is the saved synthetic observation. Source bars show
relative support under a frozen candidate set and drift model, not the
probability that a named polluter caused an item. Recomputing explicitly creates
a new evidence revision. The retained-endpoint example can legitimately return
Unknown because its missing journey is not recoverable from one stuck endpoint.

**2. Compare interception.** Open **Prevention**. The default mode is the
changing-current ocean example. One compact scenario toolbar contains the
scenario selector and **Compare ocean layouts** action. After loading, the
recommendation, combined trajectory plot and two layout result cards are primary;
the release selector stays compact above the plot and the **six independent
checkboxes follow the plot**. No-interception paths, layouts A/B, reef proxy,
interceptors and current arrows can be inspected independently.

Both layouts use the same six hypothetical releases, changing-current snapshot
and equal total interception-line length. Lower predicted reef entries are better
within that declared model. Entry ranges retain unresolved releases; they are
accounting bounds, not confidence intervals. Filtering to one release changes
only the drawing: every result still counts all six releases, with fixed axes
and vector scale. Turn on current arrows to inspect changing direction/speed;
the arrow-time slider does not recompute paths or totals.

**3. Explain the saved evidence.** With operator access, choose **Ask Chalk about
these layouts** once. Chalk sends a bounded investigation through its configured
model gateway and explains the frozen comparison; it does not calculate the
layout counts, steer a pump or infer an exact pollution source. Check the
**Live Chalk response / No live model response** label and exact report/method
citations. A provider error remains explicit, with no automatic retry. Source
investigation and tank prevention have their own evidence-bound Chalk requests.

**4. Inspect methods when needed.** Expand **Scientific method, current source
and full report** for model provenance, assumptions, the immutable identity and
complete JSON. Numerical sensitivity and plot-reading guidance remain separate
closed disclosures. Data Lab retains historical NOAA trajectories and model
comparisons with independent trajectory/vector controls. These scientific views
are available without forcing their full tables onto a first-time demonstration.

## Keep evidence categories separate

| Feature | What it demonstrates | What still needs measurement |
| --- | --- | --- |
| Synthetic source trace | Software inference under declared candidate/flow assumptions | Calibrated real tank tracking and source trials |
| Ocean comparison | Conditional first-contact outcomes under captured changing currents | Object response, barrier efficiency, local currents and reef geometry |
| 3D tank view | Animation of a frozen comparison and separate trial ledger | Physical capture; `NOT_CAPTURED` stays unmeasured, not zero error |
| NOAA Data Lab | Historical drifter/model errors with fixed study identities | Transfer to floating plastic and independent future cohorts |
| Chalk | Evidence-grounded explanation with citations and explicit failure states | Availability and accuracy of each actual provider response |

The additional origin-residual diagnostic has a saved **48/48-cell** exploratory
result on **12 already-viewed targets**. Its read-only API and bounded Chalk
review are available through **Data Lab → Research details and historical buoy
validation → Load drift-offset study**. The dedicated card shows all four saved
model rows, both groups, independent fixed-scale paths and explicit review status.
Here ‘origin’ means forecast start, not the pollution source; Investigations
retains source inference. See [the panel guide](origin-residual-datalab.md).
It is not a learned model, untouched test or promoted operational method. See
[the exact results and limits](origin-residual-results.md).

No new tank experiment is implied by this presentation. A real trial still needs
fixed overhead camera geometry, measured water-plane mapping, separate flow-fit
and validation recordings, a frozen profile and honestly counted baseline/layout
outcomes. Ocean metres and tank centimetres must not be mixed. The software has
no pump power actuator; a software stop does not turn off its wall supply.

## Release checkpoint

[Hosted run 39079486572](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/actions/runs/39079486572)
passed all three jobs for historical commit **`f3353e0`**. The newer presentation
passed **283 frontend tests**, full ESLint, TypeScript and an isolated production
build locally. Browser checks verified that hiding Layout A and filtering to R1
leaves the two full six-release scores and plot scale unchanged; current arrows
remain available. Its exact-commit hosted status is separate from these local
checks. The UI revision changes presentation, not model definitions, frozen data
or experiment outcomes.
