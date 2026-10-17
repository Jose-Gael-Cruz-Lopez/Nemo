"""Synthetic full-matrix scientific checks; no actual new NOAA scores here."""

from __future__ import annotations

import csv
import io
from datetime import timedelta

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import fresh_drifter as f
from apps.ocean.reeftrace_ocean.benchmark import SphericalLocalFrame
from apps.ocean.reeftrace_ocean.fresh_drifter_protocol import MODEL_IDS, load_design


def invented_inputs():
    p, e, h = load_design()
    groups = []
    trajectories = []
    sources = {}
    for index, block in enumerate(p["selection"]["blocks"]):
        for slot in (1, 2):
            k = index * 2 + slot
            identifier = str(900000000000000 + k)
            g = {
                "drifter_id": identifier,
                "wmo": str(8000000 + k),
                "block_id": block["id"],
                "slot": slot,
                "start_utc": block["start_utc"],
                "end_utc": block["end_utc"],
                "split_label": "evaluation",
                "selection_metadata": {},
            }
            groups.append(g)
            trajectories.append({**g, "status": "DOWNLOADED"})
            frame = SphericalLocalFrame(
                (block["latitude_min"] + block["latitude_max"]) / 2,
                (block["longitude_min"] + block["longitude_max"]) / 2,
            )
            rows = [p["preprocessing"]["csv_columns"], p["preprocessing"]["units"]]
            for hour in range(24):
                lat, lon = frame.to_latlon(
                    np.array([(0.05 + k * 0.003) * hour * 3600, 0.01 * hour * 3600])
                )
                rows.append(
                    [
                        identifier,
                        f._time(f._when(g["start_utc"]) + timedelta(hours=hour)),
                        str(lat),
                        str(lon),
                        "0",
                        "0",
                        "0",
                        "0",
                    ]
                )
            out = io.StringIO()
            csv.writer(out, lineterminator="\n").writerows(rows)
            sources["trajectory:" + identifier] = (out.getvalue().encode(), {})
    selection = {
        "groups": groups,
        "aliases": {
            "reserved_gdp_id_count": len(e["reserved_gdp_ids"]),
            "known_reserved_wmo_count": 200,
            "unresolved_reserved_alias_ids": ["8707978"],
            "unresolved_reserved_alias_count": 1,
            "physical_alias_resolution_verified": False,
            "statistical_independence": False,
        },
    }
    manifest = {
        "trajectories": trajectories,
        "source_receipts": [],
        "started_at_utc": "2026-10-17T10:00:00Z",
        "finished_at_utc": "2026-10-17T10:00:01Z",
    }
    return p, e, h, selection, manifest, sources


def run_invented(values):
    p, e, h, s, m, raw = values
    return f._score(f._base(p, e, h, s, m), f._prepare(p, s, m, raw))


def test_synthetic_full_matrix_keeps_exact_denominators_units_and_no_authority():
    report = run_invented(invented_inputs())
    assert report["status"] == "COMPLETED"
    assert report["coverage"] == {
        "target_groups": 6,
        "selected_groups": 6,
        "downloaded_groups": 6,
        "scored_groups": 6,
        "models": 5,
        "horizons": 6,
        "planned_outcomes": 180,
        "attempted_outcomes": 180,
        "scored_outcomes": 180,
        "failed_outcomes": 0,
        "unfilled_outcomes": 0,
        "unique_observed_intervals": 36,
        "unique_observed_positions": 36,
        "common_target_cohort_complete": True,
    }
    assert [m["id"] for m in report["models"]] == list(MODEL_IDS)
    assert all(m["metrics"] is not None for m in report["models"])
    for flag in (
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
        assert report["flags"][flag] is False
    assert report["flags"]["new_gdp_id_group_evaluation"] is True


def test_all_thirty_forecasts_before_any_future_coordinate_and_no_future_updates(monkeypatch):
    values = invented_inputs()
    completed = []
    original = f._one_forecast

    def track(*args):
        result = original(*args)
        completed.append(True)
        return result

    monkeypatch.setattr(f, "_one_forecast", track)
    original_lat = f._Record.latitude_deg.fget
    original_lon = f._Record.longitude_deg.fget

    def guarded(original, record):
        if record.time_utc.hour >= 18:
            assert len(completed) == 30, "Future coordinate read before all30 forecasts"
        return original(record)

    monkeypatch.setattr(
        f._Record, "latitude_deg", property(lambda self: guarded(original_lat, self))
    )
    monkeypatch.setattr(
        f._Record, "longitude_deg", property(lambda self: guarded(original_lon, self))
    )
    report = run_invented(values)
    assert len(completed) == 30 and report["coverage"]["scored_outcomes"] == 180


def test_changing_future_coordinates_changes_scores_but_never_forecast_receipt():
    values = invented_inputs()
    p, _e, _h, s, m, raw = values
    before = f._forecast_payload(f._prepare(p, s, m, raw))
    initial = run_invented(values)
    for key, (data, receipt) in list(raw.items()):
        rows = list(csv.reader(io.StringIO(data.decode())))
        for row in rows[20:]:
            row[2] = str(float(row[2]) + 0.01)
        out = io.StringIO()
        csv.writer(out, lineterminator="\n").writerows(rows)
        raw[key] = (out.getvalue().encode(), receipt)
    assert f._forecast_payload(f._prepare(p, s, m, raw)) == before
    assert run_invented(values)["models"] != initial["models"]


def test_one_failed_track_keeps_six_null_outcomes_and_withholds_all_common_metrics(monkeypatch):
    original = f._one_forecast
    failed = []

    def fail_one(model, *args):
        if model == "kalman_cv" and not failed:
            failed.append(True)
            raise ValueError("Invented numerical failure")
        return original(model, *args)

    monkeypatch.setattr(f, "_one_forecast", fail_one)
    r = run_invented(invented_inputs())
    assert r["coverage"]["scored_outcomes"] == 174 and r["coverage"]["failed_outcomes"] == 6
    assert r["status"] == "PARTIAL_COVERAGE" and all(x["metrics"] is None for x in r["models"])
    track = r["groups"][0]["models"][-1]
    assert track["metrics"] is None and all(
        p["status"] == "FAILED" and p["x_m"] is None for p in track["predictions"]
    )
    assert r["coverage"]["unique_observed_intervals"] == 36


def test_missing_truth_withholds_whole_group_but_retains_available_positions_and_real_adjacent_pair_count():
    values = invented_inputs()
    raw = values[-1]
    key = next(iter(raw))
    data, receipt = raw[key]
    rows = list(csv.reader(io.StringIO(data.decode())))
    rows[22][2] = "NaN"
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows(rows)
    raw[key] = (out.getvalue().encode(), receipt)
    r = run_invented(values)
    assert r["coverage"]["scored_outcomes"] == 150 and r["coverage"]["failed_outcomes"] == 30
    assert (
        r["coverage"]["unique_observed_positions"] == 35
        and r["coverage"]["unique_observed_intervals"] == 34
    )
    truth = r["groups"][0]["heldout_track"]
    assert len(truth) == 6
    assert (
        truth[2]["status"] == "UNAVAILABLE"
        and truth[2]["x_m"] is None
        and truth[3]["status"] == "OBSERVED"
    )
    assert all(m["metrics"] is None for m in r["groups"][0]["models"])
    assert all(
        row["position_error_m"] is None
        for m in r["groups"][0]["models"]
        for row in m["predictions"]
    )


def test_large_future_truth_is_not_removed_by_fifty_km_prefix_or_forecast_domain():
    values = invented_inputs()
    raw = values[-1]
    key = next(iter(raw))
    data, receipt = raw[key]
    rows = list(csv.reader(io.StringIO(data.decode())))
    rows[-1][2] = str(float(rows[-1][2]) + 1)
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows(rows)
    raw[key] = (out.getvalue().encode(), receipt)
    r = run_invented(values)
    assert r["coverage"]["scored_outcomes"] == 180
    assert np.linalg.norm([r["groups"][0]["heldout_track"][-1][k] for k in ("x_m", "y_m")]) > 50_000
    assert r["groups"][0]["models"][0]["predictions"][-1]["position_error_m"] > 100_000


def test_intervals_use_free_running_anchor_and_observation_ellipse_adds_R():
    r = run_invented(invented_inputs())
    for group in r["groups"]:
        for model in group["models"]:
            anchor = model["forecast_anchor"]
            previous = np.array([anchor[k] for k in ("x_m", "y_m")])
            for row in model["predictions"]:
                current = np.array([row[k] for k in ("x_m", "y_m")])
                np.testing.assert_allclose(
                    (current - previous) / 3600, row["predicted_velocity_m_s"]
                )
                np.testing.assert_allclose(
                    np.array(row["predicted_velocity_m_s"]) - row["observed_velocity_m_s"],
                    row["residual_velocity_m_s"],
                )
                if model["id"] == "kalman_cv":
                    np.testing.assert_allclose(
                        np.array(row["observation_covariance_m2"]) - row["position_covariance_m2"],
                        10000 * np.eye(2),
                    )
                previous = current


@pytest.mark.parametrize(
    "change", ["duplicate_hour", "wrong_id", "bad_units", "missing_row", "invalid_prefix"]
)
def test_bad_input_is_retained_as_failed_group_not_replaced(change):
    values = invented_inputs()
    raw = values[-1]
    key = next(iter(raw))
    data, receipt = raw[key]
    rows = list(csv.reader(io.StringIO(data.decode())))
    if change == "duplicate_hour":
        rows[5][1] = rows[4][1]
    elif change == "wrong_id":
        rows[8][0] = "1"
    elif change == "bad_units":
        rows[1][2] = "radians"
    elif change == "missing_row":
        rows.pop()
    else:
        rows[2][2] = "NaN"
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows(rows)
    raw[key] = (out.getvalue().encode(), receipt)
    r = run_invented(values)
    assert r["coverage"]["attempted_outcomes"] == 180 and r["coverage"]["failed_outcomes"] == 30
    assert r["coverage"]["scored_outcomes"] == 150 and r["groups"][0]["status"] == "FAILED"
    assert all(m["metrics"] is None for m in r["models"])
