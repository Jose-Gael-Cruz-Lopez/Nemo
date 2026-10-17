"""Inspect a local ocean-current subset without starting a tank/source experiment."""

import argparse
import json

from .field import load_copernicus_field


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("netcdf_path")
    parser.add_argument("--u-variable", default="utotal")
    parser.add_argument("--v-variable", default="vtotal")
    parser.add_argument("--depth-index", type=int, default=0)
    parser.add_argument("--max-samples", type=int, default=250_000)
    args = parser.parse_args()
    field = load_copernicus_field(
        args.netcdf_path,
        u_variable=args.u_variable,
        v_variable=args.v_variable,
        depth_index=args.depth_index,
        max_samples=args.max_samples,
    )
    print(json.dumps(field.summary(), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
