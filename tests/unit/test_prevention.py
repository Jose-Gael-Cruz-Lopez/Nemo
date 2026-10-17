import copy
import json

import numpy as np
import pytest

from apps.estimation.reeftrace_estimation import prevention
from apps.transport.reeftrace_transport.flow import fit_flow
from apps.transport.reeftrace_transport.geometry import (
    Bounds,
    advance_reflecting,
    segment_polygon_hit,
)
from apps.transport.reeftrace_transport.simulation import Ensemble

BOUNDS = {"x_min_cm": 0, "x_max_cm": 12, "y_min_cm": 0, "y_max_cm": 10}
ZONE = [[7, 0], [8, 0], [8, 10], [7, 10]]


def rectangle(x0, x1, y0=0, y1=10):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def profiles():
    samples = [{"x_cm": x, "y_cm": y, "vx_cm_s": 1, "vy_cm_s": 0}
               for x in (0, 4, 8, 12) for y in (0, 5, 10)]
    profile = {
        "id": "baseline", "calibration_id": "synthetic-map", "valid": True,
        "data_origin": "SYNTHETIC", "token_class": "red-foam",
        "bounds": BOUNDS.copy(),
        "flow": fit_flow(samples, BOUNDS, coverage_radius_cm=8, data_origin="SYNTHETIC"),
        "sources": [{"id": name, "polygon_cm": rectangle(1, 1.1, y, y + 0.1), "prior": 0.5}
                    for name, y in (("A", 2), ("B", 8))],
        "traps": [], "transport": {"dt_s": 0.2, "max_age_s": 20, "diffusivity_cm2_s": 0},
        "gates": {"min_path_coverage": 0.9},
        "sensitivity_variants": [{"id": "no-dispersion-check", "transport": {"diffusivity_cm2_s": 0}}],
    }
    intervention = copy.deepcopy(profile)
    intervention["id"] = "intervention"
    intervention["traps"] = [{"id": "upstream-pocket", "polygon_cm": rectangle(4, 4.5),
                               "validated": True, "retention": "absorbing"}]
    return profile, intervention


def compare(a=None, b=None, **kwargs):
    if a is None:
        a, b = profiles()
    return prevention.compare_layouts(a, b, ZONE, horizon_s=10, particles=20, **kwargs)


def test_uniform_transport_upstream_interception_prevents_first_entry_for_every_source():
    report = compare()
    assert report["recommendation"] == "INTERVENTION"
    assert report["robust_benefit_min"] == report["robust_benefit_max"] == 1
    for row in report["results"]:
        assert row["baseline"]["zone_entry_count"] == 20
        assert row["intervention"]["zone_entry_count"] == 0
        assert row["intervention"]["captured_before_zone_count"] == 20
        assert row["baseline"]["captured_before_zone_count"] == 0
        assert row["benefit_lower_fraction"] == row["benefit_upper_fraction"] == 1
    assert report["physical_validation"] is False
    assert report["data_origin"] == "SYNTHETIC"
    assert report["assumptions"]["source_weighting"].startswith("NONE")
    json.dumps(report, allow_nan=False)


def test_worse_intervention_recommends_baseline_and_equal_layouts_do_not_invent_benefit():
    a, b = profiles()
    assert compare(b, a)["recommendation"] == "BASELINE"
    b["traps"] = []
    report = compare(a, b)
    assert report["recommendation"] == "NO_ROBUST_RECOMMENDATION"
    assert report["robust_benefit_min"] == report["robust_benefit_max"] == 0


def test_after_zone_capture_is_not_counted_as_preventing_zone_entry():
    a, b = profiles()
    b["traps"][0]["polygon_cm"] = rectangle(9, 9.5)
    report = compare(a, b)
    assert report["recommendation"] == "NO_ROBUST_RECOMMENDATION"
    assert all(row["intervention"]["zone_entry_count"] == 20 for row in report["results"])
    assert all(row["intervention"]["captured_before_zone_count"] == 0 for row in report["results"])
    assert all(path["capture_s"] > path["zone_entry_s"]
               for group in report["nominal_paths"] if group["layout"] == "intervention"
               for path in group["paths"])


def test_source_priors_do_not_weight_prevention_and_mixed_source_effect_withholds():
    a, b = profiles()
    b["traps"][0]["polygon_cm"] = rectangle(4, 4.5, 1, 3)
    first = compare(a, b)
    for profile in (a, b):
        profile["sources"][0]["prior"] = 1e100
        profile["sources"][1]["prior"] = 1e-100
    second = compare(a, b)
    assert first["results"] == second["results"]
    assert second["recommendation"] == "NO_ROBUST_RECOMMENDATION"
    assert second["robust_benefit_min"] == 0


def test_any_unsupported_particle_withholds_and_never_disappears_from_denominator():
    a, b = profiles()
    for profile in (a, b):
        profile["flow"]["coverage_radius_cm"] = 0.01
    report = compare(a, b)
    assert report["status"] == "WITHHELD_UNSUPPORTED_FLOW"
    assert report["recommendation"] == "NO_ROBUST_RECOMMENDATION"
    assert "UNSUPPORTED_FLOW_PATHS" in report["reason_codes"]
    for row in report["results"]:
        for layout in ("baseline", "intervention"):
            value = row[layout]
            assert value["particles"] == 20
            assert value["unsupported_count"] == 20
            assert value["zone_entry_lower_fraction"] == 0
            assert value["zone_entry_upper_fraction"] == 1
            assert value["zone_entry_count"] + value["captured_before_zone_count"] + value["unresolved_count"] == 20


def test_one_unsupported_particle_withholds_even_when_frozen_profile_allows_ninety_percent(monkeypatch):
    original = prevention.simulate

    def imperfect_support(*args, **kwargs):
        value = original(*args, **kwargs)
        value.supported[0, 0] = False
        return value

    monkeypatch.setattr(prevention, "simulate", imperfect_support)
    report = compare()
    assert report["recommendation"] == "NO_ROBUST_RECOMMENDATION"
    assert report["status"] == "WITHHELD_UNSUPPORTED_FLOW"
    assert report["results"][0]["baseline"]["supported_particle_fraction"] == 0.95
    assert report["results"][0]["baseline"]["zone_entry_fraction"] == 1
    assert report["results"][0]["baseline"]["zone_entry_lower_fraction"] == 0.95
    assert report["assumptions"]["minimum_supported_particle_fraction"] == 1


def test_all_declared_scenarios_must_agree_not_only_favorable_nominal_result():
    a, b = profiles()
    for profile in (a, b):
        profile["sensitivity_variants"] = [{"id": "frozen-still-water-discrepancy",
                                              "transport": {"drift_bias_cm_s": [-1, 0]}}]
    report = compare(a, b)
    assert report["scenario_ids"] == ["nominal", "frozen-still-water-discrepancy"]
    assert all(row["benefit_fraction"] == 1 for row in report["results"]
               if row["scenario_id"] == "nominal")
    assert all(row["benefit_fraction"] == 0 for row in report["results"]
               if row["scenario_id"] != "nominal")
    assert report["recommendation"] == "NO_ROBUST_RECOMMENDATION"
    assert report["robust_benefit_min"] == 0


def ensemble(start, end, retained):
    positions = np.stack([np.asarray(start, float), np.asarray(end, float)])
    flags = np.stack([np.zeros(len(start), bool), np.asarray(retained, bool)])
    return Ensemble(np.array([0., 1.]), positions, flags, np.ones(flags.shape, bool), 1.)


@pytest.mark.parametrize("trap_x,zone_x,expected_zone,expected_capture", [
    (3, 5, 0, 1), (5, 3, 1, 0),
])
def test_competing_absorbers_resolve_within_step_event_order(trap_x, zone_x, expected_zone, expected_capture):
    bounds = Bounds.from_dict(BOUNDS)
    start, delta = np.array([[1., 5.]]), np.array([[9., 0.]])
    trap = np.array(rectangle(trap_x, trap_x + 0.1))
    zone = np.array(rectangle(zone_x, zone_x + 0.01))
    end, held = advance_reflecting(start, delta, bounds, [trap])
    race_end, race_held = advance_reflecting(start, delta, bounds, [trap, zone])
    metric, _ = prevention._first_passage(ensemble(start, end, held), ensemble(start, race_end, race_held), zone)
    assert metric["zone_entry_count"] == expected_zone
    assert metric["captured_before_zone_count"] == expected_capture


def test_thin_protected_zone_on_reflected_subsegment_is_not_missed_by_endpoint_chord():
    bounds = Bounds(0, 10, 0, 10)
    start, delta = np.array([[9.7, 2.]]), np.array([[1., 4.]])
    zone = np.array(rectangle(9.7, 9.9, 3.8, 4.5))
    end, held = advance_reflecting(start, delta, bounds, [])
    # The start-to-final-endpoint chord misses the actual reflected encounter.
    assert not np.isfinite(segment_polygon_hit(start, end - start, zone)[0])
    race_end, race_held = advance_reflecting(start, delta, bounds, [zone])
    metric, _ = prevention._first_passage(ensemble(start, end, held), ensemble(start, race_end, race_held), zone)
    assert metric["zone_entry_count"] == 1
    assert metric["captured_before_zone_count"] == 0


def test_competing_simulation_matches_actual_random_path_until_first_event(monkeypatch):
    a, b = profiles()
    for profile in (a, b):
        profile["transport"]["diffusivity_cm2_s"] = 0.01
    original = prevention.simulate
    calls = []

    def recording_simulate(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(result)
        return result

    monkeypatch.setattr(prevention, "simulate", recording_simulate)
    compare(a, b, seed=73)
    for actual, race in zip(calls[::2], calls[1::2], strict=True):
        assert np.array_equal(actual.times_s, race.times_s)
        first, _ = prevention._first_retained(race)
        for particle, event_index in enumerate(first):
            assert np.array_equal(actual.positions_cm[:event_index, particle],
                                  race.positions_cm[:event_index, particle])


def test_coverage_after_first_zone_entry_does_not_invalidate_already_observed_first_passage():
    start = [[1, 5]]
    actual = ensemble(start, [[10, 5]], [False])
    race = ensemble(start, [[7, 5]], [True])
    # Add an unsupported later node only to actual post-zone motion.
    actual.supported[-1] = False
    metric, _ = prevention._first_passage(actual, race, np.array(ZONE))
    assert metric["unsupported_count"] == 0
    assert metric["zone_entry_count"] == 1


def test_reproducible_finite_report_preserves_inputs_and_bounds_ui_payload():
    a, b = profiles()
    for profile in (a, b):
        profile["transport"]["diffusivity_cm2_s"] = 0.01
    original = copy.deepcopy((a, b))
    first = compare(a, b, seed=9)
    assert first == compare(a, b, seed=9)
    assert (a, b) == original
    assert len(first["nominal_paths"]) == 4
    assert all(len(group["paths"]) <= 6 for group in first["nominal_paths"])
    assert all(len(path["points"]) <= 80 for group in first["nominal_paths"] for path in group["paths"])
    json.dumps(first, allow_nan=False)


def test_measured_input_does_not_become_measured_or_physically_validated_outcome():
    a, b = profiles()
    for profile in (a, b):
        profile["data_origin"] = profile["flow"]["data_origin"] = "MEASURED_TANK"
        profile["flow"]["id"] = profile["id"] + "-flow"
        profile["flow"]["diagnostics"].update(validation_rmse_cm_s=0.1, validation_coverage_fraction=1)
        profile["max_validation_rmse_cm_s"] = 0.2
    report = compare(a, b)
    assert report["data_origin"] == "MEASURED_TANK"
    assert report["physical_validation"] is False
    assert report["assumptions"]["outcomes"] == "SIMULATED_FIRST_PASSAGE_NOT_PHYSICAL_TRIALS"


@pytest.mark.parametrize("edit", [
    lambda b: b.update(valid=False),
    lambda b: b.update(token_class="different"),
    lambda b: b.update(data_origin="MEASURED_TANK"),
    lambda b: b["bounds"].update(x_max_cm=13),
    lambda b: b["sources"][0].update(id="changed"),
    lambda b: b["sources"][0].update(polygon_cm=rectangle(2, 2.1, 2, 2.1)),
    lambda b: b["traps"][0].update(validated=False),
    lambda b: b["traps"][0].update(retention="sometimes"),
    lambda b: b["traps"][0].update(polygon_cm=rectangle(7, 7.5)),
    lambda b: b["traps"][0].update(polygon_cm=rectangle(6, 7)),
    lambda b: b["traps"][0].update(polygon_cm=rectangle(1, 1.5)),
    lambda b: b["transport"].update(diffusivity_cm2_s=float("nan")),
    lambda b: b["transport"].update(dt_s=True),
    lambda b: b.update(gates=[]),
    lambda b: b.update(flow=[]),
    lambda b: b["sensitivity_variants"].append({"id": "unmatched", "transport": {}}),
    lambda b: b["sensitivity_variants"].extend([
        {"id": "two", "transport": {}}, {"id": "three", "transport": {}}]),
])
def test_incompatible_or_malformed_layouts_are_rejected(edit):
    a, b = profiles()
    edit(b)
    with pytest.raises(ValueError):
        compare(a, b)


@pytest.mark.parametrize("zone", [
    rectangle(1, 2), rectangle(11, 13), [[0, 0], [2, 2], [0, 2], [2, 0]],
    [[0, 0], [1, 0], [2, 0]], [[0, 0], [float("inf"), 0], [0, 1]],
    [[False, 0], [2, 0], [1, 2]], [["0", 0], [2, 0], [1, 2]],
])
def test_ambiguous_or_invalid_protected_geometry_is_rejected(zone):
    a, b = profiles()
    with pytest.raises(ValueError):
        prevention.compare_layouts(a, b, zone)


@pytest.mark.parametrize("settings", [
    {"horizon_s": 0}, {"horizon_s": 21}, {"horizon_s": True},
    {"particles": 19}, {"particles": 201}, {"particles": 20.5}, {"seed": -1},
])
def test_resource_and_strict_numeric_caps(settings):
    a, b = profiles()
    with pytest.raises(ValueError):
        prevention.compare_layouts(a, b, ZONE, **settings)


def test_tiny_zone_fails_work_budget_before_allocating_simulations(monkeypatch):
    a, b = profiles()
    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("Should reject in preflight")

    monkeypatch.setattr(prevention, "simulate", forbidden)
    with pytest.raises(ValueError, match="budget"):
        prevention.compare_layouts(a, b, rectangle(7, 7.00001))
    assert not called


def test_global_work_budget_rejects_before_simulation(monkeypatch):
    a, b = profiles()
    for profile in (a, b):
        profile["transport"]["dt_s"] = 0.01
        profile["sources"].append({"id": "C", "polygon_cm": rectangle(1, 1.1, 5, 5.1)})
        profile["sensitivity_variants"].append({"id": "another", "transport": {}})
    monkeypatch.setattr(prevention, "simulate", lambda *a, **k: pytest.fail("Must preflight"))
    with pytest.raises(ValueError, match="workload"):
        prevention.compare_layouts(a, b, ZONE, horizon_s=20, particles=200)
