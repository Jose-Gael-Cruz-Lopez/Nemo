# Surface detector and private saved-footage replay

The local Camera page can compare saved frames without a live camera, a new background capture, or another physical setup cycle. Connect operator access and choose **Replay saved camera footage**. Choose a clip and toggle accepted boxes, rejected objects, original candidates and the frozen tank outline. **Show last saved replay** reads the saved report without evaluating again.

## What changed

`foreground_surface_v2` is an explicit opt-in detector for one compact floating cap. The historical `foreground_reference_v1` remains unchanged and existing records keep their original detector identity.

Both versions use the same saved full-frame empty background, lighting/gain checks, camera-shift checks and foreground morphology. V2 filters complete foreground components afterwards:

- The component's entire bounding box must lie inside a declared convex water-surface pixel polygon. A rim component crossing the boundary is rejected whole, rather than cropped into a false cap.
- Aspect ratio must be at most 2; circularity `4πA/P²` at least 0.45; solidity `A/convex-hull-area` at least 0.75.
- The pixel-area check and fourfold dominance requirement for learning one token remain. Zero or multiple admitted objects produce gaps. Gaps reset association; no line joins missing observations.

These are frozen engineering heuristics (`compact_cap_v1`, content-hashed), not a trained plastic classifier or a guarantee to remove every reflection. Round, cap-sized reflections inside the domain can still be ambiguous. Rejection counts are per reason; one component can fail more than one check.

## Local contracts

`POST /api/v1/camera/reference/{reference_id}/surface` accepts `detection_polygon_px`. It derives a new immutable reference using the saved background, original session and capture timestamp; it does not access the camera or approve the historical calibration for today's pose. Live recording still checks the current session, dimensions, rig state and measured token area. Detector versions cannot be mixed in a measured field workflow.

`POST /api/v1/camera/detector-replay` accepts only `{}` and reads a server-prepared private `data_dir/detector_replay/manifest.json`. `GET` returns the latest saved report. Both routes require the local operator and are disabled in the hosted software profile. The browser cannot supply arbitrary file paths. The manifest pins private JPEG/background hashes, original camera sessions, frame dimensions, increasing original receipt timestamps and the unchanged historical mapping. Inputs have clip/frame/file/memory bounds; pickle and paths escaping private data are rejected.

Reports use `nemo_surface_replay_v1`, `LOCAL_SAVED_FOOTAGE_REPLAY`, `DEVELOPMENT_REGRESSION`, and `UNVALIDATED`. They preserve the manifest and policy hashes, decisions, gaps, rejection reasons and a representative original JPEG with overlays. They are stored separately from measured recordings and cannot train measured flow, create source cases, or freeze physical receipts. The replay does not access a camera, call Chalk or send Photon messages. Photon automatic replies are a separate, explicitly configured local worker.

## Development evidence, 18 October 2026

The existing private footage contains 36 frames from the original pump-off rehearsal and one saved frame with a cap near a wall reflection. V1 accepted 33/36 in the first clip (three multiple-object gaps), and could not learn a dominant cap in the reflection frame. V2 accepted one candidate in each of the 37 frames under the frozen policy. This is a reproducible development regression, not independent detection accuracy or evidence that measured flow/source tracing is valid. The current camera-to-water alignment remains approximate. The raw images, reference arrays, calibration bundle and private manifest are excluded from the public repository.

Synthetic automated tests additionally cover empty frames, multiple caps, elongated components, boundary components, lighting/camera changes, hash/path/session failures, authentication, and isolation from physical evidence. Physical movement and source validation require separate runs; this software fix does not manufacture them.
