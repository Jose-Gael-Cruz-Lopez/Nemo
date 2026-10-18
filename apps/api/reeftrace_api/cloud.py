"""Hosted software-demo factory; run with uvicorn and exactly one API worker.

Only externally supplied environment settings are used. The cloud store is a
separate public-demo store, never a copy of the team's private tank database.
This entry point deliberately has no camera, physical rig, Photon worker or xAI
voice capability. Pinned research and operator-authorized Chalk stay available.

Example: uvicorn reeftrace_api.cloud:create_cloud_app --factory --workers 1
"""

from __future__ import annotations

import hmac
import importlib
import math
import os
import sqlite3
import threading
import time
from pathlib import Path

from fastapi import Depends, HTTPException, Request

CLOUD_MARKER = ".nemo-cloud-demo-v1"
CLOUD_MARKER_CONTENT = "Nemo isolated public software-demo store v1\n"
CLOUD_DISABLED_REASON = "This hosted demo has no local camera, physical rig, messaging or voice capability."
_FACTORY_LOCK = threading.Lock()
_FORCED_ENV = {
    "PYTHON_DOTENV_DISABLED": "1",
    "PHOTON_ENABLED": "false",
    "PHOTON_ROUTES_JSON": "[]",
    "GROK_VOICE_ENABLED": "false",
    "PHOTON_API_KEY": "",
    "PHOTON_PROJECT_ID": "",
    "XAI_API_KEY": "",
}


class _InvestigationGate:
    """One in-flight turn per app/worker, followed by a monotonic cooldown."""

    def __init__(self, cooldown_s, *, clock=time.monotonic):
        self.cooldown_s = cooldown_s
        self.clock = clock
        self.lock = threading.Lock()
        self.busy = False
        self.next_allowed = 0.

    def enter(self):
        # Never queue provider requests behind a slow turn.
        if not self.lock.acquire(blocking=False):
            return False, max(1, math.ceil(self.cooldown_s))
        try:
            remaining = self.next_allowed - self.clock()
            if self.busy or remaining > 0:
                return False, max(1, math.ceil(max(remaining, self.cooldown_s if self.busy else 0)))
            self.busy = True
            return True, 0
        finally:
            self.lock.release()

    def leave(self):
        with self.lock:
            self.next_allowed = self.clock() + self.cooldown_s
            self.busy = False


def _cooldown():
    try:
        value = float(os.environ.get("REEFTRACE_CLOUD_INVESTIGATION_COOLDOWN_S", "3"))
    except ValueError:
        raise RuntimeError("Cloud investigation cooldown must be finite, positive and at most 300 seconds") from None
    if not math.isfinite(value) or not 0 < value <= 300:
        raise RuntimeError("Cloud investigation cooldown must be finite, positive and at most 300 seconds")
    return value


def _cloud_directory():
    configured = os.environ.get("REEFTRACE_DATA_DIR", "")
    directory = Path(configured)
    if not configured or not directory.is_absolute() or directory.is_symlink():
        raise RuntimeError("Cloud mode requires an absolute, separate REEFTRACE_DATA_DIR")
    repository = Path(__file__).resolve().parents[3]
    directory = directory.resolve()
    if directory == repository or repository in directory.parents:
        raise RuntimeError("Cloud mode requires a store outside the application source tree")
    directory.mkdir(parents=True, exist_ok=True)
    marker = directory / CLOUD_MARKER
    if marker.is_symlink():
        raise RuntimeError("Cloud store ownership marker cannot be a symlink")
    if marker.exists():
        if not marker.is_file() or marker.read_text() != CLOUD_MARKER_CONTENT:
            raise RuntimeError("Cloud store ownership marker is invalid")
    else:
        if any(directory.iterdir()):
            raise RuntimeError("Use a fresh cloud demo directory; never import a private local store")
        try:
            with marker.open("x") as stream:
                stream.write(CLOUD_MARKER_CONTENT)
        except FileExistsError:
            if marker.is_symlink() or marker.read_text() != CLOUD_MARKER_CONTENT:
                raise RuntimeError("Cloud store ownership marker changed") from None
    database = directory / "reeftrace.sqlite3"
    if any((directory / name).is_symlink() for name in
           ("reeftrace.sqlite3", "reeftrace.sqlite3-wal", "reeftrace.sqlite3-shm")):
        raise RuntimeError("Cloud database files cannot be symlinks")
    if database.exists() and not database.is_file():
        raise RuntimeError("Cloud database path must be a regular file")
    return directory


def _blocked_path(path, method):
    # ASGI's path is already decoded. Trailing slashes and nested paths remain
    # blocked, before request parsing or operator authentication touches a tool.
    path = path.rstrip("/")
    if path == "/api/v1/camera" or path.startswith("/api/v1/camera/"):
        return True
    if path.endswith("/briefing/audio"):
        return True
    if method not in {"GET", "HEAD", "OPTIONS"}:
        if any(path == prefix or path.startswith(prefix + "/") for prefix in
               ("/api/v1/rig", "/api/v1/field-sessions", "/api/v1/actions")):
            return True
        if path in {"/api/v1/vision/calibrate", "/api/v1/flow/fit-recordings"}:
            return True
        if path.startswith("/api/v1/recordings/") and path.endswith("/case"):
            return True
    return False


class CloudCamera:
    """Inert capability, also protecting non-HTTP agent/tool call paths."""

    session_id = None

    def status(self):
        return {"running": False, "fresh": False, "session_id": None,
                "device_index": None, "age_s": None, "sequence": None,
                "width": None, "height": None, "backend": None,
                "available": False, "reason_code": "CLOUD_CAPABILITY_UNAVAILABLE"}

    def stop(self):
        return None

    def snapshot(self):
        return None

    def start(self, *_args, **_kwargs):
        raise ValueError(CLOUD_DISABLED_REASON)

    def image(self, *_args, **_kwargs):
        raise ValueError(CLOUD_DISABLED_REASON)

    def preview_snapshot(self, *_args, **_kwargs):
        raise ValueError(CLOUD_DISABLED_REASON)


def create_cloud_app():
    """Explicit factory: no .env discovery, device access or provider requests."""
    # Set these BEFORE importing main, whose existing module-level local app
    # otherwise reads .env and creates a Runtime. This is a process-wide cloud
    # policy: run this entry point in its own process, not beside a local app.
    with _FACTORY_LOCK:
        for key, value in _FORCED_ENV.items():
            os.environ[key] = value
        token = os.environ.get("REEFTRACE_LOCAL_TOKEN", "")
        if len(token) < 32 or token != token.strip():
            raise RuntimeError("Cloud mode requires a private REEFTRACE_LOCAL_TOKEN of at least 32 characters")
        cooldown_s = _cooldown()
        directory = _cloud_directory()
        seed_status = "DISABLED"
        seed_directory = os.environ.get("REEFTRACE_CLOUD_SEED_DIR", "")
        if seed_directory:
            from deploy.seed_demo import install_seed
            try:
                seed_status = install_seed(directory, Path(seed_directory))
            except (OSError, ValueError, sqlite3.Error) as error:
                raise RuntimeError("The optional public synthetic seed failed validation") from error
        from .core.settings import Settings

        # PYTHON_DOTENV_DISABLED stops python-dotenv discovery; Pydantic has a
        # separate dotenv source, so disable it during main's first import too.
        original_env_file = Settings.model_config.get("env_file")
        Settings.model_config["env_file"] = None
        try:
            main = importlib.import_module(".main", __package__)
            settings = Settings(_env_file=None, data_dir=directory, local_token=token,
                                allowed_origins=[])
            app = main.create_app(settings)
        finally:
            Settings.model_config["env_file"] = original_env_file

    from fastapi.responses import JSONResponse

    from adapters.grok import GrokVoiceSettings
    from adapters.photon.transport import PhotonSettings

    from .services.photon_readonly import PhotonReadOnlyVerifier

    runtime = app.state.runtime
    runtime.camera = CloudCamera()
    # Keep these disabled even if some later code changes the environment.
    runtime.photon_settings = lambda: PhotonSettings(enabled=False)
    runtime.grok_settings = lambda: GrokVoiceSettings(enabled=False)
    app.state.deployment_profile = "cloud_software_demo"
    app.state.cloud_seed_status = seed_status
    gate = _InvestigationGate(cooldown_s)
    app.state.cloud_investigation_gate = gate
    photon_verifier = PhotonReadOnlyVerifier(
        os.environ.get("PHOTON_READONLY_API_KEY", ""),
        os.environ.get("PHOTON_READONLY_PROJECT_ID", ""))

    def verify_operator(request: Request):
        if not hmac.compare_digest(request.headers.get("Authorization", "").encode(),
                                   ("Bearer " + token).encode()):
            raise HTTPException(401, "Operator token required",
                                headers={"Cache-Control": "no-store"})

    @app.post("/api/v1/integrations/photon/verify", dependencies=[Depends(verify_operator)])
    async def verify_photon_connection():
        return JSONResponse(await photon_verifier.verify(),
                            headers={"Cache-Control": "no-store"})

    @app.middleware("http")
    async def cloud_capabilities(request, call_next):
        if _blocked_path(request.url.path, request.method):
            return JSONResponse(status_code=503,
                content={"detail": CLOUD_DISABLED_REASON, "reason_code": "CLOUD_CAPABILITY_UNAVAILABLE"},
                headers={"Cache-Control": "no-store"})
        admitted = False
        if (request.method == "POST" and request.url.path.rstrip("/").endswith("/investigate")
                and request.url.path.startswith("/api/v1/")
                and hmac.compare_digest(request.headers.get("Authorization", "").encode(),
                                        ("Bearer " + token).encode())):
            admitted, retry_after = gate.enter()
            if not admitted:
                return JSONResponse(status_code=429,
                    content={"detail": "An investigation is active or cooling down; try again shortly.",
                             "reason_code": "CLOUD_INVESTIGATION_RATE_LIMIT"},
                    headers={"Cache-Control": "no-store", "Retry-After": str(retry_after)})
        try:
            response = await call_next(request)
            if request.url.path.startswith("/api/"):
                response.headers["Cache-Control"] = "no-store"
            return response
        finally:
            if admitted:
                gate.leave()

    @app.get("/api/v1/deployment")
    def deployment_profile():
        return {"profile": "cloud_software_demo", "store_scope": "shared_public_demo",
                "operator_authentication": "required_for_writes_and_Chalk",
                "camera_available": False, "physical_capture_available": False,
                "photon_replies_available": False, "grok_voice_available": False,
                "research_data": "pinned_local_public_artifacts",
                "physical_validation": False, "synthetic_seed_status": seed_status,
                "investigation_concurrency": 1,
                "investigation_cooldown_s": cooldown_s}

    return app
