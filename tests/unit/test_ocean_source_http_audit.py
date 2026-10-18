"""Offline HTTP-harness contracts; synthetic interface fixtures, never scoring."""

from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys

import pytest

from apps.api.reeftrace_api.services import ocean_source_investigation as service
from scripts import e2e_offline as audit
from scripts import evaluate_ocean_source as frozen
from tests.integration.test_ocean_source_api import fake_snapshot


def checked(name, passed, **detail):
    assert passed, name


def setup_archive(tmp_path, monkeypatch):
    snapshot, pins = fake_snapshot(tutorial=True)
    directory = tmp_path / "data/research/ocean-source-v1"
    directory.mkdir(parents=True)
    (directory / "sentinel.json").write_text('{"synthetic_interface_sentinel":true}\n')
    monkeypatch.setattr(service, "_pins", lambda: pins)

    def read(path, *, expected_identity_sha256):
        assert path == directory and expected_identity_sha256 == pins.IDENTITY_SHA256
        return copy.deepcopy(snapshot)

    monkeypatch.setattr(frozen, "read_result", read)
    return directory, snapshot


def requests(snapshot, mutate_review=None):
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
            response = {"schema_version": 1, "kind": "OCEAN_SOURCE_RESEARCH_INVESTIGATION",
                "scope": "READ_ONLY_POST_OUTCOME_EARLIER_POSITION_DIAGNOSTIC",
                "analysis_scope": "POST_OUTCOME_EXPLORATORY", "previously_viewed_earlier_positions": True,
                "action": "STOP", "provider": "chalk", "failure_code": "NOT_CONFIGURED",
                "live_model_response": False, "research_report": copy.deepcopy(snapshot["report"]),
                "artifact_identity": copy.deepcopy(snapshot["artifact_identity"]), **pins,
                "evidence_ids": [], "trace": [], "numeric_replay_verified": False,
                "store_written": False, "hardware_actuation": False, "physical_validation": False,
                "source_attribution_validated": False, "automatic_model_promotion": False}
            if mutate_review:
                mutate_review(response)
        assert code == expected
        return copy.deepcopy(response)

    return req, calls


def test_http_audit_preserves_all_stages_branches_denominators_auth_and_pins(tmp_path, monkeypatch):
    directory, snapshot = setup_archive(tmp_path, monkeypatch)
    request, calls = requests(snapshot)
    before = (directory / "sentinel.json").read_bytes()
    result = audit.ocean_source_checks(request, checked, store_digest=lambda: "a" * 64, root=tmp_path)
    assert result["status"] == "PINNED_OCEAN_SOURCE_READ_ONLY_VERIFIED"
    assert result["pipeline_stage_ids"] == list(service.TUTORIAL_STAGES)
    assert result["pipeline_planned_validation_rows"] == 8
    assert result["pipeline_scored_validation_rows"] == 0
    assert result["store_unchanged"] is result["artifacts_unchanged"] is True
    assert result["numeric_replay_verified"] is result["live_model_response"] is False
    assert (directory / "sentinel.json").read_bytes() == before
    assert sum(expected == 401 for _, _, expected, _ in calls) == 1
    assert sum(expected == 422 for _, _, expected, _ in calls) == 10
    assert sum(expected == 409 for _, _, expected, _ in calls) == 3
    assert sum(body is None for _, body, _, _ in calls) == 2


@pytest.mark.parametrize("change", ["live", "report", "promotion", "replay", "evidence", "store", "artifacts"])
def test_http_audit_rejects_relabelled_review_and_writes(tmp_path, monkeypatch, change):
    directory, snapshot = setup_archive(tmp_path, monkeypatch)

    def mutate(value):
        if change == "live":
            value["live_model_response"] = True
        elif change == "report":
            value["research_report"]["pipeline_tutorial"]["validation"]["planned_rows"] = 7
        elif change == "promotion":
            value["automatic_model_promotion"] = True
        elif change == "replay":
            value["numeric_replay_verified"] = True
        elif change == "evidence":
            value["evidence_ids"] = ["fabricated"]
        elif change == "artifacts":
            (directory / "sentinel.json").write_text('{"changed":true}\n')

    request, _ = requests(snapshot, mutate)
    digests = iter(["a" * 64, "b" * 64] if change == "store" else ["a" * 64] * 2)
    with pytest.raises(AssertionError):
        audit.ocean_source_checks(request, checked, store_digest=lambda: next(digests), root=tmp_path)


def test_missing_publication_is_honest_404_never_a_score_or_fabricated_success(tmp_path, monkeypatch):
    calls = []

    def absent():
        raise FileNotFoundError("Scientific publication has not been created")

    def forbidden(*args, **kwargs):
        raise AssertionError("A missing publication must not run or read a scientific result")

    def request(path, body=None, *, expected=200, auth=True):
        calls.append((path, expected, auth))
        assert expected == (401 if body and not auth else 404)
        return {"detail": "Unavailable"}

    monkeypatch.setattr(service, "_pins", absent)
    monkeypatch.setattr(frozen, "read_result", forbidden)
    result = audit.ocean_source_checks(request, checked, store_digest=lambda: "a" * 64, root=tmp_path)
    assert result["status"] == "NOT_PUBLISHED_UNAVAILABLE_VERIFIED"
    assert result["http_status"] == 404
    assert len(calls) == 3 and result["numeric_replay_verified"] is False


def test_child_guard_covers_actual_separate_pipeline_functions():
    assert "ocean_source_execution_attempts" in audit.GUARD_KEYS
    for name in ("build_pipeline_forecasts", "score_pipeline_forecasts", "filter_three_positions",
                 "corrected_current_field", "build_ocean_source_forecasts",
                 "score_ocean_source_forecasts", "first_score"):
        assert name in audit.CHILD
    assert "from apps.ocean.reeftrace_ocean import ocean_source_pipeline as source_pipeline" in audit.CHILD
    clean = dict.fromkeys(audit.GUARD_KEYS, 0)
    assert audit.guards_clean(clean)
    assert not audit.guards_clean({**clean, "ocean_source_execution_attempts": 1})
    assert len(audit.EXPECTED_BLOCKERS) == 6
    assert json.loads(json.dumps(clean)) == clean


def test_child_installs_fail_fast_guards_on_real_source_and_pipeline_callables(tmp_path):
    """Exercise guard wiring in its own process; never enter any scientific body."""
    prefix = audit.CHILD.split("from apps.api.reeftrace_api.core.settings import Settings", 1)[0]
    verify = r'''
targets = [(source_model, name) for name in (
    "build_ocean_source_forecasts", "score_ocean_source_forecasts", "backtrack_current")]
targets += [(source_pipeline, name) for name in (
    "build_pipeline_forecasts", "score_pipeline_forecasts", "filter_three_positions",
    "corrected_current_field", "backtrack_current")]
targets.append((source_script, "first_score"))
for module, name in targets:
    function = getattr(module, name)
    # Check replacement BEFORE calling: a missed guard must not execute science.
    assert function.__name__ == "reject" and function.__globals__ is globals(), (module.__name__, name)
    try:
        function()
    except AssertionError as error:
        assert str(error) == "Isolated audit forbids ocean_source_execution_attempts"
    else:
        raise AssertionError("Scientific execution guard did not fail fast")
assert counts["ocean_source_execution_attempts"] == len(targets) == 9
assert all(value == 0 for key, value in counts.items() if key != "ocean_source_execution_attempts")
print(json.dumps(counts))
'''
    environment = audit.child_environment(os.environ, tmp_path, "TEST-NOT-A-LIVE-TOKEN", "test-nonce", 0)
    completed = subprocess.run([sys.executable, "-c", prefix + verify],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=30, check=True)
    counts = json.loads(completed.stdout)
    assert counts == {**dict.fromkeys(audit.GUARD_KEYS, 0), "ocean_source_execution_attempts": 9}
    assert json.loads((tmp_path / "guards.json").read_text()) == counts
