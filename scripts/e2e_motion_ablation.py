"""Read-only loopback audit of real-data ML ablation; no provider or camera calls."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from e2e_demo import local_api


def audit(api="http://127.0.0.1:8000"):
    api = local_api(api)
    result = {"created_at_utc": datetime.now(UTC).isoformat(), "checks": [],
        "provider_calls": 0, "photon_messages_sent": False, "physical_trials_run": 0,
        "hardware_actuation": False, "camera_opened": False}

    def check(name, ok):
        result["checks"].append({"check": name, "status": "PASS" if ok else "FAIL"})
        if not ok:
            raise ValueError("Audit assertion failed: " + name)

    with httpx.Client(timeout=20, follow_redirects=False) as client:
        def get(path):
            response = client.get(api + "/api/v1" + path)
            if response.status_code != 200:
                raise ValueError(f"{path} returned HTTP {response.status_code}")
            return response.json()
        try:
            before_status, before_cases = get("/status"), get("/cases")
            check("Photon, camera and hardware are off before research", before_status["photon"]["enabled"] is False
                and before_status["camera"]["running"] is False and before_status["hardware_actuation"] is False)
            legacy = get("/research/training-diagnostic")
            benchmark = get("/research/real-data")
            report = get("/research/motion-ablation")
            check("authentic pinned NOAA data and training-only scope", report["kind"] == "TRAINING_ONLY_MOTION_ABLATION"
                and report["provenance"]["sha256"] == legacy["provenance"]["sha256"] == benchmark["provenance"]["sha256"]
                and report["provenance"]["integrity_verified"] is True
                and report["test_data_used"] is False and report["model_selection_performed"] is False
                and report["physical_validation"] is False and report["automatic_model_promotion"] is False)
            check("four fixed motion models share the same five origins and six horizons", report["split"]["prefix_counts"] == [8, 9, 10, 11, 12]
                and report["split"]["horizons"] == 6 and report["split"]["training_count"] == 18
                and len(report["origins"]) == 5 and len(report["aggregates"]) == 4
                and {row["baseline_id"] for row in report["paired_comparisons"]} == {"stationary", "last_drift", "mean_drift"})
            for comparison in report["paired_comparisons"]:
                for row in comparison["per_horizon"]:
                    check(f"paired count accounting: {comparison['baseline_id']} at horizon {row['horizon_hours']}",
                        row["count"] == 5 and row["candidate_lower_error_count"] + row["equal_error_count"]
                        + row["candidate_higher_error_count"] == 5)
            first = next(row for row in report["paired_comparisons"] if row["baseline_id"] == "last_drift")["per_horizon"][0]
            check("the learned model may lose to a simple baseline", first["candidate_lower_error_count"] == 0
                and first["candidate_higher_error_count"] == 5 and first["mean_delta_m"] > 0)
            check("repeated research is deterministic", get("/research/motion-ablation") == report)
            check("existing training diagnostic and frozen heldout benchmark are unchanged",
                get("/research/training-diagnostic") == legacy and get("/research/real-data") == benchmark)
            check("research leaves cases, Photon and camera unchanged", get("/cases") == before_cases
                and get("/status") == before_status)
            result["evidence"] = {"kind": report["kind"], "dataset_sha256": report["provenance"]["sha256"],
                "split": report["split"], "one_hour_ridge_vs_last_drift": first}
        except (ValueError, KeyError, TypeError, httpx.HTTPError) as error:
            result["checks"].append({"check": "workflow completion", "status": "FAIL", "reason": str(error)[:300]})
    counts = {state: sum(row["status"] == state for row in result["checks"]) for state in ("PASS", "FAIL")}
    result["summary"] = {**counts, "software_workflow_passed": counts["FAIL"] == 0, "physical_validation": False}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "work/e2e-motion-ablation.json")
    args = parser.parse_args()
    report = audit(args.api)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"]))
    raise SystemExit(0 if report["summary"]["software_workflow_passed"] else 1)
