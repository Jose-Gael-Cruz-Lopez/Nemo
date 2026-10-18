"""Offline deployment contracts, including real owned-process shutdown."""

from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("nemo_start", Path(__file__).with_name("start.py"))
START = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(START)

WORKER = """
import json, os, pathlib, signal, sys, time
folder, name, mode = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
def stop(sig, frame):
    (folder / (name + '.stopped')).write_text(str(sig))
    sys.exit(0)
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
(folder / (name + '.json')).write_text(json.dumps({'pid':os.getpid(), 'env':dict(os.environ)}))
if mode == 'fail': sys.exit(7)
(folder / (name + '.ready')).touch()
while True: time.sleep(.05)
"""


class EnvironmentTests(unittest.TestCase):
    def test_next_receives_only_required_runtime_configuration(self):
        environment = {"PATH": "/bin", "LANG": "C.UTF-8", "CHALK_ROUTER_API_KEY": "private",
                       "REEFTRACE_LOCAL_TOKEN": "x" * 32, "FUTURE_PROVIDER_SECRET": "private",
                       "NEXT_PUBLIC_API_BASE_URL": "https://wrong.invalid",
                       "NODE_OPTIONS": "--require=/private/untrusted.js",
                       "TIDEWARD_PUBLIC_SHOWCASE": "true"}
        result = START.next_environment(environment, 8080)
        self.assertEqual(result["NODE_OPTIONS"], "--max-old-space-size=128")
        self.assertFalse(any("private" == value for value in result.values()))
        self.assertEqual(result["NEXT_PUBLIC_API_BASE_URL"], "")
        self.assertEqual(result["TIDEWARD_PUBLIC_SHOWCASE"], "false")
        self.assertEqual(result["HOSTNAME"], "0.0.0.0")

    def test_api_preserves_chalk_but_forces_messaging_voice_dotenv_off(self):
        environment = {"REEFTRACE_LOCAL_TOKEN": "x" * 32, "CHALK_ROUTER_API_KEY": "private",
                       "PHOTON_ENABLED": "true", "PHOTON_API_KEY": "private",
                       "PHOTON_ROUTES_JSON": "[{}]", "XAI_API_KEY": "private",
                       "GROK_VOICE_ENABLED": "true", "PYTHON_DOTENV_DISABLED": "0"}
        result = START.api_environment(environment, Path("/app"))
        self.assertEqual(result["CHALK_ROUTER_API_KEY"], "private")
        self.assertEqual(result["PHOTON_ENABLED"], "false")
        self.assertEqual(result["PHOTON_API_KEY"], "")
        self.assertEqual(result["PHOTON_ROUTES_JSON"], "[]")
        self.assertEqual(result["XAI_API_KEY"], "")
        self.assertEqual(result["GROK_VOICE_ENABLED"], "false")
        self.assertEqual(result["PYTHON_DOTENV_DISABLED"], "1")
        self.assertEqual(result["PYTHONPATH"].split(os.pathsep), ["/app/apps/api", "/app"])

    def test_invalid_ports_data_directory_and_missing_operator_fail_closed(self):
        for port in ("0", "65536", "8000", "8080.0", "８０８０", "secret"):
            with self.subTest(port=port), self.assertRaises(ValueError):
                START.public_port({"PORT": port})
        with self.assertRaises(ValueError):
            START.api_environment({}, Path("/app"))
        with self.assertRaises(ValueError):
            START.api_environment({"REEFTRACE_LOCAL_TOKEN": "x" * 32,
                                   "REEFTRACE_DATA_DIR": "data/local"}, Path("/app"))

    def test_api_factory_is_private_and_single_worker(self):
        api, frontend = START.commands(Path("/app"), 8080)
        self.assertIn("reeftrace_api.cloud:create_cloud_app", api)
        self.assertIn("--factory", api)
        self.assertEqual(api[api.index("--workers") + 1], "1")
        self.assertEqual(api[api.index("--host") + 1], "127.0.0.1")
        self.assertEqual(frontend, ["node", "/app/dashboard/server.js"])

    def test_shutdown_kills_group_when_leader_has_already_exited(self):
        # Child process groups remain addressable after their leader exits. In
        # particular Next workers must not escape sibling-failure shutdown.
        from unittest.mock import Mock, patch
        leader = Mock(pid=123456)
        leader.poll.return_value = 0
        with patch.object(START.os, "killpg") as kill_group:
            START.stop_children([leader])
        self.assertEqual(kill_group.call_args_list[0].args, (123456, signal.SIGTERM))
        self.assertEqual(kill_group.call_args_list[-1].args, (123456, signal.SIGKILL))
        leader.wait.assert_called_once()

    def test_transient_permission_error_requires_proven_group_disappearance(self):
        from unittest.mock import patch
        with patch.object(START.os, "killpg", side_effect=[PermissionError(), PermissionError(),
                                                           ProcessLookupError()]) as kill_group:
            START.signal_group(123456, signal.SIGKILL)
        self.assertEqual([call.args for call in kill_group.call_args_list],
                         [(123456, signal.SIGKILL), (123456, 0), (123456, 0)])

    def test_persistent_permission_denial_is_not_ignored(self):
        from unittest.mock import patch
        denied = PermissionError("Owned process group remains inaccessible")
        with (patch.object(START.os, "killpg", side_effect=denied),
              patch.object(START.time, "monotonic", side_effect=[0, .1, .3]),
              patch.object(START.time, "sleep"), self.assertRaises(PermissionError) as caught):
            START.signal_group(123456, signal.SIGTERM)
        self.assertIs(caught.exception, denied)


class SupervisorTests(unittest.TestCase):
    def test_real_grandchild_is_stopped_after_its_leader_exits(self):
        with tempfile.TemporaryDirectory() as temporary:
            pid_file = Path(temporary) / "grandchild.pid"
            grandchild = ("import os,pathlib,time; "
                          f"pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid())); "
                          "time.sleep(30)")
            leader_code = ("import pathlib,subprocess,sys,time; "
                           f"subprocess.Popen([sys.executable,'-c',{grandchild!r}]); "
                           f"p=pathlib.Path({str(pid_file)!r}); "
                           "deadline=time.monotonic()+3\n"
                           "while not p.exists() and time.monotonic()<deadline: time.sleep(.02)\n"
                           "sys.exit(0 if p.exists() else 1)")
            leader = subprocess.Popen([sys.executable, "-c", leader_code], start_new_session=True,
                                      env={"PATH": os.defpath})
            try:
                self.assertEqual(leader.wait(timeout=5), 0)
                pid = int(pid_file.read_text())
                START.stop_children([leader])
                deadline = time.monotonic() + 2
                while True:
                    state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                                           capture_output=True, text=True, timeout=1,
                                           check=False).stdout.strip()
                    if not state or state.startswith("Z"):
                        break
                    if time.monotonic() >= deadline:
                        self.fail("Grandchild remained live after its process group was stopped")
                    time.sleep(.03)
            finally:
                START.signal_group(leader.pid, signal.SIGKILL)
                leader.wait(timeout=2)

    def run_scenario(self, scenario):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / "apps/api/reeftrace_api").mkdir(parents=True)
            (folder / "apps/api/reeftrace_api/cloud.py").touch()
            (folder / "dashboard/.next").mkdir(parents=True)
            (folder / "dashboard/.next/BUILD_ID").write_text("offline-test")
            (folder / "dashboard/server.js").touch()
            script = f"""
import importlib.util, os, pathlib, sys
spec = importlib.util.spec_from_file_location('start', {str(Path(__file__).with_name('start.py'))!r})
start = importlib.util.module_from_spec(spec); spec.loader.exec_module(start)
root = pathlib.Path({str(folder)!r})
os.environ.clear()
os.environ.update({{'PATH':{os.defpath!r}, 'REEFTRACE_LOCAL_TOKEN':'x'*32,
                   'REEFTRACE_DATA_DIR':str(root/'store'), 'CHALK_ROUTER_API_KEY':'dummy-private'}})
start.require_free_port = lambda port: None
start.commands = lambda root, port: (
    [sys.executable, '-c', {WORKER!r}, str(root), 'api', {'fail' if scenario == 'api_fail' else 'wait'!r}],
    [sys.executable, '-c', {WORKER!r}, str(root), 'next', {'fail' if scenario == 'next_fail' else 'wait'!r}])
start.healthy = lambda port, **kw: (root / ('api.ready' if port == 8000 else 'next.ready')).exists()
sys.exit(start.run(root, startup_timeout_s=2))
"""
            process = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, start_new_session=True,
                                       env={"PATH": os.defpath})
            try:
                if scenario in ("signal", "api_exit"):
                    deadline = time.monotonic() + 5
                    while not (folder / "next.ready").exists() and time.monotonic() < deadline:
                        if process.poll() is not None:
                            break
                        time.sleep(.03)
                    self.assertTrue((folder / "next.ready").exists(), "Fake Next never started")
                    if scenario == "signal":
                        process.send_signal(signal.SIGTERM)
                    else:
                        os.kill(json.loads((folder / "api.json").read_text())["pid"], signal.SIGTERM)
                stdout, stderr = process.communicate(timeout=7)
                self.assertIn(process.returncode, (1, 128 + signal.SIGTERM), (stdout, stderr))
                api = json.loads((folder / "api.json").read_text())
                self.assertEqual(api["env"]["CHALK_ROUTER_API_KEY"], "dummy-private")
                if scenario != "api_fail":
                    self.assertTrue((folder / "api.stopped").exists())
                if scenario == "api_fail":
                    self.assertFalse((folder / "next.json").exists())
                else:
                    next_child = json.loads((folder / "next.json").read_text())
                    self.assertNotIn("CHALK_ROUTER_API_KEY", next_child["env"])
                    self.assertNotIn("REEFTRACE_LOCAL_TOKEN", next_child["env"])
                    if scenario != "next_fail":
                        self.assertTrue((folder / "next.stopped").exists())
                self.assertNotIn("dummy-private", stdout + stderr)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=2)
                for name in ("api", "next"):
                    record = folder / (name + ".json")
                    if record.exists():
                        START.signal_group(json.loads(record.read_text())["pid"], signal.SIGKILL)

    def test_sigterm_stops_both_process_groups(self):
        self.run_scenario("signal")

    def test_api_exit_stops_frontend(self):
        self.run_scenario("api_exit")

    def test_failed_api_never_starts_frontend(self):
        self.run_scenario("api_fail")

    def test_failed_frontend_stops_api(self):
        self.run_scenario("next_fail")


if __name__ == "__main__":
    unittest.main()
