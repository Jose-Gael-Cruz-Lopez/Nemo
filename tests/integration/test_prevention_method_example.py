"""The real public router without constructing Runtime, dotenv or provider clients."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.api.v1.endpoints.method_validation import (
    create_method_validation_router,
)
from apps.api.reeftrace_api.services import method_validation


def client():
    app = FastAPI()
    app.include_router(create_method_validation_router(), prefix="/api/v1")
    return TestClient(app)


def test_readonly_router_has_distinct_envelope_and_deterministic_actual_replay():
    with client() as api:
        first = api.get("/api/v1/research/prevention-method-example")
        second = api.get("/api/v1/research/prevention-method-example")
        assert first.status_code == 200 and first.content == second.content
        assert first.json()["schema_version"] == "prevention_method_replay_v1"
        assert first.json()["examples_are_independent"] is False
        assert len(first.json()["examples"]) == 2
        assert api.post("/api/v1/research/prevention-method-example", json={}).status_code == 405


@pytest.mark.parametrize("failure,status", [(FileNotFoundError, 503), (PermissionError, 503), (ValueError, 409)])
def test_failure_is_safe_and_does_not_return_a_partial_example(monkeypatch, failure, status):
    def broken():
        raise failure("PRIVATE path or raw provider input must not escape")

    monkeypatch.setattr(method_validation, "run_prevention_method_example", broken)
    with client() as api:
        result = api.get("/api/v1/research/prevention-method-example")
        assert result.status_code == status
        assert "PRIVATE" not in result.text and "examples" not in result.json()
