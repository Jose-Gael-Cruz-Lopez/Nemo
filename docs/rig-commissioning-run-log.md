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
| Device index and backend shown in Status | |
| Camera session ID | |
| Frame size (px) | |
| Mapping marks used (count) and check marks (count, all different) | 4 inside waterline corners: (0,0), (35.56,0), (35.56,22.86), (0,22.86) cm. 3 tape check marks at the waterline: bottom-wall midpoint (17.78,0), top-wall midpoint (17.78,22.86), right-wall midpoint (0,11.43) cm |
| Declared check-point tolerance (cm, set before fitting) | |
| Calibration ID | |
| Approved? Max / mean check error (cm) | |

If the mapping is not approved, re-measure the marks. Do not raise the tolerance.

## 4. Drift recordings and profiles: one block per layout

Use one token per run. The training and validation runs must be separate
recordings, and the baseline and intervention layouts must not share any
recording. Declare the coverage radius, cell size and error limits from
development runs **before** fitting. Unsupported paths, gaps or high error are
evidence that the rig needs repair; they are never a reason to relax a gate.

### Layout: baseline

| Field | Value |
| --- | --- |
| Training recording IDs (≥2) | |
| Validation recording IDs (≥1, separate) | |
| Declared coverage radius / cell size (cm) | |
| Flow ID and content hash | |
| Held-out RMSE (cm/s), supported coverage | |
| Recorded-vector inspection (`GET /flow/{flow_id}/vector-diagnostic`) | |
| Free-running-path inspection (`GET /flow/{flow_id}/trajectory-diagnostic`) | |
| Declared `max_validation_rmse_cm_s` / `revalidation_max_rmse_cm_s` | |
| Profile ID and content hash | |

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

1. **Token detection: wired in, not yet tried on the real camera.** Green caps are found by
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
