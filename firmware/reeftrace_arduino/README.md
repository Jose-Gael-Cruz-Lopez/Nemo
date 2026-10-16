# Reeftrace Arduino firmware

Implement the device-side safety boundary here: outputs off at startup, explicit homing before absolute moves, bounded travel and speed, debounced limit switches, pump timeout, watchdog, and fault telemetry.

Do not enable motor or pump outputs until the emergency stop, limit switches, travel limits, and pump cutoff have been physically tested. The backend remains the authority for run and approval state; firmware must independently reject unsafe commands.

For the available Uno, HC-SR04, slider, and optional SG90s, use the separate
`../reeftrace_bench/reeftrace_bench.ino` sketch and `docs/GETTING_STARTED.md`.
That dry-bench controller does not implement gantry or pump control.
