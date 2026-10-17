"""Fixed public-data replay over HTTP, with providers/capture/store writes forbidden."""

import cv2
import httpx
import pytest
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.ocean.reeftrace_ocean import kalman_diagnostic

ENDPOINT = "/api/v1/research/kalman-diagnostic"


@pytest.fixture
def app(tmp_path, monkeypatch):
    for name in ("CHALK_ENABLED", "PHOTON_ENABLED", "GROK_VOICE_ENABLED"):
        monkeypatch.setenv(name, "false")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "[]")
    return create_app(Settings(data_dir=tmp_path / "isolated", local_token="PRIVATE-TEST-ONLY"))


def test_read_only_kalman_replay_matches_local_report(app, monkeypatch):
    expected = kalman_diagnostic.run_kalman_diagnostic()
    runtime = app.state.runtime

    def forbidden(*_args, **_kwargs):
        raise AssertionError("The public Kalman replay crossed its read-only boundary")

    with TestClient(app) as client:
        with runtime.store.connection() as db:
            before = tuple(db.iterdump())
        for method in ("put", "put_case_result", "add_case", "update_case", "propose", "transition_action"):
            monkeypatch.setattr(runtime.store, method, forbidden)
        monkeypatch.setattr(cv2, "VideoCapture", forbidden)
        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
        response = client.get(ENDPOINT)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == expected
        assert expected["kind"] == "FIXED_KALMAN_MOTION_DIAGNOSTIC"
        assert "PRIVATE-TEST-ONLY" not in response.text
        with runtime.store.connection() as db:
            assert tuple(db.iterdump()) == before


@pytest.mark.parametrize("error,code", [(FileNotFoundError("PRIVATE-PATH"), 503),
                                        (ValueError("PRIVATE-INTEGRITY-DETAIL"), 409),
                                        (TypeError("PRIVATE-INVALID-SHAPE"), 409)])
def test_missing_or_invalid_artifact_fails_without_leaking_details(app, monkeypatch, error, code):
    def fail():
        raise error

    monkeypatch.setattr(kalman_diagnostic, "run_kalman_diagnostic", fail)
    with TestClient(app) as client:
        response = client.get(ENDPOINT)
    assert response.status_code == code
    assert response.headers["cache-control"] == "no-store"
    assert "PRIVATE-" not in response.text
