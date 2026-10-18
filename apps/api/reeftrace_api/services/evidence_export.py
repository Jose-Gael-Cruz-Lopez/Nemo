"""Whitelisted, consistent-read export of one immutable prevention experiment.

No providers, messages, hardware, file paths or raw frames cross this boundary.
This intentionally is not a general Store dump or a numerical model rerun.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, get_args, get_origin

from pydantic import BaseModel, ValidationError

from ..schemas.evidence_export import (
    LIMITATIONS,
    AnalysisBundle,
    AnalysisPayload,
    canonical_json,
)
from ..schemas.prevention import TrialInput
from .prevention import COMPARISON_KIND, LAYOUTS, TRIAL_KIND, _profile_snapshot, digest

MAX_RECORD_BYTES = 2_000_000
MAX_TRIALS = 200
MAX_BUNDLE_BYTES = 1_000_000


def _project(annotation, value):
    """Recursively select declared fields; arbitrary nested extras cannot leak."""
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is Annotated:
        return _project(args[0], value)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        if not isinstance(value, dict):
            raise ValueError("Export object does not match its bounded schema")  # noqa: TRY004
        return {key: _project(field.annotation, value[key])
                for key, field in annotation.model_fields.items() if key in value}
    if origin is list and isinstance(value, list):
        return [_project(args[0], item) for item in value]
    if origin is dict and isinstance(value, dict):
        return {key: _project(args[1], item) for key, item in value.items()}
    return value


def _read(db, kind, record_id):
    row = db.execute("SELECT payload FROM records WHERE kind=? AND id=?",
                     (kind, record_id)).fetchone()
    if row is None:
        raise KeyError(record_id)
    if len(row[0].encode()) > MAX_RECORD_BYTES:
        raise ValueError("Export source record exceeds its bounded budget")
    result = json.loads(row[0])
    if not isinstance(result, dict) or result.get("id") != record_id:
        raise ValueError("Immutable record identity does not match its stored key")
    return result


def _transport(settings):
    return {"dt_s": settings.get("dt_s", 0.1),
            "max_age_s": settings.get("max_age_s", 60),
            "diffusivity_cm2_s": settings.get("diffusivity_cm2_s", 0.05),
            "drift_bias_cm_s": settings.get("drift_bias_cm_s", [0, 0])}


def _layout(db, comparison, layout):
    report = comparison["numerical_report"]
    profile_id = comparison[layout + "_profile_id"]
    profile = _read(db, "profile", profile_id)
    identity = report["layouts"][layout]
    if (identity["profile_id"] != profile_id or identity["profile_hash"] != digest(profile)
            or identity["flow_hash"] != digest(profile["flow"])):
        raise ValueError("Frozen layout profile/flow hashes or identities do not match originals")
    if comparison[layout + "_profile"] != _profile_snapshot(profile, identity["profile_hash"]):
        raise ValueError("Nested frozen layout snapshot differs from its immutable original")
    if profile["data_origin"] != comparison["data_origin"]:
        raise ValueError("Frozen profile and comparison origins disagree")
    flow = profile["flow"]
    if flow.get("data_origin") != profile["data_origin"] or flow["bounds"] != profile["bounds"]:
        raise ValueError("Frozen flow origin/bounds disagree with its profile")
    flow_id = flow.get("id")
    if flow_id and _read(db, "flow", flow_id) != flow:
        raise ValueError("Profile flow differs from its immutable recorded artifact")
    origin = profile["data_origin"]
    provenance = flow.get("provenance", {})
    training = provenance.get("training_recording_ids", [])
    validation = provenance.get("validation_recording_ids", [])
    if origin == "MEASURED_TANK" and (
            not flow_id or not training or not validation or set(training) & set(validation)):
        raise ValueError("Measured flow requires separate immutable training/validation recording IDs")
    settings = profile.get("transport", {})
    variants = profile.get("sensitivity_variants", [])
    scenarios = [{"id": "nominal", "transport": _transport(settings)}]
    scenarios += [{"id": variant["id"], "transport": _transport({**settings, **variant["transport"]})}
                  for variant in sorted(variants, key=lambda variant: variant["id"])]
    output = {**profile, "profile_hash": identity["profile_hash"],
        "observation_polygon_cm": profile.get("observation_polygon_cm"),
        "traps": [{**trap, "retention": trap.get("retention", "absorbing")}
                  for trap in profile.get("traps", [])],
        "transport": _transport(settings), "scenarios": scenarios,
        "flow": {"flow_id": flow_id, "flow_hash": identity["flow_hash"], "data_origin": origin,
            "training_recording_ids": training, "validation_recording_ids": validation,
            "diagnostics": flow["diagnostics"]}}
    return output, profile


def _check_plan(comparison, profiles):
    baseline, intervention = profiles
    for key in ("data_origin", "bounds", "token_class"):
        if baseline.get(key) != intervention.get(key):
            raise ValueError("Frozen layout inputs disagree")
    # Creation compares complete source records by ID, independently of list
    # order. Preserve the original profile bytes/hashes and reject duplicate IDs.
    sources = [{str(source["id"]): source for source in profile["sources"]}
               for profile in profiles]
    if (sources[0] != sources[1] or any(len(records) != len(profile["sources"])
            for records, profile in zip(sources, profiles, strict=True))):
        raise ValueError("Frozen layout inputs disagree")
    source_ids = sorted(source["id"] for source in baseline["sources"])
    sequence = []
    for repeat in range(1, comparison["trials_per_source"] + 1):
        for index, source_id in enumerate(source_ids):
            layouts = LAYOUTS if (repeat + index) % 2 else tuple(reversed(LAYOUTS))
            sequence.extend({"layout": layout, "source_id": source_id, "repeat": repeat}
                            for layout in layouts)
    expected = {"source_ids": source_ids, "layouts": list(LAYOUTS),
        "trials_per_source": comparison["trials_per_source"], "horizon_s": comparison["horizon_s"],
        "expected_total": len(sequence), "sequence": sequence, "unit": "one_token_release",
        "frozen_before_trials": True, "order": "predeclared_counterbalanced_alternation_not_randomized"}
    expected["id"] = "prevention-plan-" + digest(expected)[:20]
    if comparison["plan"] != expected:
        raise ValueError("Frozen trial plan no longer matches its declared identities/hash/order")
    report = comparison["numerical_report"]
    for key in ("data_origin", "horizon_s", "protected_zone_cm", "physical_validation"):
        if report[key] != comparison[key]:
            raise ValueError("Numerical report and comparison metadata disagree")
    if report["particles_per_source"] != comparison["particles"]:
        raise ValueError("Numerical particle denominator differs from the frozen comparison")
    scenarios = ["nominal"] + sorted(v["id"] for v in baseline.get("sensitivity_variants", []))
    if (report["scenario_ids"] != scenarios
            or scenarios != ["nominal"] + sorted(v["id"] for v in intervention.get("sensitivity_variants", []))):
        raise ValueError("Numerical scenarios do not match both complete frozen scenario sets")
    pairs = [(row["scenario_id"], row["source_id"]) for row in report["results"]]
    if pairs != [(scenario, source) for scenario in scenarios for source in source_ids]:
        raise ValueError("Numerical rows do not cover each declared source/scenario exactly once")
    for row in report["results"]:
        for layout in LAYOUTS:
            if row[layout]["particles"] != comparison["particles"]:
                raise ValueError("Numerical row denominator does not match frozen particle count")


def _check_trials(comparison, trials):
    cells, used_recordings = {}, set()
    for ordinal, trial in enumerate(trials, 1):
        try:
            request = TrialInput.model_validate({key: trial[key] for key in TrialInput.model_fields})
        except ValidationError:
            raise ValueError("Stored trial does not match the bounded evaluation contract") from None
        if (trial["comparison_id"] != comparison["id"] or trial["ordinal"] != ordinal
                or trial["source_id"] not in comparison["plan"]["source_ids"]
                or trial["id"] != "prevention-trial-" + digest([comparison["id"], request.trial_key])[:24]
                or trial["request_hash"] != digest(request.model_dump())):
            raise ValueError("Trial identity, order, request digest or evaluation source does not match")
        if any(t is not None and t > comparison["horizon_s"] for t in (
                request.entry_time_s, request.interception_time_s)):
            raise ValueError("Trial event exceeds its frozen horizon")
        if (request.data_origin == "OPERATOR_REPORTED_PHYSICAL"
                and comparison["data_origin"] != "MEASURED_TANK"):
            raise ValueError("Synthetic layout cannot contain physical trial claims")
        key = request.data_origin, request.layout, request.source_id
        cells[key] = cells.get(key, 0) + 1
        if cells[key] > comparison["trials_per_source"]:
            raise ValueError("Trial count exceeds its per-origin frozen quota")
        if request.recording_id:
            if request.recording_id in used_recordings:
                raise ValueError("Repeated recording cannot count as independent trial releases")
            used_recordings.add(request.recording_id)


def export_comparison(runtime, comparison_id):
    """Return one authenticated-route-ready redacted bundle, including archives.

    Every SQLite read uses a single read transaction. The bundle cannot mix a
    new ledger with an old evaluation during a concurrent trial append.
    """
    with runtime.store.connection() as db:
        db.execute("BEGIN")
        comparison = _read(db, COMPARISON_KIND, comparison_id)
        row = db.execute("SELECT payload FROM cases WHERE id=?", (comparison["case_id"],)).fetchone()
        if row is None:
            raise ValueError("Frozen comparison source case is missing")
        case = json.loads(row[0])
        if case["id"] != comparison["case_id"]:
            raise ValueError("Frozen comparison source case identity is inconsistent")
        source = _read(db, "estimate", comparison["source_evidence_id"])
        if (source.get("case_id") != comparison["case_id"]
                or source.get("status") != comparison["source_evidence_status"]
                or source.get("status") not in {"ranked", "unknown"}
                or source.get("data_origin") != comparison["data_origin"]
                or source.get("profile_id", comparison["baseline_profile_id"]) != comparison["baseline_profile_id"]):
            raise ValueError("Frozen source evidence identity/status/origin/profile is inconsistent")
        exports, profiles = {}, []
        for layout in LAYOUTS:
            exports[layout], profile = _layout(db, comparison, layout)
            profiles.append(profile)
        _check_plan(comparison, profiles)
        rows = db.execute("SELECT id,payload FROM records WHERE kind=? "
            "AND json_extract(payload,'$.comparison_id')=? ORDER BY created,id LIMIT ?",
            (TRIAL_KIND, comparison_id, MAX_TRIALS + 1)).fetchall()
        if len(rows) > MAX_TRIALS:
            raise ValueError("Trial export exceeds the bounded frozen plan budget")
        trials = []
        for row in rows:
            if len(row["payload"].encode()) > MAX_RECORD_BYTES:
                raise ValueError("Trial source record exceeds its bounded budget")
            trial = json.loads(row["payload"])
            if trial.get("id") != row["id"]:
                raise ValueError("Trial identity differs from its immutable stored key")
            trials.append(trial)
        trials.sort(key=lambda trial: (trial["ordinal"], trial["id"]))
        _check_trials(comparison, trials)
        evaluation = runtime.prevention.evaluate(comparison, trials)
        try:
            runtime.prevention._assert_case(comparison, case)
            current = case["profile_id"] == comparison["baseline_profile_id"]
        except ValueError:
            current = False
    flow_ids = [exports[layout]["flow"]["flow_id"] for layout in LAYOUTS]
    sets = [set(exports[layout]["flow"]["training_recording_ids"]
                + exports[layout]["flow"]["validation_recording_ids"]) for layout in LAYOUTS]
    measured = comparison["data_origin"] == "MEASURED_TANK"
    distinct = bool(all(flow_ids) and flow_ids[0] != flow_ids[1])
    disjoint = bool(all(sets) and not sets[0] & sets[1])
    if measured and not (distinct and disjoint):
        raise ValueError("Measured layouts lack distinct independently recorded flow artifacts")
    candidate = {"comparison": comparison, "frozen_plan": comparison["plan"],
        "provenance": {"layouts": exports, "independence": {
            "status": "INDEPENDENT_MEASURED_RECORDING_SETS" if measured else "SYNTHETIC_NOT_PHYSICAL",
            "independently_measured": measured, "distinct_flow_ids": distinct,
            "disjoint_layout_recording_sets": disjoint,
            "outcome_validation": "NOT_AUTOMATICALLY_VERIFIED"}},
        "source_evidence": {key: source[key] for key in ("id", "case_id", "status", "data_origin")},
        "evaluation_truth": {"purpose": "EVALUATION_ONLY_NEVER_SOURCE_INFERENCE_INPUT",
            "trials": trials, "evaluation": evaluation}, "limitations": LIMITATIONS}
    try:
        payload = AnalysisPayload.model_validate(
            _project(AnalysisPayload, candidate)).model_dump(mode="json")
    except ValidationError:
        # Pydantic's detailed errors include input values. Never return those
        # values if an ID accidentally contains a credential, address or path.
        raise ValueError("Export contains unsafe or invalid fields; source values were withheld") from None
    raw = canonical_json(payload)
    bundle = AnalysisBundle(schema_version="analysis_bundle_v1", payload=payload,
        payload_canonical_json=raw, payload_sha256=hashlib.sha256(raw.encode()).hexdigest(),
        metadata={"exported_at_utc": datetime.now(UTC).isoformat(), "is_current": current,
                  "archive_reason": None if current else "CASE_CHANGED_OR_STOPPED"}).model_dump(mode="json")
    if len(canonical_json(bundle).encode()) > MAX_BUNDLE_BYTES:
        raise ValueError("Export exceeds its bounded JSON byte budget")
    return bundle
