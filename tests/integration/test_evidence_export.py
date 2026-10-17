"""One real SQLite prevention ledger exported without providers or physical claims."""

import asyncio
import copy
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.api.reeftrace_api.schemas.evidence_export import AnalysisBundle, canonical_json
from apps.api.reeftrace_api.schemas.prevention import ComparisonInput, TrialInput
from apps.api.reeftrace_api.services.evidence_export import export_comparison
from apps.api.reeftrace_api.services.prevention import COMPARISON_KIND
from apps.transport.reeftrace_transport import fit_flow

AUTH = {"Authorization": "Bearer export-test-only"}
PRIVATE = "FAKE_PRIVATE_SENTINEL_email@example.test_+15555550123_/private/raw-frame.png"
FIXTURE = Path(__file__).parents[1] / "fixtures/team_handoff/analysis_bundle_v1.json"


@pytest.fixture
def app(tmp_path, monkeypatch):
    for key in ("CHALK_ENABLED", "PHOTON_ENABLED", "GROK_VOICE_ENABLED"):
        monkeypatch.setenv(key, "false")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "[]")
    return create_app(Settings(data_dir=tmp_path, local_token="export-test-only"))


def seed(runtime, origin="SYNTHETIC", source_ids=("A", "B")):
    """All origins here are policy fixtures, never physical measurement claims."""
    bounds = {"x_min_cm": 0, "x_max_cm": 10, "y_min_cm": 0, "y_max_cm": 10}
    samples = [{"x_cm": x, "y_cm": y, "vx_cm_s": 1, "vy_cm_s": 0}
               for x in (0, 5, 10) for y in (0, 5, 10)]
    flow = fit_flow(samples, bounds, validation_samples=copy.deepcopy(samples),
                    coverage_radius_cm=20, data_origin=origin)
    profiles = []
    for layout in ("baseline", "intervention"):
        frozen_flow = copy.deepcopy(flow)
        if origin == "MEASURED_TANK":
            frozen_flow["provenance"] = {"training_recording_ids": [layout + "-train"],
                                         "validation_recording_ids": [layout + "-validation"]}
            frozen_flow = runtime.store.put("flow", frozen_flow)
        profile = {"valid": True, "data_origin": origin, "bounds": bounds, "flow": frozen_flow,
            "sources": [{"id": source, "polygon_cm": [[1, y], [2, y], [2, y + 1], [1, y + 1]]}
                        for source, y in zip(source_ids, (2, 7), strict=True)],
            "token_class": "test-token", "calibration_id": "test-map",
            "max_validation_rmse_cm_s": 0.1,
            "transport": {"dt_s": 0.2, "max_age_s": 20, "diffusivity_cm2_s": 0.01},
            "traps": [] if layout == "baseline" else [{"id": "mesh", "validated": True,
                "retention": "absorbing", "polygon_cm": [[5, 1], [6, 1], [6, 9], [5, 9]]}],
            "private_unrecognized_field": PRIVATE}
        profiles.append(runtime.store.put("profile", profile))
    case = runtime.store.add_case({"profile_id": profiles[0]["id"], "mode": "REPLAY",
                                  "points": [], "evidence_frame_ids": [], "true_source": PRIVATE})
    runtime.store.put_case_result("estimate", {"case_id": case["id"], "status": "unknown",
        "data_origin": origin, "profile_id": profiles[0]["id"], "explanation": PRIVATE,
        "true_source": PRIVATE}, case["id"], case["revision"], changes={"state": "INVESTIGATE"})
    return asyncio.run(runtime.prevention.create_comparison(ComparisonInput(
        case_id=case["id"], baseline_profile_id=profiles[0]["id"],
        intervention_profile_id=profiles[1]["id"],
        protected_zone_cm=[[8, 1], [9, 1], [9, 9], [8, 9]],
        name=PRIVATE[:120], horizon_s=10, particles=20, trials_per_source=2)))


def add_trial(runtime, comparison_id, key="export-release", **changes):
    body = {"trial_key": key, "layout": "baseline", "source_id": "A",
        "data_origin": "SYNTHETIC_DEMO", "outcome": "zone_entry", "entry_time_s": 7.0,
        "interception_time_s": None, "token_accounted": True, "physical_confirmed": False,
        "horizon_completed": True, "note": PRIVATE, "recording_id": None, **changes}
    return runtime.prevention.add_trial(comparison_id, TrialInput(**body))


def change_record(runtime, kind, record_id, change):
    original = runtime.store.get(kind, record_id)
    updated = copy.deepcopy(original)
    change(updated)
    with runtime.store.connection() as db:
        db.execute("UPDATE records SET payload=? WHERE kind=? AND id=?",
                   (json.dumps(updated), kind, record_id))
    return original


def test_bundle_is_deterministic_round_trippable_bounded_and_redacted(app):
    runtime = app.state.runtime
    detail = seed(runtime)
    cid = detail["comparison"]["id"]
    add_trial(runtime, cid)
    runtime.store.put("unrelated", {"secret": PRIVATE})
    bundle = export_comparison(runtime, cid)
    again = export_comparison(runtime, cid)
    assert bundle["payload"] == again["payload"]
    assert bundle["payload_sha256"] == again["payload_sha256"]
    assert bundle["payload_canonical_json"] == again["payload_canonical_json"]
    assert hashlib.sha256(bundle["payload_canonical_json"].encode()).hexdigest() == bundle["payload_sha256"]
    assert AnalysisBundle.model_validate_json(json.dumps(bundle)).model_dump(mode="json") == bundle
    encoded = json.dumps(bundle)
    for forbidden in (PRIVATE, "private_unrecognized_field", "true_source", "nominal_paths",
                      '"note"', '"trial_key"', "explanation", "evidence_frame_ids"):
        assert forbidden not in encoded
    assert len(encoded.encode()) < 1_000_000
    assert len(runtime.store.list("unrelated")) == 1
    assert runtime.store.list("prevention_investigation") == []
    assert runtime.photon_settings().enabled is False
    assert runtime.camera.status()["running"] is False


def test_browser_numeric_normalization_does_not_invalidate_canonical_bytes(app):
    runtime = app.state.runtime
    cid = seed(runtime)["comparison"]["id"]
    bundle = export_comparison(runtime, cid)
    # JSON.stringify(JSON.parse(...)) changes integral floats outside protected
    # canonical-string bytes; semantics and verified exact bytes remain intact.
    def javascript_numbers(value):
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, dict):
            return {k: javascript_numbers(v) for k, v in value.items()}
        if isinstance(value, list):
            return [javascript_numbers(v) for v in value]
        return value
    normalized = javascript_numbers(copy.deepcopy(bundle))
    assert AnalysisBundle.model_validate(normalized).payload_sha256 == bundle["payload_sha256"]
    normalized["payload"]["comparison"]["particles"] += 1
    with pytest.raises(ValueError, match="disagree"):
        AnalysisBundle.model_validate(normalized)
    damaged = copy.deepcopy(bundle)
    damaged["payload_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA256"):
        AnalysisBundle.model_validate(damaged)


@pytest.mark.parametrize("archive", ["stop", "revision", "new_source"])
def test_archives_remain_exportable_without_changing_hashed_frozen_data(app, archive):
    runtime = app.state.runtime
    detail = seed(runtime)
    c = detail["comparison"]
    before = export_comparison(runtime, c["id"])
    case = runtime.store.case(c["case_id"])
    if archive == "stop":
        runtime.store.stop_case(case["id"])
    else:
        changes = {"evidence_id": "estimate-new"} if archive == "new_source" else {"state": "INVESTIGATE"}
        runtime.store.update_case(case["id"], case["revision"], changes)
    after = export_comparison(runtime, c["id"])
    assert before["payload"] == after["payload"]
    assert before["payload_sha256"] == after["payload_sha256"]
    assert after["metadata"]["is_current"] is False
    assert after["metadata"]["archive_reason"] == "CASE_CHANGED_OR_STOPPED"


@pytest.mark.parametrize("tamper", ["profile_hash", "flow_hash", "profile_id", "snapshot",
                                  "source_id", "plan", "scenario", "row_source", "row_denominator"])
def test_export_rejects_tampered_nested_identities_and_original_hashes(app, tamper):
    runtime = app.state.runtime
    c = seed(runtime)["comparison"]
    def corrupt(row):
        if tamper in {"profile_hash", "flow_hash", "profile_id"}:
            row["numerical_report"]["layouts"]["baseline"][tamper] = "wrong"
        elif tamper == "snapshot":
            row["baseline_profile"]["calibration_id"] = "wrong"
        elif tamper == "source_id":
            row["source_evidence_id"] = "estimate-missing"
        elif tamper == "plan":
            row["plan"]["sequence"][0]["source_id"] = "B"
        elif tamper == "scenario":
            row["numerical_report"]["scenario_ids"] = ["other"]
        elif tamper == "row_source":
            row["numerical_report"]["results"][0]["source_id"] = "other"
        elif tamper == "row_denominator":
            row["numerical_report"]["results"][0]["baseline"]["particles"] += 1
    change_record(runtime, COMPARISON_KIND, c["id"], corrupt)
    with pytest.raises((ValueError, KeyError)):
        export_comparison(runtime, c["id"])


def test_changed_original_profile_is_not_silently_trusted(app):
    runtime = app.state.runtime
    c = seed(runtime)["comparison"]
    change_record(runtime, "profile", c["baseline_profile_id"],
                  lambda row: row["flow"]["nodes"][0].update(vx_cm_s=2))
    with pytest.raises(ValueError, match="hashes"):
        export_comparison(runtime, c["id"])


@pytest.mark.parametrize("unsafe", ["contact@example.test", "/private/frames", "+15555550123",
                                    "ghp_FAKE_NOT_A_REAL_TOKEN_1234567890",
                                    "ck-FAKE-NOT-A-REAL-CHALK-TOKEN"])
def test_identifiers_cannot_carry_contacts_paths_or_token_shaped_values(app, unsafe):
    c = seed(app.state.runtime, source_ids=(unsafe, "B"))["comparison"]
    with pytest.raises(ValueError, match="unsafe or invalid") as error:
        export_comparison(app.state.runtime, c["id"])
    assert unsafe not in str(error.value)


def test_trial_append_changes_bundle_and_keeps_incomplete_unknown_denominators(app):
    runtime = app.state.runtime
    c = seed(runtime)["comparison"]
    before = export_comparison(runtime, c["id"])
    add_trial(runtime, c["id"], outcome="unresolved", entry_time_s=None,
              token_accounted=False, horizon_completed=False)
    bundle = export_comparison(runtime, c["id"])
    assert bundle["payload_sha256"] != before["payload_sha256"]
    truth = bundle["payload"]["evaluation_truth"]
    stats = truth["evaluation"]["by_origin"]["SYNTHETIC_DEMO"]["layouts"]["baseline"]
    assert (stats["released"], stats["unresolved"], stats["missing_planned"], stats["planned"]) == (1, 1, 3, 4)
    assert stats["entry_rate_bounds"]["upper"] == 1
    assert truth["purpose"] == "EVALUATION_ONLY_NEVER_SOURCE_INFERENCE_INPUT"
    assert "source_id" not in bundle["payload"]["source_evidence"]


def test_concurrent_append_cannot_mix_old_provenance_with_new_trial_evaluation(app, monkeypatch):
    import apps.api.reeftrace_api.services.evidence_export as exporter

    runtime = app.state.runtime
    cid = seed(runtime)["comparison"]["id"]
    original = exporter._check_plan
    appended = False

    def append_after_original_read(comparison, profiles):
        nonlocal appended
        original(comparison, profiles)
        if not appended:
            appended = True
            add_trial(runtime, cid)
    monkeypatch.setattr(exporter, "_check_plan", append_after_original_read)
    during = export_comparison(runtime, cid)
    after = export_comparison(runtime, cid)
    assert during["payload"]["evaluation_truth"]["trials"] == []
    assert during["payload"]["evaluation_truth"]["evaluation"]["trial_ids"] == []
    assert len(after["payload"]["evaluation_truth"]["trials"]) == 1
    assert after["payload_sha256"] != during["payload_sha256"]


def test_export_enforces_trial_and_record_byte_budgets(app, monkeypatch):
    import apps.api.reeftrace_api.services.evidence_export as exporter

    runtime = app.state.runtime
    cid = seed(runtime)["comparison"]["id"]
    add_trial(runtime, cid, key="release-one")
    add_trial(runtime, cid, key="release-two")
    monkeypatch.setattr(exporter, "MAX_TRIALS", 1)
    with pytest.raises(ValueError, match="budget"):
        export_comparison(runtime, cid)
    monkeypatch.setattr(exporter, "MAX_TRIALS", 200)
    monkeypatch.setattr(exporter, "MAX_RECORD_BYTES", 128)
    with pytest.raises(ValueError, match="budget"):
        export_comparison(runtime, cid)


def test_synthetic_and_operator_reported_policy_fixture_outcomes_stay_separate(app):
    runtime = app.state.runtime
    c = seed(runtime, origin="MEASURED_TANK")["comparison"]
    add_trial(runtime, c["id"], key="synthetic-policy")
    add_trial(runtime, c["id"], key="physical-policy", data_origin="OPERATOR_REPORTED_PHYSICAL",
              physical_confirmed=True)
    bundle = export_comparison(runtime, c["id"])
    independence = bundle["payload"]["provenance"]["independence"]
    assert independence["status"] == "INDEPENDENT_MEASURED_RECORDING_SETS"
    assert independence["outcome_validation"] == "NOT_AUTOMATICALLY_VERIFIED"
    for origin in ("SYNTHETIC_DEMO", "OPERATOR_REPORTED_PHYSICAL"):
        group = bundle["payload"]["evaluation_truth"]["evaluation"]["by_origin"][origin]
        assert group["layouts"]["baseline"]["released"] == 1
        assert group["supports_causal_claim"] is False
        assert group["physical_outcomes_automatically_verified"] is False


def test_export_endpoint_requires_operator_even_though_comparison_reads_are_public(app):
    with TestClient(app) as client:
        c = seed(app.state.runtime)["comparison"]
        url = f"/api/v1/prevention/comparisons/{c['id']}/export"
        assert client.get(url).status_code == 401
        response = client.get(url, headers=AUTH)
        assert response.status_code == 200, response.text
        assert response.json()["payload"]["comparison"]["id"] == c["id"]
        assert client.get("/api/v1/prevention/comparisons/missing/export", headers=AUTH).status_code == 404


def test_actual_synthetic_rehearsal_computes_then_exports_without_provider_or_actuation(app):
    with TestClient(app) as client:
        response = client.post("/api/v1/prevention/demo", headers=AUTH, json={})
        assert response.status_code == 200, response.text
        detail = response.json()
        cid = detail["comparison"]["id"]
        exported = client.get(f"/api/v1/prevention/comparisons/{cid}/export", headers=AUTH)
        assert exported.status_code == 200, exported.text
        bundle = AnalysisBundle.model_validate(exported.json())
        assert len(bundle.payload.evaluation_truth.trials) == 30
        assert bundle.payload.source_evidence.id == detail["comparison"]["source_evidence_id"]
        assert bundle.payload.evaluation_truth.evaluation.snapshot_hash == detail["evaluation"]["snapshot_hash"]
        assert bundle.payload.evaluation_truth.evaluation.by_origin["OPERATOR_REPORTED_PHYSICAL"].plan.recorded_total == 0
        status = client.get("/api/v1/status").json()
        assert status["hardware_actuation"] is False
        assert status["camera"]["running"] is False
        assert app.state.runtime.store.list("prevention_investigation") == []


def test_shared_synthetic_contract_fixture_is_valid_and_contains_no_physical_claim():
    bundle = AnalysisBundle.model_validate_json(FIXTURE.read_text())
    assert bundle.schema_version == "analysis_bundle_v1"
    assert bundle.payload.comparison.data_origin == "SYNTHETIC"
    assert bundle.payload.provenance.independence.independently_measured is False
    truth = bundle.payload.evaluation_truth
    assert all(t.data_origin == "SYNTHETIC_DEMO" for t in truth.trials)
    assert truth.evaluation.by_origin["OPERATOR_REPORTED_PHYSICAL"].plan.recorded_total == 0
    assert hashlib.sha256(bundle.payload_canonical_json.encode()).hexdigest() == bundle.payload_sha256
    assert canonical_json(json.loads(bundle.payload_canonical_json)) == bundle.payload_canonical_json
