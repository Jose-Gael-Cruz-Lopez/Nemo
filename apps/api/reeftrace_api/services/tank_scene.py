"""Hash-bound schematic replay of existing tank evidence; no numerical reruns."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime

from apps.transport.reeftrace_transport.flow import FlowField

from .evidence_export import MAX_TRIALS, _check_plan, _check_trials, _layout, _read
from .prevention import COMPARISON_KIND, LAYOUTS, TRIAL_KIND, digest

MAX_SCENE_BYTES = 2_000_000
MAX_RECORDING_POINTS = 2000
MAX_TOTAL_POINTS = 20_000
# Runtime.record derives every t_s from one received_mono_s start. The monotonic
# tolerance covers floating subtraction only. UTC is a separately read wall
# clock: its 1ms admission tolerance can conservatively reject NTP/scheduling
# changes. Neither bound measures latency, exposure accuracy or release timing.
MONOTONIC_ORIGIN_TOLERANCE_S = 1e-6
UTC_ORIGIN_TOLERANCE_S = 1e-3
STATS = ("particles", "zone_entry_count", "zone_entry_fraction", "zone_entry_lower_fraction",
         "zone_entry_upper_fraction", "captured_before_zone_count", "captured_before_zone_fraction",
         "unresolved_count", "unsupported_count", "unsupported_fraction",
         "supported_particle_fraction", "path_coverage_fraction")


def _identifier(value):
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value) is None:
        raise ValueError("Scene evidence contains an invalid artifact identity")
    return value


def _number(value, lower=0, upper=180):
    if type(value) not in (int, float) or not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError("Scene evidence contains an invalid bounded coordinate or time")
    return value


def _xy(point, bounds):
    return {"x_cm": _number(point["x_cm"], bounds["x_min_cm"], bounds["x_max_cm"]),
            "y_cm": _number(point["y_cm"], bounds["y_min_cm"], bounds["y_max_cm"])}


def _polygon(points, bounds):
    """Whitelist bounded frozen coordinates without changing the saved geometry."""
    if not isinstance(points, list) or not 3 <= len(points) <= 65:
        raise ValueError("Scene polygon exceeds its frozen geometry budget")
    result = []
    for point in points:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("Scene polygon must contain coordinate pairs")
        result.append([_number(point[0], bounds["x_min_cm"], bounds["x_max_cm"]),
                       _number(point[1], bounds["y_min_cm"], bounds["y_max_cm"])])
    return result


def _paths(report, profiles):
    groups = report.get("nominal_paths", [])
    if not isinstance(groups, list) or len(groups) > 10:
        raise ValueError("Scene representative path budget exceeded")
    result, seen = [], set()
    horizon = report["horizon_s"]
    for group in groups:
        layout, source = group["layout"], group["source_id"]
        if (layout not in LAYOUTS or source not in {s["id"] for s in profiles[layout]["sources"]}
                or (layout, source) in seen or not isinstance(group["paths"], list)
                or len(group["paths"]) > 6):
            raise ValueError("Scene representative paths changed their source/layout identities")
        seen.add((layout, source))
        particles = set()
        for path in group["paths"]:
            particle = path["particle_index"]
            if type(particle) is not int or not 0 <= particle < report["particles_per_source"] or particle in particles:
                raise ValueError("Scene representative particle identity is inconsistent")
            particles.add(particle)
            zone, capture = path["zone_entry_s"], path["capture_s"]
            for event in (zone, capture):
                if event is not None:
                    _number(event, upper=horizon)
            stop = min(value for value in (zone, capture, horizon) if value is not None)
            if type(path["supported"]) is not bool or not isinstance(path["points"], list) or len(path["points"]) > 80:
                raise ValueError("Scene representative path support or sample budget is invalid")
            points, previous = [], -1
            for point in path["points"]:
                when = _number(point["t_s"], upper=horizon)
                if when <= previous:
                    raise ValueError("Scene representative times must strictly increase")
                previous = when
                item = {"t_s": when, **_xy(point, profiles[layout]["bounds"])}
                if path["supported"] and when <= stop:
                    points.append(item)
            result.append({"layout": layout, "source_id": source, "particle_index": particle,
                "points": points, "zone_entry_s": zone, "capture_s": capture,
                "display_stop_s": stop if path["supported"] else None, "support_status": (
                    "SUPPORTED_THROUGH_FIRST_EVENT_OR_HORIZON" if path["supported"] else
                    "UNSUPPORTED_PATH_WITHHELD"),
                "sampling": "LEGACY_DECIMATED_REPRESENTATIVE", "counts_derived_from_path": False})
    return result


def _recorded_segments(recording, bounds):
    points = recording.get("points")
    if not isinstance(points, list) or not 1 <= len(points) <= MAX_RECORDING_POINTS:
        raise ValueError("Scene recording point budget exceeded")
    segments, gaps, current, previous_time = [], [], None, -1
    for point in points:
        when = _number(point["t_s"])
        if when <= previous_time:
            raise ValueError("Scene recording times must strictly increase")
        gap_time, previous_time = when - previous_time, when
        reason = None
        if point.get("observed") is not True:
            reason = (point.get("reason") if point.get("reason") in {
                "NO_DETECTION", "MULTIPLE_TOKENS", "ASSOCIATION_GAP"} else "UNOBSERVED_POINT")
        elif not isinstance(point.get("track_id"), str):
            reason = "MISSING_TRACK_ID"
        else:
            try:
                position = _xy(point, bounds)
            except (ValueError, KeyError):
                reason = "INVALID_OR_OUTSIDE_TANK_POINT"
        if reason:
            gaps.append({"t_s": when, "reason": reason})
            current = None
            continue
        track_id = _identifier(point["track_id"])
        if (current is None or current["track_id"] != track_id
                or point.get("association_break") is True or gap_time > 0.5):
            if current is not None:
                gaps.append({"t_s": when, "reason": "ASSOCIATION_GAP"})
            current = {"track_id": track_id, "points": []}
            segments.append(current)
        current["points"].append({"t_s": when, **position})
    return segments, gaps


def _recording_clock(point, frame, receipt, previous, origin):
    """Reject clockless legacy or contradictory captures without repairing time."""
    try:
        when = _number(point["t_s"])
        mono = _number(frame["received_mono_s"], 0, 1e12)
        sequence = frame["sequence"]
        if type(sequence) is not int or sequence < 1:
            raise ValueError("Invalid frame sequence")
    except (KeyError, TypeError, ValueError):
        raise ValueError("Scene recording requires finite monotonic receipt clocks and frame sequences") from None
    if previous is not None:
        prior_time, prior_mono, prior_sequence, prior_receipt = previous
        if (when <= prior_time or mono <= prior_mono or sequence <= prior_sequence
                or receipt <= prior_receipt):
            raise ValueError("Scene recording frame sequences and receipt clocks must strictly increase")
    if origin is not None:
        first_time, first_mono, first_receipt = origin
        if (abs((mono - first_mono) - (when - first_time)) > MONOTONIC_ORIGIN_TOLERANCE_S
                or abs((receipt - first_receipt) - (when - first_time)) > UTC_ORIGIN_TOLERANCE_S):
            raise ValueError("Scene recording receipt clocks contradict its shared capture-start time axis")
    else:
        origin = when, mono, receipt
    return (when, mono, sequence, receipt), origin


def build_tank_scene(runtime, comparison_id: str, evaluation_snapshot_hash: str) -> dict:
    """Read one snapshot, validate identities, then reject any concurrent change."""
    _identifier(comparison_id)
    if re.fullmatch(r"[0-9a-f]{64}", evaluation_snapshot_hash) is None:
        raise ValueError("Select the exact current trial evaluation before loading its scene")
    artifacts = {}
    with runtime.store.connection() as db:
        db.execute("BEGIN")

        def read(kind, identity):
            value = _read(db, kind, identity)
            artifacts[kind, identity] = digest(value)
            return value

        comparison = read(COMPARISON_KIND, comparison_id)
        case_row = db.execute("SELECT payload FROM cases WHERE id=?", (comparison["case_id"],)).fetchone()
        if case_row is None:
            raise ValueError("Scene source case is unavailable")
        case = json.loads(case_row[0])
        source = read("estimate", comparison["source_evidence_id"])
        if (case["id"] != comparison["case_id"]
                or source.get("case_id") != comparison["case_id"]
                or source.get("status") != comparison["source_evidence_status"]
                or source.get("status") not in {"ranked", "unknown"}
                or source.get("data_origin") != comparison["data_origin"]
                or source.get("profile_id", comparison["baseline_profile_id"]) != comparison["baseline_profile_id"]):
            raise ValueError("Scene source evidence differs from its frozen comparison")
        profiles = {}
        for layout in LAYOUTS:
            _, profile = _layout(db, comparison, layout)
            profiles[layout] = profile
            read("profile", profile["id"])
            if profile["flow"].get("id"):
                read("flow", profile["flow"]["id"])
        _check_plan(comparison, list(profiles.values()))
        rows = db.execute("SELECT id FROM records WHERE kind=? AND "
            "json_extract(payload,'$.comparison_id')=? ORDER BY created,id LIMIT ?",
            (TRIAL_KIND, comparison_id, MAX_TRIALS + 1)).fetchall()
        if len(rows) > MAX_TRIALS:
            raise ValueError("Scene trial budget exceeded")
        trials = sorted([read(TRIAL_KIND, row[0]) for row in rows], key=lambda t: (t["ordinal"], t["id"]))
        _check_trials(comparison, trials)
        evaluation = runtime.prevention.evaluate(comparison, trials)
        if evaluation["snapshot_hash"] != evaluation_snapshot_hash:
            raise ValueError("Scene trial evaluation changed; reload the comparison")
        try:
            runtime.prevention._assert_case(comparison, case)
            current = True
        except ValueError:
            current = False
        report = comparison["numerical_report"]
        layouts, vectors = [], []
        for name, profile in profiles.items():
            identity = report["layouts"][name]
            layouts.append({"id": name, "profile_id": _identifier(profile["id"]),
                "profile_hash": identity["profile_hash"], "flow_hash": identity["flow_hash"],
                "calibration_id": _identifier(profile["calibration_id"]),
                "traps": [{"id": _identifier(trap["id"]), "polygon_cm": _polygon(trap["polygon_cm"], profile["bounds"]),
                           "retention": trap.get("retention", "absorbing")} for trap in profile.get("traps", [])]})
            field = FlowField(profile["flow"])
            nodes = []
            for node in profile["flow"]["nodes"]:
                xy = _xy(node, profile["bounds"])
                nodes.append({**xy, "vx_cm_s": _number(node["vx_cm_s"], -100, 100),
                    "vy_cm_s": _number(node["vy_cm_s"], -100, 100),
                    "supported": bool(field.evaluate([[xy["x_cm"], xy["y_cm"]]])[1][0])})
            vectors.append({"layout": name, "flow_hash": identity["flow_hash"],
                            "time_varying": False, "nodes": nodes})
        physical = [trial for trial in trials if trial["data_origin"] == "OPERATOR_REPORTED_PHYSICAL"]
        recordings, point_count = [], 0
        for trial in physical:
            if not trial.get("recording_id"):
                continue
            if comparison["data_origin"] != "MEASURED_TANK":
                raise ValueError("Synthetic comparison cannot expose physical recording evidence")
            recording = read("recording", trial["recording_id"])
            if not isinstance(recording.get("points"), list) or not 1 <= len(recording["points"]) <= MAX_RECORDING_POINTS:
                raise ValueError("Scene recording point budget exceeded")
            point_count += len(recording["points"])
            if point_count > MAX_TOTAL_POINTS:
                raise ValueError("Scene total recording point budget exceeded")
            runtime.prevention._validate_recording(trial["recording_id"], comparison, trial["layout"])
            uses = db.execute("SELECT COUNT(*) FROM records WHERE kind=? AND "
                "json_extract(payload,'$.recording_id')=?", (TRIAL_KIND, trial["recording_id"])).fetchone()[0]
            if uses != 1:
                raise ValueError("A scene recording must identify exactly one trial release")
            profile = profiles[trial["layout"]]
            calibration = read("calibration", profile["calibration_id"])
            if (recording.get("profile_id") != profile["id"]
                    or recording.get("data_origin") != "MEASURED_TANK"
                    or recording.get("calibration_id") != profile["calibration_id"]
                    or calibration.get("approved") is not True or calibration.get("units") != "cm"
                    or calibration.get("plane") != "measured_water_surface"
                    or not recording.get("camera_session_id")
                    or recording["camera_session_id"] != calibration.get("camera_session_id")
                    or recording.get("timestamp_kind") != "host_receipt_not_exposure"):
                raise ValueError("Scene recording calibration, session or units do not match its layout")
            # Recheck the same snapshot bytes, rather than relying only on the
            # existing validator's separate store reads during a concurrent edit.
            completed = _number(recording.get("recorded_at"), comparison["created_at"], 1e12)
            frame_ids, points = recording.get("evidence_frame_ids"), recording.get("points")
            if (not isinstance(frame_ids, list) or not isinstance(points, list)
                    or not 1 <= len(points) <= MAX_RECORDING_POINTS
                    or len(frame_ids) != len(points) or len(set(frame_ids)) != len(frame_ids)):
                raise ValueError("Scene recording frame lineage or point budget is invalid")
            previous_clock, origin_clock = None, None
            for point, fid in zip(points, frame_ids, strict=True):
                if point.get("frame_id") != fid:
                    raise ValueError("Scene recording frame lineage does not match its points")
                frame = read("frame", fid)
                if (frame.get("camera_session_id") != recording["camera_session_id"]
                        or frame.get("profile_id") != profile["id"]):
                    raise ValueError("Scene recording frame session/profile does not match")
                try:
                    received = datetime.fromisoformat(frame["received_utc"])
                    if received.utcoffset() is None:
                        raise ValueError("Frame clock lacks timezone")
                    receipt = _number(received.timestamp(), 0, completed)
                    if receipt - _number(point["t_s"]) < comparison["created_at"]:
                        raise ValueError("Scene recording predates its frozen plan")
                except (KeyError, TypeError, ValueError, OverflowError):
                    raise ValueError("Scene recording lacks consistent prospective receipt timestamps") from None
                previous_clock, origin_clock = _recording_clock(
                    point, frame, receipt, previous_clock, origin_clock)
            segments, gaps = _recorded_segments(recording, profile["bounds"])
            recordings.append({"trial_id": trial["id"], "recording_id": recording["id"],
                "recording_content_hash": digest(recording), "layout": trial["layout"],
                "source_id": trial["source_id"], "calibration_id": profile["calibration_id"],
                "camera_session_id": recording["camera_session_id"], "segments": segments,
                "gaps": gaps, "reason_codes": sorted({gap["reason"] for gap in gaps}),
                "outcome_automatically_verified": False})
        result = {"schema_version": 1, "kind": "TANK_RIG_SCENE", "comparison_id": comparison_id,
            "comparison_sha256": digest(comparison), "numerical_report_sha256": digest(report),
            "evaluation_snapshot_hash": evaluation_snapshot_hash, "case_id": comparison["case_id"],
            "case_revision": comparison["case_revision"], "source_evidence_id": comparison["source_evidence_id"],
            "is_current": current, "archive_reason": None if current else "CASE_CHANGED_OR_STOPPED",
            "data_origin": comparison["data_origin"], "physical_validation": False,
            "units": {"position": "cm", "time": "s", "velocity": "cm/s"},
            "vertical": {"mode": "SCHEMATIC_SURFACE_ONLY", "surface_z_cm": 0,
                         "measured_depth_cm": None, "physical_geometry_verified": False},
            "geometry": {"bounds_cm": {key: profiles["baseline"]["bounds"][key]
                for key in ("x_min_cm", "x_max_cm", "y_min_cm", "y_max_cm")},
                "sources": [{"id": _identifier(source["id"]),
                             "polygon_cm": _polygon(source["polygon_cm"], profiles["baseline"]["bounds"])}
                            for source in profiles["baseline"]["sources"]],
                "protected_zone_cm": _polygon(comparison["protected_zone_cm"], profiles["baseline"]["bounds"]), "layouts": layouts},
            "simulation": {"engine": "EXISTING_TANK_EULER_MARUYAMA", "scenario_id": "nominal",
                "event_time_kind": "TIME_NODE_UPPER_BOUND_NOT_EXACT_COLLISION",
                "horizon_s": comparison["horizon_s"], "seed": report["seed"],
                "particles_per_source": report["particles_per_source"], "paths": _paths(report, profiles)},
            "vectors": vectors,
            "results": {"recommendation": report["recommendation"],
                "robust_benefit_min": report["robust_benefit_min"], "robust_benefit_max": report["robust_benefit_max"],
                "rows": [{"scenario_id": row["scenario_id"], "source_id": row["source_id"],
                    **{name: {key: row[name][key] for key in STATS} for name in LAYOUTS},
                    **{key: row[key] for key in ("benefit_fraction", "benefit_lower_fraction", "benefit_upper_fraction")}}
                         for row in report["results"]], "by_origin": evaluation["by_origin"]},
            "actual": {"status": ("RECORDED_TRACKS_AVAILABLE" if any(r["segments"] for r in recordings) else
                                   "REPORTED_COUNTS_ONLY" if physical else "NOT_CAPTURED"),
                "clock": "CAPTURE_START_UNALIGNED", "release_alignment": "MISSING",
                "positional_error_metrics": None, "reported_physical_trial_count": len(physical),
                "recordings": recordings, "reason_codes": ["NO_VERIFIED_RELEASE_TIME_ANCHOR"]},
            "limitations": [
                "This is a schematic water-surface replay, not measured tank depth, volumetric flow, CFD or a digital twin.",
                "Legacy paths are selected, decimated illustrations; full-ensemble outcome counts remain authoritative.",
                "Unsupported representative paths are withheld; supported display stops at the first declared event or horizon.",
                "No event position is invented between saved samples; visual interpolation is not a new numerical calculation.",
                "Declared event times are simulation time-node upper bounds; the final display point is not an exact collision position.",
                "Static frozen IDW vectors are model support, not new measurements or a predicted barrier-induced flow change.",
                "Recorded segments retain gaps and their capture-start clock; no token-release alignment or positional error is inferred.",
                "Recorded frame sequence, monotonic and UTC clocks must agree with saved capture times within declared admission tolerances; this is not exposure or latency validation.",
                "Operator-reported outcomes and linked recordings are not automatically camera-verified or proof of reef protection.",
            ]}
    # A separate final read catches a new trial, STOP or mutation while the scene
    # was being serialized. No camera/worker/provider or state mutation is used.
    latest = runtime.prevention.comparison_detail(comparison_id)
    if (digest(latest["comparison"]) != result["comparison_sha256"]
            or latest["evaluation"]["snapshot_hash"] != evaluation_snapshot_hash
            or latest["is_current"] != current):
        raise ValueError("Scene evidence changed while loading; reload the comparison")
    with runtime.store.connection() as db:
        db.execute("BEGIN")
        final_case = db.execute("SELECT payload FROM cases WHERE id=?", (comparison["case_id"],)).fetchone()
        if final_case is None or digest(json.loads(final_case[0])) != digest(case):
            raise ValueError("Scene source case changed while loading")
        final_trial_ids = db.execute("SELECT id FROM records WHERE kind=? AND "
            "json_extract(payload,'$.comparison_id')=? ORDER BY created,id LIMIT ?",
            (TRIAL_KIND, comparison_id, MAX_TRIALS + 1)).fetchall()
        if sorted(row[0] for row in final_trial_ids) != sorted(trial["id"] for trial in trials):
            raise ValueError("Scene trial ledger changed while loading")
        for (kind, identity), expected in artifacts.items():
            if digest(_read(db, kind, identity)) != expected:
                raise ValueError("Scene artifact changed while loading")
    result["scene_sha256"] = digest(result)
    if len(json.dumps(result, allow_nan=False).encode()) > MAX_SCENE_BYTES:
        raise ValueError("Scene payload exceeds its bounded byte budget")
    return result
