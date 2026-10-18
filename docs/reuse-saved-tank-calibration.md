# Reuse Megana’s measurements and run the first measured trial

Nemo can reuse the saved water-surface mapping after checking its alignment in the
current camera view. **Do not repeat the ruler survey merely because the app was
restarted.** A saved homography maps image pixels to centimetres; it does not prove
that a moved camera, changed water height or new lens view still has that mapping.

The measurement record is [the commissioning run log](rig-commissioning-run-log.md):

- Inside waterline: **35.56 × 22.86 cm** (14 × 9 inches).
- Origin: bottom-right inside waterline corner, on the pump side. **+x goes left
  along the long wall; +y goes up the short wall.** Preserve this frame when
  entering saved coordinates. The dashboard’s screen axes can look rotated.
- Latest documented original mapping: `cal-6b43410427d216c0`, camera session
  `usb-fd9569862c674058`, image **1280 × 720**. Earlier mapping:
  `cal-0145710e311bac07`.
- Original independent errors: **1.91, 2.24 and 2.77 cm** (mean 2.30 cm). The
  **3.0 cm** tolerance was chosen after inspecting placement data; that limitation
  remains disclosed. Position error is about **1.5 cm typical, up to 3 cm**,
  with weaker accuracy near the bottom wall. Do not describe this as a precision
  calibration or increase the tolerance to make a new check pass.

These dimensions are in Git. The original private calibration records, references
and images were intentionally excluded from Git and were **not found in the
project’s local stores during the bounded search**. The team has since supplied a
private **rig handoff folder** containing the seven historical placements and
their image-derived reference. That is enough to reconstruct the historical
mapping without repeating the ruler survey. A deployed commit does not carry
Megana’s private capture database. The estimated-rig script generates synthetic
flow; it is not a substitute for calibration or measured drift.

## 1. Prepare the supplied handoff, without opening a camera

Keep the team’s `reeftrace-rig-handoff` folder outside Git. From the repository
root, run the trusted repository helper against that folder:

```sh
mkdir -p data/local/rig-handoff
.venv/bin/python scripts/prepare_tank_handoff.py \
  --directory "/path/to/reeftrace-rig-handoff" \
  --output data/local/rig-handoff/saved-calibration.json
```

This verifies `placement_reference.npz` against `placement_reference_id.txt` using
the existing reference-integrity code, checks the bounded `placements.json`
schema, and fits the original four fit points against the original three checks
at the unchanged **3.0 cm** limit. It executes **none** of the Python files supplied
in the handoff and never opens a camera, calls an API or loads credentials.

It creates two private mode-0600 metadata files, refusing to overwrite either:

- `saved-calibration.json`: the source mapping for **Open saved mapping JSON**.
  Its session label begins `reference-pose-`, explicitly identifying a historical
  pose rather than the current webcam session. Its new content-derived ID is
  expected; it is reconstructed from the original, unshifted placements.
- `saved-calibration.measurements.json`: the existing fit/check centimetre
  positions and historical pixels for reference, plus provenance hashes. Use the
  saved centimetre positions for the new alignment checks below. Do not copy the
  old pixels and call them current observations.

The supplied real placements replay approximately **2.30 cm mean / 2.77 cm max**
historical check error. This is a historical replay, **not proof that today’s
camera view passes**. The handoff’s original `reuse_mapping.py` translates both
its old fitting and old check pixels by the same estimated shift. That preserves
the old residuals but does not provide independent current-view validation.
Nemo instead holds the reconstructed matrix fixed and requires fresh current
check pixels at the already surveyed centimetre positions.

No reference arrays or raw images enter the exported metadata files or the hosted
app. Keep both outputs and the original handoff private.

### Alternative: export the original stored calibration

On **Megana’s original capture laptop**, update the repository so this export
utility is available. It needs only Python’s standard library, not a running
server, webcam or API key. From the repository root:

```sh
python3 scripts/export_tank_calibration.py --list
```

This lists at most 100 calibration summaries: ID, image size, camera session,
approval, check errors and content-integrity status. If her capture database is
elsewhere, pass `--database /absolute/path/to/reeftrace.sqlite3`.

Choose the latest intact mapping from her real rig, then export it:

```sh
python3 scripts/export_tank_calibration.py \
  --calibration-id cal-6b43410427d216c0 \
  --output /tmp/nemo-saved-calibration.json
```

The file has schema `nemo_saved_calibration_v1` and contains that immutable
calibration record plus automatically preserved `calibration_json` metadata. This
serialized copy retains Python’s original numeric types when a browser forwards
the file, so values such as `1.0` keep their original content-derived ID. Do not
edit either copy. The utility opens SQLite read-only, checks the ID, writes a
private mode-0600 file and refuses to overwrite an existing file.
It exports no frames, background NPZ, messages, settings or credentials. Transfer
this JSON privately to the capture Mac; keep it outside Git. Also bring her notes
for the existing surveyed water-plane check positions, so their centimetre
coordinates can be reused. A calibration ID alone cannot recover the matrix.

If the original laptop has no saved record, use the supplied seven-placement
handoff above or recover a private backup. An ID, dimensions and error summary
alone cannot reconstruct a homography.

## 2. Use the local capture workspace

In the hosted Camera page, use the local experiment companion. Browser preview
must close before the local OpenCV service opens the same webcam. Frames and
recordings stay on the capture Mac; Render does not process or store them.

Start the local application with Photon disabled:

```sh
PHOTON_ENABLED=false .venv/bin/python scripts/dev.py
```

Open `http://127.0.0.1:3000/workspace#camera` and connect the **local** operator token
privately. A hosted operator token is separate. Confirm the local status reports
Photon replies and worker off before proceeding. If an older local service is
already running, setting a shell variable does not change that process; stop that
owned service first and restart it with Photon off.

Select the C270 by its actual local device index and check that the preview shows
the whole tray. The documented index was **1 on Megana’s laptop**; it is not a
portable camera identity. Match the saved **1280 × 720** image size. Keep the
camera fixed, the measured waterline unchanged and the view unmirrored.

## 3. Check alignment using existing centimetre positions

1. Open **Calibrate a tank and record trials when ready → Map the water surface**.
2. **Use Megana’s recorded tray measurements** fills the known tray bounds only.
   This is not a calibration approval.
3. In **Reuse saved measurements**, choose **Find saved mappings on this Mac**
   if using Megana’s original local store, or **Open saved mapping JSON** for the
   private export.
4. Choose **Saved mapping check pixels** in the preview. Click at least three
   distinct, well-spread, non-collinear current check positions. Enter their
   existing surveyed centimetre coordinates from Megana’s notes. Use the physical
   water-surface plane. Do not click arbitrary rim corners and call them measured
   waterline points. Her original cap-centre method used an assumed 1.45 cm radius;
   preserve that disclosure if reusing those positions.
5. Confirm the water plane is unchanged, then press **Check alignment, then use
   mapping**. The backend `POST /api/v1/vision/calibrations/revalidate` keeps the
   old matrix fixed and checks it against these fresh positions. It creates a new,
   content-addressed report bound to the current session; approval requires the
   checks to pass. The old record is not overwritten.

This checks camera registration, not the ruler distances again. It must not refit
the matrix to the same fresh checks and then claim they independently passed.
If the camera moved enough to fail, use new pixel locations with the **existing
surveyed world coordinates** to refit the mapping, retaining separate check points.
If the water plane, tray or marks themselves changed, the affected world positions
need verification. Do not widen the original tolerance.

Use **Export this mapping** to preserve the new report privately. The measured
grid should appear only for an approved mapping matching this session and image
size; a pixel guide alone is not a centimetre grid.

## 4. Renew image references without remeasuring the cap

An empty-tank background and token pixel area depend on the current camera pose,
lighting, water and pump state. They are not the cap’s ruler dimensions.

1. Prepare the intended wet layout and steady pump setting; the operator switches
   the pump manually. Keep its outlet, waterline, camera and lighting fixed.
2. With no cap or hands in view, press **Capture empty tank**.
3. Place **one** of the same green caps clearly in free water. Keep hands and
   shadows out, then press **Measure one token**. This measures image area, not a
   new physical cap diameter. Do not copy the old 3405 px area into a moved view.
4. Confirm one cap produces one detection. Empty water should not produce cap
   detections. Fix glare, shadows or occlusion before recording. A scene-change
   refusal is a reason to repair the setup and renew its reference, not bypass it.

The old pump-on reference `ref-7805b2034e319a02-2c674058` belongs to its original
camera session. Merely typing its ID on another laptop cannot recreate it.

## 5. Record a real drift trial, then a source observation

The previous recordings `recording-f7682c36f09048cc` and
`recording-c8f3f60b893a4b22` were excluded: caps hit the mesh strap almost
immediately, became occluded or were retained. Jitter of a trapped cap is not a
free-water velocity measurement. The first attempt also exposed motion faster
than the tracker’s 20 cm/s association limit.

For **each layout**, complete this sequence in the local field workflow:

1. Establish a visible, free-floating cap path through the region you will later
   observe. Adjust physical placement or the pump’s manual setting during
   development if necessary, then record the final setting. Removing or moving
   the mesh changes the layout and requires its own flow recordings.
2. Before the validation result is seen, declare cell size, coverage radius,
   maximum validation RMSE and revalidation RMSE limits. Keep those limits fixed.
3. Record **at least two training runs and one different validation run**, using
   one cap per run. Do not reuse a recording or its frames across those sets or
   across baseline/intervention layouts. Recover caps by hand between runs.
4. Fit measured flow through `POST /api/v1/flow/fit-recordings`. Inspect the vectors
   and free-running paths. Profile admission requires **at least 90% held-out
   supported coverage** and RMSE within the limits declared before fitting. If
   coverage fails, gather the missing training coverage; do not enlarge the
   radius after seeing the validation result.
5. Admit the measured profile. If the setup was disturbed, restore it and use
   `POST /api/v1/rig/revalidate` with a new drift recording after the disturbance.
6. Record a **new source observation** from that admitted profile. Keep its actual
   release source in the evaluator’s notes; do not feed it into inference. Compute
   source support and compare the ranked result with the separately recorded
   release. A live preview and the estimated-rig synthetic case are not this trial.
7. Run the field preflight and freeze a receipt only when every required step
   reports **READY**. Log the IDs, detector/reference, mapping, flow/profile hashes,
   withheld source answer, source result and failures. Keep raw frames local.

Source support ranks the declared candidate sources under the measured model; it
is not a universal geographic-origin guarantee. A retained endpoint can be
unidentifiable. Preserve **Unknown** or a failed validation when that is what the
evidence supports. Chalk explains the resulting evidence and limitations; it does
not certify the tank or replace measured flow.

Only after baseline and intervention each have independent valid profiles should
you compare prevention layouts and log independent measured trial outcomes against
their predictions. This guide and the software tests make no claim that a physical
trial has passed. Photon replies remain off throughout.
