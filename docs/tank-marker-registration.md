# Marker-assisted tank registration (development v1)

Owner: Aarush Mane (`@aarushmane`). Base: `784d9bb`. Work belongs on
`aarush/tank-marker-registration`; this ticket does not authorize a merge or deployment.

This is an implemented **dry-development workflow**, not a physically validated
centimetre measurement system. Source tracing still uses the existing sequence:
pixel detections → approved centimetre mapping → gap-preserving tracks → velocity
samples → separately fitted/checked drift → source support → intervention accounting.
No source-release labels enter CaseInput or inference tools.

## Rehearse without hardware

```sh
PYTHON_DOTENV_DISABLED=1 .venv/bin/python -m scripts.rehearse_tank_registration \
  --output-dir work/tank-registration-rehearsal
```

This constructs images locally. It does not load `.env`, open a camera, call a
provider, alter the application database or fetch models/data. It writes a
configuration, printable tiles, four before/after screenshots and a finite,
content-hashed JSON report. Repeated runs with the same OpenCV version produce
identical reports; the report records that version and frame pixel hashes.
The raster-recovery test tolerance is **0.05 cm on constructed images**, fixed in
the test, not a claimed real sensor accuracy.

Open `/registration-demo` on the dashboard for four manually stepped stages:
aligned → bumped/stale → realigned candidate → missing reference/stale. The demo
uses only constructed frames. Toggle its grid and geometry layers independently.
The initial approved state is illustrative; the live API refuses SYNTHETIC admission.
The demo and printable example are also under `dashboard/public/registration-demo/`.

## Measure once, preserve the plane

1. Fix the camera and lens settings. Mark the waterline and tank origin/axes.
   Survey the **actual water outline**, including any concavities. Do not replace
   it by a rectangular bounding box. Use centimetres throughout.
2. Print `printable-markers.svg` at **100% / actual size**, without fit-to-page.
   Verify the ruler is 50 mm and each black square is 20 mm after printing.
   These are individual example tiles, **not** a surveyed tray-size arrangement.
   The synthetic JSON's positions are examples and must never be presented as a
   survey of the real rig. Preserve the white quiet zone around each code.
3. Mount at least seven distinct `DICT_4X4_50` IDs rigidly around the tray. Their
   measured reference points must be at the water-surface height. Survey every
   black-square corner in decoded TL, TR, BR, BL order. Do not substitute rim or
   bottom coordinates. Different-height compensation and lens distortion correction
   are **not implemented**; reject that setup until separately validated. A ChArUco
   intrinsic-calibration workflow is separate work, not a water-plane shortcut.
4. Freeze at least four IDs for fitting and three other non-collinear IDs for checks.
   All corners of a check ID are excluded from fitting. The fitting-reference hull
   must cover the whole supported water region. Keep checking marks spatially
   spread; 12 correlated corners are not 12 independent experiments.
5. Create the configuration with `data_origin: "OPERATOR_SURVEYED"`,
   `references_surveyed: true`, `reference_plane: "measured_water_surface"`, the
   measured marker corners and `water_polygon_cm`. Freeze `max_error_cm` before
   looking at results (default and ceiling **0.5 cm**). Freeze the waterline,
   layout, flow-configuration and token-class identifiers under `context`.
   This declaration does not make an unsurveyed scale or height true.
6. Optionally declare the **actual surveyed** `expected_filter_polygon_cm`. Its
   location/shape gates green contour candidates. Green colour never supplies
   an interceptor identity, protected zone, source label or token track.

## Local commissioning UI and additive API

In Camera → field commissioning → water-surface mapping, paste the measured
configuration under **Recognize measured reference markers**. Start the webcam
manually using the existing controls first; registration only reads its current
buffer. Click **Propose / recover marker mapping**. Three distinct samples must
pass before approval is offered. Inspect the independent error and separate tray
and filter candidates. Correct the surveyed configuration and propose again if
needed; the existing manual mapping form stays available.

Confirm the measured scale/reference height and any unique geometry candidates,
then explicitly approve. This creates the **existing, unchanged calibration record
format**, an immutable `marker_registration` sidecar and an immutable
`marker_approval` receipt containing the detected references, original frame
identity/hash, configuration/policy references and checks. New managed recordings and their frames bind the exact `marker_approval_id`.
No scientific trial geometry is rewritten. A local UI draft containing a managed map cannot restore
approval after reload. The backend also requires a fresh proposal after restart.

Operator-only local routes (all `Cache-Control: no-store`; unavailable in the
cloud software-demo profile):

| Route | Purpose |
| --- | --- |
| POST `/api/v1/vision/registration/configure` | Freeze surveyed config; replace proposal explicitly |
| GET `/api/v1/vision/registration/status` | Examine an already buffered frame, at most 2 Hz |
| POST `/api/v1/vision/registration/approve` | Exact proposal hash, height/scale attestation, optional geometry confirmations |
| POST `/api/v1/vision/registration/context` | Declare changed rig context; invalidate mapping/flow dependencies |

Approval takes `{proposal_id, water_surface_and_scale_confirmed: true,
confirmed_layers: ["tray_boundary", "filter_border"]}`; omit layers that have not
been independently identified. On a reported rig change, update the config's
context IDs and measurements before proposing recovery. The dashboard's report
change button invalidates conservatively even when the supplied IDs are unchanged.

## What the numbers mean

For image pixel `(u,v)`, the existing homography maps
`[a,b,c]ᵀ = H [u,v,1]ᵀ`, then `x_cm=a/c`, `y_cm=b/c`. Singular matrices and image
horizons are refused. Fit error is not the admission check. For each held-out
corner, `e_i = hypot(x_predicted-x_surveyed, y_predicted-y_surveyed)`;
`max(e_i) <= max_error_cm` must hold. The report includes the mean, maximum and
actual number of check pairs. This test establishes consistency with the declared
survey, not independently proven physical accuracy or confidence coverage.

At each monitoring sample, apply the **frozen** accepted matrix to current marker
corners and compare with that matrix applied to the original marker corners.
Maximum displacement over all markers must stay ≤ **0.2 cm**. A new fit never
absorbs a bump under the old approval. Grid lines project back through `H⁻¹`, then
clip to the declared actual water polygon; cursor readout is withheld outside it.
The 1/5/10 cm display spacing is a drawing choice, not a resolution/precision claim.
Tracking uses the same existing homography; observations outside the registered
water region are gaps, and a calibration version change breaks association.

## Frozen development policy and failure states

| Policy | v1 bound |
| --- | --- |
| Frame size | uint8 BGR, ≤1920×1080 pixels |
| Expensive marker/geometry processing | ≤2 Hz, no polling overlap |
| Maximum monitoring/frame age | 1.5 s |
| Initial stability | 3 distinct processed frames (normally ≥1 s) |
| Camera reference displacement | ≤0.2 cm from frozen reference image |
| Confirmed geometry distance | ≤0.3 cm to surveyed polygon (symmetric vertex-to-edge check) |
| Blur/low-contrast guard | Laplacian variance ≥20 |
| Contours | ≤64 inspected, area ≥200 px², ≤32 vertices |
| Black tape threshold | HSV V≤65 |
| Green border threshold | HSV [35,80,40] to [85,255,255] |

The exact policy is hashed in each proposal. These thresholds are development
choices, **not tuned or validated on physical results**. Freeze a separately
reviewed new policy version before changing them for the rig; do not widen a
threshold until a problematic frame passes. The frame-size bound limits work;
there is no hard real-time latency guarantee on arbitrary hardware.

States distinguish NO_REFERENCE, CANDIDATE_MAPPING, VALIDATION_FAILED,
STABLE_APPROVED and MOVED_STALE. Missing/occluded/wrong/duplicate IDs, unreadable
codes, blur/glare, failed held-out checks, session/resolution changes, nonmonotonic
frame identity, monitoring gaps and declared context changes withhold coordinates.
A previously accepted mapping latches stale until explicit recovery. Returning
markers alone does not resume analysis. Some causes (such as glare vs occlusion)
share an unavailable-reference reason; the software does not invent the cause.

Confirmed tray/filter candidate loss also invalidates the mapping conservatively
and appends the existing `rig_change` generation. Unconfirmed colour candidates
are **not a reliable sensor of physical layout**. A matching green decoy cannot
be distinguished from the real filter by colour/shape alone: operator identification
and the layout-specific drift gate remain mandatory. Do not infer unchanged flow
because references remained still. Never move a collector, pump/outlet, waterline
or token class and reuse an old drift approval.

Backend gates recheck managed mappings before recording, at the bounded interval
during recording, at completion, before LIVE analysis and in field admission.
A detected change aborts the scientific recording; partial frame evidence may
remain for audit, but no complete recording is admitted. A new mapping uses a new
immutable record when its matrix/session/check report differs; old cases, frames,
reports and trials are never relabelled. Exact unchanged numerical records may
retain their content ID, with a separate fresh approval receipt. Detached saved-map
reuse cannot bypass the marker gate. Manual maps retain their existing workflow;
this feature does not retrofit marker monitoring onto old manual maps.

## Real-rig validation checklist (not yet completed)

- [ ] Survey reference height, positions, waterline and actual tray/filter outlines;
  identify survey/session IDs and keep fit/check IDs fixed.
- [ ] Check printed scale and lens distortion using separate measured water-plane
  checks; save errors, frame hashes, policy hash and proposal/approval IDs locally.
- [ ] At the intended lighting, test translation, rotation/perspective bumps,
  missing/wet/glared/blurred codes, duplicate/wrong IDs and token shadows.
- [ ] Confirm centimetres disappear and a recording is discarded on a bump/loss;
  confirm a fresh candidate never resumes a trial automatically.
- [ ] Test filter movement, waterline/outlet/pump/token changes and resolution/new
  session; perform the appropriate new survey and independent drift validation.
- [ ] Freeze layout-specific profiles/receipts through the existing admission contract.
  Then evaluate actual prospective trials; do not mix dry outcomes with physical ones.
- [ ] Measure per-frame processing and UI latency on the rig; verify panel close,
  hidden-tab cleanup and no overlapping polling. Save hardware/version details.

No physical run has been performed by this ticket. Dry screenshots contain no
faces or private camera frames. Pinned NOAA/scientific study sources, source
inference, Chalk/Photon, voice and hardware actuation are unchanged.

Implementation references:
[OpenCV ArUco detection](https://docs.opencv.org/4.13.0/d5/dae/tutorial_aruco_detection.html),
[homography concepts](https://docs.opencv.org/4.13.0/d9/dab/tutorial_homography.html),
[ChArUco calibration](https://docs.opencv.org/4.13.0/df/d4a/tutorial_charuco_detection.html).

## Recorded browser checks

Chrome checks on constructed frames covered the actual `TankRegistration` component
against a disposable loopback API/store, in addition to the public dry demo:
incorrect surveyed check coordinates → **1.0056 cm / 0.5 cm, approval disabled**;
manual correction → **0.008 cm, candidate only**; explicit attestation and geometry
confirmation → approved; translated frame → stale and accepted mapping cleared;
recovery requires a new proposal; manual fallback clears the automatic draft.
No camera was opened and no physical trial was logged. This temporary harness is
not a production endpoint. The persistent Python/API and Node tests cover the
same admission decisions; real-rig browser/capture testing remains on the checklist.

The dry demo grid toggle removed/reinstated its SVG grid; bump/loss removed the
grid even while its toggle stayed on, and recovery restored a candidate overlay.
At 390×844 the page had `scrollWidth == clientWidth == 390`. Screenshots:
[aligned](registration-screenshots/aligned.png),
[bumped/stale](registration-screenshots/bumped-stale.png),
[recovery candidate](registration-screenshots/recovery-candidate.png),
[missing reference](registration-screenshots/missing-reference.png),
[phone width](registration-screenshots/phone-width.png).

A local constructed-frame benchmark (OpenCV 4.14.0, this Mac, 25 proposals at
1040×840) measured 4.28 ms median / 5.29 ms maximum for reference detection and
homography/checks. It excludes network, geometry, rendering and camera exposure;
it is not a real-rig latency guarantee.

## Verification commands and results (2026-10-19)

```sh
env -u PYTHON_DOTENV_DISABLED .venv/bin/python -m pytest -q --strict-config --strict-markers -ra
# 2400 passed; 1 pre-existing documented skip (superseded foreground test).
.venv/bin/python -m pytest -q tests/unit/test_tank_registration.py tests/integration/test_marker_registration_api.py
# 40 passed; constructed frames and disposable stores only.
.venv/bin/python -m ruff check apps adapters scripts tests deploy
.venv/bin/python -m pip check
PYTHON_DOTENV_DISABLED=1 .venv/bin/python scripts/e2e_offline.py --timeout-seconds 240 --output work/tank-registration-http-final.json
# 241 PASS, 0 FAIL, 6 explicitly blocked external/live scopes; all I/O guards zero.
cd dashboard
node --test tests/*.test.mjs
# 408 passed, zero skipped.
npm run lint
./node_modules/.bin/tsc --noEmit
npm run build
```

The production build was run from an isolated copy of the same dashboard source
without `.env`, leaving the user's existing local services alone. Local output is
served at `http://127.0.0.1:3002/registration-demo`. The full Python run uses the
repository's offline autouse fixture; the launcher precedence test intentionally
uses its own temporary `.env`, so do not globally disable dotenv for that test.
The one skipped existing test is `test_foreground_detection.py:73`, explicitly
superseded by `test_a_token_matching_what_is_under_it_is_not_seen`. Registration
checks have no skips. The existing Starlette/httpx test-client deprecation warning
is unrelated to registration. No pinned scientific fixture changed.
