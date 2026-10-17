"""Offline pinned replay and tamper checks, never acquisition or model tuning."""

from __future__ import annotations

import hashlib
import json
import shutil
import socket
from pathlib import Path

import cv2
import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import fresh_drifter as f
from apps.ocean.reeftrace_ocean.fresh_drifter_protocol import pinned_json, sha


def copy_study(tmp_path):
    destination = tmp_path / "fresh"
    shutil.copytree(f.DIRECTORY, destination)
    return destination


def rewrite(directory, name, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    (directory / (name + ".json")).write_bytes(raw)
    (directory / (name + ".sha256")).write_text(hashlib.sha256(raw).hexdigest() + "\n")


def test_frozen_actual_new_id_cohort_replays_with_full_denominators_and_no_generalization_overclaim():
    r = f.run_fresh_drifter_study()
    assert r == f.run_fresh_drifter_study()
    assert r["study_id"] == "noaa-fresh-gdp-id-study-v2"
    assert r["status"] == "COMPLETED" and r["coverage"]["scored_outcomes"] == 180
    assert r["coverage"]["failed_outcomes"] == r["coverage"]["unfilled_outcomes"] == 0
    assert (
        r["coverage"]["unique_observed_intervals"]
        == r["coverage"]["unique_observed_positions"]
        == 36
    )
    assert r["replay"]["verified_numeric_replay"] is True
    assert (
        r["provenance"]["hashes"]["reference_report_sha256"]
        == r["replay"]["reference_report_sha256"]
    )
    reserved = set(r["provenance"]["reserved_gdp_ids"])
    assert len(reserved) == 223
    assert not reserved & {g["drifter_id"] for g in r["groups"]}
    assert len({g["wmo"] for g in r["groups"]}) == 6
    aliases = r["provenance"]["aliases"]
    assert (
        aliases["unresolved_reserved_alias_count"]
        == len(aliases["unresolved_reserved_alias_ids"])
        == 10
    )
    for name in (
        "physical_validation",
        "calibrated_probability",
        "automatic_model_promotion",
        "operational_causality",
        "statistical_independence",
        "physical_alias_resolution_verified",
        "provider_calls",
        "camera_started",
        "store_written",
        "global_training",
        "heldout_tuning",
    ):
        assert r["flags"][name] is False
    assert all(
        r["flags"][k] is True
        for k in ("acquisition_attempted", "new_acquisition", "new_gdp_id_group_evaluation")
    )
    metrics = {m["id"]: m["metrics"] for m in r["models"]}
    # Do not erase the inconvenience that simple last drift wins this fixed study.
    assert (
        metrics["last_drift"]["ade_m"]
        < metrics["kalman_cv"]["ade_m"]
        < metrics["ridge_ar1"]["ade_m"]
    )
    assert r["protocol"]["pre_outcome_amendment"]["parent_trajectory_payloads"] == 0


def test_acquisition_selection_implementation_and_forecast_receipts_precede_truth_report():
    p, _, hashes, s, m, _ = f._inputs(f.DIRECTORY)
    receipt, _ = pinned_json(f.DIRECTORY, "implementation-receipt")
    forecast, _ = pinned_json(f.DIRECTORY, "forecast-receipt")
    assert f._when(p["frozen_at_utc"]) <= f._when(m["started_at_utc"])
    assert all(
        f._when(t["started_at_utc"]) >= f._when(s["frozen_at_utc"]) for t in m["trajectories"]
    )
    assert f._when(receipt["frozen_at_utc"]) <= f._when(forecast["frozen_at_utc"])
    assert (
        receipt["evaluation_outcomes_computed"] is False
        and forecast["future_coordinates_accessed"] is False
    )
    assert forecast["declared_model_tracks"] == forecast["selected_model_tracks"] == 30
    assert forecast["unfilled_model_tracks"] == 0 and len(forecast["forecast_tracks"]) == 6
    assert forecast["manifest_sha256"] == hashes["manifest_sha256"]


def test_actual_vector_units_anchors_macro_summaries_and_observed_ellipse_hits_are_reproducible():
    r = f.run_fresh_drifter_study()
    for group in r["groups"]:
        for model in group["models"]:
            first = np.array([model["forecast_anchor"][k] for k in ("x_m", "y_m")])
            previous = first
            raw = np.array([group["training_track"][-1][k] for k in ("x_m", "y_m")])
            previous_truth = raw
            for row, actual in zip(model["predictions"], group["heldout_track"], strict=True):
                pred = np.array([row[k] for k in ("x_m", "y_m")])
                obs = np.array([actual[k] for k in ("x_m", "y_m")])
                np.testing.assert_allclose((pred - previous) / 3600, row["predicted_velocity_m_s"])
                np.testing.assert_allclose(
                    (obs - previous_truth) / 3600, row["observed_velocity_m_s"]
                )
                if model["id"] == "kalman_cv":
                    covariance = np.array(row["observation_covariance_m2"])
                    delta = pred - obs
                    score = float(delta @ np.linalg.solve(covariance, delta))
                    assert row["ellipse_hits"] == {k: score <= v for k, v in f.CHI2.items()}
                previous, previous_truth = pred, obs
    for model in r["models"]:
        tracks = [next(m for m in g["models"] if m["id"] == model["id"]) for g in r["groups"]]
        assert model["metrics"]["ade_m"] == pytest.approx(
            np.mean([t["metrics"]["ade_m"] for t in tracks])
        )
        assert model["metrics"]["fde_m"] == pytest.approx(
            np.mean([t["metrics"]["fde_m"] for t in tracks])
        )
        assert model["metrics"]["vector_rmse_m_s"] == pytest.approx(
            np.sqrt(np.mean([t["metrics"]["vector_rmse_m_s"] ** 2 for t in tracks]))
        )


def test_replay_uses_no_network_capture_provider_or_file_write(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Offline fresh replay attempted side effect")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(cv2, "VideoCapture", blocked)
    monkeypatch.setattr(Path, "write_bytes", blocked)
    monkeypatch.setattr(Path, "write_text", blocked)
    monkeypatch.setattr(Path, "mkdir", blocked)
    assert f.run_fresh_drifter_study()["replay"]["verified_numeric_replay"] is True


@pytest.mark.parametrize(
    "name",
    [
        "protocol",
        "exclusions",
        "selection",
        "manifest",
        "identity-receipt",
        "implementation-receipt",
        "forecast-receipt",
        "report",
    ],
)
def test_raw_artifact_byte_tampering_never_returns_success(tmp_path, name):
    d = copy_study(tmp_path)
    path = d / (name + ".json")
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="hash|receipt"):
        f.run_fresh_drifter_study(d)


@pytest.mark.parametrize("change", ["reserved_id", "wmo", "block", "rank"])
def test_rehashed_selection_cannot_change_metadata_selected_group_identity(tmp_path, change):
    d = copy_study(tmp_path)
    s, _ = pinned_json(d, "selection")
    m, _ = pinned_json(d, "manifest")
    if change == "reserved_id":
        s["groups"][0]["drifter_id"] = "8707978"
    elif change == "wmo":
        s["groups"][0]["wmo"] = s["groups"][1]["wmo"]
    elif change == "block":
        s["groups"][0]["block_id"] = "invented"
    else:
        s["groups"][0]["slot"] = 2
    rewrite(d, "selection", s)
    m["selection_sha256"] = sha((d / "selection.json").read_bytes())
    rewrite(d, "manifest", m)
    with pytest.raises(ValueError, match="Selection|selection"):
        f.run_fresh_drifter_study(d)


@pytest.mark.parametrize(
    "name,field,value",
    [
        ("forecast-receipt", "future_coordinates_accessed", True),
        ("forecast-receipt", "selected_model_tracks", 29),
        ("report", "status", "PARTIAL_COVERAGE"),
    ],
)
def test_rehashed_reference_cannot_change_forecasts_or_outcome_claims(tmp_path, name, field, value):
    d = copy_study(tmp_path)
    doc, _ = pinned_json(d, name)
    doc[field] = value
    rewrite(d, name, doc)
    with pytest.raises(ValueError, match="reference|identity|status"):
        f.run_fresh_drifter_study(d)


def test_missing_reference_is_unscored_not_synthetic_or_cached_success(tmp_path):
    d = copy_study(tmp_path)
    (d / "report.json").unlink()
    r = f.run_fresh_drifter_study(d)
    assert r["status"] != "COMPLETED" and r["replay"]["verified_numeric_replay"] is False
    assert r["flags"]["new_gdp_id_group_evaluation"] is False
    assert all(model["metrics"] is None for model in r["models"])


def test_frozen_evaluator_change_fails_before_prepare(tmp_path, monkeypatch):
    d = copy_study(tmp_path)
    doc, _ = pinned_json(d, "implementation-receipt")
    doc["implementation_sha256"][f.IMPLEMENTATION_PATHS[0]] = "0" * 64
    rewrite(d, "implementation-receipt", doc)

    def blocked(*args, **kwargs):
        raise AssertionError("Scored before frozen implementation verification")

    monkeypatch.setattr(f, "_prepare", blocked)
    with pytest.raises(ValueError, match="implementation changed"):
        f.run_fresh_drifter_study(d)


def test_first_score_never_overwrites_any_existing_forecast_or_result():
    with pytest.raises(ValueError, match="Never overwrite"):
        f.freeze_first_report()
