"""Bounded, model-conditional first-passage comparison of two frozen layouts.

Source likelihood scores are deliberately absent: every declared source and
uncertainty scenario must support a recommendation. Physical trials are separate.
"""

from __future__ import annotations

import hashlib
import json
import math

import numpy as np

from apps.transport.reeftrace_transport.flow import FlowField
from apps.transport.reeftrace_transport.geometry import (
    Bounds,
    _segments_intersect,
    points_in_polygon,
    polygon_array,
)
from apps.transport.reeftrace_transport.simulation import Ensemble, simulate

MAX_STEPS = 2000
MAX_TOTAL_STATES = 6_000_000
MAX_PROFILE_BYTES = 200_000
MAX_PATH_POINTS = 80
MAX_PATHS = 6
_OVERRIDES = {"diffusivity_cm2_s", "drift_bias_cm_s", "dt_s", "age_prior"}


def _number(value, name: str, minimum: float, maximum: float) -> float:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not minimum <= value <= maximum):
        raise ValueError(f"{name} must be finite and in [{minimum}, {maximum}]")
    return float(value)


def _integer(value, name: str, minimum: int, maximum: int) -> int:
    result = _number(value, name, minimum, maximum)
    if result != math.floor(result):
        raise ValueError(f"{name} must be an integer")
    return int(result)


def _identifier(value, name: str) -> str:
    if (not isinstance(value, str) or not value.strip() or len(value) > 128
            or any(ord(c) < 32 for c in value)):
        raise ValueError(f"{name} must be a nonempty bounded identifier")
    return value


def _snapshot(document: dict) -> tuple[dict, str]:
    if not isinstance(document, dict):
        raise TypeError("Layouts must be JSON profile objects")
    try:
        encoded = json.dumps(document, sort_keys=True, allow_nan=False,
                             separators=(",", ":")).encode()
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("Profiles must contain finite JSON values") from exc
    if len(encoded) > MAX_PROFILE_BYTES:
        raise ValueError("Profile size budget exceeded")
    return json.loads(encoded), hashlib.sha256(encoded).hexdigest()


def _polygon_key(polygon: np.ndarray) -> tuple:
    vertices = tuple(map(tuple, polygon.tolist()))
    # Equivalent vertex origins and winding do not make a different source.
    versions = []
    for sequence in (vertices, vertices[::-1]):
        versions.extend(sequence[i:] + sequence[:i] for i in range(len(sequence)))
    return min(versions)


def _polygon(value: list, bounds: Bounds) -> np.ndarray:
    if not isinstance(value, list) or not 3 <= len(value) <= 65:
        raise ValueError("Polygon requires 3-64 numeric vertices and optional closure")
    for point in value:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("Polygon vertices must be numeric coordinate pairs")
        for coordinate in point:
            _number(coordinate, "polygon coordinate", -1_000_000, 1_000_000)
    return polygon_array(value, bounds)


def _touches(a: np.ndarray, b: np.ndarray) -> bool:
    if points_in_polygon(a, b).any() or points_in_polygon(b, a).any():
        return True
    return any(_segments_intersect(p, q, r, s)
               for p, q in zip(a, np.roll(a, -1, axis=0), strict=True)
               for r, s in zip(b, np.roll(b, -1, axis=0), strict=True))


def _prepare(profile: dict, zone: np.ndarray, horizon: float) -> dict:
    if profile.get("valid") is not True:
        raise ValueError("Both frozen profiles must be declared valid")
    origin = profile.get("data_origin")
    if origin not in {"SYNTHETIC", "MEASURED_TANK"}:
        raise ValueError("Use SYNTHETIC or MEASURED_TANK layout inputs")
    profile_id = _identifier(profile.get("id"), "profile id")
    _identifier(profile.get("calibration_id"), "calibration id")
    token = _identifier(profile.get("token_class"), "token class")
    bounds = Bounds.from_dict(profile["bounds"])
    if not isinstance(profile.get("flow"), dict):
        raise TypeError("Flow must be a frozen field object")
    flow = FlowField(profile["flow"])
    if np.abs(flow.velocity).max() > 100:
        raise ValueError("Declared drift exceeds the 100 cm/s component budget")
    if flow.bounds != bounds or profile["flow"].get("data_origin") != origin:
        raise ValueError("Flow bounds/data origin must match its profile")
    sources = profile.get("sources")
    if not isinstance(sources, list) or not 2 <= len(sources) <= 5:
        raise ValueError("Compare 2-5 declared candidate sources")
    source_map = {}
    for source in sources:
        if not isinstance(source, dict):
            raise TypeError("Source must be an object")
        sid = _identifier(source.get("id"), "source id")
        if sid in source_map:
            raise ValueError("Source IDs must be unique")
        polygon = _polygon(source["polygon_cm"], bounds)
        if _touches(polygon, zone):
            raise ValueError("Protected zone must not overlap or touch a source")
        source_map[sid] = polygon
    traps = profile.get("traps", [])
    if not isinstance(traps, list) or len(traps) > 5:
        raise ValueError("At most five validated absorbing traps per layout")
    trap_polygons, trap_ids = [], set()
    for trap in traps:
        if not isinstance(trap, dict):
            raise TypeError("Trap must be an object")
        tid = _identifier(trap.get("id"), "trap id")
        if tid in trap_ids or trap.get("validated") is not True:
            raise ValueError("Traps need unique IDs and explicit validated retention")
        if trap.get("retention", "absorbing") != "absorbing":
            raise ValueError("Only perfect absorbing retention is implemented")
        trap_ids.add(tid)
        polygon = _polygon(trap["polygon_cm"], bounds)
        if _touches(polygon, zone):
            raise ValueError("Protected zone must not overlap or touch a trap")
        if any(_touches(polygon, source) for source in source_map.values()):
            raise ValueError("A source cannot start inside or touching a trap")
        if any(_touches(polygon, other) for other in trap_polygons):
            raise ValueError("Overlapping or touching traps are ambiguous")
        trap_polygons.append(polygon)
    transport = profile.get("transport", {})
    if not isinstance(transport, dict):
        raise TypeError("Transport settings must be an object")
    maximum_age = _number(transport.get("max_age_s", 60), "maximum age", 1, 180)
    if horizon > maximum_age:
        raise ValueError("Comparison horizon exceeds the frozen transport horizon")
    variants = profile.get("sensitivity_variants", [])
    if not isinstance(variants, list) or len(variants) > 2:
        raise ValueError("Use nominal plus at most two predeclared scenarios")
    scenarios = {"nominal": transport}
    for variant in variants:
        if not isinstance(variant, dict) or set(variant) != {"id", "transport"}:
            raise ValueError("Each frozen scenario needs exactly id and transport")
        sid = _identifier(variant["id"], "scenario id")
        overrides = variant["transport"]
        if sid in scenarios or not isinstance(overrides, dict) or set(overrides) - _OVERRIDES:
            raise ValueError("Invalid, duplicate or unsupported frozen scenario")
        scenarios[sid] = {**transport, **overrides}
    checked = {}
    for sid, values in scenarios.items():
        dispersion = _number(values.get("diffusivity_cm2_s", 0.05), "dispersion", 0, 100)
        dt = _number(values.get("dt_s", 0.1), "time step", 0.01, 1)
        bias = values.get("drift_bias_cm_s", [0, 0])
        if not isinstance(bias, list) or len(bias) != 2:
            raise ValueError("Drift bias must be a two-number array")
        bias = [_number(v, "drift bias", -100, 100) for v in bias]
        checked[sid] = {"diffusivity_cm2_s": dispersion, "dt_s": dt, "drift_bias_cm_s": bias}
    gates = profile.get("gates", {})
    if not isinstance(gates, dict):
        raise TypeError("Profile gates must be an object")
    minimum_coverage = _number(gates.get("min_path_coverage", 0.9),
                               "minimum path coverage", 0, 1)
    if origin == "MEASURED_TANK":
        diagnostics = profile["flow"].get("diagnostics", {})
        if not isinstance(diagnostics, dict):
            raise ValueError("Measured flow diagnostics must be an object")
        if (not profile["flow"].get("id")
                or _number(diagnostics.get("validation_coverage_fraction"), "validation coverage", 0, 1) < 0.9):
            raise ValueError("Measured layouts need frozen independently validated recorded flow")
        error = _number(diagnostics.get("validation_rmse_cm_s"), "validation RMSE", 0, 1000)
        maximum = _number(profile.get("max_validation_rmse_cm_s"), "maximum validation RMSE", 1e-12, 1000)
        if error > maximum:
            raise ValueError("Measured flow fails its frozen validation error gate")
    return {"id": profile_id, "origin": origin, "token": token, "bounds": bounds,
            "field": flow, "sources": source_map, "traps": trap_polygons,
            "scenarios": checked, "minimum_coverage": minimum_coverage}


def _common_step(a: dict, b: dict, scenario: str, zone: np.ndarray, horizon: float) -> tuple[float, int]:
    values = [layout["scenarios"][scenario] for layout in (a, b)]
    dt = min(value["dt_s"] for value in values)
    feature = min(float(a["bounds"].size.min()), float(np.ptp(zone, axis=0).min()))
    for polygon in a["traps"] + b["traps"]:
        feature = min(feature, float(np.ptp(polygon, axis=0).min()))
    speed = max(float(np.linalg.norm(layout["field"].velocity, axis=1).max()
                      + np.linalg.norm(value["drift_bias_cm_s"]))
                for layout, value in zip((a, b), values, strict=True))
    dispersion = max(value["diffusivity_cm2_s"] for value in values)
    while speed * dt + 3 * math.sqrt(2 * dispersion * dt) > 0.5 * feature:
        dt /= 2
        if dt < horizon / MAX_STEPS:
            raise ValueError("Comparison step budget exceeded by thin geometry or dispersion")
    steps = max(1, math.ceil(horizon / dt))
    if steps > MAX_STEPS:
        raise ValueError("Comparison step budget exceeded")
    return horizon / steps, steps


def _first_retained(ensemble: Ensemble) -> tuple[np.ndarray, np.ndarray]:
    retained = ensemble.retained.any(axis=0)
    first = ensemble.retained.argmax(axis=0)
    return np.where(retained, first, len(ensemble.times_s) - 1), retained


def _first_passage(actual: Ensemble, competing: Ensemble, zone: np.ndarray) -> tuple[dict, dict]:
    if not np.array_equal(actual.times_s, competing.times_s):
        raise ValueError("Competing runs must have identical time discretization")
    n = actual.positions_cm.shape[1]
    first, event = _first_retained(competing)
    event_position = competing.positions_cm[first, np.arange(n)]
    zone_first = event & points_in_polygon(event_position, zone)
    capture_first = event & ~zone_first
    active = np.arange(len(competing.times_s))[:, None] <= first[None, :]
    supported = np.all(competing.supported | ~active, axis=0)
    unsupported_count = int((~supported).sum())
    zone_count = int(zone_first.sum())
    known_zone = int((zone_first & supported).sum())
    capture_index, captured = _first_retained(actual)
    # These are time-node UPPER bounds, not exposure-resolved event times. The
    # competing-absorber run determines order even within a reflected substep.
    details = {"zone_first": zone_first, "first_index": first, "supported": supported,
               "zone_entry_s": np.where(zone_first, competing.times_s[first], np.nan),
               "capture_s": np.where(captured, actual.times_s[capture_index], np.nan)}
    return {
        "particles": n, "zone_entry_count": zone_count, "zone_entry_fraction": zone_count / n,
        "zone_entry_lower_fraction": known_zone / n,
        "zone_entry_upper_fraction": (known_zone + unsupported_count) / n,
        "captured_before_zone_count": int(capture_first.sum()),
        "captured_before_zone_fraction": float(capture_first.mean()),
        "unresolved_count": int((~event).sum()), "unsupported_count": unsupported_count,
        "unsupported_fraction": unsupported_count / n,
        "supported_particle_fraction": float(supported.mean()),
        "path_coverage_fraction": float((competing.supported & active).sum() / active.sum()),
    }, details


def _paths(actual: Ensemble, detail: dict, layout: str, source: str) -> dict:
    paths = []
    selected = np.linspace(0, actual.positions_cm.shape[1] - 1,
                           min(MAX_PATHS, actual.positions_cm.shape[1]), dtype=int)
    indices = np.unique(np.linspace(0, len(actual.times_s) - 1,
                                    min(MAX_PATH_POINTS, len(actual.times_s)), dtype=int))
    for particle in selected:
        # Decimated paths are illustrative; event counts come from the full
        # competing simulation and never from these display segments.
        paths.append({
            "particle_index": int(particle),
            "points": [{"t_s": float(actual.times_s[i]),
                        "x_cm": float(actual.positions_cm[i, particle, 0]),
                        "y_cm": float(actual.positions_cm[i, particle, 1])} for i in indices],
            "zone_entry_s": (float(detail["zone_entry_s"][particle])
                             if math.isfinite(detail["zone_entry_s"][particle]) else None),
            "capture_s": (float(detail["capture_s"][particle])
                          if math.isfinite(detail["capture_s"][particle]) else None),
            "supported": bool(detail["supported"][particle]),
        })
    return {"layout": layout, "source_id": source, "paths": paths}


def compare_layouts(baseline: dict, intervention: dict, protected_zone_cm: list, *,
                    horizon_s=20, particles=100, seed=17) -> dict:
    """Compare frozen layouts; reject malformed input and withhold unsupported claims.

    Bounds, token class and candidate source geometries must agree. Source priors
    and release-age priors are not used: all particles start in a source at t=0.
    Recommendations are conditional on the complete predeclared scenario set,
    not statistical confidence statements or observed environmental benefits.
    """
    horizon = _number(horizon_s, "horizon seconds", 1, 20)
    count = _integer(particles, "particles per source", 20, 200)
    random_seed = _integer(seed, "seed", 0, 2**32 - 1)
    try:
        baseline, baseline_hash = _snapshot(baseline)
        intervention, intervention_hash = _snapshot(intervention)
        bounds = Bounds.from_dict(baseline["bounds"])
        zone = _polygon(protected_zone_cm, bounds)
        a, b = (_prepare(profile, zone, horizon) for profile in (baseline, intervention))
        if a["bounds"] != b["bounds"] or a["origin"] != b["origin"] or a["token"] != b["token"]:
            raise ValueError("Layouts require identical bounds, data origin and token class")
        if set(a["sources"]) != set(b["sources"]):
            raise ValueError("Layouts require the same declared source IDs")
        for sid in a["sources"]:
            if _polygon_key(a["sources"][sid]) != _polygon_key(b["sources"][sid]):
                raise ValueError("Layouts require identical source polygons")
        if set(a["scenarios"]) != set(b["scenarios"]):
            raise ValueError("Layouts require matching complete scenario IDs")
        scenarios = ["nominal"] + sorted(set(a["scenarios"]) - {"nominal"})
        steps = {sid: _common_step(a, b, sid, zone, horizon) for sid in scenarios}
        work = sum(4 * len(a["sources"]) * count * (n + 1) for _, n in steps.values())
        if work > MAX_TOTAL_STATES:
            raise ValueError("Total comparison workload exceeded; simplify the frozen experiment")
        rows, display_paths = [], []
        coverage_ok = True
        for scenario in scenarios:
            dt, _ = steps[scenario]
            for source in sorted(a["sources"]):
                row = {"scenario_id": scenario, "source_id": source}
                for name, layout, profile in (("baseline", a, baseline), ("intervention", b, intervention)):
                    settings = layout["scenarios"][scenario]
                    args = {"bounds": profile["bounds"], "particles": count, "dt_s": dt,
                            "horizon_s": horizon, "seed": random_seed, "max_steps": MAX_STEPS,
                            "diffusivity_cm2_s": settings["diffusivity_cm2_s"],
                            "drift_bias_cm_s": settings["drift_bias_cm_s"]}
                    actual = simulate(profile["flow"], layout["sources"][source].tolist(),
                                      traps=profile.get("traps", []), **args)
                    competing = simulate(profile["flow"], layout["sources"][source].tolist(),
                                         traps=profile.get("traps", []) + [
                                             {"polygon_cm": zone.tolist(), "retention": "absorbing"}], **args)
                    metrics, details = _first_passage(actual, competing, zone)
                    row[name] = metrics
                    # A single unsupported particle in ANY declared scenario
                    # withholds a prototype recommendation. Unknown outcomes
                    # still appear in conservative bounds and all denominators.
                    coverage_ok &= metrics["unsupported_count"] == 0
                    if scenario == "nominal":
                        display_paths.append(_paths(actual, details, name, source))
                row["benefit_fraction"] = row["baseline"]["zone_entry_fraction"] - row["intervention"]["zone_entry_fraction"]
                row["benefit_lower_fraction"] = row["baseline"]["zone_entry_lower_fraction"] - row["intervention"]["zone_entry_upper_fraction"]
                row["benefit_upper_fraction"] = row["baseline"]["zone_entry_upper_fraction"] - row["intervention"]["zone_entry_lower_fraction"]
                rows.append(row)
        lower = min(row["benefit_lower_fraction"] for row in rows)
        upper = max(row["benefit_upper_fraction"] for row in rows)
        recommendation, reasons = "NO_ROBUST_RECOMMENDATION", []
        if not coverage_ok:
            reasons.append("UNSUPPORTED_FLOW_PATHS")
        elif lower > 1e-12:
            recommendation = "INTERVENTION"
        elif upper < -1e-12:
            recommendation = "BASELINE"
        else:
            reasons.append("MIXED_OR_ZERO_EFFECT")
        report = {
            "schema_version": 1,
            "status": "SIMULATED_COMPARISON" if coverage_ok else "WITHHELD_UNSUPPORTED_FLOW",
            "data_origin": a["origin"], "physical_validation": False,
            "layouts": {name: {"profile_id": profile["id"], "profile_hash": digest,
                                "flow_hash": _snapshot(profile["flow"])[1]}
                        for name, profile, digest in (("baseline", baseline, baseline_hash),
                                                       ("intervention", intervention, intervention_hash))},
            "protected_zone_cm": zone.tolist(), "horizon_s": horizon,
            "particles_per_source": count, "seed": random_seed, "scenario_ids": scenarios,
            "results": rows, "robust_benefit_min": lower, "robust_benefit_max": upper,
            "recommendation": recommendation, "reason_codes": reasons,
            "nominal_paths": display_paths,
            "assumptions": {
                "outcomes": "SIMULATED_FIRST_PASSAGE_NOT_PHYSICAL_TRIALS",
                "world_units": "cm", "time_units": "s", "boundary": "reflecting_rectangle",
                "retention": "perfect_absorbing_traps_no_escape_or_partial_capture",
                "flow": "fixed_separate_layout_fields_no_predicted_hydrodynamic_change",
                "source_weighting": "NONE_all_declared_sources_must_agree",
                "source_prior_and_release_age": "NOT_USED_particles_released_at_t0",
                "support_rule": "any_unsupported_time_node_until_first_event_or_horizon_is_unknown",
                "unsupported_denominator": "all_particles_retained_unknown_outcomes_bound_benefit",
                "minimum_supported_particle_fraction": 1.0,
                "declared_profile_min_path_coverage": {"baseline": a["minimum_coverage"], "intervention": b["minimum_coverage"]},
                "event_rule": "competing_absorbing_zone_and_traps_segment_crossing_including_reflections",
                "touch_rule": "boundary_contact_counts_as_entry_overlapping_geometries_rejected",
                "event_time_kind": "time_node_upper_bound_resolution_dt_not_exact_exposure_time",
                "time_step_by_scenario_s": {sid: value[0] for sid, value in steps.items()},
                "recommendation_scope": "declared_sources_and_scenarios_not_statistical_confidence",
                "monte_carlo": "fixed_seed_common_random_numbers_no_sampling_confidence_claim",
                "display_paths": "decimated_illustrations_not_used_for_metrics",
                "particle_time_states": work,
                "limitations": ["No coral injury, avoided mortality or real-world pollution reduction is measured.",
                                "Input data origin does not validate simulated intervention outcomes.",
                                "Time-node support is a finite-step diagnostic, not continuous spatial coverage proof."],
            },
        }
        json.dumps(report, allow_nan=False)
        return report
    except (KeyError, TypeError, IndexError, OverflowError) as exc:
        raise ValueError("Malformed prevention comparison input") from exc
