"""Explicit cloud deployment definitions. Do not import from the application.

Import only via `python -m adapters.chalk.evaluate --mode remote`. Chalk's
decorator starts deployment at import time. This module never imports hardware.
"""

import asyncio
import json
import os

import chalkcompute

from .agent import ChalkSettings, investigate
from .evaluate import ReplayBackend, policy_scores

IMAGE = (
    chalkcompute.Image.debian_slim("3.12")
    .pip_install(["httpx>=0.28,<1"])
    .add_local_python_source("adapters")
    .env(
        {
            "CHALK_ROUTER_BASE_URL": os.getenv(
                "CHALK_ROUTER_BASE_URL", "https://api.chalk.ai/v1/router"
            )
        }
    )
)
SECRETS = [
    chalkcompute.Secret.from_local_env(name)
    for name in ("CHALK_ROUTER_API_KEY", "CHALK_ENV_ID", "CHALK_MODEL")
]


@chalkcompute.function(image=IMAGE, secrets=SECRETS, call_timeout=90)
def reeftrace_task(fixture_json: str, request: str) -> str:
    fixture = json.loads(fixture_json)
    settings = ChalkSettings(
        True,
        os.getenv("CHALK_ROUTER_BASE_URL", "https://api.chalk.ai/v1/router"),
        os.environ["CHALK_ROUTER_API_KEY"],
        os.environ["CHALK_ENV_ID"],
        os.environ["CHALK_MODEL"],
    )
    result = asyncio.run(
        investigate(
            request,
            ReplayBackend(fixture),
            {
                "case_id": fixture["case"]["case_id"],
                "role": fixture["role"],
                "execution_mode": "FROZEN_FIXTURE_NO_HARDWARE",
            },
            settings,
        )
    )
    return json.dumps(result, allow_nan=False)


@chalkcompute.function(image=IMAGE)
def action_correct(output: str, allowed_actions_json: str) -> float:
    return policy_scores(output, allowed_actions_json, "[]", "[]", "[]")["action_correct"]


@chalkcompute.function(image=IMAGE)
def tool_policy(output: str, required_tools_json: str, forbidden_tools_json: str) -> float:
    return policy_scores(output, "[]", required_tools_json, forbidden_tools_json, "[]")[
        "tool_policy"
    ]


@chalkcompute.function(image=IMAGE)
def evidence_grounded(output: str, required_evidence_json: str) -> float:
    return policy_scores(output, "[]", "[]", "[]", required_evidence_json)["evidence_grounded"]


@chalkcompute.function(image=IMAGE)
def numerical_authority(output: str) -> float:
    return policy_scores(output, "[]", "[]", "[]", "[]")["numerical_authority"]


@chalkcompute.function(image=IMAGE)
def source_status_preserved(output: str) -> float:
    return policy_scores(output, "[]", "[]", "[]", "[]")["source_status_preserved"]


@chalkcompute.function(image=IMAGE)
def model_response_valid(output: str) -> float:
    return policy_scores(output, "[]", "[]", "[]", "[]")["model_response_valid"]


# Every deployed function imports this module: the built-in scorer needs IMAGE too.
valid_json = chalkcompute.scorers.json_valid(name="valid-json", image=IMAGE)
