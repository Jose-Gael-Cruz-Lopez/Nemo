# Architecture

The local critical path is camera frames → calibrated detections and motion state → site transport model → source estimator → evidence and uncertainty. Moving observations use trajectory-conditioned backward ensembles; stationary observations use forward simulations and deposition support. Insufficient coverage, stale calibration, low-quality tracks, or ambiguous candidate scores produce `Unknown`.

The optional response path is estimate → short-lived human approval → bounded gantry action → suction → visual verification. FastAPI owns the state machine and approval contract. Arduino firmware independently enforces startup-off, homing, travel, timeout, limit-switch, and watchdog protections. Sponsor integrations must remain replaceable adapters.
