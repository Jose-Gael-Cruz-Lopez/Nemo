"""Actual pinned NOAA training-only ablation through its read-only public API.

No external data, provider, model deployment, tank state or physical action is
needed. Paired deltas are recomputed from returned origin errors, not trusted.
"""

from __future__ import annotations

import json
import math
import socket
import statistics
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
from apps.ocean.reeftrace_ocean import ablation, benchmark
from apps.ocean.reeftrace_ocean.data import parse_drifter_csv

ENDPOINT = "/api/v1/research/motion-ablation"
MODEL_IDS = ["stationary", "last_drift", "mean_drift", "ridge_ar1"]


@pytest.fixture
def app(tmp_path, monkeypatch):
    for key in ("CHALK_ENABLED", "PHOTON_ENABLED", "GROK_VOICE_ENABLED"):
        monkeypatch.setenv(key, "false")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "[]")
    for key in ("CHALK_ROUTER_API_KEY", "PHOTON_API_KEY", "XAI_API_KEY"):
        monkeypatch.setenv(key, "PRIVATE-ABLATION-TEST-KEY")
    return create_app(Settings(data_dir=tmp_path / "store", local_token="PRIVATE-LOCAL-TOKEN"))


def finite_json(value):
    if isinstance(value, dict):
        for item in value.values():
            finite_json(item)
    elif isinstance(value, list):
        for item in value:
            finite_json(item)
    elif isinstance(value, float):
        assert math.isfinite(value)


def store_snapshot(runtime):
    tables = ("records", "cases", "actions", "settings", "inbox", "outbox", "transport_errors")
    with runtime.store.connection() as db:
        return {table: sorted(tuple(row) for row in db.execute(f"SELECT * FROM {table}").fetchall())
                for table in tables}


def error(report, model_id, horizon):
    return [next(model for model in origin["models"] if model["id"] == model_id)
            ["predictions"][horizon - 1]["error_m"] for origin in report["origins"]]


def test_motion_ablation_authentic_provenance_chronology_and_four_finite_models(app, tmp_path):
    with TestClient(app) as client:
        before = client.get("/api/v1/status").json()
        database = store_snapshot(app.state.runtime)
        response = client.get(ENDPOINT)
        assert response.status_code == 200, response.text
        report = response.json()
        assert response.headers["content-type"].startswith("application/json")
        assert report["schema_version"] == 1
        assert report["kind"] == "TRAINING_ONLY_MOTION_ABLATION"
        assert report["status"] == "COMPLETED"
        assert report["data_origin"] == "REAL_HISTORICAL_NOAA_DRIFTER"
        split = report["split"]
        assert split["training_count"] == 18
        assert split["min_prefix"] == 8 and split["horizons"] == 6
        assert split["prefix_counts"] == list(range(8, 13)) and split["origin_count"] == 5
        assert split["step_seconds"] == 3600
        assert split["test_data_used"] is False
        assert split["model_selection_performed"] is False
        assert report["test_data_used"] is False
        assert report["model_selection_performed"] is False
        assert report["calibrated_probability"] is False
        assert report["physical_validation"] is False
        assert report["automatic_model_promotion"] is False
        assert "selected_model" not in report and "heldout_track" not in report
        provenance = report["provenance"]
        assert provenance["sha256"] == benchmark.SAMPLE_SHA256
        assert provenance["bytes"] == 1950 and provenance["row_count"] == 24
        assert provenance["drifter_id"] == "8707978"
        assert provenance["source_url"] == benchmark.EXPECTED_PROVENANCE["source_url"]
        assert provenance["product_doi"] == "10.25921/x46c-3620"
        assert provenance["license"] == "CC-BY-4.0"
        assert provenance["integrity_verified"] is True
        assert provenance["benchmark_scope"] == "training_only_motion_ablation_without_heldout_forecast_or_scoring"
        assert report["coordinate_system"]["fit"] == "spherical_azimuthal_equidistant_east_north_metres"
        assert report["coordinate_system"]["error"] == "spherical_great_circle_metres"
        start = datetime(1987, 10, 3, tzinfo=UTC)
        assert len(report["origins"]) == 5
        for origin, prefix in zip(report["origins"], range(8, 13), strict=True):
            assert origin["prefix_count"] == prefix
            assert origin["fit_end_utc"] == (start + timedelta(hours=prefix - 1)).isoformat().replace("+00:00", "Z")
            assert [row["id"] for row in origin["models"]] == MODEL_IDS
            for model in origin["models"]:
                assert len(model["predictions"]) == 6
                for horizon, point in enumerate(model["predictions"], 1):
                    expected = start + timedelta(hours=prefix + horizon - 1)
                    assert point["horizon_hours"] == horizon
                    assert point["time_utc"] == expected.isoformat().replace("+00:00", "Z")
                    assert expected <= start + timedelta(hours=17)
                    assert point["error_m"] >= 0
        finite_json(report)
        json.dumps(report, allow_nan=False)
        assert "PRIVATE-" not in response.text
        assert str(tmp_path) not in response.text and str(benchmark.ROOT) not in response.text
        assert store_snapshot(app.state.runtime) == database
        assert client.get("/api/v1/status").json() == before
        assert before["camera"]["running"] is False
        assert before["hardware_actuation"] is False
        assert before["photon"]["enabled"] is False


def test_aggregate_and_paired_metrics_reconstruct_from_exact_same_origin_errors(app):
    with TestClient(app) as client:
        response = client.get(ENDPOINT)
        assert response.status_code == 200
        report = response.json()
    assert [model["id"] for model in report["aggregates"]] == MODEL_IDS
    for model in report["aggregates"]:
        assert len(model["per_horizon"]) == 6
        for row in model["per_horizon"]:
            errors = error(report, model["id"], row["horizon_hours"])
            assert row["count"] == 5
            assert row["mean_error_m"] == pytest.approx(math.fsum(errors) / 5)
            assert row["rmse_error_m"] == pytest.approx(math.sqrt(math.fsum(x * x for x in errors) / 5))
            assert row["median_error_m"] == pytest.approx(statistics.median(errors))
            assert row["min_error_m"] == min(errors) and row["max_error_m"] == max(errors)
    assert [row["baseline_id"] for row in report["paired_comparisons"]] == MODEL_IDS[:-1]
    for comparison in report["paired_comparisons"]:
        assert comparison["candidate_id"] == "ridge_ar1"
        assert comparison["delta_definition"] == "candidate_minus_baseline_error_m"
        assert len(comparison["per_horizon"]) == 6
        for row in comparison["per_horizon"]:
            ridge = error(report, "ridge_ar1", row["horizon_hours"])
            baseline = error(report, comparison["baseline_id"], row["horizon_hours"])
            deltas = [candidate - reference for candidate, reference in zip(ridge, baseline, strict=True)]
            assert row["count"] == 5
            assert row["mean_delta_m"] == pytest.approx(math.fsum(deltas) / 5)
            assert row["median_delta_m"] == pytest.approx(statistics.median(deltas))
            assert row["min_delta_m"] == min(deltas) and row["max_delta_m"] == max(deltas)
            assert row["candidate_lower_error_count"] == sum(delta < 0 for delta in deltas)
            assert row["equal_error_count"] == sum(delta == 0 for delta in deltas)
            assert row["candidate_higher_error_count"] == sum(delta > 0 for delta in deltas)
            assert row["skill_vs_baseline"] == pytest.approx(1 - math.fsum(ridge) / math.fsum(baseline))


def test_api_mean_drift_uses_prefix_net_metres_per_step_with_no_extra_hour_conversion(app):
    source = benchmark.ROOT / "data/public" / benchmark.SAMPLE_NAME
    records = parse_drifter_csv(source.read_text())[:18]
    frame = benchmark.SphericalLocalFrame(records[0].latitude_deg, records[0].longitude_deg)
    xy = [frame.to_xy(record.latitude_deg, record.longitude_deg) for record in records]
    with TestClient(app) as client:
        response = client.get(ENDPOINT)
        assert response.status_code == 200
        for origin in response.json()["origins"]:
            prefix = origin["prefix_count"]
            anchor = xy[prefix - 1]
            displacement_per_step = (anchor - xy[0]) / (prefix - 1)
            model = next(model for model in origin["models"] if model["id"] == "mean_drift")
            for horizon, prediction in enumerate(model["predictions"], 1):
                actual = frame.to_xy(prediction["latitude_deg"], prediction["longitude_deg"])
                expected = anchor + horizon * displacement_per_step
                assert actual.tolist() == pytest.approx(expected.tolist(), abs=1e-6)


def test_read_is_deterministic_public_and_preserves_operator_mutation_auth(app):
    with TestClient(app) as client:
        first = client.get(ENDPOINT)
        second = client.get(ENDPOINT, headers={"Authorization": "Bearer wrong"})
        assert first.status_code == second.status_code == 200
        assert first.content == second.content
        assert first.json() == second.json()
        assert client.post("/api/v1/demo/load", json={}).status_code == 401
    assert app.state.runtime.store.cases() == []


def test_research_read_never_runs_heldout_benchmark_provider_network_or_runtime_mutations(app, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Training-only research must not use heldout benchmark, providers or runtime actions")

    monkeypatch.setattr(benchmark, "run_real_data_example", forbidden)
    monkeypatch.setattr(benchmark, "benchmark_drifter_records", forbidden)
    monkeypatch.setattr(ablation, "run_real_data_example", forbidden, raising=False)
    with TestClient(app) as client:
        runtime = app.state.runtime
        before = store_snapshot(runtime)
        for name in ("put", "put_case_result", "add_case", "update_case", "stop_case", "propose"):
            monkeypatch.setattr(runtime.store, name, forbidden)
        monkeypatch.setattr(runtime.camera, "start", forbidden)
        for name in ("record", "compute", "speak_briefing", "photon_handler"):
            monkeypatch.setattr(runtime, name, forbidden)
        monkeypatch.setattr(socket.socket, "connect", forbidden)
        monkeypatch.setattr(socket, "create_connection", forbidden)
        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
        response = client.get(ENDPOINT)
        assert response.status_code == 200
        assert response.json()["test_data_used"] is False
        assert store_snapshot(runtime) == before
    assert benchmark.MODEL_IDS == ("stationary", "last_drift", "ridge_ar1")


@pytest.mark.parametrize("failure", [FileNotFoundError, PermissionError])
def test_missing_or_unreadable_motion_dataset_returns_safe_503(app, monkeypatch, failure):
    def unavailable():
        raise failure("PRIVATE-PATH /private/noaa.csv")
    monkeypatch.setattr(ablation, "run_motion_ablation", unavailable)
    with TestClient(app) as client:
        response = client.get(ENDPOINT)
        assert response.status_code == 503
        assert response.json() == {"detail": "The pinned motion dataset is unavailable locally"}
        assert "PRIVATE" not in response.text and "/private/" not in response.text


def test_corrupt_actual_csv_cannot_publish_a_plausible_motion_report(app, tmp_path, monkeypatch):
    folder = tmp_path / "corrupt-source/data/public"
    folder.mkdir(parents=True)
    source = benchmark.ROOT / "data/public" / benchmark.SAMPLE_NAME
    payload = source.read_bytes()
    corrupt = payload.replace(b"-0.0736", b"-0.0735", 1)
    assert corrupt != payload
    target = folder / benchmark.SAMPLE_NAME
    target.write_bytes(corrupt)
    target.with_suffix(".provenance.json").write_bytes(source.with_suffix(".provenance.json").read_bytes())
    monkeypatch.setattr(ablation, "ROOT", tmp_path / "corrupt-source", raising=False)
    monkeypatch.setattr(benchmark, "ROOT", tmp_path / "corrupt-source")
    with TestClient(app) as client:
        response = client.get(ENDPOINT)
        assert response.status_code == 409
        assert "hash" in response.json()["detail"].lower()
        assert "origins" not in response.json() and "paired_comparisons" not in response.json()
