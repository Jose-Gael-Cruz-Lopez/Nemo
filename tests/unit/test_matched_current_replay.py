"""Synthetic orchestration evidence; no GDP/HYCOM values or provider requests."""

import copy
import csv
import io
import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean.field import OceanField
from apps.ocean.reeftrace_ocean.matched_current import (
    GROUP_IDS,
    ORIGIN,
    build_matched_current_forecasts,
)
from scripts import evaluate_matched_current_study as wrapper


def csv_bytes(group=GROUP_IDS[0]):
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["ID", "time", "latitude", "longitude"])
    writer.writerow(["", "UTC", "degrees_north", "degrees_east"])
    for when in wrapper.EXPECTED_TIMES:
        writer.writerow([group, when, "30", "-75"])
    return stream.getvalue().encode()


def fake_inputs():
    contexts, targets = {}, {}
    for group in GROUP_IDS:
        contexts[group], targets[group] = wrapper.parse_position_strings(csv_bytes(group), group)
    shape = (3, 2, 2)
    field = OceanField(
        np.array(["2022-06-01T00", "2022-06-01T03", "2022-06-01T06"], dtype="datetime64[us]"),
        np.array([-80.0, -65.0]), np.array([25.0, 35.0]),
        np.full(shape, 0.1), np.zeros(shape), np.ones(shape, dtype=bool), 15.0,
        {"kind": "SYNTHETIC_TEST_FIELD"},
    )
    forecasts = build_matched_current_forecasts(contexts, {group: field for group in GROUP_IDS})
    return ({"study_id": "synthetic-wrapper-test"},
            {"source_receipts": [], "finished_at_utc": "2026-01-01T00:00:00Z"},
            {"protocol_sha256": "a" * 64, "manifest_sha256": "b" * 64},
            contexts, targets, forecasts, field, None)


def test_csv_partition_does_not_decode_reserved_coordinates():
    raw = csv_bytes()
    lines = raw.decode().splitlines()
    lines[-1] = lines[-1].replace(",30,-75", ",FUTURE_NOT_NUMERIC,ALSO_NOT_NUMERIC")
    context, target = wrapper.parse_position_strings(("\n".join(lines) + "\n").encode(), GROUP_IDS[0])
    assert len(context) == 25 and len(target) == 6
    assert target[-1]["latitude_deg"] == "FUTURE_NOT_NUMERIC"


@pytest.mark.parametrize("change", ["header", "units", "count", "id", "time", "width", "duplicate"])
def test_csv_exact_identity_structure_and_schedule(change):
    rows = list(csv.reader(io.StringIO(csv_bytes().decode())))
    if change == "header":
        rows[0][0] = "WMO"
    elif change == "units":
        rows[1][2] = "radians"
    elif change == "count":
        rows.pop()
    elif change == "id":
        rows[-1][0] = GROUP_IDS[1]
    elif change == "time":
        rows[-1][1] = "2022-06-01T07:00:00Z"
    elif change == "width":
        rows[-1].append("unexpected")
    else:
        rows[-1][1] = rows[-2][1]
    stream = io.StringIO()
    csv.writer(stream).writerows(rows)
    with pytest.raises(ValueError, match="GDP_"):
        wrapper.parse_position_strings(stream.getvalue().encode(), GROUP_IDS[0])


def test_full_forecasts_are_persisted_before_any_target_numeric_read(tmp_path, monkeypatch):
    inputs = list(fake_inputs())
    checked = []

    class GuardedRow(dict):
        def get(self, key, default=None):
            if key in ("latitude_deg", "longitude_deg"):
                saved, _ = wrapper._pinned(tmp_path / "forecasts.json")
                assert len(saved["forecasts"]["groups"]) == 2
                assert all(len(group["candidates"]) == 3 for group in saved["forecasts"]["groups"])
                assert saved["future_coordinates_decoded"] is False
                checked.append(key)
            return super().get(key, default)

    inputs[4] = {group: [GuardedRow(row) for row in rows] for group, rows in inputs[4].items()}
    monkeypatch.setattr(wrapper, "_inputs", lambda _directory: tuple(inputs))
    result = wrapper.evaluate_study(tmp_path, first_score=True)
    assert checked
    assert result["scores"]["scored_cell_count"] == 36
    assert result["scores"]["primary_common_cohort_complete"] is True
    assert wrapper.evaluate_study(tmp_path) == result
    with pytest.raises(ValueError, match="already exists"):
        wrapper.evaluate_study(tmp_path, first_score=True)


def test_default_replay_never_first_scores(tmp_path, monkeypatch):
    def forbidden(_directory):
        pytest.fail("Replay attempted to load inputs and compute first forecasts")

    monkeypatch.setattr(wrapper, "_inputs", forbidden)
    with pytest.raises(ValueError, match="replay never"):
        wrapper.evaluate_study(tmp_path)


@pytest.mark.parametrize("artifact", ["forecasts", "evaluation"])
def test_rehashed_changed_saved_receipt_fails_replay(tmp_path, monkeypatch, artifact):
    inputs = fake_inputs()
    monkeypatch.setattr(wrapper, "_inputs", lambda _directory: inputs)
    wrapper.evaluate_study(tmp_path, first_score=True)
    path = tmp_path / f"{artifact}.json"
    value = json.loads(path.read_text())
    if artifact == "forecasts":
        value["future_coordinates_decoded"] = True
    else:
        value["physical_validation"] = True
    raw = wrapper.canonical_json(value)
    path.write_bytes(raw)
    path.with_suffix(".sha256").write_text(wrapper._sha(raw) + "\n")
    with pytest.raises(ValueError, match="differs"):
        wrapper.evaluate_study(tmp_path)


def test_future_corruption_changes_only_scores_and_retains_all_cells(tmp_path, monkeypatch):
    inputs = list(fake_inputs())
    original_forecasts = copy.deepcopy(inputs[5])
    inputs[4][GROUP_IDS[0]][0]["latitude_deg"] = "NaN"
    monkeypatch.setattr(wrapper, "_inputs", lambda _directory: tuple(inputs))
    result = wrapper.evaluate_study(tmp_path, first_score=True)
    assert result["scores"]["planned_cell_count"] == 36
    assert result["scores"]["scored_cell_count"] == 33
    assert result["scores"]["primary_equal_id_macro_results"] is None
    assert result["scores"]["forecast_report"] == original_forecasts


def test_orphaned_detached_receipt_prevents_first_score(tmp_path):
    (tmp_path / "forecasts.sha256").write_text("a" * 64)
    with pytest.raises(ValueError, match="already exists"):
        wrapper.evaluate_study(tmp_path, first_score=True)


def test_acquisition_after_forecast_clock_is_rejected(tmp_path, monkeypatch):
    inputs = list(fake_inputs())
    inputs[1]["source_receipts"] = [{"finished_at_utc": "2099-01-01T00:00:00+00:00"}]
    monkeypatch.setattr(wrapper, "_inputs", lambda _directory: tuple(inputs))
    with pytest.raises(ValueError, match="predates acquisition"):
        wrapper.evaluate_study(tmp_path, first_score=True)
    assert not (tmp_path / "forecasts.json").exists()


def test_acquisition_manifest_completion_bounds_forecast_even_after_all_requests_finished(tmp_path, monkeypatch):
    inputs = list(fake_inputs())
    inputs[1] = {"source_receipts": [{"finished_at_utc": "2026-01-01T00:00:00Z"}],
                 "finished_at_utc": "2099-01-01T00:00:00Z"}
    monkeypatch.setattr(wrapper, "_inputs", lambda _directory: tuple(inputs))
    with pytest.raises(ValueError, match="predates acquisition manifest"):
        wrapper.evaluate_study(tmp_path, first_score=True)
    assert not (tmp_path / "forecasts.json").exists()


def test_rehashed_replay_forecast_cannot_precede_manifest_completion_with_coherent_result_hashes(tmp_path, monkeypatch):
    inputs = list(fake_inputs())
    inputs[1] = {"source_receipts": [{"finished_at_utc": "2026-01-01T00:00:00Z"}],
                 "finished_at_utc": "2026-02-01T00:00:00Z"}
    monkeypatch.setattr(wrapper, "_inputs", lambda _directory: tuple(inputs))
    wrapper.evaluate_study(tmp_path, first_score=True)
    forecast_path, result_path = tmp_path / "forecasts.json", tmp_path / "evaluation.json"
    forecast, result = json.loads(forecast_path.read_text()), json.loads(result_path.read_text())
    forecast["frozen_at_utc"] = "2026-01-15T00:00:00Z"
    payload = wrapper.canonical_json(forecast)
    forecast_path.write_bytes(payload)
    forecast_path.with_suffix(".sha256").write_text(wrapper._sha(payload) + "\n")
    result["forecast_file_sha256"] = wrapper._sha(payload)
    result["forecast_frozen_at_utc"] = forecast["frozen_at_utc"]
    payload = wrapper.canonical_json(result)
    result_path.write_bytes(payload)
    result_path.with_suffix(".sha256").write_text(wrapper._sha(payload) + "\n")
    with pytest.raises(ValueError, match="predates acquisition manifest"):
        wrapper.evaluate_study(tmp_path)


def test_context_qc_is_descriptive_and_does_not_read_future():
    context = [{"time_utc": (ORIGIN - timedelta(hours=24 - i)).isoformat(),
                "latitude_deg": "bad" if i < 23 else "30", "longitude_deg": "-75"}
               for i in range(25)]
    qc = wrapper._context_qc(context)
    assert qc["invalid_coordinate_indices"] == list(range(23))
    assert qc["used_as_whole_group_admission_gate"] is False


@pytest.mark.parametrize("artifact", ["forecasts", "evaluation"])
@pytest.mark.parametrize("change", ["invalid", "before_dependency", "non_utc", "naive"])
def test_replay_revalidates_rehashed_receipt_clock_chain(tmp_path, monkeypatch, artifact, change):
    """Detached hashes alone cannot certify acquisition <= forecast <= score."""
    inputs = list(fake_inputs())
    inputs[1]["source_receipts"] = [{"finished_at_utc": "2026-01-01T00:00:00+00:00"}]
    monkeypatch.setattr(wrapper, "_inputs", lambda _directory: tuple(inputs))
    wrapper.evaluate_study(tmp_path, first_score=True)
    forecast_path, result_path = tmp_path / "forecasts.json", tmp_path / "evaluation.json"
    forecast = json.loads(forecast_path.read_text())
    result = json.loads(result_path.read_text())
    value = forecast if artifact == "forecasts" else result
    key = "frozen_at_utc" if artifact == "forecasts" else "scored_at_utc"
    original = datetime.fromisoformat(value[key])
    if change == "invalid":
        value[key] = "not-even-a-time"
    elif change == "before_dependency":
        value[key] = ("2025-12-31T23:59:59+00:00" if artifact == "forecasts"
                      else (datetime.fromisoformat(forecast["frozen_at_utc"])
                            - timedelta(seconds=1)).isoformat())
    elif change == "non_utc":
        value[key] = original.astimezone(timezone(timedelta(hours=1))).isoformat()
    else:
        value[key] = original.replace(tzinfo=None).isoformat()

    def rewrite(path, document):
        raw = wrapper.canonical_json(document)
        path.write_bytes(raw)
        path.with_suffix(".sha256").write_text(wrapper._sha(raw) + "\n")
        return wrapper._sha(raw)

    if artifact == "forecasts":
        # Keep all hashes and cross-references coherent: only chronology is bad.
        result["forecast_file_sha256"] = rewrite(forecast_path, forecast)
        result["forecast_frozen_at_utc"] = forecast["frozen_at_utc"]
    rewrite(result_path, result)
    with pytest.raises(ValueError):
        wrapper.evaluate_study(tmp_path)


def test_current_reader_bytes_must_match_verified_acquisition_before_forecasting(tmp_path, monkeypatch):
    """A second path read cannot silently replace the acquisition-verified bytes."""
    from apps.ocean.reeftrace_ocean import matched_current_protocol

    current_bytes = b"synthetic acquisition-verified current bytes; never a real download"
    current_sha = wrapper._sha(current_bytes)
    sources = {"trajectory:" + group: csv_bytes(group) for group in GROUP_IDS}
    sources["hycom_currents"] = current_bytes
    receipts = [{"role": "trajectory:" + group} for group in GROUP_IDS]
    receipts.append({"role": "hycom_currents", "raw_path": "raw/synthetic-current.nc",
                     "sha256": current_sha})
    protocol = {"groups": [{"drifter_id": group} for group in GROUP_IDS],
                "models": list(wrapper.MODEL_IDS),
                "windows": {"horizons_s": list(wrapper.HORIZONS_S),
                            "origin_time_utc": wrapper.EXPECTED_TIMES[24]}}
    monkeypatch.setattr(matched_current_protocol, "load_acquisition", lambda _directory: (
        protocol, {"source_receipts": receipts}, {}, sources,
    ))
    field = fake_inputs()[6]
    # A changed decoder contract cannot claim that a different payload was read.
    field.metadata["sha256"] = "f" * 64
    monkeypatch.setattr(wrapper, "_study_field", lambda _path: field)

    def no_forecast_on_mismatched_bytes(*args, **kwargs):
        pytest.fail("Forecasting consumed forcing unrelated to the verified acquisition bytes")

    monkeypatch.setattr(wrapper, "build_matched_current_forecasts", no_forecast_on_mismatched_bytes)
    with pytest.raises(ValueError, match="(?i)(hycom|provenance|bytes|identity)"):
        wrapper._inputs(tmp_path)
    assert not (tmp_path / "forecasts.json").exists()


def test_wrapper_decodes_verified_memory_bytes_without_reopening_mutable_raw_path(tmp_path, monkeypatch):
    from apps.ocean.reeftrace_ocean import hycom, matched_current_protocol

    payload = b"synthetic already verified payload; byte transport contract test only"
    sources = {"trajectory:" + group: csv_bytes(group) for group in GROUP_IDS}
    sources["hycom_currents"] = payload
    raw_path = tmp_path / "raw" / "synthetic-current.nc"
    raw_path.parent.mkdir()
    raw_path.write_bytes(b"concurrent malformed replacement, never scientific data")
    receipts = [{"role": "trajectory:" + group} for group in GROUP_IDS]
    receipts.append({"role": "hycom_currents", "raw_path": "raw/synthetic-current.nc",
                     "sha256": wrapper._sha(payload)})
    protocol = {"groups": [{"drifter_id": group} for group in GROUP_IDS],
                "models": list(wrapper.MODEL_IDS),
                "windows": {"horizons_s": list(wrapper.HORIZONS_S),
                            "origin_time_utc": wrapper.EXPECTED_TIMES[24]}}
    monkeypatch.setattr(matched_current_protocol, "load_acquisition", lambda _directory: (
        protocol, {"source_receipts": receipts}, {}, sources,
    ))
    field = fake_inputs()[6]
    field.latitude_deg[:] = [30, 30.04]
    field.longitude_deg[:] = [-75, -74.92]
    field.metadata["sha256"] = wrapper._sha(payload)
    seen = []

    def memory_only(value):
        assert value is payload
        seen.append(value)
        return field

    def forbidden_file_read(*args, **kwargs):
        pytest.fail("Verified forcing was reopened from a mutable filesystem path")

    monkeypatch.setattr(wrapper, "load_hycom_field_bytes", memory_only)
    monkeypatch.setattr(hycom, "load_hycom_field", forbidden_file_read)
    result = wrapper._inputs(tmp_path)
    assert seen == [payload]
    assert result[-1] is None
    assert result[5]["planned_cell_count"] == 36
    assert all(candidate["status"] == "COMPLETED" for group in result[5]["groups"]
               for candidate in group["candidates"])
    assert not (tmp_path / "forecasts.json").exists()
