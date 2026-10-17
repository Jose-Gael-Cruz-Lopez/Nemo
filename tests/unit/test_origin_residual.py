"""Synthetic development contracts; never score the already-viewed real cohort."""

import copy
import math
from datetime import timedelta

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from apps.ocean.reeftrace_ocean import matched_current as original
from apps.ocean.reeftrace_ocean import origin_residual as model
from apps.ocean.reeftrace_ocean.advection import advect_current
from apps.ocean.reeftrace_ocean.benchmark import SphericalLocalFrame
from apps.ocean.reeftrace_ocean.field import OceanField
from scripts import evaluate_origin_residual_diagnostic as runner

LATITUDE, LONGITUDE = 30.0, -79.5


def context(identity, *, east=0.5, north=0.0):
    frame = SphericalLocalFrame(LATITUDE, LONGITUDE)
    previous = frame.to_latlon(np.array([-east, -north]) * 3600)
    rows = [{"drifter_id": identity,
        "time_utc": (model.ORIGIN - timedelta(hours=24 - index)).isoformat(),
        "latitude_deg": str(LATITUDE), "longitude_deg": str(LONGITUDE)} for index in range(25)]
    rows[-2].update({"latitude_deg": str(previous[0]), "longitude_deg": str(previous[1])})
    return rows


def contexts(**kwargs):
    return {identity: context(identity, **kwargs) for identity in model.GROUP_IDS}


def field(*, east=(0.2, 0.7, 0.1), north=(0.0, 0.0, 0.0), mask=None,
          longitude=(-80.0, -78.0)):
    shape = (3, 2, 2)
    return OceanField(
        time_utc=np.array(["2022-06-01T00:00:00", "2022-06-01T03:00:00", "2022-06-01T06:00:00"],
                          dtype="datetime64[us]"),
        longitude_deg=np.array(longitude), latitude_deg=np.array([29.0, 31.0]),
        eastward_m_s=np.broadcast_to(np.asarray(east)[:, None, None], shape).copy(),
        northward_m_s=np.broadcast_to(np.asarray(north)[:, None, None], shape).copy(),
        valid_mask=np.ones(shape, dtype=bool) if mask is None else np.array(mask, copy=True),
        selected_depth_m=15.0,
        metadata={"velocity_units": "m/s", "data_kind": "SYNTHETIC_TEST",
                  "sha256": "a" * 64, "nested": {"untouched": [1, 2]}})


def fields(value=None):
    return dict.fromkeys(model.GROUP_IDS, field() if value is None else value)


def targets():
    return {identity: [{"drifter_id": identity,
        "time_utc": (model.ORIGIN + timedelta(seconds=h)).isoformat(),
        "latitude_deg": str(LATITUDE), "longitude_deg": str(LONGITUDE)}
        for h in model.HORIZONS_S] for identity in model.GROUP_IDS}


def test_plan_allocates_four_candidates_and_keeps_original_three_outputs_exact():
    ctx, forcing = contexts(), fields()
    before = original.build_matched_current_forecasts(ctx, forcing)
    result = model.build_forecasts(ctx, forcing)
    assert result["planned_cell_count"] == 48 and result["planned_distinct_target_count"] == 12
    assert len(result["groups"]) == 2
    for old, group in zip(before["groups"], result["groups"], strict=True):
        assert group["candidates"][:3] == old["candidates"]
        assert len(group["candidates"]) == 4
        assert all(item["learned_parameters"] == 0 for item in group["candidates"])
        assert all(item["future_positions_used"] is False for item in group["candidates"])
    assert sum(len(c["cells"]) for g in result["groups"] for c in g["candidates"]) == 48
    assert result["analysis_scope"] == "POST_OUTCOME_EXPLORATORY"
    assert result["previously_viewed_target_outcomes"] is True
    assert result["forecast_sha256"] == model.forecast_sha256(result)


def test_zero_residual_reproduces_current_track_with_separate_derived_provenance():
    ctx = context(model.GROUP_IDS[0])
    frame = SphericalLocalFrame(LATITUDE, LONGITUDE)
    velocity = -frame.to_xy(float(ctx[-2]["latitude_deg"]), float(ctx[-2]["longitude_deg"])) / 3600
    forcing = field(east=(velocity[0],) * 3, north=(velocity[1],) * 3)
    candidate = model.build_origin_residual_candidate(ctx, forcing, group_id=model.GROUP_IDS[0])
    original_track = advect_current(forcing, latitude_deg=LATITUDE, longitude_deg=LONGITUDE,
        start_time_utc=model.ORIGIN, horizon_s=21600, step_s=300, output_step_s=3600)
    assert candidate["residual_east_north_m_s"] == [0.0, 0.0]
    assert candidate["advection"]["track"] == original_track["track"]
    assert candidate["advection"]["status"] == original_track["status"] == "COMPLETED"
    assert candidate["derived_field_sha256"] != candidate["source_field_sha256"]


def test_copy_has_actual_axes_masks_and_immutable_original_arrays_and_metadata():
    forcing = field()
    before = copy.deepcopy(forcing)
    result = model.corrected_field(forcing, [0.3, -0.2])
    for name in ("time_utc", "longitude_deg", "latitude_deg", "valid_mask"):
        assert np.array_equal(getattr(result, name), getattr(forcing, name))
        assert not np.shares_memory(getattr(result, name), getattr(forcing, name))
    assert np.array_equal(result.eastward_m_s, forcing.eastward_m_s + 0.3)
    result.metadata["source_field_provenance"]["nested"]["untouched"].append(3)
    for name in ("time_utc", "longitude_deg", "latitude_deg", "valid_mask",
                 "eastward_m_s", "northward_m_s"):
        assert np.array_equal(getattr(forcing, name), getattr(before, name))
    assert forcing.metadata == before.metadata


@pytest.mark.parametrize("residual", [[True, 0.0], ["0.3", "0.0"], [0.0, "1"],
                                     [0.0], [0.0, 0.0, 0.0], [float("nan"), 0.0]])
def test_residual_rejects_boolean_strings_nonfinite_and_wrong_shape(residual):
    with pytest.raises(ValueError):
        model.corrected_field(field(), residual)


def test_missing_context_preserves_upstream_failure_in_48_cell_plan():
    result = model.build_forecasts({}, {}, failures_by_group={model.GROUP_IDS[0]: "HTTP_TIMEOUT"})
    assert result["groups"][0]["candidates"][3]["reason_code"] == "HTTP_TIMEOUT"
    assert sum(len(c["cells"]) for g in result["groups"] for c in g["candidates"]) == 48


def test_corrected_east_only_piecewise_linear_flow_has_independent_exact_integral():
    forcing = model.corrected_field(field(), [0.3, 0.0])
    result = advect_current(forcing, latitude_deg=LATITUDE, longitude_deg=LONGITUDE,
        start_time_utc=model.ORIGIN, horizon_s=21600, step_s=300, output_step_s=3600)
    # Latitude is constant, so WGS84 metres per longitude degree is constant.
    # This exact oracle is valid for east-only flow, not general turning flow.
    f, a = 1 / 298.257223563, 6378137.0
    e2 = f * (2 - f)
    phi = math.radians(LATITUDE)
    metres_per_degree = math.pi / 180 * a * math.cos(phi) / math.sqrt(1 - e2 * math.sin(phi) ** 2)
    east_metres = ((0.5 + 1.0) / 2 + (1.0 + 0.4) / 2) * 10800
    assert result["track"][-1]["latitude_deg"] == LATITUDE
    assert result["track"][-1]["longitude_deg"] == pytest.approx(
        LONGITUDE + east_metres / metres_per_degree, abs=2e-12)


def test_turning_geographic_flow_matches_independent_dop853_reference_not_cartesian_integral():
    east, north, residual = np.array([0.2, 0.8, -0.1]), np.array([0.0, 0.6, -0.2]), [0.3, -0.1]
    forcing = model.corrected_field(field(east=east, north=north), residual)
    result = advect_current(forcing, latitude_deg=LATITUDE, longitude_deg=LONGITUDE,
        start_time_utc=model.ORIGIN, horizon_s=21600, step_s=300, output_step_s=3600)

    def derivative(t, position):
        phi = math.radians(position[0])
        a, f = 6378137.0, 1 / 298.257223563
        e2 = f * (2 - f)
        factor = 1 - e2 * math.sin(phi) ** 2
        east_scale = math.pi / 180 * a * math.cos(phi) / math.sqrt(factor)
        north_scale = math.pi / 180 * a * (1 - e2) / factor ** 1.5
        u = np.interp(t, [0, 10800, 21600], east) + residual[0]
        v = np.interp(t, [0, 10800, 21600], north) + residual[1]
        return [v / north_scale, u / east_scale]

    state = [LATITUDE, LONGITUDE]
    for begin, end in ((0, 10800), (10800, 21600)):
        reference = solve_ivp(derivative, (begin, end), state, method="DOP853",
                              rtol=2e-13, atol=2e-13, max_step=60)
        assert reference.success
        state = reference.y[:, -1]
    assert [result["track"][-1][key] for key in ("latitude_deg", "longitude_deg")] == pytest.approx(state, abs=2e-11)


@pytest.mark.parametrize("delta", [0, -3600, 1800, 3601, 7200])
def test_bad_context_cadence_fails_residual_only(delta):
    ctx = contexts()
    ctx[model.GROUP_IDS[0]][-2]["time_utc"] = (model.ORIGIN - timedelta(seconds=delta)).isoformat()
    result = model.build_forecasts(ctx, fields())
    assert result["groups"][0]["candidates"][3]["reason_code"] == "CONTEXT_CADENCE_MISMATCH"
    assert result["groups"][0]["candidates"][0]["status"] == "COMPLETED"
    assert result["groups"][0]["candidates"][2]["status"] == "COMPLETED"


@pytest.mark.parametrize(("change", "reason"), [
    ("origin_time", "ORIGIN_TIME_MISMATCH"), ("origin_nan", "INVALID_COORDINATE"),
    ("previous_nan", "INVALID_COORDINATE"), ("previous_id", "ID_MISMATCH"),
    ("far_previous", "LOCAL_GEOMETRY_BUDGET_EXCEEDED"),
])
def test_bad_fix_contract_is_explicit(change, reason):
    ctx = context(model.GROUP_IDS[0])
    if change == "origin_time":
        ctx[-1]["time_utc"] = (model.ORIGIN + timedelta(seconds=1)).isoformat()
    elif change == "previous_id":
        ctx[-2]["drifter_id"] = "wrong"
    elif change == "far_previous":
        ctx[-2]["longitude_deg"] = "-70"
    else:
        ctx[-1 if change == "origin_nan" else -2]["latitude_deg"] = "NaN"
    candidate = model.build_origin_residual_candidate(ctx, field(), group_id=model.GROUP_IDS[0])
    assert candidate["reason_code"] == reason
    assert candidate["available_count"] == 0 and len(candidate["cells"]) == 6


def test_masked_origin_and_future_gap_never_become_zero_filled_current():
    mask = np.ones((3, 2, 2), dtype=bool)
    mask[0] = False
    result = model.build_origin_residual_candidate(context(model.GROUP_IDS[0]), field(mask=mask), group_id=model.GROUP_IDS[0])
    assert result["status"] == "UNSUPPORTED" and result["reason_code"] == "MASKED_CURRENT_CELL"
    mask[:] = True
    mask[2] = False
    result = model.build_origin_residual_candidate(context(model.GROUP_IDS[0]), field(mask=mask), group_id=model.GROUP_IDS[0])
    assert result["status"] == "PARTIAL" and result["completed_horizon_s"] == 10800
    assert result["available_count"] == 3
    assert all(row["latitude_deg"] is None for row in result["cells"][3:])


def test_all_masked_field_is_explicitly_unavailable():
    result = model.build_origin_residual_candidate(context(model.GROUP_IDS[0]),
        field(mask=np.zeros((3, 2, 2), dtype=bool)), group_id=model.GROUP_IDS[0])
    assert result["reason_code"] == "CURRENT_FIELD_ALL_MASKED" and result["available_count"] == 0


def test_first23_context_values_are_not_new_residual_inputs():
    ctx = contexts()
    before = model.build_forecasts(ctx, fields())
    for rows in ctx.values():
        for row in rows[:23]:
            row["latitude_deg"], row["longitude_deg"] = "not read", "not read"
    assert model.build_forecasts(ctx, fields()) == before


def test_corrected_whole_grid_speed_excess_fails_without_clipping():
    result = model.build_origin_residual_candidate(context(model.GROUP_IDS[0]),
        field(east=(0, 9.9, 0)), group_id=model.GROUP_IDS[0])
    assert result["reason_code"] == "CORRECTED_FIELD_SPEED_BUDGET_EXCEEDED"
    assert result["available_count"] == 0


def test_domain_exit_retains_only_supported_prefix_and_no_artificial_hourly_tail():
    result = model.build_origin_residual_candidate(context(model.GROUP_IDS[0]),
        field(longitude=(-80, -79.45)), group_id=model.GROUP_IDS[0])
    assert result["status"] == "PARTIAL"
    assert result["reason_code"] == "OUTSIDE_CURRENT_DOMAIN"
    assert result["available_count"] < 6
    assert result["advection"]["track"][-1]["elapsed_s"] == result["completed_horizon_s"]
    assert all(cell["latitude_deg"] is None for cell in result["cells"] if cell["elapsed_s"] > result["completed_horizon_s"])


@pytest.mark.parametrize("supplied", [None, "invalid", 17])
def test_missing_or_invalid_field_has_no_silent_fallback(supplied):
    result = model.build_origin_residual_candidate(context(model.GROUP_IDS[0]), supplied, group_id=model.GROUP_IDS[0])
    assert result["available_count"] == 0
    assert result["reason_code"] == ("CURRENT_FIELD_UNAVAILABLE" if supplied is None else "CURRENT_CONFIGURATION_INVALID")


def test_all48_cells_and_missing_targets_are_retained_with_primary_withheld():
    forecasts = model.build_forecasts(contexts(), {})
    scored = model.score_forecasts(forecasts, targets())
    assert scored["planned_cell_count"] == 48 and scored["planned_distinct_target_count"] == 12
    assert scored["scored_cell_count"] == 24
    assert scored["primary_common_cohort_complete"] is False
    assert scored["primary_equal_id_macro_results"] is None
    assert all(row["analysis_scope"] == "SECONDARY_COMMON_AVAILABLE_CELLS" for row in scored["paired_comparisons"])
    assert sum(len(c["cells"]) for g in scored["groups"] for c in g["candidates"]) == 48
    absent = model.score_forecasts(model.build_forecasts({}, {}), {})
    assert absent["scored_cell_count"] == 0 and len(absent["models"]) == 4


def test_complete48_scores_have_equal_id_macros_and_common_pair_denominators():
    forecasts = model.build_forecasts(contexts(), fields())
    before = copy.deepcopy(forecasts)
    scored = model.score_forecasts(forecasts, targets())
    assert forecasts == before
    assert scored["scored_cell_count"] == 48 and scored["primary_common_cohort_complete"] is True
    assert len(scored["primary_equal_id_macro_results"]) == 4
    assert len(scored["paired_comparisons"]) == 6
    assert all(row["common_scored_count"] == 12 for row in scored["paired_comparisons"])
    assert scored["automatic_winner_selected"] is False
    assert scored["physical_validation"] is False


def test_no_target_number_is_read_until_every_forecast_and_hash_exists():
    state = {"built": False}

    class Future(str):
        def __float__(self):
            assert state["built"]
            return float(str(self))

    held = targets()
    for rows in held.values():
        for row in rows:
            row["latitude_deg"] = Future(row["latitude_deg"])
    forecasts = model.build_forecasts(contexts(), fields())
    assert forecasts["forecast_sha256"] == model.forecast_sha256(forecasts)
    assert all(len(g["candidates"]) == 4 for g in forecasts["groups"])
    state["built"] = True
    assert model.score_forecasts(forecasts, held)["scored_cell_count"] == 48


def test_invalid_forecast_hash_or_rehashed_coordinates_fail_before_target_access():
    forecasts = model.build_forecasts(contexts(), fields())
    forecasts["groups"][0]["candidates"][3]["cells"][0]["latitude_deg"] = float("nan")
    with pytest.raises(ValueError):
        model.score_forecasts(forecasts, {})
    forecasts = model.build_forecasts(contexts(), fields())
    forecasts["groups"][0]["candidates"][3]["cells"][0]["latitude_deg"] = 100.0
    forecasts["forecast_sha256"] = model.forecast_sha256(forecasts)
    with pytest.raises(ValueError, match="INVALID_COORDINATE"):
        model.score_forecasts(forecasts, {})


def test_missing_bad_and_duplicate_targets_remain_unknown_in_planned_denominator():
    forecasts = model.build_forecasts(contexts(), fields())
    held = targets()
    held[model.GROUP_IDS[0]][2]["latitude_deg"] = "NaN"
    held[model.GROUP_IDS[1]].append(copy.deepcopy(held[model.GROUP_IDS[1]][0]))
    held[model.GROUP_IDS[1]][-1]["latitude_deg"] = "invalid"
    scored = model.score_forecasts(forecasts, held)
    assert scored["scored_cell_count"] == 40
    assert scored["primary_equal_id_macro_results"] is None
    assert "DUPLICATE_TARGET_TIME" in scored["groups"][1]["target_issues"]


@pytest.fixture
def synthetic_runner(monkeypatch):
    hashes = {"protocol_sha256": "b" * 64, "manifest_sha256": "c" * 64}
    pins = {"forecasts.json": "d" * 64, "evaluation.json": "e" * 64, "manifest.json": "f" * 64}
    held = targets()
    forcing = field()
    monkeypatch.setattr(runner, "_source_pins", lambda: pins)
    monkeypatch.setattr(runner, "_committed_method", lambda: "1" * 40)
    monkeypatch.setattr(runner.source, "_inputs", lambda directory: (
        {}, {}, hashes, contexts(), held, None, forcing, None))
    monkeypatch.setattr(runner, "load_acquisition", lambda directory: ({}, {}, hashes, {}))
    return held


def test_default_read_never_scores_or_creates_a_missing_diagnostic(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Read-only default must not build or score")

    monkeypatch.setattr(model, "build_forecasts", forbidden)
    monkeypatch.setattr(model, "score_forecasts", forbidden)
    target = tmp_path / "absent"
    with pytest.raises(FileNotFoundError):
        runner.read_diagnostic(target)
    assert not target.exists()


def test_first_score_persists_all_four_and_reads_back_before_numeric_target_decode(
        tmp_path, synthetic_runner, monkeypatch):
    directory = tmp_path / "synthetic"
    numeric_reads = []

    class Future(str):
        def __float__(self):
            document, digest = runner._load(directory / "forecasts.json")
            assert document["forecasts"]["forecast_sha256"] == model.forecast_sha256(document["forecasts"])
            assert sum(len(c["cells"]) for g in document["forecasts"]["groups"] for c in g["candidates"]) == 48
            assert len(digest) == 64
            numeric_reads.append(True)
            return float(str(self))

    for rows in synthetic_runner.values():
        for row in rows:
            row["latitude_deg"] = Future(row["latitude_deg"])
    report = runner.first_score(directory)
    assert len(numeric_reads) == 12 and report["scores"]["scored_cell_count"] == 48
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    monkeypatch.setattr(model, "build_forecasts", lambda *a, **kw: pytest.fail("reader built forecasts"))
    monkeypatch.setattr(model, "score_forecasts", lambda *a, **kw: pytest.fail("reader scored targets"))
    view = runner.read_diagnostic(directory)
    assert view["report"] == report
    assert view["artifact_identity"]["external_result_pin_verified"] is False
    identity_sha = runner._load(directory / "identity.json")[1]
    assert runner.read_diagnostic(directory, expected_identity_sha256=identity_sha)["artifact_identity"]["external_result_pin_verified"] is True
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == before
    with pytest.raises(ValueError, match="never overwrite"):
        runner.first_score(directory)


def test_failed_readback_never_decodes_or_scores_targets_and_attempt_is_not_retried(
        tmp_path, synthetic_runner, monkeypatch):
    directory = tmp_path / "synthetic"
    monkeypatch.setattr(runner, "_load", lambda path: ({}, "0" * 64))
    monkeypatch.setattr(model, "score_forecasts", lambda *a, **kw: pytest.fail("scored after failed readback"))
    with pytest.raises(ValueError, match="persisted and read back"):
        runner.first_score(directory)
    assert (directory / "forecasts.json").exists()
    assert not (directory / "evaluation.json").exists()
    with pytest.raises(ValueError, match="never overwrite"):
        runner.first_score(directory)


def test_saved_artifact_tampering_and_external_pin_mismatch_are_rejected(tmp_path, synthetic_runner):
    directory = tmp_path / "synthetic"
    runner.first_score(directory)
    with pytest.raises(ValueError, match="external diagnostic result identity"):
        runner.read_diagnostic(directory, expected_identity_sha256="0" * 64)
    path = directory / "forecasts.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="detached hash"):
        runner.read_diagnostic(directory)


def test_method_must_be_committed_before_any_new_diagnostic_attempt(tmp_path, synthetic_runner, monkeypatch):
    directory = tmp_path / "synthetic"

    def uncommitted():
        raise ValueError("Commit reviewed sources first")

    monkeypatch.setattr(runner, "_committed_method", uncommitted)
    with pytest.raises(ValueError, match="Commit reviewed"):
        runner.first_score(directory)
    assert not directory.exists()
