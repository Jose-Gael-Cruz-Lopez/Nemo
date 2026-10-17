"""List Butterbase models, check setup, or explicitly send one small model request."""

import argparse
import asyncio

import httpx
from dotenv import load_dotenv

from apps.core.reeftrace_core.butterbase import (
    ButterbaseConfig,
    butterbase_completion,
    checked_json,
)


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--public",
        action="store_true",
        help="Public catalog; no API key needed; does not verify access or credits",
    )
    group.add_argument(
        "--test",
        action="store_true",
        help="Send one small model request using your account credits",
    )
    args = parser.parse_args()
    try:
        config = ButterbaseConfig.from_env(require_key=not args.public, require_model=args.test)
        if args.test:
            output = asyncio.run(
                butterbase_completion(
                    [{"role": "user", "content": "Reply with exactly: ReefTrace gateway connected"}]
                )
            )
            print("Model request succeeded:", output)
            return
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            path = "public/models" if args.public else "models"
            response = client.get(
                config.endpoint(path), headers={} if args.public else config.headers()
            )
            payload = checked_json(response)
        models = payload.get("models" if args.public else "data", [])
        print(
            "Public catalog (account access unverified):"
            if args.public
            else "Models returned for your Butterbase key:"
        )
        for model in models:
            print(model["id"])
        if not models:
            print("(none; check account access and key scope)")
    except (RuntimeError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(str(error)) from None
    except httpx.HTTPError as error:
        raise SystemExit("Butterbase connection failed: " + type(error).__name__) from None


if __name__ == "__main__":
    main()
