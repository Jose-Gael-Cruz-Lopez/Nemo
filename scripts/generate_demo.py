"""Generate reproducible SYNTHETIC fixtures, never physical validation evidence.

Run from the repository: .venv/bin/python scripts/generate_demo.py
Source/age labels are written only to evaluation_truth.json, outside observations.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.estimation.reeftrace_estimation import estimate
from apps.transport.reeftrace_transport import fit_flow, simulate


def generate(seed: int = 7) -> tuple[dict, list[dict], dict, list[dict]]:
    bounds = {"x_min_cm": 0, "x_max_cm": 40, "y_min_cm": 0, "y_max_cm": 30}
    # A synthetic converging marker-drift field erases source differences in a
    # downstream trap while retaining useful upstream trajectory information.
    samples = [{"x_cm": x, "y_cm": y, "vx_cm_s": 1.0, "vy_cm_s": 0.22 * (15 - y)}
               for x in range(0, 41, 5) for y in range(0, 31, 5)]
    profile = {
        "id": "SYNTHETIC-PROFILE-001", "calibration_id": "SYNTHETIC-CAL-001",
        "valid": True, "data_origin": "SYNTHETIC", "token_class": "standard-float",
        "bounds": bounds,
        "flow": fit_flow(samples, bounds, cell_size_cm=2.5, coverage_radius_cm=8,
                      data_origin="SYNTHETIC"),
        "sources": [{"id": name, "prior": 1/3,
                      "polygon_cm": [[0.9, y-0.2], [1.1, y-0.2], [1.1, y+0.2], [0.9, y+0.2]]}
                 for name, y in zip("ABC", (5, 15, 25), strict=True)],
        "traps": [{"id": "surface-trap-01", "polygon_cm": [[25, 0], [27, 0], [27, 30], [25, 30]],
                    "retention": "absorbing", "validated": True,
                    "validation_scope": "SYNTHETIC_MODEL_ONLY_NOT_PHYSICALLY_VALIDATED"}],
        "transport": {"particles_per_source": 160, "dt_s": 0.1, "max_age_s": 40,
                       "diffusivity_cm2_s": 0.002, "drift_bias_cm_s": [0.0, 0.0],
                       "age_prior": {"min_s": 0.5, "max_s": 32, "count": 32}},
        "gates": {"position_sigma_cm": 0.6, "model_error_cm": 0.2, "min_absolute_fit": 0.015},
    }
    truth_path = simulate(
        profile["flow"], profile["sources"][2]["polygon_cm"], bounds=bounds,
        traps=profile["traps"], particles=1, dt_s=0.05, horizon_s=35,
        diffusivity_cm2_s=0.002, seed=seed + 100,
    )
    times = np.arange(0, 3.01, 0.5)
    positions = truth_path.at(3 + times)[0][:, 0]
    trajectory = {
        "case_id": "SYNTHETIC-CASE-001", "profile_id": profile["id"],
        "calibration_id": profile["calibration_id"], "data_origin": "SYNTHETIC",
        "token_class": profile["token_class"], "association_valid": True,
        "points": [{"t_s": float(t), "x_cm": float(p[0]), "y_cm": float(p[1]),
                     "quality": 1.0, "observed": True} for t, p in zip(times, positions, strict=True)],
        "evidence_frame_ids": [f"synthetic-case-001-frame-{i:03}" for i in range(len(times))],
    }
    # This endpoint is from a different forward release; previous history is
    # withheld. All candidate paths converge near the same retaining boundary.
    retained_path = simulate(
        profile["flow"], profile["sources"][0]["polygon_cm"], bounds=bounds,
        traps=profile["traps"], particles=1, dt_s=0.05, horizon_s=30,
        diffusivity_cm2_s=0.002, seed=seed + 200,
    )
    endpoint_xy, held = retained_path.at(np.array([30.0]))
    if not held[0, 0]:
        raise RuntimeError("Synthetic retained fixture did not reach its modeled trap")
    endpoint = {
        "case_id": "SYNTHETIC-CASE-002", "profile_id": profile["id"],
        "calibration_id": profile["calibration_id"], "data_origin": "SYNTHETIC",
        "token_class": profile["token_class"], "points": [],
        "endpoint": {"x_cm": float(endpoint_xy[0, 0, 0]), "y_cm": float(endpoint_xy[0, 0, 1]),
                      "retained": True, "quality": 1.0},
        "evidence_frame_ids": ["synthetic-case-002-frame-000"],
    }
    invalid = copy.deepcopy(trajectory)
    invalid["case_id"] = "SYNTHETIC-CASE-003"
    invalid["calibration_id"] = "SYNTHETIC-OLD-CALIBRATION"
    observations = [trajectory, endpoint, invalid]
    truth = {
        "data_origin": "SYNTHETIC", "physical_validation": False, "seed": seed,
        "note": "Evaluator-only computational labels. Never pass this file to inference or the agent.",
        "cases": [
            {"case_id": trajectory["case_id"], "actual_source": "C", "release_age_at_first_point_s": 3,
                 "expected_status": "ranked", "expected_ranked_source": "C"},
            {"case_id": endpoint["case_id"], "actual_source": "A", "release_age_at_endpoint_s": 30,
                 "expected_status": "unknown", "expected_reason": "AMBIGUOUS_SOURCES"},
            {"case_id": invalid["case_id"], "actual_source": "C", "expected_status": "invalid",
                 "expected_reason": "CALIBRATION_INVALID"},
        ],
    }
    return profile, observations, truth, samples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "sample_runs")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    profile, observations, truth, samples = generate(args.seed)
    for filename, value in (
        ("synthetic_profile.json", profile), ("synthetic_observations.json", observations),
        ("evaluation_truth.json", truth), ("synthetic_flow_samples.json", samples),
    ):
        (args.output / filename).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    for obs in observations:
        result = estimate(profile, obs, seed=args.seed)
        print(obs["case_id"], result["status"], result["ranked_source"], result["reason_codes"])
    print("SYNTHETIC ONLY: these files do not validate tank physics or camera performance.")


if __name__ == "__main__":
    main()
