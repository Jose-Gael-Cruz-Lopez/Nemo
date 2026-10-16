"""Read-only USB telemetry bridge. Never sends movement commands."""

import argparse
import json
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="/dev/cu.usbmodem...")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    import serial

    with serial.Serial(args.port, 115200, timeout=1) as device:
        time.sleep(2)  # Uno resets when USB serial opens.
        while True:
            line = device.readline(512)
            try:
                event = json.loads(line)
                if event.get("type") != "telemetry":
                    continue
                request = urllib.request.Request(
                    args.api + "/api/v1/bench/telemetry",
                    data=json.dumps(event).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=2) as response:
                    response.read()
            except (ValueError, AttributeError, OSError) as exc:
                print(f"Telemetry skipped: {exc}", flush=True)


if __name__ == "__main__":
    main()
