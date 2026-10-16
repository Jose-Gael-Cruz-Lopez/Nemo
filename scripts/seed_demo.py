"""Persist a synthetic case for the dashboard. No hardware or sponsor calls."""

import argparse

from dotenv import load_dotenv

from apps.core.reeftrace_core.contracts import CaseInput, ModelConfig
from apps.core.reeftrace_core.service import create_case, get_store, register_profile
from apps.estimation.reeftrace_estimation.demo import demo_profile, make_demo


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=["moving", "stationary", "unknown"], default="moving")
    args = parser.parse_args()
    store = get_store()
    profile = demo_profile()
    try:
        register_profile(store, profile)
    except ValueError:
        pass
    demo = make_demo(args.scenario)
    case = CaseInput(
        run_id="synthetic-" + args.scenario,
        calibration_id=profile.id,
        token_class=profile.token_class,
        mode="synthetic",
        observation_region_declared=True,
        evidence_mode="trajectory" if args.scenario == "moving" else "retained_endpoint",
        retained_trap_id="A-trap" if args.scenario == "stationary" else None,
        track=demo["track"],
    )
    result = create_case(
        store, case, ModelConfig(particles_per_source=80, dt_s=0.25, max_age_s=40, min_fit=0.005)
    )
    print("SYNTHETIC case:", result["case"]["id"])
    print("Evidence:", result["estimate"]["id"], result["estimate"]["source"])


if __name__ == "__main__":
    main()
