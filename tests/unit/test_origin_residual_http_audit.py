"""Guarded HTTP-harness contract checks; saved artifacts only, no model execution."""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys

import pytest

from scripts import e2e_offline as audit
from scripts import evaluate_origin_residual_diagnostic as frozen


@pytest.fixture(scope="module")
def saved_snapshot():
    from apps.ocean.reeftrace_ocean.origin_residual_result_identity import IDENTITY_SHA256

    return frozen.read_diagnostic(expected_identity_sha256=IDENTITY_SHA256)


def setup_archive(tmp_path, monkeypatch, snapshot):
    """A disposable hash-change sentinel, not a scientific result or acquisition."""
    directory = tmp_path / "data/research/origin-residual-v1"
    directory.mkdir(parents=True)
    (directory / "sentinel.json").write_text('{"synthetic_audit_sentinel":true}\n')
    calls = []

    def read(directory, *, expected_identity_sha256):
        calls.append((directory, expected_identity_sha256))
        return copy.deepcopy(snapshot)

    monkeypatch.setattr(frozen, "read_diagnostic", read)
    return directory, calls


def origin_requests(snapshot, *, mutate_review=None):
    calls = []
    pins = {key: snapshot["artifact_identity"][key] for key in (
        "report_sha256", "protocol_sha256", "identity_sha256")}

    def req(path, body=None, *, expected=200, auth=True):
        calls.append((path, copy.deepcopy(body), expected, auth))
        code, response = 200, None
        if body is None:
            response = snapshot
        elif not auth:
            code = 401
        elif (set(body) != {"question", *pins} or not isinstance(body["question"], str)
                or not body["question"].strip() or len(body["question"]) > 2000
                or any(not isinstance(body[key], str)
                       or re.fullmatch("[0-9a-f]{64}", body[key]) is None for key in pins)):
            code = 422
        elif any(body[key] != value for key, value in pins.items()):
            code = 409
        else:
            response = {"schema_version": 1, "kind": "ORIGIN_RESIDUAL_RESEARCH_INVESTIGATION",
                "scope": "READ_ONLY_POST_OUTCOME_EXPLORATORY_DIAGNOSTIC",
                "analysis_scope": "POST_OUTCOME_EXPLORATORY", "previously_viewed_target_outcomes": True,
                "action": "STOP", "provider": "chalk", "failure_code": "NOT_CONFIGURED",
                "live_model_response": False, "research_report": copy.deepcopy(snapshot["report"]),
                "artifact_identity": copy.deepcopy(snapshot["artifact_identity"]), **pins,
                "evidence_ids": [], "trace": [], "numeric_replay_verified": False,
                "store_written": False, "hardware_actuation": False, "physical_validation": False,
                "automatic_model_promotion": False}
            if mutate_review:
                mutate_review(response)
        assert code == expected
        return copy.deepcopy(response)

    return req, calls


def checked(name, passed, **detail):
    assert passed, name


def test_exploratory_http_audit_checks_auth_schema_every_pin_and_saved_metrics(
    tmp_path, monkeypatch, saved_snapshot,
):
    directory, reads = setup_archive(tmp_path, monkeypatch, saved_snapshot)
    req, calls = origin_requests(saved_snapshot)
    before = (directory / "sentinel.json").read_bytes()
    result = audit.origin_residual_checks(req, checked, store_digest=lambda: "a" * 64,
                                          root=tmp_path)
    assert len(reads) == 1 and reads[0][0] == directory
    assert result["primary_equal_id_macro_results"] == (
        saved_snapshot["report"]["scores"]["primary_equal_id_macro_results"])
    assert result["planned_cells"] == result["scored_cells"] == 48
    assert result["planned_distinct_targets"] == 12
    assert result["numeric_replay_verified"] is False
    assert result["store_unchanged"] is result["artifacts_unchanged"] is True
    assert (directory / "sentinel.json").read_bytes() == before
    assert sum(expected == 401 for _, _, expected, _ in calls) == 1
    assert sum(expected == 422 for _, _, expected, _ in calls) == 10
    stale = [body for _, body, expected, _ in calls if expected == 409]
    assert len(stale) == 3
    for key in ("report_sha256", "protocol_sha256", "identity_sha256"):
        assert any(body[key] == "0" * 64 for body in stale)
    assert sum(body is None for _, body, _, _ in calls) == 2


@pytest.mark.parametrize("change", ["replay", "scope", "report", "live", "evidence", "promotion",
                                     "store", "artifacts"])
def test_exploratory_audit_rejects_relabelled_answers_writes_and_changed_artifacts(
    tmp_path, monkeypatch, saved_snapshot, change,
):
    directory, _ = setup_archive(tmp_path, monkeypatch, saved_snapshot)

    def mutate(value):
        if change == "replay":
            value["numeric_replay_verified"] = True
        elif change == "scope":
            value["analysis_scope"] = "CONFIRMATORY"
        elif change == "report":
            value["research_report"]["scores"]["scored_cell_count"] = 47
        elif change == "live":
            value["live_model_response"] = True
        elif change == "evidence":
            value["evidence_ids"] = ["fabricated"]
        elif change == "promotion":
            value["automatic_model_promotion"] = True
        elif change == "artifacts":
            (directory / "sentinel.json").write_text('{"changed":true}\n')

    req, _ = origin_requests(saved_snapshot, mutate_review=mutate)
    digests = iter(["a" * 64, "b" * 64] if change == "store" else ["a" * 64] * 2)
    with pytest.raises(AssertionError):
        audit.origin_residual_checks(req, checked, store_digest=lambda: next(digests),
                                     root=tmp_path)


def test_child_scientific_execution_guard_is_required_for_any_success_claim():
    assert "origin_residual_execution_attempts" in audit.GUARD_KEYS
    for name in ("build_forecasts", "score_forecasts", "corrected_field", "first_score"):
        assert name in audit.CHILD
    clean = dict.fromkeys(audit.GUARD_KEYS, 0)
    assert audit.guards_clean(clean)
    assert not audit.guards_clean({**clean, "origin_residual_execution_attempts": 1})
    assert not audit.guards_clean({key: value for key, value in clean.items()
                                   if key != "origin_residual_execution_attempts"})
    assert len(audit.EXPECTED_BLOCKERS) == 6
    assert json.loads(json.dumps(clean)) == clean


def test_direct_script_import_scope_reaches_http_and_restores_sys_path(tmp_path):
    # A fresh process cannot borrow pytest's repository path or scripts imports.
    code = """
import importlib.util, pathlib, sys
root = pathlib.Path(sys.argv[1])
sys.path[:] = [entry for entry in sys.path if entry not in {str(root), str(root / 'scripts')}]
spec = importlib.util.spec_from_file_location('offline_direct_cli', root / 'scripts/e2e_offline.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
before = sys.path[:]
def request(*args, **kwargs):
    raise RuntimeError('PUBLIC_READ_REACHED_HTTP_SEAM')
try:
    audit.origin_residual_checks(request, lambda *args: None, store_digest=lambda: 'a' * 64)
except RuntimeError as error:
    assert str(error) == 'PUBLIC_READ_REACHED_HTTP_SEAM'
else:
    raise AssertionError('HTTP seam was not reached')
assert sys.path == before
"""
    result = subprocess.run([sys.executable, "-c", code, str(audit.ROOT)], cwd=tmp_path,
                            capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
