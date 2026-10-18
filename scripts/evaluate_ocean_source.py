"""Read a saved ocean-source diagnostic; execution requires explicit --first-score.

No network or scientific execution occurs on import/default read. First scoring
requires the exact protocol and method sources committed, saves and reads back
ALL inference/closure outputs before decoding separate earlier-position truth,
and never overwrites an existing attempt. Earlier targets are already viewed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from apps.ocean.reeftrace_ocean import ocean_source as model
from apps.ocean.reeftrace_ocean import ocean_source_pipeline as pipeline
from apps.ocean.reeftrace_ocean.matched_current_v2_protocol import load_acquisition
from apps.ocean.reeftrace_ocean.matched_current_v2_result_identity import (
    FORECAST_SHA256,
    MANIFEST_SHA256,
    REPORT_SHA256,
)
from scripts import evaluate_matched_current_v2_study as source

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "data/research/ocean-source-v1"
SOURCE_DIRECTORY = ROOT / "data/research/matched-current-v2"
METHOD_FILES = ("apps/ocean/reeftrace_ocean/ocean_source.py", "scripts/evaluate_ocean_source.py",
                "tests/unit/test_ocean_source.py", "apps/ocean/reeftrace_ocean/ocean_source_pipeline.py",
                "tests/unit/test_ocean_source_pipeline.py")
PROTOCOL_PATH = "data/research/ocean-source-v1/protocol.json"
MAX_FILE_BYTES = 4_194_304


def _raw(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Ocean-source artifacts cannot be symlinks")
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("Ocean-source artifact exceeds its byte budget")
    return raw


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _save(path, value):
    raw = _canonical(value)
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("Ocean-source artifact exceeds its byte budget")
    with path.open("xb") as stream:
        stream.write(raw)
    with path.with_suffix(".sha256").open("x") as stream:
        stream.write(_sha(raw) + "\n")
    return _sha(raw)


def _load(path):
    raw = _raw(path)
    if _raw(path.with_suffix(".sha256")) != (_sha(raw) + "\n").encode():
        raise ValueError("Ocean-source detached hash changed")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Ocean-source artifact must be an object")  # noqa: TRY004 - saved artifact contract
    return value, _sha(raw)


def _method_hashes():
    return {name: _sha(_raw(ROOT / name)) for name in METHOD_FILES}


def _source_pins():
    pins = {"forecasts.json": FORECAST_SHA256, "evaluation.json": REPORT_SHA256,
            "manifest.json": MANIFEST_SHA256}
    if any(_sha(_raw(SOURCE_DIRECTORY / name)) != value for name, value in pins.items()):
        raise ValueError("The immutable matched-current v2 source changed")
    return pins


def make_protocol():
    """Freeze-ready method specification; no trajectory/current decoding or fits."""
    return {"schema_version": 1, "kind": "OCEAN_SOURCE_EXPLORATORY_PROTOCOL", "study_id": model.STUDY_ID,
        "analysis_scope": "POST_OUTCOME_EXPLORATORY", "previously_viewed_earlier_positions": True,
        "confirmatory": False, "group_ids": list(model.GROUP_IDS), "model_ids": list(model.MODEL_IDS),
        "observation_time_utc": model.OBSERVATION_TIME_UTC,
        "penultimate_time_utc": "2022-06-01T05:00:00Z", "earlier_time_utc": model.EARLIER_TIME_UTC,
        "inference_inputs": "final06Z_and_penultimate05Z_only; penultimate used by last-drift baseline only",
        "earlier_truth_scope": "00Z_evaluator_only_after_all_inference_outputs_persisted_and_readback",
        "maximum_lookback_s": model.HORIZON_S, "solver_step_s": model.STEP_S,
        "output_step_s": model.STEP_S, "lookback_hours": list(model.LOOKBACK_HOURS),
        "reverse_equation": "dY/dtau=-(u(Y,t_observed-tau)+constant_forward_current_bias)",
        "time_transform": "pseudo_UTC=t_observed+tau; actual_UTC=t_observed-tau",
        "endpoint_offsets_east_north_m": [[name, x, y] for name, x, y in model.OFFSETS],
        "current_biases_east_north_m_s": [[name, u, v] for name, u, v in model.BIASES],
        "scenarios_per_group": 25, "nominal_scenario_id": "center|zero",
        "offset_geometry": "origin_anchored_mean_sphere_log_exp",
        "last_drift_geometry": "endpoint_anchored_mean_sphere_final_hour_displacement_times_six;50km_budget",
        "solver": "unchanged bounded WGS84 RK4; reversed actual axes/mask/time; no fill or clipping",
        "current_depth_m": 15, "maximum_speed_m_s": 10,
        "closure": "nominal_00Z_estimate_advected_forward_on_unmodified_field_to06Z;not_real_accuracy",
        "score": "great_circle_distance_to_recorded00Z; mean per model only if all six rows scored",
        "planned_model_rows": 6, "planned_distinct_earlier_positions": 2,
        "pipeline_tutorial": {"kind": "THREE_FIX_BIDIRECTIONAL_RESEARCH_WALKTHROUGH",
            "inference_times_utc": list(pipeline.OBSERVATION_TIMES), "anchor_time_utc": pipeline.ANCHOR_TIME,
            "validation_times_utc": list(pipeline.TRUTH_TIMES), "planned_validation_rows": 8,
            "branches_horizon_s": pipeline.BRANCH_HORIZON_S,
            "frame": "mean_sphere_log_exp_anchored_at_first_allowed01Z_fix",
            "filter": "causal01position_only_02twofix_initialization_03measurement_update;no_RTS",
            "state_units": "[east_m,north_m,eastward_m_s,northward_m_s]",
            "position_std_m": pipeline.POSITION_STD_M,
            "acceleration_spectral_density_m2_s3": pipeline.ACCELERATION_SPECTRAL_DENSITY_M2_S3,
            "covariance_update": "Joseph; gain=solve(S,H@P).T",
            "residual": "constant local ENU b=filtered_velocity03-current(filtered_position03,03)",
            "equations": pipeline.STAGES, "limitations": pipeline.LIMITATIONS,
            "observed_truth_used_by_inference": False, "probabilities_or_calibrated_region": False,
            "execution_order": "build_both_tutorial_groups01_02_03_save_readback_then_decode05_06_for_separate_base_then_save_readback_combined_then_score00_and04_05_06"},
        "source_artifact_pins": _source_pins(), "method_source_sha256": _method_hashes(),
        "pinned_numerical_dependencies": {name: _sha(_raw(ROOT / name)) for name in (
            "apps/ocean/reeftrace_ocean/advection.py", "apps/ocean/reeftrace_ocean/field.py",
            "apps/ocean/reeftrace_ocean/benchmark.py", "apps/ocean/reeftrace_ocean/hycom.py",
            "apps/ocean/reeftrace_ocean/kalman.py",
            "apps/ocean/reeftrace_ocean/matched_current_v2_protocol.py",
            "apps/ocean/reeftrace_ocean/matched_current_v2_result_identity.py",
            "scripts/evaluate_matched_current_v2_study.py")},
        "source_attribution_validated": False, "physical_validation": False,
        "probabilities_or_calibrated_region": False, "automatic_model_promotion": False,
        "network_acquisition": False, "provider_calls": False, "limitations": list(model.LIMITATIONS)}


def _verify_protocol(directory):
    protocol = json.loads(_raw(directory / "protocol.json"))
    expected = make_protocol()
    if protocol != expected:
        raise ValueError("Ocean-source protocol, source pins or exact method bytes changed")
    return protocol, _sha(_raw(directory / "protocol.json"))


def _committed_method():
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                              capture_output=True, timeout=10).stdout.decode().strip()
        for name in (*METHOD_FILES, PROTOCOL_PATH):
            raw = subprocess.run(["git", "show", f"HEAD:{name}"], cwd=ROOT, check=True,
                                 capture_output=True, timeout=10).stdout
            if raw != _raw(ROOT / name):
                raise ValueError("Commit the exact reviewed ocean-source method and protocol before scoring")
    except (subprocess.SubprocessError, UnicodeError):
        raise ValueError("Committed reviewed ocean-source methods and protocol are required") from None
    return head


def _source_inputs():
    """Identity/time/structure checks leave all unneeded coordinates as strings."""
    _protocol, manifest, hashes, payloads = load_acquisition(SOURCE_DIRECTORY)
    if manifest is None:
        raise ValueError("The frozen v2 acquisition is unavailable")
    receipts = {row["role"]: row for row in manifest["source_receipts"]}
    observations, truth, tutorial_observations, tutorial_truth = {}, {}, {}, {}
    failures = {}
    for group in model.GROUP_IDS:
        payload = payloads.get("trajectory:" + group)
        if payload is None:
            failures[group] = "GDP_PAYLOAD_UNAVAILABLE"
            continue
        try:
            context, later = source.parse_position_strings(payload, group)
        except ValueError:
            failures[group] = "GDP_SCHEMA_OR_IDENTITY_UNSUPPORTED"
            continue
        rows = {row["time_utc"]: row for row in context + later}
        observations[group] = [rows["2022-06-01T05:00:00Z"], rows[model.OBSERVATION_TIME_UTC]]
        truth[group] = rows[model.EARLIER_TIME_UTC]  # Strings, not decoded or passed to inference.
        tutorial_observations[group] = [rows[time] for time in pipeline.OBSERVATION_TIMES]
        tutorial_truth[group] = {time: rows[time] for time in pipeline.TRUTH_TIMES}
    field, field_failure = None, None
    payload = payloads.get("hycom_currents")
    if payload is None:
        field_failure = "HYCOM_PAYLOAD_UNAVAILABLE"
    else:
        try:
            field = source._study_field(payload)
            if field.metadata.get("sha256") != receipts["hycom_currents"]["sha256"]:
                raise ValueError("HYCOM_FIELD_BYTE_IDENTITY_CHANGED")
        except (ValueError, TypeError, ImportError):
            field, field_failure = None, "HYCOM_FIELD_CONTRACT_UNSUPPORTED"
    return observations, truth, tutorial_observations, tutorial_truth, field, field_failure, hashes, failures


def first_score(directory=DIRECTORY):
    """Only explicit committed execution; retain any attempt and refuse overwrites."""
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("The committed protocol directory must exist")
    if any(path.name != "protocol.json" for path in directory.iterdir()):
        raise ValueError("An ocean-source attempt already exists; never overwrite artifacts")
    protocol, protocol_sha = _verify_protocol(directory)
    head = _committed_method()
    (observations, reserved, tutorial_observations, tutorial_reserved, field, failure,
     lineage, input_failures) = _source_inputs()
    _save(directory / "attempt.json", {"schema_version": 1, "kind": "EXCLUSIVE_OCEAN_SOURCE_ATTEMPT",
        "protocol_sha256": protocol_sha, "reviewed_code_commit": head,
        "started_at_utc": datetime.now(UTC).isoformat(), "source_acquisition_lineage": lineage})
    tutorial = pipeline.build_pipeline_forecasts(tutorial_observations, field, field_failure=failure)
    tutorial_document = {"schema_version": 1, "kind": "FROZEN_THREE_FIX_PIPELINE_FORECASTS",
        "study_id": model.STUDY_ID, "protocol_sha256": protocol_sha, "forecasts": tutorial,
        "validation_truth_decoded": False, "source_acquisition_lineage": lineage,
        "frozen_at_utc": datetime.now(UTC).isoformat()}
    tutorial_file_sha = _save(directory / "pipeline-forecasts.json", tutorial_document)
    saved_tutorial, tutorial_readback_sha = _load(directory / "pipeline-forecasts.json")
    if saved_tutorial != tutorial_document or tutorial_readback_sha != tutorial_file_sha:
        raise ValueError("Both tutorial groups must be saved and read back before any05/06 coordinate decode")
    # The independent endpoint study may now decode its05/06 inputs. Neither
    # tutorial forecast can change after seeing those coordinates.
    forecasts = model.build_ocean_source_forecasts(observations, field, field_failure=failure)
    forecasts["pipeline_tutorial"] = saved_tutorial["forecasts"]
    forecasts["forecast_sha256"] = model.forecast_sha256(forecasts)
    document = {"schema_version": 1, "kind": "FROZEN_OCEAN_SOURCE_FORECASTS", "study_id": model.STUDY_ID,
        "protocol_sha256": protocol_sha, "forecasts": forecasts,
        "earlier_truth_decoded": False, "tutorial_validation_scoring_started": False,
        "pipeline_forecast_file_sha256": tutorial_file_sha, "input_failures": input_failures,
        "source_acquisition_lineage": lineage, "frozen_at_utc": datetime.now(UTC).isoformat()}
    forecast_file_sha = _save(directory / "forecasts.json", document)
    saved, readback_sha = _load(directory / "forecasts.json")
    if saved != document or readback_sha != forecast_file_sha:
        raise ValueError("Every inference output must be saved and read back before earlier truth decode")
    validation = model.score_ocean_source_forecasts(saved["forecasts"], reserved)
    tutorial_validation = pipeline.score_pipeline_forecasts(saved["forecasts"]["pipeline_tutorial"], tutorial_reserved)
    result = {"schema_version": 1, "kind": "OCEAN_SOURCE_EXPLORATORY_RESULT", "study_id": model.STUDY_ID,
        "protocol_sha256": protocol_sha, "forecast_file_sha256": forecast_file_sha,
        "pipeline_forecast_file_sha256": tutorial_file_sha,
        "pipeline_saved_before_any05_06_position_decode": True,
        "analysis_scope": "POST_OUTCOME_EXPLORATORY", "previously_viewed_earlier_positions": True,
        "forecasts_saved_before_earlier_truth_decode": True,
        "forecast_frozen_at_utc": document["frozen_at_utc"], "scored_at_utc": datetime.now(UTC).isoformat(),
        "reviewed_code_commit": head, "source_artifact_pins": protocol["source_artifact_pins"],
        "source_acquisition_lineage": lineage, "method_source_sha256": protocol["method_source_sha256"],
        "forecasts": saved["forecasts"], "validation": validation,
        "pipeline_tutorial": {"kind": "THREE_FIX_BIDIRECTIONAL_RESEARCH_WALKTHROUGH",
            "forecasts": saved["forecasts"]["pipeline_tutorial"], "validation": tutorial_validation},
        "all_tutorial_forecasts_saved_before_validation_truth_decode": True,
        "new_data_acquisition": False, "provider_calls": False, "physical_validation": False,
        "source_attribution_validated": False, "automatic_model_promotion": False,
        "limitations": list(model.LIMITATIONS)}
    if _verify_protocol(directory)[1] != protocol_sha:
        raise ValueError("Protocol changed during execution")
    report_sha = _save(directory / "evaluation.json", result)
    _save(directory / "identity.json", {"schema_version": 1, "kind": "OCEAN_SOURCE_RESULT_IDENTITY",
        "study_id": model.STUDY_ID, "protocol_sha256": protocol_sha,
        "forecast_file_sha256": forecast_file_sha, "report_sha256": report_sha,
        "pipeline_forecast_file_sha256": tutorial_file_sha,
        "externally_trusted_pin_required_for_publication": True})
    return result


def read_result(directory=DIRECTORY, *, expected_identity_sha256=None):
    """Saved-byte/lineage checks only: never call inference, closure, scoring or network acquisition."""
    directory = Path(directory)
    if directory.is_symlink():
        raise ValueError("A symlinked result directory is not accepted")
    identity, identity_sha = _load(directory / "identity.json")
    if expected_identity_sha256 is not None and identity_sha != expected_identity_sha256:
        raise ValueError("The externally pinned ocean-source result changed")
    protocol, protocol_sha = _verify_protocol(directory)
    _source_protocol, _source_manifest, source_lineage, _source_payloads = load_acquisition(SOURCE_DIRECTORY)
    forecasts, forecast_file_sha = _load(directory / "forecasts.json")
    tutorial_document, tutorial_file_sha = _load(directory / "pipeline-forecasts.json")
    result, report_sha = _load(directory / "evaluation.json")
    attempt, _ = _load(directory / "attempt.json")
    if identity != {"schema_version": 1, "kind": "OCEAN_SOURCE_RESULT_IDENTITY", "study_id": model.STUDY_ID,
            "protocol_sha256": protocol_sha, "forecast_file_sha256": forecast_file_sha,
            "report_sha256": report_sha, "pipeline_forecast_file_sha256": tutorial_file_sha,
            "externally_trusted_pin_required_for_publication": True}:
        raise ValueError("Ocean-source artifact identities disagree")
    if (result.get("forecasts") != forecasts.get("forecasts")
            or model.forecast_sha256(result["forecasts"]) != result["forecasts"].get("forecast_sha256")
            or result.get("protocol_sha256") != protocol_sha or forecasts.get("protocol_sha256") != protocol_sha
            or result.get("forecast_file_sha256") != forecast_file_sha
            or result.get("pipeline_forecast_file_sha256") != tutorial_file_sha
            or forecasts.get("pipeline_forecast_file_sha256") != tutorial_file_sha
            or tutorial_document.get("forecasts") != result["forecasts"].get("pipeline_tutorial")
            or tutorial_document.get("protocol_sha256") != protocol_sha
            or tutorial_document.get("source_acquisition_lineage") != source_lineage
            or result.get("method_source_sha256") != protocol["method_source_sha256"]
            or result.get("source_artifact_pins") != protocol["source_artifact_pins"]
            or result.get("forecast_frozen_at_utc") != forecasts.get("frozen_at_utc")
            or attempt.get("protocol_sha256") != protocol_sha
            or result.get("reviewed_code_commit") != attempt.get("reviewed_code_commit")
            or result.get("source_acquisition_lineage") != attempt.get("source_acquisition_lineage")
            or result.get("source_acquisition_lineage") != forecasts.get("source_acquisition_lineage")
            or result.get("source_acquisition_lineage") != source_lineage):
        raise ValueError("Ocean-source method, forecast or source lineage changed")
    times = [_clock(attempt.get("started_at_utc")), _clock(tutorial_document.get("frozen_at_utc")),
             _clock(forecasts.get("frozen_at_utc")),
             _clock(result.get("scored_at_utc"))]
    if times != sorted(times):
        raise ValueError("Ocean-source forecast/score chronology changed")
    if (result.get("analysis_scope") != "POST_OUTCOME_EXPLORATORY"
            or result.get("previously_viewed_earlier_positions") is not True
            or result.get("forecasts_saved_before_earlier_truth_decode") is not True
            or result.get("all_tutorial_forecasts_saved_before_validation_truth_decode") is not True
            or forecasts.get("earlier_truth_decoded") is not False
            or forecasts.get("tutorial_validation_scoring_started") is not False
            or tutorial_document.get("validation_truth_decoded") is not False
            or result.get("pipeline_saved_before_any05_06_position_decode") is not True
            or result.get("kind") != "OCEAN_SOURCE_EXPLORATORY_RESULT"
            or result.get("study_id") != model.STUDY_ID
            or result.get("schema_version") != 1
            or model.forecast_sha256(result["forecasts"].get("pipeline_tutorial", {}))
                != result["forecasts"].get("pipeline_tutorial", {}).get("forecast_sha256")
            or result.get("pipeline_tutorial", {}).get("forecasts") != result["forecasts"].get("pipeline_tutorial")
            or any(result.get(key) is not False for key in (
                "new_data_acquisition", "provider_calls", "physical_validation",
                "source_attribution_validated", "automatic_model_promotion"))):
        raise ValueError("Ocean-source scientific scope changed")
    for name, expected in (("identity", identity_sha), ("forecasts", forecast_file_sha),
                           ("evaluation", report_sha), ("pipeline-forecasts", tutorial_file_sha)):
        if _load(directory / (name + ".json"))[1] != expected:
            raise ValueError("Ocean-source artifacts changed during read")
    if _verify_protocol(directory)[1] != protocol_sha:
        raise ValueError("Ocean-source protocol changed during read")
    return {"report": result, "artifact_identity": {**identity, "identity_sha256": identity_sha,
        "integrity_verified": True, "external_result_pin_verified": expected_identity_sha256 is not None,
        "numeric_replay_verified": False, "verification_scope": "SAVED_BYTES_AND_LINEAGE_NOT_NUMERIC_REPLAY"}}


def _clock(value):
    try:
        result = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("A UTC execution receipt is required") from None
    if result.utcoffset() is None or result.utcoffset().total_seconds() != 0:
        raise ValueError("A UTC execution receipt is required")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-score", action="store_true")
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    args = parser.parse_args(argv)
    value = first_score(args.directory) if args.first_score else read_result(args.directory)
    print(json.dumps(value, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
