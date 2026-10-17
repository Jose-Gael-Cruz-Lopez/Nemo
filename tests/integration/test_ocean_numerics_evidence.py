"""Exact-hash Chalk evidence retains both numerical experiments and limits."""

from __future__ import annotations

import asyncio
import copy
import json
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest

from adapters.chalk.agent import ChalkSettings
from apps.api.reeftrace_api.services import ocean_prevention_investigation as service
from apps.ocean.reeftrace_ocean import ocean_prevention as ocean


@pytest.fixture(scope="module")
def reports():
    return {identity: ocean.run_ocean_prevention(identity) for identity in ocean.SUPPORTED_SCENARIOS}


def sign(report):
    report["report_sha256"] = service._report_hash(report)
    return report


def test_real_pinned_numerics_leave_main_comparison_and_negative_control_unchanged(reports):
    downstream = reports["downstream-corridor-v2"]
    control = reports["initial-proxy-v1"]
    assert [layout["summary"]["protected_entry_count_bounds"] for layout in downstream["layouts"]] == [
        [2, 2], [4, 4]]
    assert downstream["recommendation"]["best_layout_id"] == "central"
    assert control["recommendation"]["status"] == "TIE"
    for report in reports.values():
        assert service.snapshot_identity(report)[-1] == report["report_sha256"]
        assert len(json.dumps(report).encode()) < 750_000
        numerical = report["numerical_sensitivity"]
        assert numerical["summary"]["all_integrations_completed"] is True
        assert numerical["summary"]["event_recommendation_agrees_at_all_levels"] is True
        assert [row["solver_step_s"] for row in numerical["integration"]["levels"]] == [300, 150, 75]
        for level in numerical["events"]["levels"]:
            assert all(row["summary"]["release_count"] == 6 for row in [level["baseline"], *level["layouts"]])
            assert level["recommendation"]["status"] == report["recommendation"]["status"]
            assert level["recommendation"]["best_layout_id"] == report["recommendation"]["best_layout_id"]
        assert report["method"]["paths_integrated_once_per_release"] is True
        assert "main_decision_paths_only" in report["method"]["paths_integrated_once_scope"]


def test_optional_field_is_hash_bound_and_legacy_absence_remains_valid(reports):
    report = copy.deepcopy(reports["downstream-corridor-v2"])
    original_identity = service.snapshot_identity(report)
    report["numerical_sensitivity"]["summary"]["integration_max_separation_m"] += 1
    with pytest.raises(ValueError, match="digest"):
        service.snapshot_identity(report)
    report.pop("numerical_sensitivity")
    sign(report)
    assert service.snapshot_identity(report)[-1] != original_identity[-1]
    assert "numerical_sensitivity" not in service._compact_summary(report)


@pytest.mark.parametrize("path,value", [
    (("physical_validation",), True),
    (("independent_truth_used",), True),
    (("model_parameters_tuned",), True),
    (("release_count",), 5),
    (("integration", "levels", 0, "release_count"), 5),
    (("integration", "levels", 0, "output_step_s"), 150),
    (("integration", "levels", 0, "forcing_status_counts", "PARTIAL"), 1),
    (("integration", "levels", 0, "releases", 0, "comparison", "common_positive_time_count"), 0),
    (("integration", "levels", 0, "releases", 0, "comparison", "max_separation_m"), None),
    (("integration", "levels", 0, "releases", 0, "comparison", "reference_forcing_status"), "UNKNOWN"),
    (("integration", "levels", 0, "releases", 0, "comparison", "reference_completed_horizon_s"), 999999),
    (("integration", "levels", 0, "releases", 0, "comparison", "rms_separation_m"), 999999),
    (("integration", "levels", 0, "releases", 0, "forcing_reason_code"), "OUTSIDE_FORCING_TIME"),
    (("events", "same_fine_tracks_downsampled"), False),
    (("events", "levels", 0, "recommendation", "best_layout_id"), "flanking"),
    (("events", "levels", 0, "baseline", "summary", "release_count"), 5),
    (("events", "levels", 0, "layouts", 0, "outcomes", 0, "segment_id"), "wrong-collector"),
    (("events", "levels", 0, "layouts", 0, "outcomes", 0, "completed_horizon_s"), 999999),
    (("events", "levels", 0, "layouts", 0, "outcomes", 0, "event_elapsed_s"), 999999),
    (("events", "levels", 0, "comparison_to_finest", "max_matched_event_time_difference_s"), 0),
    (("summary", "all_integrations_completed"), False),
    (("summary", "integration_max_separation_m"), 0),
])
def test_resigned_malformed_numerics_cannot_upgrade_scope_or_change_accounting(reports, path, value):
    report = copy.deepcopy(reports["downstream-corridor-v2"])
    current = report["numerical_sensitivity"]
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = value
    sign(report)
    with pytest.raises((ValueError, TypeError)):
        service.snapshot_identity(report)


def test_numerical_event_comparisons_cannot_pair_different_release_identities(reports):
    report = copy.deepcopy(reports["downstream-corridor-v2"])
    # Every fixed release remains present, but the positional pairing to the
    # finest event reference is now wrong. Count-only validation is insufficient.
    outcomes = report["numerical_sensitivity"]["events"]["levels"][0]["layouts"][0]["outcomes"]
    outcomes[0], outcomes[1] = outcomes[1], outcomes[0]
    sign(report)
    with pytest.raises(ValueError, match="sensitivity"):
        service.snapshot_identity(report)


@pytest.mark.parametrize("experiments", [("integration",), ("events",), ("integration", "events")])
def test_resigned_coordinated_diagnostic_horizons_must_match_frozen_release_horizons(
    reports, experiments,
):
    report = copy.deepcopy(reports["downstream-corridor-v2"])
    numerical = report["numerical_sensitivity"]
    if "integration" in experiments:
        for level in numerical["integration"]["levels"]:
            for row in level["releases"]:
                # Every diagnostic level, reference and declared completed
                # output agrees internally, but differs from the frozen input.
                row["requested_horizon_s"] = row["completed_horizon_s"] = 24000
                row["comparison"]["reference_completed_horizon_s"] = 24000
                row["comparison"]["last_common_elapsed_s"] = 24000
                row["comparison"]["common_positive_time_count"] = 80
    if "events" in experiments:
        for level in numerical["events"]["levels"]:
            for layout in [level["baseline"], *level["layouts"]]:
                for row in layout["outcomes"]:
                    row["requested_horizon_s"] = row["completed_horizon_s"] = 24000
    sign(report)  # A fresh digest is insufficient to approve a different experiment.
    assert all(release["horizon_s"] == 21600 for release in report["scenario"]["releases"])
    assert len(report["releases"]) == numerical["release_count"] == 6
    with pytest.raises(ValueError, match="sensitivity"):
        service.snapshot_identity(report)


@pytest.mark.parametrize("coverage", ["PARTIAL", "UNSUPPORTED"])
def test_horizon_binding_accepts_censored_forcing_and_keeps_every_frozen_release(
    monkeypatch, coverage,
):
    field, manifest = ocean.load_current_snapshot()
    # Deliberately truncated local test forcing; this is not a new data product
    # or a claim that the pinned public snapshot itself has missing observations.
    if coverage == "PARTIAL":
        censored = replace(field, time_utc=field.time_utc[:2], eastward_m_s=field.eastward_m_s[:2],
                           northward_m_s=field.northward_m_s[:2], valid_mask=field.valid_mask[:2])
    else:
        mask = field.valid_mask.copy()
        mask[:] = False
        mask[0, 0, 0] = True  # One remote sample remains valid; all releases lack forcing.
        censored = replace(field, valid_mask=mask)
    monkeypatch.setattr(ocean, "load_current_snapshot", lambda: (censored, manifest))
    report = ocean.run_ocean_prevention()
    assert service.snapshot_identity(report)[-1] == report["report_sha256"]
    assert report["status"] == coverage
    numerical = report["numerical_sensitivity"]
    assert numerical["summary"]["all_integrations_completed"] is False
    for level in numerical["integration"]["levels"]:
        assert level["release_count"] == level["forcing_status_counts"][coverage] == 6
        completed = 10800 if coverage == "PARTIAL" else 0
        assert all(row["requested_horizon_s"] == 21600 and row["completed_horizon_s"] == completed
                   for row in level["releases"])
    for level in numerical["events"]["levels"]:
        for row in [level["baseline"], *level["layouts"]]:
            assert row["summary"]["release_count"] == len(row["outcomes"]) == 6
            assert all(outcome["requested_horizon_s"] == 21600
                       and outcome["forcing_status"] == coverage for outcome in row["outcomes"])


def test_resigned_finest_path_cannot_claim_nonzero_separation_from_itself(reports):
    report = copy.deepcopy(reports["downstream-corridor-v2"])
    numerical = report["numerical_sensitivity"]
    fine = numerical["integration"]["levels"][-1]
    comparison = fine["releases"][0]["comparison"]
    for key in ("max_separation_m", "rms_separation_m", "last_common_separation_m"):
        comparison[key] = 0.1
    fine["max_separation_m"] = numerical["summary"]["integration_max_separation_m"] = 0.1
    sign(report)
    with pytest.raises(ValueError, match="sensitivity"):
        service.snapshot_identity(report)


def test_resigned_completed_pair_cannot_withhold_its_positive_common_time_coverage(reports):
    report = copy.deepcopy(reports["downstream-corridor-v2"])
    numerical = report["numerical_sensitivity"]
    coarse = numerical["integration"]["levels"][0]
    comparison = coarse["releases"][0]["comparison"]
    comparison.update(status="NO_COMMON_POSITIVE_TIME", common_positive_time_count=0,
                      last_common_elapsed_s=None, max_separation_m=None,
                      rms_separation_m=None, last_common_separation_m=None)
    assert comparison["both_completed"] is True
    coarse["comparable_release_count"] = 5
    coarse["max_separation_m"] = max(row["comparison"]["max_separation_m"]
                                      for row in coarse["releases"]
                                      if row["comparison"]["max_separation_m"] is not None)
    numerical["summary"]["integration_max_separation_m"] = max(
        level["max_separation_m"] for level in numerical["integration"]["levels"])
    sign(report)
    with pytest.raises(ValueError, match="sensitivity"):
        service.snapshot_identity(report)


def test_resigned_chord_levels_cannot_agree_on_an_undeclared_collector(reports):
    report = copy.deepcopy(reports["downstream-corridor-v2"])
    numerical = report["numerical_sensitivity"]
    for level in numerical["events"]["levels"]:
        for outcome in level["layouts"][0]["outcomes"]:
            if outcome["event_kind"] == "IDEALIZED_CAPTURE":
                outcome["segment_id"] = "nonexistent-collector"
    sign(report)
    assert numerical["summary"]["event_recommendation_agrees_at_all_levels"] is True
    with pytest.raises(ValueError, match="sensitivity"):
        service.snapshot_identity(report)


def test_same_clicked_hash_rejects_changed_numerics_after_chalk_review(reports, monkeypatch):
    original = reports["downstream-corridor-v2"]
    changed = copy.deepcopy(original)
    # A changed numerical experiment receives a new, internally valid report
    # identity. It cannot silently replace the evidence selected before billing.
    changed["numerical_sensitivity"]["limitations"].append("A newly documented numerical limitation.")
    sign(changed)
    assert service.snapshot_identity(changed) != service.snapshot_identity(original)
    reads = iter((original, changed))
    calls = []

    async def mocked_study(*args, **kwargs):
        calls.append(True)
        return {"action": "STOP", "explanation": "Research complete", "evidence_ids": []}

    monkeypatch.setattr(service, "investigate_study", mocked_study)
    runtime = SimpleNamespace(chalk_settings=lambda: object())
    with pytest.raises(ValueError, match="during the research review"):
        asyncio.run(service.investigate_ocean_prevention(
            runtime, "Explain the numerical limitations", **{key: original[key] for key in (
                "snapshot_sha256", "method_sha256", "scenario_sha256", "report_sha256")},
            loader=lambda: next(reads)))
    assert calls == [True]


def test_chalk_receives_compact_checked_numerical_evidence_and_exact_citations(reports):
    report = reports["downstream-corridor-v2"]
    source = copy.deepcopy(report)
    requests = []

    async def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        context = json.loads(payload["messages"][1]["content"])["trusted_context"]
        response = ({"tool": "get_study_evidence", "arguments": {}} if len(requests) == 1 else {
            "tool": "finish", "arguments": {"action": "REPORT", "evidence_ids": [
                context["study_evidence_id"], context["protocol_evidence_id"]],
                "explanation": "Central coverage has the lower conditional simulated entry range. Stable numerical checks do not establish physical accuracy. Independent current and interception measurements remain necessary."}})
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(response)}}]})

    async def execute():
        runtime = SimpleNamespace(chalk_settings=lambda: ChalkSettings(
            True, "https://chalk.example.test/v1/router", "TEST-KEY", "TEST-ENV", "TEST-MODEL"))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await service.investigate_ocean_prevention(
                runtime, "What do the separate solver and chord checks support?",
                **{key: report[key] for key in (
                    "snapshot_sha256", "method_sha256", "scenario_sha256", "report_sha256")},
                scenario_id="downstream-corridor-v2", client=client, loader=lambda: report)

    result = asyncio.run(execute())
    assert len(requests) == 2 and result["action"] == "REPORT"
    assert result["evidence_ids"] == ["ocean-comparison:" + report["report_sha256"],
                                       "ocean-method:" + report["method_sha256"]]
    evidence = result["trace"][0]["result"]["ocean_prevention"]
    checked = evidence["numerical_sensitivity"]
    assert checked["summary"] == report["numerical_sensitivity"]["summary"]
    assert checked["physical_validation"] is checked["independent_truth_used"] is False
    assert checked["events"]["same_fine_tracks_downsampled"] is True
    assert len(checked["integration"]["levels"]) == len(checked["events"]["levels"]) == 3
    assert checked["events"]["levels"][0]["comparison_to_finest"] == (
        report["numerical_sensitivity"]["events"]["levels"][0]["comparison_to_finest"])
    assert len(json.dumps(evidence).encode()) < 40_000
    assert '"track":' not in json.dumps(checked)
    system = requests[0]["messages"][0]["content"]
    assert "precision checks, not" in system and "not observed truth" in system
    assert "fourth-order convergence" in system
    assert report == source
    assert all(result[key] is False for key in ("store_written", "physical_validation", "hardware_actuation"))
