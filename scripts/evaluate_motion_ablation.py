"""Run the pinned training-only motion ablation offline; no credentials or downloads."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apps.ocean.reeftrace_ocean.ablation import run_motion_ablation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write the full auditable training-only JSON report")
    args = parser.parse_args()
    report = run_motion_ablation()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"kind": report["kind"], "data_origin": report["data_origin"],
        "integrity_verified": report["provenance"]["integrity_verified"],
        "split": report["split"], "paired_comparisons": report["paired_comparisons"],
        "test_data_used": report["test_data_used"],
        "automatic_model_promotion": report["automatic_model_promotion"],
        "output": str(args.output) if args.output else None}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
