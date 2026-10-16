"""Explicit local sampler test. No agent/API dispatch and no physical retries."""

import argparse
import json
import time
import uuid


def pulse(device, duration_ms):
    if not 1 <= duration_ms <= 5000:
        raise ValueError("Pulse must be 1–5000 ms")
    command_id = uuid.uuid4().hex
    device.write(b"ARM\n")
    deadline = time.monotonic() + 2
    armed = False
    while time.monotonic() < deadline:
        try:
            if json.loads(device.readline()).get("state") == "armed":
                armed = True
                break
        except (ValueError, AttributeError):
            continue
    if not armed:
        return {
            "state": "rejected",
            "reason": "No local arming acknowledgement",
            "command_id": command_id,
        }
    device.write(f"PULSE {duration_ms} {command_id}\n".encode())
    deadline = time.monotonic() + duration_ms / 1000 + 2
    last_ping = 0
    try:
        while time.monotonic() < deadline:
            if time.monotonic() - last_ping > 0.5:
                device.write(b"PING\n")
                last_ping = time.monotonic()
            try:
                event = json.loads(device.readline())
            except (ValueError, AttributeError):
                continue
            if event.get("command_id") == command_id and event.get("state") in {
                "completed",
                "stopped",
                "fault_local_enable_or_watchdog",
            }:
                return {**event, "delivered_volume_ml": None, "physical_retry": False}
        return {
            "state": "uncertain",
            "command_id": command_id,
            "physical_retry": False,
            "reason": "Completion acknowledgement missing; inspect physically, do not repeat automatically",
        }
    finally:
        device.write(b"STOP\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--milliseconds", type=int, required=True)
    parser.add_argument("--circuit-tested", action="store_true", required=True)
    args = parser.parse_args()
    import serial

    with serial.Serial(args.port, 115200, timeout=0.1) as device:
        time.sleep(2)
        print(json.dumps(pulse(device, args.milliseconds)))


if __name__ == "__main__":
    main()
