"""Actual pinned method replay, never parse-only trust or current-case relabeling."""

import copy
import json
import socket
import sqlite3

import pytest

from apps.api.reeftrace_api.services import method_validation as service


def test_pinned_examples_rerun_actual_validator_and_match_shared_report(monkeypatch):
    original = service.validate_bundle
    calls = []

    def checked(bundle, **kwargs):
        calls.append(kwargs)
        return original(bundle, **kwargs)

    monkeypatch.setattr(service, "validate_bundle", checked)
    result = service.run_prevention_method_example()
    assert result["schema_version"] == "prevention_method_replay_v1"
    assert result["kind"] == "SYNTHETIC_REPLAY_EXAMPLE"
    assert result["not_current_case"] is True and result["physical_validation"] is False
    assert result["method_rerun"] is True and result["examples_are_independent"] is False
    assert len(calls) == 2 and all(call == {"development_protocol_id": service.DEVELOPMENT_PROTOCOL,
                                         "validation_protocol_id": service.VALIDATION_PROTOCOL} for call in calls)
    unresolved, positive = result["examples"]
    assert unresolved["provenance"]["expected_report_match"] is True
    assert unresolved["report"]["next_measurement"]["source_id"] == "B"
    assert unresolved["report"]["selected_layout_usefulness"]["SYNTHETIC_DEMO"]["status"] == "UNRESOLVED_ON_REPORTED_NEW_TRIALS"
    assert positive["report"]["selected_layout_usefulness"]["SYNTHETIC_DEMO"]["status"] == "DESCRIPTIVELY_USEFUL_ON_REPORTED_NEW_TRIALS"
    for example in result["examples"]:
        report = example["report"]
        assert report["numerical_replay_verified"] is True
        assert report["by_origin"]["OPERATOR_REPORTED_PHYSICAL"]["plan"]["recorded_total"] == 0
        assert report["by_origin"]["SYNTHETIC_DEMO"]["plan"]["recorded_total"] == 8
        assert report["physical_validation"] is False
    assert result == service.run_prevention_method_example()
    json.dumps(result, allow_nan=False)


def test_actual_validator_output_cannot_replace_shared_receipt_with_rehashed_fiction(monkeypatch):
    original = service.validate_bundle

    def changed(*args, **kwargs):
        report = copy.deepcopy(original(*args, **kwargs))
        report["next_measurement"]["kind"] = "INVENTED_OPTIMAL_MEASUREMENT"
        return report

    monkeypatch.setattr(service, "validate_bundle", changed)
    with pytest.raises(ValueError, match="pinned shared report"):
        service.run_prevention_method_example()


@pytest.mark.parametrize("key", list(service.FIXTURES))
def test_every_fixture_is_byte_pinned_before_method_runs(tmp_path, monkeypatch, key):
    for name, (relative, _) in service.FIXTURES.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = (service.ROOT / relative).read_bytes()
        target.write_bytes(raw + b" " if name == key else raw)
    monkeypatch.setattr(service, "ROOT", tmp_path)
    monkeypatch.setattr(service, "validate_bundle", lambda *a, **k: pytest.fail("Integrity failed before replay"))
    with pytest.raises(ValueError, match="integrity"):
        service.run_prevention_method_example()


def test_method_example_has_no_network_database_or_write_side_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Example must not access network, database or runtime state")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    assert service.run_prevention_method_example()["status"] == "COMPLETED"
