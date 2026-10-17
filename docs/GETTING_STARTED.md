# ReefTrace v3: source tracing first

This guide follows the updated 66-page **Build Manual 3.0**, October 16, 2026. The repository copy of `ReefTrace_Final_Plan.pdf` is updated. The previous bench instructions remain in `docs/LEGACY_BENCH.md` for your existing Uno/sensor kit.

## What changed

- The core sensor is the fixed USB webcam. Camera → measured flow → one forward ensemble engine → trajectory or retained-endpoint evidence → source support / Unknown.
- Keep a recorded moving history when the token later stops. First-seen retained cases use only endpoint/verified-trap evidence.
- Submerged artificial coral is scenery, not an assumed surface obstacle or absorbing trap. Build and map a real mesh pocket touching the waterline.
- Manual net recovery is the complete baseline. No gantry is required. Optional peristaltic control samples water; the small tube is not a vacuum for 8–10 mm plastic tokens.
- Gemini powers bounded investigation; Photon 2.0 provides the optional phone interface. Source arithmetic remains in Python.

## Physical assembly with the planned materials

| ID | Planned part | Connection / role |
| --- | --- | --- |
| H01–02 | Clear tank, artificial coral | Measure actual inside geometry. Coral remains submerged scenery. |
| H03–04 | Logitech C920s and NEEWER overhead support | Camera USB-A **data** to laptop; clamp support to desk. |
| H05 | Two NEEWER BP66 lights | Each panel to its own rated 5V/2A supply. |
| H06–08 | Lifegard DC132, third 5V/2A supply, fixed return hose | Pump independent of laptop/Arduino; fixed flooded outlet. |
| H09 | Optional Anker USB-C hub | Only if needed for camera/controller data connections. |
| H10–12 | Waterline mesh pocket, standard floating tokens, net | Measure trap geometry and prove retention; recover/count every token. |
| Existing Unos | Your ELEGOO boards | Reuse one for optional sampler; second is spare. |
| Existing ESP32/ESP8266, servos and sensors | Separate optional bench work | Not required for source tracing. Leave unidentified modules disconnected. |

The manual starts near **12 cm water depth** for the selected pump; verify actual flooding and intake clearance. Mark the waterline, use gentle water-surface releases, secure the submerged return, and run the supervised stability check from the manual. Do not join the independent 5V supplies. Keep computer, supplies and exposed electronics dry and outside the splash region.

Planned equipment is not assumed delivered or tested. Prices and stock in the PDF are snapshots, not verified purchase recommendations here.

## Local startup now

Prefer Python 3.12 and Node 20+ on the eventual ASUS machine. This checkout was verified on the current Mac; ASUS details are placeholders in `config/asus.example.json`.

macOS/Linux, repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,photon]'
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Paste the generated secret into `REEFTRACE_LOCAL_TOKEN` in `.env`. Keep `.env` private. The API loads it automatically; no frontend environment variable should contain this secret.

```sh
python scripts/seed_demo.py --scenario moving
python scripts/seed_demo.py --scenario stationary
python scripts/seed_demo.py --scenario unknown
python -m uvicorn apps.api.reeftrace_api.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Second terminal:

```sh
cd dashboard
npm ci
npm run dev
```

Open http://localhost:3000, enter the local token in the investigation panel and click **Load cases**. All seeded cases are SYNTHETIC. They exercise software; they do not establish tank accuracy. The separate bench console still supports Uno telemetry and quick demos.

Docs: http://127.0.0.1:8000/docs. Click **Authorize** is not configured in Swagger; supply the `authorization` header field as `Bearer YOUR_TOKEN` on protected operations. Mutations and case/evidence access under `/v1` require the token. Health and synthetic demo endpoints are available without it. Bind to localhost and use one worker. Startup invalidates pending approvals and requires another rig check.

## ASUS / Windows placeholders

In PowerShell from the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,photon]"
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
# Set REEFTRACE_LOCAL_TOKEN in .env before continuing.
.\.venv\Scripts\python.exe scripts\seed_demo.py --scenario moving
.\.venv\Scripts\python.exe -m uvicorn apps.api.reeftrace_api.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Use a second PowerShell for `cd dashboard`, `npm ci`, `npm run dev`. Direct venv Python commands avoid changing PowerShell execution policy. Confirm actual ASUS model/OS and set `REEFTRACE_COMPUTER_MODEL`, `REEFTRACE_COMPUTER_OS`, camera index, and optional Uno COM port. Try OpenCV `--backend dshow` or `--backend msmf` after confirming camera permission in Windows settings. No GPU, CUDA, extra computer or Raspberry Pi is required by this implementation. Do not copy the Mac `.venv` or `node_modules` to Windows; reinstall there.

## Water-plane camera calibration

1. Fix the camera/mount and capture resolution. Request 1920×1080, then verify actual returned dimensions. Disable autofocus/exposure drift where the actual driver permits; the code does not certify those controls are locked.
2. Copy `config/water_plane_references.example.json` to a local file. Replace **every illustrative coordinate**, calibration ID and capture size with measured references at water-surface height. Include at least three independent check points not used in fitting.
3. Fit and inspect mapping errors:

```sh
python scripts/calibrate_camera.py --references config/references.local.json --output config/camera.local.json
```

The saved mean/max errors are measurements, not an automatic pass. Set acceptable errors on development data relative to path separation/trap size. Recalibrate after mount, waterline, resolution or geometry changes.

## Measured flow and physical profile

Copy `config/site.example.json` to `config/site.local.json`. It contains **placeholder geometry, zero coverage, and unverified retention**; it intentionally cannot produce a valid real source result. Replace inside dimensions, source polygons, actual waterline surface trap, token class, fixed pump setting and a downstream observation polygon that hides release locations. Do not map submerged coral footprints as surface barriers.

Record distributed flow-marker sequences (the manual suggests five 30–60 second recordings):

```sh
python scripts/track_camera.py --site config/site.local.json --calibration config/camera.local.json --purpose flow_measurement --seconds 45 --output data/runs/markers-1.json
python scripts/build_flow.py --site config/site.local.json --tracks data/runs/markers-1.json data/runs/markers-2.json --output config/measured-flow.local.json
```

Use all actual recordings. The builder uses median timestamped displacement and saves cell sample count/dispersion. It skips marked gaps, low quality and `collision: true` points. Review and flag collisions in flow recordings before fitting. Sparse cells remain unsupported. Runtime uses piecewise-constant cells, not interpolation across walls or unsupported gaps. Defaults and sampling thresholds need development validation.

Prove actual trap retention before setting `retention_verified: true`. After independent camera, drift/material and geometry checks, make a new frozen calibration ID/profile with `validity: "validated"`. This is an operator declaration; software cannot validate a physical setup from a JSON flag.

Register the profile using authenticated `POST /v1/profiles` with the JSON profile body. IDs are immutable; changing geometry/flow needs a new ID. Call `POST /v1/rig/check` with the calibration ID and all four check fields true **after actually checking waterline, camera mapping, pump/geometry and recovered flow**. API schemas are in `/docs`. Any intervention requires a recovery check; `POST /v1/rig/invalidate` stops pending manual tasks and prevents new live attribution under an unchecked rig.

## Actual observations and source inference

Trajectory recording (same frozen profile and calibration IDs):

```sh
python scripts/track_camera.py --site config/measured-flow.local.json --calibration config/camera.local.json --seconds 15 --start-after-s 3 --live-submit
```

The masked downstream recording excludes the first three seconds. Choose the mask/delay during development so release location is genuinely hidden. A fixed delay by itself is not proof of isolation. `--raw-video data/evaluator/raw-trial-1.avi` optionally archives full frames for the independent truth keeper; that archive is never submitted to the estimator.

First-seen-retained recording:

```sh
python scripts/track_camera.py --site config/measured-flow.local.json --calibration config/camera.local.json --seconds 5 --evidence-mode retained_endpoint --retained-trap surface-pocket-1 --live-submit
```

Start this recording only after retention. It exports an endpoint, not an earlier path. For an object you observed moving before it stuck, keep trajectory mode. Recording exports original pixels, real timestamps, frame references, actual camera properties and explicit misses. Segmentation supports one high-saturation green token by default; adjust hue bounds on development data. One blob does not prove identity across an occlusion; long gaps force Unknown. `--live-submit` requires an actual camera capture and posts the resulting case to `/v1/cases`. Recorded JSON can also be imported as a `CaseInput`, excluding recorder-only metadata; label it `recorded`.

The model uses seeded forward diffusion ensembles, explicit source priors, an age window, absolute fit, relative margin, coverage and named age-sensitivity gates. Retained-endpoint likelihood counts particles still retained at observation age, not earlier pass-through. Source support is conditional relative support, **not probability**. The simulator is a coarse drift approximation with absorbing verified traps; release/resuspension physics and general ocean attribution are unsupported.

## Evidence, investigation and manual recovery

SQLite in `data/runs/reeftrace.sqlite3` holds immutable profiles, cases, estimates, sensitivity outputs, agent traces, manual proposals and messaging state. Raw final-test truth stays in `data/evaluator/`, outside the API/tool interface. Back up DB and calibration artifacts before transport.

- `GET /v1/cases/{id}/evidence` retrieves the authoritative report.
- `POST /v1/cases/{id}/sensitivity` accepts only `age_short_v1` or `age_wide_v1`.
- `POST /v1/cases/{id}/observe` queues a fixed 3-second recording request. **It does not open the camera automatically or claim new evidence.** Run the recorder and create a new case; current capture uses an explicit CLI process.
- `POST /v1/cases/{id}/investigate` runs the shared configured AI tool loop if configured. No canned response is presented as live agent reasoning.
- Manual proposals bind operator, conversation, evidence ID, calibration, expiry and body hash. Approval is atomic and creates one logical human task. It requires a live observation under 15 seconds old and a checked rig. Synthetic/replay cases cannot authorize a physical task.
- Confirm actual recovery with `/v1/recovery-evidence` (action ID, frame reference and human statement), then `/v1/actions/{id}/outcome`. Camera disappearance alone is not proof. Confirmation switches the rig to RECOVERING; check it before another attribution trial.

Camera frame IDs reference masked images saved in `data/runs/frames/` and retrievable through authenticated `/v1/frames/{frame_id}`. Endpoint-only recording saves only its final permitted frame. Recovery references identify externally saved images; the API does not certify that an operator-supplied recovery reference depicts a recovered token. Use independent physical checks. There is no automatic recovery verifier or integrated continuous camera feed.

## Gemini, Neon and Photon provisioning

See [the current integration guide](integrations.md) for direct Gemini inference,
Neon/Supabase database selection and the current workspace API. Set
`GEMINI_API_KEY`, `GEMINI_MODEL` and `DATABASE_URL` in ignored `.env`.
`python -m scripts.check_gemini --test` verifies a small model response;
`python -m scripts.check_database` verifies workspace storage.
The older `/v1` API remains available and can explicitly select Butterbase,
but new workspace and Photon investigations use Gemini.

## Optional water sampler

Use your existing Uno instead of purchasing another. Open `firmware/sampler/sampler.ino`; **do not upload the bench and sampler sketches together**. D9 is sampler driver IN in this sketch, not a servo signal. Wire the delivered Adafruit 5648 driver/pump/fused external 12V supply exactly as manual pages 13–15 specify; check polarity with a meter. Driver ground and Uno ground join; external +12V never goes to Uno logic pins. Keep an accessible physical motor-power switch. D2 is a normally-closed local enable contact to GND; open disables.

The sketch defaults `ENABLE_SAMPLER 0`. After circuit/stop testing, enable locally, upload and test unloaded/with clean water. It starts unarmed/off, caps a pulse at 5000 ms, times out without heartbeat, rejects repeated IDs within its 16-command boot session, and reports switched duration. It never reports delivered volume or plastic capture.

```sh
python -m apps.hardware.reeftrace_hardware.sampler --port COM_REPLACE --milliseconds 1000 --circuit-tested
```

On Mac use the actual `/dev/cu...` port. This is an **explicit local circuit test that can energize the pump** when firmware is enabled and locally armed. It is not connected to agent collection approvals. Missing completion acknowledgement becomes UNCERTAIN without automatic retry. Calibrate delivered sample volume separately using a graduated cup. Firmware has not been compiled/flashed or tested on the physical Uno in this session.

## Validation and remaining work

```sh
pytest -q
ruff check apps scripts tests eval
cd dashboard
npm run lint
npm run build
```

`data/replay/agent.synthetic.jsonl` contains synthetic protocol fixtures only. With real Gemini configuration, `python -m eval.run_replay data/replay/agent.synthetic.jsonl` runs the shared investigator against fixture-only tools and saves every row/failure. No camera or hardware dispatch exists in that backend. Expected answers stay outside model context. Evaluation runs locally against fixture-only tools while model requests use Gemini. Results and row failures are saved locally; no managed evaluation deployment is required or claimed.

For scientific metrics, an evaluator-only JSONL uses `run_id`, `actual`, `predicted`, `evidence_mode`, `mode`, `split: "test"`. Run `python -m eval.metrics data/evaluator/frozen-trials.jsonl`. It reports answered/all, correct/answered, correct/all, wrong and Unknown separately, with per-mode counts. It rejects synthetic records and duplicate run IDs. No physical trials have been run or accuracy figures invented. Nearest-source and upstream-direction baselines are saved with estimator reports using the same permitted observations. Collect larger held-out datasets and compare their actual performance separately.

Current dashboard dependencies retain the previously reported npm advisories; a framework upgrade is a separate unresolved task. Keep the prototype local. The source pipeline still requires measured profiles, retention tests, held-out trials, a Gemini key/model, Photon setup and ASUS-specific verification. The optional sampling action remains deliberately outside the agent and API actuation path.

## Next steps with the currently confirmed equipment

Your confirmed electronics inventory supports the Uno dry bench now. The webcam,
lights, tank, pump and surface trap are planned; confirm arrival before following
the wet-tank stages. Existing dataset imports are cached research material and do
not require another download to start the application.

1. Generate a local token with `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   and set `REEFTRACE_LOCAL_TOKEN` in your existing `.env`. Start the existing API
   and dashboard using the commands above. Preserve your current `.env`; do not
   copy `.env.example` over it. Enter the local operator
   token in the dashboard and inspect synthetic cases and the Dataset library.
2. Use one Uno, HC-SR04, slider, breadboard and USB cable for the dry bench described
   in LEGACY_BENCH.md. Leave unidentified modules, the speaker, ESP boards and servo
   power disconnected until identified or powered appropriately.
3. Upload the default-off bench sketch, verify JSON at 115200 baud, close Serial
   Monitor and run the read-only USB bridge using the actual listed serial port.
4. Once the core kit is available, mount the camera and lights, fix the pump and
   marked waterline, install a real waterline-contact mesh trap, and gently mark
   A/B/C source locations. Recover all test tokens manually with the net.
5. Measure actual water-plane camera references and independent check points;
   replace every illustrative coordinate before fitting the homography.
6. Record distributed flow markers, review collisions/misses and build the coarse
   flow profile. Sparse cells stay unsupported. Demonstrate trap retention and
   validate token drift before declaring a frozen profile validated.
7. Register the frozen profile via POST /v1/profiles, complete POST /v1/rig/check
   after actual checks, then submit permitted downstream camera observations.
   Keep release truth/full-frame recordings outside the inference/agent input.
8. Record both trajectory-history and first-seen-retained trials; keep wrong and
   Unknown results. Compare the stored baselines and report accuracy separately
   from coverage. Do not count synthetic cases as physical trials.
9. Provision Gemini/Photon only when needed for the conversation demo. A cached
   dataset import does not establish a trained detector or a live agent. Copernicus
   already has a local currents import; it is not your tank's flow calibration.
10. Keep the optional water sampler disabled until its driver, fused supply,
    physical power switch, wiring and timeout tests are complete. Confirm ASUS
    model/OS/ports on arrival and reinstall dependencies on that computer.

The dataset importer, exporter and local library remain implemented. Their command
help is available with `python scripts/datasets.py --help`; this replaces the removed
standalone dataset setup guide. No new model training or source validation is implied.
