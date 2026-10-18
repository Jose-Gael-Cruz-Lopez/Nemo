# Initial drift offset in Data Lab

Open **Data Lab → Research details and historical buoy validation → Load
drift-offset study**. This explicit action reads the separately pinned saved
origin-residual diagnostic. It does not download trajectories, fit a parameter,
build a forecast, score another experiment or change the active model.

Here **origin means forecast start**, not the original pollution-release source.
This card tests later buoy movement. Source inference remains in Investigations;
see [the source-first mission](source-tracing-mission.md).

## What is displayed

The complete saved comparison has **48 model/hour cells**, but only **12 distinct
already-viewed processed positions**: two buoy groups, four candidates and six
later hours. The method was proposed after the preceding two-group outcomes were
seen. Its scope remains `POST_OUTCOME_EXPLORATORY`.

The four ADE/FDE rows are stored equal-group summaries, in metres:

| Candidate | Average miss, ADE | Miss at six hours, FDE |
| --- | ---: | ---: |
| Stationary | 3,490.1188 | 6,069.3529 |
| Last observed drift | 1,510.2316 | 3,240.5762 |
| HYCOM current-only | 5,063.0203 | 9,151.6451 |
| HYCOM + initial drift offset | 1,030.0495 | 2,355.9582 |

These descriptive scores do not establish transfer to unseen drifters, surface
plastic, source recovery, a real tank or reef protection. No model is promoted.
The earlier v2 result and all immutable first-score artifacts remain unchanged.

## Plot controls

- Select either GDP group. The table still describes both groups equally.
- Use independent checkboxes for recorded positions and all four predictions.
  Hiding a series changes neither scores nor its group's full plot domain.
- Select a saved hour. An enlarged marker identifies that hour.
- **Adjacent-endpoint displacement arrows** show the difference between two
  consecutive saved positions. They are not native HYCOM water-current samples.
- The plot uses equal east/north display scale in a local geographic projection.
  It does not recompute the stored great-circle errors. Unavailable hours remain
  gaps; the renderer does not join across them.

Metric help is available on hover, focus or touch. All-hidden paths have an
explicit message; missing paths are never replaced by a synthetic fixture.
Scientific lineage, per-group coverage, assumptions and complete JSON remain
inside **Method, missing outcomes and provenance**.

## What the adjustment and RK4 do

The last context interval supplies an observed drift velocity. Subtract the
HYCOM current at the forecast start to obtain a constant local east/north offset,
then add it to a copy of the changing current field. The unchanged RK4 solver
samples that field at intermediate times and positions within each short step.
It estimates motion under the supplied field, not the true water motion itself.

There is no fitted coefficient, decay tuning, clipping or inferred windage.
The offset may combine object response, forcing discrepancy and data processing;
this comparison does not identify the physical cause. Full equations and source
identities are in [the saved result guide](origin-residual-results.md).

## Chalk and evidence identity

Local operator access enables the explicit **Ask Chalk about the drift offset**
action. It posts only the question and the loaded report/protocol/identity pins.
The backend binds a read-only evidence snapshot, allows one evidence tool and at
most two bounded model calls, then rechecks freshness. A REPORT must cite the
exact report and protocol. It cannot acquire data, rerun models, mutate trials,
operate devices or send messages.

The UI checks the actual envelope's fields, scope, units, group/model/hour
alignment, available/null cells and returned answer identity. Its guards do not
perform independent byte verification. The backend verifies saved bytes and
lineage against a separately committed literal anchor; that is not independent
scientific attestation or numerical replay. The default reader's
`numeric_replay_verified:false` remains accurate.

Missing artifacts, stale pins, unsupported data, authentication failures and
provider errors stay explicit. A disabled provider returns **STOP · No live
model response** while the numerical table remains available. Neither loading
the card nor moving a control calls Chalk. There is no automatic retry, and
in-flight results are discarded after unmount or API/token/evidence changes.

Browser verification used a disposable, provider-disabled API and separate Next
source copy; the active local API/Photon worker was not restarted. The running
main server may need its ordinary authorized restart to load the previously
added endpoint. That runtime transition is separate from testing this code.

## Review and execution provenance

Actual Grok web round thirteen reviewed this integration, and round fourteen
reviewed the original source-tracing mission and source-labelled validation.
Full prompts/responses and corrections are preserved in the [additive
archive](grok-evidence-continuation.md) and [contribution
ledger](grok-contribution-ledger.md). Static advice and actual local/browser/HTTP
execution are separate records. These exchanges do not prove live xAI
Voice/Imagine use or sponsor qualification.
