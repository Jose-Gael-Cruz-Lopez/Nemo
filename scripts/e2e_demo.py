"""Audit the running local API without opening hardware or sending Photon messages.

Run .venv/bin/python scripts/e2e_demo.py --output work/e2e-demo.json.
The private operator token is read from the repository .env and is never printed.
Configured Chalk can make a metered model request. Missing sponsor credentials
remain explicit blockers; scripted transport never pretends to be a live answer.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def local_api(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
        raise ValueError("This audit only accepts an HTTP loopback API origin")
    return value.rstrip("/")


def audit(api_url: str, token: str, *, client: httpx.Client | None = None) -> dict:
    api_url = local_api(api_url)
    if not token:
        raise ValueError("Set REEFTRACE_LOCAL_TOKEN in the private local .env before the audit")
    result = {"created_at_utc": datetime.now(UTC).isoformat(), "api_url": api_url,
              "scope": "actual local HTTP API; synthetic source replay plus separate real NOAA forecast",
              "camera_opened": False, "hardware_actuation": False,
              "photon_messages_sent": False, "checks": [], "evidence": {}}
    owned = client is None
    http = client or httpx.Client(timeout=90, follow_redirects=False)

    def check(name, ok, **details):
        result["checks"].append({"check": name, "status": "PASS" if ok else "FAIL", **details})
        if not ok:
            raise ValueError(f"Audit assertion failed: {name}")

    def request(path, body=None, *, authenticated=True, expected=200):
        response = http.request("GET" if body is None else "POST", api_url + "/api/v1" + path,
                                headers={"Authorization": "Bearer " + token} if authenticated else {},
                                json=body)
        if response.status_code != expected:
            raise ValueError(f"{path} returned HTTP {response.status_code}; expected {expected}")
        return response.json()

    try:
        check("API health", request("/health") == {"status": "ok"})
        readiness = request("/status")
        check("no hardware actuation", readiness["hardware_actuation"] is False)
        check("unauthorized mutation rejected", bool(request("/demo/load", {},
              authenticated=False, expected=401).get("detail")))
        first = request("/demo/load", {})
        loaded = first["cases"]
        check("source replay is explicitly synthetic", first["mode"] == "SYNTHETIC"
              and first["physical_validation"] is False)
        again = request("/demo/load", {})
        check("repeated demo load is idempotent", [row["case"]["id"] for row in loaded] == [
            row["case"]["id"] for row in again["cases"]])
        check("three contrasting source cases", [row["evidence"]["status"] for row in loaded]
              == ["ranked", "unknown", "invalid"])
        case_id = loaded[0]["case"]["id"]
        check("case selection loads its saved observation", bool(request(f"/cases/{case_id}")["points"]))
        recomputed = []
        for row in loaded:
            report = request(f"/cases/{row['case']['id']}/estimate", {})
            check("recompute " + row["evidence"]["status"], report["status"] == row["evidence"]["status"]
                  and report["confidence_kind"] == "relative_support_not_probability")
            recomputed.append(report)
        check("known synthetic trajectory ranks its development source", recomputed[0]["ranked_source"] == "C")
        sensitivity = request(f"/cases/{case_id}/sensitivity", {
            "preset_id": "predeclared-transport-envelope-v1"})
        check("sensitivity is bound to latest evidence", sensitivity["parent_estimate_id"] == recomputed[0]["id"]
              and len(sensitivity["variants"]) == 2)
        answer = request(f"/cases/{case_id}/investigate", {
            "text": "Explain which candidate source the saved path supports and what remains uncertain. Preserve the numerical report."})
        check("investigation keeps numerical source authority", answer["source_report"] == recomputed[0])
        if answer.get("live_model_response"):
            check("Chalk live structured response", answer["provider"] == "chalk"
                  and answer["action"] == "REPORT" and bool(answer["trace"])
                  and recomputed[0]["id"] in answer["evidence_ids"])
        else:
            check("Chalk fallback is explicit", answer["action"] == "STOP"
                  and answer["live_model_response"] is False)
            result["checks"].append({"check": "Chalk live model verification", "status": "BLOCKED",
                "reason": "Live Chalk response unavailable; configure gateway credentials/model or inspect provider failure.",
                "failure_code": answer.get("failure_code"),
                "provider_status_code": answer.get("provider_status_code"),
                "configuration_reasons": readiness["chalk"]["reasons"]})
        check("manual task history is recoverable", isinstance(request(f"/cases/{case_id}/actions"), list))
        real_data = request("/research/real-data")
        check("real NOAA chronological holdout", real_data["data_origin"] == "REAL_HISTORICAL_NOAA_DRIFTER"
              and real_data["split"]["training_count"] == 18 and real_data["split"]["heldout_count"] == 6
              and real_data["split"]["test_values_used_for_model_selection"] is False)
        request_body = {key: value for key, value in loaded[0]["case"].items() if key in {
            "profile_id", "calibration_id", "token_class", "points", "endpoint",
            "evidence_frame_ids", "mode", "camera_session_id", "association_valid"}}
        disposable = request("/cases", request_body)
        stopped_id = disposable["id"]
        check("STOP changes only disposable case", request(f"/cases/{stopped_id}/stop", {})["state"] == "STOPPED")
        request(f"/cases/{stopped_id}/estimate", {}, expected=409)
        request(f"/cases/{stopped_id}/sensitivity", {
            "preset_id": "predeclared-transport-envelope-v1"}, expected=409)
        stopped_answer = request(f"/cases/{stopped_id}/investigate", {"text": "Continue"})
        check("stopped case cannot continue", stopped_answer["action"] == "STOP"
              and stopped_answer["live_model_response"] is False and stopped_answer["source_report"] is None)
        result["evidence"] = {"source_cases": [{"case_id": row["case"]["id"],
                "evidence_id": report["id"], "status": report["status"],
                "ranked_source": report.get("ranked_source"),
                "relative_support": report.get("relative_support"),
                "reason_codes": report.get("reason_codes")} for row, report in zip(loaded, recomputed, strict=True)],
            "sensitivity_id": sensitivity["id"], "investigation_action": answer["action"],
            "live_chalk_response": answer["live_model_response"],
            "real_data_experiment_id": real_data["experiment_id"],
            "real_data_split": real_data["split"], "disposable_stopped_case": stopped_id}
        result["checks"].extend([
            {"check": "physical webcam/tank calibration", "status": "BLOCKED",
             "reason": "Requires connected external camera, measured drift and blind physical trials; audit does not open hardware."},
            {"check": "Photon device round trip", "status": "BLOCKED",
             "reason": "Requires configured assigned channel and authorized human-initiated message; audit sends no messages.",
             "configuration_reasons": readiness["photon"]["reasons"]}])
    except (ValueError, KeyError, TypeError, httpx.HTTPError) as error:
        # Errors contain endpoint/status and assertions, never request headers or env.
        result["checks"].append({"check": "workflow completion", "status": "FAIL",
                                  "reason": str(error).replace(token, "[redacted]")[:400]})
    finally:
        if owned:
            http.close()
    counts = {state: sum(row["status"] == state for row in result["checks"])
              for state in ("PASS", "FAIL", "BLOCKED")}
    result["summary"] = {**counts, "software_workflow_passed": counts["FAIL"] == 0,
                         "complete_live_product_verified": counts["FAIL"] == counts["BLOCKED"] == 0}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=ROOT / "work/e2e-demo.json")
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env", override=False)
    try:
        result = audit(args.api, os.environ.get("REEFTRACE_LOCAL_TOKEN", ""))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result["summary"]))
    print("Report: " + str(args.output))
    return 0 if result["summary"]["software_workflow_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
