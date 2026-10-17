import copy
import json

import pytest

from apps.estimation.reeftrace_estimation import estimate
from apps.transport.reeftrace_transport import fit_flow

BOUNDS = {"x_min_cm": 0, "x_max_cm": 40, "y_min_cm": 0, "y_max_cm": 30}


def profile():
    samples = [{"x_cm": x, "y_cm": y, "vx_cm_s": 1, "vy_cm_s": 0}
               for x in (0, 10, 20, 30, 40) for y in (0, 10, 20, 30)]
    return {
        "id": "synthetic-profile", "calibration_id": "SYNTHETIC-CAL", "valid": True,
        "data_origin": "SYNTHETIC", "token_class": "standard-float", "bounds": BOUNDS,
        "flow": fit_flow(samples, BOUNDS, coverage_radius_cm=15, data_origin="SYNTHETIC"),
        "sources": [{"id": name, "prior": 1/3,
                      "polygon_cm": [[0.9, y-0.2], [1.1, y-0.2], [1.1, y+0.2], [0.9, y+0.2]]}
                 for name, y in zip("ABC", (5, 15, 25), strict=True)],
        "traps": [{"id": "T", "polygon_cm": [[25, 0], [27, 0], [27, 30], [25, 30]],
                    "retention": "absorbing", "validated": True}],
        "transport": {"particles_per_source": 80, "dt_s": 0.2, "max_age_s": 40,
                       "diffusivity_cm2_s": 0, "drift_bias_cm_s": [0, 0],
                       "age_prior": {"values_s": [7], "weights": [1]}},
        "gates": {"position_sigma_cm": 0.4, "model_error_cm": 0.1},
    }


def observation():
    return {"case_id": "SYNTHETIC-trajectory", "calibration_id": "SYNTHETIC-CAL",
                "token_class": "standard-float", "association_valid": True,
                "points": [{"t_s": t, "x_cm": 8+t, "y_cm": 15, "quality": 1, "observed": True}
                        for t in (0, 1, 2, 3)], "evidence_frame_ids": ["synthetic-frame-1"]}


def test_uniform_advection_informative_trajectory_ranks_correct_candidate():
    result = estimate(profile(), observation())
    assert result["status"] == "ranked", result
    assert result["ranked_source"] == "B"
    assert result["relative_support"]["B"] > 0.99
    assert sum(result["relative_support"].values()) == pytest.approx(1)
    assert result["confidence_kind"] == "relative_support_not_probability"
    assert result["physical_validation"] is False
    assert result["data_origin"] == "SYNTHETIC"
    json.dumps(result, allow_nan=False)


def test_observed_history_is_retained_when_object_is_now_stationary():
    obs = observation()
    obs["endpoint"] = {"x_cm": 25, "y_cm": 15, "retained": True}
    obs["mode"] = "retained_endpoint"  # current-speed hint cannot discard recorded history
    assert estimate(profile(), obs)["inference_mode"] == "trajectory"


def test_identical_source_geometry_cannot_be_resolved_even_with_strong_prior():
    p = profile()
    for source, prior in zip(p["sources"], (0.8, 0.1, 0.1), strict=True):
        source["polygon_cm"] = copy.deepcopy(p["sources"][1]["polygon_cm"])
        source["prior"] = prior
    result = estimate(p, observation())
    assert result["status"] == "unknown"
    assert result["ranked_source"] is None
    assert "AMBIGUOUS_SOURCES" in result["reason_codes"]
    assert result["likelihood_margin"] == pytest.approx(0)


def test_absolute_model_mismatch_cannot_be_hidden_by_normalization():
    obs = observation()
    for point in obs["points"]:
        point["x_cm"] += 20
    result = estimate(profile(), obs)
    assert result["status"] == "unknown"
    assert "MODEL_MISMATCH" in result["reason_codes"]
    assert result["absolute_fit"] < 0.02


def test_high_prior_cannot_borrow_a_different_candidates_good_absolute_fit():
    p = profile()
    # Candidate A lies close enough for a finite but poor fit. B genuinely fits.
    p["sources"][0]["polygon_cm"] = [[0.9, 16.5], [1.1, 16.5], [1.1, 16.9], [0.9, 16.9]]
    for source, prior in zip(p["sources"], (1e30, 1, 1), strict=True):
        source["prior"] = prior
    result = estimate(p, observation())
    assert result["leading_source"] == "A"
    assert result["best_absolute_fit"] > 0.9
    assert result["absolute_fit"] < 0.02
    assert result["status"] == "unknown"
    assert "MODEL_MISMATCH" in result["reason_codes"]


def test_out_of_domain_observation_and_stale_calibration_are_invalid():
    obs = observation()
    obs["points"][0]["x_cm"] = -1
    assert estimate(profile(), obs)["status"] == "invalid"
    obs = observation()
    obs["calibration_id"] = "an-old-calibration"
    result = estimate(profile(), obs)
    assert result["status"] == "invalid"
    assert "CALIBRATION_INVALID" in result["reason_codes"]


def test_insufficient_flow_coverage_returns_unknown_not_missing_source_evidence():
    p = profile()
    p["flow"]["coverage_radius_cm"] = 0.5
    result = estimate(p, observation())
    assert result["status"] == "unknown"
    assert "CALIBRATION_INVALID" in result["reason_codes"]
    assert result["coverage"] < 0.9


def test_retained_endpoint_scores_retained_population_at_observation_time():
    p = profile()
    p["transport"]["age_prior"] = {"min_s": 25, "max_s": 32, "count": 8}
    obs = {"case_id": "SYNTHETIC-retained", "calibration_id": "SYNTHETIC-CAL",
               "token_class": "standard-float", "points": [],
               "endpoint": {"x_cm": 25, "y_cm": 15, "retained": True}}
    result = estimate(p, obs)
    assert result["inference_mode"] == "retained_endpoint"
    assert result["ranked_source"] == "B", result
    assert result["source_diagnostics"]["B"]["retained_fraction"] == pytest.approx(1)
    p["transport"]["age_prior"] = {"values_s": [5], "weights": [1]}
    too_early = estimate(p, obs)
    assert too_early["status"] == "unknown"
    assert too_early["absolute_fit"] == 0
    assert "MODEL_MISMATCH" in too_early["reason_codes"]


def test_unvalidated_or_unsupported_retention_is_never_ranked():
    p = profile()
    p["transport"]["age_prior"] = {"values_s": [30], "weights": [1]}
    obs = {"case_id": "SYNTHETIC-retained", "calibration_id": "SYNTHETIC-CAL",
               "token_class": "standard-float", "points": [],
               "endpoint": {"x_cm": 25, "y_cm": 15, "retained": True}}
    p["traps"][0]["validated"] = False
    result = estimate(p, obs)
    assert "RETENTION_UNVALIDATED" in result["reason_codes"]
    assert result["status"] == "unknown"
    p["traps"] = []
    result = estimate(p, obs)
    assert "RETENTION_UNSUPPORTED" in result["reason_codes"]
    assert result["absolute_fit"] == 0  # passing the location is not retention


def test_tiny_likelihoods_remain_json_finite_and_rank_stably():
    p = profile()
    p["gates"].update(position_sigma_cm=0.0001, model_error_cm=0)
    result = estimate(p, observation())
    assert result["status"] in ("ranked", "unknown")
    json.dumps(result, allow_nan=False)
    assert sum(result["relative_support"].values()) == pytest.approx(1)


def test_age_window_is_not_silently_truncated_to_force_a_fit():
    p = profile()
    p["transport"]["age_prior"] = {"min_s": 39, "max_s": 40, "count": 8}
    result = estimate(p, observation())
    assert result["status"] == "invalid"
    assert "horizon" in result["error"]


def test_named_predeclared_sensitivity_can_revoke_a_ranked_result():
    p = profile()
    p["sensitivity_variants"] = [{"id": "different-documented-age", "transport": {
        "age_prior": {"values_s": [20], "weights": [1]},
    }}]
    result = estimate(p, observation())
    assert result["status"] == "unknown"
    assert "ASSUMPTION_SENSITIVE" in result["reason_codes"]
    assert len(result["sensitivity_results"]) == 1
    assert result["sensitivity_results"][0]["id"] == "different-documented-age"


def test_seed_and_input_order_are_reproducible_and_inputs_are_not_mutated():
    p, obs = profile(), observation()
    original = copy.deepcopy(p)
    first = estimate(p, obs, seed=22)
    second = estimate(p, obs, seed=22)
    assert first == second
    assert p == original
    p["sources"].reverse()
    reordered = estimate(p, obs, seed=22)
    assert first["relative_support"] == reordered["relative_support"]


@pytest.mark.parametrize("edit", [
    lambda p: p["sources"][0].update(prior=-1),
    lambda p: p["transport"].update(diffusivity_cm2_s=-0.1),
    lambda p: p["transport"].update(dt_s=float("nan")),
    lambda p: p["gates"].update(position_sigma_cm=0),
])
def test_invalid_numerical_configuration_is_reported(edit):
    p = profile()
    edit(p)
    result = estimate(p, observation())
    assert result["status"] == "invalid"
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("edit", [
    lambda obs: obs.update(evidence_frame_ids=None),
    lambda obs: obs.update(points=None),
    lambda obs: obs.update(points=[None]),
    lambda obs: obs["points"][0].update(quality=0),
])
def test_malformed_observation_returns_finite_invalid_report(edit):
    obs = observation()
    edit(obs)
    result = estimate(profile(), obs)
    assert result["status"] == "invalid"
    assert result["reason_codes"] == ["INVALID_INPUT"]
    json.dumps(result, allow_nan=False)


def test_synthetic_fixtures_keep_evaluator_truth_out_of_model_inputs():
    from pathlib import Path

    directory = Path(__file__).parents[2] / "data" / "sample_runs"
    p = json.loads((directory / "synthetic_profile.json").read_text())
    observations = json.loads((directory / "synthetic_observations.json").read_text())
    truth = json.loads((directory / "evaluation_truth.json").read_text())
    assert p["data_origin"] == "SYNTHETIC" and p["valid"] is True
    assert "source_id" not in json.dumps(observations)
    assert "true_source" not in json.dumps(observations)
    assert "true_release" not in json.dumps(observations)
    assert truth["data_origin"] == "SYNTHETIC"
    expected = [("ranked", "C"), ("unknown", None), ("invalid", None)]
    assert [(result["status"], result["ranked_source"])
            for result in (estimate(p, obs) for obs in observations)] == expected
