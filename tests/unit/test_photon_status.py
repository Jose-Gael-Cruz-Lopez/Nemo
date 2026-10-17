"""Configuration alone must not claim a running messaging worker."""
from types import SimpleNamespace

import pytest

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.services.runtime import Runtime


def test_disabled_photon_does_not_claim_running_worker(tmp_path):
    runtime = Runtime(Settings(data_dir=tmp_path))
    result = runtime.photon_status()
    assert result["enabled"] is False and result["worker_running"] is False
    assert result["connection_verified"] is False


@pytest.mark.parametrize("done,ready,expected", [(False, True, True), (True, True, False), (False, False, False)])
def test_actual_worker_task_and_authorization_control_running_status(tmp_path, done, ready, expected):
    runtime = Runtime(Settings(data_dir=tmp_path))
    runtime.photon_worker = SimpleNamespace(readiness=lambda: {
        "enabled": True, "ready": ready, "connection_verified": False,
        "reasons": [] if ready else ["authorization_failed_restart_required"]})
    runtime.photon_task = SimpleNamespace(done=lambda: done)
    result = runtime.photon_status()
    assert result["worker_running"] is expected
    assert result["connection_verified"] is False
    assert result["ready"] is ready
