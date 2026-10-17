"""Evaluate the shared agent on fixture-only tools through actual Gemini requests.
Never imports serial, camera acquisition, or physical action dispatch.
"""

import argparse
import asyncio
import json
from pathlib import Path

import httpx
from dotenv import load_dotenv

from apps.core.reeftrace_core.agent import investigate
from apps.core.reeftrace_core.replay import ReplayBackend
from eval.scorers import grade


async def run(path):
    results = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        # Expected labels stay outside all model messages and tool returns.
        try:
            output = await investigate(
                row["request"],
                ReplayBackend(row["fixture"]),
                {"case_id": row["fixture"]["case_id"], "role": row["fixture"]["role"]},
            )
            results.append(
                {
                    "case_id": row["fixture"]["case_id"],
                    "scores": grade(output, row["reference"]),
                    "output": output,
                    "output_error": None,
                }
            )
        except (
            ValueError,
            RuntimeError,
            KeyError,
            TypeError,
            TimeoutError,
            httpx.HTTPError,
        ) as error:
            results.append(
                {"case_id": row["fixture"]["case_id"], "output_error": type(error).__name__}
            )
    return {"hardware_enabled": False, "rows": len(results), "results": results}


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures")
    parser.add_argument("--output", default="data/runs/agent_evaluation.json")
    args = parser.parse_args()
    result = asyncio.run(run(args.fixtures))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, allow_nan=False))
    print(f"Saved {result['rows']} replay rows, including failures, to {path}")


if __name__ == "__main__":
    main()
