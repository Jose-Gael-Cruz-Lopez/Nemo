"""Loopback Trace 3 contract audit; synthetic ledger only and one bounded Chalk turn."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import dotenv_values
from e2e_demo import local_api


def audit(*, token, api="http://127.0.0.1:8000"):
    api = local_api(api)
    if not token:
        raise ValueError("Private local operator token required")
    result = {"created_at_utc": datetime.now(UTC).isoformat(), "checks": [],
              "physical_trials_run": 0, "photon_messages_sent": False,
              "hardware_actuation": False, "camera_opened": False}

    def check(label, passed):
        result["checks"].append({"check": label, "status": "PASS" if passed else "FAIL"})
        if not passed:
            raise ValueError("Assertion failed: " + label)

    with httpx.Client(timeout=90, follow_redirects=False) as client:
        def req(path, body=None, *, expected=200, auth=True):
            response = client.request("GET" if body is None else "POST", api + "/api/v1" + path,
                headers={"Authorization": "Bearer " + token} if auth else {}, json=body)
            if response.status_code != expected:
                raise ValueError(f"{path} returned {response.status_code}; expected {expected}")
            return response.json()
        try:
            status = req("/status")
            check("audit starts with Photon, camera, actuation and Voice off", not status["photon"]["enabled"]
                and not status["camera"]["running"] and not status["hardware_actuation"]
                and not status["grok"]["enabled"])
            demo = req("/prevention/demo", {})
            source_case = req("/cases/" + demo["comparison"]["case_id"])
            fields = {"profile_id", "calibration_id", "token_class", "points", "endpoint",
                      "evidence_frame_ids", "mode", "camera_session_id", "association_valid"}
            case = req("/cases", {key: value for key, value in source_case.items() if key in fields})
            source = req(f"/cases/{case['id']}/estimate", {})
            detail = req("/prevention/comparisons", {
                "case_id": case["id"], "name": "Trace 3 synthetic contract audit",
                "baseline_profile_id": demo["comparison"]["baseline_profile_id"],
                "intervention_profile_id": demo["comparison"]["intervention_profile_id"],
                "protected_zone_cm": demo["comparison"]["protected_zone_cm"],
                "horizon_s": 20, "particles": 60, "trials_per_source": 2})
            cid = detail["comparison"]["id"]
            base = f"/prevention/comparisons/{cid}"
            trial = {"trial_key": "trace3-audit-baseline", "layout": "baseline", "source_id": "A",
                "data_origin": "SYNTHETIC_DEMO", "outcome": "zone_entry", "entry_time_s": 15,
                "interception_time_s": None, "token_accounted": True, "physical_confirmed": False,
                "horizon_completed": True, "note": "Synthetic interface audit only."}
            req(base + "/trials", trial)
            detail = req(base + "/trials", {**trial, "trial_key": "trace3-audit-intervention",
                "layout": "intervention", "outcome": "unresolved", "entry_time_s": None,
                "token_accounted": False, "horizon_completed": False})
            req(base + "/export", expected=401, auth=False)
            bundle = req(base + "/export")
            check("authenticated export preserves canonical bytes and exact evidence identities",
                hashlib.sha256(bundle["payload_canonical_json"].encode()).hexdigest() == bundle["payload_sha256"]
                and json.loads(bundle["payload_canonical_json"]) == bundle["payload"]
                and bundle["payload"]["comparison"]["source_evidence_id"] == source["id"])
            check("export excludes raw prose, trial keys and illustrative paths",
                all("note" not in row and "trial_key" not in row for row in bundle["payload"]["evaluation_truth"]["trials"])
                and "nominal_paths" not in bundle["payload"]["comparison"]["numerical_report"])
            manifest = req(base + "/validation-template?origin=SYNTHETIC_DEMO")
            saved = req(base + "/validation-reports", {"report": manifest})
            same = req(base + "/validation-reports", {"report": manifest})
            rid = saved["report"]["id"]
            check("rehearsal import is idempotent and explicitly not independent validation",
                rid == same["report"]["id"] and saved["report"]["purpose"] == "CONTRACT_REHEARSAL"
                and saved["checks"]["method_rerun"] is False and saved["checks"]["physical_validation"] is False)
            check("server recomputes missing and unresolved counts from saved releases",
                saved["summary"]["validation_count"] == 2 and saved["summary"]["unresolved"] == 1
                and saved["summary"]["missing_planned"] == detail["comparison"]["plan"]["expected_total"] - 2)
            req(base + "/validation-reports", {"report": {**manifest, "accuracy": 1}}, expected=422)
            check("uploaded metrics are rejected", True)
            check("saved history and detail retain exact receipt identity",
                req(base + "/validation-reports")[0]["id"] == rid
                and req(base + "/validation-reports/" + rid)["report"] == saved["report"])
            answer = req(base + "/investigate", {"text":
                "Read the case, source evidence, prevention evidence and selected validation evidence. Explain the contract rehearsal, missing and unresolved outcomes, and next measurement. Keep Unknown source identity unchanged. Cite all exact returned evidence IDs.",
                "validation_report_id": rid})
            check("Chalk review remains tied to selected receipt and immutable evaluation",
                answer["validation_report_id"] == rid
                and answer["evaluation_digest"] == manifest["evaluation_snapshot_hash"]
                and answer["validation_summary"] == saved["summary"])
            if answer.get("live_model_response"):
                check("live Chalk reads all four scoped tools and cites selected receipt",
                    {"get_case", "get_source_evidence", "get_prevention_evidence", "get_validation_evidence"}
                    <= {row["tool"] for row in answer["trace"]}
                    and {source["id"], cid, detail["evaluation"]["id"], rid} <= set(answer["evidence_ids"]))
            else:
                check("provider failure is explicit without fabricated results", answer["action"] == "STOP")
                result["checks"].append({"check": "live Chalk validation review", "status": "BLOCKED",
                    "failure_code": answer.get("failure_code"), "provider_status_code": answer.get("provider_status_code")})
            req(base + "/trials", {**trial, "trial_key": "trace3-audit-new-slot", "source_id": "B"})
            archive = req(base + "/validation-reports/" + rid)
            req(base + "/validation-reports", {"report": manifest}, expected=409)
            req(base + "/investigate", {"text": "Explain old report.", "validation_report_id": rid}, expected=409)
            check("new trial archives receipt and rejects stale import and Chalk review",
                not archive["is_current"] and archive["archive_reason"] == "EVALUATION_CHANGED")
            req(f"/cases/{case['id']}/stop", {})
            check("STOP retains readable archival evidence", not req(base)["is_current"]
                and not req(base + "/export")["metadata"]["is_current"])
            status = req("/status")
            check("Photon, camera and hardware remain off after audit", not status["photon"]["enabled"]
                and not status["camera"]["running"] and not status["hardware_actuation"])
            result["evidence"] = {"comparison_id": cid, "validation_report_id": rid,
                "payload_sha256": bundle["payload_sha256"], "chalk": {key: answer.get(key) for key in
                ("action", "live_model_response", "evidence_ids", "failure_code", "provider_status_code")}}
        except (ValueError, KeyError, TypeError, httpx.HTTPError) as error:
            result["checks"].append({"check": "workflow completion", "status": "FAIL",
                "reason": str(error).replace(token, "[redacted]")[:400]})
    counts = {state: sum(row["status"] == state for row in result["checks"]) for state in ("PASS", "FAIL", "BLOCKED")}
    result["summary"] = {**counts, "software_workflow_passed": counts["FAIL"] == 0, "physical_validation": False}
    return result


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    report = audit(token=dotenv_values(root / ".env").get("REEFTRACE_LOCAL_TOKEN"))
    report_path = root / "work/e2e-validation.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report["summary"]))
    raise SystemExit(0 if report["summary"]["software_workflow_passed"] else 1)
