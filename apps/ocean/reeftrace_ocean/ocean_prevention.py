"""Frozen, illustrative interception comparison through real changing currents.

This is a counterfactual passive-tracer experiment, not an engineered boom plan:
barriers absorb a model particle on first contact without changing the flow.
Geometry is fixed independently of outputs; every layout sees the same releases
and identical immutable current-forced paths. No tank evidence is used.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

import numpy as np

from .advection import CurrentSampler, advect_current
from .current_forecast import (
    ATTRIBUTION,
    DATASET_ID,
    END_UTC,
    MANIFEST_SHA256,
    METADATA_URL,
    PRODUCT_URL,
    SOURCE_URL,
    START_UTC,
    load_current_snapshot,
)
from .field import _wgs84_metres_per_degree

LENGTH_TOL_M = 1e-7
TIME_TOL_S = 1e-6
DEFAULT_SCENARIO_ID = "downstream-corridor-v2"
SUPPORTED_SCENARIOS = ("initial-proxy-v1", "downstream-corridor-v2")
FRAME_LATITUDE_DEG = 21.0
FRAME_LONGITUDE_DEG = -158.0
HORIZON_S = 21600.0
CHORD_INTERVAL_S = 300.0


def _sha256(value: dict) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def _frame() -> dict:
    east, north = _wgs84_metres_per_degree(FRAME_LATITUDE_DEG)
    return {
        "kind": "fixed_local_WGS84_metric_linearization",
        "origin_latitude_deg": FRAME_LATITUDE_DEG,
        "origin_longitude_deg": FRAME_LONGITUDE_DEG,
        "east_metres_per_degree": east, "north_metres_per_degree": north,
        "axes": "x east, y north", "position_units": "m",
        "limitation": "Fixed-origin local linearization for this bounded kilometre-scale geometry.",
    }


def _geo(x: float, y: float, frame: dict) -> dict:
    return {
        "latitude_deg": frame["origin_latitude_deg"] + y / frame["north_metres_per_degree"],
        "longitude_deg": frame["origin_longitude_deg"] + x / frame["east_metres_per_degree"],
    }


def _xy(point: dict, frame: dict) -> list[float]:
    return [
        (point["longitude_deg"] - frame["origin_longitude_deg"])
        * frame["east_metres_per_degree"],
        (point["latitude_deg"] - frame["origin_latitude_deg"])
        * frame["north_metres_per_degree"],
    ]


def frozen_scenario(scenario_id: str = DEFAULT_SCENARIO_ID) -> dict:
    """Return fresh copies of a pre-outcome hypothesis, never an optimized site plan.

    The proxy is offshore south of Oahu, not a mapped real coral polygon. Central
    and flanking hypotheses have equal total line length and differ in coverage.
    All geometry is declared here before the pinned source is integrated.
    """
    if scenario_id not in SUPPORTED_SCENARIOS:
        raise ValueError("Select a supported frozen illustrative scenario")
    frame = _frame()
    initial = scenario_id == "initial-proxy-v1"
    polygon = ([[-5000.0, -1000.0], [-3500.0, -1000.0],
                [-3500.0, 1000.0], [-5000.0, 1000.0]] if initial else
               [[-6000.0, -5000.0], [-3500.0, -5000.0],
                [-3500.0, 500.0], [-6000.0, 500.0]])

    def segment(identity: str, y0: float, y1: float) -> dict:
        a, b = [-1500.0, y0], [-1500.0, y1]
        return {"id": identity, "start_xy_m": a, "end_xy_m": b,
                "start_geo": _geo(*a, frame), "end_geo": _geo(*b, frame)}

    return {
        "id": scenario_id,
        "label": ("Initial proxy · negative control" if initial else
                  "Downstream corridor · illustrative what-if"),
        "design_status": ("INITIAL_GEOMETRY_NEGATIVE_CONTROL" if initial else
                          "ILLUSTRATIVE_WHAT_IF_AFTER_VIEWING_PREVIEW"),
        "geometry_status": ("fixed_pre_outcome_illustrative_hypothesis_not_optimized" if initial
                            else "fixed_post_preview_illustrative_hypothesis_not_independent_validation"),
        "design_disclosure": (
            "Original geometry is retained unchanged, including a valid zero-baseline-entry result."
            if initial else
            "The downstream area was chosen after viewing the initial preview. This is an exploratory planning what-if, not independent performance evidence or an optimized real deployment."
        ),
        "frame": frame,
        "start_time_utc": START_UTC, "horizon_s": HORIZON_S,
        "protected_zone": {
            "id": "hypothetical-reef-proxy", "label": "Hypothetical protected reef-area proxy",
            "polygon_xy_m": polygon, "polygon_geo": [_geo(*point, frame) for point in polygon],
            "is_mapped_real_reef": False,
        },
        "releases": [
            {"id": f"release-{index + 1}", "x_m": 0.0, "y_m": y,
             **_geo(0, y, frame), "start_time_utc": START_UTC, "horizon_s": HORIZON_S,
             "kind": "hypothetical_passive_tracer_not_observed_waste"}
            for index, y in enumerate((-1250.0, -750.0, -250.0, 250.0, 750.0, 1250.0))
        ],
        "layouts": [
            {"id": "central", "label": "Central coverage", "total_length_m": 2000.0,
             "segments": [segment("central-line", -1000, 1000)]},
            {"id": "flanking", "label": "Flanking coverage", "total_length_m": 2000.0,
             "segments": [segment("southern-line", -2000, -1000),
                          segment("northern-line", 1000, 2000)]},
        ],
        "resource_constraint": "Both layouts use 2000 m of idealized absorbing line; no cost model.",
        "event_model": {
            "capture": "first_path_segment_contact_with_ideal_absorbing_line",
            "reef_entry": "first_path_segment_contact_with_closed_protected_polygon",
            "ties": "protected_zone_entry_wins_within_1_microsecond",
            "solver_step_s": CHORD_INTERVAL_S,
            "event_chord_output_step_s": CHORD_INTERVAL_S,
            "event_localization": "linear_fraction_on_supported_300_second_output_chords",
            "start_inside_zone": "immediate_entry_at_release",
        },
    }


def _cross(a: list[float], b: list[float]) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _on_segment(point: list[float], start: list[float], end: list[float]) -> bool:
    delta = [end[0] - start[0], end[1] - start[1]]
    offset = [point[0] - start[0], point[1] - start[1]]
    length = math.hypot(*delta)
    if length <= LENGTH_TOL_M:
        return math.hypot(*offset) <= LENGTH_TOL_M
    projection = sum(a * b for a, b in zip(offset, delta, strict=True)) / length
    return (abs(_cross(offset, delta)) / length <= LENGTH_TOL_M
            and -LENGTH_TOL_M <= projection <= length + LENGTH_TOL_M)


def _segment_crossing_fraction(a: list[float], b: list[float],
                               c: list[float], d: list[float]) -> float | None:
    """First closed-segment contact along a→b, including collinear overlap."""
    r, s = [b[0] - a[0], b[1] - a[1]], [d[0] - c[0], d[1] - c[1]]
    length_r, length_s = math.hypot(*r), math.hypot(*s)
    if length_r <= LENGTH_TOL_M:
        return 0.0 if _on_segment(a, c, d) else None
    if length_s <= LENGTH_TOL_M:
        if not _on_segment(c, a, b):
            return None
        return max(0.0, min(1.0, ((c[0] - a[0]) * r[0] + (c[1] - a[1]) * r[1])
                                / (length_r * length_r)))
    offset = [c[0] - a[0], c[1] - a[1]]
    denominator = _cross(r, s)
    if abs(denominator) <= 1e-12 * length_r * length_s:
        if abs(_cross(offset, r)) / length_r > LENGTH_TOL_M:
            return None
        projections = [((p[0] - a[0]) * r[0] + (p[1] - a[1]) * r[1])
                       / (length_r * length_r) for p in (c, d)]
        low, high = max(0.0, min(projections)), min(1.0, max(projections))
        return low if low <= high else None
    fraction = _cross(offset, s) / denominator
    other = _cross(offset, r) / denominator
    tolerance = LENGTH_TOL_M / min(length_r, length_s)
    if -tolerance <= fraction <= 1 + tolerance and -tolerance <= other <= 1 + tolerance:
        return max(0.0, min(1.0, fraction))
    return None


def _inside(point: list[float], polygon: list[list[float]]) -> bool:
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        if _on_segment(point, a, b):
            return True
        if (a[1] > point[1]) != (b[1] > point[1]):
            x_cross = a[0] + (point[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if point[0] < x_cross:
                inside = not inside
    return inside


def _polygon_entry_fraction(a: list[float], b: list[float],
                            polygon: list[list[float]]) -> float | None:
    if _inside(a, polygon):
        return 0.0
    fractions = [fraction for c, d in zip(polygon, polygon[1:] + polygon[:1], strict=True)
                 if (fraction := _segment_crossing_fraction(a, b, c, d)) is not None]
    return min(fractions) if fractions else None


def _local_track(track: list[dict], frame: dict) -> list[dict]:
    result = []
    for point in track:
        x, y = _xy(point, frame)
        result.append({**point, "x_m": x, "y_m": y})
    return result


def _event_point(a: dict, b: dict, fraction: float) -> dict:
    elapsed = a["elapsed_s"] + fraction * (b["elapsed_s"] - a["elapsed_s"])
    when = datetime.fromisoformat(a["time_utc"]) + timedelta(
        seconds=elapsed - a["elapsed_s"]
    )
    point = {key: a[key] + fraction * (b[key] - a[key]) for key in (
        "elapsed_s", "latitude_deg", "longitude_deg", "x_m", "y_m",
        "eastward_m_s", "northward_m_s", "speed_m_s",
    )}
    point.update({"time_utc": when.isoformat().replace("+00:00", "Z"),
                  "interpolated_event": True})
    return point


def evaluate_path(path: dict, release: dict, segments: list[dict],
                  polygon: list[list[float]], frame: dict) -> dict:
    """Evaluate a supported path once; retain explicit unknowns on forcing stops.

    Public only for deterministic numerical verification; the product endpoint
    always supplies the frozen scenario. This function cannot change the field.
    """
    track = _local_track(path["track"], frame)
    event = None
    status = None
    # A declared release position is known even if no velocity is available.
    # Only an immediate geometric event may resolve an otherwise empty path;
    # no future trajectory or zero velocity is manufactured.
    if not track:
        x, y = _xy(release, frame)
        immediate = _inside([x, y], polygon) or any(
            _on_segment([x, y], segment["start_xy_m"], segment["end_xy_m"])
            for segment in segments
        )
        if immediate:
            track = [{"x_m": x, "y_m": y, **_geo(x, y, frame), "elapsed_s": 0.0,
                      "time_utc": release["start_time_utc"], "eastward_m_s": None,
                      "northward_m_s": None, "speed_m_s": None}]
    if track and _inside([track[0]["x_m"], track[0]["y_m"]], polygon):
        event = {"kind": "PROTECTED_ZONE_ENTRY", **track[0], "segment_id": None}
        status, track = "ENTERED_PROTECTED_ZONE", track[:1]
    else:
        # A release on a collector is contact at t=0, unless it is also already
        # in the protected zone. Handle a singleton path before any forcing step.
        if track:
            xy = [track[0]["x_m"], track[0]["y_m"]]
            for segment in segments:
                if _on_segment(xy, segment["start_xy_m"], segment["end_xy_m"]):
                    event = {"kind": "IDEALIZED_CAPTURE", **track[0],
                             "segment_id": segment["id"]}
                    status, track = "IDEALIZED_INTERCEPTION", track[:1]
                    break
        if event is None:
            for index, (a, b) in enumerate(pairwise(track)):
                start, end = [a["x_m"], a["y_m"]], [b["x_m"], b["y_m"]]
                entry = _polygon_entry_fraction(start, end, polygon)
                captures = [(fraction, segment["id"]) for segment in segments
                            if (fraction := _segment_crossing_fraction(
                                start, end, segment["start_xy_m"], segment["end_xy_m"],
                            )) is not None]
                capture = min(captures, default=None)
                if entry is None and capture is None:
                    continue
                dt = b["elapsed_s"] - a["elapsed_s"]
                if entry is not None and (capture is None
                                         or entry * dt <= capture[0] * dt + TIME_TOL_S):
                    fraction, kind, identity = entry, "PROTECTED_ZONE_ENTRY", None
                    status = "ENTERED_PROTECTED_ZONE"
                else:
                    fraction, identity = capture
                    kind, status = "IDEALIZED_CAPTURE", "IDEALIZED_INTERCEPTION"
                point = _event_point(a, b, fraction)
                event = {"kind": kind, **point, "segment_id": identity}
                track = track[:index + 1]
                if point["elapsed_s"] > track[-1]["elapsed_s"]:
                    track.append(point)
                break
    if status is None:
        status = "NO_ENTRY_WITHIN_HORIZON" if path["status"] == "COMPLETED" else "UNRESOLVED"
    return {
        "release_id": release["id"], "status": status, "event": event,
        "forcing_status": path["status"], "forcing_reason_code": path["reason_code"],
        "requested_horizon_s": path["requested_horizon_s"],
        "integrated_horizon_s": path["completed_horizon_s"],
        "track_end_elapsed_s": track[-1]["elapsed_s"] if track else None,
        "track": track,
    }


def summarize_outcomes(outcomes: list[dict]) -> dict:
    counts = {name: sum(outcome["status"] == status for outcome in outcomes)
              for name, status in (
                  ("entered_count", "ENTERED_PROTECTED_ZONE"),
                  ("intercepted_count", "IDEALIZED_INTERCEPTION"),
                  ("no_entry_count", "NO_ENTRY_WITHIN_HORIZON"),
                  ("unresolved_count", "UNRESOLVED"),
              )}
    denominator = len(outcomes)
    if not denominator or sum(counts.values()) != denominator:
        raise ValueError("Every release requires exactly one recognized outcome")
    lower, upper = counts["entered_count"], counts["entered_count"] + counts["unresolved_count"]
    return {
        "release_count": denominator, **counts,
        "protected_entry_count_bounds": [lower, upper],
        "protected_entry_fraction_bounds": [lower / denominator, upper / denominator],
        "denominator_policy": "all_fixed_releases_including_missing_forcing_and_partial_paths",
    }


def recommend_layout(layouts: list[dict]) -> dict:
    """Recommend only a strictly nonoverlapping lower entry range, never a tie-break."""
    if len(layouts) != 2:
        raise ValueError("This frozen comparison requires exactly two layouts")
    left, right = layouts
    left_bounds = left["summary"]["protected_entry_count_bounds"]
    right_bounds = right["summary"]["protected_entry_count_bounds"]
    if left_bounds[1] < right_bounds[0]:
        best = left
    elif right_bounds[1] < left_bounds[0]:
        best = right
    else:
        exact_tie = (left_bounds[0] == left_bounds[1] == right_bounds[0] == right_bounds[1])
        return {
            "status": "TIE" if exact_tie else "INDETERMINATE", "best_layout_id": None,
            "reason": ("Both hypothetical layouts have the same fully resolved model entry count."
                       if exact_tie else
                       "Entry bounds overlap; unresolved forcing does not support a best layout."),
            "comparison_basis": "strict_nonoverlap_of_model_protected_entry_count_bounds",
        }
    return {
        "status": "BEST_LAYOUT", "best_layout_id": best["id"],
        "reason": f"{best['label']} has a strictly lower modeled entry range for this frozen scenario.",
        "comparison_basis": "strict_nonoverlap_of_model_protected_entry_count_bounds",
    }


def _method_sha256() -> str:
    digest = hashlib.sha256()
    for name in ("advection.py", "field.py", "current_forecast.py", "ocean_prevention.py",
                 "ocean_numerics.py"):
        digest.update(name.encode() + b"\0")
        digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def run_ocean_prevention(scenario_id: str = DEFAULT_SCENARIO_ID) -> dict:
    """Compare two predeclared layouts using one identical dynamic path per release."""
    from .ocean_numerics import run_numerical_sensitivity

    scenario = frozen_scenario(scenario_id)
    scenario_sha256 = _sha256(scenario)
    field, manifest = load_current_snapshot()
    # Integrate once per release. Counterfactual barriers do not alter the flow;
    # each layout observes exactly these same supported paths and first events.
    paths = [advect_current(
        field, latitude_deg=release["latitude_deg"], longitude_deg=release["longitude_deg"],
        start_time_utc=release["start_time_utc"], horizon_s=release["horizon_s"],
        step_s=CHORD_INTERVAL_S, output_step_s=CHORD_INTERVAL_S,
    ) for release in scenario["releases"]]
    polygon, frame = scenario["protected_zone"]["polygon_xy_m"], scenario["frame"]

    def comparison(identity: str, label: str, segments: list[dict], length: float) -> dict:
        outcomes = [evaluate_path(path, release, segments, polygon, frame)
                    for path, release in zip(paths, scenario["releases"], strict=True)]
        return {"id": identity, "label": label, "segments": segments,
                "total_length_m": length, "outcomes": outcomes,
                "summary": summarize_outcomes(outcomes)}

    baseline = comparison("no-interceptor", "No-interceptor context", [], 0.0)
    layouts = [comparison(layout["id"], layout["label"], layout["segments"],
                          layout["total_length_m"]) for layout in scenario["layouts"]]
    baseline_bounds = baseline["summary"]["protected_entry_count_bounds"]
    for layout in layouts:
        bounds = layout["summary"]["protected_entry_count_bounds"]
        layout["summary"]["entry_reduction_count_bounds_vs_baseline"] = [
            baseline_bounds[0] - bounds[1], baseline_bounds[1] - bounds[0],
        ]
    archived = datetime.now(UTC) > datetime.fromisoformat(END_UTC)
    field_summary = field.summary()
    # A fixed 3×3 display sampling is not a refinement of the 4 km model grid.
    # Include all counterfactual paths when fixing display bounds, not only the
    # currently selected layout or trajectories.
    display_points = polygon + [[release["x_m"], release["y_m"]]
                                for release in scenario["releases"]]
    for layout in scenario["layouts"]:
        for segment in layout["segments"]:
            display_points.extend([segment["start_xy_m"], segment["end_xy_m"]])
    display_points.extend(_xy(point, frame) for path in paths for point in path["track"])
    x_bounds = [min(point[0] for point in display_points), max(point[0] for point in display_points)]
    y_bounds = [min(point[1] for point in display_points), max(point[1] for point in display_points)]
    sampler, vector_frames = CurrentSampler(field), []
    for when in field.time_utc:
        seconds = float((when - field.time_utc[0]) / np.timedelta64(1, "s"))
        vectors = []
        for x in np.linspace(*x_bounds, 3):
            for y in np.linspace(*y_bounds, 3):
                position = _geo(float(x), float(y), frame)
                try:
                    east, north = sampler.sample(
                        position["latitude_deg"], position["longitude_deg"], seconds,
                    )
                except ValueError:
                    continue
                vectors.append({"x_m": float(x), "y_m": float(y), **position,
                                "eastward_m_s": east, "northward_m_s": north})
        vector_frames.append({"time_utc": str(when) + "Z", "vectors": vectors})
    report = {
        "schema_version": 1, "kind": "OCEAN_PREVENTION_COMPARISON",
        "status": ("COMPLETED" if all(path["status"] == "COMPLETED" for path in paths)
                   else "PARTIAL" if any(path["completed_horizon_s"] > 0 for path in paths)
                   else "UNSUPPORTED"),
        "mode": "archived_forecast_snapshot" if archived else "forecast_snapshot",
        "snapshot_sha256": manifest["files"]["csv"]["sha256"],
        "manifest_sha256": MANIFEST_SHA256, "method_sha256": _method_sha256(),
        "scenario_sha256": scenario_sha256, "scenario": scenario,
        "available_scenarios": [
            {key: preset[key] for key in ("id", "label", "design_status", "design_disclosure")}
            for identity in SUPPORTED_SCENARIOS if (preset := frozen_scenario(identity))
        ],
        "protected_zone": scenario["protected_zone"], "releases": scenario["releases"],
        "baseline": baseline, "layouts": layouts, "recommendation": recommend_layout(layouts),
        "vector_frames": vector_frames,
        "vector_sampling": "interpolated_display_samples_not_finer_observations",
        "vector_speed_scale_m_s": max((math.hypot(vector["eastward_m_s"], vector["northward_m_s"])
                                       for item in vector_frames for vector in item["vectors"]),
                                      default=0.0),
        "display_bounds_xy_m": {"x_m": x_bounds, "y_m": y_bounds},
        "forcing": {
            "dataset_id": DATASET_ID, "source_url": SOURCE_URL, "metadata_url": METADATA_URL,
            "product_url": PRODUCT_URL, "attribution": ATTRIBUTION,
            "captured_at_utc": manifest["captured_at_utc"],
            "valid_start_utc": START_UTC, "valid_end_utc": END_UTC,
            "model_issue_time_utc": None,
            "aggregation": "FMRC Best Dataset; not a separately pinned single model run",
            "future_valid_times_at_acquisition": manifest["future_valid_times_at_acquisition"],
            "depth_m": field.selected_depth_m, "nominal_grid_spacing_m": 4000,
            "time_step_s": 10800, "grid_shape": field_summary["shape"],
            "valid_sample_count": field_summary["valid_sample_count"],
            "invalid_sample_count": field_summary["invalid_sample_count"],
            "license": field.metadata["license"],
        },
        "method": {
            "trajectory": "dynamic_current_advection_only",
            "equation": "dX/dt = u(X,t)",
            "solver": "RK4 with local WGS84 metric derivatives",
            "spatial_interpolation": "bilinear", "temporal_interpolation": "linear",
            "step_s": CHORD_INTERVAL_S, "output_step_s": CHORD_INTERVAL_S,
            "geometry_frame": frame, "event_model": scenario["event_model"],
            "identical_unmodified_forcing_for_every_layout": True,
            "paths_integrated_once_per_release": True,
            "paths_integrated_once_scope": "main_decision_paths_only_separate_numerical_diagnostic_reruns",
            "barriers_modify_flow": False,
            "capture_efficiency_assumption": "ideal_absorbing_first_contact_not_measured",
            "winner_rule": "strict_nonoverlap_of_entry_bounds_else_tie_or_indeterminate",
        },
        "validation": {
            "measured_track_available": False, "physical_validation": False,
            "plastic_motion_validated": False, "forecast_skill_established": False,
            "interception_benefit_established": False, "real_reef_boundary_used": False,
            "tank_flow_used": False, "heldout_buoy_positions_used": False,
            "measured_entry_count": None, "measured_intercepted_count": None,
        },
        "limitations": [
            "Real model currents drive hypothetical passive releases, not observed waste.",
            "The protected area and both equal-line-length layouts are illustrative fixed hypotheses, not mapped or optimized real deployments.",
            scenario["design_disclosure"],
            "An ideal absorbing line captures on geometric first contact; no boom efficiency, depth, waves, navigation, engineering feasibility or cost is established.",
            "Layouts do not change currents; no barrier-flow interaction or collection hydrodynamics is modeled.",
            "Protected-zone boundary contact is entry; entry wins simultaneous capture ties conservatively.",
            "Events are interpolated on supported 300-second solver-output chords; sub-chord curvature and brief contacts can be missed.",
            "A 4 km grid and 3-hour forcing do not resolve reef-scale eddies or 2 km collection lines.",
            "No windage, Stokes drift, diffusion, beaching, retention or object response is modeled.",
            "Missing forcing leaves explicit unresolved outcomes in the full release denominator and entry bounds.",
            "No measured ecological protection, physical interception benefit or forecast accuracy is claimed.",
            "The best-forecast aggregation has no verified single issue time; acquisition-time valid times do not prove full operational forecast causality.",
            "Ocean SI units and hypothetical results do not calibrate the centimetre tank experiment.",
        ] + (["The valid-time window has ended; this is an archived forecast snapshot, not live conditions."]
             if archived else []),
    }
    report["numerical_sensitivity"] = run_numerical_sensitivity(field, scenario)
    # Clock-dependent archival labeling is an honest display state; the complete
    # serialized report identity includes that state rather than hiding changes.
    report["report_sha256"] = _sha256(report)
    return report
