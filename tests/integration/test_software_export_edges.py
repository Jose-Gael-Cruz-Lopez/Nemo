"""Synthetic contract audit; real services, temporary stores, no live API or hardware."""

import asyncio
import copy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_experiment_protocol import experiment as rehearsal_fixture
from test_experiment_protocol import submit
from test_validation_chalk import prepare, scripted_client

from adapters.chalk.agent import ChalkSettings
from apps.api.reeftrace_api.schemas.contracts import CaseInput
from apps.api.reeftrace_api.schemas.evidence_export import AnalysisBundle, canonical_json
from apps.api.reeftrace_api.schemas.prevention import TrialInput
from apps.api.reeftrace_api.schemas.validation_reports import ValidationReportInput
from apps.api.reeftrace_api.services.evidence_export import export_comparison
from apps.api.reeftrace_api.services.prevention import TRIAL_KIND
from apps.api.reeftrace_api.services.prevention_investigation import (
    PreventionCaseBackend,
    investigate_prevention,
)
from apps.api.reeftrace_api.services.validation_reports import (
    VALIDATION_KIND,
    _check_manifest,
    accept_validation_report,
    get_validation_report,
    template_validation_report,
)
from apps.estimation.reeftrace_estimation.prevention_validation import (
    _existing_evaluation,
    content_hash,
    validate_bundle,
)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    # Reuse the merged three-source synthetic constructor; never bypass its gates.
    runtime, freeze, evidence = rehearsal_fixture.__wrapped__(tmp_path)
    return runtime, freeze(1), evidence


def receipt(runtime, comparison):
    body = ValidationReportInput(report=template_validation_report(runtime, comparison["id"]))
    return accept_validation_report(runtime, comparison["id"], body)


def assert_binding(detail, bundle, accepted):
    c, evaluation = detail["comparison"], detail["evaluation"]
    payload = bundle["payload"]
    assert AnalysisBundle.model_validate(bundle).payload_sha256 == bundle["payload_sha256"]
    assert hashlib.sha256(bundle["payload_canonical_json"].encode()).hexdigest() == bundle["payload_sha256"]
    assert payload["comparison"]["id"] == accepted["report"]["comparison_id"] == c["id"]
    assert payload["frozen_plan"] == c["plan"]
    assert payload["evaluation_truth"]["evaluation"] == {
        key: value for key, value in evaluation.items() if key != "limitations"}
    assert accepted["report"]["input_payload_sha256"] == bundle["payload_sha256"]
    assert accepted["report"]["evaluation_snapshot_hash"] == evaluation["snapshot_hash"]
    assert accepted["report"]["verification"] == "IDENTITY_AND_ACCOUNTING_CHECKED_METHOD_NOT_RERUN"
    assert accepted["checks"] == {"identity_verified": True, "accounting_verified": True,
                                  "method_rerun": False, "physical_validation": False}
    assert accepted["is_current"] is True and accepted["archive_reason"] is None
    assert accepted["summary"]["outcome_origin"] == "SYNTHETIC_DEMO"
    assert accepted["summary"]["physical_validation"] is False
    for layout in ("baseline", "intervention"):
        assert payload["provenance"]["layouts"][layout]["id"] == c[layout + "_profile_id"]
    return payload


def test_zero_releases_export_unknown_bounds_but_no_empty_validation_receipt(setup):
    runtime, c, _ = setup
    exported = export_comparison(runtime, c["id"])
    groups = exported["payload"]["evaluation_truth"]["evaluation"]["by_origin"]
    for origin in ("SYNTHETIC_DEMO", "OPERATOR_REPORTED_PHYSICAL"):
        assert groups[origin]["plan"] == {"expected_total": 6, "recorded_total": 0,
            "complete": False, "balanced": False, "order_followed": True}
        for stats in groups[origin]["layouts"].values():
            assert (stats["planned"], stats["released"], stats["missing_planned"], stats["unresolved"]) == (3, 0, 3, 0)
            assert stats["entry_rate_bounds"] == {"lower": 0.0, "upper": 1.0, "denominator": 3,
                "kind": "planned_slots_missing_and_unresolved_are_unknown"}
            assert stats["observed_entry_rate_bounds"] == {"lower": 0.0, "upper": 1.0, "denominator": 0,
                "kind": "actual_releases_including_unresolved"}
    with pytest.raises(ValueError, match="no recorded trials"):
        template_validation_report(runtime, c["id"])
    assert runtime.store.list(VALIDATION_KIND) == []


def test_entry_and_lost_token_keep_exact_counts_through_receipt(setup):
    runtime, c, _ = setup
    _, body = submit(runtime, c, 1)
    # Retrying an observation must not create another released token.
    assert runtime.prevention.add_trial(c["id"], body)["trials"][0]["request_hash"] == content_hash(body.model_dump())
    lost, _ = submit(runtime, c, 2, outcome="unresolved")
    accepted = receipt(runtime, c)
    payload = assert_binding(lost, export_comparison(runtime, c["id"]), accepted)
    rows = {(r["source_id"], r["layout"]): r for r in accepted["summary"]["by_source"]}
    assert accepted["summary"]["validation_count"] == 2
    assert accepted["summary"]["missing_planned"] == 4 and accepted["summary"]["unresolved"] == 1
    assert (rows["A", "intervention"]["planned"], rows["A", "intervention"]["released"],
            rows["A", "intervention"]["unaccounted"], rows["A", "intervention"]["captured_before_entry"]) == (1, 1, 1, 0)
    assert rows["A", "intervention"]["entry_rate_bounds"]["upper"] == 1.0
    assert payload["evaluation_truth"]["evaluation"]["by_origin"]["OPERATOR_REPORTED_PHYSICAL"]["plan"]["recorded_total"] == 0


@pytest.mark.parametrize("outcome", ["no_entry", "intercepted_before_entry"])
def test_nonentry_claims_require_whole_horizon_at_schema_boundary(setup, outcome):
    runtime, c, _ = setup
    body = {"trial_key": "incomplete", "source_id": "A", "layout": "baseline", "data_origin": "SYNTHETIC_DEMO",
        "outcome": outcome, "entry_time_s": None, "interception_time_s": 3.0 if outcome.startswith("intercepted") else None,
        "token_accounted": True, "physical_confirmed": False, "horizon_completed": False, "note": "Synthetic incomplete observation"}
    with pytest.raises(ValidationError, match="complete fixed horizon"):
        TrialInput(**body)
    assert runtime.prevention.comparison_detail(c["id"])["trials"] == []
    body["horizon_completed"] = True
    detail = runtime.prevention.add_trial(c["id"], TrialInput(**body))
    assert_binding(detail, export_comparison(runtime, c["id"]), receipt(runtime, c))


def test_later_collection_cannot_undo_zone_entry(setup):
    runtime, c, _ = setup
    body = TrialInput(trial_key="entry-before-pickup", source_id="A", layout="baseline",
        data_origin="SYNTHETIC_DEMO", outcome="zone_entry", entry_time_s=6.0,
        interception_time_s=8.0, token_accounted=True, physical_confirmed=False,
        horizon_completed=True, note="Synthetic zone entry then later pickup")
    detail = runtime.prevention.add_trial(c["id"], body)
    exported = export_comparison(runtime, c["id"])
    assert_binding(detail, exported, receipt(runtime, c))
    row = exported["payload"]["evaluation_truth"]["trials"][0]
    assert (row["id"], row["outcome"], row["entry_time_s"], row["interception_time_s"]) == (
        detail["trials"][0]["id"], "zone_entry", 6.0, 8.0)
    stats = detail["evaluation"]["by_origin"]["SYNTHETIC_DEMO"]["layouts"]["baseline"]
    assert stats["zone_entries"] == 1 and stats["captured_before_entry"] == 0


def test_out_of_order_is_recorded_flagged_and_not_silently_rejected(setup):
    runtime, c, _ = setup
    detail, _ = submit(runtime, c, 2)
    assert detail["trials"][0]["layout"] == "intervention" and detail["trials"][0]["ordinal"] == 1
    payload = assert_binding(detail, export_comparison(runtime, c["id"]), receipt(runtime, c))
    assert payload["evaluation_truth"]["evaluation"]["by_origin"]["SYNTHETIC_DEMO"]["plan"]["order_followed"] is False
    assert detail["evaluation"]["by_origin"]["SYNTHETIC_DEMO"]["supports_causal_claim"] is False


def test_exact_retry_changed_body_conflict_and_cell_quota_preserve_export(setup):
    runtime, c, _ = setup
    detail, body = submit(runtime, c, 1)
    before = export_comparison(runtime, c["id"])
    accepted = receipt(runtime, c)
    assert runtime.prevention.add_trial(c["id"], body) == detail
    for change, message in (({"note": "Different immutable claim"}, "immutable data"),
                            ({"trial_key": "second-same-cell"}, "quota")):
        with pytest.raises(ValueError, match=message):
            runtime.prevention.add_trial(c["id"], TrialInput(**{**body.model_dump(), **change}))
    after = export_comparison(runtime, c["id"])
    assert before["payload_sha256"] == after["payload_sha256"]
    assert before["payload"] == after["payload"]
    assert get_validation_report(runtime, accepted["report"]["id"]) == accepted


@pytest.mark.parametrize("change", ["stop", "revision", "trial"])
def test_saved_receipt_archives_and_old_manifest_cannot_be_reaccepted(setup, change):
    runtime, c, _ = setup
    submit(runtime, c, 1)
    manifest = template_validation_report(runtime, c["id"])
    saved = accept_validation_report(runtime, c["id"], ValidationReportInput(report=manifest))
    if change == "trial":
        submit(runtime, c, 2)
    elif change == "stop":
        runtime.store.stop_case(c["case_id"])
    else:
        case = runtime.store.case(c["case_id"])
        runtime.store.update_case(case["id"], case["revision"], {"state": "INVESTIGATE"})
    archived = get_validation_report(runtime, saved["report"]["id"])
    assert archived["report"] == saved["report"] and archived["summary"] == saved["summary"]
    assert archived["is_current"] is False
    assert archived["archive_reason"] == ("EVALUATION_CHANGED" if change == "trial" else "CASE_CHANGED_OR_STOPPED")
    with pytest.raises(ValueError):
        accept_validation_report(runtime, c["id"], ValidationReportInput(report=manifest))
    if change != "trial":
        with pytest.raises(ValueError):
            submit(runtime, c, 2)
    assert len(runtime.store.list(VALIDATION_KIND)) == 1


@pytest.mark.parametrize("edit", [
    lambda m: m.update(input_payload_sha256="0" * 64),
    lambda m: m.update(evaluation_snapshot_hash="0" * 64),
    lambda m: m.update(comparison_id="comparison-other"),
    lambda m: m.update(validation_trial_ids=["prevention-trial-absent"]),
    lambda m: m.update(validation_trial_ids=m["validation_trial_ids"][:-1]),
    lambda m: m.update(development_trial_ids=m["validation_trial_ids"][:1]),
    lambda m: m.update(validation_trial_ids=m["validation_trial_ids"] * 2),
    lambda m: m.update(content_hash="0" * 64),
])
def test_bad_identity_partition_or_method_fields_never_persist_receipt(setup, edit):
    runtime, c, _ = setup
    submit(runtime, c, 1)
    submit(runtime, c, 2)
    manifest = template_validation_report(runtime, c["id"])
    manifest["purpose"] = "DECLARED_VALIDATION_SPLIT"
    edit(manifest)
    with pytest.raises(ValueError):
        accept_validation_report(runtime, c["id"], ValidationReportInput(report=manifest))
    assert runtime.store.list(VALIDATION_KIND) == []


def test_duplicate_record_identity_fails_export_before_receipt(setup):
    runtime, c, _ = setup
    detail, _ = submit(runtime, c, 1)
    trial = detail["trials"][0]
    # Corrupt ONLY a disposable store: duplicate payload under another immutable key.
    runtime.store.put(TRIAL_KIND, trial, "prevention-trial-duplicate-key")
    with pytest.raises(ValueError, match="Trial identity"):
        export_comparison(runtime, c["id"])
    assert runtime.store.list(VALIDATION_KIND) == []


def test_duplicate_or_overlapping_recordings_are_checked_by_partition_layer(setup):
    runtime, c, _ = setup
    submit(runtime, c, 1)
    submit(runtime, c, 2)
    manifest = ValidationReportInput(report=template_validation_report(runtime, c["id"])).report
    bundle = export_comparison(runtime, c["id"])
    # Direct adversarial policy inputs, not admitted measured profiles/physical trials.
    for trial in bundle["payload"]["evaluation_truth"]["trials"]:
        trial["recording_id"] = "synthetic-duplicate-recording"
    with pytest.raises(ValueError, match="multiple or overlapping"):
        _check_manifest(manifest, bundle)
    manifest = manifest.model_copy(update={"purpose": "DECLARED_VALIDATION_SPLIT",
        "development_trial_ids": manifest.validation_trial_ids[:1],
        "validation_trial_ids": manifest.validation_trial_ids[1:]})
    with pytest.raises(ValueError, match="multiple or overlapping"):
        _check_manifest(manifest, bundle)


def test_synthetic_profile_refuses_physical_claim_before_any_ledger_write(setup):
    runtime, c, _ = setup
    physical_claim = TrialInput(trial_key="refused-physical", source_id="A", layout="baseline",
        data_origin="OPERATOR_REPORTED_PHYSICAL", outcome="unresolved", token_accounted=False,
        physical_confirmed=True, horizon_completed=False, note="Negative policy fixture only")
    with pytest.raises(ValueError, match="physical-outcome"):
        runtime.prevention.add_trial(c["id"], physical_claim)
    assert runtime.prevention.comparison_detail(c["id"])["trials"] == []
    submit(runtime, c, 1)
    exported = export_comparison(runtime, c["id"])
    groups = exported["payload"]["evaluation_truth"]["evaluation"]["by_origin"]
    assert groups["SYNTHETIC_DEMO"]["plan"]["recorded_total"] == 1
    assert groups["OPERATOR_REPORTED_PHYSICAL"]["plan"]["recorded_total"] == 0
    assert set(groups) == {"SYNTHETIC_DEMO", "OPERATOR_REPORTED_PHYSICAL"}


def test_rehashed_redacted_export_is_not_a_method_replay_input(setup):
    runtime, c, _ = setup
    submit(runtime, c, 1)
    value = export_comparison(runtime, c["id"])
    changed = copy.deepcopy(value)
    changed["payload"]["comparison"]["numerical_report"]["results"][0]["baseline"]["zone_entry_count"] -= 1
    with pytest.raises(ValueError, match="disagree"):
        AnalysisBundle.model_validate(changed)
    # A matching content digest proves self-consistency only, not numerical truth.
    changed["payload_canonical_json"] = canonical_json(changed["payload"])
    changed["payload_sha256"] = hashlib.sha256(changed["payload_canonical_json"].encode()).hexdigest()
    assert AnalysisBundle.model_validate(changed).payload_sha256 != value["payload_sha256"]
    with pytest.raises(ValueError):
        validate_bundle(changed, development_protocol_id="dev", validation_protocol_id="test")
    changed["content_hash"] = changed.pop("payload_sha256")
    with pytest.raises(ValueError):
        validate_bundle(changed, development_protocol_id="dev", validation_protocol_id="test")
    with pytest.raises(ValueError):
        AnalysisBundle.model_validate(changed)


def test_full_method_replay_refuses_forged_prediction_even_after_all_hashes_are_updated():
    root = Path(__file__).resolve().parents[1] / "fixtures/prevention_validation/analysis_bundle_v1.json"
    value = json.loads(root.read_text())
    p = value["payload"]
    c = p["comparison"]
    c["numerical_report"]["results"][0]["baseline"]["zone_entry_count"] = 0
    for protocol in p["protocols"].values():
        protocol["comparison_hash"] = content_hash(c)
    labels = {t["trial_id"]: t["source_id"] for t in p["evaluation_truth"]["trial_sources"]}
    joined = [{**trial, "source_id": labels[trial["id"]]} for trial in p["trials"]]
    evaluation = _existing_evaluation(c, joined)
    p["evaluation"]["export_snapshot_hash"] = evaluation["snapshot_hash"]
    p["evaluation"]["by_origin"] = evaluation["by_origin"]
    value["content_hash"] = content_hash(p)
    value["id"] = "analysis-bundle-" + value["content_hash"][:20]
    with pytest.raises(ValueError, match="Stale/tampered numerical report"):
        validate_bundle(value, development_protocol_id=p["protocols"]["development"]["id"],
                        validation_protocol_id=p["protocols"]["validation"]["id"])


def test_source_truth_stays_out_of_observations_and_mocked_chalk_cannot_write_ledger(setup, monkeypatch):
    runtime, c, evidence = setup
    # The mocked model requires a genuinely computed source report, not the
    # minimal Unknown policy record used by the ledger-only scenarios above.
    detail, saved = asyncio.run(prepare(runtime))
    c = detail["comparison"]
    evidence = runtime.store.get("estimate", c["source_evidence_id"])
    before = copy.deepcopy(detail)
    profile = runtime.store.get("profile", c["baseline_profile_id"])
    observation = CaseInput(profile_id=profile["id"], calibration_id=profile["calibration_id"],
                            token_class=profile["token_class"], mode="REPLAY", points=[])
    with pytest.raises(ValidationError, match="source_id") as error:
        CaseInput(**observation.model_dump(), source_id="A")
    assert [(e["loc"], e["type"]) for e in error.value.errors()] == [(('source_id',), 'extra_forbidden')]
    monkeypatch.setattr(runtime, "chalk_settings", lambda: ChalkSettings(
        True, "https://provider.invalid/router", "test-only", "test-env", "test-model"))

    async def review():
        backend = PreventionCaseBackend(runtime, detail, saved)
        source_before = await backend.call("get_source_evidence", {})
        with pytest.raises(ValueError, match="read-only"):
            await backend.call("record_trial", {"source_id": "A"})
        client, requests = scripted_client()
        async with client:
            result = await investigate_prevention(runtime, c["id"], "Explain the checked accounting.",
                client=client, validation_report_id=saved["report"]["id"])
        assert await backend.call("get_source_evidence", {}) == source_before
        assert result["validation_checks"] == saved["checks"]
        assert result["validation_report_id"] == saved["report"]["id"]
        assert result["evaluation_digest"] == detail["evaluation"]["snapshot_hash"]
        assert {e["tool"] for e in result["trace"]} == {
            "get_case", "get_source_evidence", "get_prevention_evidence", "get_validation_evidence"}
        encoded = json.dumps(requests)
        for t in detail["trials"]:
            assert t["id"] not in encoded and t["trial_key"] not in encoded and t["note"] not in encoded
        assert '"trial_sources"' not in encoded
        return result

    asyncio.run(review())
    assert runtime.prevention.comparison_detail(c["id"]) == before
    assert runtime.store.get("estimate", evidence["id"]) == evidence
    assert runtime.store.list("action") == []
    assert runtime.photon_settings().enabled is False and runtime.camera.status()["running"] is False


def test_contradictory_complete_plan_survives_export_receipt_without_promotion(setup):
    runtime, c, _ = setup
    assert c["numerical_report"]["recommendation"] == "INTERVENTION"
    for index, slot in enumerate(c["plan"]["sequence"], 1):
        detail, _ = submit(runtime, c, index,
            outcome="no_entry" if slot["layout"] == "baseline" else "zone_entry")
    saved = receipt(runtime, c)
    assert_binding(detail, export_comparison(runtime, c["id"]), saved)
    assert saved["summary"]["validation_count"] == 6 and saved["summary"]["missing_planned"] == 0
    assert saved["summary"]["next_measurement"]["action"] == "DECLARE_NEW_INDEPENDENT_PROTOCOL"
    for row in saved["summary"]["by_source"]:
        observed, predicted = (0, 1.0) if row["layout"] == "baseline" else (1, 0.0)
        assert (row["zone_entries"], row["planned"], row["released"], row["unresolved"]) == (observed, 1, 1, 0)
        assert row["predicted_entry_fraction"] == predicted
        assert row["entry_rate_bounds"]["lower"] == row["entry_rate_bounds"]["upper"] == observed
    assert detail["evaluation"]["by_origin"]["SYNTHETIC_DEMO"]["effect_bounds"]["upper"] == -1.0
    assert saved["summary"]["supports_causal_claim"] is False


def test_whitelist_detached_metadata_and_no_hash_aliases(setup):
    runtime, c, _ = setup
    _, body = submit(runtime, c, 1)
    exported = export_comparison(runtime, c["id"])
    assert set(exported) == {"schema_version", "payload", "payload_canonical_json", "payload_sha256", "metadata"}
    raw = canonical_json(exported["payload"])
    assert raw == exported["payload_canonical_json"]
    assert body.note not in raw and body.trial_key not in raw
    for forbidden in ('"note"', '"trial_key"', '"request_hash"', '"nominal_paths"', '"points"'):
        assert forbidden not in raw
    detached = copy.deepcopy(exported)
    detached["metadata"]["exported_at_utc"] = "2030-01-01T00:00:00+00:00"
    assert AnalysisBundle.model_validate(detached).payload_sha256 == exported["payload_sha256"]
    detached["content_hash"] = detached["payload_sha256"]
    with pytest.raises(ValidationError, match="Extra inputs"):
        AnalysisBundle.model_validate(detached)


@pytest.mark.parametrize("target", ["profile", "source", "comparison"])
def test_corrupt_immutable_binding_fails_at_export_layer(setup, target):
    runtime, c, _ = setup
    submit(runtime, c, 1)
    if target == "profile":
        kind, identity = "profile", c["intervention_profile_id"]
        edit = lambda record: record.update(token_class="different-synthetic-token")
    elif target == "source":
        kind, identity = "estimate", c["source_evidence_id"]
        edit = lambda record: record.update(profile_id=c["intervention_profile_id"])
    else:
        kind, identity = "prevention_comparison", c["id"]
        edit = lambda record: record["numerical_report"].update(particles_per_source=21)
    record = runtime.store.get(kind, identity)
    edit(record)
    with runtime.store.connection() as db:
        db.execute("UPDATE records SET payload=? WHERE kind=? AND id=?", (json.dumps(record), kind, identity))
    with pytest.raises(ValueError):
        export_comparison(runtime, c["id"])
    assert runtime.store.list(VALIDATION_KIND) == []


def test_concurrent_append_is_rechecked_atomically_before_receipt_save(setup, monkeypatch):
    from apps.api.reeftrace_api.services import validation_reports as service

    runtime, c, _ = setup
    submit(runtime, c, 1)
    body = ValidationReportInput(report=template_validation_report(runtime, c["id"]))
    original = service._check_manifest

    def append_after_checked(manifest, bundle):
        result = original(manifest, bundle)
        submit(runtime, c, 2)
        return result

    monkeypatch.setattr(service, "_check_manifest", append_after_checked)
    with pytest.raises(ValueError, match="changed while checking"):
        accept_validation_report(runtime, c["id"], body)
    assert len(runtime.prevention.comparison_detail(c["id"])["trials"]) == 2
    assert runtime.store.list(VALIDATION_KIND) == []
