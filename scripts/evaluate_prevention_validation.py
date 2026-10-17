"""Validate one bounded local prevention JSON bundle without accounts or hardware."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from apps.estimation.reeftrace_estimation.prevention_validation import (
    MAX_BYTES,
    canonical_json,
    validate_bundle,
)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("Non-finite JSON constant")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--development-protocol", required=True)
    parser.add_argument("--validation-protocol", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    temporary = None
    try:
        if args.bundle.suffix.lower() != ".json" or not args.bundle.is_file():
            raise ValueError("Input must be a local .json bundle file")
        if args.bundle.resolve() == args.output.resolve():
            raise ValueError("Output must not replace the input bundle")
        with args.bundle.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Bundle byte budget exceeded")
        bundle = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
        report = validate_bundle(bundle, development_protocol_id=args.development_protocol,
                                 validation_protocol_id=args.validation_protocol)
        encoded = (canonical_json(report) + "\n").encode()
        if len(encoded) > MAX_BYTES:
            raise ValueError("Report byte budget exceeded")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=args.output.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
        os.replace(temporary, args.output)
        temporary = None
        print("Validation report:", report["id"])
        print("Next measurement:", report["next_measurement"]["kind"])
        return 0
    except (ValueError, OSError, RecursionError) as error:
        parser.exit(2, "Validation failed: " + str(error) + "\n")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
