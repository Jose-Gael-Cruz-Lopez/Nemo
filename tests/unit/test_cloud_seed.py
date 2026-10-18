"""Public synthetic seed cache tests, without provider/device/ocean execution."""

import hashlib
import json
import os
import sqlite3

import cv2
import httpx
import pytest
from fastapi.testclient import TestClient

from apps.api.reeftrace_api import cloud
from deploy import seed_demo as seed


@pytest.fixture(scope="module")
def public_bundle(tmp_path_factory):
    path = tmp_path_factory.mktemp("public-seed")
    seed.build_seed(path)
    return path


@pytest.fixture
def environment(tmp_path, monkeypatch):
    for name in cloud._FORCED_ENV:
        monkeypatch.setenv(name, "TEST-INITIAL-VALUE")
    monkeypatch.setenv("REEFTRACE_DATA_DIR", str(tmp_path / "cloud"))
    monkeypatch.setenv("REEFTRACE_LOCAL_TOKEN", "SEED-TEST-OPERATOR-ONLY-1234567890")
    monkeypatch.setenv("CHALK_ENABLED", "false")
    monkeypatch.setenv("PHOTON_ENABLED", "false")
    monkeypatch.setenv("PHOTON_ROUTES_JSON", "[]")
    monkeypatch.delenv("REEFTRACE_CLOUD_SEED_DIR", raising=False)
    counters = {"provider": 0, "camera": 0, "ocean": 0}

    def forbidden(kind):
        def fail(*_args, **_kwargs):
            counters[kind] += 1
            raise AssertionError("Unexpected seed side effect: " + kind)
        return fail

    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden("provider"))
    monkeypatch.setattr(cv2, "VideoCapture", forbidden("camera"))
    from scripts import evaluate_ocean_source
    monkeypatch.setattr(evaluate_ocean_source, "first_score", forbidden("ocean"))
    yield tmp_path / "cloud"
    assert counters == {"provider": 0, "camera": 0, "ocean": 0}


def copy_bundle(source, destination):
    destination.mkdir()
    for path in source.iterdir():
        (destination / path.name).write_bytes(path.read_bytes())
    return destination


def update_db_hash(directory):
    manifest = json.loads((directory / seed.MANIFEST).read_bytes())
    raw = (directory / seed.DATABASE).read_bytes()
    manifest.update(database_bytes=len(raw), database_sha256=hashlib.sha256(raw).hexdigest())
    (directory / seed.MANIFEST).write_text(json.dumps(manifest))


def test_builder_is_fresh_provider_free_and_manifest_bound_to_shipped_public_inputs(environment, monkeypatch, tmp_path):
    import dotenv.main
    import pydantic_settings.sources.providers.dotenv

    def forbidden(*_args, **_kwargs):
        pytest.fail("Seed builder must never load .env")
    monkeypatch.setattr(dotenv.main, "find_dotenv", forbidden)
    monkeypatch.setattr(pydantic_settings.sources.providers.dotenv, "dotenv_values", forbidden)
    output = tmp_path / "build-output"
    manifest = seed.build_seed(output)
    assert manifest["summary"] == {"cases": 3, "record_counts": {"estimate": 3, "profile": 1},
        "recordings": 0, "messages": 0, "physical_evidence": False,
        "synthetic_evidence_identifiers_only": True}
    assert manifest["provider_calls"] is manifest["physical_validation"] is manifest["ocean_first_score_executed"] is False
    assert manifest["fixture_sha256"] == seed._fixture_hashes()
    assert manifest["method_sha256"] == seed._method_hashes()
    assert {path.name for path in output.iterdir()} == {seed.DATABASE, seed.MANIFEST}
    assert seed.validate_bundle(output)[0] == manifest
    assert all(path.stat().st_mode & 0o222 == 0 for path in output.iterdir())
    with pytest.raises(ValueError, match="overwrite"):
        seed.build_seed(output)


def test_default_no_seed_keeps_existing_empty_cloud_start(environment):
    app = cloud.create_cloud_app()
    assert app.state.cloud_seed_status == "DISABLED"
    with TestClient(app) as client:
        assert client.get("/api/v1/cases").json() == []


def test_first_start_imports_seed_and_demo_load_reuses_without_recomputing(environment, public_bundle, monkeypatch):
    from apps.estimation import reeftrace_estimation

    monkeypatch.setenv("REEFTRACE_CLOUD_SEED_DIR", str(public_bundle))
    app = cloud.create_cloud_app()
    assert app.state.cloud_seed_status == "IMPORTED_PUBLIC_SYNTHETIC_FIXTURES"

    def forbidden(*_args, **_kwargs):
        pytest.fail("Warm demo load unexpectedly recomputed its source particles")
    monkeypatch.setattr(reeftrace_estimation, "estimate", forbidden)
    with TestClient(app) as client:
        before = client.get("/api/v1/cases").json()
        assert len(before) == 3 and all(case["mode"] == "SYNTHETIC" for case in before)
        response = client.post("/api/v1/demo/load", headers={"Authorization": "Bearer " + os.environ["REEFTRACE_LOCAL_TOKEN"]})
        assert response.status_code == 200 and response.json()["reused_cases"] == 3
        assert {case["evidence_id"] for case in before} == {row["evidence"]["id"] for row in response.json()["cases"]}
        assert client.get("/api/v1/recordings").json() == []
        assert client.get("/api/v1/status").json()["photon"]["worker_running"] is False
    previous = (environment / seed.DATABASE).read_bytes()
    # An existing store is neither reseeded nor required to trust/read a newer bundle.
    monkeypatch.setenv("REEFTRACE_CLOUD_SEED_DIR", "/not/an/existing/seed")
    restarted = cloud.create_cloud_app()
    assert restarted.state.cloud_seed_status == "EXISTING_STORE_UNCHANGED"
    assert (environment / seed.DATABASE).read_bytes() == previous
    with TestClient(restarted) as client:
        assert len(client.get("/api/v1/cases").json()) == 3


@pytest.mark.parametrize("mutation", ["fixture_hash", "method_hash", "database_bytes", "extra_file", "db_symlink"])
def test_bundle_identity_tampering_is_rejected(public_bundle, tmp_path, mutation):
    copy = copy_bundle(public_bundle, tmp_path / "copy")
    manifest = json.loads((copy / seed.MANIFEST).read_bytes())
    if mutation == "fixture_hash":
        manifest["fixture_sha256"][seed.FIXTURE_FILES[0]] = "0" * 64
    elif mutation == "method_hash":
        manifest["method_sha256"]["deploy/seed_demo.py"] = "0" * 64
    elif mutation == "database_bytes":
        manifest["database_bytes"] += 1
    elif mutation == "extra_file":
        (copy / "private.env").write_text("not permitted")
    else:
        (copy / seed.DATABASE).unlink()
        (copy / seed.DATABASE).symlink_to(public_bundle / seed.DATABASE)
    (copy / seed.MANIFEST).write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        seed.validate_bundle(copy)


@pytest.mark.parametrize("mutation", ["message", "recording", "photon_project", "live_case", "changed_observation", "changed_profile", "physical_estimate", "trigger"])
def test_private_or_physical_records_rejected_even_if_database_hash_is_recomputed(public_bundle, tmp_path, mutation):
    copy = copy_bundle(public_bundle, tmp_path / "copy")
    with sqlite3.connect(copy / seed.DATABASE) as db:
        if mutation == "message":
            db.execute("INSERT INTO inbox(id,payload,state) VALUES('private','private','queued')")
        elif mutation == "recording":
            db.execute("INSERT INTO records VALUES('recording','private','{}',0)")
        elif mutation == "photon_project":
            db.execute("INSERT INTO settings VALUES('photon_project_id','private')")
        elif mutation in {"live_case", "changed_observation"}:
            identifier, raw = db.execute("SELECT id,payload FROM cases LIMIT 1").fetchone()
            payload = json.loads(raw)
            if mutation == "live_case":
                payload["mode"] = "LIVE"
            else:
                payload["token_class"] = "not-the-public-fixture"
            db.execute("UPDATE cases SET payload=? WHERE id=?", (json.dumps(payload), identifier))
        elif mutation in {"changed_profile", "physical_estimate"}:
            kind = "profile" if mutation == "changed_profile" else "estimate"
            identifier, raw = db.execute("SELECT id,payload FROM records WHERE kind=? LIMIT 1", (kind,)).fetchone()
            payload = json.loads(raw)
            payload["data_origin"] = "MEASURED_TANK"
            db.execute("UPDATE records SET payload=? WHERE kind=? AND id=?", (json.dumps(payload), kind, identifier))
        else:
            db.execute("CREATE TRIGGER forbidden AFTER INSERT ON settings BEGIN SELECT 1; END")
    update_db_hash(copy)
    with pytest.raises(ValueError):
        seed.validate_bundle(copy)


def test_failed_seed_does_not_create_or_replace_database(environment, public_bundle, monkeypatch, tmp_path):
    invalid = copy_bundle(public_bundle, tmp_path / "invalid")
    (invalid / seed.MANIFEST).write_text("{}")
    monkeypatch.setenv("REEFTRACE_CLOUD_SEED_DIR", str(invalid))
    with pytest.raises(RuntimeError, match="seed failed validation"):
        cloud.create_cloud_app()
    assert not (environment / seed.DATABASE).exists()
    assert {path.name for path in environment.iterdir()} == {cloud.CLOUD_MARKER}
