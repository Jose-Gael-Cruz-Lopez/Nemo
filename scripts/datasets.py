"""Explicit dataset setup. Importing the API never downloads data or trains models."""

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from apps.datasets.reeftrace_datasets.catalog import CATALOG


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("catalog")
    taco = commands.add_parser("taco")
    taco.add_argument("--image-limit", type=int, default=0)
    export = commands.add_parser("export-yolo")
    export.add_argument("--snapshot", required=True)
    export.add_argument("--output", required=True)
    export.add_argument("--seed", type=int, default=7)
    noaa = commands.add_parser("noaa")
    noaa.add_argument("--config", required=True)
    marine = commands.add_parser("copernicus")
    marine.add_argument("--config", required=True)
    marine.add_argument("--download", action="store_true", help="Default is vendor dry-run only")
    local = commands.add_parser("import-netcdf")
    local.add_argument("--file", required=True)
    local.add_argument("--dataset-id", required=True)
    local.add_argument("--dataset-version")
    args = parser.parse_args()
    if args.command == "catalog":
        result = CATALOG
    elif args.command == "taco":
        from apps.datasets.reeftrace_datasets.taco import import_taco

        result = import_taco(args.image_limit)
    elif args.command == "export-yolo":
        from apps.datasets.reeftrace_datasets.taco import export_yolo

        result = export_yolo(args.snapshot, args.output, args.seed)
    elif args.command == "noaa":
        from apps.datasets.reeftrace_datasets.noaa import import_noaa

        result = import_noaa(json.loads(Path(args.config).read_text()))
    elif args.command == "copernicus":
        from apps.datasets.reeftrace_datasets.copernicus import fetch_subset

        result = fetch_subset(json.loads(Path(args.config).read_text()), dry_run=not args.download)
    else:
        from apps.datasets.reeftrace_datasets.copernicus import import_netcdf

        result = import_netcdf(args.file, args.dataset_id, args.dataset_version)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
