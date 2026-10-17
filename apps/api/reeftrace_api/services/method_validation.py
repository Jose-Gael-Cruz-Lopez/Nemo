"""Replay pinned Trace 2 synthetic examples; never manufacture a live protocol.

The legacy offline bundle/report formats stay inside this service. The distinct
public envelope does not change Trace 3's accounting-receipt import contract.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from apps.estimation.reeftrace_estimation.prevention_validation import validate_bundle

ROOT = Path(__file__).resolve().parents[4]
MAX_FIXTURE_BYTES = 150_000
MAX_RESPONSE_BYTES = 250_000
DEVELOPMENT_PROTOCOL = "development-prevention-v1"
VALIDATION_PROTOCOL = "heldout-prevention-v1"
FIXTURES = {
    "positive_control": ("tests/fixtures/prevention_validation/analysis_bundle_v1.json",
                         "89e85a50abcd182d1ba0a80140d313fd286b18babedd9a4703e93ae95570328e"),
    "unresolved": ("tests/fixtures/prevention_validation/unresolved_analysis_bundle_v1.json",
                   "4425620448332638ef5dabf75837cd59763c058348bfba1e8d8857bcdc2c94e2"),
    "expected_report": ("tests/fixtures/team_handoff/validation_report_v1.json",
                        "2f3e6dd60e68f701e32996c870d5e6e6a37c4e107d86638a38f5ee89bea8104d"),
}
LIMITATIONS = [
    "Both examples are synthetic alternative outcomes for the same frozen contract; reused trial IDs must never be pooled as independent observations.",
    "These reports do not describe the currently selected case or provide physical validation, coral benefit, significance or source-identification accuracy.",
    "The actual Trace 2 validator is rerun; its legacy formats remain separate from the current Trace 3 analysis export and split-manifest accounting receipt.",
    "Pinned content hashes establish consistency with the reviewed example, not authentic physical events or an authenticated signature.",
]
CURRENT_CASE_REQUIREMENTS = [
    "Full immutable flow/profile inputs are required to rerun the numerical model; the current redacted export deliberately omits full flow nodes.",
    "Development and validation protocols, frozen selection and session/recording inventories must be recorded before validation releases. Do not invent them at import time.",
    "The current Trace 3 split receipt checks identity and accounting only; it does not rerun this method or prove experimental independence.",
]


def _pinned_json(key):
    relative, expected = FIXTURES[key]
    with (ROOT / relative).open("rb") as stream:
        raw = stream.read(MAX_FIXTURE_BYTES + 1)
    if len(raw) > MAX_FIXTURE_BYTES or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Pinned prevention-method fixture integrity check failed")
    return json.loads(raw), {"path": relative, "sha256": expected, "bytes": len(raw)}


def run_prevention_method_example() -> dict:
    """Compute both bounded public examples without state, configuration or I/O writes."""
    loaded = {key: _pinned_json(key) for key in FIXTURES}
    examples = []
    for key in ("unresolved", "positive_control"):
        bundle, provenance = loaded[key]
        try:
            report = validate_bundle(bundle, development_protocol_id=DEVELOPMENT_PROTOCOL,
                                     validation_protocol_id=VALIDATION_PROTOCOL)
        except ValueError:
            raise ValueError("Pinned prevention-method example failed numerical validation") from None
        if report["data_origin"] != "SYNTHETIC" or report["physical_validation"] is not False:
            raise ValueError("Pinned prevention-method example has an invalid origin")
        if key == "unresolved" and report != loaded["expected_report"][0]:
            raise ValueError("Replayed prevention-method report differs from the pinned shared report")
        examples.append({"id": key,
            "label": "Source B remains unresolved" if key == "unresolved" else "Fully resolved positive control",
            "data_origin": "SYNTHETIC", "not_current_case": True,
            "physical_validation": False, "method_rerun": True,
            "provenance": {"input": provenance, "integrity_verified": True,
                "expected_report": loaded["expected_report"][1] if key == "unresolved" else None,
                "expected_report_match": True if key == "unresolved" else None},
            "report": report})
    envelope = {"schema_version": "prevention_method_replay_v1",
        "kind": "SYNTHETIC_REPLAY_EXAMPLE", "status": "COMPLETED",
        "not_current_case": True, "physical_validation": False,
        "method_rerun": True, "examples_are_independent": False,
        "protocols": {"development": DEVELOPMENT_PROTOCOL, "validation": VALIDATION_PROTOCOL},
        "examples": examples, "limitations": list(LIMITATIONS),
        "current_case_requirements": list(CURRENT_CASE_REQUIREMENTS)}
    if len(json.dumps(envelope, allow_nan=False).encode()) > MAX_RESPONSE_BYTES:
        raise ValueError("Prevention-method example exceeds its bounded response size")
    return envelope
