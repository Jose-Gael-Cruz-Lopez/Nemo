"""Build a measured coarse-cell drift profile from timestamped marker recordings."""

import argparse
import json
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site", required=True, help="Profile template JSON with measured geometry"
    )
    parser.add_argument("--tracks", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--nx", type=int, default=6)
    parser.add_argument("--ny", type=int, default=4)
    parser.add_argument("--min-samples", type=int, default=3)
    args = parser.parse_args()
    if not 2 <= args.nx <= 40 or not 2 <= args.ny <= 40 or args.min_samples < 1:
        raise ValueError("Invalid grid settings")
    site = json.loads(Path(args.site).read_text())
    width, height = site["width_cm"], site["height_cm"]
    bins = [[[] for _ in range(args.nx)] for _ in range(args.ny)]
    for path in args.tracks:
        record = json.loads(Path(path).read_text())
        if (
            record.get("calibration_id") != site["id"]
            or record.get("purpose") != "flow_measurement"
        ):
            raise ValueError("Use flow_measurement recordings from the same calibration")
        for a, b in zip(record["track"], record["track"][1:]):
            dt = b["t"] - a["t"]
            if not (a.get("observed", True) and b.get("observed", True)) or not 0 < dt <= 0.6:
                continue
            if (
                min(a.get("quality", 1), b.get("quality", 1)) < 0.7
                or a.get("collision", False)
                or b.get("collision", False)
            ):
                continue
            x, y = (a["x"] + b["x"]) / 2, (a["y"] + b["y"]) / 2
            if not (0 <= x < width and 0 <= y < height):
                continue
            velocity = [(b["x"] - a["x"]) / dt, (b["y"] - a["y"]) / dt]
            if np.isfinite(velocity).all():
                bins[int(y / height * args.ny)][int(x / width * args.nx)].append(velocity)
    field, counts, dispersion = [], [], []
    for row in bins:
        field.append([])
        counts.append([])
        dispersion.append([])
        for samples in row:
            median = np.median(samples, axis=0) if samples else np.array([0.0, 0.0])
            field[-1].append(median.tolist())
            counts[-1].append(len(samples))
            dispersion[-1].append(
                float(np.median(np.linalg.norm(np.asarray(samples) - median, axis=1)))
                if samples
                else 0.0
            )
    site["flow"] = {
        "nx": args.nx,
        "ny": args.ny,
        "velocity_cm_s": field,
        "counts": counts,
        "dispersion_cm_s": dispersion,
        "min_samples": args.min_samples,
    }
    site["validity"] = "development"
    from apps.core.reeftrace_core.contracts import Profile

    profile = Profile.model_validate(site)
    Path(args.output).write_text(profile.model_dump_json(indent=2))
    coverage = sum(v >= args.min_samples for row in counts for v in row) / (args.nx * args.ny)
    print(
        f"Saved development profile; supported grid fraction {coverage:.3f}. Validate before real inference."
    )


if __name__ == "__main__":
    main()
