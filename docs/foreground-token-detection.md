# Colour-independent token detection (empty-tank reference)

**Status:** detector, tests and evaluation are done (`apps/vision/reeftrace_vision/foreground.py`).
It is **not yet used by recording**. That needs the small API/runtime change in
section 5, which belongs to Jose. Nothing in the existing red pipeline changed.

## 1. Why

The team's tokens are green bottle caps. The existing detector (`detect_red` in
`tracking.py`) only accepts two fixed red hue ranges, so green caps are never
recorded. An offline check confirms it: a synthetic red disc gives 1 detection,
green discs give 0. Recolouring the caps isn't possible, so the detector now
finds *whatever new object is on the water* instead of a colour.

## 2. How it works

1. **Empty-tank reference.** Capture 5–60 frames of the tank with **no token**,
   with the pump running, the lamp on and hands out of view. For each pixel it
   stores the usual appearance (median, in Lab colour) and its natural flicker
   (a robust spread). Capture is refused if:
   - the camera moved during capture, or
   - more than 10% of the view was "busy" (too much ripple or motion).
2. **One-token size check.** Put one cap in view; `measure_token_area` records its
   blob area. From then on only blobs of about that size count (0.35×–3× the
   measured area), so a hand or a fragment is rejected.
3. **Every frame.** It compares the frame with the reference after allowing for a
   small lamp or exposure drift (±20%; saturated glare stays saturated). A pixel
   is "object" only if its colour differs by more than six times its own normal
   flicker, and by at least 18 Lab units. Blobs of the right size are returned
   in the same format as `detect_red`.
4. **Gaps, not guesses.** `SingleTokenTracker` is unchanged: zero or several
   blobs are recorded as a gap.
5. **Scene checks.** It raises `SceneChanged` instead of reporting detections if:
   - the whole image shifted by more than 1.5 px (camera bumped),
   - brightness changed by more than 20% (lamp moved), or
   - more than 15% of the view changed.

   In each case, retake the reference, and after a camera move also retake the
   mapping.

It **locates an unexpected object; it does not recognise plastic.** In the
controlled tank the cap is the only moving object, so it serves as a stand-in for
floating debris. Recognising real plastic on coral would need a trained image
model, which is a separate project that hasn't been started.

## 3. What the operator must do at the rig

- **Put a plain, opaque, light sheet under the bin** (white poster board, or a
  towel folded flat). The bin is clear, and the patterned carpet under it shows
  through and shimmers with every ripple. In the evaluation, ripple of 3 px or
  more over that carpet made the reference refuse to form.
- **Fix the camera** in its overhead mount. Any bump means a new mapping and a new
  reference.
- **Turn the pump on** before capturing the reference, so ripples count as normal.
  Aim the return outlet along a wall at the lowest stable setting.
- **Keep everything else still and out of frame**: hands, loose tape ends, cables.
  The green mesh frame, black tape, tube and pump are fine because they're in the
  reference.
- **Use identical caps**, one per run.

## 4. Evaluation

These results are software evidence only, not tank accuracy.

**Unit tests** (`tests/unit/test_foreground_detection.py`): 23 passed, 1 skipped.
The skip is a deliberate duplicate of the limitation test. They use synthetic
images only: a textured greenish floor, a green mesh frame, black tape and a
saturated glare spot. They cover:
- green, dark-green, white and black caps in open water, on tape and on the mesh
- empty frames with fresh noise
- two caps becoming a tracker gap
- a hand-sized object being rejected
- ±10% lamp change, including the glare spot
- a large lamp change, a camera bump or a resized frame being refused
- a shaking reference capture being refused
- bad inputs, the one-token size check, and stable image-free provenance
- a moving cap forming one continuous track at the true speed (slope within 0.05 cm/s)

**Team's empty-tank photo.** This used the private phone photo of the real bin, with
the pump, tube, mesh and tape in place. It was scaled to 1280 × 720, and synthetic
noise, ripple and drawn caps were added. It was run locally and not committed. A
phone photo is not the C270's actual view, so this is a feasibility check only.

| Scenario | Result |
| --- | --- |
| Empty tank, 3 fresh noise + ripple frames | 0 detections each |
| Green and dark-green cap: open water over carpet, on green mesh frame, on black tape, near pump, by tube | 1 detection each, at the drawn position (within 1 px) |
| White cap | 1 detection |
| Two caps | 2 detections (tracker gap) |
| Hand at the edge | 0 detections, rejected by the measured token size |
| Lamp +10% | 0 detections |
| Lamp +35% | refused: brightness changed |
| Camera shifted 6 px | refused: "camera view moved by about 7.2 px" |
| Red detector on a green cap | 0 detections (the reason for this change) |

**Ripple sweep on the photo** (the reference was captured at the same ripple):
- 0.5, 1 and 2 px: **0 false detections** in 20 frames each.
- 3 px: the reference was refused because too much of the carpet pattern varied.
- 5 px: the reference was refused because of whole-image motion.

**Moving green cap** (photo background, 10 Hz, 3 cm/s for 4 s, synthetic mapping):
- **41/41 frames** observed as one track with no gaps.
- Position error: mean 0.011 cm, max 0.031 cm.
- A least-squares speed of **3.002 cm/s**.

The existing per-sample velocities (`flow_samples`, unchanged) averaged 2.87 cm/s,
because they divide 0.1–0.2 s moves and so amplify pixel rounding. That step is the
same for both detectors and wasn't modified here.

**Known limitations**
- A token that looks like what's under it (for example a black cap over black
  tape) is not seen, and is recorded as a gap. Green caps on a plain light sheet
  avoid this.
- Background subtraction is **not** a plastic classifier.
- Heavy ripple over a textured floor will be refused rather than tracked.
- It has not yet been run on real C270 frames.

## 5. Integration request for Jose (shared files; not changed here)

Only Jose edits `runtime.py`, `main.py`, the camera endpoints and `RecordInput`.
Proposed minimal wiring:

1. **`POST /api/v1/camera/reference`** (operator). Body: `{frame_count: 5–60,
   roi_polygon_px?}`. It captures fresh frames from the **current** session, builds
   `EmptyTankReference`, and stores a record `{reference_id, camera_session_id,
   image_size_px, describe()}`. The arrays (median, noise) go privately under
   `data/local`, never in API responses or Git. It is refused if the camera isn't
   fresh.
2. **`POST /api/v1/camera/token-size`** (operator). With one cap in view, it runs
   `measure_token_area` against a stored reference and saves
   `token_area_range(...)` with that reference.
3. **`RecordInput`**: add an optional `detector: "red_hsv" | "foreground_reference_v1"`
   (default `red_hsv`, so existing behaviour is unchanged) and `reference_id`.
   `CaseInput` is untouched.
4. **`Runtime.record`**: replace `detect_red(image)` with the chosen detector. For
   the foreground detector:
   - require a reference from the same camera session and image size, plus a
     measured token size;
   - treat `SceneChanged` as ending the recording, like the existing "camera
     restarted" error;
   - store `{detector, reference_id, token_area_px_range}` on the recording.
5. **Disturbance**: `POST /rig/disturbed` (or any revalidation) should also require
   a new reference.

After that lands, Megana adds two follow-ups in Lane 1 files:
- a "Capture empty-tank reference" and "Measure one token" step in the field wizard;
- a field-session check that every recording in a receipt shares one detector and
  one reference.
