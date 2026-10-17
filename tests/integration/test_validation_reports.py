"""Real SQLite/API identity and accounting checks, never physical validation.

Reuse explicit policy-fixture constructors from the evidence-export tests.
Providers, messages and camera capture remain disabled.
"""

import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from test_evidence_export import add_trial, seed

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.api.reeftrace_api.schemas.validation_reports import VERIFICATION, ValidationReportInput
from apps.api.reeftrace_api.services.validation_reports import (
    VALIDATION_KIND,
    accept_validation_report,
    get_validation_report,
    list_validation_reports,
    template_validation_report,
)

AUTH = {"Authorization": "Bearer validation-test-only"}
ROOT = "/api/v1/prevention/comparisons/"


@pytest.fixture
def app(tmp_path, monkeypatch):
    for name in ("CHALK_ENABLED", "PHOTON_ENABLED", "GROK_VOICE_ENABLED"):
        monkeypatch.setenv(name, "false")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "[]")
    return create_app(Settings(data_dir=tmp_path, local_token="validation-test-only"))


def save(runtime, comparison_id, report=None):
    report = report or template_validation_report(runtime, comparison_id)
    return accept_validation_report(runtime, comparison_id, ValidationReportInput(report=report))


def test_template_uses_only_current_existing_origin_trials_and_never_persists_outcomes(app):
    runtime = app.state.runtime
    c = seed(runtime)["comparison"]
    add_trial(runtime, c["id"])
    manifest = template_validation_report(runtime, c["id"])
    trials = runtime.prevention.comparison_detail(c["id"])["trials"]
    assert manifest["purpose"] == "CONTRACT_REHEARSAL"
    assert manifest["development_trial_ids"] == []
    assert manifest["validation_trial_ids"] == [trials[0]["id"]]
    assert manifest["data_origin"] == "SYNTHETIC"
    assert runtime.store.list(VALIDATION_KIND) == []
    assert runtime.store.get("estimate", c["source_evidence_id"])["status"] == "unknown"
    assert runtime.camera.status()["running"] is False
    assert runtime.photon_settings().enabled is False
    with pytest.raises(ValueError, match="physical"):
        template_validation_report(runtime, c["id"], "OPERATOR_REPORTED_PHYSICAL")


def test_zero_recorded_selected_origin_has_no_rehearsal_template_or_saved_receipt(app):
    runtime = app.state.runtime
    c = seed(runtime, origin="MEASURED_TANK")["comparison"]
    add_trial(runtime, c["id"])
    with pytest.raises(ValueError, match="no recorded trials"):
        template_validation_report(runtime, c["id"], "OPERATOR_REPORTED_PHYSICAL")
    with TestClient(app) as client:
        response = client.get(ROOT + c["id"] + "/validation-template?origin=OPERATOR_REPORTED_PHYSICAL",
                              headers=AUTH)
        assert response.status_code == 409
        assert "no recorded trials" in response.json()["detail"]
    assert runtime.store.list(VALIDATION_KIND) == []


def test_empty_validation_partition_is_rejected_even_when_all_trials_are_development(app):
    runtime = app.state.runtime
    c = seed(runtime)["comparison"]
    add_trial(runtime, c["id"])
    manifest = template_validation_report(runtime, c["id"])
    manifest.update(purpose="DECLARED_VALIDATION_SPLIT",
                    development_trial_ids=manifest["validation_trial_ids"], validation_trial_ids=[])
    with pytest.raises(ValueError, match="at least 1"):
        save(runtime, c["id"], manifest)
    assert runtime.store.list(VALIDATION_KIND) == []


def test_saved_accounting_keeps_unknowns_denominators_and_immutable_idempotency(app):
    runtime = app.state.runtime
    c = seed(runtime)["comparison"]
    add_trial(runtime, c["id"], outcome="unresolved", entry_time_s=None,
              token_accounted=False, horizon_completed=False)
    detail = save(runtime, c["id"])
    assert detail == save(runtime, c["id"])
    assert len(runtime.store.list(VALIDATION_KIND)) == 1
    assert detail["report"]["verification"] == VERIFICATION
    assert detail["report"]["case_id"] == c["case_id"]
    assert detail["report"]["source_evidence_id"] == c["source_evidence_id"]
    assert detail["checks"] == {"identity_verified": True, "accounting_verified": True,
                                "method_rerun": False, "physical_validation": False}
    summary = detail["summary"]
    assert (summary["development_count"], summary["validation_count"], summary["missing_planned"],
            summary["unresolved"]) == (0, 1, 7, 1)
    row = next(row for row in summary["by_source"] if row["source_id"] == "A" and row["layout"] == "baseline")
    assert row["released"] == 1 and row["planned"] == 2 and row["missing_planned"] == 1
    assert row["entry_rate_bounds"] == {"lower": 0.0, "upper": 1.0, "denominator": 2,
                                        "kind": "planned_slots_missing_and_unresolved_are_unknown"}
    assert row["observed_entry_rate_bounds"]["denominator"] == 1
    assert summary["physical_validation"] is False and summary["supports_causal_claim"] is False
    assert summary["calibrated_probability"] is False
    assert summary["next_measurement"]["action"] == "COMPLETE_FROZEN_PLAN"
    assert get_validation_report(runtime, detail["report"]["id"]) == detail
    assert list_validation_reports(runtime, c["id"])[0]["id"] == detail["report"]["id"]


@pytest.mark.parametrize("field,value", [
    ("input_payload_sha256", "0" * 64), ("evaluation_snapshot_hash", "0" * 64),
    ("comparison_id", "comparison-other"), ("data_origin", "MEASURED_TANK"),
    ("outcome_origin", "OPERATOR_REPORTED_PHYSICAL"),
])
def test_import_rejects_wrong_frozen_identity_and_origin(app, field, value):
    runtime = app.state.runtime
    c = seed(runtime)["comparison"]
    add_trial(runtime, c["id"])
    manifest = template_validation_report(runtime, c["id"])
    manifest[field] = value
    with pytest.raises(ValueError):
        save(runtime, c["id"], manifest)
    assert runtime.store.list(VALIDATION_KIND) == []


@pytest.mark.parametrize("change", ["extra_metric", "duplicate", "overlap", "missing_trial", "other_trial"])
def test_split_manifest_rejects_uploaded_metrics_duplicates_overlap_and_cherry_picking(app, change):
    runtime = app.state.runtime
    c = seed(runtime)["comparison"]
    add_trial(runtime, c["id"])
    manifest = template_validation_report(runtime, c["id"])
    trial_id = manifest["validation_trial_ids"][0]
    if change == "extra_metric":
        manifest["accuracy"] = 1.0
    elif change == "duplicate":
        manifest["validation_trial_ids"].append(trial_id)
    elif change == "overlap":
        manifest.update(purpose="DECLARED_VALIDATION_SPLIT", development_trial_ids=[trial_id])
    elif change == "missing_trial":
        manifest["validation_trial_ids"] = []
    else:
        manifest["validation_trial_ids"] = ["trial-other"]
    with pytest.raises(ValueError):
        save(runtime, c["id"], manifest)
    assert runtime.store.list(VALIDATION_KIND) == []


def test_development_trials_never_count_as_validation_and_splits_have_canonical_identity(app):
    runtime = app.state.runtime
    c = seed(runtime)["comparison"]
    add_trial(runtime, c["id"], key="dev-release")
    add_trial(runtime, c["id"], key="validation-release")
    manifest = template_validation_report(runtime, c["id"])
    first, second = manifest["validation_trial_ids"]
    manifest.update(purpose="DECLARED_VALIDATION_SPLIT", protocol_id="declared-pilot-v1",
                    development_trial_ids=[first], validation_trial_ids=[second])
    detail = save(runtime, c["id"], manifest)
    summary = detail["summary"]
    assert summary["development_count"] == summary["validation_count"] == 1
    assert summary["missing_planned"] == 7
    assert sum(row["released"] for row in summary["by_source"]) == 1
    assert detail["checks"]["method_rerun"] is False
    # The verifier checks declared references, not independent scientific behavior.
    assert any("not proof of independence" in text for text in summary["limitations"])


def test_unsupported_layout_requests_drift_before_more_trials_without_inventing_coordinates(app, monkeypatch):
    import test_evidence_export as fixtures

    original = fixtures.fit_flow

    def sparse_flow(*args, **kwargs):
        kwargs["coverage_radius_cm"] = 0.1
        return original(*args, **kwargs)

    monkeypatch.setattr(fixtures, "fit_flow", sparse_flow)
    runtime = app.state.runtime
    c = seed(runtime)["comparison"]
    assert c["numerical_report"]["status"] == "WITHHELD_UNSUPPORTED_FLOW"
    add_trial(runtime, c["id"])
    detail = save(runtime, c["id"])
    next_measurement = detail["summary"]["next_measurement"]
    assert next_measurement["action"] == "MEASURE_LAYOUT_DRIFT"
    assert next_measurement["layout"] in {"baseline", "intervention"}
    assert next_measurement["source_id"] in c["plan"]["source_ids"]
    assert next_measurement["scenario_id"] == "nominal"
    assert next_measurement["location_cm"] is None
    for row in detail["summary"]["by_source"]:
        nominal = next(prediction for prediction in c["numerical_report"]["results"]
                       if prediction["source_id"] == row["source_id"] and prediction["scenario_id"] == "nominal")
        expected = nominal[row["layout"]]
        assert expected["unsupported_count"] > 0
        assert row["predicted_entry_fraction"] is None
        assert row["predicted_entry_bounds"] == {"lower": expected["zone_entry_lower_fraction"],
                                                 "upper": expected["zone_entry_upper_fraction"]}


def test_completed_plan_with_development_exclusions_requests_new_protocol_not_over_quota_releases(app):
    runtime = app.state.runtime
    c = seed(runtime)["comparison"]
    for index, slot in enumerate(c["plan"]["sequence"]):
        add_trial(runtime, c["id"], key=f"release-{index}", layout=slot["layout"], source_id=slot["source_id"])
    manifest = template_validation_report(runtime, c["id"])
    all_ids = manifest["validation_trial_ids"]
    manifest.update(purpose="DECLARED_VALIDATION_SPLIT", protocol_id="declared-split-v1",
                    development_trial_ids=all_ids[:4], validation_trial_ids=all_ids[4:])
    detail = save(runtime, c["id"], manifest)
    assert detail["summary"]["validation_count"] == detail["summary"]["development_count"] == 4
    assert detail["summary"]["missing_planned"] == 4
    assert detail["summary"]["next_measurement"]["action"] == "DECLARE_NEW_INDEPENDENT_PROTOCOL"
    assert detail["checks"]["method_rerun"] is False


def test_selected_physical_and_synthetic_origin_rates_are_never_pooled(app):
    runtime = app.state.runtime
    c = seed(runtime, origin="MEASURED_TANK")["comparison"]
    add_trial(runtime, c["id"], key="synthetic-release")
    add_trial(runtime, c["id"], key="reported-physical", data_origin="OPERATOR_REPORTED_PHYSICAL",
              physical_confirmed=True, outcome="unresolved", entry_time_s=None,
              token_accounted=False, horizon_completed=False)
    for origin, expected_entries in (("SYNTHETIC_DEMO", 1), ("OPERATOR_REPORTED_PHYSICAL", 0)):
        manifest = template_validation_report(runtime, c["id"], origin)
        detail = save(runtime, c["id"], manifest)
        assert detail["summary"]["validation_count"] == 1
        assert sum(row["zone_entries"] for row in detail["summary"]["by_source"]) == expected_entries
        assert detail["report"]["outcome_origin"] == origin
        assert detail["checks"]["physical_validation"] is False


def test_validation_recording_cannot_be_reused_from_flow_fitting(app):
    runtime = app.state.runtime
    c = seed(runtime, origin="MEASURED_TANK")["comparison"]
    # Explicit policy fixture: make a prospective recorder-shaped artifact whose
    # ID is deliberately also listed in the frozen baseline's fit provenance.
    start = c["created_at"] + 1
    frame = runtime.store.put("frame", {"received_utc": datetime.fromtimestamp(start + 0.1, UTC).isoformat()})
    recording = runtime.store.put("recording", {"profile_id": c["baseline_profile_id"],
        "data_origin": "MEASURED_TANK", "recorded_at": start + 10,
        "points": [{"frame_id": frame["id"], "t_s": 0.1}], "evidence_frame_ids": [frame["id"]]},
        "baseline-train")
    add_trial(runtime, c["id"], data_origin="OPERATOR_REPORTED_PHYSICAL", physical_confirmed=True,
              recording_id=recording["id"])
    manifest = template_validation_report(runtime, c["id"], "OPERATOR_REPORTED_PHYSICAL")
    with pytest.raises(ValueError, match="fit or validate"):
        save(runtime, c["id"], manifest)
    assert runtime.store.list(VALIDATION_KIND) == []


@pytest.mark.parametrize("change", ["trial", "stop"])
def test_concurrent_lineage_change_during_accounting_cannot_commit_stale_report(app, monkeypatch, change):
    import apps.api.reeftrace_api.services.validation_reports as verifier

    runtime = app.state.runtime
    c = seed(runtime)["comparison"]
    add_trial(runtime, c["id"], key="initial-release")
    manifest = template_validation_report(runtime, c["id"])
    original = verifier._summary

    def change_after_read(*args):
        summary = original(*args)
        if change == "trial":
            add_trial(runtime, c["id"])
        else:
            runtime.store.stop_case(c["case_id"])
        return summary

    monkeypatch.setattr(verifier, "_summary", change_after_read)
    with pytest.raises(ValueError):
        save(runtime, c["id"], manifest)
    assert runtime.store.list(VALIDATION_KIND) == []


def test_concurrent_identical_manifest_commits_one_immutable_receipt(app):
    runtime = app.state.runtime
    c = seed(runtime)["comparison"]
    add_trial(runtime, c["id"], key="initial-release")
    manifest = template_validation_report(runtime, c["id"])
    with ThreadPoolExecutor() as pool:
        calls = [pool.submit(save, runtime, c["id"], copy.deepcopy(manifest)) for _ in range(2)]
        responses = [future.result(timeout=10) for future in calls]
    assert responses[0] == responses[1]
    assert len(runtime.store.list(VALIDATION_KIND)) == 1


@pytest.mark.parametrize("change,reason", [("trial", "EVALUATION_CHANGED"), ("stop", "CASE_CHANGED_OR_STOPPED")])
def test_saved_reports_remain_readable_but_archive_after_their_snapshot_changes(app, change, reason):
    runtime = app.state.runtime
    c = seed(runtime)["comparison"]
    add_trial(runtime, c["id"], key="initial-release")
    manifest = template_validation_report(runtime, c["id"])
    detail = save(runtime, c["id"], manifest)
    if change == "trial":
        add_trial(runtime, c["id"])
    else:
        runtime.store.stop_case(c["case_id"])
    archival = get_validation_report(runtime, detail["report"]["id"])
    assert archival["report"] == detail["report"]
    assert archival["summary"] == detail["summary"]
    assert archival["is_current"] is False and archival["archive_reason"] == reason
    with pytest.raises(ValueError):
        save(runtime, c["id"], manifest)
    assert list_validation_reports(runtime, c["id"])[0]["is_current"] is False


def test_http_operator_guard_template_import_list_and_archival_detail(app):
    runtime = app.state.runtime
    c = seed(runtime)["comparison"]
    add_trial(runtime, c["id"])
    base = ROOT + c["id"]
    with TestClient(app) as client:
        for path in ("/validation-template", "/validation-reports"):
            assert client.get(base + path).status_code == 401
        assert client.post(base + "/validation-reports", json={}).status_code == 401
        template = client.get(base + "/validation-template", headers=AUTH)
        assert template.status_code == 200, template.text
        manifest = template.json()
        accepted = client.post(base + "/validation-reports", headers=AUTH, json={"report": manifest})
        assert accepted.status_code == 200, accepted.text
        detail = accepted.json()
        report_id = detail["report"]["id"]
        url = base + "/validation-reports/" + report_id
        assert client.get(url).status_code == 401
        assert client.get(url, headers=AUTH).json() == detail
        assert client.get(base + "/validation-reports", headers=AUTH).json()[0]["id"] == report_id
        malformed = {**manifest, "metrics": {"accuracy": 1.0}}
        assert client.post(base + "/validation-reports", headers=AUTH,
                           json={"report": malformed}).status_code == 422
        runtime.store.stop_case(c["case_id"])
        assert client.get(url, headers=AUTH).json()["archive_reason"] == "CASE_CHANGED_OR_STOPPED"
        assert client.post(base + "/validation-reports", headers=AUTH,
                           json={"report": manifest}).status_code == 409
