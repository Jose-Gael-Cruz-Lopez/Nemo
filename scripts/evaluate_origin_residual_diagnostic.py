"""Read a saved exploratory diagnostic; first scoring requires --first-score.

The completed v2 source study is immutable. This script never downloads, repairs
or re-scores that source experiment. Its separate first-score mode requires all
method sources committed, writes new exclusive artifacts, then reads every
forecast back before decoding this diagnostic's already-viewed target numbers.
The default is a read-only integrity check, not a new numerical replay.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from apps.ocean.reeftrace_ocean import origin_residual as model
from apps.ocean.reeftrace_ocean.matched_current_v2_protocol import load_acquisition
from apps.ocean.reeftrace_ocean.matched_current_v2_result_identity import (
    FORECAST_SHA256,
    MANIFEST_SHA256,
    REPORT_SHA256,
)
from scripts import evaluate_matched_current_v2_study as source

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "data/research/origin-residual-v1"
SOURCE_DIRECTORY = source.DIRECTORY
METHOD_FILES = (
    "apps/ocean/reeftrace_ocean/origin_residual.py",
    "scripts/evaluate_origin_residual_diagnostic.py",
    "tests/unit/test_origin_residual.py",
)
MAX_FILE_BYTES = 4_194_304


def _raw(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Diagnostic artifacts must not be symlinks")
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("Diagnostic artifact exceeds its bounded byte budget")
    return raw


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _save(path, value):
    raw = _canonical(value)
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("Diagnostic artifact exceeds its bounded byte budget")
    with path.open("xb") as stream:
        stream.write(raw)
    with path.with_suffix(".sha256").open("x") as stream:
        stream.write(_sha(raw) + "\n")
    return _sha(raw)


def _load(path):
    raw = _raw(path)
    detached = _raw(path.with_suffix(".sha256"))
    if len(detached) != 65 or detached != (_sha(raw) + "\n").encode():
        raise ValueError("Diagnostic artifact detached hash changed")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise TypeError("Diagnostic artifact must be an object")
    return value, _sha(raw)


def _method_hashes():
    return {relative: _sha(_raw(ROOT / relative)) for relative in METHOD_FILES}


def _committed_method():
    """Require the exact reviewed source bytes in HEAD before an actual first score."""
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                              capture_output=True, timeout=10).stdout.decode().strip()
        for relative in METHOD_FILES:
            committed = subprocess.run(["git", "show", f"HEAD:{relative}"], cwd=ROOT,
                check=True, capture_output=True, timeout=10).stdout
            if committed != _raw(ROOT / relative):
                raise ValueError("Commit the exact reviewed diagnostic sources before first scoring")
    except (subprocess.SubprocessError, UnicodeError):
        raise ValueError("Committed reviewed diagnostic sources are required before first scoring") from None
    return head


def _source_pins():
    """Hash original outcomes without decoding any target number for this run."""
    pins = {"forecasts.json": FORECAST_SHA256, "evaluation.json": REPORT_SHA256,
            "manifest.json": MANIFEST_SHA256}
    for name, expected in pins.items():
        if _sha(_raw(SOURCE_DIRECTORY / name)) != expected:
            raise ValueError("The trusted immutable v2 source artifact changed")
    return pins


def _clock(value):
    try:
        when = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("Diagnostic requires a timezone-aware UTC clock") from None
    if when.utcoffset() is None or when.utcoffset().total_seconds() != 0:
        raise ValueError("Diagnostic requires a timezone-aware UTC clock")
    return when


def _contract(hashes, source_pins, head):
    return {"schema_version": 1, "kind": "POST_OUTCOME_EXPLORATORY_METHOD_CONTRACT",
        "study_id": model.STUDY_ID, "analysis_scope": "POST_OUTCOME_EXPLORATORY",
        "previously_viewed_target_outcomes": True, "confirmatory": False,
        "models": list(model.MODEL_IDS), "groups": list(model.GROUP_IDS),
        "origin_time_utc": model.ORIGIN_TIME_UTC, "horizons_s": list(model.HORIZONS_S),
        "planned_cell_count": model.PLANNED_CELLS,
        "planned_distinct_target_count": model.PLANNED_DISTINCT_TARGETS,
        "residual": "v_last_origin_mean_sphere_minus_current_at_origin",
        "residual_transport": "constant_local_east_north_m_s",
        "coefficient_fitting": False, "decay_or_clipping": False,
        "source_study_id": "matched-current-gdp-hycom-15m-v2",
        "source_artifact_pins": source_pins, "source_acquisition_lineage": hashes,
        "method_source_sha256": _method_hashes(), "reviewed_code_commit": head,
        "maximum_speed_m_s": 10, "maximum_horizon_s": 21600,
        "requested_step_s": 300, "hourly_output_s": 3600,
        "primary_requires_all_cells": True,
        "forecast_and_score_clock_kind": "local_execution_receipt_not_external_attestation",
        "physical_validation": False, "automatic_model_promotion": False}


def first_score(directory: Path = DIRECTORY) -> dict:
    """Create one new diagnostic; refuse any existing attempt and never repair it."""
    directory = Path(directory)
    if directory.exists() or directory.is_symlink():
        raise ValueError("A diagnostic attempt already exists; never overwrite its artifacts")
    pins = _source_pins()
    head = _committed_method()
    (_protocol, _manifest, hashes, contexts, targets, _original_forecasts,
     forcing, current_failure) = source._inputs(SOURCE_DIRECTORY)
    contract = _contract(hashes, pins, head)
    # The directory is itself an exclusive attempt sentinel. Any failed attempt
    # stays visible and cannot silently be retried into the same identity.
    directory.mkdir(parents=True, exist_ok=False)
    contract["frozen_at_utc"] = datetime.now(UTC).isoformat()
    contract_sha = _save(directory / "protocol.json", contract)
    fields = dict.fromkeys(model.GROUP_IDS, forcing) if forcing is not None else {}
    failures = dict.fromkeys(model.GROUP_IDS, current_failure) if current_failure else {}
    forecasts = model.build_forecasts(contexts, fields, current_failures_by_group=failures)
    document = {"schema_version": 1, "kind": "FROZEN_ORIGIN_RESIDUAL_EXPLORATORY_FORECASTS",
        "study_id": model.STUDY_ID, "protocol_sha256": contract_sha,
        "source_artifact_pins": pins, "future_coordinates_decoded_in_this_diagnostic": False,
        "previously_viewed_target_outcomes": True, "forecasts": forecasts,
        "frozen_at_utc": datetime.now(UTC).isoformat()}
    if _clock(document["frozen_at_utc"]) < _clock(contract["frozen_at_utc"]):
        raise ValueError("Forecast receipt predates the exploratory method receipt")
    forecast_file_sha = _save(directory / "forecasts.json", document)
    saved, readback_sha = _load(directory / "forecasts.json")
    if (saved != document or forecast_file_sha != readback_sha
            or saved["forecasts"]["forecast_sha256"] != model.forecast_sha256(forecasts)):
        raise ValueError("All four prior forecast candidates must be persisted and read back before scoring")
    # This is the first numeric target decode in this diagnostic. These targets
    # were viewed in the prior v2 study; this ordering does not make them unseen.
    scores = model.score_forecasts(forecasts, targets)
    result = {"schema_version": 1, "kind": "ORIGIN_RESIDUAL_EXPLORATORY_DIAGNOSTIC",
        "study_id": model.STUDY_ID, "protocol_sha256": contract_sha,
        "forecast_file_sha256": forecast_file_sha,
        "forecast_frozen_at_utc": document["frozen_at_utc"],
        "source_artifact_pins": pins, "method_source_sha256": contract["method_source_sha256"],
        "source_acquisition_lineage": hashes, "scores": scores,
        "all_four_forecasts_saved_before_this_diagnostic_target_decode": True,
        "previously_viewed_target_outcomes": True, "analysis_scope": "POST_OUTCOME_EXPLORATORY",
        "new_data_acquisition": False, "frozen_source_study_changed": False,
        "provider_calls": False, "physical_validation": False,
        "scored_at_utc": datetime.now(UTC).isoformat()}
    if _clock(result["scored_at_utc"]) < _clock(document["frozen_at_utc"]):
        raise ValueError("Score receipt predates the forecast receipt")
    if _source_pins() != pins or _method_hashes() != contract["method_source_sha256"]:
        raise ValueError("Source inputs or method changed during the diagnostic")
    result_sha = _save(directory / "evaluation.json", result)
    identity = {"schema_version": 1, "kind": "ORIGIN_RESIDUAL_LOCAL_RESULT_IDENTITY",
        "study_id": model.STUDY_ID, "protocol_sha256": contract_sha,
        "forecast_file_sha256": forecast_file_sha, "report_sha256": result_sha,
        "externally_trusted_pin_required_for_publication": True}
    _save(directory / "identity.json", identity)
    return result


def read_diagnostic(directory: Path = DIRECTORY, *, expected_identity_sha256: str | None = None):
    """Verify saved bytes/lineage, without forecasts, fitting or score execution.

    A colocated hash is not an external trust anchor. Public integrations must
    supply the separately reviewed identity digest after an actual result exists.
    """
    directory = Path(directory)
    if directory.is_symlink():
        raise ValueError("A symlinked diagnostic directory is not accepted")
    identity, identity_sha = _load(directory / "identity.json")
    if expected_identity_sha256 is not None and identity_sha != expected_identity_sha256:
        raise ValueError("The external diagnostic result identity changed")
    contract, contract_sha = _load(directory / "protocol.json")
    forecasts, forecast_sha = _load(directory / "forecasts.json")
    result, report_sha = _load(directory / "evaluation.json")
    if identity != {"schema_version": 1, "kind": "ORIGIN_RESIDUAL_LOCAL_RESULT_IDENTITY",
            "study_id": model.STUDY_ID, "protocol_sha256": contract_sha,
            "forecast_file_sha256": forecast_sha, "report_sha256": report_sha,
            "externally_trusted_pin_required_for_publication": True}:
        raise ValueError("The diagnostic result identity does not bind its exact artifacts")
    pins = _source_pins()
    _, manifest, source_hashes, _ = load_acquisition(SOURCE_DIRECTORY)
    expected_contract = _contract(source_hashes, pins, contract["reviewed_code_commit"])
    expected_contract["frozen_at_utc"] = contract["frozen_at_utc"]
    if (contract["study_id"] != model.STUDY_ID or result["study_id"] != model.STUDY_ID
            or forecasts["study_id"] != model.STUDY_ID
            or contract != expected_contract
            or contract["source_artifact_pins"] != pins
            or result["source_artifact_pins"] != pins or forecasts["source_artifact_pins"] != pins
            or contract["method_source_sha256"] != _method_hashes()
            or result["method_source_sha256"] != contract["method_source_sha256"]
            or manifest is None or contract["source_acquisition_lineage"] != source_hashes
            or result["source_acquisition_lineage"] != source_hashes
            or result["protocol_sha256"] != contract_sha
            or forecasts["protocol_sha256"] != contract_sha
            or result["forecast_file_sha256"] != forecast_sha
            or result["forecast_frozen_at_utc"] != forecasts["frozen_at_utc"]
            or not _clock(contract["frozen_at_utc"]) <= _clock(forecasts["frozen_at_utc"])
            <= _clock(result["scored_at_utc"])):
        raise ValueError("Diagnostic method, source lineage or chronology changed")
    model._validate_forecasts(forecasts["forecasts"])
    if (not contract["analysis_scope"] == result["analysis_scope"] == "POST_OUTCOME_EXPLORATORY"
            or result["previously_viewed_target_outcomes"] is not True
            or forecasts["future_coordinates_decoded_in_this_diagnostic"] is not False
            or result["all_four_forecasts_saved_before_this_diagnostic_target_decode"] is not True
            or result["new_data_acquisition"] is not False
            or result["frozen_source_study_changed"] is not False
            or result["provider_calls"] is not False or result["physical_validation"] is not False):
        raise ValueError("Exploratory diagnostic claim boundaries changed")
    # Read each exact artifact once more so a concurrent overwrite cannot return
    # a mixed generation. No numerical replay is implied by this byte check.
    for name, expected in (("identity", identity_sha), ("protocol", contract_sha),
                           ("forecasts", forecast_sha), ("evaluation", report_sha)):
        if _load(directory / f"{name}.json")[1] != expected:
            raise ValueError("Diagnostic artifacts changed during verification")
    if (_source_pins() != pins or load_acquisition(SOURCE_DIRECTORY)[2] != source_hashes
            or _method_hashes() != contract["method_source_sha256"]):
        raise ValueError("Diagnostic source inputs or method changed during verification")
    return {"report": result, "forecasts": forecasts["forecasts"],
        "artifact_identity": {**identity, "identity_sha256": identity_sha,
            "integrity_verified": True, "numeric_replay_verified": False,
            "external_result_pin_verified": expected_identity_sha256 is not None,
            "verification_scope": "SAVED_BYTES_AND_LINEAGE_NOT_NUMERIC_REPLAY"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    parser.add_argument("--first-score", action="store_true")
    parser.add_argument("--expected-identity-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value = first_score(args.directory) if args.first_score else read_diagnostic(
        args.directory, expected_identity_sha256=args.expected_identity_sha256)
    raw = _canonical(value)
    if args.output:
        with args.output.open("xb") as stream:
            stream.write(raw)
    else:
        print(raw.decode(), end="")


if __name__ == "__main__":
    main()
