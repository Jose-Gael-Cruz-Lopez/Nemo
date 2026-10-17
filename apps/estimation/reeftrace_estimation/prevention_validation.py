"""Offline validation of whitelisted prevention exports; no inference truth or I/O."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections import Counter
from types import SimpleNamespace
from typing import Any, Literal, TypedDict

from apps.api.reeftrace_api.schemas.prevention import TrialInput
from apps.api.reeftrace_api.services.prevention import PreventionService
from apps.estimation.reeftrace_estimation.prevention import compare_layouts

MAX_BYTES = 2_000_000
MAX_TRIALS = 100
LAYOUTS = ("baseline", "intervention")
ORIGINS = ("SYNTHETIC_DEMO", "OPERATOR_REPORTED_PHYSICAL")
FORBIDDEN_KEYS = {"note", "notes", "credentials", "api_key", "phone", "phone_handle",
                  "absolute_path", "raw_image", "true_source", "expected_source", "password", "secret"}
LIMITATIONS = [
    "Particle fractions are model-conditional, not calibrated probabilities or confidence intervals.",
    "Outcome bounds describe logged releases and missing slots, not significance or a causal estimate.",
    "Synthetic and operator-reported physical outcomes are never pooled or automatically camera-verified.",
    "Distinct IDs and exporter session receipts do not prove experimental independence.",
    "No source-identification accuracy, ocean accuracy, coral survival or CO2 benefit is established.",
    "Repeated images of a retained endpoint do not recover missing history; a crop is not a new observation.",
    "Collector movement requires fresh independent layout-specific drift validation.",
    "Original private-ledger hashes are exporter receipts, not independently recomputed from scrubbed notes.",
    "Content hashes detect changed payloads relative to a receipt; they are not signatures or proof of authenticity.",
]


class ValidationReport(TypedDict):
    """Lane 3's versioned renderer contract; nested quantities retain ledger names."""

    schema_version: Literal["validation_report_v1"]
    id: str
    content_hash: str
    input_bundle_hash: str
    comparison_id: str
    plan_id: str
    source_evaluation_hash: str
    export_evaluation_hash: str
    original_private_hash_verified: bool
    numerical_replay_verified: bool
    development_protocol_id: str
    validation_protocol_id: str
    data_origin: str
    physical_validation: bool
    supports_significance_or_causal_claim: bool
    protocols: dict[str, Any]
    by_origin: dict[str, Any]
    diagnostics: list[dict[str, Any]]
    selected_layout_usefulness: dict[str, Any]
    source_identification: dict[str, Any]
    dependence_warnings: list[str]
    next_measurement: dict[str, Any]
    limitations: list[str]


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def content_hash(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _keys(value, required, optional=()):
    _require(isinstance(value, dict), "Expected a JSON object")
    _require(set(required) <= value.keys() <= set(required) | set(optional),
             "Missing or non-whitelisted fields")


def _id(value):
    _require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value),
             "Invalid bounded identifier")
    return value


def _hash(value):
    _require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "Invalid SHA-256")
    return value


def _ids(values):
    _require(isinstance(values, list) and len(values) <= 1000, "Invalid identity inventory")
    result = {_id(value) for value in values}
    _require(len(result) == len(values), "Duplicate trial/recording/session identity")
    return result


def _number(value):
    _require(type(value) in (int, float) and math.isfinite(value), "Expected a finite number")
    return value


def _safe(value, depth=0, budget=None):
    budget = budget if budget is not None else [100_000]
    budget[0] -= 1
    _require(depth <= 40 and budget[0] >= 0, "JSON structure budget exceeded")
    if isinstance(value, dict):
        for key, item in value.items():
            _require(isinstance(key, str) and key not in FORBIDDEN_KEYS, "Non-whitelisted private/truth field")
            _safe(item, depth + 1, budget)
    elif isinstance(value, list):
        for item in value:
            _safe(item, depth + 1, budget)
    elif isinstance(value, str):
        _require(len(value) <= 2000 and not value.startswith(("/", "\\"))
                 and not re.match(r"^[A-Za-z]:[\\/]", value), "Unbounded string or absolute local path")
    elif type(value) in (int, float):
        _number(value)
    else:
        _require(value is None or type(value) is bool, "Not a JSON value")


def _plan(comparison):
    plan = comparison["plan"]
    _keys(plan, {"id", "source_ids", "layouts", "trials_per_source", "horizon_s", "expected_total",
                 "sequence", "unit", "frozen_before_trials", "order"})
    sources = sorted(_ids(plan["source_ids"]))
    quota = plan["trials_per_source"]
    _require(type(quota) is int and 1 <= quota <= 10 and 2 <= len(sources) <= 5,
             "Invalid frozen plan size")
    _require(plan["layouts"] == list(LAYOUTS) and plan["source_ids"] == sources,
             "Frozen plan layout/source identities differ")
    _require(plan["unit"] == "one_token_release" and plan["frozen_before_trials"] is True,
             "Plan must be frozen before one-token trials")
    _require(plan["order"] == "predeclared_counterbalanced_alternation_not_randomized",
             "Unknown frozen sequence contract")
    _number(plan["horizon_s"])
    _require(type(comparison["trials_per_source"]) is int, "Invalid frozen trial quota")
    sequence = []
    for repeat in range(1, quota + 1):
        for index, source in enumerate(sources):
            layouts = LAYOUTS if (repeat + index) % 2 else tuple(reversed(LAYOUTS))
            sequence.extend({"layout": layout, "source_id": source, "repeat": repeat}
                            for layout in layouts)
    _require(canonical_json(plan["sequence"]) == canonical_json(sequence) and type(plan["expected_total"]) is int
             and plan["expected_total"] == len(sequence), "Frozen plan denominator/sequence mismatch")
    _require(plan["id"] == "prevention-plan-" + content_hash(
        {key: value for key, value in plan.items() if key != "id"})[:20], "Stale frozen plan ID/hash")
    _require(comparison["trials_per_source"] == quota
             and comparison["horizon_s"] == plan["horizon_s"], "Changed frozen plan settings")
    return sources


def _profile_whitelist(profile):
    _keys(profile["bounds"], {"x_min_cm", "x_max_cm", "y_min_cm", "y_max_cm"})
    for source in profile["sources"]:
        _keys(source, {"id", "polygon_cm"}, {"prior"})
        _id(source["id"])
        if "prior" in source:
            _number(source["prior"])
    for trap in profile.get("traps", []):
        _keys(trap, {"id", "polygon_cm"}, {"validated", "retention"})
    transport = {"dt_s", "max_age_s", "min_age_s", "particles_per_source", "diffusivity_cm2_s",
                 "drift_bias_cm_s", "age_prior"}
    _keys(profile["transport"], (), transport)
    for variant in profile.get("sensitivity_variants", []):
        _keys(variant, {"id", "transport"})
        _keys(variant["transport"], (), transport)
    if "age_prior" in profile["transport"]:
        _keys(profile["transport"]["age_prior"], {"min_s", "max_s", "count"})
    from .estimator import DEFAULT_GATES

    _keys(profile.get("gates", {}), (), DEFAULT_GATES)
    flow = profile["flow"]
    _keys(flow, {"kind", "units", "bounds", "nodes", "coverage_radius_cm", "neighbors", "power",
                 "cell_size_cm", "data_origin", "validity", "diagnostics"}, {"id", "provenance"})
    if "id" in flow:
        _id(flow["id"])
    _keys(flow["bounds"], {"x_min_cm", "x_max_cm", "y_min_cm", "y_max_cm"})
    for node in flow["nodes"]:
        _keys(node, {"x_cm", "y_cm", "vx_cm_s", "vy_cm_s", "sample_count", "scatter_cm_s"})
    _keys(flow["diagnostics"], {"sample_count", "node_count", "training_rmse_cm_s", "loo_rmse_cm_s",
                               "loo_supported_nodes", "grid_coverage_fraction", "max_speed_cm_s",
                               "validation_rmse_cm_s", "validation_coverage_fraction"})
    if "provenance" in flow:
        _keys(flow["provenance"], {"calibration_id", "camera_session_id", "training_recording_ids",
                                   "validation_recording_ids", "frame_splits_disjoint"})
        _require(flow["provenance"]["calibration_id"] == profile["calibration_id"]
                 and flow["provenance"]["frame_splits_disjoint"] is True,
                 "Invalid frozen calibration/frame-split provenance")
        _id(flow["provenance"]["camera_session_id"])


def _profiles(payload):
    comparison = payload["comparison"]
    report = comparison["numerical_report"]
    _keys(payload["profiles"], LAYOUTS)
    profiles = payload["profiles"]
    allowed = {"id", "calibration_id", "valid", "data_origin", "token_class", "bounds", "flow",
               "sources", "traps", "transport", "gates", "sensitivity_variants",
               "observation_polygon_cm", "max_validation_rmse_cm_s", "revalidation_max_rmse_cm_s"}
    drift_ids, drift_sessions = set(), set()
    for layout in LAYOUTS:
        profile = profiles[layout]
        _keys(profile, {"id", "calibration_id", "valid", "data_origin", "token_class", "bounds",
                        "flow", "sources", "transport"}, allowed)
        _profile_whitelist(profile)
        _id(profile["id"])
        _id(profile["calibration_id"])
        _require(profile["id"] == comparison[layout + "_profile_id"], "Profile ID mismatch")
        _require(profile["data_origin"] == comparison["data_origin"], "Mixed profile origins")
        snapshot = comparison[layout + "_profile"]
        expected_snapshot = {key: copy.deepcopy(profile[key]) for key in (
            "id", "bounds", "sources", "traps", "token_class", "calibration_id",
            "observation_polygon_cm", "data_origin") if key in profile}
        expected_snapshot.update(profile_hash=content_hash(profile), flow_id=profile["flow"].get("id"))
        _require(snapshot == expected_snapshot, "Stale profile snapshot/hash")
        expected_layout = {"profile_id": profile["id"], "profile_hash": content_hash(profile),
                           "flow_hash": content_hash(profile["flow"])}
        _require(report["layouts"][layout] == expected_layout, "Stale profile/flow hash")
        provenance = profile["flow"].get("provenance", {})
        training = _ids(provenance.get("training_recording_ids", []))
        validation = _ids(provenance.get("validation_recording_ids", []))
        _require(not training & validation, "Flow training/validation recording leakage")
        recordings = training | validation
        if comparison["data_origin"] == "MEASURED_TANK":
            _require(training and validation and profile["flow"].get("id"),
                     "Measured profiles need independent drift recording provenance")
            _require(not recordings & drift_ids, "Layout drift recordings are not independent")
        drift_ids |= recordings
        if provenance:
            drift_sessions.add(provenance["camera_session_id"])
    _require(profiles["baseline"]["id"] != profiles["intervention"]["id"], "Layouts need distinct profiles")
    if comparison["data_origin"] == "MEASURED_TANK":
        _require(profiles["baseline"]["flow"]["id"] != profiles["intervention"]["flow"]["id"],
                 "Measured layouts need independent drift fields")
    _require(report["data_origin"] == comparison["data_origin"]
             and report["physical_validation"] is False and comparison["physical_validation"] is False,
             "Simulation cannot claim physical validation")
    _require(report["protected_zone_cm"] == comparison["protected_zone_cm"]
             and report["horizon_s"] == comparison["horizon_s"]
             and report["particles_per_source"] == comparison["particles"], "Numerical report settings mismatch")
    return drift_ids, drift_sessions


def _numerical_difference(actual, frozen, path="numerical_report"):
    """Locate the first replay mismatch without hiding changed identities or counts."""
    if type(actual) is not type(frozen):
        return f"{path}: {type(actual).__name__} != {type(frozen).__name__}"
    if isinstance(actual, dict):
        if actual.keys() != frozen.keys():
            return f"{path}: keys differ"
        for key in actual:
            difference = _numerical_difference(actual[key], frozen[key], f"{path}.{key}")
            if difference:
                return difference
    elif isinstance(actual, list):
        if len(actual) != len(frozen):
            return f"{path}: lengths differ"
        for index, (a, b) in enumerate(zip(actual, frozen, strict=True)):
            difference = _numerical_difference(a, b, f"{path}[{index}]")
            if difference:
                return difference
    elif (isinstance(actual, float)
          and re.fullmatch(r"numerical_report\.nominal_paths\[\d+\]\.paths\[\d+\]"
                           r"\.points\[\d+\]\.(?:x_cm|y_cm)", path)
          and math.isfinite(actual) and math.isfinite(frozen)
          and math.isclose(actual, frozen, rel_tol=0.0, abs_tol=1e-12)):
        # ARM/x86 arithmetic may round illustration coordinates differently.
        # No tolerance applies to time nodes, event order, metrics or decisions.
        return None
    elif canonical_json(actual) != canonical_json(frozen):
        return f"{path}: replay={actual!r}, frozen={frozen!r}"
    return None


def _replay_numerical(comparison, profiles):
    # Reuse the frozen numerical engine; do not derive metrics from illustration paths.
    report = comparison["numerical_report"]
    replay = compare_layouts(profiles["baseline"], profiles["intervention"],
                             comparison["protected_zone_cm"], horizon_s=comparison["horizon_s"],
                             particles=comparison["particles"], seed=report["seed"])
    difference = _numerical_difference(replay, report)
    _require(difference is None, f"Stale/tampered numerical report or incompatible profiles: {difference}")


def _protocols(payload, development_id, validation_id, drift_ids, drift_sessions):
    _id(development_id)
    _id(validation_id)
    _require(development_id != validation_id, "Development and validation protocols must differ")
    _keys(payload["protocols"], {"development", "validation"})
    inventories = {}
    comparison = payload["comparison"]
    for split, identifier in (("development", development_id), ("validation", validation_id)):
        protocol = payload["protocols"][split]
        _keys(protocol, {"id", "split", "plan_hash", "comparison_hash", "trial_ids",
                         "recording_ids", "session_ids", "frozen_at", "selected_layout", "selection_basis"})
        _require(protocol["id"] == identifier and protocol["split"] == split, "Protocol/split identity mismatch")
        _require(_hash(protocol["plan_hash"]) == content_hash(comparison["plan"])
                 and _hash(protocol["comparison_hash"]) == content_hash(comparison),
                 "Changed frozen plan/comparison after development selection")
        _require(protocol["selected_layout"] in LAYOUTS
                 and protocol["selection_basis"] in {"SIMULATION_ONLY", "DEVELOPMENT_TRIALS"},
                 "Invalid frozen layout selection")
        inventories[split] = {key: _ids(protocol[key]) for key in ("trial_ids", "recording_ids", "session_ids")}
        _number(protocol["frozen_at"])
    development, validation = (payload["protocols"][key] for key in ("development", "validation"))
    _require(development["selected_layout"] == validation["selected_layout"]
             and development["selection_basis"] == validation["selection_basis"], "Held-out selection was changed")
    _require(development["frozen_at"] <= validation["frozen_at"], "Development must be frozen before validation")
    _require(comparison["created_at"] <= development["frozen_at"], "Comparison must precede development freeze")
    if development["selection_basis"] == "DEVELOPMENT_TRIALS":
        _require(inventories["development"]["trial_ids"], "Development-trial selection needs declared trial identities")
    for key in ("trial_ids", "recording_ids", "session_ids"):
        _require(not inventories["development"][key] & inventories["validation"][key],
                 "Development/validation trial, recording or session leakage")
    _require(drift_ids <= inventories["development"]["recording_ids"], "Missing drift development recording identities")
    _require(drift_sessions <= inventories["development"]["session_ids"], "Missing drift development session identities")
    return inventories


def _trials(payload, inventories):
    comparison = payload["comparison"]
    trials = payload["trials"]
    _require(isinstance(trials, list) and len(trials) <= MAX_TRIALS, "Trial budget exceeded")
    truth = payload["evaluation_truth"]
    _keys(truth, {"scope", "trial_sources"})
    _require(truth["scope"] == "EVALUATION_ONLY_NEVER_SOURCE_INFERENCE", "Source labels need evaluation-only scope")
    labels = {}
    for label in truth["trial_sources"]:
        _keys(label, {"trial_id", "source_id"})
        tid = _id(label["trial_id"])
        _require(tid not in labels, "Duplicate evaluation trial identity")
        _require(label["source_id"] in comparison["plan"]["source_ids"], "Undeclared evaluation source")
        labels[tid] = label["source_id"]
    required = {"id", "comparison_id", "trial_key", "layout", "data_origin", "outcome", "entry_time_s",
                "interception_time_s", "token_accounted", "physical_confirmed", "horizon_completed",
                "recording_id", "ordinal", "created_at", "request_hash"}
    seen, recordings, ordinals, keys, origins = set(), set(), set(), set(), set()
    reconstructed = []
    for trial in trials:
        _keys(trial, required)
        tid = _id(trial["id"])
        _require(tid not in seen and trial["trial_key"] not in keys, "Duplicate trial identity/key")
        seen.add(tid)
        keys.add(trial["trial_key"])
        _require(trial["comparison_id"] == comparison["id"] and tid in labels, "Trial/comparison/evaluation label ID mismatch")
        _require(tid == "prevention-trial-" + content_hash([comparison["id"], trial["trial_key"]])[:24],
                 "Stale trial ID")
        _hash(trial["request_hash"])
        _require(type(trial["ordinal"]) is int and trial["ordinal"] > 0
                 and trial["ordinal"] not in ordinals, "Duplicate/invalid trial ordinal")
        ordinals.add(trial["ordinal"])
        _require(_number(trial["created_at"]) >= payload["protocols"]["validation"]["frozen_at"],
                 "Trial predates frozen validation protocol")
        data = {key: trial[key] for key in TrialInput.model_fields if key not in {"source_id", "note"}}
        data.update(source_id=labels[tid], note="Scrubbed evaluation-only export")
        checked = TrialInput.model_validate(data)
        for event_time in (checked.entry_time_s, checked.interception_time_s):
            _require(event_time is None or event_time <= comparison["horizon_s"], "Outcome exceeds frozen horizon")
        if checked.recording_id is not None:
            _id(checked.recording_id)
            _require(checked.recording_id not in recordings, "Duplicate recording identity across releases")
            recordings.add(checked.recording_id)
        origins.add(checked.data_origin)
        reconstructed.append({**trial, "source_id": labels[tid]})
    _require(seen == set(labels) == inventories["validation"]["trial_ids"], "Validation trial/label inventory mismatch")
    _require(recordings == inventories["validation"]["recording_ids"], "Validation recording inventory mismatch")
    _require(len(origins) <= 1, "Mixed synthetic/physical pooling is forbidden; export separate cohorts")
    if comparison["data_origin"] == "SYNTHETIC":
        _require(origins <= {"SYNTHETIC_DEMO"}, "Synthetic simulation cannot claim physical outcomes")
    _require(ordinals == set(range(1, len(trials) + 1)), "Missing/noncontiguous ledger ordinals")
    counts = Counter((trial["layout"], trial["source_id"]) for trial in reconstructed)
    _require(all(count <= comparison["trials_per_source"] for count in counts.values()),
             "Frozen per-source/layout quota exceeded")
    sessions = {}
    for receipt in payload["trial_sessions"]:
        _keys(receipt, {"trial_id", "session_id"})
        tid, sid = _id(receipt["trial_id"]), _id(receipt["session_id"])
        _require(tid not in sessions, "Duplicate trial session receipt")
        sessions[tid] = sid
    _require(set(sessions) == seen and set(sessions.values()) == inventories["validation"]["session_ids"],
             "Missing/mismatched validation session provenance")
    return reconstructed, len(sessions.values()) != len(set(sessions.values()))


def _existing_evaluation(comparison, trials):
    # evaluate/_stats are store-free; reuse their frozen accounting contract unchanged.
    return PreventionService(SimpleNamespace(store=None)).evaluate(comparison, trials)


def _diagnostics(report, evaluation, selected_layout):
    rows, usefulness = [], {}
    for origin in ORIGINS:
        group = evaluation["by_origin"][origin]
        sources = {row["source_id"]: row for row in group["by_source"]}
        effects = []
        for prediction in report["results"]:
            source = prediction["source_id"]
            observed = sources[source]
            effect = {"lower": observed["baseline"]["entry_rate_bounds"]["lower"]
                       - observed["intervention"]["entry_rate_bounds"]["upper"],
                      "upper": observed["baseline"]["entry_rate_bounds"]["upper"]
                       - observed["intervention"]["entry_rate_bounds"]["lower"]}
            layouts = {}
            for layout in LAYOUTS:
                predicted = prediction[layout]
                actual = observed[layout]
                p_lo, p_hi = predicted["zone_entry_lower_fraction"], predicted["zone_entry_upper_fraction"]
                o_lo, o_hi = actual["observed_entry_rate_bounds"]["lower"], actual["observed_entry_rate_bounds"]["upper"]
                layouts[layout] = {
                    "predicted": {key: predicted[key] for key in (
                        "particles", "zone_entry_count", "captured_before_zone_count", "unresolved_count",
                        "unsupported_count", "captured_before_zone_fraction", "zone_entry_fraction", "zone_entry_lower_fraction", "zone_entry_upper_fraction")},
                    "observed": copy.deepcopy(actual),
                    "prediction_outside_recorded_bounds": actual["released"] > 0 and (p_hi < o_lo or p_lo > o_hi),
                }
            row = {"data_origin": origin, "source_id": source, "scenario_id": prediction["scenario_id"],
                   "layouts": layouts, "predicted_benefit_bounds": {
                       "lower": prediction["benefit_lower_fraction"], "upper": prediction["benefit_upper_fraction"]},
                   "observed_planned_benefit_bounds": effect,
                   "scenario_observation_label": "NONE_same_source_layout_trials_not_additional_releases"}
            rows.append(row)
        for source in sources.values():
            a, b = (source[layout]["entry_rate_bounds"] for layout in LAYOUTS)
            effects.append((a["lower"] - b["upper"], a["upper"] - b["lower"]))
        if not group["plan"]["recorded_total"]:
            status = "NO_NEW_TRIALS"
        elif selected_layout == "intervention" and all(low > 0 for low, _ in effects) or selected_layout == "baseline" and all(high < 0 for _, high in effects):
            status = "DESCRIPTIVELY_USEFUL_ON_REPORTED_NEW_TRIALS"
        elif ((selected_layout == "intervention" and any(high < 0 for _, high in effects))
              or (selected_layout == "baseline" and any(low > 0 for low, _ in effects))):
            status = "CONTRADICTED_BY_REPORTED_NEW_TRIALS"
        else:
            status = "UNRESOLVED_ON_REPORTED_NEW_TRIALS"
        usefulness[origin] = {"status": status, "selected_layout": selected_layout,
                              "physical_results_claimed": False}
    return rows, usefulness


def _next_measurement(report, rows, evaluation):
    common = {"heuristic": "transparent_priority_rule_not_optimal_active_learning",
              "collector_movement_requires_fresh_layout_drift": True,
              "independent_recordings_required": True,
              "retained_endpoint_rewatch_or_crop_is_new_evidence": False}
    unsupported = [{"layout": layout, "source_id": row["source_id"], "scenario_id": row["scenario_id"]}
                   for row in report["results"] for layout in LAYOUTS if row[layout]["unsupported_count"]]
    if unsupported:
        return {**common, "kind": "INDEPENDENT_LAYOUT_DRIFT", "reason_codes": [
            "UNSUPPORTED_FLOW_PATHS", "USEFUL_REGION_NOT_LOCALIZED_IN_SAVED_REPORT"],
            "targets": unsupported, "region_identified": False, "region_cm": None,
            "explanation": "Request independent drift for these layouts; aggregate counts and illustrative paths cannot locate a useful unsupported region."}
    origin = next((key for key in ORIGINS if evaluation["by_origin"][key]["plan"]["recorded_total"]), (ORIGINS[0] if report["data_origin"] == "SYNTHETIC" else ORIGINS[1]))
    candidates = []
    for row in rows:
        if row["data_origin"] != origin:
            continue
        low = row["observed_planned_benefit_bounds"]["lower"]
        high = row["observed_planned_benefit_bounds"]["upper"]
        predicted = row["predicted_benefit_bounds"]
        mismatch = any(value["prediction_outside_recorded_bounds"] for value in row["layouts"].values())
        if ((low < high and low <= 0 <= high)
                or (predicted["lower"] < predicted["upper"] and predicted["lower"] <= 0 <= predicted["upper"])
                or mismatch):
            candidates.append((mismatch, high - low, row["source_id"], row["scenario_id"]))
    if candidates:
        mismatch, _, source, scenario = min(candidates, key=lambda item: (-item[0], -item[1], item[2], item[3]))
        return {**common, "kind": "INDEPENDENT_PAIRED_TRIAL", "source_id": source,
                "scenario_id": scenario, "scenario_role": "frozen_model_scenario_not_an_observed_trial_label",
                "layouts": list(LAYOUTS), "releases": 2, "region_identified": False, "region_cm": None,
                "reason_codes": ["PREDICTION_OUTCOME_DISAGREEMENT" if mismatch else "UNCERTAINTY_CAN_CHANGE_LAYOUT_DECISION"],
                "explanation": "Request a new independent paired baseline/intervention release at this declared source after layout-specific drift validation. Do not change the frozen plan; register a new plan if its quota is complete."}
    return {**common, "kind": "NO_USEFUL_NEXT_MEASUREMENT_IDENTIFIED", "reason_codes": [
        "NO_SAVED_DECISION_CHANGING_UNCERTAINTY"], "region_identified": False, "region_cm": None,
        "explanation": "The saved report identifies no decision-changing source/scenario. Independent replication may still be needed; no optimality or significance is claimed."}


def validate_bundle(bundle, *, development_protocol_id, validation_protocol_id) -> ValidationReport:
    """Return deterministic validation_report_v1, or ValueError; never mutate input."""
    try:
        _safe(bundle)
        _require(len(canonical_json(bundle).encode()) <= MAX_BYTES, "Bundle byte budget exceeded")
        _keys(bundle, {"schema_version", "id", "content_hash", "payload"}, {"metadata"})
        _require(bundle["schema_version"] == "analysis_bundle_v1", "Unsupported analysis bundle version")
        if "metadata" in bundle:
            _keys(bundle["metadata"], {"exported_at"})
            _require(isinstance(bundle["metadata"]["exported_at"], str), "Invalid detached export timestamp")
        payload = bundle["payload"]
        _require(_hash(bundle["content_hash"]) == content_hash(payload)
                 and bundle["id"] == "analysis-bundle-" + bundle["content_hash"][:20], "Stale/tampered bundle hash/ID")
        _keys(payload, {"comparison", "profiles", "trials", "evaluation_truth", "evaluation", "protocols", "trial_sessions"}, {"field_manifest"})
        if payload.get("field_manifest") is not None:
            _keys(payload["field_manifest"], {"schema_version", "id", "content_hash"})
            _require(payload["field_manifest"]["schema_version"] == "field_manifest_v1", "Unknown field manifest version")
            _id(payload["field_manifest"]["id"])
            _hash(payload["field_manifest"]["content_hash"])
        comparison = payload["comparison"]
        _keys(comparison, {"id", "name", "case_id", "case_revision", "source_evidence_id", "source_evidence_status",
                          "baseline_profile_id", "intervention_profile_id", "protected_zone_cm", "data_origin",
                          "physical_validation", "baseline_profile", "intervention_profile", "numerical_report", "plan",
                          "created_at", "horizon_s", "particles", "trials_per_source"}, {"demo_fixture_key"})
        for key in ("id", "case_id", "source_evidence_id"):
            _id(comparison[key])
        _require(type(comparison["case_revision"]) is int and comparison["case_revision"] > 0,
                 "Invalid source case revision")
        _require(comparison["source_evidence_status"] in {"ranked", "unknown"}, "Invalid source evidence anchor")
        _number(comparison["created_at"])
        _plan(comparison)
        drift_ids, drift_sessions = _profiles(payload)
        inventories = _protocols(payload, development_protocol_id, validation_protocol_id, drift_ids, drift_sessions)
        trials, session_reuse = _trials(payload, inventories)
        computed = _existing_evaluation(comparison, trials)
        evaluation = payload["evaluation"]
        _keys(evaluation, {"source_snapshot_hash", "source_evaluation_id", "export_snapshot_hash", "by_origin"})
        source_hash = _hash(evaluation["source_snapshot_hash"])
        _require(evaluation["source_evaluation_id"] == "prevention-evaluation-" + source_hash[:20], "Stale source evaluation ID")
        _require(_hash(evaluation["export_snapshot_hash"]) == computed["snapshot_hash"], "Stale exported evaluation hash")
        _require(canonical_json(evaluation["by_origin"]) == canonical_json(computed["by_origin"]),
                 "Evaluation denominator/accounting mismatch")
        _replay_numerical(comparison, payload["profiles"])
        selected = payload["protocols"]["development"]["selected_layout"]
        rows, usefulness = _diagnostics(comparison["numerical_report"], computed, selected)
        report = {"schema_version": "validation_report_v1", "input_bundle_hash": bundle["content_hash"],
                  "comparison_id": comparison["id"], "plan_id": comparison["plan"]["id"],
                  "source_evaluation_hash": source_hash, "export_evaluation_hash": computed["snapshot_hash"],
                  "original_private_hash_verified": False, "numerical_replay_verified": True,
                  "development_protocol_id": development_protocol_id, "validation_protocol_id": validation_protocol_id,
                  "data_origin": comparison["data_origin"], "physical_validation": False,
                  "supports_significance_or_causal_claim": False,
                  "protocols": copy.deepcopy(payload["protocols"]), "by_origin": computed["by_origin"],
                  "diagnostics": rows, "selected_layout_usefulness": usefulness,
                  "source_identification": {"evaluated": False, "reason": "Release labels group intervention outcomes only; no source-classifier predictions are supplied."},
                  "dependence_warnings": ["WITHIN_VALIDATION_SESSION_REUSE"] if session_reuse else [],
                  "next_measurement": _next_measurement(comparison["numerical_report"], rows, computed),
                  "limitations": list(LIMITATIONS)}
        _require(len(canonical_json(report).encode()) <= MAX_BYTES - 256, "Report byte budget exceeded")
        digest = content_hash(report)
        return {**report, "id": "prevention-validation-" + digest[:20], "content_hash": digest}
    except (KeyError, TypeError, IndexError, OverflowError, RecursionError) as error:
        raise ValueError("Malformed or over-budget analysis_bundle_v1") from error


def parse_validation_report(report, *, input_bundle_hash, comparison_id, export_evaluation_hash) -> ValidationReport:
    """Check finite report/hash/lineage before rendering; not a signature or revalidation."""
    try:
        _safe(report)
        _require(len(canonical_json(report).encode()) <= MAX_BYTES, "Report byte budget exceeded")
        _keys(report, ValidationReport.__annotations__)
        _require(report["schema_version"] == "validation_report_v1", "Unsupported validation report version")
        _require(report["input_bundle_hash"] == _hash(input_bundle_hash)
                 and report["comparison_id"] == _id(comparison_id)
                 and report["export_evaluation_hash"] == _hash(export_evaluation_hash),
                 "Stale validation report lineage")
        body = {key: value for key, value in report.items() if key not in {"id", "content_hash"}}
        digest = content_hash(body)
        _require(report["content_hash"] == digest and report["id"] == "prevention-validation-" + digest[:20],
                 "Stale/tampered validation report hash/ID")
        _require(report["physical_validation"] is False
                 and report["supports_significance_or_causal_claim"] is False
                 and report["original_private_hash_verified"] is False
                 and report["numerical_replay_verified"] is True,
                 "Unsupported validation/effect claim")
        _keys(report["by_origin"], ORIGINS)
        _require(report["data_origin"] in {"SYNTHETIC", "MEASURED_TANK"}, "Invalid report origin")
        if report["data_origin"] == "SYNTHETIC":
            _require(report["by_origin"]["OPERATOR_REPORTED_PHYSICAL"]["plan"]["recorded_total"] == 0,
                     "Synthetic report cannot claim physical releases")
        return copy.deepcopy(report)
    except (KeyError, TypeError, IndexError, OverflowError, RecursionError) as error:
        raise ValueError("Malformed validation_report_v1") from error
