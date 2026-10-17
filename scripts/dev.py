#!/usr/bin/env python3
"""Run the existing local ReefTrace services without installing or contacting sponsors.

Run from any directory: python /path/to/reeftrace/scripts/dev.py [--check].
The script itself uses only Python's standard library. It never starts the camera.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
PORTS = {"API": 8000, "dashboard": 3000}
DEPENDENCIES = (
    "fastapi", "uvicorn", "pydantic_settings", "numpy", "scipy", "cv2", "httpx", "yaml", "dotenv"
)


class LauncherError(Exception):
    """An actionable local setup problem, with no credential contents."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_get(port: int, path: str, timeout: float = 1.0) -> tuple[str, bytes]:
    """Bounded, proxy-free loopback request; never follow remote redirects."""
    request = Request(f"http://{HOST}:{port}{path}", headers={"User-Agent": "ReefTrace-local-launcher"})
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        if response.status != 200:
            raise LauncherError("Unexpected local HTTP status")
        body = response.read(262145)
        if len(body) > 262144:
            raise LauncherError("Local service response exceeds verification limit")
        return response.headers.get("Content-Type", ""), body


def port_in_use(port: int) -> bool:
    try:
        with socket.create_connection((HOST, port), timeout=0.5):
            return True
    except ConnectionRefusedError:
        return False
    except OSError:
        # An uninspectable port is not a safe port for a new owned listener.
        return True


def verified_service(name: str) -> bool:
    """Check identity using safe GETs only; health alone is not an identity."""
    port = PORTS[name]
    try:
        content_type, body = http_get(port, "/")
        if name == "API":
            root = json.loads(body)
            if "application/json" not in content_type or root.get("name") != "ReefTrace API":
                return False
            _, health_body = http_get(port, "/api/v1/health")
            _, schema_body = http_get(port, "/openapi.json")
            return (
                json.loads(health_body).get("status") == "ok"
                and json.loads(schema_body).get("info", {}).get("title") == "ReefTrace"
            )
        html = body.decode("utf-8", errors="replace")
        return (
            "text/html" in content_type
            and re.search(
                r"<title\b[^>]*>\s*(?:Reeftrace \| Source intelligence|Tideward \| Coastal intelligence)\s*</title>",
                html, re.IGNORECASE,
            ) is not None
            and "/_next/" in html
        )
    except (LauncherError, URLError, HTTPError, OSError, ValueError, AttributeError, TypeError):
        return False


def inspect_port(name: str) -> str:
    if not port_in_use(PORTS[name]):
        return "free"
    return "reeftrace" if verified_service(name) else "conflict"


def python_for(root: Path) -> Path:
    interpreter = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not interpreter.is_file():
        raise LauncherError(
            "Repository .venv is missing. Create it and install the README dependencies first; "
            "this launcher never installs packages."
        )
    return interpreter


def probe_python(interpreter: Path, root: Path) -> dict:
    """Inspect dependencies and dotenv precedence in a child, returning booleans only."""
    # Do not import ReefTrace's app here: importing it creates its local database.
    code = (
        "import importlib.util,json,os; "
        f"names={DEPENDENCIES!r}; "
        "missing=[n for n in names if importlib.util.find_spec(n) is None]; "
        "result={'missing':missing}; "
        "exec(\"if not missing:\\n"
        " from dotenv import load_dotenv\\n"
        " load_dotenv('.env',override=False)\\n"
        " result['photon_enabled']=os.getenv('PHOTON_ENABLED','false').lower()=='true'\\n"
        " result['token_present']=bool(os.getenv('REEFTRACE_LOCAL_TOKEN',''))\\n\"); "
        "print(json.dumps(result))"
    )
    try:
        result = subprocess.run(
            [str(interpreter), "-B", "-c", code], cwd=root, capture_output=True,
            text=True, timeout=10, check=False,
        )
        if result.returncode:
            raise LauncherError("Python preflight failed. Check the repository .venv dependencies.")
        data = json.loads(result.stdout)
        if not isinstance(data, dict) or not isinstance(data.get("missing"), list):
            raise TypeError
        return data
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError):
        # Captured output can contain dependency diagnostics; never echo it or .env values.
        raise LauncherError("Python preflight failed. Check the repository .venv dependencies.") from None


@dataclass
class Preflight:
    root: Path
    python: Path | None = None
    npm: str | None = None
    ports: dict[str, str] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    needs_bootstrap: bool = False
    photon_enabled: bool = False


def preflight(root: Path, *, check: bool, allow_photon: bool) -> Preflight:
    report = Preflight(root=root)
    try:
        report.python = python_for(root)
        probe = probe_python(report.python, root)
        if probe["missing"]:
            report.problems.append("Missing Python packages: " + ", ".join(probe["missing"]))
        else:
            report.photon_enabled = probe.get("photon_enabled", False)
            report.needs_bootstrap = not (root / ".env").is_file() or not probe.get("token_present", False)
            if report.needs_bootstrap:
                if check:
                    report.problems.append(
                        "Local .env/operator token needs bootstrap. Run this launcher without --check "
                        "or run python scripts/bootstrap.py; no settings were changed."
                    )
                else:
                    report.notes.append("Private local settings will be initialized without printing the token.")
    except LauncherError as error:
        report.problems.append(str(error))

    node = shutil.which("node")
    report.npm = shutil.which("npm")
    if not node or not report.npm:
        report.problems.append("Node.js and npm must be on PATH. Install/use the README Node runtime first.")
    if not (root / "dashboard/node_modules/next/dist/bin/next").is_file():
        report.problems.append(
            "Dashboard dependencies are missing. Run npm ci inside dashboard first; "
            "this launcher never installs packages."
        )
    for name, port in PORTS.items():
        status = inspect_port(name)
        report.ports[name] = status
        if status == "conflict":
            report.problems.append(
                f"Port {port} has an unrelated or unverifiable listener. "
                "Stop it yourself or use its own project; no process was killed."
            )
        elif status == "reeftrace":
            report.notes.append(f"ReefTrace {name} is already running on loopback:{port}; it will be reused.")
    # Merely launching the API can start a configured Photon worker. Never silently enable it.
    if report.photon_enabled and not allow_photon and report.ports.get("API") != "reeftrace":
        report.problems.append(
            "PHOTON_ENABLED=true can start an external messaging worker. "
            "Use --allow-photon only when you intend that configured worker to run, "
            "or disable PHOTON_ENABLED in your private settings."
        )
    if report.photon_enabled and report.ports.get("API") == "reeftrace":
        report.notes.append("The existing API may already own its configured Photon worker; it is left untouched.")
    return report


def bootstrap(report: Preflight) -> None:
    if not report.needs_bootstrap:
        return
    try:
        result = subprocess.run(
            [str(report.python), str(report.root / "scripts/bootstrap.py")],
            cwd=report.root, capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise LauncherError("Local bootstrap failed. Run python scripts/bootstrap.py locally.") from None
    if result.returncode:
        raise LauncherError("Local bootstrap failed. Run python scripts/bootstrap.py locally.")
    probe = probe_python(report.python, report.root)
    if not probe.get("token_present"):
        raise LauncherError("Operator token is still unset. Run python scripts/bootstrap.py locally.")
    if probe.get("photon_enabled") != report.photon_enabled:
        raise LauncherError("Photon settings changed during bootstrap. Rerun preflight before starting.")


@dataclass
class OwnedChild:
    name: str
    process: subprocess.Popen


def start_child(name: str, report: Preflight) -> OwnedChild:
    environment = os.environ.copy()
    environment.update({"PYTHONUNBUFFERED": "1", "NEXT_TELEMETRY_DISABLED": "1"})
    if name == "API":
        command = [str(report.python), "-m", "uvicorn", "apps.api.reeftrace_api.main:app",
                   "--host", HOST, "--port", "8000", "--workers", "1", "--no-access-log"]
        cwd = report.root
    else:
        # Sponsor/operator secrets are server-only and are not needed by Next's dev process.
        environment = {k: v for k, v in environment.items()
                       if not k.startswith(("CHALK_", "PHOTON_", "REEFTRACE_"))}
        environment.update({
            "NEXT_PUBLIC_API_BASE_URL": "",
            "NPM_CONFIG_UPDATE_NOTIFIER": "false", "NPM_CONFIG_AUDIT": "false",
            "NPM_CONFIG_FUND": "false",
        })
        command = [str(report.npm), "--offline", "run", "dev", "--", "--hostname", HOST, "--port", "3000"]
        cwd = report.root / "dashboard"
    try:
        kwargs = {"start_new_session": True} if os.name == "posix" else {
            "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP,
        }
        return OwnedChild(name, subprocess.Popen(command, cwd=cwd, env=environment, **kwargs))
    except OSError:
        raise LauncherError(f"Could not start the {name}; check the local runtime and dependencies.") from None


def wait_ready(child: OwnedChild, *, timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if child.process.poll() is not None:
            raise LauncherError(f"The owned {child.name} exited before becoming ready; inspect its local log above.")
        if verified_service(child.name):
            return
        time.sleep(0.2)
    raise LauncherError(f"The owned {child.name} did not become ready within {timeout:g} seconds.")


def stop_children(children: list[OwnedChild]) -> None:
    """Only terminate the process groups created by this invocation, never reused services."""
    for child in reversed(children):
        process = child.process
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGTERM)
            elif process.poll() is None:
                process.terminate()
        except ProcessLookupError:
            pass
    for child in reversed(children):
        process = child.process
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass


def interrupt_launcher(*_args):
    raise KeyboardInterrupt


def run_services(report: Preflight) -> int:
    children: list[OwnedChild] = []
    old_term = None
    try:
        if hasattr(signal, "SIGTERM"):
            old_term = signal.getsignal(signal.SIGTERM)
            signal.signal(signal.SIGTERM, interrupt_launcher)
        for name, port in PORTS.items():
            if report.ports[name] == "reeftrace":
                continue
            # Detect a port claimed since preflight before spawning anything on it.
            if inspect_port(name) != "free":
                raise LauncherError(f"Port {port} changed after preflight. Rerun the launcher.")
            child = start_child(name, report)
            children.append(child)
            wait_ready(child)
            print(f"ReefTrace {name} ready at http://{HOST}:{port}", flush=True)
        print("Dashboard: http://127.0.0.1:3000", flush=True)
        print("Camera remains off until an operator starts it in the dashboard.", flush=True)
        print("Read the private .env token locally when the dashboard requests it; never publish it.", flush=True)
        if not children:
            print("Both verified services were already running; this invocation owns no process.")
            return 0
        print("Press Ctrl+C to stop only the services started by this launcher.", flush=True)
        while True:
            for child in children:
                if child.process.poll() is not None:
                    raise LauncherError(f"The owned {child.name} exited; stopping the other owned services.")
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("\nStopping owned ReefTrace services. Existing services are left running.")
        return 0
    finally:
        stop_children(children)
        if old_term is not None:
            signal.signal(signal.SIGTERM, old_term)


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Read-only preflight; start nothing and change no files")
    parser.add_argument("--allow-photon", action="store_true",
                        help="Allow startup of an already enabled Photon messaging worker")
    args = parser.parse_args(argv)
    try:
        report = preflight(root, check=args.check, allow_photon=args.allow_photon)
        for note in report.notes:
            print(note)
        if report.problems:
            for problem in report.problems:
                print("Setup: " + problem, file=sys.stderr)
            return 1
        if args.check:
            print("Preflight passed. No processes started, files changed, camera opened or sponsor calls made.")
            return 0
        bootstrap(report)
        return run_services(report)
    except LauncherError as error:
        print("Setup: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
