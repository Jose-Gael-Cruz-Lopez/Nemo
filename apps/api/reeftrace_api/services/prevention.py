"""Frozen intervention comparisons and a separate, provenance-labelled trial ledger.

No camera, provider or actuator is opened here. A model prediction is never a
physical outcome. Missing planned trials remain unknown in the plan's bounds.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import math
import time
from datetime import datetime

from ..schemas.contracts import CaseInput
from ..schemas.prevention import ComparisonInput, TrialInput
from .store import uid

COMPARISON_KIND = "prevention_comparison"
TRIAL_KIND = "prevention_trial"
ORIGINS = ("SYNTHETIC_DEMO", "OPERATOR_REPORTED_PHYSICAL")
LAYOUTS = ("baseline", "intervention")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _profile_snapshot(profile, profile_hash):
    keys = ("id", "bounds", "sources", "traps", "token_class", "calibration_id",
            "observation_polygon_cm", "data_origin")
    return {**{key: copy.deepcopy(profile[key]) for key in keys if key in profile},
            "profile_hash": profile_hash, "flow_id": profile.get("flow", {}).get("id")}


def _finite_timestamp(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Linked recording needs finite prospective capture timestamps")
    return float(value)


class PreventionService:
    def __init__(self, runtime):
        self.runtime = runtime
        self.store = runtime.store
        self.demo_lock = asyncio.Lock()

    @staticmethod
    def _assert_case(comparison, case):
        if (case["state"] in {"STOPPED", "RECOVERING"}
                or case["revision"] != comparison["case_revision"]
                or case.get("evidence_id") != comparison["source_evidence_id"]):
            raise ValueError("Source case changed or stopped; create a new frozen prevention comparison")
        return case

    def assert_active(self, comparison):
        return self._assert_case(comparison, self.store.case(comparison["case_id"]))

    def commit_for_comparison(self, kind, payload, comparison, *, expected_evaluation_hash=None):
        """Shared receipt seam for the separately owned bounded Chalk investigator."""
        if expected_evaluation_hash is None:
            self.assert_active(comparison)
            return self.store.put_case_result(kind, payload, comparison["case_id"],
                                              comparison["case_revision"])
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM cases WHERE id=?", (comparison["case_id"],)).fetchone()
            if row is None:
                raise KeyError(comparison["case_id"])
            self._assert_case(comparison, json.loads(row[0]))
            current_hash = self.evaluate(comparison, self._trials(comparison["id"], db))["snapshot_hash"]
            if current_hash != expected_evaluation_hash:
                raise ValueError("Trial evaluation changed while investigating; discard the stale answer")
            record = {**payload, "id": uid(kind)}
            db.execute("INSERT INTO records VALUES(?,?,?,?)", (
                kind, record["id"], json.dumps(record, allow_nan=False), time.time()))
        return record

    def _trials(self, comparison_id, db=None):
        if db is None:
            with self.store.connection() as connection:
                return self._trials(comparison_id, connection)
        rows = db.execute("SELECT payload FROM records WHERE kind=? ORDER BY created,id",
                          (TRIAL_KIND,)).fetchall()
        trials = [trial for row in rows if (trial := json.loads(row[0]))["comparison_id"] == comparison_id]
        return sorted(trials, key=lambda trial: (trial["ordinal"], trial["id"]))

    def list_comparisons(self):
        summaries = []
        for comparison in self.store.list(COMPARISON_KIND, 100):
            try:
                self.assert_active(comparison)
                current = True
            except (KeyError, ValueError):
                current = False
            summaries.append({key: comparison[key] for key in (
                "id", "name", "case_id", "source_evidence_id", "data_origin", "created_at")}
                | {"status": comparison["numerical_report"]["status"], "is_current": current})
        return summaries

    def comparison_detail(self, comparison_id, *, require_active=False):
        comparison = self.store.get(COMPARISON_KIND, comparison_id)
        try:
            self.assert_active(comparison)
            current = True
        except (KeyError, ValueError):
            if require_active:
                raise ValueError("Source case changed or stopped; comparison is archival") from None
            current = False
        trials = self._trials(comparison_id)
        return {"comparison": comparison, "trials": trials,
                "evaluation": self.evaluate(comparison, trials), "is_current": current,
                "archive_reason": None if current else "CASE_CHANGED_OR_STOPPED"}

    def _profiles(self, body, case):
        if case["profile_id"] != body.baseline_profile_id:
            raise ValueError("Baseline profile must match the anchored source case")
        if body.baseline_profile_id == body.intervention_profile_id:
            raise ValueError("Compare two distinct registered layout profiles")
        profiles = [self.store.get("profile", profile_id) for profile_id in (
            body.baseline_profile_id, body.intervention_profile_id)]
        baseline, intervention = profiles
        if baseline.get("data_origin") not in {"SYNTHETIC", "MEASURED_TANK"}:
            raise ValueError("Only registered synthetic or measured tank layouts are supported")
        for key in ("data_origin", "bounds", "token_class"):
            if baseline.get(key) != intervention.get(key):
                raise ValueError("Layout origins, bounds and token class must match")
        sources = lambda profile: {str(source["id"]): source for source in profile["sources"]}
        if sources(baseline) != sources(intervention):
            raise ValueError("Freeze identical declared candidate sources in both layouts")
        if baseline["data_origin"] == "MEASURED_TANK":
            flow_ids = [profile.get("flow", {}).get("id") for profile in profiles]
            if not all(flow_ids) or flow_ids[0] == flow_ids[1]:
                raise ValueError("Measured layouts require distinct independently measured immutable flow IDs")
            for profile, flow_id in zip(profiles, flow_ids, strict=True):
                flow = self.store.get("flow", flow_id)
                if flow != profile["flow"] or flow.get("data_origin") != "MEASURED_TANK":
                    raise ValueError("Layout flow must be its unchanged recorded measured artifact")
            provenance = [profile["flow"].get("provenance", {}) for profile in profiles]
            recordings = [set(p.get("training_recording_ids", []) + p.get("validation_recording_ids", []))
                          for p in provenance]
            if not all(recordings) or recordings[0] & recordings[1]:
                raise ValueError("Layout drift measurements must use independent recording sets")
        return baseline, intervention

    async def create_comparison(self, body: ComparisonInput, *, demo_fixture_key=None):
        from apps.estimation.reeftrace_estimation.prevention import compare_layouts

        case = self.store.case(body.case_id)
        if case["state"] in {"STOPPED", "RECOVERING"} or not case.get("evidence_id"):
            raise ValueError("An active case with frozen noninvalid source evidence is required")
        source = self.store.get("estimate", case["evidence_id"])
        if source.get("case_id") != case["id"] or source.get("status") not in {"ranked", "unknown"}:
            raise ValueError("Invalid or mismatched source evidence cannot anchor a comparison")
        baseline, intervention = self._profiles(body, case)
        async with self.runtime.model_budget:
            report = await asyncio.to_thread(compare_layouts, baseline, intervention,
                [list(point) for point in body.protected_zone_cm], horizon_s=body.horizon_s,
                particles=body.particles)
        source_ids = sorted(str(source["id"]) for source in baseline["sources"])
        sequence = []
        for repeat in range(1, body.trials_per_source + 1):
            for index, source_id in enumerate(source_ids):
                layouts = LAYOUTS if (repeat + index) % 2 else tuple(reversed(LAYOUTS))
                sequence.extend({"layout": layout, "source_id": source_id, "repeat": repeat}
                                for layout in layouts)
        plan = {"source_ids": source_ids, "layouts": list(LAYOUTS),
                "trials_per_source": body.trials_per_source, "horizon_s": body.horizon_s,
                "expected_total": len(sequence), "sequence": sequence,
                "unit": "one_token_release", "frozen_before_trials": True,
                "order": "predeclared_counterbalanced_alternation_not_randomized"}
        plan["id"] = "prevention-plan-" + digest(plan)[:20]
        comparison = {**body.model_dump(exclude={"protected_zone_cm"}),
            "case_revision": case["revision"], "source_evidence_id": source["id"],
            "source_evidence_status": source["status"],
            "protected_zone_cm": [list(point) for point in body.protected_zone_cm],
            "data_origin": baseline["data_origin"], "physical_validation": False,
            "baseline_profile": _profile_snapshot(baseline, report["layouts"]["baseline"]["profile_hash"]),
            "intervention_profile": _profile_snapshot(intervention, report["layouts"]["intervention"]["profile_hash"]),
            "numerical_report": report, "plan": plan, "created_at": time.time()}
        if demo_fixture_key:
            comparison["demo_fixture_key"] = demo_fixture_key
        saved = self.store.put_case_result(COMPARISON_KIND, comparison, case["id"], case["revision"])
        return self.comparison_detail(saved["id"])

    def _validate_recording(self, recording_id, comparison, layout):
        recording = self.store.get("recording", recording_id)
        if recording.get("profile_id") != comparison[layout + "_profile_id"]:
            raise ValueError("Linked recording belongs to another layout profile")
        if recording.get("data_origin") != "MEASURED_TANK":
            raise ValueError("Linked recording must be a measured tank capture")
        frozen_at = comparison["created_at"]
        completed_at = _finite_timestamp(recording.get("recorded_at"))
        if completed_at < frozen_at:
            raise ValueError("Linked recording predates the frozen prevention plan")
        points, frame_ids = recording.get("points", []), recording.get("evidence_frame_ids", [])
        if not points or len(points) != len(frame_ids):
            raise ValueError("Linked recording needs timestamped capture frames for prospective provenance")
        for point, frame_id in zip(points, frame_ids, strict=True):
            if point.get("frame_id") != frame_id:
                raise ValueError("Linked recording frame lineage does not match its points")
            frame = self.store.get("frame", frame_id)
            try:
                received = datetime.fromisoformat(frame["received_utc"])
                if received.utcoffset() is None:
                    raise ValueError("Frame receipt timestamp needs a timezone")
                received_at = _finite_timestamp(received.timestamp())
            except (KeyError, TypeError, ValueError, OverflowError) as error:
                raise ValueError("Linked recording needs timezone-aware frame receipt timestamps") from error
            elapsed_s = _finite_timestamp(point.get("t_s"))
            if elapsed_s < 0 or received_at > completed_at:
                raise ValueError("Linked recording has inconsistent capture timestamps")
            # Runtime.record stores completion UTC, not start UTC. A frame's
            # receipt UTC minus its monotonic elapsed time reconstructs the
            # capture start; checking completion alone admits pre-plan footage.
            if received_at - elapsed_s < frozen_at:
                raise ValueError("Linked recording began before the frozen prevention plan")
        # Linking provenance never verifies the reported outcome or whole-horizon
        # observation. The recorder does not persist a requested duration.

    def add_trial(self, comparison_id, body: TrialInput):
        comparison = self.store.get(COMPARISON_KIND, comparison_id)
        if body.source_id not in comparison["plan"]["source_ids"]:
            raise ValueError("Trial source must be in the frozen plan")
        if any(value is not None and value > comparison["horizon_s"] for value in (
                body.entry_time_s, body.interception_time_s)):
            raise ValueError("An observed event cannot exceed the frozen trial horizon")
        if body.data_origin == "OPERATOR_REPORTED_PHYSICAL" and comparison["data_origin"] != "MEASURED_TANK":
            raise ValueError("Synthetic layouts cannot accept a physical-outcome claim")
        if body.recording_id:
            self._validate_recording(body.recording_id, comparison, body.layout)
        request = body.model_dump()
        request_hash = digest(request)
        trial_id = "prevention-trial-" + digest([comparison_id, body.trial_key])[:24]
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM cases WHERE id=?", (comparison["case_id"],)).fetchone()
            if row is None:
                raise KeyError(comparison["case_id"])
            self._assert_case(comparison, json.loads(row[0]))
            existing = db.execute("SELECT payload FROM records WHERE kind=? AND id=?",
                                  (TRIAL_KIND, trial_id)).fetchone()
            if existing:
                if json.loads(existing[0])["request_hash"] != request_hash:
                    raise ValueError("Trial key was already recorded with different immutable data")
            else:
                if body.recording_id:
                    rows = db.execute("SELECT payload FROM records WHERE kind=?", (TRIAL_KIND,)).fetchall()
                    if any(json.loads(row[0]).get("recording_id") == body.recording_id for row in rows):
                        # A recording represents one release, with no sub-trial
                        # windows in this schema. Keep it one release globally,
                        # including comparisons sharing a frozen source case.
                        raise ValueError("Linked recording already belongs to another trial; record a fresh release")
                trials = self._trials(comparison_id, db)
                same_cell = [trial for trial in trials if trial["data_origin"] == body.data_origin
                             and trial["layout"] == body.layout and trial["source_id"] == body.source_id]
                if len(same_cell) >= comparison["trials_per_source"]:
                    raise ValueError("Frozen per-source/layout trial quota is complete")
                trial = {**request, "id": trial_id, "comparison_id": comparison_id,
                         "request_hash": request_hash, "created_at": time.time(), "ordinal": len(trials) + 1,
                         "outcome_verification": "operator_reported_not_automatically_camera_verified"}
                db.execute("INSERT INTO records VALUES(?,?,?,?)", (
                    TRIAL_KIND, trial_id, json.dumps(trial, allow_nan=False), trial["created_at"]))
        return self.comparison_detail(comparison_id)

    @staticmethod
    def _stats(trials, planned):
        released = len(trials)
        entries = sum(t["outcome"] == "zone_entry" for t in trials)
        unresolved = sum(t["outcome"] == "unresolved" for t in trials)
        missing = max(0, planned - released)
        accounted = sum(t["token_accounted"] for t in trials)
        return {"planned": planned, "released": released, "missing_planned": missing,
            "zone_entries": entries,
            "captured_before_entry": sum(t["outcome"] == "intercepted_before_entry" for t in trials),
            "no_entry": sum(t["outcome"] == "no_entry" for t in trials), "unresolved": unresolved,
            "token_accounted": accounted, "unaccounted": released - accounted,
            "recording_linked": sum(bool(t["recording_id"]) for t in trials),
            "horizon_completed": sum(t["horizon_completed"] for t in trials),
            "outcome_resolved": released - unresolved,
            "tracking_verification": "not_automatically_verified",
            "entry_rate_bounds": {"lower": entries / planned,
                "upper": (entries + unresolved + missing) / planned, "denominator": planned,
                "kind": "planned_slots_missing_and_unresolved_are_unknown"},
            "observed_entry_rate_bounds": {"lower": entries / released if released else 0.0,
                "upper": (entries + unresolved) / released if released else 1.0,
                "denominator": released, "kind": "actual_releases_including_unresolved"}}

    def evaluate(self, comparison, trials):
        # Insertion ordinal, not wall-clock timestamps or caller list order,
        # determines whether the recorded sequence followed its frozen plan.
        trials = sorted(trials, key=lambda trial: (trial["ordinal"], trial["id"]))
        by_origin = {}
        sources = comparison["plan"]["source_ids"]
        quota = comparison["trials_per_source"]
        for origin in ORIGINS:
            selected = [trial for trial in trials if trial["data_origin"] == origin]
            layouts = {layout: self._stats([t for t in selected if t["layout"] == layout],
                                           len(sources) * quota) for layout in LAYOUTS}
            cells = [{"source_id": source, **{layout: self._stats([t for t in selected
                      if t["source_id"] == source and t["layout"] == layout], quota)
                      for layout in LAYOUTS}} for source in sources]
            counts = [cell[layout]["released"] for cell in cells for layout in LAYOUTS]
            a, b = (layouts[layout]["entry_rate_bounds"] for layout in LAYOUTS)
            observed_a, observed_b = (layouts[layout]["observed_entry_rate_bounds"] for layout in LAYOUTS)
            order_followed = all(trial["layout"] == slot["layout"] and trial["source_id"] == slot["source_id"]
                                 for trial, slot in zip(selected, comparison["plan"]["sequence"]))
            by_origin[origin] = {"data_origin": origin, "layouts": layouts, "by_source": cells,
                "plan": {"expected_total": comparison["plan"]["expected_total"],
                    "recorded_total": len(selected), "complete": all(n == quota for n in counts),
                    "balanced": bool(selected) and len(set(counts)) == 1,
                    "order_followed": order_followed},
                "effect_bounds": {"lower": a["lower"] - b["upper"],
                    "upper": a["upper"] - b["lower"],
                    "kind": "baseline_minus_intervention_planned_entry_fraction"},
                "observed_effect_bounds": {"lower": observed_a["lower"] - observed_b["upper"],
                    "upper": observed_a["upper"] - observed_b["lower"],
                    "kind": "actual_releases_including_unresolved_not_causal_estimate"},
                "supports_causal_claim": False,
                "physical_outcomes_automatically_verified": False}
        snapshot_hash = digest({"comparison": comparison,
                                "trials": sorted(trials, key=lambda trial: trial["id"])})
        return {"id": "prevention-evaluation-" + snapshot_hash[:20], "snapshot_hash": snapshot_hash,
            "comparison_id": comparison["id"], "trial_ids": sorted(t["id"] for t in trials),
            "physical_validation": False, "by_origin": by_origin,
            "limitations": ["Synthetic demonstrations and operator-reported physical outcomes are separate; neither is automatically camera-verified.",
                "Missing planned trials and unresolved outcomes remain unknown in the planned rate bounds; released counts contain only logged trials.",
                "Incomplete, unbalanced or reordered plans cannot support a causal effect claim. Even a completed pilot is not a randomized reef experiment.",
                "Surface-zone entry is a tabletop proxy, not coral injury, marine survival or carbon savings."]}

    async def load_demo(self):
        """An explicit synthetic software rehearsal, not a physical experiment."""
        from apps.transport.reeftrace_transport import fit_flow

        async with self.demo_lock:
            for row in self.store.list(COMPARISON_KIND, 100):
                if row.get("demo_fixture_key") == "prevention-demo-v1":
                    try:
                        self.assert_active(row)
                        return self.comparison_detail(row["id"])
                    except (KeyError, ValueError):
                        pass
            bounds = {"x_min_cm": 0, "x_max_cm": 40, "y_min_cm": 0, "y_max_cm": 30}
            samples = [{"x_cm": x, "y_cm": y, "vx_cm_s": 2, "vy_cm_s": 0}
                       for x in (0, 20, 40) for y in (0, 15, 30)]
            flow = fit_flow(samples, bounds, coverage_radius_cm=50, data_origin="SYNTHETIC")
            sources = [{"id": name, "polygon_cm": [[x, 12], [x + 2, 12], [x + 2, 16], [x, 16]],
                        "prior": 1 / 3} for name, x in zip(("A", "B", "C"), (1, 5, 9), strict=True)]
            for layout, x in (("baseline", 36), ("intervention", 24)):
                profile_id = f"prevention-demo-{layout}-v1"
                try:
                    self.store.get("profile", profile_id)
                except KeyError:
                    self.runtime.register_profile({"id": profile_id, "valid": True,
                        "data_origin": "SYNTHETIC", "calibration_id": "prevention-synthetic-map-v1",
                        "bounds": bounds, "sources": sources, "token_class": "synthetic-red-token",
                        "flow": flow, "traps": [{"id": "mesh-pocket", "polygon_cm": [
                            [x, 10], [x + 2, 10], [x + 2, 20], [x, 20]],
                            "retention": "absorbing", "validated": True}],
                        "transport": {"particles_per_source": 80, "dt_s": 0.2, "max_age_s": 20,
                            "diffusivity_cm2_s": 0.02, "age_prior": {"min_s": 0, "max_s": 15, "count": 16}}})
            case = self.runtime.add_case(CaseInput(profile_id="prevention-demo-baseline-v1",
                calibration_id="prevention-synthetic-map-v1", token_class="synthetic-red-token",
                mode="SYNTHETIC", points=[{"t_s": t, "x_cm": 16 + 2 * t, "y_cm": 14}
                                         for t in (0, 1, 2)]))
            await self.runtime.compute(case["id"])
            detail = await self.create_comparison(ComparisonInput(case_id=case["id"],
                baseline_profile_id="prevention-demo-baseline-v1",
                intervention_profile_id="prevention-demo-intervention-v1",
                protected_zone_cm=[[30, 10], [34, 10], [34, 20], [30, 20]],
                name="Synthetic interception rehearsal"), demo_fixture_key="prevention-demo-v1")
            for index, slot in enumerate(detail["comparison"]["plan"]["sequence"]):
                captured = slot["layout"] == "intervention" and slot["repeat"] < 5
                unresolved = slot["repeat"] == 5
                outcome = "unresolved" if unresolved else "intercepted_before_entry" if captured else "zone_entry"
                self.add_trial(detail["comparison"]["id"], TrialInput(
                    trial_key=f"demo-{index + 1}", layout=slot["layout"], source_id=slot["source_id"],
                    data_origin="SYNTHETIC_DEMO", outcome=outcome,
                    entry_time_s=15 if outcome == "zone_entry" else None,
                    interception_time_s=10 if captured else None,
                    token_accounted=not unresolved, physical_confirmed=False,
                    horizon_completed=not unresolved,
                    note="Hand-authored synthetic software demonstration; not a physical trial or a model measurement."))
            return self.comparison_detail(detail["comparison"]["id"])
