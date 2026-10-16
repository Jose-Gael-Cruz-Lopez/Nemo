# Start ReefTrace with your current parts

## What you can build now

The supplied project plan describes a **source-attribution tank**, with robotic collection as an optional response. Start with a dry sensor bench and the synthetic software sandbox. Your inventory does not include a camera, clear tank, circulation pump, collection pump, tubing/mesh, gantry, stepper drivers, limit switches, or rated motor power supply. Do not treat the two micro servos as XY gantry motors.

Use one Uno over USB as the bench controller. The second Uno is a spare. Keep the ESP32 and ESP8266 disconnected for now: USB already carries all bench telemetry. Breadboards, jumper wires, the HC-SR04 and slider are enough for stage 1. The servos can provide a later dry pan/tilt demonstration. The display is optional.

The blue/black sensors, expansion boards, bagged module, and speaker cannot be identified by color. Read their model markings and pin labels before connecting them. An ESP32 development board is not necessarily an ESP32-CAM. Confirm the second motor is a standard positional SG90-compatible servo before using this sketch with it. Leave the speaker disconnected unless its impedance and an appropriate driver circuit are known.

## Stage 1: dry sensor bench

Disconnect power while wiring. Put the Uno and breadboard on a dry table. Check whether the breadboard power rails are split in the middle. This wiring is for the **5V Uno**, not ESP32.

| Component pin | Uno connection |
| --- | --- |
| HC-SR04 VCC | 5V |
| HC-SR04 GND | GND |
| HC-SR04 TRIG | D7 |
| HC-SR04 ECHO | D8 |
| Slider VCC / + | 5V, only after checking module voltage rating |
| Slider GND / - | GND |
| Slider signal / OUT | A0 |

Identify slider labels from its board documentation, not connector position. If leaving the slider disconnected, ignore the floating A0 reading. Aim the range sensor at a flat object in air; it is not an underwater sensor and does not measure the plastic's tank coordinates. Distance is null on timeout/out-of-range, and readings are approximate.

1. Install Arduino IDE and select **Arduino Uno**, then the USB port for your ELEGOO board. Some clones need a USB serial driver; identify the USB chip before installing one.
2. Open `firmware/reeftrace_bench/reeftrace_bench.ino`. Install the Arduino Servo and LiquidCrystal libraries if absent. Keep `ENABLE_SERVOS 0` and `USE_LCD 0`.
3. Upload. Open Serial Monitor at **115200 baud**, newline ending. JSON telemetry should arrive four times per second. Move a flat object in front of the range sensor and slide the potentiometer.
4. Close Serial Monitor before starting the bridge: only one process can own the serial port.

## Stage 2: optional two-servo dry demonstration

Do this only after a separate regulated 5V servo supply with sufficient current is available. Do not power two servos from the Uno USB/5V pin. Wire servo red leads to external +5V, brown/black leads to external ground, and connect that ground to Uno GND. Do not connect the external +5V to Uno 5V. Verify wire colors and ratings against your actual servos.

| Signal | Uno |
| --- | --- |
| Pan servo signal | D9 |
| Tilt servo signal | D10 |
| Normally closed enable/stop contact | Between D2 and GND |

D2 is pulled high internally: an open contact or broken wire disarms. An absent contact keeps motion disabled. For a supervised unloaded bench test only, a removable D2-to-GND jumper can stand in for the contact. Pulling the jumper stops command pulses; **it does not disconnect servo power**. Use a physical power disconnect. Do not use this bench controller to hold a load above water.

Set `ENABLE_SERVOS 1`, upload, and use Serial Monitor:

```text
ARM
POSE 90 90
POSE 110 80
PING
STOP
```

ARM can move both servos to center immediately. Test unloaded with horns removed first. Allowed angles: pan 30–150°, tilt 60–120°. Send PING at least once per second during testing; a two-second command timeout detaches both servos. STOP detaches immediately. Servo ranges are conservative starting points, not verified mechanical limits. Detach removes command pulses, not electrical power or stored mechanical energy. The read-only Python bridge never arms or sends PING; an armed board will time out when using the bridge.

## Stage 3: optional 16×2 LCD

Inspect whether your LCD has a four-pin I2C backpack or a bare 16-pin parallel interface. The sketch supports the **parallel interface only**. Leave four-pin I2C displays disconnected until the backpack/controller is identified.

For a standard HD44780-compatible parallel display: VSS→GND, VDD→5V, RW→GND, RS→D12, E→D11, D4→D6, D5→D5, D6→D4, D7→D3. Leave LCD data D0–D3 disconnected. VO needs an adjustable contrast voltage (usually a separate 10k potentiometer); do not assume the sensor slider is available for both tasks. Verify the backlight resistor on your module before supplying its LED pins. Enable `USE_LCD 1` only after wiring is verified.

## Start the software

From the repository root, Python 3.11+ and Node 20+:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn apps.api.reeftrace_api.main:app --reload --host 127.0.0.1
```

In a second terminal:

```sh
cd dashboard
npm install
npm run dev
```

Open http://localhost:3000. The console offers moving, stationary, and Unknown synthetic scenarios. The API is at http://127.0.0.1:8000/docs. Synthetic trajectories and uniform-current diffusion ensembles are **software demonstrations**, not evidence of tank accuracy. Stationary mode compares forward reachability over 0–60 seconds; it has no coral trapping model. Moving mode compares backward source support and observed velocity. The thresholds (support ≥0.25, first/second gap ≥0.15) are demonstration settings and have not been calibrated on physical trials.

In a third terminal, activate the environment and find the Uno port:

```sh
source .venv/bin/activate
python -m serial.tools.list_ports
python -m apps.hardware.reeftrace_hardware.bridge --port /dev/cu.usbmodemREPLACE
```

Use the actual listed port. The bridge posts telemetry to the local API; the dashboard marks data disconnected after three seconds without updates. The latest reading is held in memory only. No dashboard movement, pump, gantry, or collection action is implemented. Keep this unauthenticated development API bound to localhost.

## Stage 4: camera observations, when a camera is available

Borrow a USB webcam or use a laptop camera if you can mount it rigidly overhead. Borrow a clear tank, stable lighting and an adjustable low-voltage circulation pump for meaningful flow measurements. A tray and a colored marker on a dry table are sufficient for initial vision testing.

Copy `config/camera.example.json` to a local calibration file and replace the example pixels and dimensions. Measure the four inside corners in the exact order **bottom-left, bottom-right, top-right, top-left**. Camera calibration must be remeasured after any mount movement. Validate at independent points with a ruler; the script does not certify calibration accuracy.

```sh
python scripts/track_camera.py --calibration config/camera.local.json --seconds 15
```

The tracker detects one green/high-saturation object by default (OpenCV hue 35–85). Adjust hue bounds for your marker. It rejects frames with zero or multiple qualifying blobs, and saves timestamps and tank coordinates to `data/sample_runs/camera_observation.json`. It does not identify plastic chemistry or robustly associate multiple objects. Large gaps, glare and missed detections require a new recording or better illumination. This recorder does not stream to the dashboard, and real observations return Unknown because no measured tank transport model is implemented yet.

## What to do after the bench works

1. Measure tank geometry, camera mapping, source polygons and flow-marker trajectories at a fixed pump setting and water depth.
2. Implement a spatial flow field with coverage masks and timestamp checks, then replace the synthetic uniform current with it. Add obstacles, deposition regions and release-time assumptions for stationary inference.
3. Freeze model settings before held-out tests: at least nine moving releases (three per inlet), six naturally deposited objects, and three Unknown cases, as proposed in your plan. Report wrong predictions as well as abstentions.
4. Add collection only when the power supply, fused driver, physical E-stop, limits, mechanical structure, pump and mesh plumbing are available and tested. Existing bench firmware is not gantry safety firmware.

## Verified component references

- Arduino servo power and common-ground guidance: https://support.arduino.cc/hc/en-us/articles/360017053760-Troubleshoot-servo-motors
- Servo library API: https://github.com/arduino-libraries/Servo/blob/master/docs/api.md
- ESP32 electrical limits: https://documentation.espressif.com/esp32_datasheet_en.html (do not connect 5V Uno/HC-SR04 signals directly to ESP32 GPIO; use verified level shifting if adding that board later).

## Dependency status

The installed Next.js 15 toolchain reports seven npm advisories (six high, one moderate), involving PostCSS and glob-pattern development dependencies. The suggested automatic fix changes major framework versions; it has not been applied. Keep this local development prototype off public hosting until the dependency upgrade is reviewed.
