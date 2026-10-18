"""Supervise the native, single-origin cloud demo without opening local devices.

Only the Next child listens publicly. API/provider credentials remain exclusively
in the API child; Photon and xAI are disabled regardless of inherited settings.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_PORT = 8000
STARTUP_TIMEOUT_S = 120
SHUTDOWN_TIMEOUT_S = 8


def public_port(environment: dict[str, str]) -> int:
    raw = environment.get("PORT", "8080")
    if not raw.isascii() or not raw.isdecimal() or not 1 <= int(raw) <= 65535:
        raise ValueError("PORT must be an integer between 1 and 65535")
    port = int(raw)
    if port == API_PORT:
        raise ValueError("PORT cannot be 8000; that port belongs to the private API")
    return port


def api_environment(environment: dict[str, str], root: Path) -> dict[str, str]:
    if len(environment.get("REEFTRACE_LOCAL_TOKEN", "")) < 32:
        raise ValueError("REEFTRACE_LOCAL_TOKEN must contain at least 32 private characters")
    data_dir = Path(environment.get("REEFTRACE_DATA_DIR", "/data/nemo"))
    if not data_dir.is_absolute():
        raise ValueError("REEFTRACE_DATA_DIR must be an absolute persistent-volume path")
    result = dict(environment)
    result.update({
        "PYTHONPATH": os.pathsep.join((str(root / "apps/api"), str(root))),
        "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHON_DOTENV_DISABLED": "1",
        "REEFTRACE_DATA_DIR": str(data_dir),
        "PHOTON_ENABLED": "false", "PHOTON_API_KEY": "", "PHOTON_PROJECT_ID": "",
        "PHOTON_ROUTES_JSON": "[]", "GROK_VOICE_ENABLED": "false", "XAI_API_KEY": "",
    })
    return result


def next_environment(environment: dict[str, str], port: int) -> dict[str, str]:
    # Positive allowlist: a future provider secret must not silently reach Next.
    result = {key: environment[key] for key in ("PATH", "LANG", "LC_ALL", "TZ")
              if key in environment}
    result.update({
        "NODE_ENV": "production", "NEXT_TELEMETRY_DISABLED": "1",
        "NODE_OPTIONS": "--max-old-space-size=128",
        "NEXT_PUBLIC_API_BASE_URL": "", "TIDEWARD_PUBLIC_SHOWCASE": "false",
        "PORT": str(port), "HOSTNAME": "0.0.0.0",
    })
    return result


def commands(root: Path, port: int) -> tuple[list[str], list[str]]:
    api = [sys.executable, "-m", "uvicorn", "reeftrace_api.cloud:create_cloud_app", "--factory",
           "--host", "127.0.0.1", "--port", str(API_PORT), "--workers", "1", "--no-access-log"]
    frontend = ["node", str(root / "dashboard/server.js")]
    return api, frontend


def healthy(port: int, *, html: bool = False) -> bool:
    path = "/" if html else "/api/v1/health"
    # Ignore inherited outbound proxy settings for owned loopback probes.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}{path}", timeout=2) as response:
            payload = response.read(8192)
            if response.status != 200:
                return False
            if html:
                return "text/html" in response.headers.get("Content-Type", "").lower()
            return json.loads(payload) == {"status": "ok"}
    except (OSError, ValueError, urllib.error.URLError):
        return False


def require_free_port(port: int) -> None:
    with socket.socket() as probe:
        probe.bind(("0.0.0.0", port))


def signal_group(group_id: int, signum: int) -> None:
    try:
        os.killpg(group_id, signum)
    except ProcessLookupError:
        return
    except PermissionError:
        # Darwin can report EPERM while a group's final orphan is being reaped.
        # Accept only a proven disappearance, never persistent permission denial
        # or a still-live group. Signal 0 observes existence without killing it.
        deadline = time.monotonic() + 0.25
        while time.monotonic() < deadline:
            try:
                os.killpg(group_id, 0)
            except ProcessLookupError:
                return
            except PermissionError:
                pass
            time.sleep(0.005)
        raise


def stop_children(children: list[subprocess.Popen]) -> None:
    # Each child owns a process group, so any descendants receive shutdown too.
    for child in reversed(children):
        # A leader may already have exited while its descendants are still alive.
        signal_group(child.pid, signal.SIGTERM)
    deadline = time.monotonic() + SHUTDOWN_TIMEOUT_S
    for child in reversed(children):
        try:
            child.wait(timeout=max(0.01, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            signal_group(child.pid, signal.SIGKILL)
            child.wait(timeout=2)
    # Reap an orphaned worker group too, even if its direct parent exited cleanly.
    for child in reversed(children):
        signal_group(child.pid, signal.SIGKILL)


def run(root: Path = ROOT, *, startup_timeout_s: float = STARTUP_TIMEOUT_S) -> int:
    environment = dict(os.environ)
    port = public_port(environment)
    api_env = api_environment(environment, root)
    if not (root / "apps/api/reeftrace_api/cloud.py").is_file():
        raise ValueError("Missing cloud safety wrapper; deploy the complete reviewed revision")
    if (not (root / "dashboard/server.js").is_file()
            or not (root / "dashboard/.next/BUILD_ID").is_file()):
        raise ValueError("Missing standalone Next build; build the deployment image first")
    require_free_port(API_PORT)
    require_free_port(port)
    Path(api_env["REEFTRACE_DATA_DIR"]).mkdir(parents=True, exist_ok=True)
    api_command, next_command = commands(root, port)
    children: list[subprocess.Popen] = []
    stop_signal = 0

    def request_stop(signum, _frame):
        nonlocal stop_signal
        stop_signal = signum

    previous = {sig: signal.signal(sig, request_stop) for sig in (signal.SIGTERM, signal.SIGINT)}

    def wait_ready(child: subprocess.Popen, check) -> bool:
        deadline = time.monotonic() + startup_timeout_s
        while not stop_signal and time.monotonic() < deadline:
            if any(owned.poll() is not None for owned in children):
                return False
            if check() and child.poll() is None:
                return True
            time.sleep(0.1)
        return False

    try:
        api = subprocess.Popen(api_command, cwd=root, env=api_env, start_new_session=True)
        children.append(api)
        if not wait_ready(api, lambda: healthy(API_PORT)):
            print("Nemo API failed readiness; shutting down both owned processes", file=sys.stderr)
            return 128 + stop_signal if stop_signal else 1
        frontend = subprocess.Popen(next_command, cwd=root / "dashboard",
                                    env=next_environment(environment, port), start_new_session=True)
        children.append(frontend)
        if not wait_ready(frontend, lambda: healthy(port) and healthy(port, html=True)):
            print("Nemo dashboard/API proxy failed readiness; shutting down", file=sys.stderr)
            return 128 + stop_signal if stop_signal else 1
        print(f"Nemo ready on port {port}; Photon and xAI disabled", flush=True)
        while not stop_signal:
            if any(child.poll() is not None for child in children):
                print("An owned Nemo process exited; shutting down its sibling", file=sys.stderr)
                return 1
            time.sleep(0.2)
        return 128 + stop_signal
    finally:
        stop_children(children)
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Probe health only; never start a service")
    args = parser.parse_args()
    try:
        if args.check:
            port = public_port(dict(os.environ))
            return 0 if healthy(API_PORT) and healthy(port) else 1
        return run()
    except (OSError, ValueError) as error:
        # Configuration messages contain names/paths, never environment values or keys.
        print(f"Nemo startup failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
