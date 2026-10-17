"""Local launcher boundaries: no installs, secret output, camera or sponsor requests."""
from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/dev.py"
spec = importlib.util.spec_from_file_location("reeftrace_dev_launcher", SCRIPT)
dev = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = dev
spec.loader.exec_module(dev)


@pytest.fixture
def ready_root(tmp_path, monkeypatch):
    next_bin = tmp_path / "dashboard/node_modules/next/dist/bin/next"
    next_bin.parent.mkdir(parents=True)
    next_bin.write_text("test dependency placeholder")
    (tmp_path / ".env").write_text("REEFTRACE_LOCAL_TOKEN=private-unit-test-token\n")
    monkeypatch.setattr(dev, "python_for", lambda _: Path(sys.executable))
    monkeypatch.setattr(dev, "probe_python", lambda *_: {
        "missing": [], "photon_enabled": False, "token_present": True,
    })
    monkeypatch.setattr(dev.shutil, "which", lambda name: "/local/bin/" + name)
    monkeypatch.setattr(dev, "inspect_port", lambda _: "free")
    return tmp_path


def test_preflight_check_is_read_only(ready_root, monkeypatch, capsys):
    before = {p: p.read_bytes() for p in ready_root.rglob("*") if p.is_file()}
    monkeypatch.setattr(dev, "bootstrap", lambda *_: pytest.fail("check must not bootstrap"))
    monkeypatch.setattr(dev, "run_services", lambda *_: pytest.fail("check must not start"))
    assert dev.main(["--check"], root=ready_root) == 0
    assert before == {p: p.read_bytes() for p in ready_root.rglob("*") if p.is_file()}
    output = capsys.readouterr()
    assert "private-unit-test-token" not in output.out + output.err
    assert "Preflight passed" in output.out


def test_check_missing_env_does_not_create_it(ready_root, monkeypatch):
    (ready_root / ".env").unlink()
    monkeypatch.setattr(dev, "bootstrap", lambda *_: pytest.fail("must not bootstrap"))
    assert dev.main(["--check"], root=ready_root) == 1
    assert not (ready_root / ".env").exists()


def test_default_repairs_copied_blank_template_without_printing_it(ready_root, monkeypatch, capsys):
    (ready_root / ".env").write_text("REEFTRACE_LOCAL_TOKEN=\nCHALK_ROUTER_API_KEY=private-sponsor-key\n")
    monkeypatch.setattr(dev, "probe_python", lambda *_: {
        "missing": [], "photon_enabled": False, "token_present": False,
    })
    calls = []
    monkeypatch.setattr(dev, "bootstrap", lambda report: calls.append(report.needs_bootstrap))
    monkeypatch.setattr(dev, "run_services", lambda _: 0)
    assert dev.main([], root=ready_root) == 0
    assert calls == [True]
    assert "private-sponsor-key" not in str(capsys.readouterr())


def test_unrelated_listener_blocks_all_startup(ready_root, monkeypatch, capsys):
    monkeypatch.setattr(dev, "inspect_port", lambda name: "conflict" if name == "API" else "free")
    monkeypatch.setattr(dev, "bootstrap", lambda *_: pytest.fail("conflict must not mutate settings"))
    monkeypatch.setattr(dev, "run_services", lambda *_: pytest.fail("conflict must not start"))
    assert dev.main([], root=ready_root) == 1
    assert "Port 8000" in capsys.readouterr().err


def test_enabled_photon_requires_explicit_flag_for_new_api(ready_root, monkeypatch):
    monkeypatch.setattr(dev, "probe_python", lambda *_: {
        "missing": [], "photon_enabled": True, "token_present": True,
    })
    blocked = dev.preflight(ready_root, check=False, allow_photon=False)
    assert any("--allow-photon" in message for message in blocked.problems)
    allowed = dev.preflight(ready_root, check=False, allow_photon=True)
    assert not allowed.problems


def test_reused_api_with_photon_is_not_newly_started(ready_root, monkeypatch):
    monkeypatch.setattr(dev, "probe_python", lambda *_: {
        "missing": [], "photon_enabled": True, "token_present": True,
    })
    monkeypatch.setattr(dev, "inspect_port", lambda _: "reeftrace")
    monkeypatch.setattr(dev, "start_child", lambda *_: pytest.fail("existing service must be reused"))
    report = dev.preflight(ready_root, check=False, allow_photon=False)
    assert not report.problems
    assert dev.run_services(report) == 0


def test_missing_runtimes_have_actionable_errors(ready_root, monkeypatch):
    monkeypatch.setattr(dev.shutil, "which", lambda _: None)
    monkeypatch.setattr(dev, "probe_python", lambda *_: {"missing": ["uvicorn"]})
    report = dev.preflight(ready_root, check=True, allow_photon=False)
    assert any("uvicorn" in problem for problem in report.problems)
    assert any("Node.js and npm" in problem for problem in report.problems)


def test_repo_python_selection_is_independent_of_cwd(tmp_path, monkeypatch):
    interpreter = tmp_path / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    interpreter.parent.mkdir(parents=True)
    interpreter.touch()
    monkeypatch.chdir(tmp_path.parent)
    assert dev.python_for(tmp_path) == interpreter


def test_dependency_probe_has_exact_dotenv_precedence_and_returns_no_secrets(tmp_path, monkeypatch):
    monkeypatch.delenv("PHOTON_ENABLED", raising=False)
    monkeypatch.delenv("REEFTRACE_LOCAL_TOKEN", raising=False)
    (tmp_path / ".env").write_text(
        'REEFTRACE_LOCAL_TOKEN="private-probe-value"\n'
        'PHOTON_SWITCH=true\nPHOTON_ENABLED=${PHOTON_SWITCH}\n'
    )
    result = dev.probe_python(Path(sys.executable), tmp_path)
    assert result == {"missing": [], "photon_enabled": True, "token_present": True}
    assert "private-probe-value" not in json.dumps(result)
    monkeypatch.setenv("PHOTON_ENABLED", "false")
    assert not dev.probe_python(Path(sys.executable), tmp_path)["photon_enabled"]
    assert not (tmp_path / "__pycache__").exists()


def test_probe_failure_never_echoes_captured_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr(dev.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(
        returncode=0, stdout="private-secret-in-bad-output", stderr="another-private-secret",
    ))
    with pytest.raises(dev.LauncherError) as error:
        dev.probe_python(Path(sys.executable), tmp_path)
    assert "private-secret" not in str(error.value)


def test_health_alone_is_not_service_identity(monkeypatch):
    monkeypatch.setattr(dev, "http_get", lambda *_: (
        "application/json", b'{"status":"ok","name":"Another API"}',
    ))
    assert not dev.verified_service("API")


def test_api_identity_requires_root_health_and_schema(monkeypatch):
    paths = {
        "/": {"name": "ReefTrace API"},
        "/api/v1/health": {"status": "ok"},
        "/openapi.json": {"info": {"title": "ReefTrace"}},
    }
    monkeypatch.setattr(dev, "http_get", lambda _, path: (
        "application/json", json.dumps(paths[path]).encode(),
    ))
    assert dev.verified_service("API")
    paths["/openapi.json"]["info"]["title"] = "Unrelated"
    assert not dev.verified_service("API")


def test_dashboard_identity_requires_title_and_next_assets(monkeypatch):
    monkeypatch.setattr(dev, "http_get", lambda *_: (
        "text/html", b'<title>Reeftrace | Source intelligence</title><script src="/_next/x.js"></script>',
    ))
    assert dev.verified_service("dashboard")
    monkeypatch.setattr(dev, "http_get", lambda *_: ("text/html", b"Another project"))
    assert not dev.verified_service("dashboard")


def test_dashboard_spawn_is_offline_loopback_and_excludes_server_secrets(ready_root, monkeypatch):
    monkeypatch.setenv("PHOTON_API_KEY", "private-photon")
    monkeypatch.setenv("CHALK_ROUTER_API_KEY", "private-chalk")
    monkeypatch.setenv("REEFTRACE_LOCAL_TOKEN", "private-operator")
    calls = []
    monkeypatch.setattr(dev.subprocess, "Popen", lambda command, **kwargs: calls.append((command, kwargs)))
    report = dev.preflight(ready_root, check=False, allow_photon=False)
    dev.start_child("dashboard", report)
    command, kwargs = calls[0]
    assert command == ["/local/bin/npm", "--offline", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", "3000"]
    assert kwargs["cwd"] == ready_root / "dashboard"
    assert "shell" not in kwargs
    assert not any(key.startswith(("CHALK_", "PHOTON_", "REEFTRACE_")) for key in kwargs["env"])
    assert kwargs["env"]["NEXT_PUBLIC_API_BASE_URL"] == ""
    assert kwargs.get("start_new_session") if os.name == "posix" else kwargs["creationflags"]


def test_api_spawn_keeps_single_loopback_worker_and_never_starts_camera(ready_root, monkeypatch):
    calls = []
    monkeypatch.setattr(dev.subprocess, "Popen", lambda command, **kwargs: calls.append((command, kwargs)))
    report = dev.preflight(ready_root, check=False, allow_photon=False)
    dev.start_child("API", report)
    command, kwargs = calls[0]
    assert command[1:4] == ["-m", "uvicorn", "apps.api.reeftrace_api.main:app"]
    assert command[command.index("--host") + 1] == "127.0.0.1"
    assert command[command.index("--workers") + 1] == "1"
    assert "--reload" not in command and "camera" not in command
    assert kwargs["cwd"] == ready_root


def test_failed_second_start_cleans_only_owned_first_child(ready_root, monkeypatch):
    report = dev.Preflight(root=ready_root, ports={"API": "free", "dashboard": "free"})
    owned = dev.OwnedChild("API", SimpleNamespace())
    cleaned = []

    def start(name, _report):
        if name == "dashboard":
            raise dev.LauncherError("simulated dashboard failure")
        return owned

    monkeypatch.setattr(dev, "start_child", start)
    monkeypatch.setattr(dev, "wait_ready", lambda *_: None)
    monkeypatch.setattr(dev, "stop_children", lambda children: cleaned.extend(children))
    with pytest.raises(dev.LauncherError, match="dashboard failure"):
        dev.run_services(report)
    assert cleaned == [owned]


def test_port_change_before_spawn_aborts_without_ownership(ready_root, monkeypatch):
    report = dev.Preflight(root=ready_root, ports={"API": "free", "dashboard": "free"})
    monkeypatch.setattr(dev, "inspect_port", lambda _: "conflict")
    monkeypatch.setattr(dev, "start_child", lambda *_: pytest.fail("must not start"))
    with pytest.raises(dev.LauncherError, match="changed after preflight"):
        dev.run_services(report)


def test_wait_ready_detects_child_exit_and_is_bounded(monkeypatch):
    child = dev.OwnedChild("API", SimpleNamespace(poll=lambda: 2))
    with pytest.raises(dev.LauncherError, match="exited before"):
        dev.wait_ready(child)
    child.process.poll = lambda: None
    monkeypatch.setattr(dev, "verified_service", lambda _: False)
    with pytest.raises(dev.LauncherError, match="within 0 seconds"):
        dev.wait_ready(child, timeout=0)


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group ownership contract")
def test_cleanup_terminates_real_owned_process_group_only():
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
    try:
        dev.stop_children([dev.OwnedChild("unit-test", process)])
        assert process.poll() == -signal.SIGTERM
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)
