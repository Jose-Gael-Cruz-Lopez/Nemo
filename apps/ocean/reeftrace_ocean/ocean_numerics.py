"""Two separate, bounded numerical checks of one frozen ocean scenario.

Integration changes the solver step while keeping output times fixed. Event
localization changes only the chords sampled from one fine path. Neither check
has observed truth or measures physical/ML skill; neither changes the decision.
"""

from __future__ import annotations

import math

from .advection import advect_current
from .ocean_prevention import _xy, evaluate_path, recommend_layout, summarize_outcomes

LEVELS_S = (300.0, 150.0, 75.0)
OUTPUT_S = 300.0


def _integrate(field, release: dict, step: float, output: float) -> dict:
    return advect_current(
        field, latitude_deg=release["latitude_deg"], longitude_deg=release["longitude_deg"],
        start_time_utc=release["start_time_utc"], horizon_s=release["horizon_s"],
        step_s=step, output_step_s=output,
    )


def _forcing(path: dict) -> dict:
    return {
        "forcing_status": path["status"], "forcing_reason_code": path["reason_code"],
        "requested_horizon_s": path["requested_horizon_s"],
        "completed_horizon_s": path["completed_horizon_s"],
    }


def _separation(path: dict, reference: dict, frame: dict) -> dict:
    # Exact common output timestamps only. A terminal partial point is compared
    # only when both integrations accepted that exact time; no interpolation or
    # extrapolation is used to manufacture coverage.
    truth_free_reference = {p["elapsed_s"]: p for p in reference["track"]
                            if p["elapsed_s"] > 0}
    differences = []
    for point in path["track"]:
        elapsed = point["elapsed_s"]
        if elapsed <= 0 or elapsed not in truth_free_reference:
            continue
        xy, other = _xy(point, frame), _xy(truth_free_reference[elapsed], frame)
        differences.append((elapsed, math.hypot(xy[0] - other[0], xy[1] - other[1])))
    return {
        "status": "COMPARED" if differences else "NO_COMMON_POSITIVE_TIME",
        "common_positive_time_count": len(differences),
        "last_common_elapsed_s": differences[-1][0] if differences else None,
        "max_separation_m": max((item[1] for item in differences), default=None),
        "rms_separation_m": (math.sqrt(sum(item[1] ** 2 for item in differences)
                                       / len(differences)) if differences else None),
        "last_common_separation_m": differences[-1][1] if differences else None,
        "both_completed": path["status"] == reference["status"] == "COMPLETED",
        "reference_completed_horizon_s": reference["completed_horizon_s"],
        "reference_forcing_status": reference["status"],
        "reference_forcing_reason_code": reference["reason_code"],
    }


def _downsample(path: dict, interval: float) -> dict:
    """Retain actual fine-path samples and its terminal accepted partial point."""
    track = path["track"]
    selected = [p for p in track if math.isclose(
        p["elapsed_s"] % interval, 0.0, rel_tol=0, abs_tol=1e-8)]
    if track and (not selected or selected[-1]["elapsed_s"] != track[-1]["elapsed_s"]):
        selected.append(track[-1])
    return {**path, "track": selected}


def _outcome_identity(outcome: dict) -> tuple:
    event = outcome["event"]
    return (outcome["status"], event["kind"] if event else None,
            event["segment_id"] if event else None)


def _compact_outcome(outcome: dict, reference: dict) -> dict:
    event, reference_event = outcome["event"], reference["event"]
    resolved = outcome["status"] != "UNRESOLVED" and reference["status"] != "UNRESOLVED"
    matches = resolved and _outcome_identity(outcome) == _outcome_identity(reference)
    timed = matches and event is not None and reference_event is not None
    return {
        "release_id": outcome["release_id"], "status": outcome["status"],
        "event_kind": event["kind"] if event else None,
        "segment_id": event["segment_id"] if event else None,
        "event_elapsed_s": event["elapsed_s"] if event else None,
        "forcing_status": outcome["forcing_status"],
        "forcing_reason_code": outcome["forcing_reason_code"],
        "requested_horizon_s": outcome["requested_horizon_s"],
        "completed_horizon_s": outcome["integrated_horizon_s"],
        "track_end_elapsed_s": outcome["track_end_elapsed_s"],
        "comparison_status": ("UNRESOLVED" if not resolved else
                              "MATCHED_EVENT" if timed else
                              "MATCHED_NO_EVENT" if matches else "CHANGED_OUTCOME"),
        "event_time_difference_s": (abs(event["elapsed_s"] - reference_event["elapsed_s"])
                                    if timed else None),
    }


def _evaluate(paths: list[dict], scenario: dict) -> dict:
    def row(identity: str, label: str, segments: list[dict]) -> dict:
        outcomes = [evaluate_path(path, release, segments,
                                 scenario["protected_zone"]["polygon_xy_m"], scenario["frame"])
                    for path, release in zip(paths, scenario["releases"], strict=True)]
        return {"id": identity, "label": label, "outcomes": outcomes,
                "summary": summarize_outcomes(outcomes)}

    baseline = row("no-interceptor", "No-interceptor context", [])
    layouts = [row(item["id"], item["label"], item["segments"])
               for item in scenario["layouts"]]
    return {"baseline": baseline, "layouts": layouts, "recommendation": recommend_layout(layouts)}


def run_numerical_sensitivity(field, scenario: dict) -> dict:
    """Use supplied immutable forcing/geometry, without data or provider requests.

    The fixed release denominator is retained at every level. Only aggregate
    comparisons and compact outcomes are serialized; the diagnostic tracks do
    not enter the displayed main paths or the source/tank evidence ledger.
    """
    releases = scenario["releases"]
    if not 1 <= len(releases) <= 12 or len(scenario["layouts"]) != 2:
        raise ValueError("The numerical diagnostic needs bounded fixed releases and two layouts")
    integration_paths = [[_integrate(field, release, step, OUTPUT_S) for release in releases]
                         for step in LEVELS_S]
    reference_paths = integration_paths[-1]
    integration_levels = []
    for step, paths in zip(LEVELS_S, integration_paths, strict=True):
        rows = [{"release_id": release["id"], **_forcing(path),
                 "comparison": _separation(path, reference, scenario["frame"])}
                for release, path, reference in zip(releases, paths, reference_paths, strict=True)]
        differences = [r["comparison"]["max_separation_m"] for r in rows
                       if r["comparison"]["max_separation_m"] is not None]
        integration_levels.append({
            "solver_step_s": step, "output_step_s": OUTPUT_S, "release_count": len(releases),
            "forcing_status_counts": {status: sum(p["status"] == status for p in paths)
                                      for status in ("COMPLETED", "PARTIAL", "UNSUPPORTED")},
            "releases": rows, "max_separation_m": max(differences, default=None),
            "comparable_release_count": len(differences),
        })
    # This is a separate experiment. Integrate exactly once per release at the
    # fine solver/output rate; every chord level selects points from that SAME
    # path. Re-running with output_step_s=300 here would confound the two checks.
    fine_paths = [_integrate(field, release, LEVELS_S[-1], LEVELS_S[-1]) for release in releases]
    event_results = [_evaluate([_downsample(path, interval) for path in fine_paths], scenario)
                     for interval in LEVELS_S]
    event_reference = event_results[-1]
    event_levels = []
    for interval, result in zip(LEVELS_S, event_results, strict=True):
        compact_rows = []
        for row, reference in zip([result["baseline"], *result["layouts"]],
                                  [event_reference["baseline"], *event_reference["layouts"]],
                                  strict=True):
            compact_rows.append({key: row[key] for key in ("id", "label", "summary")} | {
                "outcomes": [_compact_outcome(outcome, ref) for outcome, ref in zip(
                    row["outcomes"], reference["outcomes"], strict=True)]})
        outcomes = [outcome for row in compact_rows for outcome in row["outcomes"]]
        time_differences = [o["event_time_difference_s"] for o in outcomes
                            if o["event_time_difference_s"] is not None]
        recommendation = result["recommendation"]
        same_recommendation = all(recommendation[key] == event_reference["recommendation"][key]
                                  for key in ("status", "best_layout_id"))
        event_levels.append({
            "chord_interval_s": interval, "release_count": len(releases),
            "baseline": compact_rows[0], "layouts": compact_rows[1:],
            "recommendation": recommendation,
            "comparison_to_finest": {
                "recommendation_agrees": same_recommendation,
                "matched_event_count": sum(o["comparison_status"] == "MATCHED_EVENT"
                                           for o in outcomes),
                "matched_no_event_count": sum(o["comparison_status"] == "MATCHED_NO_EVENT"
                                              for o in outcomes),
                "changed_outcome_count": sum(o["comparison_status"] == "CHANGED_OUTCOME"
                                             for o in outcomes),
                "unresolved_comparison_count": sum(o["comparison_status"] == "UNRESOLVED"
                                                    for o in outcomes),
                "outcome_comparison_count": len(outcomes),
                "max_matched_event_time_difference_s": max(time_differences, default=None),
            },
        })
    separations = [level["max_separation_m"] for level in integration_levels
                   if level["max_separation_m"] is not None]
    all_complete = all(path["status"] == "COMPLETED"
                       for paths in [*integration_paths, fine_paths] for path in paths)
    return {
        "schema_version": 1, "kind": "OCEAN_NUMERICAL_SENSITIVITY", "release_count": len(releases),
        "scope": "separate_diagnostic_reruns_do_not_replace_main_decision_paths",
        "physical_validation": False, "independent_truth_used": False,
        "model_parameters_tuned": False,
        "diagnostic_advection_runs_per_release": 4,
        "integration": {"output_step_s": OUTPUT_S, "reference_solver_step_s": LEVELS_S[-1],
                        "comparison_metric": "fixed_scenario_frame_Euclidean_separation_m",
                        "positive_time_matching": "exact_common_accepted_output_times_only",
                        "levels": integration_levels},
        "events": {"solver_step_s": LEVELS_S[-1],
                   "reference_chord_interval_s": LEVELS_S[-1],
                   "same_fine_tracks_downsampled": True,
                   "terminal_accepted_partial_point_retained": True,
                   "forcing_status_counts": {status: sum(p["status"] == status for p in fine_paths)
                                             for status in ("COMPLETED", "PARTIAL", "UNSUPPORTED")},
                   "levels": event_levels},
        "summary": {
            "integration_max_separation_m": max(separations, default=None),
            "event_recommendation_agrees_at_all_levels": all(
                level["comparison_to_finest"]["recommendation_agrees"] for level in event_levels),
            "all_integrations_completed": all_complete,
            "meaning": "numerical sensitivity only; no physical accuracy or ML skill established",
        },
        "limitations": [
            "The finest numerical path is a comparison reference, not observed truth or an error bound.",
            "Step differences do not establish fourth-order convergence, forecast skill or physical accuracy.",
            "Only common positive accepted times are compared; missing or censored coverage stays explicit.",
            "Event time differences are compared only for resolved outcomes with the same event kind and collector identity.",
            "Partial or unsupported forcing is not numerical success, even when an earlier ideal geometric event is resolved.",
            "Chord refinement can still miss brief or tangent contacts; it does not improve the forcing grid or measure collector efficiency.",
            "No model promotion, scientific validation, tank calibration or hardware action is performed.",
        ],
    }
