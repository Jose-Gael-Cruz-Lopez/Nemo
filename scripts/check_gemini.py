"""Check Gemini configuration; --test sends one synthetic request."""

import argparse
import asyncio
import json

import httpx
from dotenv import load_dotenv

from apps.core.reeftrace_core.ai import ai_configured, ai_provider, gemini_completion


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    try:
        if ai_provider() != "gemini" or not ai_configured():
            raise RuntimeError("Set REEFTRACE_AI_PROVIDER=gemini, GEMINI_API_KEY and GEMINI_MODEL")
        if args.test:
            output = asyncio.run(gemini_completion([
                {"role": "user", "content": 'Return only this JSON object: {"connected": true}'}
            ]))
            if json.loads(output) != {"connected": True}:
                raise ValueError("Unexpected connection test response")
            print("Gemini connection and JSON output verified.")
        else:
            print("Gemini configured. Use --test to verify a model request.")
    except (RuntimeError, ValueError, httpx.HTTPError) as error:
        if isinstance(error, httpx.HTTPError):
            raise SystemExit("Gemini connection failed: " + type(error).__name__) from None
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()
