"""Isolation, failure semantics and owned-process cleanup for the HTTP CI harness."""

from __future__ import annotations

import copy
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


def version_fixture(version, *, scored=0):
    """Minimal invented HTTP envelope; never a real forecast or scored study."""
    return {"report": {"study_id": "matched-current-gdp-hycom-15m-" + version,
        "physical_validation": False, "automatic_model_promotion": False,
        "scores": {"planned_group_count": 2, "planned_cell_count": 36,
            "planned_distinct_target_count": 12, "scored_cell_count": scored,
            "automatic_winner_selected": False,
            "groups": [{"candidates": [{"cells": [{} for _ in range(6)]}
                                        for _ in range(3)]} for _ in range(2)]}},
        "artifact_identity": {"study_id": "matched-current-gdp-hycom-15m-" + version,
            "report_sha256": ("a" if version == "v1" else "c") * 64,
            "protocol_sha256": ("b" if version == "v1" else "d") * 64,
            "integrity_verified": True, "result_pin_verified": True,
            "numeric_replay_verified": False}}


def version_requests(v1, v2=None, *, mutate_review=None):
    calls = []

    def req(path, body=None, *, expected=200, auth=True):
        calls.append((path, copy.deepcopy(body), expected, auth))
        version = (body or {}).get("study_version", path.partition("study_version=")[2] or "v1")
        status, result = 200, None
        if version not in {"v1", "v2"}:
            status = 422
        elif version == "v2" and v2 is None:
            status = 404
        elif body is None:
            result = v1 if version == "v1" else v2
        elif not auth:
            status = 401
        else:
            selected = v1 if version == "v1" else v2
            identity = selected["artifact_identity"]
            if any(body[key] != identity[key] for key in ("report_sha256", "protocol_sha256")):
                status = 409
            else:
                result = {"action": "STOP", "failure_code": "NOT_CONFIGURED",
                    "live_model_response": False, "research_report": selected["report"],
                    "artifact_identity": identity, "store_written": False,
                    "hardware_actuation": False}
                if mutate_review:
                    mutate_review(result)
        assert status == expected
        return copy.deepcopy(result)

    return req, calls


def checked(name, passed, **detail):
    assert passed, name


def test_version_audit_absent_identity_demands_404_without_reader_or_fallback(tmp_path, monkeypatch):
    from apps.ocean.reeftrace_ocean import matched_current_result as reader

    def forbidden(*args, **kwargs):
        pytest.fail("Absent v2 identity attempted reader, store or invented evidence")

    monkeypatch.setattr(reader, "load_frozen_matched_current_result", forbidden)
    v1 = version_fixture("v1")
    req, calls = version_requests(v1)
    result = audit.matched_version_checks(req, checked, v1_snapshot=v1,
                                          store_digest=forbidden, root=tmp_path)
    assert result == {"status": "TRUSTED_RESULT_ABSENT_HTTP404", "study_version": "v2"}
    assert calls[-1] == ("/research/matched-current?study_version=v2", None, 404, False)
    assert not any(body and body.get("study_version") == "v2" for _, body, _, _ in calls)


@pytest.mark.parametrize("scored", [0, 18, 36])
def test_version_audit_accepts_authoritative_results_without_assuming_v2_numeric_outcome(
    tmp_path, monkeypatch, scored,
):
    from apps.ocean.reeftrace_ocean import matched_current_result as reader

    path = tmp_path / "apps/ocean/reeftrace_ocean/matched_current_v2_result_identity.py"
    path.parent.mkdir(parents=True)
    path.write_text("# invented presence marker, never imported\n")
    v1, v2 = version_fixture("v1"), version_fixture("v2", scored=scored)
    loads = []

    def load(**kwargs):
        loads.append(kwargs)
        return copy.deepcopy(v2)

    monkeypatch.setattr(reader, "load_frozen_matched_current_result", load)
    req, calls = version_requests(v1, v2)
    result = audit.matched_version_checks(req, checked, v1_snapshot=v1,
                                          store_digest=lambda: "e" * 64, root=tmp_path)
    assert loads == [{"root": tmp_path, "study_version": "v2"}]
    assert result["scored_cells"] == scored and result["planned_cells"] == 36
    assert result["store_unchanged"] is True
    assert any(body and body.get("study_version") == "v2" and expected == 409
               and body["report_sha256"] == v1["artifact_identity"]["report_sha256"]
               for _, body, expected, _ in calls)


@pytest.mark.parametrize("change", ["reader_mismatch", "wrong_version", "promoted", "store_write"])
def test_version_audit_fails_changed_reader_identity_promotion_or_store(tmp_path, monkeypatch, change):
    from apps.ocean.reeftrace_ocean import matched_current_result as reader

    path = tmp_path / "apps/ocean/reeftrace_ocean/matched_current_v2_result_identity.py"
    path.parent.mkdir(parents=True)
    path.write_text("# invented presence marker\n")
    v1, v2 = version_fixture("v1"), version_fixture("v2")
    authoritative = copy.deepcopy(v2)
    if change == "reader_mismatch":
        v2["report"]["scores"]["scored_cell_count"] = 1
    elif change == "wrong_version":
        v2["report"]["study_id"] = v1["report"]["study_id"]
        authoritative = copy.deepcopy(v2)
    elif change == "promoted":
        v2["report"]["automatic_model_promotion"] = True
        authoritative = copy.deepcopy(v2)
    monkeypatch.setattr(reader, "load_frozen_matched_current_result", lambda **kwargs: authoritative)
    req, _ = version_requests(v1, v2)
    digests = iter(["e" * 64, "f" * 64] if change == "store_write" else ["e" * 64] * 2)
    with pytest.raises(AssertionError):
        audit.matched_version_checks(req, checked, v1_snapshot=v1,
                                     store_digest=lambda: next(digests), root=tmp_path)
