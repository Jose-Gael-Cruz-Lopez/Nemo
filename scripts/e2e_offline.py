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
              "photon_send_attempts", "photon_poll_attempts"}
EXPECTED_BLOCKERS = {"Chalk live model verification", "physical webcam/tank calibration",
                     "Photon device round trip", "xAI speech provider round trip",
                     "live Chalk prevention response", "live Chalk validation review"}

CHILD = r'''
import atexit, json, os
from pathlib import Path
import cv2, httpx, uvicorn
counts = {"camera_open_attempts": 0, "provider_http_attempts": 0,
          "photon_send_attempts": 0, "photon_poll_attempts": 0}
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
from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app
app = create_app(Settings(_env_file=None, data_dir=Path(os.environ["AUDIT_STORE"]),
                          local_token=os.environ["AUDIT_OPERATOR_TOKEN"]))
@app.get("/__offline_audit__/identity")
def identity():
    return {"nonce": os.environ["AUDIT_PROCESS_NONCE"]}
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
            return response.json()

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
            current_forecast_snapshot_sha256=currents["snapshot_sha256"],
            current_forecast_method_sha256=currents["method_sha256"],
            no_live_provider_calls=True, no_physical_trials=True)


if __name__ == "__main__":
    raise SystemExit(main())
