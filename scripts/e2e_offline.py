"""Run actual HTTP workflows in a disposable, provider-disabled API process.

No existing API URL is accepted. The child uses an OS-assigned loopback port, a
fresh private token and store, no repository .env, and fail-fast side-effect guards.
Missing live providers/hardware stay explicit BLOCKED scopes, not successful tests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
MAX_RECEIPT_BYTES = 2_000_000
MAX_TIMEOUT_SECONDS = 240
GUARD_KEYS = {"camera_open_attempts", "provider_http_attempts",
              "photon_send_attempts", "photon_poll_attempts",
              "origin_residual_execution_attempts", "ocean_source_execution_attempts"}
EXPECTED_BLOCKERS = {"Chalk live model verification", "physical webcam/tank calibration",
                     "Photon device round trip", "xAI speech provider round trip",
                     "live Chalk prevention response", "live Chalk validation review"}

CHILD = r'''
import atexit, hashlib, json, os
from pathlib import Path
import cv2, httpx, uvicorn
counts = {"camera_open_attempts": 0, "provider_http_attempts": 0,
          "photon_send_attempts": 0, "photon_poll_attempts": 0,
          "origin_residual_execution_attempts": 0, "ocean_source_execution_attempts": 0}
guard_path = Path(os.environ["AUDIT_GUARD_RECEIPT"])
guard_path.write_text(json.dumps(counts))
def forbidden(name):
    def reject(*args, **kwargs):
        counts[name] += 1
        guard_path.write_text(json.dumps(counts))
        raise AssertionError("Isolated audit forbids " + name)
    return reject
cv2.VideoCapture = forbidden("camera_open_attempts")
httpx.AsyncClient.request = forbidden("provider_http_attempts")
from adapters.photon.transport import PhotonTransport
PhotonTransport.send_saved = forbidden("photon_send_attempts")
PhotonTransport.list_page = forbidden("photon_poll_attempts")
# This result is a saved-artifact read, never a new forecast or first score.
from apps.ocean.reeftrace_ocean import origin_residual as residual_model
from scripts import evaluate_origin_residual_diagnostic as residual_script
for name in ("build_forecasts", "score_forecasts", "corrected_field"):
    setattr(residual_model, name, forbidden("origin_residual_execution_attempts"))
residual_script.first_score = forbidden("origin_residual_execution_attempts")
from apps.ocean.reeftrace_ocean import ocean_source as source_model
from apps.ocean.reeftrace_ocean import ocean_source_pipeline as source_pipeline
from scripts import evaluate_ocean_source as source_script
for name in ("build_ocean_source_forecasts", "score_ocean_source_forecasts", "backtrack_current"):
    setattr(source_model, name, forbidden("ocean_source_execution_attempts"))
for name in ("build_pipeline_forecasts", "score_pipeline_forecasts", "filter_three_positions",
             "corrected_current_field", "backtrack_current"):
    setattr(source_pipeline, name, forbidden("ocean_source_execution_attempts"))
source_script.first_score = forbidden("ocean_source_execution_attempts")
from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
app = create_app(Settings(_env_file=None, data_dir=Path(os.environ["AUDIT_STORE"]),
                          local_token=os.environ["AUDIT_OPERATOR_TOKEN"]))
@app.get("/__offline_audit__/identity")
def identity():
    return {"nonce": os.environ["AUDIT_PROCESS_NONCE"]}
@app.get("/__offline_audit__/store-digest")
def store_digest():
    # Opaque digest only, inside the disposable process; no live store is opened.
    with app.state.runtime.store.connection() as db:
        payload = "\n".join(db.iterdump()).encode()
    return {"sha256": hashlib.sha256(payload).hexdigest()}
atexit.register(lambda: guard_path.write_text(json.dumps(counts)))
uvicorn.run(app, host="127.0.0.1", port=int(os.environ["AUDIT_PORT"]), log_level="warning")
'''


def child_environment(parent, scratch, token, nonce, port):
    """Do not inherit credentials, application stores, user PYTHONPATH or .env."""
    env = {key: value for key, value in parent.items()
           if not key.upper().startswith(("CHALK_", "PHOTON_", "GROK_", "XAI_", "REEFTRACE_",
                                          "GEMINI_", "GOOGLE_", "OPENAI_", "ANTHROPIC_", "AUDIT_"))
           and key.upper() not in {"PYTHONPATH", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"}}
    env.update(PYTHONPATH=str(ROOT), CHALK_ENABLED="false", PHOTON_ENABLED="false",
        PHOTON_ROUTES_JSON="[]", GROK_VOICE_ENABLED="false", AUDIT_STORE=str(scratch / "store"),
        AUDIT_OPERATOR_TOKEN=token, AUDIT_PROCESS_NONCE=nonce, AUDIT_PORT=str(port),
        AUDIT_GUARD_RECEIPT=str(scratch / "guards.json"), NO_PROXY="127.0.0.1,localhost,::1")
    return env


@contextmanager
def loopback_proxy_environment():
    """The reused HTTP clients must not forward loopback traffic to a proxy."""
    keys = [key for key in os.environ if key.upper() in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"}]
    old = {key: os.environ.pop(key) for key in keys}
    os.environ["NO_PROXY"] = "127.0.0.1,localhost,::1"
    try:
        yield
    finally:
        os.environ.pop("NO_PROXY", None)
        os.environ.update(old)


def terminate_owned_process(child, grace_s=3):
    """Only terminate/reap the process created by this harness."""
    if child.poll() is None:
        try:
            child.terminate()
        except ProcessLookupError:
            pass
    try:
        child.wait(timeout=grace_s)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=grace_s)


@contextmanager
def process_deadline(child, seconds):
    expired = threading.Event()

    def stop():
        expired.set()
        if child.poll() is None:
            try:
                child.kill()
            except ProcessLookupError:
                pass

    timer = threading.Timer(seconds, stop)
    timer.daemon = True
    timer.start()
    try:
        yield expired
    finally:
        timer.cancel()


def suite_functions(api, token):
    """Import the existing CLI audits without running their credential loaders."""
    previous = sys.path[:]
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from e2e_demo import audit as source_audit
        from e2e_prevention import audit as prevention_audit
        from e2e_team_integration import audit as team_audit
        from e2e_validation import audit as validation_audit
    finally:
        sys.path[:] = previous
    return (("source", lambda: source_audit(api, token)),
            ("prevention", lambda: prevention_audit(api, token=token)),
            ("validation", lambda: validation_audit(api=api, token=token)),
            ("team", lambda: team_audit(api, token)))


def guards_clean(counts):
    return isinstance(counts, dict) and set(counts) == GUARD_KEYS and all(
        type(value) is int and value == 0 for value in counts.values())


def summarize(result):
    checks = [*result["extra_checks"], *[check for suite in result["suite_reports"].values()
                                      for check in suite["checks"]]]
    blockers = {check["check"] for check in checks if check["status"] == "BLOCKED"}
    counts = {state: sum(check["status"] == state for check in checks)
              for state in ("PASS", "FAIL", "BLOCKED")}
    return {**counts, "software_workflow_passed": counts["FAIL"] == 0
            and blockers == EXPECTED_BLOCKERS and len(result["suite_reports"]) == 4,
            "expected_external_scopes_blocked": blockers == EXPECTED_BLOCKERS,
            "complete_live_product_verified": False, "physical_validation": False,
            "live_provider_round_trip_verified": False}


def write_receipt(path, result):
    payload = (json.dumps(result, indent=2, allow_nan=False) + "\n").encode()
    if len(payload) > MAX_RECEIPT_BYTES:
        raise ValueError("Offline HTTP receipt exceeds its bounded size")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def run_audit(timeout_seconds=MAX_TIMEOUT_SECONDS):
    if not 5 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise ValueError("Offline HTTP deadline must be between 5 and 240 seconds")
    began = time.monotonic()
    result = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "scope": "Actual HTTP requests to a separate loopback API and temporary SQLite store; synthetic operational evidence only",
        "live_port_8000_untouched": True, "provider_configuration_changed": False,
        "camera_opened": False, "physical_trials_run": 0, "hardware_actuation": False,
        "new_photon_messages_sent": 0, "provider_model_requests": 0,
        "deadline_seconds": timeout_seconds,
        "suite_reports": {}, "extra_checks": [], "evidence": {},
    }
    token, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    with tempfile.TemporaryDirectory(prefix="reeftrace-offline-http-") as scratch:
        scratch = Path(scratch)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        api = f"http://127.0.0.1:{port}"
        env = child_environment(os.environ, scratch, token, nonce, port)
        with (scratch / "server.log").open("w") as log:
            child = subprocess.Popen([sys.executable, "-c", CHILD], cwd=scratch, env=env,
                                     stdout=log, stderr=subprocess.STDOUT)
            with process_deadline(child, timeout_seconds) as expired:
                try:
                    with httpx.Client(timeout=1, follow_redirects=False, trust_env=False) as client:
                        deadline = time.monotonic() + min(15, timeout_seconds)
                        while True:
                            try:
                                response = client.get(api + "/__offline_audit__/identity")
                                if response.status_code == 200 and response.json() == {"nonce": nonce}:
                                    break
                            except (httpx.TransportError, ValueError):
                                pass
                            if child.poll() is not None or time.monotonic() >= deadline:
                                raise RuntimeError("Owned isolated API did not start or match its private process nonce")
                            time.sleep(0.05)
                    result["api_scope"] = "isolated_loopback_dynamic_port_verified_process_nonce"
                    with loopback_proxy_environment():
                        for name, run in suite_functions(api, token):
                            if expired.is_set():
                                raise TimeoutError("Offline HTTP workflow exceeded its total deadline")
                            started = time.monotonic()
                            report = run()
                            report["elapsed_seconds"] = round(time.monotonic() - started, 3)
                            result["suite_reports"][name] = report
                        extra(result, api, token)
                except (AssertionError, ImportError, ValueError, KeyError, TypeError,
                        OSError, RuntimeError, httpx.HTTPError) as error:
                    result["extra_checks"].append({"check": "isolated workflow completion", "status": "FAIL",
                        "reason": str(error).replace(token, "[redacted]").replace(str(scratch), "[isolated-store]").replace(str(ROOT), "[repository]")[:400]})
                finally:
                    terminate_owned_process(child)
            result["deadline_expired"] = expired.is_set()
            if expired.is_set():
                result["extra_checks"].append({"check": "total offline HTTP deadline", "status": "FAIL"})
            guards = scratch / "guards.json"
            result["side_effect_guards"] = json.loads(guards.read_text()) if guards.exists() else {"guard_receipt_missing": True}
            result["extra_checks"].append({"check": "no guarded hardware/provider/messaging attempt occurred",
                "status": "PASS" if guards_clean(result["side_effect_guards"]) else "FAIL"})
    result["elapsed_seconds"] = round(time.monotonic() - began, 3)
    result["summary"] = summarize(result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "work/e2e-offline.json")
    parser.add_argument("--timeout-seconds", type=float, default=MAX_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)
    try:
        result = run_audit(args.timeout_seconds)
        write_receipt(args.output, result)
    except (ValueError, OSError) as error:
        print(type(error).__name__ + ": offline audit setup or bounded receipt failed", file=sys.stderr)
        return 2
    print(json.dumps({**result["summary"], "elapsed_seconds": result["elapsed_seconds"]}))
    return int(not result["summary"]["software_workflow_passed"])


def matched_version_checks(req, check, *, v1_snapshot, store_digest, root=ROOT):
    """Verify fixed version selection using frozen artifacts only; no scoring.

    Until the distinct v2 result identity exists, absence must remain HTTP404.
    A present identity must pass the authoritative pure reader and exact HTTP
    envelope comparison; no fallback or fabricated expected numeric result.
    """
    base = "/research/matched-current"
    check("explicit matched-current v1 selection preserves the historical envelope",
          req(base + "?study_version=v1", auth=False) == v1_snapshot)
    v1_identity = v1_snapshot["artifact_identity"]
    for version in ("v3", "V2", "untrusted-module"):
        req(base + "?study_version=" + version, expected=422, auth=False)
        req(base + "/investigate", {
            "study_version": version, "question": "Explain this saved result.",
            "report_sha256": v1_identity["report_sha256"],
            "protocol_sha256": v1_identity["protocol_sha256"]}, expected=422)
    identity_path = Path(root) / (
        "apps/ocean/reeftrace_ocean/matched_current_v2_result_identity.py")
    if not identity_path.is_file():
        req(base + "?study_version=v2", expected=404, auth=False)
        return {"status": "TRUSTED_RESULT_ABSENT_HTTP404", "study_version": "v2"}

    from apps.ocean.reeftrace_ocean.matched_current_result import load_frozen_matched_current_result

    authoritative = load_frozen_matched_current_result(root=root, study_version="v2")
    selected = req(base + "?study_version=v2", auth=False)
    check("v2 HTTP envelope equals the authoritative pinned artifact reader", selected == authoritative)
    report, identity = selected["report"], selected["artifact_identity"]
    scores = report["scores"]
    check("v2 keeps its selected identity, full denominator and no automatic promotion",
        report["study_id"] == identity["study_id"] == "matched-current-gdp-hycom-15m-v2"
        and identity["integrity_verified"] is identity["result_pin_verified"] is True
        and identity["numeric_replay_verified"] is False
        and scores["planned_group_count"] == len(scores["groups"]) == 2
        and scores["planned_cell_count"] == 36
        and scores["planned_distinct_target_count"] == 12
        and sum(len(model["cells"]) for group in scores["groups"]
                for model in group["candidates"]) == 36
        and not scores["automatic_winner_selected"]
        and report["automatic_model_promotion"] is False
        and report["physical_validation"] is False)
    question = {"study_version": "v2", "question": "Explain this saved amendment and its limits.",
        "report_sha256": identity["report_sha256"], "protocol_sha256": identity["protocol_sha256"]}
    before = store_digest()
    req(base + "/investigate", question, expected=401, auth=False)
    req(base + "/investigate", {**question,
        "report_sha256": v1_identity["report_sha256"],
        "protocol_sha256": v1_identity["protocol_sha256"]}, expected=409)
    for key in ("report_sha256", "protocol_sha256"):
        req(base + "/investigate", {**question, key: "0" * 64}, expected=409)
    review = req(base + "/investigate", question)
    check("disabled v2 Chalk preserves exact evidence and the full disposable store",
        review["action"] == "STOP" and review["failure_code"] == "NOT_CONFIGURED"
        and review["live_model_response"] is False
        and review["research_report"] == report
        and review["artifact_identity"] == identity
        and review["store_written"] is review["hardware_actuation"] is False
        and store_digest() == before)
    return {"status": "TRUSTED_RESULT_READ_ONLY_VERIFIED", "study_version": "v2",
        "report_sha256": identity["report_sha256"],
        "protocol_sha256": identity["protocol_sha256"],
        "planned_cells": scores["planned_cell_count"],
        "scored_cells": scores["scored_cell_count"], "store_unchanged": True}


def origin_residual_checks(req, check, *, store_digest, root=ROOT):
    """Exercise the fixed exploratory result over HTTP with providers disabled.

    Expected numbers come only from the authoritative saved-artifact reader.
    No fixture is rescored and no missing target is replaced with a success.
    """
    from apps.ocean.reeftrace_ocean.origin_residual_result_identity import IDENTITY_SHA256

    # Direct `python scripts/e2e_offline.py` puts scripts/, not the repository,
    # on sys.path. Keep the same reviewed import scope in CLI and pytest runs.
    previous = sys.path[:]
    try:
        sys.path.insert(0, str(ROOT))
        from scripts.evaluate_origin_residual_diagnostic import read_diagnostic
    finally:
        sys.path[:] = previous

    directory = Path(root) / "data/research/origin-residual-v1"

    def artifacts():
        return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in directory.iterdir() if path.is_file()}

    before_files, before_store = artifacts(), store_digest()
    authoritative = read_diagnostic(directory, expected_identity_sha256=IDENTITY_SHA256)
    base = "/research/origin-residual"
    selected = req(base, auth=False)
    check("origin-residual HTTP envelope equals the authoritative pinned artifact reader",
          selected == authoritative)
    report, forecasts, identity = (selected[key] for key in (
        "report", "forecasts", "artifact_identity"))
    scores = report["scores"]
    check("exploratory result retains two groups, four candidates and twelve reused targets",
        report["study_id"] == identity["study_id"] == forecasts["study_id"]
        == "origin-residual-gdp-hycom-15m-exploratory-v1"
        and identity["identity_sha256"] == IDENTITY_SHA256
        and identity["integrity_verified"] is identity["external_result_pin_verified"] is True
        and identity["numeric_replay_verified"] is False
        and identity["verification_scope"] == "SAVED_BYTES_AND_LINEAGE_NOT_NUMERIC_REPLAY"
        and scores["planned_group_count"] == len(scores["groups"]) == len(forecasts["groups"]) == 2
        and scores["planned_cell_count"] == forecasts["planned_cell_count"] == 48
        and scores["planned_distinct_target_count"] == forecasts["planned_distinct_target_count"] == 12
        and len(scores["models"]) == len(forecasts["model_ids"]) == 4
        and sum(len(candidate["cells"]) for group in scores["groups"]
                for candidate in group["candidates"]) == 48
        and all(len(group["candidates"]) == 4 for group in scores["groups"])
        and report["analysis_scope"] == scores["analysis_scope"]
        == forecasts["analysis_scope"] == "POST_OUTCOME_EXPLORATORY"
        and report["previously_viewed_target_outcomes"] is True
        and scores["previously_viewed_target_outcomes"] is True
        and forecasts["previously_viewed_target_outcomes"] is True
        and all(scores[key] is False for key in (
            "statistical_independence", "automatic_winner_selected", "automatic_model_promotion",
            "operational_forecast_skill_verified", "physical_validation", "heldout_tuning", "global_training")))
    check("exploratory coverage and primary table equal saved outcomes without numerical replay",
        scores == authoritative["report"]["scores"]
        and scores["scored_cell_count"] == sum(
            row["metrics"]["scored_count"] for row in scores["models"])
        and scores["primary_common_cohort_complete"]
            is (scores["scored_cell_count"] == scores["planned_cell_count"])
        and ((scores["primary_equal_id_macro_results"] is not None)
             is scores["primary_common_cohort_complete"]))
    pins = {key: identity[key] for key in (
        "report_sha256", "protocol_sha256", "identity_sha256")}
    question = {"question": "Explain this exploratory result and the next independent measurement.",
                **pins}
    req(base + "/investigate", question, expected=401, auth=False)
    invalid = [{**question, "question": " "}, {**question, "question": True},
               {**question, "question": "x" * 2001}, {**question, "study_version": "v2"}]
    for key in pins:
        missing = dict(question)
        del missing[key]
        invalid.extend((missing, {**question, key: "not-a-sha256"}))
    for body in invalid:
        req(base + "/investigate", body, expected=422)
    for key in pins:
        req(base + "/investigate", {**question, key: "0" * 64}, expected=409)
    review = req(base + "/investigate", question)
    check("disabled origin-residual Chalk retains exact report and no fabricated live answer",
        review["schema_version"] == 1
        and review["kind"] == "ORIGIN_RESIDUAL_RESEARCH_INVESTIGATION"
        and review["scope"] == "READ_ONLY_POST_OUTCOME_EXPLORATORY_DIAGNOSTIC"
        and review["analysis_scope"] == "POST_OUTCOME_EXPLORATORY"
        and review["previously_viewed_target_outcomes"] is True
        and review["provider"] == "chalk" and review["action"] == "STOP"
        and review["failure_code"] == "NOT_CONFIGURED"
        and review["live_model_response"] is False
        and review["research_report"] == report and review["artifact_identity"] == identity
        and all(review[key] == value for key, value in pins.items())
        and review["evidence_ids"] == review["trace"] == []
        and all(review[key] is False for key in (
            "numeric_replay_verified", "store_written", "hardware_actuation",
            "physical_validation", "automatic_model_promotion")))
    check("origin-residual research leaves full store and all saved artifacts unchanged",
        req(base, auth=False) == selected and store_digest() == before_store
        and artifacts() == before_files)
    return {"status": "PINNED_EXPLORATORY_RESULT_READ_ONLY_VERIFIED", **pins,
        "analysis_scope": "POST_OUTCOME_EXPLORATORY", "previously_viewed_target_outcomes": True,
        "planned_cells": scores["planned_cell_count"], "scored_cells": scores["scored_cell_count"],
        "planned_distinct_targets": scores["planned_distinct_target_count"],
        "primary_equal_id_macro_results": scores["primary_equal_id_macro_results"],
        "numeric_replay_verified": False, "store_unchanged": True, "artifacts_unchanged": True,
        "cache_control_scope": "Data/route responses are no-store; pre-handler 422 schema headers are recorded separately, not guaranteed"}


def ocean_source_checks(req, check, *, store_digest, root=ROOT):
    """Read the actual source-reconstruction artifact over isolated HTTP, never execute it."""
    previous = sys.path[:]
    try:
        sys.path.insert(0, str(ROOT))
        from apps.api.reeftrace_api.services import ocean_source_investigation as service
        from scripts.evaluate_ocean_source import read_result
    finally:
        sys.path[:] = previous
    directory = Path(root) / "data/research/ocean-source-v1"

    def artifact_hashes():
        return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in directory.iterdir() if path.is_file()} if directory.is_dir() else {}

    before_files, before_store = artifact_hashes(), store_digest()
    base = "/research/ocean-source"
    try:
        pins_module = service._pins()
        expected = read_result(directory, expected_identity_sha256=pins_module.IDENTITY_SHA256)
    except FileNotFoundError:
        req(base, expected=404, auth=False)
        absent_question = {"question": "Explain the available saved source evidence.",
            **dict.fromkeys(("report_sha256", "protocol_sha256", "identity_sha256"), "0" * 64)}
        req(base + "/investigate", absent_question, expected=401, auth=False)
        req(base + "/investigate", absent_question, expected=404)
        check("unpublished ocean source stays unavailable without scoring or store/artifact changes",
              before_store == store_digest() and artifact_hashes() == before_files)
        return {"status": "NOT_PUBLISHED_UNAVAILABLE_VERIFIED", "http_status": 404,
                "store_unchanged": True, "artifacts_unchanged": True,
                "numeric_replay_verified": False, "live_model_response": False}
    selected = req(base, auth=False)
    check("ocean-source HTTP equals the pinned saved artifact without executing inference",
          selected == expected)
    report, identity = selected["report"], selected["artifact_identity"]
    forecasts, validation = report["forecasts"], report["validation"]
    check("ocean source preserves two viewed groups, all scenarios and separate validation",
          report["analysis_scope"] == "POST_OUTCOME_EXPLORATORY"
          and report["previously_viewed_earlier_positions"] is True
          and forecasts["earlier_truth_used"] is False
          and forecasts["planned_model_rows"] == validation["planned_model_rows"] == 6
          and forecasts["planned_distinct_earlier_positions"] == 2
          and forecasts["scenarios_per_group"] == 25
          and len(forecasts["groups"]) == 2
          and all(len(group["reverse_current"]["scenarios"]) == 25 for group in forecasts["groups"])
          and identity["numeric_replay_verified"] is False)
    tutorial = report["pipeline_tutorial"]
    pipeline, pipeline_validation = tutorial["forecasts"], tutorial["validation"]
    check("bidirectional walkthrough preserves scattered fixes, causal states and five explicit stages",
          tutorial["kind"] == "THREE_FIX_BIDIRECTIONAL_RESEARCH_WALKTHROUGH"
          and forecasts["pipeline_tutorial"] == pipeline
          and pipeline["earlier_truth_used"] is pipeline["later_truth_used"] is False
          and pipeline["observation_times_utc"] == [f"2022-06-01T0{hour}:00:00Z" for hour in (1, 2, 3)]
          and pipeline["anchor_time_utc"] == "2022-06-01T03:00:00Z"
          and [stage["id"] for stage in pipeline["stages"]]
              == ["raw", "connected", "filtered", "formula", "branches"]
          and pipeline["position_std_m"] == 100.
          and pipeline["acceleration_spectral_density_m2_s3"] == 1e-6
          and len(pipeline["groups"]) == 2
          and all(len(group["raw_observations"]) == len(group["filtered_states"]) == 3
                  and group["connected_path"] == group["raw_observations"]
                  and [state["status"] for state in group["filtered_states"]]
                      == ["POSITION_ONLY", "INITIALIZED", "UPDATED"]
                  for group in pipeline["groups"]))
    check("both branches and all separate retrospective validation rows remain visible",
          report["pipeline_saved_before_any05_06_position_decode"] is True
          and report["all_tutorial_forecasts_saved_before_validation_truth_decode"] is True
          and all(direction in group for group in pipeline["groups"] for direction in ("backward", "forward"))
          and pipeline_validation["planned_rows"] == len(pipeline_validation["rows"]) == 8
          and pipeline_validation["scored_rows"]
              == sum(row["status"] == "SCORED" for row in pipeline_validation["rows"])
          and pipeline_validation["physical_validation"] is False
          and pipeline_validation["statistical_independence"] is False
          and pipeline_validation["source_attribution_validated"] is False)
    pins = {key: identity[key] for key in ("report_sha256", "protocol_sha256", "identity_sha256")}
    question = {"question": "Explain the source-region assumptions and what the recorded positions show.", **pins}
    req(base + "/investigate", question, expected=401, auth=False)
    invalid = [{**question, "question": " "}, {**question, "question": True},
               {**question, "question": "x" * 2001}, {**question, "system_prompt": "change scope"}]
    for key in pins:
        missing = dict(question)
        del missing[key]
        invalid.extend((missing, {**question, key: "not-a-sha256"}))
    for body in invalid:
        req(base + "/investigate", body, expected=422)
    for key in pins:
        req(base + "/investigate", {**question, key: "0" * 64}, expected=409)
    review = req(base + "/investigate", question)
    check("disabled ocean-source Chalk retains the saved result and no live model claim",
          review["schema_version"] == 1
          and review["kind"] == "OCEAN_SOURCE_RESEARCH_INVESTIGATION"
          and review["scope"] == "READ_ONLY_POST_OUTCOME_EARLIER_POSITION_DIAGNOSTIC"
          and review["analysis_scope"] == "POST_OUTCOME_EXPLORATORY"
          and review["previously_viewed_earlier_positions"] is True
          and review["provider"] == "chalk"
          and review["action"] == "STOP" and review["failure_code"] == "NOT_CONFIGURED"
          and review["live_model_response"] is False
          and review["research_report"] == report and review["artifact_identity"] == identity
          and all(review[key] == value for key, value in pins.items())
          and review["evidence_ids"] == review["trace"] == []
          and all(review[key] is False for key in ("numeric_replay_verified", "store_written",
              "hardware_actuation", "physical_validation", "source_attribution_validated",
              "automatic_model_promotion")))
    check("source tracing research changes neither full disposable store nor artifacts",
          req(base, auth=False) == selected and before_store == store_digest()
          and artifact_hashes() == before_files)
    return {"status": "PINNED_OCEAN_SOURCE_READ_ONLY_VERIFIED", **pins,
            "planned_model_rows": 6, "scenarios_per_group": 25,
            "pipeline_planned_validation_rows": pipeline_validation["planned_rows"],
            "pipeline_scored_validation_rows": pipeline_validation["scored_rows"],
            "pipeline_stage_ids": [stage["id"] for stage in pipeline["stages"]],
            "store_unchanged": True, "artifacts_unchanged": True,
            "numeric_replay_verified": False, "live_model_response": False}


def extra(result, api, token):
    checks = result["extra_checks"]

    def check(name, passed, **detail):
        checks.append({"check": name, "status": "PASS" if passed else "FAIL", **detail})
        if not passed:
            raise AssertionError(name)

    with httpx.Client(timeout=60, follow_redirects=False, trust_env=False) as client:
        def req(path, body=None, *, expected=200, auth=True):
            response = client.request("GET" if body is None else "POST", api + "/api/v1" + path,
                headers={"Authorization": "Bearer " + token} if auth else {}, json=body)
            check(f"HTTP {response.request.method} {path.split('?')[0]} → {expected}", response.status_code == expected)
            # Pydantic rejects 422 requests before the route's Response exists;
            # its generic validation response is distinct from a result read.
            if path.startswith(("/research/origin-residual", "/research/ocean-source")):
                scope = "ocean_source" if path.startswith("/research/ocean-source") else "origin_residual"
                if expected == 422:
                    result["evidence"].setdefault(scope + "_schema_response_headers", []).append({
                        "status": response.status_code,
                        "cache_control": response.headers.get("cache-control")})
                else:
                    check(scope + " result or route-error response is explicitly no-store",
                          response.headers.get("cache-control") == "no-store")
            return response.json()

        def store_digest():
            response = client.get(api + "/__offline_audit__/store-digest")
            check("opaque disposable store digest is available", response.status_code == 200)
            digest = response.json()["sha256"]
            check("disposable store digest is bounded SHA256", isinstance(digest, str)
                  and len(digest) == 64 and set(digest) <= set("0123456789abcdef"))
            return digest

        status = req("/status")
        check("isolated providers, automatic replies, camera and actuation remain disabled",
            not any(status[provider]["enabled"] for provider in ("chalk", "photon", "grok"))
            and not status["photon"]["worker_running"] and not status["camera"]["running"]
            and not status["hardware_actuation"])
        demo = req("/prevention/demo", {})
        old_case = req("/cases/" + demo["comparison"]["case_id"])
        fields = {"profile_id", "calibration_id", "token_class", "points", "endpoint",
                  "evidence_frame_ids", "mode", "camera_session_id", "association_valid"}
        case = req("/cases", {key: value for key, value in old_case.items() if key in fields})
        source = req(f"/cases/{case['id']}/estimate", {})
        detail = req("/prevention/comparisons", {"case_id": case["id"],
            "name": "Extended isolated SYNTHETIC software-only trial ledger",
            "baseline_profile_id": demo["comparison"]["baseline_profile_id"],
            "intervention_profile_id": demo["comparison"]["intervention_profile_id"],
            "protected_zone_cm": demo["comparison"]["protected_zone_cm"],
            "horizon_s": 20, "particles": 40, "trials_per_source": 2})
        comparison_id = detail["comparison"]["id"]
        base = "/prevention/comparisons/" + comparison_id
        scene_query = "?evaluation_snapshot_hash=" + detail["evaluation"]["snapshot_hash"]
        scene = req(base + "/scene" + scene_query, auth=False)
        check("3D scene is a read-only view of the exact full tank comparison",
            scene["kind"] == "TANK_RIG_SCENE"
            and scene["evaluation_snapshot_hash"] == detail["evaluation"]["snapshot_hash"]
            and scene["physical_validation"] is False
            and scene["actual"]["reported_physical_trial_count"] == 0
            and scene["actual"]["positional_error_metrics"] is None
            and scene["vertical"]["measured_depth_cm"] is None
            and len(scene["simulation"]["paths"]) <= 36
            and req(base) == detail)
        req(base + "/scene?evaluation_snapshot_hash=" + "0" * 64, expected=409, auth=False)
        blank = {"trial_key": "extra-no-entry", "layout": "baseline", "source_id": "A",
            "data_origin": "SYNTHETIC_DEMO", "outcome": "no_entry", "entry_time_s": None,
            "interception_time_s": None, "token_accounted": True, "physical_confirmed": False,
            "horizon_completed": True, "note": "Hand-authored synthetic software audit; no token was physically released."}
        no_entry = req(base + "/trials", blank)
        retry = req(base + "/trials", blank)
        check("no-entry save retry is exactly idempotent", no_entry == retry)
        req(base + "/trials", {**blank, "horizon_completed": False}, expected=422)
        req(base + "/trials", {**blank, "trial_key": "unlocated-no-entry", "token_accounted": False}, expected=422)
        req(base + "/trials", {**blank, "note": "Different immutable text"}, expected=409)
        unresolved = req(base + "/trials", {**blank, "trial_key": "extra-unresolved", "layout": "intervention",
            "outcome": "unresolved", "token_accounted": False, "horizon_completed": False})
        ledger = unresolved["evaluation"]["by_origin"]["SYNTHETIC_DEMO"]
        check("no-entry is resolved but unresolved/missing remain unknown in planned bounds",
            ledger["layouts"]["baseline"]["no_entry"] == 1
            and ledger["layouts"]["baseline"]["entry_rate_bounds"] == {
                "lower": 0, "upper": 5 / 6, "denominator": 6,
                "kind": "planned_slots_missing_and_unresolved_are_unknown"}
            and ledger["layouts"]["intervention"]["unresolved"] == 1
            and ledger["layouts"]["intervention"]["entry_rate_bounds"]["upper"] == 1
            and ledger["supports_causal_claim"] is False
            and unresolved["evaluation"]["by_origin"]["OPERATOR_REPORTED_PHYSICAL"]["plan"]["recorded_total"] == 0)
        bundle = req(base + "/export")
        check("export canonical hash is independently recomputed", hashlib.sha256(
            bundle["payload_canonical_json"].encode()).hexdigest() == bundle["payload_sha256"])
        manifest = req(base + "/validation-template?origin=SYNTHETIC_DEMO")
        receipt = req(base + "/validation-reports", {"report": manifest})
        check("receipt is accounting only, not method rerun or physical evidence",
            receipt["checks"] == {"identity_verified": True, "accounting_verified": True,
                "method_rerun": False, "physical_validation": False}
            and receipt["summary"]["unresolved"] == 1 and receipt["summary"]["validation_count"] == 2)
        req(base + "/validation-reports", {"report": {**manifest, "input_payload_sha256": "0" * 64}}, expected=409)
        req(f"/cases/{case['id']}/estimate", {})
        archive = req(base)
        check("recomputing source archives exact old comparison", archive["is_current"] is False
            and archive["archive_reason"] == "CASE_CHANGED_OR_STOPPED"
            and archive["comparison"]["source_evidence_id"] == source["id"])
        req(base + "/trials", {**blank, "trial_key": "after-source-recompute"}, expected=409)
        req(base + "/validation-reports", {"report": manifest}, expected=409)
        old_receipt = req(base + "/validation-reports/" + receipt["report"]["id"])
        check("old receipt remains readable but not current", old_receipt["is_current"] is False)
        req(f"/cases/{case['id']}/stop", {})
        req(f"/cases/{case['id']}/sensitivity", {"preset_id": "predeclared-transport-envelope-v1"}, expected=409)
        snapshots = req("/cases")
        noaa = req("/research/vector-diagnostic")
        cohort = req("/research/cohort-vectors")
        kalman = req("/research/kalman-diagnostic")
        fresh = req("/research/fresh-physics")
        matched = req("/research/matched-current", auth=False)
        matched_report, matched_identity = matched["report"], matched["artifact_identity"]
        matched_scores = matched_report["scores"]
        check("matched-current frozen failure ledger preserves both groups and all 36 cells",
            matched_identity["integrity_verified"] is True
            and matched_identity["result_pin_verified"] is True
            and matched_identity["numeric_replay_verified"] is False
            and matched_scores["planned_group_count"] == len(matched_scores["groups"]) == 2
            and matched_scores["planned_cell_count"] == 36
            and matched_scores["planned_distinct_target_count"] == 12
            and sum(len(model["cells"]) for group in matched_scores["groups"]
                    for model in group["candidates"]) == 36
            and matched_report["physical_validation"] is False)
        check("unavailable matched-current study never becomes a successful result",
            matched_scores["scored_cell_count"] == 0
            and matched_scores["primary_equal_id_macro_results"] is None
            and matched_scores["primary_paired_comparisons"] is None
            and not matched_scores["automatic_winner_selected"]
            and all(cell["error_m"] is None for group in matched_scores["groups"]
                    for model in group["candidates"] for cell in model["cells"]))
        matched_question = {"question": "Explain the acquisition blockers and remaining uncertainty.",
            "report_sha256": matched_identity["report_sha256"],
            "protocol_sha256": matched_identity["protocol_sha256"]}
        req("/research/matched-current/investigate", matched_question, expected=401, auth=False)
        req("/research/matched-current/investigate", {
            **matched_question, "report_sha256": "0" * 64}, expected=409)
        matched_review = req("/research/matched-current/investigate", matched_question)
        check("disabled Chalk preserves the pinned matched-current evidence without side effects",
            matched_review["action"] == "STOP"
            and matched_review["failure_code"] == "NOT_CONFIGURED"
            and matched_review["live_model_response"] is False
            and matched_review["research_report"] == matched_report
            and matched_review["artifact_identity"] == matched_identity
            and matched_review["store_written"] is False
            and matched_review["hardware_actuation"] is False)
        result["evidence"]["matched_current_v2"] = matched_version_checks(
            req, check, v1_snapshot=matched, store_digest=store_digest)
        result["evidence"]["origin_residual"] = origin_residual_checks(
            req, check, store_digest=store_digest)
        result["evidence"]["ocean_source"] = ocean_source_checks(
            req, check, store_digest=store_digest)
        fresh_coverage = fresh["coverage"]
        check("fresh study keeps the frozen requested cohort and all missing or failed outcomes",
            fresh["kind"] == "FRESH_NOAA_DRIFTER_STUDY"
            and fresh["design_status"] == "FROZEN_NEW_GDP_ID_GROUP_EVALUATION_WITH_KNOWN_ALIAS_EXCLUSIONS"
            and fresh_coverage["target_groups"] == len(fresh["groups"]) == 6
            and fresh_coverage["models"] == len(fresh["models"]) == 5
            and fresh_coverage["horizons"] == 6
            and fresh_coverage["planned_outcomes"] == 180
            and fresh_coverage["scored_outcomes"] + fresh_coverage["failed_outcomes"]
                + fresh_coverage["unfilled_outcomes"] == 180
            and fresh["provenance"]["integrity_verified"] is True
            and fresh["flags"]["physical_validation"] is False
            and fresh["flags"]["automatic_model_promotion"] is False
            and fresh["flags"]["statistical_independence"] is False)
        if not fresh_coverage["common_target_cohort_complete"]:
            check("incomplete fresh target never becomes a successful-subset aggregate",
                  all(model["metrics"] is None for model in fresh["models"]))
        req("/research/fresh-physics/investigate", {"question": "Explain this study."},
            expected=401, auth=False)
        req("/research/fresh-physics/investigate", {"question": "Explain this study.",
            "source_id": "invented-source"}, expected=422)
        fresh_review = req("/research/fresh-physics/investigate", {
            "question": "What can these new GDP-ID motion results establish, and what remains uncertain?"})
        snapshot_hash = hashlib.sha256(json.dumps(fresh, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False).encode()).hexdigest()
        check("disabled Chalk preserves exact fresh-study evidence without a provider call",
            fresh_review["kind"] == "FRESH_DRIFTER_RESEARCH_INVESTIGATION"
            and fresh_review["action"] == "STOP"
            and fresh_review["failure_code"] == "NOT_CONFIGURED"
            and fresh_review["live_model_response"] is False
            and fresh_review["research_report"] == fresh
            and fresh_review["snapshot_report_sha256"] == snapshot_hash
            and fresh_review["store_written"] is False
            and fresh_review["hardware_actuation"] is False)
        currents = req("/research/current-forecast", auth=False)
        check("public current forcing uses a pinned real forecast without inventing measurements",
            currents["kind"] == "CURRENT_FORCED_PREVIEW"
            and currents["dynamic"]["status"] == currents["persistence"]["status"] == "COMPLETED"
            and len(currents["dynamic"]["track"]) == len(currents["persistence"]["track"]) == 25
            and currents["forcing"]["future_valid_times_at_acquisition"] is True
            and currents["validation"]["measured_track_available"] is False
            and currents["validation"]["physical_validation"] is False
            and currents["validation"]["ade_m"] is None
            and currents["validation"]["fde_m"] is None
            and currents["endpoint_separation_m"] > 0)
        current_question = {"question": "Explain this changing-current prediction and its limitations.",
            "snapshot_sha256": currents["snapshot_sha256"],
            "method_sha256": currents["method_sha256"]}
        req("/research/current-forecast/investigate", current_question, expected=401, auth=False)
        req("/research/current-forecast/investigate", {
            **current_question, "snapshot_sha256": "0" * 64}, expected=409)
        current_review = req("/research/current-forecast/investigate", current_question)
        check("disabled Chalk preserves the exact geographic current snapshot",
            current_review["action"] == "STOP"
            and current_review["failure_code"] == "NOT_CONFIGURED"
            and current_review["live_model_response"] is False
            and current_review["research_report"] == currents
            and current_review["snapshot_sha256"] == currents["snapshot_sha256"]
            and current_review["method_sha256"] == currents["method_sha256"]
            and current_review["store_written"] is False
            and current_review["hardware_actuation"] is False)
        ocean = req("/research/ocean-prevention", auth=False)
        control = req("/research/ocean-prevention?scenario_id=initial-proxy-v1", auth=False)
        req("/research/ocean-prevention?scenario_id=invented", expected=422, auth=False)
        check("ocean prevention compares equal layouts with the same changing-current releases",
            ocean["kind"] == "OCEAN_PREVENTION_COMPARISON"
            and ocean["scenario"]["id"] == "downstream-corridor-v2"
            and ocean["method"]["trajectory"] == "dynamic_current_advection_only"
            and ocean["method"]["identical_unmodified_forcing_for_every_layout"] is True
            and ocean["method"]["barriers_modify_flow"] is False
            and len(ocean["releases"]) == 6
            and ocean["baseline"]["summary"]["entered_count"] == 6
            and [layout["total_length_m"] for layout in ocean["layouts"]] == [2000, 2000]
            and [layout["summary"]["entered_count"] for layout in ocean["layouts"]] == [2, 4]
            and ocean["recommendation"]["best_layout_id"] == "central"
            and ocean["validation"]["physical_validation"] is False
            and ocean["validation"]["measured_entry_count"] is None)
        check("the original unexposed proxy stays a no-benefit control, not a forced winner",
            control["baseline"]["summary"]["entered_count"] == 0
            and control["recommendation"]["status"] == "TIE"
            and control["recommendation"]["best_layout_id"] is None)
        ocean_question = {"question": "Explain the predicted protection comparison and its limits.",
            "scenario_id": ocean["scenario"]["id"],
            **{key: ocean[key] for key in (
                "snapshot_sha256", "method_sha256", "scenario_sha256", "report_sha256")}}
        req("/research/ocean-prevention/investigate", ocean_question, expected=401, auth=False)
        req("/research/ocean-prevention/investigate", {
            **ocean_question, "report_sha256": "0" * 64}, expected=409)
        ocean_review = req("/research/ocean-prevention/investigate", ocean_question)
        check("disabled Chalk preserves the exact ocean scenario and numerical comparison",
            ocean_review["action"] == "STOP"
            and ocean_review["failure_code"] == "NOT_CONFIGURED"
            and ocean_review["live_model_response"] is False
            and ocean_review["research_report"] == ocean
            and ocean_review["report_sha256"] == ocean["report_sha256"]
            and ocean_review["store_written"] is False
            and ocean_review["hardware_actuation"] is False)
        check("real-vector units and synthetic vision evidence stay separated", noaa["noaa"]["velocity_units"] == "m/s"
            and noaa["synthetic_tank"]["coordinates"]["velocity_units"] == "cm/s"
            and noaa["synthetic_tank"]["data_origin"] == "SYNTHETIC_SOFTWARE_REPLAY"
            and not noaa["physical_validation"])
        check("cohort scores retain 24 reused observations, 96 paired intervals and 144 target slots",
            cohort["coverage"]["unique_observed_intervals"] == 24
            and cohort["coverage"]["scored_model_intervals"] == 96
            and cohort["coverage"]["planned_model_intervals"] == 144
            and cohort["coverage"]["missing_drifters"] == 2
            and not cohort["independent_evaluation"] and not cohort["automatic_model_promotion"])
        check("fixed Kalman study replays 120 acquired outcomes without hiding 60 missing target slots",
            kalman["kind"] == "FIXED_KALMAN_MOTION_DIAGNOSTIC"
            and kalman["coverage"]["scored_outcomes"] == 120
            and kalman["coverage"]["planned_outcomes"] == 180
            and kalman["coverage"]["unique_observed_intervals"] == 24
            and not kalman["independent_evaluation"] and not kalman["automatic_model_promotion"])
        check("vector inspection does not modify operational cases", req("/cases") == snapshots)
        req("/field-sessions/preflight", {"camera_session_id": "not-started"}, expected=401, auth=False)
        check("no physical session was fabricated", req("/field-sessions") == [])
        final = req("/status")
        check("isolated safety state unchanged", final == status)
        result["evidence"].update(comparison_id=comparison_id, source_evidence_id=source["id"],
            validation_report_id=receipt["report"]["id"], export_payload_sha256=bundle["payload_sha256"],
            synthetic_evaluation=ledger, real_vector_metrics=[{"id": model["id"], "metrics": model["metrics"]}
                for model in noaa["noaa"]["models"]], cohort_coverage=cohort["coverage"],
            fixed_kalman_coverage=kalman["coverage"],
            fresh_study_coverage=fresh_coverage,
            fresh_study_snapshot_sha256=snapshot_hash,
            matched_current_report_sha256=matched_identity["report_sha256"],
            matched_current_scored_cells=matched_scores["scored_cell_count"],
            current_forecast_snapshot_sha256=currents["snapshot_sha256"],
            current_forecast_method_sha256=currents["method_sha256"],
            ocean_prevention_report_sha256=ocean["report_sha256"],
            ocean_prevention_scenario_sha256=ocean["scenario_sha256"],
            ocean_prevention_recommendation=ocean["recommendation"],
            no_live_provider_calls=True, no_physical_trials=True)


if __name__ == "__main__":
    raise SystemExit(main())
