"""Verify Chalk credentials and list permitted models, or explicitly test a model."""

import argparse
import os

import httpx
from dotenv import load_dotenv


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true", help="Send one small model request")
    args = parser.parse_args()
    required = ["CHALK_ROUTER_API_KEY", "CHALK_ENV_ID"]
    if args.test:
        required.append("CHALK_MODEL")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise SystemExit("Set these in .env first: " + ", ".join(missing))
    base = (os.environ.get("CHALK_ROUTER_BASE_URL") or "https://api.chalk.ai/v1/router").rstrip("/")
    headers = {
        "Authorization": "Bearer " + os.environ["CHALK_ROUTER_API_KEY"],
        "X-Chalk-Env-Id": os.environ["CHALK_ENV_ID"],
    }
    try:
        with httpx.Client(timeout=30) as client:
            if args.test:
                response = client.post(
                    base + "/chat/completions",
                    headers=headers,
                    json={
                        "model": os.environ["CHALK_MODEL"],
                        "messages": [
                            {
                                "role": "user",
                                "content": "Reply with exactly: ReefTrace gateway connected",
                            }
                        ],
                    },
                )
            else:
                response = client.get(base + "/models", headers=headers)
            if response.status_code >= 400:
                raise SystemExit(
                    f"Chalk returned HTTP {response.status_code}. Check router key, environment, model access and provider connection; credentials were not printed."
                )
            payload = response.json()
            if args.test:
                print("Model request succeeded:", payload["choices"][0]["message"]["content"])
            else:
                models = [model["id"] for model in payload.get("data", [])]
                print("Gateway reachable. Models available to this key:")
                print(
                    "\n".join(models)
                    if models
                    else "(none; configure a provider connection or model permissions)"
                )
    except httpx.HTTPError as error:
        raise SystemExit("Gateway connection failed: " + type(error).__name__) from None


if __name__ == "__main__":
    main()
