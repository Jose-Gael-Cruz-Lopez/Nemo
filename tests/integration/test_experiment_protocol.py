"""P2 six-slot/30-new-slot rehearsal: synthetic policy inputs, never tank evidence."""

import asyncio
import copy

import pytest

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.api.reeftrace_api.schemas.evidence_export import AnalysisBundle
from apps.api.reeftrace_api.schemas.prevention import ComparisonInput, TrialInput
from apps.api.reeftrace_api.schemas.validation_reports import ValidationReportInput
from apps.api.reeftrace_api.services.evidence_export import export_comparison
from apps.api.reeftrace_api.services.validation_reports import (
    accept_validation_report,
    template_validation_report,
)
from apps.transport.reeftrace_transport import fit_flow


@pytest.fixture
def experiment(tmp_path):
    runtime = create_app(Settings(_env_file=None, data_dir=tmp_path,
        local_token="synthetic-p2-only", chalk_enabled=False,
        photon_enabled=False, grok_voice_enabled=False)).state.runtime
    bounds = {"x_min_cm": 0, "x_max_cm": 12, "y_min_cm": 0, "y_max_cm": 10}
    flow = fit_flow([{"x_cm": x, "y_cm": y, "vx_cm_s": 1, "vy_cm_s": 0}
                    for x in (0, 4, 8, 12) for y in (0, 5, 10)], bounds,
                    coverage_radius_cm=20, data_origin="SYNTHETIC")
    profiles = []
    for layout in ("baseline", "intervention"):
        profile = {"valid": True, "data_origin": "SYNTHETIC", "bounds": bounds, "flow": copy.deepcopy(flow),
            "token_class": "synthetic-red-token", "calibration_id": "synthetic-p2-map",
            "sources": [{"id": source, "polygon_cm": [[1, y], [1.1, y], [1.1, y + .1], [1, y + .1]]}
                     for source, y in zip(("A", "B", "C"), (2, 5, 8), strict=True)],
            "transport": {"dt_s": .5, "max_age_s": 20, "diffusivity_cm2_s": 0},
            "traps": [] if layout == "baseline" else [{"id": "mesh", "validated": True,
                "retention": "absorbing", "polygon_cm": [[4, 0], [5.5, 0], [5.5, 10], [4, 10]]}]}
        profiles.append(runtime.store.put("profile", profile))
    case = runtime.store.add_case({"profile_id": profiles[0]["id"], "mode": "REPLAY",
                                     "points": [], "evidence_frame_ids": []})
    evidence = runtime.store.put_case_result("estimate", {"case_id": case["id"],
        "status": "unknown", "profile_id": profiles[0]["id"], "data_origin": "SYNTHETIC"},
        case["id"], case["revision"], changes={"state": "INVESTIGATE"})

    def freeze(quota):
        return asyncio.run(runtime.prevention.create_comparison(ComparisonInput(
            case_id=case["id"], baseline_profile_id=profiles[0]["id"],
            intervention_profile_id=profiles[1]["id"], protected_zone_cm=[[7, 0], [8, 0], [8, 10], [7, 10]],
            name="Synthetic P2 rehearsal", horizon_s=10, particles=20,
            trials_per_source=quota)))["comparison"]

    return runtime, freeze, evidence


def submit(runtime, comparison, ordinal, *, outcome="zone_entry"):
    slot = comparison["plan"]["sequence"][ordinal - 1]
    body = TrialInput(trial_key=f"synthetic-slot-{ordinal}", layout=slot["layout"],
        source_id=slot["source_id"], data_origin="SYNTHETIC_DEMO", outcome=outcome,
        entry_time_s=6.0 if outcome == "zone_entry" else None,
        interception_time_s=3.0 if outcome == "intercepted_before_entry" else None,
        token_accounted=outcome != "unresolved", horizon_completed=outcome != "unresolved",
        physical_confirmed=False, note="Synthetic software rehearsal only")
    return runtime.prevention.add_trial(comparison["id"], body), body


def test_six_slot_pilot_preserves_frozen_order_exact_retry_and_unknown_source(experiment):
    runtime, freeze, evidence = experiment
    comparison = freeze(1)
    assert comparison["plan"]["expected_total"] == 6
    assert [(s["source_id"], s["layout"]) for s in comparison["plan"]["sequence"]] == [
        ("A", "baseline"), ("A", "intervention"), ("B", "intervention"),
        ("B", "baseline"), ("C", "baseline"), ("C", "intervention")]
    first, body = submit(runtime, comparison, 1)
    assert runtime.prevention.add_trial(comparison["id"], body) == first
    with pytest.raises(ValueError):
        runtime.prevention.add_trial(comparison["id"], body.model_copy(update={"note": "Changed claim"}))
    for ordinal in range(2, 7):
        detail, _ = submit(runtime, comparison, ordinal)
    assert len(detail["trials"]) == 6
    assert detail["evaluation"]["by_origin"]["SYNTHETIC_DEMO"]["plan"]["complete"] is True
    assert runtime.store.get("estimate", evidence["id"]) == evidence
    assert runtime.camera.status()["running"] is False
    assert runtime.photon_settings().enabled is False


def test_confirmation_is_30_new_slots_not_six_pilot_plus_24(experiment):
    runtime, freeze, _ = experiment
    pilot = freeze(1)
    for ordinal in range(1, 7):
        pilot_detail, _ = submit(runtime, pilot, ordinal)
    confirmation = freeze(5)
    assert confirmation["id"] != pilot["id"] and confirmation["plan"]["id"] != pilot["plan"]["id"]
    before = runtime.prevention.comparison_detail(confirmation["id"])
    group = before["evaluation"]["by_origin"]["SYNTHETIC_DEMO"]
    assert group["plan"]["expected_total"] == 30 and group["plan"]["recorded_total"] == 0
    detail, _ = submit(runtime, confirmation, 1)
    assert detail["trials"][0]["id"] not in {t["id"] for t in pilot_detail["trials"]}
    manifest = template_validation_report(runtime, confirmation["id"])
    manifest["validation_trial_ids"] += [t["id"] for t in pilot_detail["trials"]]
    with pytest.raises(ValueError, match="partition"):
        accept_validation_report(runtime, confirmation["id"], ValidationReportInput(report=manifest))


def test_incomplete_pilot_retains_missing_and_unresolved_with_real_denominators(experiment):
    runtime, freeze, _ = experiment
    comparison = freeze(1)
    submit(runtime, comparison, 1)
    detail, _ = submit(runtime, comparison, 2, outcome="unresolved")
    group = detail["evaluation"]["by_origin"]["SYNTHETIC_DEMO"]
    assert group["plan"]["recorded_total"] == 2
    assert sum(group["layouts"][layout]["missing_planned"] for layout in group["layouts"]) == 4
    assert group["layouts"]["intervention"]["unresolved"] == 1
    assert group["layouts"]["intervention"]["entry_rate_bounds"] == {"lower": 0.0, "upper": 1.0,
        "denominator": 3, "kind": "planned_slots_missing_and_unresolved_are_unknown"}
    assert group["layouts"]["intervention"]["observed_entry_rate_bounds"]["denominator"] == 1
    assert group["supports_causal_claim"] is False


def test_contradictory_pilot_export_and_accounting_cannot_become_physical_method_validation(experiment):
    runtime, freeze, _ = experiment
    comparison = freeze(1)
    assert comparison["numerical_report"]["recommendation"] == "INTERVENTION"
    for ordinal, slot in enumerate(comparison["plan"]["sequence"], 1):
        submit(runtime, comparison, ordinal,
               outcome="no_entry" if slot["layout"] == "baseline" else "zone_entry")
    bundle = export_comparison(runtime, comparison["id"])
    assert AnalysisBundle.model_validate(bundle).payload_sha256 == bundle["payload_sha256"]
    manifest = template_validation_report(runtime, comparison["id"])
    saved = accept_validation_report(runtime, comparison["id"], ValidationReportInput(report=manifest))
    assert saved["checks"]["method_rerun"] is False and saved["checks"]["physical_validation"] is False
    assert saved["report"]["input_payload_sha256"] == bundle["payload_sha256"]
    assert saved["report"]["evaluation_snapshot_hash"] == bundle["payload"]["evaluation_truth"]["evaluation"]["snapshot_hash"]
    for row in saved["summary"]["by_source"]:
        assert row["zone_entries"] == (0 if row["layout"] == "baseline" else 1)
        assert row["predicted_entry_fraction"] == (1.0 if row["layout"] == "baseline" else 0.0)
    assert saved["summary"]["physical_validation"] is False
    with pytest.raises(ValueError, match="physical"):
        template_validation_report(runtime, comparison["id"], "OPERATOR_REPORTED_PHYSICAL")
