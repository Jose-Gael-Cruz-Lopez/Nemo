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
| Base `main` (CI green) | `e39b64ca4443820a8f2b9302f60ca7dc1b4da587` |
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
| 2 | External USB webcam (C920s or equivalent) | macOS lists it; OpenCV opens it at an explicit device index; the full bin is sharp in frame | **NOT DETECTED** | Claude, 14:47 UTC | `system_profiler` listed only the built-in FaceTime camera and an iPhone Continuity Camera. Neither is the rig camera. Plug in the webcam and recheck. |
| 3 | Webcam data cable and host adapter | Carries data, not charge only; matches the laptop's ports | UNCHECKED | | |
| 4 | Rigid overhead mount | Clamp, tripod or support holding the whole bin in view; no hand-held camera; cable secured | UNCHECKED | | |
| 5 | Pond Boss 80 GPH corded pump | Model label and manual read privately; cord intact; operating water depth noted; low-flow setting located | UNCHECKED | | Record the model and minimum depth only. No photos in Git. |
| 6 | Pump's supplied outlet barb (3/8-inch) | The supplied adapter is in hand and matches 3/8-inch ID tube | UNCHECKED | | Resolve any mismatch before buying tube. |
| 7 | About 3 ft of clear vinyl tube, 3/8-inch **inside** diameter | Push-fits the supplied barb with no forcing | UNCHECKED | | Buy or cut only after row 6 is PRESENT. |
| 8 | Two small hose clamps, plus ties for the outlet | Seal the barb; fix the return outlet outside the tracked region | UNCHECKED | | Tape alone is not a seal. |
| 9 | Watertight bin (Sterilite 6 qt or larger) | Interior measured; pump submerged at a stable waterline with overflow margin; collector fits | UNCHECKED | | 6 qt capacity does not guarantee depth or clearance. |
| 10 | Mesh pocket (Top Fin breeder or a smaller secured pocket cut from its mesh) | Fits with clearance; holds a token for the full declared horizon | UNCHECKED | | Validate retention before treating it as absorbing. |
| 11 | Three identical red floating tokens | Float; one clean red detection each; only one used per run; all recovered | UNCHECKED | | No red coral or other red objects in the scene. |
| 12 | Ruler or tape measure | Centimetre scale | UNCHECKED | | |
| 13 | Seven water-plane reference marks | At least 4 mapping marks and 3 **different** check marks at the water-surface height (not the bin floor) | UNCHECKED | | |
| 14 | Stable lighting, tray and towels, dry protected mains outlet | Tracking stable under room or desk light; electronics dry; GFCI outlet; pump unplugged before touching wet parts | UNCHECKED | | |

Not used in this build: Arduino, ESP32-CAM, MIPI camera, relay, servo, motor
driver, breadboard power, decorative coral and 3D printing. The pump runs only on
its own cord, switched by hand.

## 2. Measured setup (centimetres, from one fixed origin)

Choose one bin corner as the origin, with x along the long wall and y along the
short wall. Measure on the **water surface**.

| Quantity | Value | Method / note |
| --- | --- | --- |
| Origin corner and axis directions | | |
| Bin interior length × width × depth | | |
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
| Mapping marks used (count) and check marks (count, all different) | |
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

1. **External USB webcam not detected** (14:47 UTC): no camera session can start.
2. **Inventory rows 1 and 3–14 are unchecked.** The barb and tube fit (rows 6–7)
   and the bin, pump and mesh clearance (rows 9–10) gate any wet work.
3. **No measurements yet** (section 2). Mapping, drift, profiles and receipts
   depend on them.
4. **Second layout:** the intervention collector position must be declared and
   marked before its drift is recorded.
