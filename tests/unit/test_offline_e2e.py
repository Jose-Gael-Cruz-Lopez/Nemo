"""Isolation, failure semantics and owned-process cleanup for the HTTP CI harness."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import pytest

from scripts import e2e_offline as audit


def test_child_environment_cannot_inherit_live_stores_credentials_or_proxies(tmp_path):
    parent = {"PATH": os.environ["PATH"], "CHALK_ENABLED": "true", "PHOTON_ENABLED": "true",
        "CHALK_ROUTER_API_KEY": "private-chalk", "PHOTON_API_KEY": "private-photon",
        "GROK_VOICE_ENABLED": "true", "XAI_API_KEY": "private-xai",
        "GOOGLE_API_KEY": "private-google", "OPENAI_API_KEY": "private-openai",
        "ANTHROPIC_API_KEY": "private-anthropic", "REEFTRACE_DATA_DIR": "/live-store",
        "REEFTRACE_LOCAL_TOKEN": "private-live-operator", "AUDIT_STORE": "/inherited-audit",
        "PYTHONPATH": "/untrusted-module-path", "HTTP_PROXY": "https://private-proxy",
        "https_proxy": "https://private-lowercase-proxy", "NO_PROXY": "external.test"}
    before = parent.copy()
    child = audit.child_environment(parent, tmp_path, "ephemeral-test-token", "test-nonce", 49152)
    assert parent == before
    assert child["CHALK_ENABLED"] == child["PHOTON_ENABLED"] == child["GROK_VOICE_ENABLED"] == "false"
    assert child["PHOTON_ROUTES_JSON"] == "[]"
    assert child["AUDIT_STORE"] == str(tmp_path / "store")
    assert child["AUDIT_OPERATOR_TOKEN"] == "ephemeral-test-token"
    assert child["AUDIT_PROCESS_NONCE"] == "test-nonce"
    assert child["PYTHONPATH"] == str(audit.ROOT)
    assert child["NO_PROXY"] == "127.0.0.1,localhost,::1"
    assert not any("private-" in value or "/live-store" in value for value in child.values())
    assert not any(key.upper() in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"} for key in child)


def test_proxy_environment_is_restored_even_after_an_audit_failure(monkeypatch):
    for key in list(os.environ):
        if key.upper() in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"}:
            monkeypatch.delenv(key)
    monkeypatch.setenv("http_proxy", "https://unit-test-proxy")
    monkeypatch.setenv("NO_PROXY", "existing.test")
    with pytest.raises(RuntimeError, match="intentional"), audit.loopback_proxy_environment():
        assert "http_proxy" not in os.environ
        assert os.environ["NO_PROXY"] == "127.0.0.1,localhost,::1"
        raise RuntimeError("intentional")
    assert os.environ["http_proxy"] == "https://unit-test-proxy"
    assert os.environ["NO_PROXY"] == "existing.test"


def test_process_deadline_kills_only_the_owned_child_and_it_is_reaped():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    began = time.monotonic()
    try:
        with audit.process_deadline(child, 0.05) as expired:
            child.wait(timeout=3)
            assert expired.is_set()
        assert child.returncode is not None and child.returncode != 0
        assert time.monotonic() - began < 3
    finally:
        audit.terminate_owned_process(child)


def test_normal_child_exit_cancels_the_deadline_without_marking_expired():
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    try:
        with audit.process_deadline(child, 5) as expired:
            assert child.wait(timeout=3) == 0
        assert not expired.is_set()
    finally:
        audit.terminate_owned_process(child)


@pytest.mark.parametrize("counts", [
    {}, {"guard_receipt_missing": True},
    {**dict.fromkeys(audit.GUARD_KEYS, 0), "camera_open_attempts": 1},
    {**dict.fromkeys(audit.GUARD_KEYS, 0), "provider_http_attempts": False},
    {**dict.fromkeys(audit.GUARD_KEYS, 0), "unknown_guard": 0},
])
def test_missing_or_nonzero_guard_counters_cannot_claim_an_offline_pass(counts):
    assert not audit.guards_clean(counts)


def test_all_four_explicit_zero_integer_counters_are_required():
    assert audit.guards_clean(dict.fromkeys(audit.GUARD_KEYS, 0))


def summary_fixture():
    return {"extra_checks": [{"check": "real HTTP workflow", "status": "PASS"}],
        "suite_reports": {"source": {"checks": [
            {"check": name, "status": "BLOCKED"} for name in audit.EXPECTED_BLOCKERS]},
            "prevention": {"checks": []}, "validation": {"checks": []}, "team": {"checks": []}}}


def test_intentional_external_blockers_never_become_live_product_or_physical_success():
    result = audit.summarize(summary_fixture())
    assert result["software_workflow_passed"] is True
    assert result["PASS"] == 1 and result["BLOCKED"] == 6 and result["FAIL"] == 0
    assert result["expected_external_scopes_blocked"] is True
    assert result["complete_live_product_verified"] is False
    assert result["physical_validation"] is False
    assert result["live_provider_round_trip_verified"] is False


def test_unexpected_blocker_missing_suite_or_real_failure_cannot_exit_successfully():
    for change in ("unexpected_blocker", "missing_suite", "failure"):
        result = summary_fixture()
        if change == "unexpected_blocker":
            result["extra_checks"].append({"check": "unexpected missing data", "status": "BLOCKED"})
        elif change == "missing_suite":
            del result["suite_reports"]["team"]
        else:
            result["extra_checks"].append({"check": "corrupt export", "status": "FAIL"})
        assert audit.summarize(result)["software_workflow_passed"] is False


def test_receipt_is_finite_bounded_and_over_budget_does_not_replace_existing_file(tmp_path):
    path = tmp_path / "audit.json"
    audit.write_receipt(path, {"software_workflow_passed": True})
    before = path.read_bytes()
    assert json.loads(before) == {"software_workflow_passed": True}
    with pytest.raises(ValueError, match="bounded size"):
        audit.write_receipt(path, {"oversized": "x" * audit.MAX_RECEIPT_BYTES})
    assert path.read_bytes() == before
    with pytest.raises(ValueError):
        audit.write_receipt(path, {"score": float("nan")})
    assert path.read_bytes() == before


@pytest.mark.parametrize("seconds", [-1, 0, 4.99, 241, float("inf"), float("nan")])
def test_invalid_total_deadline_rejected_before_any_server_can_start(seconds, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Invalid deadline started a process")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    with pytest.raises(ValueError, match="deadline"):
        audit.run_audit(seconds)
