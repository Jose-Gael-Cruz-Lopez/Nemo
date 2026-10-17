"""Invented frozen artifacts only; no formal study freeze, data acquisition or first score."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest

from apps.ocean.reeftrace_ocean import matched_current as models
from apps.ocean.reeftrace_ocean import matched_current_result as reader
from apps.ocean.reeftrace_ocean.field import OceanField


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def save(path, value):
    raw = canonical(value)
    path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    path.with_suffix(".sha256").write_text(digest + "\n")
    return digest


def make_artifacts(tmp_path, monkeypatch, *, partial=False):
    """Reusable synthetic result envelope; pure acquisition helper is a unit seam.

    Model functions prepare invented fixture data BEFORE the reader boundary is
    guarded. No script wrapper/freeze/acquisition/real scientific values are used.
    """
    root = tmp_path / "synthetic-repo"
    directory = root / "data/research/matched-current-v1"
    directory.mkdir(parents=True)
    p = reader.protocol_io
    protocol = {"study_id": p.STUDY_ID, "frozen_at_utc": "2026-01-01T00:00:00Z"}
    hashes = {"protocol_sha256": "a" * 64, "trusted_identity_sha256": "b" * 64,
              "manifest_sha256": "c" * 64, "acquisition_start_sha256": "d" * 64}
    context = {group: [{"drifter_id": group,
        "time_utc": (models.ORIGIN - timedelta(hours=24 - i)).isoformat(),
        "latitude_deg": "30", "longitude_deg": "-75"} for i in range(25)]
        for group in models.GROUP_IDS}
    targets = {group: [{"drifter_id": group,
        "time_utc": (models.ORIGIN + timedelta(seconds=hour)).isoformat(),
        "latitude_deg": "30", "longitude_deg": "-75"} for hour in models.HORIZONS_S]
        for group in models.GROUP_IDS}
    if partial:
        targets[models.GROUP_IDS[0]][0]["latitude_deg"] = "NaN"
    receipts = []
    for role in p.ROLE_ORDER:
        receipts.append({"role": role, "status": "DOWNLOADED", "reason": None,
            "source_url": "https://example.invalid/invented-fixture-only", "raw_path": None,
            "sha256": "e" * 64, "bytes": 123, "received_bytes": 123, "retained_bytes": 123,
            "request_attempted": True, "http_status": 200, "response_complete": True,
            "content_type": "application/x-netcdf" if role == "hycom_currents" else "text/plain",
            "content_encoding": "identity", "started_at_utc": "2026-01-01T00:00:01Z",
            "finished_at_utc": "2026-01-01T00:00:02Z", "elapsed_wall_s": 1.0})
    manifest = {"finished_at_utc": "2026-01-01T00:00:03Z", "source_receipts": receipts}
    shape = (3, 2, 2)
    metadata = {"product": "HYCOM_GOFS3.1_GLBy0.08_expt93.0_UV3Z_2022_format_contract",
        "contract_metadata_url": "https://example.invalid/invented-metadata",
        "sha256": "e" * 64, "source_bytes": 123, "u_variable": "water_u", "v_variable": "water_v",
        "velocity_units": "m/s", "data_kind": "local_model_subset_not_observed_plastic",
        "source_origin_verified": False, "issue_time_verified": False, "calendar": "gregorian",
        "time_units": "hours since 2000-01-01 00:00:00",
        "longitude_normalization": "((native_lon+180)%360)-180_without_reordering",
        "raw_encoding": {"dtype": "signed_int16", "fill_and_missing": -30000,
            "scale_factor_encoding": "exact_pinned_float32", "applied_decimal_scale": 0.001,
            "add_offset": 0, "mask_before_scaling": True, "decode_count": 1},
        "limitations": ["Invented test summary, not an acquired current field."]}
    field = OceanField(np.array(["2022-06-01T00", "2022-06-01T03", "2022-06-01T06"],
                                dtype="datetime64[us]"),
        np.array([-80., -65.]), np.array([25., 35.]), np.zeros(shape), np.zeros(shape),
        np.ones(shape, dtype=bool), 15., metadata)
    forecasts = models.build_matched_current_forecasts(context, dict.fromkeys(models.GROUP_IDS, field))
    scores = models.score_matched_current_forecasts(forecasts, targets)
    forecast = {"schema_version": 1, "kind": "FROZEN_MATCHED_CURRENT_FORECASTS",
        "study_id": p.STUDY_ID, "lineage": hashes.copy(), "forecasts": forecasts,
        "future_coordinates_decoded": False, "frozen_at_utc": "2026-01-01T00:00:04Z"}
    report = {"schema_version": 1, "kind": "MATCHED_CURRENT_RETROSPECTIVE_DIAGNOSTIC",
        "study_id": p.STUDY_ID, "lineage": hashes.copy(), "forecast_file_sha256": None,
        "forecast_frozen_at_utc": forecast["frozen_at_utc"],
        "forecasts_saved_before_target_coordinate_decode": True,
        "source_receipts": copy.deepcopy(receipts),
        "context_qc": {group: {"planned_context_rows": 25, "received_context_rows": 25,
            "invalid_coordinate_indices": [], "used_as_whole_group_admission_gate": False,
            "first_23_positions_used_by_models": False} for group in models.GROUP_IDS},
        "current_field": field.summary(), "current_field_failure": None,
        "scores": scores, "scored_at_utc": "2026-01-01T00:00:05Z",
        **dict.fromkeys(reader.FALSE_FLAGS, False)}
    calls = []

    def load(selected_directory, *, root):
        assert Path(selected_directory) == directory
        assert Path(root) == case["root"]
        calls.append(True)
        return copy.deepcopy((protocol, manifest, hashes, {}))

    case = {"root": root, "directory": directory, "protocol": protocol, "manifest": manifest,
        "hashes": hashes, "forecast": forecast, "report": report, "loads": calls}
    monkeypatch.setattr(p, "load_acquisition", load)
    rewrite(case)
    return case


def rewrite(case, *, refresh_inner=False):
    if refresh_inner:
        forecasts = case["forecast"]["forecasts"]
        forecasts["forecast_sha256"] = models.forecast_sha256(forecasts)
        case["report"]["scores"]["forecast_report"] = copy.deepcopy(forecasts)
    case["forecast_hash"] = save(case["directory"] / "forecasts.json", case["forecast"])
    case["report"]["forecast_file_sha256"] = case["forecast_hash"]
    case["report_hash"] = save(case["directory"] / "evaluation.json", case["report"])
    identity = case["root"] / reader.RESULT_IDENTITY_RELATIVE
    identity.parent.mkdir(parents=True, exist_ok=True)
    identity.write_text(f'STUDY_ID = {reader.protocol_io.STUDY_ID!r}\n'
        f'REPORT_SHA256 = {case["report_hash"]!r}\nFORECAST_SHA256 = {case["forecast_hash"]!r}\n'
        f'MANIFEST_SHA256 = {case["hashes"]["manifest_sha256"]!r}\n')


@pytest.fixture
def artifacts(tmp_path, monkeypatch):
    return make_artifacts(tmp_path, monkeypatch)


def read(case, **kwargs):
    return reader.load_frozen_matched_current_result(case["directory"], root=case["root"], **kwargs)


def test_reads_exact_whitelisted_report_and_separates_structure_from_numeric_replay(artifacts):
    result = read(artifacts)
    assert result["report"] == artifacts["report"]
    identity = result["artifact_identity"]
    assert identity["report_sha256"] == artifacts["report_hash"]
    assert identity["forecast_file_sha256"] == artifacts["forecast_hash"]
    assert identity["numeric_replay_verified"] is False
    assert identity["result_pin_verified"] is True
    assert identity["pin_source"] == "TRUSTED_RESULT_IDENTITY"
    assert len(artifacts["loads"]) == 2
    result["report"]["scores"]["groups"].clear()
    assert len(read(artifacts)["report"]["scores"]["groups"]) == 2


def test_default_uses_research_archive_without_rewriting_the_snapshot(artifacts):
    assert artifacts["directory"] == artifacts["root"] / "data/research/matched-current-v1"
    before = {str(p): p.read_bytes() for p in artifacts["root"].rglob("*") if p.is_file()}
    result = reader.load_frozen_matched_current_result(root=artifacts["root"])
    assert result["report"] == artifacts["report"]
    assert result["artifact_identity"]["report_sha256"] == artifacts["report_hash"]
    assert result["artifact_identity"]["pin_source"] == "TRUSTED_RESULT_IDENTITY"
    assert not (artifacts["root"] / "data/public/matched-current-v1").exists()
    after = {str(p): p.read_bytes() for p in artifacts["root"].rglob("*") if p.is_file()}
    assert after == before


def test_reader_cannot_build_score_fetch_freeze_or_write(artifacts, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Public result reader tried an executable scientific or network operation")
    monkeypatch.setattr(models, "build_matched_current_forecasts", forbidden)
    monkeypatch.setattr(models, "score_matched_current_forecasts", forbidden)
    monkeypatch.setattr(reader.protocol_io, "freeze_protocol", forbidden)
    import socket
    monkeypatch.setattr(socket, "create_connection", forbidden)
    before = {str(p): p.read_bytes() for p in artifacts["root"].rglob("*") if p.is_file()}
    assert read(artifacts)["report"]["scores"]["scored_cell_count"] == 36
    after = {str(p): p.read_bytes() for p in artifacts["root"].rglob("*") if p.is_file()}
    assert after == before


def test_unpinned_default_fails_closed_and_local_opt_in_is_explicit(artifacts):
    (artifacts["root"] / reader.RESULT_IDENTITY_RELATIVE).unlink()
    with pytest.raises(FileNotFoundError, match="Trusted"):
        read(artifacts)
    assert read(artifacts, expected_report_sha256=artifacts["report_hash"])["artifact_identity"]["pin_source"] == "EXPLICIT_CALLER_PIN"
    local = read(artifacts, allow_unpinned_local=True)["artifact_identity"]
    assert local["result_pin_verified"] is False
    assert local["pin_source"] == "UNPINNED_LOCAL_ONLY"


@pytest.mark.parametrize("value", ["bad", "A" * 64, 1, True])
def test_invalid_explicit_result_pin_is_rejected(artifacts, value):
    with pytest.raises(ValueError, match="hash"):
        read(artifacts, expected_report_sha256=value)


def test_wrong_expected_hash_and_wrong_trusted_manifest_are_rejected(artifacts):
    with pytest.raises(ValueError, match="trusted artifact hash"):
        read(artifacts, expected_report_sha256="f" * 64)
    identity = artifacts["root"] / reader.RESULT_IDENTITY_RELATIVE
    identity.write_text(identity.read_text().replace("c" * 64, "f" * 64))
    with pytest.raises(ValueError, match="manifest"):
        read(artifacts)


def test_executable_or_extra_trusted_identity_never_executes(artifacts):
    path = artifacts["root"] / reader.RESULT_IDENTITY_RELATIVE
    path.write_text("raise RuntimeError('must not execute')\n")
    with pytest.raises(ValueError, match="literal"):
        read(artifacts)


@pytest.mark.parametrize("name", ["forecasts.json", "evaluation.json", "forecasts.sha256", "evaluation.sha256"])
def test_missing_saved_artifact_is_unavailable(artifacts, name):
    (artifacts["directory"] / name).unlink()
    with pytest.raises(FileNotFoundError):
        read(artifacts)


@pytest.mark.parametrize("name", ["forecasts", "evaluation"])
def test_changed_bytes_and_detached_hashes_fail_before_result_exposure(artifacts, name):
    path = artifacts["directory"] / (name + ".json")
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="detached"):
        read(artifacts)
    path.with_suffix(".sha256").write_text(hashlib.sha256(path.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match="trusted"):
        read(artifacts)


def test_bounded_json_duplicate_nonfinite_and_unknown_fields_fail(artifacts):
    artifacts["report"]["PRIVATE_EXTRA"] = "must not be exposed"
    rewrite(artifacts)
    with pytest.raises(ValueError, match="schema"):
        read(artifacts)
    path = artifacts["directory"] / "evaluation.json"
    for raw in (b'{"same":1,"same":2}', b'{"bad":NaN}', b'{"bad":Infinity}'):
        path.write_bytes(raw)
        path.with_suffix(".sha256").write_text(hashlib.sha256(raw).hexdigest())
        with pytest.raises(ValueError):
            read(artifacts, allow_unpinned_local=True, expected_report_sha256=hashlib.sha256(raw).hexdigest())


@pytest.mark.parametrize("name", ["forecasts.json", "evaluation.json", "forecasts.sha256"])
def test_symlinked_result_or_detached_hash_is_rejected(artifacts, name):
    original = artifacts["directory"] / name
    moved = artifacts["root"] / ("outside-" + name)
    original.rename(moved)
    original.symlink_to(moved)
    with pytest.raises(ValueError, match="([Ss]ymlink|escapes)"):
        read(artifacts)


@pytest.mark.parametrize("change", ["before_manifest", "before_source", "before_forecast", "invalid", "naive", "offset"])
def test_rehashed_clock_chain_is_still_verified(artifacts, change):
    if change == "before_manifest":
        artifacts["manifest"]["finished_at_utc"] = "2026-01-01T00:00:10Z"
    elif change == "before_source":
        artifacts["manifest"]["source_receipts"][0]["finished_at_utc"] = "2026-01-01T00:00:10Z"
        artifacts["report"]["source_receipts"] = copy.deepcopy(artifacts["manifest"]["source_receipts"])
    elif change == "before_forecast":
        artifacts["report"]["scored_at_utc"] = "2026-01-01T00:00:03Z"
    else:
        artifacts["report"]["scored_at_utc"] = {"invalid": "bad", "naive": "2026-01-01T00:00:05",
            "offset": "2026-01-01T01:00:05+01:00"}[change]
    rewrite(artifacts)
    with pytest.raises(ValueError, match="(chronology|UTC)"):
        read(artifacts)


@pytest.mark.parametrize("change", ["group", "model", "cell", "null", "target", "count", "primary", "paired", "flag", "lineage", "isolated"])
def test_all_planned_cells_metrics_and_claim_boundaries_are_checked(artifacts, change):
    report = artifacts["report"]
    scores = report["scores"]
    if change == "group":
        scores["groups"].pop()
    elif change == "model":
        scores["groups"][0]["candidates"].pop()
    elif change == "cell":
        scores["groups"][0]["candidates"][0]["cells"].pop()
    elif change == "null":
        scores["groups"][0]["candidates"][0]["cells"][0]["error_m"] = None
    elif change == "target":
        scores["groups"][0]["candidates"][0]["cells"][0]["target_latitude_deg"] = 31
    elif change == "count":
        scores["scored_cell_count"] = 35
    elif change == "primary":
        scores["primary_equal_id_macro_results"][0]["equal_id_macro_ade_m"] = 1.
    elif change == "paired":
        scores["paired_comparisons"][0]["common_scored_count"] = 11
    elif change == "flag":
        report["physical_validation"] = True
    elif change == "lineage":
        report["lineage"]["protocol_sha256"] = "f" * 64
    else:
        report["forecasts_saved_before_target_coordinate_decode"] = False
    rewrite(artifacts)
    with pytest.raises(ValueError):
        read(artifacts)


def test_partial_cohort_keeps_36_cells_and_null_primary_not_successful_subset(tmp_path, monkeypatch):
    case = make_artifacts(tmp_path, monkeypatch, partial=True)
    scores = read(case)["report"]["scores"]
    assert scores["planned_cell_count"] == 36 and scores["scored_cell_count"] == 33
    assert scores["primary_equal_id_macro_results"] is None
    assert scores["primary_paired_comparisons"] is None
    assert scores["paired_comparisons"][0]["common_scored_count"] == 11
    assert scores["groups"][0]["candidates"][0]["metrics"]["endpoint_scored"] is True
    case["report"]["scores"]["primary_equal_id_macro_results"] = []
    rewrite(case)
    with pytest.raises(ValueError, match="incomplete"):
        read(case)


def test_concurrent_manifest_or_result_swap_is_rejected(artifacts, monkeypatch):
    original = reader.protocol_io.load_acquisition
    count = []
    def changed(*args, **kwargs):
        protocol, manifest, hashes, sources = original(*args, **kwargs)
        if count:
            hashes["manifest_sha256"] = "f" * 64
        count.append(True)
        return protocol, manifest, hashes, sources
    monkeypatch.setattr(reader.protocol_io, "load_acquisition", changed)
    with pytest.raises(ValueError, match="changed while"):
        read(artifacts)


def test_honest_zero_of_36_retains_every_failed_cell_and_null_result(artifacts):
    forecasts = models.build_matched_current_forecasts({}, {}, failures_by_group={
        group: "DEPENDENCY_UNAVAILABLE" for group in models.GROUP_IDS})
    artifacts["forecast"]["forecasts"] = forecasts
    artifacts["report"]["scores"] = models.score_matched_current_forecasts(forecasts, {})
    artifacts["report"]["current_field"] = None
    artifacts["report"]["current_field_failure"] = "HYCOM_REQUESTED_NATIVE_TILE_OR_STRIDE_CHANGED"
    for qc in artifacts["report"]["context_qc"].values():
        qc["received_context_rows"] = 0
    rewrite(artifacts)
    result = read(artifacts)["report"]
    scores = result["scores"]
    assert scores["scored_cell_count"] == 0 and scores["planned_cell_count"] == 36
    assert scores["primary_equal_id_macro_results"] is None
    assert sum(len(model["cells"]) for group in scores["groups"]
               for model in group["candidates"]) == 36
    assert all(cell["error_m"] is None for group in scores["groups"]
               for model in group["candidates"] for cell in model["cells"])


def test_untrusted_protocol_helper_failure_is_never_bypassed(artifacts, monkeypatch):
    def invalid(*args, **kwargs):
        raise ValueError("Trusted protocol changed")
    monkeypatch.setattr(reader.protocol_io, "load_acquisition", invalid)
    with pytest.raises(ValueError, match="Trusted protocol"):
        read(artifacts)


def test_current_field_and_advection_unknown_fields_are_not_exposed(artifacts):
    artifacts["report"]["current_field"]["private_file_path"] = "must not leak"
    rewrite(artifacts)
    with pytest.raises(ValueError, match="schema"):
        read(artifacts)
