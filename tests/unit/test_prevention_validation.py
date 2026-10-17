"""Offline synthetic contracts; no private configuration, providers or database."""

import copy
import json
import math
from pathlib import Path

import pytest

from apps.estimation.reeftrace_estimation.prevention import compare_layouts
from apps.estimation.reeftrace_estimation.prevention_validation import (
    _existing_evaluation,
    content_hash,
    validate_bundle,
)
from scripts.evaluate_prevention_validation import main

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
DEV = "development-prevention-v1"
TEST = "heldout-prevention-v1"


def bundle():
    return json.loads((FIXTURES / "prevention_validation" / "analysis_bundle_v1.json").read_text())


def seal(value, *, freeze=False):
    """Fixture authoring only: valid receipts for deliberate adversarial scenarios."""
    p = value["payload"]
    c = p["comparison"]
    if freeze:
        c["plan"]["id"] = "prevention-plan-" + content_hash({k: v for k, v in c["plan"].items() if k != "id"})[:20]
        for layout in ("baseline", "intervention"):
            profile = p["profiles"][layout]
            c[layout + "_profile"] = {k: copy.deepcopy(profile[k]) for k in (
                "id", "bounds", "sources", "traps", "token_class", "calibration_id",
                "observation_polygon_cm", "data_origin") if k in profile}
            c[layout + "_profile"].update(profile_hash=content_hash(profile), flow_id=profile["flow"].get("id"))
        c["numerical_report"] = compare_layouts(p["profiles"]["baseline"], p["profiles"]["intervention"],
            c["protected_zone_cm"], horizon_s=c["horizon_s"], particles=c["particles"], seed=7)
        for protocol in p["protocols"].values():
            protocol["plan_hash"] = content_hash(c["plan"])
            protocol["comparison_hash"] = content_hash(c)
    labels = {row["trial_id"]: row["source_id"] for row in p["evaluation_truth"]["trial_sources"]}
    joined = [{**trial, "source_id": labels[trial["id"]]} for trial in p["trials"]]
    e = _existing_evaluation(c, joined)
    p["evaluation"]["by_origin"] = e["by_origin"]
    p["evaluation"]["export_snapshot_hash"] = e["snapshot_hash"]
    v = p["protocols"]["validation"]
    v["trial_ids"] = sorted(trial["id"] for trial in p["trials"])
    v["recording_ids"] = sorted({t["recording_id"] for t in p["trials"] if t["recording_id"]})
    p["trial_sessions"] = [{"trial_id": t["id"], "session_id": "validation-session-" + str(t["ordinal"])} for t in p["trials"]]
    v["session_ids"] = sorted({row["session_id"] for row in p["trial_sessions"]})
    value["content_hash"] = content_hash(p)
    value["id"] = "analysis-bundle-" + value["content_hash"][:20]
    return value


def run(value):
    return validate_bundle(value, development_protocol_id=DEV, validation_protocol_id=TEST)


def finite(value):
    if isinstance(value, dict):
        return all(finite(item) for item in value.values())
    if isinstance(value, list):
        return all(finite(item) for item in value)
    return not isinstance(value, float) or math.isfinite(value)


def test_known_first_entry_capture_order_and_exact_report_contract():
    value = bundle()
    original = copy.deepcopy(value)
    result = run(value)
    expected = json.loads((FIXTURES / "team_handoff" / "validation_report_v1.json").read_text())
    assert result == run(copy.deepcopy(value))
    unresolved = json.loads((FIXTURES / "prevention_validation" / "unresolved_analysis_bundle_v1.json").read_text())
    assert run(unresolved) == expected
    assert expected["next_measurement"]["kind"] == "INDEPENDENT_PAIRED_TRIAL"
    assert expected["next_measurement"]["source_id"] == "B"
    assert value == original and finite(result)
    body = {k: v for k, v in result.items() if k not in {"id", "content_hash"}}
    assert result["content_hash"] == content_hash(body)
    assert result["physical_validation"] is False
    assert result["source_identification"]["evaluated"] is False
    assert result["original_private_hash_verified"] is False
    assert result["selected_layout_usefulness"]["SYNTHETIC_DEMO"]["status"] == "DESCRIPTIVELY_USEFUL_ON_REPORTED_NEW_TRIALS"
    for row in result["diagnostics"]:
        if row["data_origin"] == "SYNTHETIC_DEMO":
            assert row["layouts"]["baseline"]["predicted"]["zone_entry_count"] == 20
            assert row["layouts"]["intervention"]["predicted"]["captured_before_zone_count"] == 20
            assert row["layouts"]["baseline"]["observed"]["released"] == 2
    assert result["by_origin"]["OPERATOR_REPORTED_PHYSICAL"]["plan"]["recorded_total"] == 0


def test_detached_timestamp_changes_neither_input_hash_nor_report():
    value = bundle()
    expected = run(value)
    value["metadata"]["exported_at"] = "2026-10-18T00:00:00Z"
    assert run(value) == expected


def test_all_unresolved_and_no_trials_remain_unknown_with_real_denominators():
    value = bundle()
    for trial in value["payload"]["trials"]:
        trial.update(outcome="unresolved", entry_time_s=None, interception_time_s=None,
                     token_accounted=False, horizon_completed=False)
    result = run(seal(value))
    group = result["by_origin"]["SYNTHETIC_DEMO"]
    assert group["layouts"]["baseline"]["unresolved"] == 4
    assert group["layouts"]["baseline"]["observed_entry_rate_bounds"] == {
        "lower": 0.0, "upper": 1.0, "denominator": 4, "kind": "actual_releases_including_unresolved"}
    assert result["selected_layout_usefulness"]["SYNTHETIC_DEMO"]["status"].startswith("UNRESOLVED")
    assert result["next_measurement"]["kind"] == "INDEPENDENT_PAIRED_TRIAL"
    value["payload"]["trials"] = []
    value["payload"]["evaluation_truth"]["trial_sources"] = []
    result = run(seal(value))
    assert result["by_origin"]["SYNTHETIC_DEMO"]["layouts"]["baseline"]["missing_planned"] == 4
    assert result["by_origin"]["SYNTHETIC_DEMO"]["layouts"]["baseline"]["observed_entry_rate_bounds"]["denominator"] == 0


def test_incomplete_unbalanced_plan_exposes_missing_slots_and_never_drops_denominator():
    value = bundle()
    value["payload"]["trials"] = value["payload"]["trials"][:1]
    identities = {row["id"] for row in value["payload"]["trials"]}
    value["payload"]["evaluation_truth"]["trial_sources"] = [r for r in value["payload"]["evaluation_truth"]["trial_sources"] if r["trial_id"] in identities]
    result = run(seal(value))
    group = result["by_origin"]["SYNTHETIC_DEMO"]
    assert group["plan"]["recorded_total"] == 1
    assert group["plan"]["complete"] is False and group["plan"]["balanced"] is False
    assert sum(row["missing_planned"] for row in group["layouts"].values()) == 7
    assert result["next_measurement"]["kind"] == "INDEPENDENT_PAIRED_TRIAL"


def test_heldout_outcomes_can_contradict_proposed_model_and_favor_baseline():
    value = bundle()
    for trial in value["payload"]["trials"]:
        trial.update(outcome="no_entry" if trial["layout"] == "baseline" else "zone_entry",
                     entry_time_s=None if trial["layout"] == "baseline" else 5.0,
                     interception_time_s=None)
    result = run(seal(value))
    assert result["selected_layout_usefulness"]["SYNTHETIC_DEMO"]["status"] == "CONTRADICTED_BY_REPORTED_NEW_TRIALS"
    assert result["by_origin"]["SYNTHETIC_DEMO"]["effect_bounds"] == {
        "lower": -1.0, "upper": -1.0, "kind": "baseline_minus_intervention_planned_entry_fraction"}
    assert result["next_measurement"]["reason_codes"] == ["PREDICTION_OUTCOME_DISAGREEMENT"]
    assert result["next_measurement"]["collector_movement_requires_fresh_layout_drift"] is True
    assert any(row["layouts"]["baseline"]["prediction_outside_recorded_bounds"] for row in result["diagnostics"] if row["data_origin"] == "SYNTHETIC_DEMO")


def test_unsupported_flow_prioritizes_drift_without_invented_region():
    value = bundle()
    for profile in value["payload"]["profiles"].values():
        profile["flow"]["coverage_radius_cm"] = 0.01
    result = run(seal(value, freeze=True))
    recommendation = result["next_measurement"]
    assert recommendation["kind"] == "INDEPENDENT_LAYOUT_DRIFT"
    assert recommendation["region_identified"] is False and recommendation["region_cm"] is None
    assert "USEFUL_REGION_NOT_LOCALIZED_IN_SAVED_REPORT" in recommendation["reason_codes"]


@pytest.mark.parametrize("target", ["trial_ids", "recording_ids", "session_ids"])
def test_development_validation_identity_leakage(target):
    value = bundle()
    p = value["payload"]
    if target == "recording_ids":
        # Invented recordings on synthetic trials are already independently invalid.
        p["protocols"]["development"][target] = ["same-recording"]
        p["protocols"]["validation"][target] = ["same-recording"]
    else:
        p["protocols"]["development"][target] = p["protocols"]["validation"][target][:1]
    value["content_hash"] = content_hash(p)
    value["id"] = "analysis-bundle-" + value["content_hash"][:20]
    with pytest.raises(ValueError, match="leakage"):
        run(value)


@pytest.mark.parametrize("edit,match", [
    (lambda p: p["trials"].append(copy.deepcopy(p["trials"][0])), "Duplicate"),
    (lambda p: p["evaluation_truth"]["trial_sources"].append(copy.deepcopy(p["evaluation_truth"]["trial_sources"][0])), "Duplicate"),
    (lambda p: p["trials"][0].update(id="wrong-trial"), "ID mismatch"),
    (lambda p: p["trials"][0].update(ordinal=2), "ordinal"),
    (lambda p: p["trials"][0].update(created_at=1), "predates"),
    (lambda p: p["trials"][0].update(note="private arbitrary note"), "private/truth"),
    (lambda p: p["profiles"]["baseline"]["flow"].update(password="secret"), "private/truth"),
    (lambda p: p["comparison"]["plan"].update(trials_per_source=3), "denominator"),
    (lambda p: p["comparison"]["numerical_report"]["results"][0]["baseline"].update(zone_entry_count=0), "frozen plan/comparison"),
    (lambda p: p["profiles"]["intervention"].update(token_class="different"), "profile"),
    (lambda p: p["evaluation"].update(export_snapshot_hash="0" * 64), "evaluation hash"),
    (lambda p: p["evaluation"].update(source_evaluation_id="wrong"), "evaluation ID"),
    (lambda p: p["protocols"]["development"].update(selected_layout="baseline"), "selection"),
])
def test_tampered_frozen_id_hash_or_contract_is_refused(edit, match):
    value = bundle()
    edit(value["payload"])
    value["content_hash"] = content_hash(value["payload"])
    value["id"] = "analysis-bundle-" + value["content_hash"][:20]
    with pytest.raises(ValueError, match=match):
        run(value)


def test_outer_stale_hash_nonfinite_values_and_protocol_relabelling_fail():
    value = bundle()
    value["payload"]["trials"][0]["token_accounted"] = False
    with pytest.raises(ValueError, match="bundle hash"):
        run(value)
    value = bundle()
    value["payload"]["comparison"]["horizon_s"] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        run(value)
    with pytest.raises(ValueError, match="identity"):
        validate_bundle(bundle(), development_protocol_id=DEV, validation_protocol_id=DEV + "-relabeled")


def test_mixed_origins_and_synthetic_physical_claim_are_refused():
    value = bundle()
    value["payload"]["trials"][0].update(data_origin="OPERATOR_REPORTED_PHYSICAL", physical_confirmed=True)
    with pytest.raises(ValueError, match="Mixed synthetic/physical"):
        run(seal(value))
    for trial in value["payload"]["trials"]:
        trial.update(data_origin="OPERATOR_REPORTED_PHYSICAL", physical_confirmed=True)
    with pytest.raises(ValueError, match="Synthetic simulation"):
        run(seal(value))


def test_session_dependence_is_disclosed_not_significance():
    value = bundle()
    p = value["payload"]
    for receipt in p["trial_sessions"]:
        receipt["session_id"] = "same-validation-session"
    p["protocols"]["validation"]["session_ids"] = ["same-validation-session"]
    value["content_hash"] = content_hash(p)
    value["id"] = "analysis-bundle-" + value["content_hash"][:20]
    result = run(value)
    assert result["dependence_warnings"] == ["WITHIN_VALIDATION_SESSION_REUSE"]
    assert result["supports_significance_or_causal_claim"] is False


def test_cli_is_deterministic_bounded_and_failure_does_not_overwrite(tmp_path):
    source = FIXTURES / "prevention_validation" / "analysis_bundle_v1.json"
    output = tmp_path / "report.json"
    args = [str(source), "--development-protocol", DEV, "--validation-protocol", TEST, "--output", str(output)]
    assert main(args) == 0
    first = output.read_bytes()
    assert main(args) == 0 and output.read_bytes() == first
    invalid = tmp_path / "invalid.json"
    for text in ('{"payload":{},"payload":{}}', '{"x":NaN}', '{"x":1e999}', '[' * 1000):
        invalid.write_text(text)
        with pytest.raises(SystemExit) as error:
            main([str(invalid), *args[1:]])
        assert error.value.code == 2 and output.read_bytes() == first
    with pytest.raises(SystemExit):
        main([str(source), *args[1:-1], str(source)])


def test_validation_has_no_database_or_network_side_effects(monkeypatch):
    import socket
    import sqlite3

    def forbidden(*args, **kwargs):
        raise AssertionError("Offline validation cannot access accounts, camera or database")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    assert run(bundle())["numerical_replay_verified"] is True


def measured_fixture():
    """Fake operator-reported inputs for rejection tests, never physical evidence."""
    value = bundle()
    p = value["payload"]
    p["comparison"]["data_origin"] = "MEASURED_TANK"
    development = p["protocols"]["development"]
    for layout, profile in p["profiles"].items():
        profile["data_origin"] = profile["flow"]["data_origin"] = "MEASURED_TANK"
        profile["flow"]["id"] = layout + "-flow-fixture"
        profile["max_validation_rmse_cm_s"] = 0.2
        profile["flow"]["diagnostics"].update(validation_rmse_cm_s=0.1, validation_coverage_fraction=1.0)
        profile["flow"]["provenance"] = {
            "calibration_id": profile["calibration_id"], "camera_session_id": layout + "-drift-session",
            "training_recording_ids": [layout + "-drift-train"],
            "validation_recording_ids": [layout + "-drift-validation"], "frame_splits_disjoint": True}
        development["recording_ids"].extend([layout + "-drift-train", layout + "-drift-validation"])
        development["session_ids"].append(layout + "-drift-session")
    for trial in p["trials"]:
        trial.update(data_origin="OPERATOR_REPORTED_PHYSICAL", physical_confirmed=True,
                     recording_id="heldout-recording-" + str(trial["ordinal"]))
    return seal(value, freeze=True)


def test_duplicate_physical_recording_id_refused_and_physical_origin_stays_unverified():
    value = measured_fixture()
    result = run(value)
    assert result["data_origin"] == "MEASURED_TANK" and result["physical_validation"] is False
    assert result["selected_layout_usefulness"]["OPERATOR_REPORTED_PHYSICAL"]["physical_results_claimed"] is False
    p = value["payload"]
    p["trials"][1]["recording_id"] = p["trials"][0]["recording_id"]
    with pytest.raises(ValueError, match="Duplicate recording"):
        run(seal(value))


def test_flow_training_test_and_outcome_recordings_cannot_overlap():
    value = measured_fixture()
    p = value["payload"]
    p["trials"][0]["recording_id"] = p["profiles"]["baseline"]["flow"]["provenance"]["training_recording_ids"][0]
    with pytest.raises(ValueError, match="leakage"):
        run(seal(value))
    value = measured_fixture()
    flow = value["payload"]["profiles"]["baseline"]["flow"]
    flow["provenance"]["validation_recording_ids"] = flow["provenance"]["training_recording_ids"][:]
    with pytest.raises(ValueError, match="training/validation recording leakage"):
        run(seal(value, freeze=True))


def test_trial_quota_overflow_cannot_hide_in_planned_denominator():
    value = bundle()
    p = value["payload"]
    original = p["trials"][0]
    trial = {**original, "trial_key": "extra-release", "ordinal": len(p["trials"]) + 1}
    trial["id"] = "prevention-trial-" + content_hash([p["comparison"]["id"], trial["trial_key"]])[:24]
    p["trials"].append(trial)
    source = p["evaluation_truth"]["trial_sources"][0]["source_id"]
    p["evaluation_truth"]["trial_sources"].append({"trial_id": trial["id"], "source_id": source})
    with pytest.raises(ValueError, match="quota exceeded"):
        run(seal(value))


def test_changed_plan_is_refused_even_with_new_valid_plan_and_evaluation_hashes():
    value = bundle()
    c = value["payload"]["comparison"]
    c["plan"]["horizon_s"] = c["horizon_s"] = 9.0
    c["plan"]["id"] = "prevention-plan-" + content_hash({k: v for k, v in c["plan"].items() if k != "id"})[:20]
    c["numerical_report"] = compare_layouts(value["payload"]["profiles"]["baseline"], value["payload"]["profiles"]["intervention"], c["protected_zone_cm"], horizon_s=9.0, particles=20, seed=7)
    with pytest.raises(ValueError, match="Changed frozen plan/comparison"):
        run(seal(value))


def test_zero_width_no_effect_does_not_invent_a_useful_source_or_region():
    value = bundle()
    p = value["payload"]
    p["profiles"]["intervention"]["traps"] = []
    for trial in p["trials"]:
        trial.update(outcome="zone_entry", entry_time_s=6.0, interception_time_s=None)
    result = run(seal(value, freeze=True))
    assert result["next_measurement"]["kind"] == "NO_USEFUL_NEXT_MEASUREMENT_IDENTIFIED"
    assert result["next_measurement"]["region_cm"] is None


def test_cli_rejects_oversized_input_before_json_parsing(tmp_path):
    source = tmp_path / "oversized.json"
    source.write_bytes(b" " * 2_000_001)
    with pytest.raises(SystemExit) as error:
        main([str(source), "--development-protocol", DEV, "--validation-protocol", TEST,
              "--output", str(tmp_path / "report.json")])
    assert error.value.code == 2 and not (tmp_path / "report.json").exists()


def test_lane_three_report_parser_checks_exact_fixture_hash_and_current_lineage():
    from apps.estimation.reeftrace_estimation.prevention_validation import parse_validation_report

    report = json.loads((FIXTURES / "team_handoff" / "validation_report_v1.json").read_text())
    expected = {key: report[key] for key in ("input_bundle_hash", "comparison_id", "export_evaluation_hash")}
    assert parse_validation_report(report, **expected) == report
    with pytest.raises(ValueError, match="lineage"):
        parse_validation_report(report, **{**expected, "input_bundle_hash": "0" * 64})
    with pytest.raises(ValueError, match="lineage"):
        parse_validation_report(report, **{**expected, "export_evaluation_hash": "0" * 64})
    report["next_measurement"]["kind"] = "INVENTED_OPTIMAL_MEASUREMENT"
    with pytest.raises(ValueError, match="hash/ID"):
        parse_validation_report(report, **expected)


def test_forged_prediction_is_replayed_even_after_exporter_commitments_are_rehashed():
    value = bundle()
    p = value["payload"]
    p["comparison"]["numerical_report"]["results"][0]["baseline"]["zone_entry_count"] = 0
    for protocol in p["protocols"].values():
        protocol["comparison_hash"] = content_hash(p["comparison"])
    with pytest.raises(ValueError, match="Stale/tampered numerical report"):
        run(seal(value))


def test_exported_evaluation_cannot_change_actual_release_denominator():
    value = bundle()
    p = value["payload"]
    p["evaluation"]["by_origin"]["SYNTHETIC_DEMO"]["layouts"]["baseline"]["observed_entry_rate_bounds"]["denominator"] = 40
    value["content_hash"] = content_hash(p)
    value["id"] = "analysis-bundle-" + value["content_hash"][:20]
    with pytest.raises(ValueError, match="denominator/accounting"):
        run(value)


def test_scenario_rows_do_not_multiply_trial_release_denominators():
    result = run(bundle())
    scenarios = {r["scenario_id"] for r in result["diagnostics"]}
    assert len(scenarios) == 2
    assert result["by_origin"]["SYNTHETIC_DEMO"]["plan"]["recorded_total"] == 8
    assert all(row["scenario_observation_label"].startswith("NONE_same_source") for row in result["diagnostics"])


@pytest.mark.parametrize("edit", [
    lambda p: p["comparison"]["plan"].update(horizon_s=True),
    lambda p: p["comparison"]["plan"]["sequence"][0].update(repeat=True),
    lambda p: p["profiles"]["baseline"].update(data_origin="MEASURED_TANK"),
    lambda p: p["trials"][0].update(source_id="A"),
    lambda p: p["profiles"]["baseline"]["flow"].update(absolute_path="/private/camera.png"),
])
def test_strict_numeric_origin_truth_and_path_boundaries(edit):
    value = bundle()
    edit(value["payload"])
    value["content_hash"] = content_hash(value["payload"])
    value["id"] = "analysis-bundle-" + value["content_hash"][:20]
    with pytest.raises(ValueError):
        run(value)
