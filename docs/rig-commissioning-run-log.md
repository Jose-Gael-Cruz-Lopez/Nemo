# Rig commissioning run log (P1, Megana)

This is the working record for the first physical ReefTrace / Tideward rig. Each
entry says what was actually checked, measured or recorded, and by whom. An
unticked line means **not checked**, not "probably fine".

**Overall status: BLOCKED.** The first physical tank has not run. No calibration,
recording, profile or field receipt in this document comes from synthetic
fixtures or the 23 demo cases.

| Field | Value |
| --- | --- |
| Branch | `team/rig-commissioning-v2` |
| Base `main` (CI green) | `33280da` (rebased 2026-10-17 18:55 EDT; first opened on `e39b64c`) |
| Assignment | Trov handoff #6, claimed after Jose confirmed the rig work is active |
| Log opened | 2026-10-17 14:47 UTC |
| Operator | Megana (@megana111) |

Keep raw images, frame files, SQLite, private paths and evaluator source answers
out of this file and out of Git. They stay under the ignored `data/local/`. Record
only IDs, hashes and measurements here.

## 1. Inventory audit

Use one status per item:
- **PRESENT**: physically in hand and usable.
- **MISSING**: not in hand.
- **FIT-FAILED**: in hand but fails its acceptance check.
- **UNCHECKED**: nobody has looked yet.

Do not buy or cut tubing until the barb fit row says PRESENT.

| # | Item | Acceptance check | Status | Checked by / time | Notes |
| - | ---- | ---------------- | ------ | ----------------- | ----- |
| 1 | Laptop and charger | Runs the repo; a USB data port works; sits outside the splash area | **PRESENT** | Megana (reported), 14:49 UTC
| 2 | External USB webcam: Logitech C270 (team's verified camera, native 1280 × 720) | macOS lists it; OpenCV opens it at an explicit device index; the full bin is sharp in frame | **PRESENT** | Megana + Claude, 22:53 UTC | Enumerated by macOS as "C270 HD WEBCAM" via a USB 3.1/2.1 hub (listed without opening it). Still to confirm in the app: its OpenCV device index (likely not 0 here, because the built-in FaceTime camera is also present) and a sharp full-bin image from the mount. |
| 3 | Webcam data cable and host adapter | Carries data, not charge only; matches the laptop's ports | **PRESENT** | Megana + Claude, 22:54 UTC | Cable and hub carry data: the C270 enumerates through them. |
| 4 | Rigid overhead mount | Clamp, tripod or support holding the whole bin in view; no hand-held camera; cable secured | **PRESENT** | Megana (reported), 22:54 UTC | Rigid mount in hand. Still to confirm once mounted: the whole bin is in frame, looking straight down. |
| 5 | Pond Boss 80 GPH corded pump | Model label and manual read privately; cord intact; operating water depth noted; low-flow setting located | **PRESENT** | Megana (reported), 22:55 UTC | Pump in hand, cord intact, label read privately. Still to record: model and manual's minimum operating depth (section 2). No photos in Git. |
| 6 | Pump's supplied outlet barb (3/8-inch) | The supplied adapter is in hand and matches 3/8-inch ID tube | **PRESENT** | Megana (reported), 22:55 UTC | Supplied 3/8-inch barb in hand and fits the pump outlet. Tubing may now be bought or cut. |
| 7 | About 3 ft of clear vinyl tube, 3/8-inch **inside** diameter | Push-fits the supplied barb with no forcing | **PRESENT** | Megana (reported), 22:56 UTC | 3/8-inch ID tube in hand; push-fits the supplied barb snugly. |
| 8 | Two small hose clamps, plus ties for the outlet | Seal the barb; fix the return outlet outside the tracked region | **NOT USED (operator decision)** | Megana, 22:56 UTC | Operator judged the snug push-fit sufficient without hose clamps. Risk accepted: check for leaks at the barb during the first wet run. The return outlet still needs a fixed, marked position (clip, tie or weight outside the tracked region); method recorded in section 2. |
| 9 | Watertight bin (Sterilite 6 qt or larger) | Interior measured; pump submerged at a stable waterline with overflow margin; collector fits | **PRESENT** | Megana (reported), 22:57 UTC | Watertight; pump fits submerged with overflow margin. Interior dimensions to be recorded in section 2. |
| 10 | Mesh pocket (Top Fin breeder or a smaller secured pocket cut from its mesh) | Fits with clearance; holds a token for the full declared horizon | **PRESENT** | Megana (reported), 22:57 UTC | Fits with the pump, leaves open water, and can be fixed in place. Token retention over the full horizon is not yet tested. |
| 11 | Three identical floating tokens (green bottle caps) | Float; one clean detection each (see the token-detection doc); only one used per run; all recovered | **PRESENT (green caps; needs new detector wired in)** | Megana + Claude, 23:13 UTC | Green bottle caps. The red-only tracker cannot see them, so a colour-independent empty-tank-reference detector was built (docs/foreground-token-detection.md). Recording cannot use it until Jose wires it into runtime.py. Caps must be identical, one per run. |
| 12 | Ruler or tape measure | Centimetre scale | UNCHECKED | | |
| 13 | Seven water-plane reference marks | At least 4 mapping marks and 3 **different** check marks at the water-surface height (not the bin floor) | UNCHECKED | | |
| 14 | Stable lighting, tray and towels, dry protected mains outlet, **plain light sheet under the clear bin** | Tracking stable under room or desk light; electronics dry; GFCI outlet; pump unplugged before touching wet parts | UNCHECKED | | |

Not used in this build: Arduino, ESP32-CAM, MIPI camera, relay, servo, motor
driver, breadboard power, decorative coral and 3D printing. The pump runs only on
its own cord, switched by hand.

## 2. Measured setup (centimetres, from one fixed origin)

Choose one bin corner as the origin, with x along the long wall and y along the
short wall. Measure on the **water surface**.

| Quantity | Value | Method / note |
| --- | --- | --- |
| Origin corner and axis directions | Bottom-right inside corner at the waterline = (0, 0). +x along the bottom long wall toward bottom-left; +y up the right short wall toward top-right. | Operator-reported, 2026-10-17. |
| Bin interior length × width × depth | Overall 41.3 × 28.6 × 17.1 cm (rim/outer, reported earlier). **At the waterline (inside): 14 in × 9 in = 35.56 × 22.86 cm.** | Operator-measured in inches and converted at 2.54 cm/in. Measured diagonal 16.5 in vs 16.64 in for a perfect rectangle (difference 0.14 in ≈ 0.36 cm): consistent and near-square. |
| Waterline height above the floor, and its tape mark | | |
| Pump minimum operating depth (from the manual) | | |
| Overflow margin above the waterline | | |
| Pump position (x, y) | | |
| Return outlet position (x, y) and direction | | Aim along a wall at the lowest stable setting. |
| Pump flow setting used | | |
| Camera height above the water and mount marks | | |
| Inlet regions A, B, C (polygon corners) | | |
| Permitted observation region (polygon) | | |
| Protected zone (polygon) | | A measured polygon, marked on the rig. |
| Collector: baseline position (polygon) | | |
| Collector: intervention position (polygon) | | |
| Mesh pocket (polygon) and retention test | | |
| Lighting arrangement | | |

Sketch, to be replaced with the measured version:

```text
 y ↑   (top view, cm, origin = chosen corner)
   ┌──────────────────────────────────────────────┐
   │ A[ ]                         protected zone  │
   │                [collector]   [          ]    │
   │ B[ ]   ~~ drift ~~>                          │
   │                                     outlet ⇐ │
   │ C[ ]          pump ▣                         │
   └──────────────────────────────────────────────┘ → x
   camera fixed overhead; laptop and mains kept dry, off to the side
```

## 3. Camera and mapping

Start the webcam yourself in the Camera view by entering its device index.
Nothing opens it automatically.

| Field | Value |
| --- | --- |
| Device index and backend shown in Status | C270 at USB device index 1 on this laptop (built-in and iPhone cameras are 0 and 2), AVFOUNDATION, 1280 × 720 |
| Camera session ID | `usb-71fc876dd8b54b73`. The app was restarted to load the sparkle fix, so the camera got a new session. Phase correlation showed the camera within about 3.4 px of the placement pose (earlier readings 3.2–5.1 px), so the same cap-placement points were resubmitted. |
| Frame size (px) | 1280 × 720 |
| Mapping marks used (count) and check marks (count, all different) | **Cap-placement method, no tape marks.** One green cap pushed against a straight wall, and its centre found by the empty-tank detector (pump off). Centre = cap radius (assumed 1.45 cm, typical 26/22 closure) from the wall, and the ruler distance along the wall. Fit (4): left wall 7 in, top wall 2 in from the top-right corner, right wall 4 in, bottom wall 7 in. Checks (3): left wall 4 in, right wall 7 in, top wall 2 in from the top-left corner. Small camera shifts (up to about 5 px) were measured by phase correlation and removed before locating the cap. |
| Declared check-point tolerance (cm, set before fitting) | **3.0 cm, set after seeing the placement data (disclosed).** It is the 95% bound from the 7-point fit's residual standard error. The team's original 0.5 cm cannot be met with this method. |
| Calibration ID | `cal-0145710e311bac07`, the current session's mapping (supersedes `cal-5f6b56f3ce6cae80` from the previous session; same placement data) |
| Approved? Max / mean check error (cm) | Approved under the 3.0 cm declared bound. Independent check errors 1.91, 2.24, 2.77 cm (mean 2.30, max 2.77). |

If the mapping is not approved, re-measure the marks. Do not raise the tolerance.

**Mapping accuracy, stated as a range.** 7 placements, homography with 6 degrees of freedom:
- residual standard error 1.17 cm per coordinate;
- typical position error about 1.5 cm;
- 95% bound about 2.9 cm;
- leave-one-out errors 0.8–3.3 cm, except the only bottom-wall point (6.4 cm, an extrapolation), so accuracy is weakest near the bottom wall.

Treat positions as **±1.5 cm typical, up to ±3 cm**. Source regions or zones closer together than about 3 cm cannot be distinguished reliably. This is a coarse mapping: good enough for the software demo, not precise metrology.

### Token detection (colour-independent, pump on)

| Field | Value |
| --- | --- |
| Detector | `foreground_reference_v1` (empty-tank reference; green bottle caps) |
| Empty-tank reference (pump on, lowest setting) | `ref-807c157d75211178-d8b54b73` |
| One-token size | 3219 px; recordings accept 1127–9656 px |
| Notes | Ripple sparkles with the pump on: median about 50 px, at most about 700 px; the cap is 4.5–7× larger. Stand back from the bin during captures and recordings: a body shadow once changed brightness by +24% and was refused. |

## 4. Drift recordings and profiles: one block per layout

Use one token per run. The training and validation runs must be separate
recordings, and the baseline and intervention layouts must not share any
recording. Declare the coverage radius, cell size and error limits from
development runs **before** fitting. Unsupported paths, gaps or high error are
evidence that the rig needs repair; they are never a reason to relax a gate.

### Layout: baseline

| Field | Value |
| --- | --- |
| Training recording IDs (≥2) | Attempt 1 (excluded): `recording-f7682c36f09048cc`, 15 s, pump at its lowest setting. The cap reached the mesh's lower edge within about 2.5 s and stayed there; 29/99 frames observed (gaps from occlusion by the mesh frame and black strap). Its 12 "drift" samples are positional jitter of a retained cap, so it was left out of training. A first attempt was discarded by the app because a hand was in view. |
| Validation recording IDs (≥1, separate) | |
| Declared coverage radius / cell size (cm) | |
| Flow ID and content hash | |
| Held-out RMSE (cm/s), supported coverage | |
| Recorded-vector inspection (`GET /flow/{flow_id}/vector-diagnostic`) | |
| Free-running-path inspection (`GET /flow/{flow_id}/trajectory-diagnostic`) | |
| Declared `max_validation_rmse_cm_s` / `revalidation_max_rmse_cm_s` | |
| Profile ID and content hash | |

Attempt 2 (excluded): `recording-c8f3f60b893a4b22`. Same outcome: every release ended under the black strap at the mesh edge within about one second, faster than the tracker's 20 cm/s association limit.

### Estimated rig model (SYNTHETIC: not a measurement)

Measured drift was not achievable on this rig (see attempts above), so the team
chose an explicitly labelled **estimate** for the demo. `scripts/load_estimated_rig.py`
builds it; `tests/unit/test_estimated_rig_model.py` checks its labels and path.

- **Inputs, observed:** waterline 35.56 × 22.86 cm; outlet at the left wall (≈34.2, 1.4–10.9 cm);
  mesh footprint ≈ x 8–24, y 11.5–22.86; ten cap positions along the mesh edge
  (x 15.9–22.1, y 12.7–13.6) from the two excluded recordings; ≈1 s outlet-to-mesh transit (operator).
  Positions carry the coarse mapping error (≈±1.5 cm typical, up to 3 cm).
- **Inputs, assumed:** the path continues to ≈(4.5, 18.5) without the mesh; jet speed 15 cm/s
  (range 8–25), jet half-width 1.5 cm; 2 cm/s return flow toward the pump; candidate sources
  A (outlet), B (upper left wall), C (bottom wall); protected zone x 2–7, y 15.5–21.5.
- **Gap filling:** a weighted least-squares quadratic y(x) = −0.0036x² − 0.2781x + 19.749
  through the outlet, the edge points and the assumed continuation, sampled every 0.75 cm.
- **Profiles:** `estimated-rig-baseline-v1` (no trap) and `estimated-rig-intervention-v1`
  (mesh as an absorbing trap), both `data_origin: SYNTHETIC` with `estimate_provenance`.
- **Offline result (simulated, not a trial):** the source estimate ranks A for an outlet-side
  path. In the comparison the mesh stops 92–99% of zone entries from A and B in all three
  dispersion scenarios. C never reaches the zone in either layout, so the engine reports
  `NO_ROBUST_RECOMMENDATION` (`MIXED_OR_ZERO_EFFECT`): every source must benefit.

These numbers come from the assumptions above. They are not tank accuracy and must not
be described as measured drift, a validated profile or a field receipt.

**Loaded into the local app (17 Oct 2026):** case `case-2f7ffada1e704c0f` (SYNTHETIC, shown as
"Demo"), comparison `prevention_comparison-3e16a619d2364420` ("Estimated rig model (not measured):
mesh vs no mesh"). Checked in the dashboard: source map and ranking, 2D layout maps, and the 3D tank
in both layouts. The dashboard draws x to the right and y downward, so the view is this frame
rotated 180° (the outlet side and A/B are on the right, and the pump corner is top-left). The geometry
is rotated, not mirrored.

**Circular by construction:** the case's "observation" is four points sampled from the same
estimated path that drives the model, so Source A's 100% support only shows that the pipeline runs
end to end. It is not evidence about where a real cap entered. Narrate it as an estimated path,
even though the dashboard's generic case title reads "Observed trajectory".

### Layout: intervention (collector moved to its measured marks)

Moving the collector changes the flow. Record the disturbance, then record new
drift for this layout.

| Field | Value |
| --- | --- |
| Training recording IDs (≥2) | |
| Validation recording IDs (≥1, separate) | |
| Declared coverage radius / cell size (cm) | |
| Flow ID and content hash | |
| Held-out RMSE (cm/s), supported coverage | |
| Recorded-vector inspection (`GET /flow/{flow_id}/vector-diagnostic`) | |
| Free-running-path inspection (`GET /flow/{flow_id}/trajectory-diagnostic`) | |
| Declared limits | |
| Profile ID and content hash | |

## 5. Disturbances, revalidation and field receipts

| Time (UTC) | Event (disturbance / revalidation / restore) | Profile | Recording / rig-check ID | Result |
| --- | --- | --- | --- | --- |
| | | | | |

| Layout | First LIVE case ID | Field manifest ID | Content hash | Capture origin | Status |
| --- | --- | --- | --- | --- | --- |
| baseline | | | | | not frozen |
| intervention | | | | | not frozen |

Freeze a receipt only when "Check all steps" reports READY. A receipt whose
capture origin is `SYNTHETIC_FAKE_CAPTURE` is never physical evidence.

## 6. Current blockers

1. **Token detection: working on the real C270** (reference and token size recorded above). Green caps are found by
   the colour-independent detector (`docs/foreground-token-detection.md`), now selectable
   in recording and in the field wizard (Jose approved the shared-file change, relayed by
   Megana). Still to do on the rig: put a plain light sheet under the clear bin, start the
   app, capture the empty tank with the pump running, and measure one cap.
2. **Inventory rows 12–14 not yet checked.**
3. **No measurements yet** (section 2). Mapping, drift, profiles and receipts depend on them.
4. **Second layout:** the intervention collector position must be declared and marked
   before its drift is recorded.
5. **Clamps not used** (operator decision): leak check at the barb and a fixed outlet
   position are still required.
