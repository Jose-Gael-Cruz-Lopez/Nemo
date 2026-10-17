"""The public-data demo must be real, chronological, bounded and scientifically honest."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import timedelta

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import benchmark
from apps.ocean.reeftrace_ocean.benchmark import (
    ROOT,
    SAMPLE_NAME,
    SphericalLocalFrame,
    benchmark_drifter_records,
    great_circle_distance_m,
    run_real_data_example,
)
from apps.ocean.reeftrace_ocean.data import load_drifter_csv


def records():
    return load_drifter_csv(ROOT / "data/public" / SAMPLE_NAME)


def test_real_report_verifies_bytes_and_discloses_exact_experiment():
    report = run_real_data_example()
    assert report["data_origin"] == "REAL_HISTORICAL_NOAA_DRIFTER"
    assert report["provenance"]["integrity_verified"] is True
    assert report["provenance"]["bytes"] == 1950
    assert report["provenance"]["row_count"] == 24
    assert report["provenance"]["sha256"] == benchmark.SAMPLE_SHA256
    assert report["provenance"]["license"] == "CC-BY-4.0"
    assert report["split"]["training_count"] == 18
    assert report["split"]["heldout_count"] == 6
    assert report["training_track"][-1]["time_utc"] == "1987-10-03T17:00:00Z"
    assert report["heldout_track"][0]["time_utc"] == "1987-10-03T18:00:00Z"
    assert report["source_attribution"]["status"] == "NOT_SUPPORTED_BY_THIS_DATASET"
    assert report["uncertainty_method"]["probability_claim"] is None
    assert len(report["models"]) == 3
    json.dumps(report, allow_nan=False)


def test_real_metrics_match_reported_predictions_and_include_worse_results():
    report = run_real_data_example()
    for model in report["models"]:
        errors = [p["error_m"] for p in model["predictions"]]
        assert model["metrics"]["mean_error_m"] == pytest.approx(np.mean(errors))
        assert model["metrics"]["rmse_error_m"] == pytest.approx(
            np.sqrt(np.mean(np.square(errors)))
        )
        assert model["metrics"]["endpoint_error_m"] == errors[-1]
        assert model["free_run_without_heldout_updates"] is True
        assert model["metrics"]["uncertainty_is_calibrated"] is False
        assert [r["training_hindcast_count"] for r in model["training_error_radii"]] == [
            10,
            9,
            8,
            7,
            6,
            5,
        ]
    persistence, last_drift, learned = report["models"]
    # Pin the behavior, not an artificially favorable summary: learned mean
    # error is lower on this day, but its final error is WORSE than stationary.
    assert persistence["metrics"]["mean_error_m"] == pytest.approx(3855.003585, abs=0.01)
    assert last_drift["metrics"]["mae_skill_vs_stationary"] < 0
    assert learned["metrics"]["mean_error_m"] < persistence["metrics"]["mean_error_m"]
    assert learned["metrics"]["endpoint_error_m"] > persistence["metrics"]["endpoint_error_m"]


def test_no_heldout_position_or_velocity_leaks_into_predictions_or_radii():
    original = records()
    changed = [
        replace(r, latitude_deg=r.latitude_deg + 0.08, longitude_deg=r.longitude_deg - 0.04)
        if i >= 18
        else r
        for i, r in enumerate(original)
    ]
    changed = [
        replace(
            r,
            eastward_m_s=1000 + i,
            northward_m_s=-999 - i,
            eastward_uncertainty_m_s=500,
            northward_uncertainty_m_s=500,
        )
        for i, r in enumerate(changed)
    ]
    baseline = benchmark_drifter_records(original)
    alternative = benchmark_drifter_records(changed)
    for first, second in zip(baseline["models"], alternative["models"], strict=True):
        assert first["parameters"] == second["parameters"]
        assert first["training_error_radii"] == second["training_error_radii"]
        for a, b in zip(first["predictions"], second["predictions"], strict=True):
            assert a["latitude_deg"] == b["latitude_deg"]
            assert a["longitude_deg"] == b["longitude_deg"]
        assert first["metrics"]["mean_error_m"] != second["metrics"]["mean_error_m"]


@pytest.mark.parametrize(
    ("origin", "location"),
    [((46.4, -137.7), (46.46, -137.62)), ((0, 179.9), (0.1, -179.9)), ((89.9, 20), (89.9, 50))],
)
def test_spherical_log_exp_roundtrip_handles_dateline_and_near_pole(origin, location):
    frame = SphericalLocalFrame(*origin)
    xy = frame.to_xy(*location)
    reconstructed = frame.to_latlon(xy)
    assert great_circle_distance_m(location, reconstructed) < 1e-5
    assert np.linalg.norm(xy) == pytest.approx(great_circle_distance_m(origin, location))


def test_spherical_geometry_units_and_bounds():
    assert great_circle_distance_m((0, 0), (0, 1)) == pytest.approx(111_195.08023, abs=0.01)
    frame = SphericalLocalFrame(0, 0)
    assert frame.to_xy(0, 0).tolist() == [0, 0]
    assert frame.to_latlon(np.zeros(2)) == (0, 0)
    assert frame.to_xy(0, 0.1)[0] == pytest.approx(11_119.50802, abs=0.01)
    assert frame.to_xy(0.1, 0)[1] == pytest.approx(11_119.50802, abs=0.01)
    with pytest.raises(ValueError, match="50 km"):
        frame.to_xy(1, 0)
    with pytest.raises(ValueError, match="50 km"):
        frame.to_latlon(np.array([50_001, 0]))
    with pytest.raises(ValueError, match="Finite"):
        frame.to_xy(float("nan"), 0)
    with pytest.raises(ValueError, match="limits"):
        frame.to_xy(91, 0)


def test_constant_drift_learned_model_preserves_motion_without_future_data():
    base = records()[0]
    frame = SphericalLocalFrame(base.latitude_deg, base.longitude_deg)
    straight = []
    for i in range(24):
        lat, lon = frame.to_latlon(np.array([i * 100, i * 200]))
        straight.append(
            replace(
                base,
                time_utc=base.time_utc + timedelta(hours=i),
                latitude_deg=lat,
                longitude_deg=lon,
            )
        )
    result = benchmark_drifter_records(straight)
    assert result["models"][1]["metrics"]["mean_error_m"] < 1e-5
    assert result["models"][2]["metrics"]["mean_error_m"] < 1e-5
    assert result["models"][0]["metrics"]["mean_error_m"] > 700


def test_bad_cadence_multiple_drifters_and_excess_forecast_are_rejected():
    original = records()
    changed = original.copy()
    changed[4] = replace(changed[4], time_utc=changed[4].time_utc + timedelta(minutes=1))
    with pytest.raises(ValueError, match="hourly"):
        benchmark_drifter_records(changed)
    changed[4] = replace(original[4], drifter_id="another-buoy")
    with pytest.raises(ValueError, match="one drifter"):
        benchmark_drifter_records(changed)
    with pytest.raises(ValueError, match="training"):
        benchmark_drifter_records(original, train_count=8)
    with pytest.raises(ValueError, match="12 heldout"):
        benchmark_drifter_records(original, train_count=9)


def test_pinned_hash_protects_actual_data_even_if_manifest_is_changed(tmp_path, monkeypatch):
    target = tmp_path / "data/public"
    target.mkdir(parents=True)
    original = ROOT / "data/public" / SAMPLE_NAME
    payload = original.read_bytes().replace(b"-0.0736", b"-0.0735", 1)
    (target / SAMPLE_NAME).write_bytes(payload)
    manifest = json.loads(original.with_suffix(".provenance.json").read_text())
    import hashlib

    manifest["sha256"] = hashlib.sha256(payload).hexdigest()
    (target / SAMPLE_NAME).with_suffix(".provenance.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(benchmark, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="hash"):
        run_real_data_example()


def test_source_and_rights_provenance_cannot_be_replaced_by_unreviewed_links(tmp_path, monkeypatch):
    target = tmp_path / "data/public"
    target.mkdir(parents=True)
    original = ROOT / "data/public" / SAMPLE_NAME
    (target / SAMPLE_NAME).write_bytes(original.read_bytes())
    manifest = json.loads(original.with_suffix(".provenance.json").read_text())
    manifest["source_url"] = "https://example.com/not-noaa"
    (target / SAMPLE_NAME).with_suffix(".provenance.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(benchmark, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="official-source"):
        run_real_data_example()
