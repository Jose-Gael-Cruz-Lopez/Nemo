"""Real pinned-data replay and integrity boundaries for the isolated new diagnostic."""

from __future__ import annotations

import hashlib
import json
import shutil
import socket
from pathlib import Path

import cv2
import pytest

from apps.ocean.reeftrace_ocean import kalman_diagnostic as diagnostic
from apps.ocean.reeftrace_ocean.multidrifter import run_multidrifter_study


def copy_artifacts(tmp_path, monkeypatch):
    destination = tmp_path / "kalman"
    shutil.copytree(diagnostic.DIRECTORY, destination)
    monkeypatch.setattr(diagnostic, "DIRECTORY", destination)
    return destination


def rewrite_json(directory, name, document):
    payload = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    (directory / (name + ".json")).write_bytes(payload)
    (directory / (name + ".sha256")).write_text(hashlib.sha256(payload).hexdigest() + "\n")


def test_verified_real_replay_keeps_all_denominators_and_explicit_limits():
    report = diagnostic.run_kalman_diagnostic()
    assert report == diagnostic.run_kalman_diagnostic()
    assert report["data_origin"] == "REAL_HISTORICAL_NOAA_DRIFTERS_ALREADY_VIEWED"
    assert report["coverage"] == {
        "target_groups": 6, "acquired_groups": 4, "missing_groups": 2, "models": 5,
        "horizons": 6, "planned_outcomes": 180, "attempted_outcomes": 120,
        "scored_outcomes": 120, "failed_outcomes": 0, "unique_observed_intervals": 24,
        "common_acquired_cohort_complete": True,
    }
    assert report["parameter_fitting_scope"] == "KALMAN_NOISE_HYPERPARAMETERS_ONLY"
    assert report["parameter_fitting_performed"] is False
    assert report["test_data_used"] is True
    for flag in ("physical_validation", "calibrated_probability", "independent_evaluation",
                 "automatic_model_promotion", "new_trajectory_acquisition", "provider_calls",
                 "camera_started", "store_written"):
        assert report[flag] is False
    assert report["replay"]["verified_numeric_replay"] is True
    assert len(report["replay"]["reference_report_sha256"]) == 64
    assert report["provenance"]["integrity_verified"] is True
    assert len(report["provenance"]["sources"]) == 4
    assert all(row["sha256"] and row["bytes"] > 0 for row in report["provenance"]["sources"])
    # This candidate is worse here. Replay must not erase that inconvenient result.
    by_id = {row["id"]: row for row in report["models"]}
    assert by_id["kalman_cv"]["metrics"]["ade_m"] > by_id["ridge_ar1"]["metrics"]["ade_m"]
    assert report["uncertainty"]["per_drifter"][-1]["nominal90_hit_count"] == 1
    assert report["uncertainty"]["fraction_ranges"]["nominal90"] == {"min": 1 / 6, "max": 1.0}


def test_existing_four_baselines_and_original_artifacts_are_unchanged():
    original_directory = diagnostic.ROOT / "data/public/noaa-multidrifter-v1"
    before = {path.name: path.read_bytes() for path in original_directory.iterdir() if path.is_file()}
    original = run_multidrifter_study()
    report = diagnostic.run_kalman_diagnostic()
    after = {path.name: path.read_bytes() for path in original_directory.iterdir() if path.is_file()}
    assert before == after
    # Reconstruct the four unchanged algorithms from their original result rows.
    original_rows = original["outcomes"]
    for group in report["groups"]:
        for model in group["models"][:4]:
            rows = [row for row in original_rows if row["drifter_id"] == group["drifter_id"]
                    and row["model_id"] == model["id"]]
            assert len(rows) == 6
            for actual, prior in zip(model["predictions"], rows, strict=True):
                assert actual["position_error_m"] == prior["error_m"]


def test_replay_performs_no_network_camera_or_application_writes(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Read-only offline diagnostic attempted a side effect")
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(cv2, "VideoCapture", blocked)
    monkeypatch.setattr(Path, "write_bytes", blocked)
    monkeypatch.setattr(Path, "write_text", blocked)
    monkeypatch.setattr(Path, "mkdir", blocked)
    assert diagnostic.run_kalman_diagnostic()["status"] == "COMPLETED"


@pytest.mark.parametrize("name", ["protocol", "implementation-receipt", "report"])
def test_raw_artifact_tampering_fails_closed_even_before_schema_use(tmp_path, monkeypatch, name):
    directory = copy_artifacts(tmp_path, monkeypatch)
    path = directory / (name + ".json")
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="hash|receipt"):
        diagnostic.run_kalman_diagnostic()


def test_protocol_cannot_be_replaced_by_recomputing_its_detached_hash(tmp_path, monkeypatch):
    directory = copy_artifacts(tmp_path, monkeypatch)
    protocol = json.loads((directory / "protocol.json").read_text())
    protocol["position_std_m"] = 10
    rewrite_json(directory, "protocol", protocol)
    with pytest.raises(ValueError, match="hash|receipt"):
        diagnostic.run_kalman_diagnostic()


@pytest.mark.parametrize("change", ["implementation", "missing_module", "future_scored", "escape"])
def test_rehashed_bad_implementation_receipt_is_rejected(tmp_path, monkeypatch, change):
    directory = copy_artifacts(tmp_path, monkeypatch)
    receipt = json.loads((directory / "implementation-receipt.json").read_text())
    if change == "implementation":
        receipt["implementation_sha256"]["apps/ocean/reeftrace_ocean/kalman.py"] = "0" * 64
    elif change == "missing_module":
        del receipt["implementation_sha256"]["apps/ocean/reeftrace_ocean/kalman.py"]
    elif change == "future_scored":
        receipt["real_kalman_outcomes_computed"] = True
    else:
        receipt["implementation_sha256"]["../outside.py"] = "0" * 64
    rewrite_json(directory, "implementation-receipt", receipt)
    with pytest.raises(ValueError, match="freeze|implementation|required|reference"):
        diagnostic.run_kalman_diagnostic()


@pytest.mark.parametrize("change", ["count", "id", "float", "status", "type"])
def test_rehashed_report_cannot_promote_counts_identities_statuses_or_metrics(tmp_path, monkeypatch, change):
    directory = copy_artifacts(tmp_path, monkeypatch)
    report = json.loads((directory / "report.json").read_text())
    if change == "count":
        report["coverage"]["scored_outcomes"] -= 1
    elif change == "id":
        report["groups"][0]["drifter_id"] = "invented"
    elif change == "float":
        report["models"][4]["metrics"]["ade_m"] -= 100
    elif change == "status":
        report["independent_evaluation"] = True
    else:
        report["coverage"]["scored_outcomes"] = 120.0
    rewrite_json(directory, "report", report)
    with pytest.raises(ValueError, match="reference"):
        diagnostic.run_kalman_diagnostic()


def test_missing_reference_report_is_unavailable_not_synthetic_success(tmp_path, monkeypatch):
    directory = copy_artifacts(tmp_path, monkeypatch)
    (directory / "report.json").unlink()
    with pytest.raises(FileNotFoundError):
        diagnostic.run_kalman_diagnostic()


def test_corrupt_original_dataset_is_rejected_before_new_forecasts(monkeypatch):
    invoked = []
    def broken_inputs():
        raise ValueError("Pinned NOAA raw payload hash or byte count changed")
    def unexpected_score(*args, **kwargs):
        invoked.append(True)
        raise AssertionError("Must verify raw input before scores")
    monkeypatch.setattr(diagnostic, "load_multidrifter_inputs", broken_inputs)
    monkeypatch.setattr(diagnostic, "diagnostic_from_records", unexpected_score)
    with pytest.raises(ValueError, match="Pinned NOAA"):
        diagnostic.run_kalman_diagnostic()
    assert invoked == []
