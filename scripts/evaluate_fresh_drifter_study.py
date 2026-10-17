"""Read-only offline replay of the frozen fresh NOAA study; no first scoring."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from apps.ocean.reeftrace_ocean.fresh_drifter import run_fresh_drifter_study


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_fresh_drifter_study()
    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
