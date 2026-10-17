"""Evaluate the pinned authentic NOAA drifter sample offline; no credentials needed."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apps.ocean.reeftrace_ocean.benchmark import run_real_data_example


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write the complete auditable JSON report")
    args = parser.parse_args()
    report = run_real_data_example()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "data_origin": report["data_origin"],
                "sha256_verified": report["provenance"]["integrity_verified"],
                "split": report["split"],
                "models": [{"id": m["id"], **m["metrics"]} for m in report["models"]],
                "source_attribution": report["source_attribution"],
                "output": str(args.output) if args.output else None,
            },
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
