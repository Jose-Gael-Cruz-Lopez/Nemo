"""Replay the frozen acquired NOAA cohort offline; no downloads or model tuning."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apps.ocean.reeftrace_ocean.multidrifter import run_multidrifter_study


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write the complete acquired-cohort evidence report")
    args = parser.parse_args()
    report = run_multidrifter_study()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"kind": report["kind"], "status": report["status"], "metric_scope": report["metric_scope"],
        "coverage": report["coverage"], "selection_failures": report["selection_failures"],
        "protocol": report["protocol"], "models": report["models"],
        "paired_comparisons": report["paired_comparisons"],
        "statistical_independence": report["statistical_independence"],
        "automatic_model_promotion": report["automatic_model_promotion"],
        "output": str(args.output) if args.output else None}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
