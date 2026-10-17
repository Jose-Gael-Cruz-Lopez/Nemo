"""Explicit metadata-only freeze; does not acquire scientific values or score models."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from apps.ocean.reeftrace_ocean.matched_current_v2_protocol import DIRECTORY, freeze_protocol


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    print(json.dumps(freeze_protocol(args.output_dir), indent=2))


if __name__ == "__main__":
    main()
