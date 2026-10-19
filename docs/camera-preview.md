# Camera preview before the tank is ready

The connected **Logitech C270** was verified as **USB device 0 on this Mac**, delivering fresh **1280 × 720** frames. Device numbers can differ on another computer or after reconnecting hardware. The interface therefore labels the selected external USB device rather than assuming a C920s.

No tank, pump, calibration or token is needed to view the camera. Viewing the feed does not record a trial or establish a physical measurement.

## View the camera

1. Open the running local dashboard at `http://127.0.0.1:3000/workspace#camera`.
2. The **Live camera** panel comes first. If capture is already live, leave it running. Otherwise connect local operator access, select the external webcam's device index and choose **Start webcam**. On the verified Mac, the C270 is device **0**.
3. Toggle **Pixel guide (px)** to show or hide the image grid. Move over the picture to see a crosshair and native image coordinates. At 1280 × 720, valid pixel centres run from x = 0–1279 and y = 0–719; resizing the displayed image does not change those coordinates.
4. **Measured grid (cm)** stays disabled until an approved, matching water-surface calibration exists. The pixel grid is a positioning guide, not a ruler.
5. Choose **Close webcam** to end capture. Changing workspace pages disconnects the preview stream but does not itself close the camera. The preview uses the available width, keeps the full native aspect ratio without cropping, and places capture controls underneath.

The preview keeps one **continuous MJPEG connection** for each visible image, bound to the current camera session. It sends the latest available JPEG bytes at **no more than 15 fps**; it does not replace the image URL or rerender the workspace for every frame. Cursor updates are animation-frame throttled, and unchanged grid geometry is memoized. The closed commissioning section retains its draft but opens **no hidden preview stream**. Ordinary status checks remain three seconds apart.

The capture worker preserves the device's **native negotiated mode**. On this C270, forcing an unsupported 1920 × 1080 request caused failed frame reads even though the driver accepted the settings. Native 1280 × 720 delivered 49 new capture sequences over 2.011 seconds (about 24 fps in this check). Device-reported FPS can be misleading. Recorded tracking uses a separate sampling setting, **10 Hz by default**. Capture, preview and tracking rates are different. The preview cap does not define a recorded trajectory's time interval. A missing, stale or changed session ends the stream rather than silently switching cameras.

Actual start/stop/restart checks on 17 October 2026 produced fresh native frames in 0.635 and 0.637 seconds. Two twelve-frame HTTP samples delivered 14.69 and 14.63 fps with strictly increasing frame identities. These are bounded host-side checks, not guaranteed optical latency or proof of long-duration reliability; the tank calibration and physical trials remain unperformed.

The preview is available in the local application. The [public ocean showcase](public-ocean-showcase.md) has no connection to this computer's webcam, local experiment store or operator credential.

## Hosted app with private local frames

On the Render software demo, Camera uses the browser’s own preview rather than asking the remote server to open USB device 0. Select **Start preview**, allow camera access, and choose the external webcam. The full frame is unmirrored and uncropped. It requests no microphone, uploads no frames, and cannot create a calibration, reference or recording. **Close preview**, leaving Camera, or closing the page releases its tracks. A late permission response is also stopped after closure.

For the full pipeline, start the local companion with `PHOTON_ENABLED=false .venv/bin/python scripts/dev.py`, then choose **Open local camera workspace**. The link closes browser capture first and opens `http://127.0.0.1:3000/workspace#camera` without a token in the URL. Enter that laptop’s local operator token privately. Camera, OpenCV, background references, frame timing and recordings stay on that laptop. Hosted and local operator tokens/stores are separate; the link does not synchronize private evidence or configure network access. Stop any older Photon-enabled local server before starting the disabled one; the launcher reuses already-running services.

The cloud API continues to reject physical capture/calibration routes. Preview is distinct from token detection: it cannot establish a distance, flow or source. Reference capture, token-size measurement and recording are mutually exclusive. The two-reference memory cache reloads older private NPZ references with the existing integrity check rather than deleting their evidence.

### Reuse the measurements already taken

Megana’s [commissioning log](rig-commissioning-run-log.md) contains an actual 14 × 9 inch inside waterline (35.56 × 22.86 cm), real cap-size captures, camera-session/calibration/reference IDs and the coarse mapping error. Do not remeasure that unchanged container merely to show the software. However, its camera mapping and background references belong to the recorded camera pose/session and private laptop store. Do not copy their IDs into another laptop’s draft as if the underlying records, pixels and camera pose had transferred. The current log also records excluded drift attempts and an estimated SYNTHETIC rig model; it does not establish an admitted measured flow or physical source-identification accuracy.

## Coordinates when the tank is ready

Expand **Calibrate a tank and record trials when ready** below the live preview. The draft and selected camera session remain available while that section is collapsed. The separate raw JSON setup tools remain below it for advanced use.

- Keep the camera fixed, dry and above the whole water surface. Choose one fixed water-surface corner as `(0, 0)`, with +x to the right and +y away from the operator; use that convention consistently. Image pixels instead have their origin at the image's top-left and +y downward.
- Measure at the **actual water surface**, not the tank bottom. Supply at least **four spread-out mapping marks** with measured coordinates and **three separate, noncollinear check marks** that were not used to fit the map. Select the unit actually measured; the wizard explicitly converts millimetres or inches to centimetres.
- Declare a check-point error tolerance before fitting; the existing default is **0.5 cm**. Click the surveyed marks to append their native pixel positions, enter the matching measured coordinates, and select **Fit and validate mapping**. A saved but unapproved mapping cannot enable recording.
- An approved mapping must match the current camera session and image dimensions and identify the plane as `measured_water_surface`, with units `cm`. Its finite, invertible homography maps image pixels to the measured plane. Camera movement, resolution changes or a changed water plane require a new mapping.

The centimetre grid is projected through that mapping and clipped to the convex hull of its frozen fitting marks. No centimetre cursor readout is shown outside that hull. Grid spacing is a display setting, not measurement accuracy or the flow model's cell size. Independent check-point error remains the mapping quality check. Legacy drafts without the saved mapping matrix remain readable but cannot display a centimetre grid until mapped again.

## Physics starts with measured motion

For calibrated positions in centimetres and elapsed time in seconds:

```text
vx = (x2 − x1) / Δt     cm/s
vy = (y2 − y1) / Δt     cm/s
speed = sqrt(vx² + vy²) cm/s
```

The software uses recorded frame receipt timestamps; these are not independently measured camera exposure times. One visible red token is tracked at a time. Missing or multiple detections create gaps; the software does not bridge them into invented motion. Pump GPH is not converted into a local token speed.

Actual water-plane measurements, calibrated drift recordings, held-out flow/path error, source trials and interception outcomes are **still required**. They have not been produced by activating this preview. NOAA/PacIOOS ocean trajectories and the illustrative ocean layout comparison remain separate from these future centimetre-scale tank measurements.

## Marker-assisted registration (dry development)

See [the setup, frozen thresholds and real-rig checklist](tank-marker-registration.md)
for optional ArUco proposals, independent checks and stale-map gates. The manual
workflow remains available; no physical accuracy or unchanged flow is certified
by the synthetic demonstration at `/registration-demo`.
