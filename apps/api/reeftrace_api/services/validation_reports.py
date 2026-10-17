"""Check exported identities and recompute accounting, without rerunning Trace 2.

Accepted records are immutable receipts of a declared split. They do not verify
an independent scientific protocol or accept arbitrary uploaded metrics.
"""

from __future__ import annotations

import json
import time

from ..schemas.validation_reports import (
    VERIFICATION,
    ValidationReportInput,
    ValidationReportManifest,
)
from .evidence_export import export_comparison
from .prevention import COMPARISON_KIND, LAYOUTS, ORIGINS, PreventionService, digest

VALIDATION_KIND = "prevention_validation_report"

LIMITATIONS = [
    "Identity and trial accounting were checked against the exact local export; the external validation method was not rerun.",
    "Split labels are declarations, not proof of independence, preregistration or unseen test outcomes.",
    "Synthetic rehearsals and operator-reported physical outcomes are separate; outcomes are not automatically camera-verified.",
    "Bounds describe missing or unresolved recorded outcomes, not confidence intervals or calibrated probabilities.",
    "The original per-source/layout quota remains the validation target; development trials are excluded, not counted as validation successes.",
    "No causal effect, reef benefit, polluter identity or ocean generalization is established.",
]


def _current_bundle(runtime, comparison_id):
    bundle = export_comparison(runtime, comparison_id)
    if not bundle["metadata"]["is_current"]:
        raise ValueError("Source case changed or stopped; only current comparisons accept validation manifests")
    return bundle


def template_validation_report(runtime, comparison_id, outcome_origin="SYNTHETIC_DEMO"):
    """Return a nonpersisted rehearsal manifest using only existing origin trials."""
    if outcome_origin not in ORIGINS:
        raise ValueError("Choose one existing trial origin")
    bundle = _current_bundle(runtime, comparison_id)
    payload = bundle["payload"]
    if outcome_origin == "OPERATOR_REPORTED_PHYSICAL" and payload["comparison"]["data_origin"] != "MEASURED_TANK":
        raise ValueError("Synthetic layout cannot prepare a physical validation manifest")
    trial_ids = [trial["id"] for trial in payload["evaluation_truth"]["trials"]
                 if trial["data_origin"] == outcome_origin]
    if not trial_ids:
        raise ValueError("Selected origin has no recorded trials; record actual outcomes before preparing a rehearsal")
    return ValidationReportManifest(
        schema_version="validation_report_v1", comparison_id=comparison_id,
        input_payload_sha256=bundle["payload_sha256"],
        evaluation_snapshot_hash=payload["evaluation_truth"]["evaluation"]["snapshot_hash"],
        data_origin=payload["comparison"]["data_origin"], outcome_origin=outcome_origin,
        protocol_id="contract-rehearsal-v1", purpose="CONTRACT_REHEARSAL",
        development_trial_ids=[], validation_trial_ids=trial_ids,
    ).model_dump(mode="json")


def _check_manifest(manifest, bundle):
    payload = bundle["payload"]
    comparison, evaluation = payload["comparison"], payload["evaluation_truth"]["evaluation"]
    if (manifest.comparison_id != comparison["id"]
            or manifest.input_payload_sha256 != bundle["payload_sha256"]
            or manifest.evaluation_snapshot_hash != evaluation["snapshot_hash"]
            or manifest.data_origin != comparison["data_origin"]):
        raise ValueError("Validation manifest does not match the exact current comparison/export/evaluation")
    if (manifest.outcome_origin == "OPERATOR_REPORTED_PHYSICAL"
            and manifest.data_origin != "MEASURED_TANK"):
        raise ValueError("Synthetic layout cannot claim a physical validation partition")
    trials = payload["evaluation_truth"]["trials"]
    by_id = {trial["id"]: trial for trial in trials}
    expected_ids = {trial["id"] for trial in trials if trial["data_origin"] == manifest.outcome_origin}
    declared_ids = set(manifest.development_trial_ids + manifest.validation_trial_ids)
    if declared_ids != expected_ids:
        raise ValueError("Development and validation IDs must exactly partition all existing trials of the selected origin")
    development = [by_id[trial_id] for trial_id in manifest.development_trial_ids]
    validation = [by_id[trial_id] for trial_id in manifest.validation_trial_ids]
    dev_recordings = {trial["recording_id"] for trial in development if trial["recording_id"]}
    validation_recordings = [trial["recording_id"] for trial in validation if trial["recording_id"]]
    if len(set(validation_recordings)) != len(validation_recordings) or dev_recordings & set(validation_recordings):
        raise ValueError("One recording cannot appear as multiple or overlapping development/validation releases")
    fit_recordings = set()
    for layout in LAYOUTS:
        flow = payload["provenance"]["layouts"][layout]["flow"]
        fit_recordings.update(flow["training_recording_ids"] + flow["validation_recording_ids"])
    if fit_recordings & set(validation_recordings):
        raise ValueError("Validation outcomes cannot reuse a recording used to fit or validate a layout flow")
    return development, validation


def _summary(manifest, payload, development, validation):
    comparison, plan = payload["comparison"], payload["frozen_plan"]
    numerical = comparison["numerical_report"]
    rows = []
    for source_id in plan["source_ids"]:
        prediction = next(row for row in numerical["results"]
                          if row["source_id"] == source_id and row["scenario_id"] == "nominal")
        for layout in LAYOUTS:
            trials = [trial for trial in validation
                      if trial["source_id"] == source_id and trial["layout"] == layout]
            stats = PreventionService._stats(trials, comparison["trials_per_source"])
            simulated = prediction[layout]
            rows.append({"source_id": source_id, "layout": layout, **stats,
                "predicted_entry_fraction": (None if simulated["unsupported_count"]
                                             else simulated["zone_entry_fraction"]),
                "predicted_entry_bounds": {"lower": simulated["zone_entry_lower_fraction"],
                                            "upper": simulated["zone_entry_upper_fraction"]}})
    missing = sum(row["missing_planned"] for row in rows)
    unsupported = [row for row in numerical["results"]
                   if any(row[layout]["unsupported_count"] for layout in LAYOUTS)]
    if unsupported:
        row = unsupported[0]
        next_measurement = {"action": "MEASURE_LAYOUT_DRIFT", "reason_codes": ["UNSUPPORTED_FLOW"],
            "source_id": row["source_id"], "scenario_id": row["scenario_id"],
            "layout": next(layout for layout in LAYOUTS if row[layout]["unsupported_count"]),
            "location_cm": None}
    elif len(development) + len(validation) < plan["expected_total"]:
        # Follow the frozen sequence, rather than adaptively selecting a cell
        # after seeing favorable outcomes. Development slots do not become test data.
        used = {}
        for trial in development + validation:
            key = trial["layout"], trial["source_id"]
            used[key] = used.get(key, 0) + 1
        slot = None
        for candidate in plan["sequence"]:
            key = candidate["layout"], candidate["source_id"]
            if used.get(key, 0):
                used[key] -= 1
            else:
                slot = candidate
                break
        next_measurement = {"action": "COMPLETE_FROZEN_PLAN", "reason_codes": ["MISSING_VALIDATION_SLOTS"],
            "source_id": slot["source_id"], "layout": slot["layout"], "location_cm": None}
    else:
        next_measurement = {"action": "DECLARE_NEW_INDEPENDENT_PROTOCOL",
            "reason_codes": ["METHOD_NOT_RERUN", "INDEPENDENCE_NOT_VERIFIED"], "location_cm": None}
    return {"by_source": rows, "development_count": len(development), "validation_count": len(validation),
        "missing_planned": missing, "unresolved": sum(row["unresolved"] for row in rows),
        "data_origin": manifest.data_origin, "outcome_origin": manifest.outcome_origin,
        "purpose": manifest.purpose, "limitations": list(LIMITATIONS),
        "next_measurement": next_measurement, "physical_validation": False,
        "supports_causal_claim": False, "calibrated_probability": False}


def accept_validation_report(runtime, comparison_id, body: ValidationReportInput):
    """Persist a checked manifest only while its exact exported lineage is current."""
    manifest = body.report
    if manifest.comparison_id != comparison_id:
        raise ValueError("Route comparison and manifest comparison disagree")
    bundle = _current_bundle(runtime, comparison_id)
    development, validation = _check_manifest(manifest, bundle)
    payload = bundle["payload"]
    comparison = runtime.store.get(COMPARISON_KIND, comparison_id)
    request = manifest.model_dump(mode="json")
    report_id = "validation-report-" + digest(request)[:24]
    checks = {"identity_verified": True, "accounting_verified": True,
              "method_rerun": False, "physical_validation": False}
    summary = _summary(manifest, payload, development, validation)
    report = {**request, "id": report_id, "case_id": comparison["case_id"],
        "case_revision": comparison["case_revision"], "source_evidence_id": comparison["source_evidence_id"],
        "created_at": time.time(), "verification": VERIFICATION}
    with runtime.store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT payload FROM cases WHERE id=?", (comparison["case_id"],)).fetchone()
        if row is None:
            raise KeyError(comparison["case_id"])
        runtime.prevention._assert_case(comparison, json.loads(row[0]))
        evaluation = runtime.prevention.evaluate(comparison, runtime.prevention._trials(comparison_id, db))
        if evaluation["snapshot_hash"] != manifest.evaluation_snapshot_hash:
            raise ValueError("Trial evaluation changed while checking validation; export the new snapshot")
        existing = db.execute("SELECT payload FROM records WHERE kind=? AND id=?",
                              (VALIDATION_KIND, report_id)).fetchone()
        if existing:
            saved = json.loads(existing[0])
        else:
            saved = {"id": report_id, "comparison_id": comparison_id, "report": report,
                     "checks": checks, "summary": summary}
            db.execute("INSERT INTO records VALUES(?,?,?,?)", (
                VALIDATION_KIND, report_id, json.dumps(saved, allow_nan=False), report["created_at"]))
    return _detail(runtime, saved)


def _detail(runtime, saved):
    bundle = export_comparison(runtime, saved["comparison_id"])
    if not bundle["metadata"]["is_current"]:
        reason = "CASE_CHANGED_OR_STOPPED"
    elif bundle["payload_sha256"] != saved["report"]["input_payload_sha256"]:
        reason = "EVALUATION_CHANGED"
    else:
        reason = None
    return {"report": saved["report"], "checks": saved["checks"], "summary": saved["summary"],
            "is_current": reason is None, "archive_reason": reason}


def get_validation_report(runtime, report_id):
    return _detail(runtime, runtime.store.get(VALIDATION_KIND, report_id))


def list_validation_reports(runtime, comparison_id):
    runtime.store.get(COMPARISON_KIND, comparison_id)
    with runtime.store.connection() as db:
        rows = db.execute("SELECT payload FROM records WHERE kind=? "
            "AND json_extract(payload,'$.comparison_id')=? ORDER BY created DESC,id LIMIT 100",
            (VALIDATION_KIND, comparison_id)).fetchall()
    summaries = []
    for row in rows:
        detail = _detail(runtime, json.loads(row[0]))
        report = detail["report"]
        summaries.append({key: report[key] for key in ("id", "comparison_id", "case_id",
            "source_evidence_id", "evaluation_snapshot_hash", "input_payload_sha256", "data_origin",
            "outcome_origin", "protocol_id", "purpose", "created_at", "verification")}
            | {"is_current": detail["is_current"], "archive_reason": detail["archive_reason"]})
    return summaries
