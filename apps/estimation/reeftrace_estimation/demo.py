"""Version 3 forward-only synthetic sandbox; never a measured tank result."""

from apps.core.reeftrace_core.contracts import CaseInput, ModelConfig, Profile
from apps.core.reeftrace_core.engine import estimate as forward_estimate

SOURCES = {"A": (3.0, 8.0), "B": (3.0, 20.0), "C": (3.0, 32.0)}


def classify(track):
    if len(track) < 5 or track[-1]["t"] - track[0]["t"] < 2:
        return "uncertain"
    # Evidence survives later stopping. Route from the entire history.
    displacement = max(
        ((p["x"] - track[0]["x"]) ** 2 + (p["y"] - track[0]["y"]) ** 2) ** 0.5 for p in track
    )
    return "moving" if displacement > 1 else "stationary"


def demo_profile():
    return Profile.model_validate(
        {
            "id": "SYNTHETIC-v3",
            "width_cm": 60,
            "height_cm": 40,
            "water_depth_cm": 12,
            "token_class": "synthetic-token",
            "pump_setting": "synthetic-uniform",
            "synthetic": True,
            "sources": [
                {"id": s, "polygon_cm": [[2, y - 1], [4, y - 1], [4, y + 1], [2, y + 1]]}
                for s, (_, y) in SOURCES.items()
            ],
            "traps": [
                {
                    "id": s + "-trap",
                    "polygon_cm": [[29, y - 2], [32, y - 2], [32, y + 2], [29, y + 2]],
                    "retention_verified": True,
                }
                for s, (_, y) in SOURCES.items()
            ],
            "observation_polygon_cm": [[10, 0], [60, 0], [60, 40], [10, 40]],
            "flow": {
                "nx": 6,
                "ny": 4,
                "velocity_cm_s": [[[1, 0]] * 6 for _ in range(4)],
                "counts": [[10] * 6 for _ in range(4)],
                "dispersion_cm_s": [[0.1] * 6 for _ in range(4)],
            },
        }
    )


def make_demo(scenario):
    if scenario == "moving":
        track = [{"t": i * 0.5, "x": 15 + i * 0.5, "y": 20.0} for i in range(13)]
    else:
        track = [
            {"t": i * 0.5, "x": 29.0, "y": 8.0 if scenario == "stationary" else 38.0}
            for i in range(13)
        ]
    if scenario != "moving":
        track = track[-1:]
    case = CaseInput(
        run_id="synthetic-" + scenario,
        calibration_id="SYNTHETIC-v3",
        token_class="synthetic-token",
        mode="synthetic",
        evidence_mode="trajectory" if scenario == "moving" else "retained_endpoint",
        retained_trap_id="A-trap" if scenario == "stationary" else None,
        observation_region_declared=True,
        track=track,
    )
    result = forward_estimate(
        case,
        demo_profile(),
        ModelConfig(particles_per_source=80, dt_s=0.25, max_age_s=40, min_fit=0.005),
    )
    # Compatibility fields for the existing bench panel.
    result.update(
        mode="moving" if scenario == "moving" else "stationary",
        ranking=[
            {"source": s, "match": v}
            for s, v in sorted(
                result["relative_support"].items(), key=lambda item: item[1], reverse=True
            )
        ],
        reason=", ".join(result["reason_codes"])
        or "Synthetic forward ensemble support and separation passed",
    )
    return {
        "track": track,
        "estimate": result,
        "sources": [{"id": s, "x": p[0], "y": p[1]} for s, p in SOURCES.items()],
    }


def estimate(track, *, seed=7):
    case = CaseInput(
        run_id="synthetic-track",
        calibration_id="SYNTHETIC-v3",
        token_class="synthetic-token",
        mode="synthetic",
        evidence_mode="trajectory",
        observation_region_declared=True,
        track=track,
    )
    return forward_estimate(case, demo_profile(), ModelConfig(seed=seed))
