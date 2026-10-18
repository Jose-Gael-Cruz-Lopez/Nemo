"""Hosted-demo boundaries use temporary stores and prohibit external effects."""

import os
import subprocess
import sys
from pathlib import Path

import cv2
import httpx
import pytest
from fastapi.testclient import TestClient

from apps.api.reeftrace_api import cloud

TOKEN = "CLOUD-TEST-OPERATOR-ONLY-1234567890"
AUTH = {"Authorization": "Bearer " + TOKEN}
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def cloud_env(tmp_path, monkeypatch):
    monkeypatch.delenv("REEFTRACE_CLOUD_SEED_DIR", raising=False)
    # Every changed process value is restored by monkeypatch, including the
    # wrapper's process-wide policy. No real key or personal store is used.
    for name in cloud._FORCED_ENV:
        monkeypatch.setenv(name, "UNTRUSTED-INITIAL-CONFIGURATION")
    monkeypatch.setenv("PHOTON_ENABLED", "true")
    monkeypatch.setenv("GROK_VOICE_ENABLED", "true")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "not-json-that-must-never-be-parsed")
    monkeypatch.setenv("REEFTRACE_DATA_DIR", str(tmp_path / "cloud-store"))
    monkeypatch.setenv("REEFTRACE_LOCAL_TOKEN", TOKEN)
    monkeypatch.setenv("CHALK_ENABLED", "false")
    monkeypatch.setenv("CHALK_ROUTER_API_KEY", "CLOUD-TEST-GATEWAY-ONLY")
    monkeypatch.setenv("CHALK_ENV_ID", "CLOUD-TEST-ENVIRONMENT")
    monkeypatch.setenv("CHALK_MODEL", "CLOUD-TEST-MODEL")
    monkeypatch.setenv("REEFTRACE_CLOUD_INVESTIGATION_COOLDOWN_S", "3")
    attempts = {"camera": 0, "provider": 0, "photon": 0}

    def forbidden(kind):
        def fail(*_args, **_kwargs):
            attempts[kind] += 1
            raise AssertionError("Cloud test attempted " + kind)
        return fail

    monkeypatch.setattr(cv2, "VideoCapture", forbidden("camera"))
    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden("provider"))
    from adapters.photon.worker import PhotonWorker
    monkeypatch.setattr(PhotonWorker, "__init__", forbidden("photon"))
    yield tmp_path / "cloud-store", attempts
    assert attempts == {"camera": 0, "provider": 0, "photon": 0}


def test_factory_disables_both_dotenv_sources_and_retains_only_explicit_chalk(cloud_env, monkeypatch, tmp_path):
    import dotenv.main
    import pydantic_settings.sources.providers.dotenv

    from apps.api.reeftrace_api.core.settings import Settings

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("CHALK_ROUTER_API_KEY=POISON-FILE-KEY\nPHOTON_ENABLED=true\n")
    original_env_file = Settings.model_config.get("env_file")

    def forbidden(*_args, **_kwargs):
        pytest.fail("Cloud factory tried to discover or read a .env file")

    monkeypatch.setattr(dotenv.main, "find_dotenv", forbidden)
    monkeypatch.setattr(pydantic_settings.sources.providers.dotenv, "dotenv_values", forbidden)
    app = cloud.create_cloud_app()
    assert Settings.model_config.get("env_file") == original_env_file
    runtime = app.state.runtime
    assert runtime.settings.data_dir == cloud_env[0]
    assert runtime.settings.allowed_origins == []
    assert runtime.chalk_settings().api_key == "CLOUD-TEST-GATEWAY-ONLY"
    assert app.state.deployment_profile == "cloud_software_demo"
    assert all(os.environ[name] == value for name, value in cloud._FORCED_ENV.items())
    assert isinstance(runtime.camera, cloud.CloudCamera)
    with TestClient(app) as client:
        status = client.get("/api/v1/status")
        assert status.status_code == 200
        data = status.json()
        assert data["photon"]["enabled"] is data["photon"]["worker_running"] is False
        assert data["grok"]["enabled"] is False
        assert data["camera"]["running"] is data["camera"]["fresh"] is False
        assert data["operator_configured"] is True
        assert TOKEN not in status.text and "CLOUD-TEST-GATEWAY-ONLY" not in status.text
        assert client.get("/api/v1/deployment").json()["store_scope"] == "shared_public_demo"


@pytest.mark.parametrize("method,path", [
    ("POST", "/api/v1/camera/start"), ("POST", "/api/v1/camera/start/"),
    ("POST", "/api/v1/camera/stop"), ("POST", "/api/v1/camera/record"),
    ("GET", "/api/v1/camera/frame.jpg"), ("GET", "/api/v1/camera/stream.mjpg?session_id=anything"),
    ("POST", "/api/v1/vision/calibrate"), ("POST", "/api/v1/flow/fit-recordings"),
    ("POST", "/api/v1/rig/disturbed"), ("POST", "/api/v1/rig/revalidate"),
    ("POST", "/api/v1/field-sessions/preflight"), ("POST", "/api/v1/field-sessions"),
    ("POST", "/api/v1/recordings/missing/case"), ("POST", "/api/v1/actions/propose"),
    ("POST", "/api/v1/actions/missing/approve"), ("POST", "/api/v1/actions/missing/outcome"),
    ("POST", "/api/v1/cases/missing/briefing/audio"),
])
def test_hardware_and_voice_routes_fail_before_body_auth_or_device_access(cloud_env, method, path):
    with TestClient(cloud.create_cloud_app()) as client:
        for headers in ({}, AUTH):
            response = client.request(method, path, headers=headers, content=b"malformed-body")
            assert response.status_code == 503
            assert response.json()["reason_code"] == "CLOUD_CAPABILITY_UNAVAILABLE"
            assert response.headers["Cache-Control"] == "no-store"


def test_inert_camera_and_frozen_disabled_provider_settings_also_protect_tools(cloud_env, monkeypatch):
    app = cloud.create_cloud_app()
    runtime = app.state.runtime
    monkeypatch.setenv("PHOTON_ENABLED", "true")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "invalid")
    monkeypatch.setenv("GROK_VOICE_ENABLED", "true")
    assert not runtime.photon_settings().enabled and not runtime.photon_settings().api_key
    assert not runtime.grok_settings().enabled and not runtime.grok_settings().api_key
    for name in ("start", "image", "preview_snapshot"):
        with pytest.raises(ValueError, match="hosted demo"):
            getattr(runtime.camera, name)()
    assert runtime.camera.snapshot() is None
    assert runtime.camera.stop() is None
    with TestClient(app) as client:
        assert client.get("/api/v1/status").json()["photon"]["worker_running"] is False
    assert runtime.photon_worker is runtime.photon_task is None


def test_operator_authentication_software_demo_and_persistent_restart(cloud_env):
    directory, _attempts = cloud_env
    with TestClient(cloud.create_cloud_app()) as client:
        assert client.get("/api/v1/operator/session").status_code == 401
        assert client.get("/api/v1/operator/session", headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert client.get("/api/v1/operator/session", headers=AUTH).json() == {
            "authenticated": True, "scope": "local_operator"}
        assert client.post("/api/v1/demo/load").status_code == 401
        loaded = client.post("/api/v1/demo/load", headers=AUTH)
        assert loaded.status_code == 200
        assert loaded.json()["mode"] == "SYNTHETIC" and loaded.json()["physical_validation"] is False
        cases = client.get("/api/v1/cases").json()
        assert cases and all(case["mode"] == "SYNTHETIC" for case in cases)
        case = cases[0]
        evidence = client.get(f"/api/v1/cases/{case['id']}/evidence")
        assert evidence.status_code == 200
        assert client.post(f"/api/v1/cases/{case['id']}/investigate", json={"text": "Explain the evidence"}).status_code == 401
        stopped = client.post(f"/api/v1/cases/{case['id']}/investigate", headers=AUTH,
                              json={"text": "Explain the evidence"})
        assert stopped.status_code == 200 and stopped.json()["live_model_response"] is False
        assert stopped.json()["action"] == "STOP"
        comparison = client.post("/api/v1/prevention/demo", headers=AUTH)
        assert comparison.status_code == 200
        assert client.get("/api/v1/prevention/comparisons").json()
    assert (directory / cloud.CLOUD_MARKER).read_text() == cloud.CLOUD_MARKER_CONTENT
    assert (directory / "reeftrace.sqlite3").is_file()
    with TestClient(cloud.create_cloud_app()) as client:
        assert {case["id"] for case in cases} <= {case["id"] for case in client.get("/api/v1/cases").json()}
        assert client.get(f"/api/v1/cases/{case['id']}/evidence").json() == evidence.json()
        assert client.get("/api/v1/prevention/comparisons").json()


def test_saved_ocean_research_and_disabled_chalk_remain_available_without_execution(cloud_env, monkeypatch):
    from apps.ocean.reeftrace_ocean import ocean_source, ocean_source_pipeline
    from scripts import evaluate_ocean_source

    def forbidden(*_args, **_kwargs):
        pytest.fail("A cloud GET tried to execute the frozen first-score method")

    for module, names in ((ocean_source, ("build_ocean_source_forecasts", "score_ocean_source_forecasts")),
                          (ocean_source_pipeline, ("build_pipeline_forecasts", "score_pipeline_forecasts")),
                          (evaluate_ocean_source, ("first_score",))):
        for name in names:
            monkeypatch.setattr(module, name, forbidden)
    app = cloud.create_cloud_app()
    clock = [100.]
    app.state.cloud_investigation_gate.clock = lambda: clock[0]
    with TestClient(app) as client:
        response = client.get("/api/v1/research/ocean-source")
        assert response.status_code == 200
        data = response.json()
        assert data["report"]["pipeline_tutorial"]["validation"]["scored_rows"] == 8
        assert data["artifact_identity"]["external_result_pin_verified"] is True
        request = {"question": "Explain this saved trajectory", **{key: data["artifact_identity"][key]
                   for key in ("report_sha256", "protocol_sha256", "identity_sha256")}}
        assert client.post("/api/v1/research/ocean-source/investigate", json=request).status_code == 401
        stopped = client.post("/api/v1/research/ocean-source/investigate", json=request, headers=AUTH)
        assert stopped.status_code == 200 and stopped.json()["action"] == "STOP"
        assert stopped.json()["live_model_response"] is False
        request["identity_sha256"] = "0" * 64
        clock[0] += 4.
        assert client.post("/api/v1/research/ocean-source/investigate", json=request, headers=AUTH).status_code == 409


@pytest.mark.parametrize("token", ["", "short", " " + TOKEN, TOKEN + " "])
def test_cloud_requires_external_private_operator_token(cloud_env, monkeypatch, token):
    monkeypatch.setenv("REEFTRACE_LOCAL_TOKEN", token)
    with pytest.raises(RuntimeError, match="REEFTRACE_LOCAL_TOKEN"):
        cloud.create_cloud_app()


@pytest.mark.parametrize("configuration", ["absent", "relative", "repository", "unmarked", "bad_marker", "symlink"])
def test_cloud_refuses_private_or_unowned_store_paths(cloud_env, monkeypatch, tmp_path, configuration):
    directory = tmp_path / "separate"
    if configuration == "absent":
        monkeypatch.delenv("REEFTRACE_DATA_DIR")
    elif configuration == "relative":
        monkeypatch.setenv("REEFTRACE_DATA_DIR", "data/local")
    elif configuration == "repository":
        monkeypatch.setenv("REEFTRACE_DATA_DIR", str(ROOT / "data/local"))
    else:
        directory.mkdir()
        if configuration == "unmarked":
            (directory / "reeftrace.sqlite3").write_bytes(b"PRIVATE-DB-DO-NOT-OPEN")
        elif configuration == "bad_marker":
            (directory / cloud.CLOUD_MARKER).write_text("not-the-cloud-marker")
        else:
            alias = tmp_path / "alias"
            alias.symlink_to(directory, target_is_directory=True)
            directory = alias
        monkeypatch.setenv("REEFTRACE_DATA_DIR", str(directory))
    with pytest.raises(RuntimeError):
        cloud.create_cloud_app()
    if configuration == "unmarked":
        assert (directory / "reeftrace.sqlite3").read_bytes() == b"PRIVATE-DB-DO-NOT-OPEN"


def test_real_uvicorn_package_import_shape_does_not_read_poison_dotenv(tmp_path):
    (tmp_path / ".env").write_text("CHALK_ROUTER_API_KEY=POISON\nPHOTON_ENABLED=true\n")
    code = '''
import dotenv.main, pydantic_settings.sources.providers.dotenv

def forbidden(*args, **kwargs):
    raise AssertionError("dotenv source was touched")
dotenv.main.find_dotenv = forbidden
pydantic_settings.sources.providers.dotenv.dotenv_values = forbidden
from reeftrace_api.cloud import create_cloud_app
app = create_cloud_app()
assert app.state.runtime.photon_settings().enabled is False
assert app.state.runtime.chalk_settings().api_key == ""
assert app.state.runtime.settings.local_token == "CLOUD-TEST-OPERATOR-ONLY-1234567890"
print("CLOUD_PACKAGE_IMPORT_PASS")
'''
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(ROOT / "apps/api") + os.pathsep + str(ROOT),
           "REEFTRACE_DATA_DIR": str(tmp_path / "external-store"), "REEFTRACE_LOCAL_TOKEN": TOKEN}
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=30, check=True)
    assert result.stdout.strip() == "CLOUD_PACKAGE_IMPORT_PASS"
    assert not (tmp_path / "data/local").exists()


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "301", "not-a-number"])
def test_cloud_investigation_cooldown_is_bounded_positive_configuration(cloud_env, monkeypatch, value):
    monkeypatch.setenv("REEFTRACE_CLOUD_INVESTIGATION_COOLDOWN_S", value)
    with pytest.raises(RuntimeError, match="cooldown"):
        cloud.create_cloud_app()


def test_investigation_gate_does_not_queue_and_recovers_after_exception(cloud_env):
    import asyncio

    app = cloud.create_cloud_app()
    clock = [100.]
    gate = app.state.cloud_investigation_gate
    gate.clock = lambda: clock[0]
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    @app.post("/api/v1/cloud-test/investigate")
    async def controlled_turn():
        calls.append("called")
        entered.set()
        await release.wait()
        return {"action": "STOP", "live_model_response": False}

    async def exercise():
        transport = httpx.ASGITransport(app=app)
        # The fixture forbids AsyncClient.request provider use; exercising the
        # in-process ASGI client uses send directly with no network connection.
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = asyncio.create_task(client.send(httpx.Request("POST", "http://test/api/v1/cloud-test/investigate", headers=AUTH)))
            await asyncio.wait_for(entered.wait(), timeout=2)
            second = await client.send(httpx.Request("POST", "http://test/api/v1/cloud-test/investigate", headers=AUTH))
            assert second.status_code == 429 and second.headers["Retry-After"] == "3"
            assert len(calls) == 1
            release.set()
            assert (await first).status_code == 200
            cooldown = await client.send(httpx.Request("POST", "http://test/api/v1/cloud-test/investigate", headers=AUTH))
            assert cooldown.status_code == 429
            clock[0] += 3.
            assert (await client.send(httpx.Request("POST", "http://test/api/v1/cloud-test/investigate", headers=AUTH))).status_code == 200
            assert len(calls) == 2

    asyncio.run(exercise())
    assert gate.busy is False
    clock[0] += 3.
    assert gate.enter() == (True, 0)
    try:
        raise ValueError("simulated failure")
    except ValueError:
        pass
    finally:
        gate.leave()
    assert gate.busy is False and gate.enter()[0] is False


def test_unauthorized_requests_do_not_take_investigation_quota(cloud_env):
    app = cloud.create_cloud_app()
    gate = app.state.cloud_investigation_gate
    with TestClient(app) as client:
        response = client.post("/api/v1/research/ocean-source/investigate", json={"question": "anything"})
        assert response.status_code == 401
        assert gate.busy is False and gate.next_allowed == 0.
        response = client.post("/api/v1/research/ocean-source/investigate", headers={"Authorization": "Bearer invalid"}, json={})
        assert response.status_code == 401 and gate.next_allowed == 0.
