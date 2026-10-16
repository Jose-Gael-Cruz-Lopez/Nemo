"""Offline scientific metrics. Truth files never enter the inference API."""

import argparse
import json
from collections import defaultdict
from pathlib import Path


def summarize(rows):
    n = len(rows)
    correct = sum(r["predicted"] == r["actual"] and r["predicted"] != "Unknown" for r in rows)
    answered = sum(r["predicted"] != "Unknown" for r in rows)
    return {
        "all": n,
        "answered": answered,
        "correct": correct,
        "wrong": answered - correct,
        "unknown": n - answered,
        "coverage": answered / n if n else None,
        "accuracy_answered": correct / answered if answered else None,
        "correct_all": correct / n if n else None,
        "wrong_all": (answered - correct) / n if n else None,
        "unknown_all": (n - answered) / n if n else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evaluator_only_jsonl")
    args = parser.parse_args()
    rows = [
        json.loads(line)
        for line in Path(args.evaluator_only_jsonl).read_text().splitlines()
        if line.strip()
    ]
    if len({r["run_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate run IDs cannot count as independent trials")
    if any(r["split"] != "test" or r["mode"] == "synthetic" for r in rows):
        raise ValueError("Final metrics require frozen physical test records")
    groups = defaultdict(list)
    by_source = defaultdict(list)
    for row in rows:
        groups[row["evidence_mode"]].append(row)
        by_source[row["actual"]].append(row)
    print(
        json.dumps(
            {
                "overall": summarize(rows),
                "per_mode": {k: summarize(v) for k, v in groups.items()},
                "per_source": {k: summarize(v) for k, v in by_source.items()},
                "limitations": "Counts are not calibrated probabilities",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
