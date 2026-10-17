"""Exercise mounted team features over loopback, before enabling live messaging.

This checks software with a stopped camera and no provider requests. It does not
commission a physical rig or claim independence for the NOAA sample.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from e2e_demo import ROOT, local_api


def audit(api, token):
    api = local_api(api)
    if not token:
        raise ValueError("A private local operator token is required")
    result = {"created_at_utc": datetime.now(UTC).isoformat(), "checks": [],
              "provider_calls": 0, "messages_sent": 0, "camera_opened": False,
              "physical_trials_performed": False, "hardware_actuation": False}

    def check(label, ok):
        result["checks"].append({"check": label, "status": "PASS" if ok else "FAIL"})
        if not ok:
            raise ValueError("Failed assertion: " + label)

    with httpx.Client(timeout=30, follow_redirects=False) as client:
        def request(path, body=None, expected=200, auth=True):
            response = client.request("GET" if body is None else "POST", api + "/api/v1" + path,
                json=body, headers={"Authorization": "Bearer " + token} if auth else {})
            if response.status_code != expected:
                raise ValueError(f"{path} returned {response.status_code}, expected {expected}")
            return response.json()

        try:
            status, cases = request("/status"), request("/cases")
            check("research audit starts with messaging and physical capture off",
                  not status["photon"]["enabled"] and not status["camera"]["running"]
                  and not status["hardware_actuation"])
            receipts = request("/field-sessions")
            missing_rig = {"camera_session_id": "not-started"}
            check("field write requires operator authentication",
                  bool(request("/field-sessions/preflight", missing_rig, 401, False).get("detail")))
            preflight = request("/field-sessions/preflight", missing_rig)
            check("absent physical rig cannot pass commissioning", preflight["status"] != "READY")
            check("blocked freeze is rejected", bool(request("/field-sessions", missing_rig, 409).get("detail")))
            check("preflight and blocked freeze create no field receipt", request("/field-sessions") == receipts)

            method = request("/research/prevention-method-example")
            check("Trace 2 uses a distinct explicit synthetic replay envelope",
                  method["schema_version"] == "prevention_method_replay_v1"
                  and method["kind"] == "SYNTHETIC_REPLAY_EXAMPLE" and method["not_current_case"] is True
                  and method["method_rerun"] is True and method["physical_validation"] is False)
            check("alternative examples are separate, not pooled", len(method["examples"]) == 2
                  and method["examples_are_independent"] is False)
            unresolved = next(x for x in method["examples"] if x["id"] == "unresolved")
            check("shared Trace 2 fixture exactly matches rerun", unresolved["provenance"]["expected_report_match"] is True)
            check("Trace 2 identifies a next independent measurement", unresolved["report"]["next_measurement"]["source_id"] == "B")
            check("method replay is deterministic", request("/research/prevention-method-example") == method)

            original, diagnostic = request("/research/real-data"), request("/research/training-diagnostic")
            study = request("/research/multi-drifter")
            check("new data are declared as real historical unseen-drifter evaluation",
                  study["kind"] == "MULTI_DRIFTER_RETROSPECTIVE_STUDY"
                  and study["data_origin"] == "REAL_HISTORICAL_NOAA_DRIFTERS"
                  and study["test_data_used"] is True and study["model_selection_performed"] is False
                  and study["physical_validation"] is False and study["automatic_model_promotion"] is False
                  and study["independent_replication_verified"] is False and study["statistical_independence"] is False)
            ids = {g["drifter_id"] for g in study["groups"]}
            check("entire inspected drifter is excluded", len(ids) == len(study["groups"]) and "8707978" not in ids)
            coverage = study["coverage"]
            check("unfilled acquisition slots remain visible", coverage["target_groups"] == 6
                  and coverage["declared_groups"] == len(ids) and len(ids) <= 6)
            expected = {(d, m, h) for d in ids for m in ("stationary", "last_drift", "mean_drift", "ridge_ar1") for h in range(1, 7)}
            rows = study["outcomes"]
            actual = {(r["drifter_id"], r["model_id"], r["horizon_hours"]) for r in rows}
            check("all declared model/group/horizon outcomes are retained exactly once", actual == expected and len(rows) == len(expected))
            check("scored and failed outcomes preserve the declared denominator",
                  coverage["attempted_outcomes"] == len(expected)
                  and coverage["scored_outcomes"] + coverage["failed_outcomes"] == len(expected))
            check("failed predictions carry explicit reasons and no fake error", all(
                (r["error_m"] is not None) if r["status"] == "SCORED" else
                r["error_m"] is None and bool(r["reason_codes"]) for r in rows))
            check("preregistered protocol and sources are verified", study["provenance"]["integrity_verified"] is True
                  and len(study["protocol"]["sha256"]) == 64 and study["protocol"]["training_count"] == 18)
            check("new study is deterministic", request("/research/multi-drifter") == study)
            check("original single-day research remains unchanged", request("/research/real-data") == original
                  and request("/research/training-diagnostic") == diagnostic)
            check("team research leaves cases and operational state unchanged",
                  request("/cases") == cases and request("/status") == status)
            result["evidence"] = {"field_preflight_status": preflight["status"],
                "method_next_measurement": unresolved["report"]["next_measurement"],
                "multi_drifter_study_id": study["study_id"], "coverage": coverage,
                "models": study["models"], "protocol": study["protocol"]}
        except (ValueError, KeyError, TypeError, httpx.HTTPError) as error:
            result["checks"].append({"check": "workflow completion", "status": "FAIL",
                "reason": str(error).replace(token, "[redacted]")[:300]})
    result["summary"] = {state: sum(r["status"] == state for r in result["checks"]) for state in ("PASS", "FAIL")}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=ROOT / "work/e2e-team-integration.json")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env", override=False)
    report = audit(args.api, os.getenv("REEFTRACE_LOCAL_TOKEN", ""))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report["summary"]))
    raise SystemExit(1 if report["summary"]["FAIL"] else 0)
