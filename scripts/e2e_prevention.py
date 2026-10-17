"""Actual loopback prevention audit; synthetic releases only, no camera or messages.

The configured Chalk gateway is called once. Missing provider service is recorded
as BLOCKED, never replaced by a pretend live response or physical measurement.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from e2e_demo import local_api

ROOT = Path(__file__).resolve().parents[1]


def audit(api="http://127.0.0.1:8000", *, token):
    api = local_api(api)
    if not token:
        raise ValueError("Private local operator token is required")
    result = {"created_at_utc": datetime.now(UTC).isoformat(), "checks": [],
              "scope": "actual HTTP prevention API, separate synthetic trial ledger and bounded Chalk review",
              "physical_trials_run": 0, "camera_opened": False,
              "hardware_actuation": False, "photon_messages_sent": False}

    def check(label, passed):
        result["checks"].append({"check": label, "status": "PASS" if passed else "FAIL"})
        if not passed:
            raise ValueError("Assertion failed: " + label)

    with httpx.Client(timeout=90, follow_redirects=False) as client:
        def request(path, body=None, *, expected=200, auth=True):
            response = client.request("GET" if body is None else "POST", api + "/api/v1" + path,
                headers={"Authorization": "Bearer " + token} if auth else {}, json=body)
            if response.status_code != expected:
                raise ValueError(f"{path} returned {response.status_code}; expected {expected}")
            return response.json()
        try:
            status = request("/status")
            check("Photon replies and hardware are off", status["photon"]["enabled"] is False
                  and status["camera"]["running"] is False and status["hardware_actuation"] is False)
            request("/prevention/demo", {}, expected=401, auth=False)
            check("operator authentication protects prevention writes", True)
            demo = request("/prevention/demo", {})
            same = request("/prevention/demo", {})
            check("synthetic demo is idempotent and never measured", demo["comparison"]["id"] == same["comparison"]["id"]
                  and demo["comparison"]["data_origin"] == "SYNTHETIC"
                  and demo["evaluation"]["by_origin"]["OPERATOR_REPORTED_PHYSICAL"]["plan"]["recorded_total"] == 0)
            source_case = request("/cases/" + demo["comparison"]["case_id"])
            fields = {"profile_id", "calibration_id", "token_class", "points", "endpoint",
                      "evidence_frame_ids", "mode", "camera_session_id", "association_valid"}
            case = request("/cases", {k: v for k, v in source_case.items() if k in fields})
            source = request(f"/cases/{case['id']}/estimate", {})
            plan = request("/prevention/comparisons", {
                "case_id": case["id"], "name": "HTTP synthetic prevention audit",
                "baseline_profile_id": demo["comparison"]["baseline_profile_id"],
                "intervention_profile_id": demo["comparison"]["intervention_profile_id"],
                "protected_zone_cm": demo["comparison"]["protected_zone_cm"],
                "horizon_s": 20, "particles": 60, "trials_per_source": 2})
            comparison_id = plan["comparison"]["id"]
            base = f"/prevention/comparisons/{comparison_id}"
            numeric = plan["comparison"]["numerical_report"]
            check("prediction is frozen against exact source and layout artifacts",
                  plan["comparison"]["source_evidence_id"] == source["id"]
                  and numeric["physical_validation"] is False and len(numeric["results"]) >= 3
                  and numeric["layouts"]["baseline"]["profile_hash"] != numeric["layouts"]["intervention"]["profile_hash"])
            scene_url = base + "/scene?evaluation_snapshot_hash=" + plan["evaluation"]["snapshot_hash"]
            scene = request(scene_url, auth=False)
            scene_hash = scene.pop("scene_sha256")
            check("3D scene is a read-only hash-bound view of the frozen comparison",
                  scene["kind"] == "TANK_RIG_SCENE" and scene["comparison_id"] == comparison_id
                  and scene["evaluation_snapshot_hash"] == plan["evaluation"]["snapshot_hash"]
                  and scene_hash == hashlib.sha256(json.dumps(
                      scene, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
                  and request(base) == plan)
            check("3D forecasts retain the complete ensemble rather than count display paths",
                  scene["results"]["rows"][0]["baseline"]["particles"] == numeric["particles_per_source"]
                  and all(len(path["points"]) <= 80 and path["counts_derived_from_path"] is False
                          and (not path["points"] if path["support_status"] == "UNSUPPORTED_PATH_WITHHELD"
                               else all(point["t_s"] <= path["display_stop_s"] for point in path["points"]))
                          for path in scene["simulation"]["paths"]))
            check("3D rig does not invent depth, measured motion or release alignment",
                  scene["vertical"]["measured_depth_cm"] is None
                  and scene["physical_validation"] is False and scene["actual"]["status"] == "NOT_CAPTURED"
                  and scene["actual"]["recordings"] == []
                  and scene["actual"]["clock"] == "CAPTURE_START_UNALIGNED"
                  and scene["actual"]["positional_error_metrics"] is None)
            trial = {"trial_key": "http-a-baseline", "layout": "baseline", "source_id": "A",
                     "data_origin": "SYNTHETIC_DEMO", "outcome": "zone_entry", "entry_time_s": 15,
                     "interception_time_s": 18, "token_accounted": True, "physical_confirmed": False,
                     "horizon_completed": True, "note": "Synthetic API audit: later collection does not undo earlier entry."}
            first = request(base + "/trials", trial)
            duplicate = request(base + "/trials", trial)
            check("retrying a trial is idempotent", len(first["trials"]) == len(duplicate["trials"]) == 1
                  and first["evaluation"]["snapshot_hash"] == duplicate["evaluation"]["snapshot_hash"])
            request(base + "/trials", {**trial, "note": "Changed immutable payload"}, expected=409)
            check("trial keys cannot rewrite outcomes", True)
            second = request(base + "/trials", {**trial, "trial_key": "http-a-intervention",
                "layout": "intervention", "outcome": "intercepted_before_entry", "entry_time_s": None,
                "interception_time_s": 10, "note": "Synthetic API audit: retained before entry."})
            third = request(base + "/trials", {**trial, "trial_key": "http-b-unresolved", "source_id": "B",
                "outcome": "unresolved", "entry_time_s": None, "interception_time_s": None,
                "token_accounted": False, "horizon_completed": False,
                "note": "Synthetic API audit: tracking lost; do not infer prevention."})
            evaluation = third["evaluation"]
            synthetic = evaluation["by_origin"]["SYNTHETIC_DEMO"]
            check("unresolved and missing trials stay in displayed bounds",
                  synthetic["layouts"]["baseline"]["released"] == 2
                  and synthetic["layouts"]["baseline"]["zone_entries"] == 1
                  and synthetic["layouts"]["baseline"]["unresolved"] == 1
                  and synthetic["layouts"]["baseline"]["entry_rate_bounds"]["denominator"] == 6
                  and synthetic["plan"]["complete"] is False
                  and synthetic["supports_causal_claim"] is False
                  and evaluation["snapshot_hash"] != second["evaluation"]["snapshot_hash"])
            request(scene_url, expected=409, auth=False)
            updated_scene = request(base + "/scene?evaluation_snapshot_hash=" + evaluation["snapshot_hash"], auth=False)
            check("3D rejects stale evaluation identity and reflects separate updated synthetic outcomes",
                  updated_scene["results"]["by_origin"] == evaluation["by_origin"]
                  and updated_scene["actual"]["reported_physical_trial_count"] == 0
                  and updated_scene["numerical_report_sha256"] == scene["numerical_report_sha256"])
            request(base + "/trials", {**trial, "trial_key": "false-physical",
                "data_origin": "OPERATOR_REPORTED_PHYSICAL", "physical_confirmed": True}, expected=409)
            check("synthetic layouts reject physical measurement claims", True)
            before = request("/cases/" + case["id"])
            answer = request(base + "/investigate", {"text":
                "Read the source evidence and prevention evidence. Explain the frozen layout comparison and incomplete synthetic trial bounds. Keep UNKNOWN source identity unchanged. Cite the source, comparison and evaluation IDs. Do not propose an action."})
            check("Chalk preserves frozen deterministic evidence and trial identity",
                  answer["comparison_id"] == comparison_id
                  and answer["evaluation_digest"] == evaluation["snapshot_hash"]
                  and answer["prevention_evaluation"] == evaluation
                  and answer["source_report"] == source
                  and request("/cases/" + case["id"]) == before)
            if answer.get("live_model_response"):
                check("live Chalk reads all prevention tools and cites exact snapshots",
                      {"get_case", "get_source_evidence", "get_prevention_evidence"} <=
                      {row["tool"] for row in answer["trace"]}
                      and {comparison_id, evaluation["id"], source["id"]} <= set(answer["evidence_ids"]))
            else:
                check("Chalk provider failure is explicit and does not invent results", answer["action"] == "STOP")
                result["checks"].append({"check": "live Chalk prevention response", "status": "BLOCKED",
                    "failure_code": answer.get("failure_code"),
                    "provider_status_code": answer.get("provider_status_code"),
                    "timeout_stage": answer.get("timeout_stage")})
            request(f"/cases/{case['id']}/stop", {})
            archive = request(base)
            request(base + "/trials", {**trial, "trial_key": "after-stop"}, expected=409)
            request(base + "/investigate", {"text": "Continue"}, expected=409)
            check("STOP preserves readable history and blocks new writes", archive["is_current"] is False
                  and len(archive["trials"]) == 3)
            archived_scene = request(base + "/scene?evaluation_snapshot_hash=" + archive["evaluation"]["snapshot_hash"], auth=False)
            check("archived 3D comparison remains readable without reviving the experiment",
                  archived_scene["is_current"] is False
                  and archived_scene["archive_reason"] == "CASE_CHANGED_OR_STOPPED"
                  and request("/cases/" + case["id"])["state"] == "STOPPED")
            final = request("/status")
            check("Photon and camera remain off after the complete workflow",
                  final["photon"]["enabled"] is False and final["camera"]["running"] is False)
            result["evidence"] = {"comparison_id": comparison_id,
                "source_evidence_id": source["id"], "evaluation_id": evaluation["id"],
                "evaluation_digest": evaluation["snapshot_hash"], "prediction": numeric,
                "evaluation": evaluation, "chalk": {key: answer.get(key) for key in (
                    "action", "live_model_response", "evidence_ids", "failure_code", "investigation_id")}}
        except (ValueError, KeyError, TypeError, httpx.HTTPError) as error:
            result["checks"].append({"check": "workflow completion", "status": "FAIL",
                                     "reason": str(error).replace(token, "[redacted]")[:400]})
    counts = {state: sum(row["status"] == state for row in result["checks"])
              for state in ("PASS", "FAIL", "BLOCKED")}
    result["summary"] = {**counts, "software_workflow_passed": counts["FAIL"] == 0,
                         "physical_validation": False}
    return result


if __name__ == "__main__":
    load_dotenv(ROOT / ".env", override=False)
    report = audit(token=os.environ.get("REEFTRACE_LOCAL_TOKEN", ""))
    path = ROOT / "work/e2e-prevention.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report["summary"]))
    print("Report: " + str(path))
    raise SystemExit(0 if report["summary"]["software_workflow_passed"] else 1)
