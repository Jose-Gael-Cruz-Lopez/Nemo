"""Real current-source integrity and bounded preview semantics, without network."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime

import httpx
import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import current_forecast as forecast
from scripts.acquire_current_forecast import _fetch, acquire


def source_bytes() -> bytes:
    return (forecast.DATA_DIR / forecast.FILE_NAME).read_bytes()


def changed_row(payload: bytes, index: int, value: str) -> bytes:
    rows = payload.decode().splitlines()
    fields = rows[2].split(",")
    fields[index] = value
    rows[2] = ",".join(fields)
    return ("\n".join(rows) + "\n").encode()


def test_real_snapshot_preserves_missing_cells_and_future_time_receipt():
    field, manifest = forecast.load_current_snapshot()
    assert field.eastward_m_s.shape == (3, 29, 37)
    assert int(field.valid_mask.sum()) == 2997
    assert int((~field.valid_mask).sum()) == 222
    assert np.isnan(field.eastward_m_s[~field.valid_mask]).all()
    assert np.isnan(field.northward_m_s[~field.valid_mask]).all()
    assert field.selected_depth_m == 0.25
    assert manifest["future_valid_times_at_acquisition"] is True
    assert datetime.fromisoformat(manifest["captured_at_utc"]) < datetime.fromisoformat(
        forecast.START_UTC
    )
    assert manifest["model_issue_time_utc"] is None
    assert field.metadata["data_kind"] == "model_output_not_plastic_ground_truth"


@pytest.mark.parametrize("filename", [forecast.FILE_NAME, forecast.METADATA_FILE])
def test_pinned_raw_files_cannot_be_silently_changed(tmp_path, filename):
    shutil.copytree(forecast.DATA_DIR, tmp_path / "snapshot")
    path = tmp_path / "snapshot" / filename
    data = bytearray(path.read_bytes())
    data[-2] = 32 if data[-2] != 32 else 33
    path.write_bytes(data)
    with pytest.raises(ValueError, match="reviewed bytes"):
        forecast.load_current_snapshot(tmp_path / "snapshot")


def test_receipt_cannot_be_rewritten_to_accept_changed_sources(tmp_path):
    shutil.copytree(forecast.DATA_DIR, tmp_path / "snapshot")
    path = tmp_path / "snapshot" / forecast.MANIFEST_FILE
    manifest = json.loads(path.read_bytes())
    manifest["files"]["csv"]["sha256"] = "0" * 64
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="immutable manifest"):
        forecast.load_current_snapshot(tmp_path / "snapshot")


@pytest.mark.parametrize("column,value,reason", [
    (0, "2026-10-17T15:00:00Z", "valid time"),
    (1, "10", "depth"),
    (2, "1.0", "geographic subset"),
    (3, "-81", "geographic subset"),
    (4, "inf", "velocity"),
    (5, "100", "velocity"),
])
def test_parser_rejects_wrong_time_units_space_or_velocity(column, value, reason):
    with pytest.raises(ValueError, match=reason):
        forecast.parse_current_csv(changed_row(source_bytes(), column, value))


def test_parser_rejects_unconverted_velocity_units():
    payload = source_bytes().replace(b"meter second-1", b"cm/s", 1)
    with pytest.raises(ValueError, match="units"):
        forecast.parse_current_csv(payload)


def test_parser_rejects_duplicate_or_incomplete_grid():
    payload = source_bytes()
    first_data_row = payload.splitlines()[2] + b"\n"
    with pytest.raises(ValueError, match="Duplicate"):
        forecast.parse_current_csv(payload + first_data_row)
    rows = payload.splitlines(keepends=True)
    with pytest.raises(ValueError, match="complete rectilinear"):
        forecast.parse_current_csv(b"".join(rows[:2] + rows[3:]))


def test_missing_component_is_masked_rather_than_zero_filled():
    field = forecast.parse_current_csv(changed_row(source_bytes(), 4, "NaN"))
    assert not field.valid_mask[0, 0, 0]
    assert np.isnan(field.eastward_m_s[0, 0, 0])
    assert np.isnan(field.northward_m_s[0, 0, 0])


def test_report_runs_offline_and_has_no_measured_accuracy_claim(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Report reads must not request any network data or provider")

    monkeypatch.setattr(httpx.Client, "send", forbidden)
    report = forecast.run_current_forecast()
    assert report["kind"] == "CURRENT_FORCED_PREVIEW"
    assert report["status"] == "COMPLETED"
    assert report["dynamic"]["status"] == report["persistence"]["status"] == "COMPLETED"
    for path in (report["dynamic"], report["persistence"]):
        assert len(path["track"]) == 25
        assert path["completed_horizon_s"] == 21600
        assert path["track"][-1]["time_utc"] == forecast.END_UTC
        assert path["physical_validation"] is False
        assert path["heldout_buoy_positions_used"] is False
    assert report["validation"] == {
        "measured_track_available": False, "physical_validation": False,
        "plastic_motion_validated": False, "forecast_skill_established": False,
        "tank_flow_used": False, "heldout_buoy_positions_used": False,
        "ade_m": None, "fde_m": None,
    }
    assert report["forcing"]["model_issue_time_utc"] is None
    assert report["endpoint_separation_description"] == (
        "Difference between two predictions, not forecast error"
    )
    assert len(report["snapshot_sha256"]) == len(report["method_sha256"]) == 64


def test_dynamic_path_follows_changing_source_currents_against_fair_frozen_baseline():
    report = forecast.run_current_forecast()
    dynamic, baseline = report["dynamic"], report["persistence"]
    assert dynamic["track"][0] == baseline["track"][0]
    # Genuine real-source flow changes; this is not a hand-authored curved path.
    assert dynamic["track"][-1]["northward_m_s"] != dynamic["track"][0]["northward_m_s"]
    assert len({round(point["eastward_m_s"], 12) for point in baseline["track"]}) == 1
    assert len({round(point["northward_m_s"], 12) for point in baseline["track"]}) == 1
    assert dynamic["solver"] == baseline["solver"]
    assert report["endpoint_separation_m"] == pytest.approx(792.1283099852296, abs=1e-5)
    # This difference is between predictions; no historical NOAA score is reused.
    assert report["validation"]["ade_m"] is None


def test_vectors_are_bounded_interpolated_display_samples_with_fixed_domain():
    report = forecast.run_current_forecast()
    assert report["vector_sampling"] == "interpolated_display_samples_not_finer_observations"
    assert [len(frame["vectors"]) for frame in report["vector_frames"]] == [9, 9, 9]
    bounds = report["vector_display_bounds"]
    for frame in report["vector_frames"]:
        for vector in frame["vectors"]:
            assert bounds["latitude_deg"][0] <= vector["latitude_deg"] <= bounds["latitude_deg"][1]
            assert bounds["longitude_deg"][0] <= vector["longitude_deg"] <= bounds["longitude_deg"][1]
    assert report["forcing"]["nominal_grid_spacing_m"] == 4000
    assert report["vector_frames"][0]["vectors"] != report["vector_frames"][2]["vectors"]


def test_archive_mode_follows_valid_window_without_claiming_live_conditions(monkeypatch):
    class Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 19, tzinfo=UTC)

    monkeypatch.setattr(forecast, "datetime", Later)
    report = forecast.run_current_forecast()
    assert report["mode"] == "archived_forecast_snapshot"
    assert any("not live water conditions" in line for line in report["limitations"])


def test_acquisition_refuses_overwriting_pinned_snapshot(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Refusal must happen before any network request")

    monkeypatch.setattr(httpx.Client, "send", forbidden)
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        acquire(forecast.DATA_DIR)


def test_acquisition_transport_rejects_oversized_and_redirected_payloads():
    def oversized(request):
        return httpx.Response(200, content=b"12345")

    with (httpx.Client(transport=httpx.MockTransport(oversized)) as client,
          pytest.raises(ValueError, match="byte budget")):
        _fetch(client, "https://example.org/fixture", 4)

    def redirect(request):
        return httpx.Response(302, headers={"Location": "https://example.org/other"})

    with (httpx.Client(transport=httpx.MockTransport(redirect)) as client,
          pytest.raises(httpx.HTTPStatusError)):
        _fetch(client, "https://example.org/fixture", 4)


def test_snapshot_identity_is_the_exact_source_bytes():
    report = forecast.run_current_forecast()
    assert report["snapshot_sha256"] == hashlib.sha256(source_bytes()).hexdigest()
    assert len(json.dumps(report, allow_nan=False)) < 40_000
