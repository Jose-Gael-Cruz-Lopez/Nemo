# Reeftrace Arduino firmware

Implement the device-side safety boundary here: outputs off at startup, explicit homing before absolute moves, bounded travel and speed, debounced limit switches, pump timeout, watchdog, and fault telemetry.

Do not enable motor or pump outputs until the emergency stop, limit switches, travel limits, and pump cutoff have been physically tested. The backend remains the authority for run and approval state; firmware must independently reject unsafe commands.
