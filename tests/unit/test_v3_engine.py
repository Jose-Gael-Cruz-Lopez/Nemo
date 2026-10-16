import numpy as np

from apps.core.reeftrace_core.contracts import CaseInput, ModelConfig
from apps.core.reeftrace_core.engine import estimate, segment_intersections, simulate
from apps.estimation.reeftrace_estimation.demo import demo_profile


def case(mode="trajectory", track=None):
    return CaseInput(
        run_id="test",
        calibration_id="SYNTHETIC-v3",
        token_class="synthetic-token",
        mode="synthetic",
        evidence_mode=mode,
        observation_region_declared=True,
        retained_trap_id="A-trap" if mode == "retained_endpoint" else None,
        track=track or [{"t": i * 0.5, "x": 15 + i * 0.5, "y": 20.0} for i in range(9)],
    )


def config():
    return ModelConfig(
        particles_per_source=20,
        dt_s=0.5,
        max_age_s=40,
        min_fit=0.001,
        diffusion_cm2_s=0,
        drift_bound_cm_s=0,
    )


def test_forward_trajectory_retains_history_after_stop():
    track = [{"t": i * 0.5, "x": 25 + min(i * 0.5, 4), "y": 20.0} for i in range(17)]
    result = estimate(case(track=track), demo_profile(), config())
    assert result["inference_mode"] == "trajectory"
    assert result["source"] == "B"
    assert result["confidence_kind"] == "relative_support_not_probability"


def test_endpoint_requires_verified_retention_and_does_not_count_passage():
    profile = demo_profile()
    endpoint = case("retained_endpoint", [{"t": 0, "x": 29, "y": 8}])
    assert estimate(endpoint, profile, config())["source"] == "A"
    profile.traps[0].retention_verified = False
    assert "RETENTION_UNVERIFIED" in estimate(endpoint, profile, config())["reason_codes"]


def test_coverage_profile_and_gap_gates():
    profile = demo_profile()
    profile.flow.counts = [[0] * 6 for _ in range(4)]
    assert "CALIBRATION_INVALID" in estimate(case(), profile, config())["reason_codes"]
    profile = demo_profile()
    profile.validity = "invalid"
    assert estimate(case(), profile, config())["source"] == "Unknown"
    broken = case()
    broken.track[4].observed = False
    assert "TRACK_GAP" in estimate(broken, demo_profile(), config())["reason_codes"]


def test_release_region_hidden_and_no_truth_contract():
    import pytest
    from pydantic import ValidationError

    values = case().model_dump()
    values["actual_source"] = "A"
    with pytest.raises(ValidationError):
        CaseInput.model_validate(values)
    observed = case()
    observed.track[0].x = 3
    assert (
        "OBSERVATION_REGION_VIOLATION"
        in estimate(observed, demo_profile(), config())["reason_codes"]
    )


def test_exact_segment_intersection_and_seeded_simulation():
    t = segment_intersections(
        np.array([[0.0, 0.0]]), np.array([[10.0, 0.0]]), [(4, -1), (4.01, -1), (4.01, 1), (4, 1)]
    )
    assert np.allclose(t, [0.4])
    profile = demo_profile()
    first = simulate(profile, config(), profile.sources[0])
    second = simulate(profile, config(), profile.sources[0])
    assert np.allclose(first[0], second[0], equal_nan=True)
    assert np.array_equal(first[1], second[1])
    valid = first[0][np.isfinite(first[0][:, :, 0])]
    assert valid[:, 0].max() <= 29.000001
