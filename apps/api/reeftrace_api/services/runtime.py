"""Local orchestration. Physics runs without a model key; agent transport is explicit."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import math
import os
import time

from apps.vision.reeftrace_vision.capture import Camera
from apps.vision.reeftrace_vision.tracking import SingleTokenTracker, detect_red, in_polygon

from .investigation import CaseBackend, conditional_report
from .store import Store, uid


class Runtime:
    def __init__(self, settings):
        self.settings = settings
        self.store = Store(settings.data_dir, database_url=settings.database_url)
        self.camera = Camera(settings.camera_stale_s)
        self.case_locks = {}
        self.record_lock = asyncio.Lock()
        self.demo_lock = asyncio.Lock()
        self.model_budget = asyncio.Semaphore(1)
        self.voice_budget = asyncio.Semaphore(1)

    def grok_settings(self):
        from adapters.grok import GrokVoiceSettings
        return GrokVoiceSettings(
            enabled=os.getenv("GROK_VOICE_ENABLED", "false").lower() == "true",
            api_key=os.getenv("XAI_API_KEY", ""),
        )

    def briefing(self, case_id):
        from adapters.grok import build_briefing
        case = self.store.case(case_id)
        if case["state"] in {"STOPPED", "RECOVERING"}:
            raise ValueError("Case is stopped or recovering; briefing unavailable")
        if not case.get("evidence_id"):
            raise ValueError("Compute source support before preparing a briefing")
        report = self.store.get("estimate", case["evidence_id"])
        if report.get("case_id") != case_id or report.get("id") != case["evidence_id"]:
            raise ValueError("Saved evidence does not match this case")
        return build_briefing(report)

    async def speak_briefing(self, case_id):
        from adapters.grok import synthesize_briefing
        lock = self.case_locks.setdefault(case_id, asyncio.Lock())
        async with lock:
            case = self.store.case(case_id)
            briefing = self.briefing(case_id)
            async with self.voice_budget:
                result = await synthesize_briefing(briefing, self.grok_settings())
            current = self.store.case(case_id)
            if (current["revision"] != case["revision"]
                    or current.get("evidence_id") != briefing["source_evidence_id"]
                    or current["state"] in {"STOPPED", "RECOVERING"}):
                raise ValueError("Case changed while generating speech; discard old briefing")
            if result.get("ok"):
                receipt = {key: value for key, value in result.items() if key != "audio_bytes"}
                receipt.update(case_id=case_id, evidence_id=briefing["source_evidence_id"],
                               created_at=time.time())
                self.store.put_case_result("voice_receipt", receipt, case_id, case["revision"])
                result["evidence_id"] = briefing["source_evidence_id"]
            return result

    def gemini_settings(self):
        from adapters.gemini.agent import GeminiSettings
        return GeminiSettings(
            enabled=(os.getenv("REEFTRACE_AI_PROVIDER", "gemini") == "gemini"
                     and os.getenv("GEMINI_ENABLED", "true").lower() == "true"),
            api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", ""),
            model=os.getenv("GEMINI_MODEL", ""))

    def photon_settings(self):
        from adapters.photon.transport import PhotonSettings, RouteConfig
        enabled = os.getenv("PHOTON_ENABLED", "false").lower() == "true"
        routes = (tuple(RouteConfig(**r) for r in json.loads(os.getenv("PHOTON_ROUTES_JSON", "[]")))
                  if enabled else ())
        return PhotonSettings(enabled=enabled,
                              api_key=os.getenv("PHOTON_API_KEY", ""),
                              project_id=os.getenv("PHOTON_PROJECT_ID", ""), routes=routes)

    def register_profile(self, profile):
        return self._register_profile(profile)

    def _register_profile(self, profile):
        if profile.get("data_origin") not in {"SYNTHETIC", "MEASURED_TANK"}:
            raise ValueError("Profile data_origin must be SYNTHETIC or MEASURED_TANK")
        if not profile.get("calibration_id") or not profile.get("bounds") or not profile.get("sources"):
            raise ValueError("Profile needs calibration_id, measured bounds and candidate sources")
        t = profile.get("transport", {})
        if not 20 <= t.get("particles_per_source", 500) <= 2000:
            raise ValueError("Use 20-2000 particles per source")
        if not 0.01 <= t.get("dt_s", 0.1) <= 1 or not 1 <= t.get("max_age_s", 60) <= 120:
            raise ValueError("Simulation must use 0.01-1 s steps and a 1-120 s horizon")
        if t.get("max_age_s", 60) / t.get("dt_s", 0.1) > 3000:
            raise ValueError("Simulation step budget exceeded")
        if not 2 <= len(profile["sources"]) <= 5:
            raise ValueError("Use 2-5 candidate sources")
        if profile["data_origin"] == "MEASURED_TANK":
            flow_id = (profile.get("flow") or {}).get("id")
            if not flow_id:
                raise ValueError("Measured profiles require the immutable flow object from /flow/fit-recordings")
            frozen_flow = self.store.get("flow", flow_id)
            if frozen_flow != profile["flow"]:
                raise ValueError("Flow was changed after fitting; use the exact immutable flow object")
            if frozen_flow["provenance"]["calibration_id"] != profile["calibration_id"]:
                raise ValueError("Recorded flow and profile use different calibrations")
            calibration = self.store.get("calibration", profile["calibration_id"])
            if not calibration.get("approved") or not profile.get("observation_polygon_cm"):
                raise ValueError("Measured profiles require a validated water-plane map and permitted observation polygon")
            if not profile.get("flow"):
                raise ValueError("Fit a measured transport field before registering the profile")
            diagnostics = profile["flow"].get("diagnostics", {})
            if (diagnostics.get("validation_rmse_cm_s") is None
                    or (diagnostics.get("validation_coverage_fraction") or 0) < 0.9):
                raise ValueError("A measured flow profile requires independent validation samples with at least 90% supported coverage")
            maximum = profile.get("max_validation_rmse_cm_s")
            if (maximum is None or not math.isfinite(maximum) or maximum <= 0
                    or diagnostics["validation_rmse_cm_s"] > maximum):
                raise ValueError("Declare a positive development-frozen max_validation_rmse_cm_s and pass it on held-out drift")
            tolerance = profile.get("revalidation_max_rmse_cm_s")
            if tolerance is None or not math.isfinite(tolerance) or tolerance <= 0:
                raise ValueError("Freeze a positive revalidation_max_rmse_cm_s before registering a measured profile")
        profile = copy.deepcopy(profile)
        if "sensitivity_variants" not in profile:
            diffusion = profile.get("transport", {}).get("diffusivity_cm2_s", 0.05)
            profile["sensitivity_variants"] = [
                {"id": "dispersion_x0.5", "transport": {"diffusivity_cm2_s": diffusion * 0.5}},
                {"id": "dispersion_x2.0", "transport": {"diffusivity_cm2_s": diffusion * 2.0}},
            ]
        return self.store.put("profile", profile, profile.get("id"))

    def fit_recorded_flow(self, body):
        from apps.transport.reeftrace_transport import fit_flow
        from apps.vision.reeftrace_vision.tracking import flow_samples
        allowed = {"training_recording_ids", "validation_recording_ids", "bounds",
                   "cell_size_cm", "coverage_radius_cm"}
        if set(body) - allowed:
            raise ValueError("Unsupported recorded-flow fields")
        training_ids, validation_ids = body.get("training_recording_ids", []), body.get("validation_recording_ids", [])
        if not all(isinstance(ids, list) and 1 <= len(ids) <= 100 for ids in (training_ids, validation_ids)):
            raise ValueError("Supply 1-100 complete recordings per split")
        if set(training_ids) & set(validation_ids):
            raise ValueError("Training and validation recording IDs must be disjoint")
        training = [self.store.get("recording", rid) for rid in training_ids]
        validation = [self.store.get("recording", rid) for rid in validation_ids]
        calibration_ids = {r["calibration_id"] for r in training + validation}
        sessions = {r["camera_session_id"] for r in training + validation}
        if len(calibration_ids) != 1 or len(sessions) != 1:
            raise ValueError("Flow recordings must share one frozen calibration and camera session")
        frames_a = {f for r in training for f in r["evidence_frame_ids"]}
        frames_b = {f for r in validation for f in r["evidence_frame_ids"]}
        if not frames_a or not frames_b or frames_a & frames_b:
            raise ValueError("Flow train/validation frames must be present and disjoint")
        samples = [s for r in training for s in flow_samples(r["points"])]
        holdout = [s for r in validation for s in flow_samples(r["points"])]
        if not samples or not holdout or len(samples) + len(holdout) > 10000:
            raise ValueError("Need measured supported drift samples in both splits within 10000 sample budget")
        flow = fit_flow(samples, body["bounds"], validation_samples=holdout,
            cell_size_cm=body.get("cell_size_cm", 1),
            coverage_radius_cm=body.get("coverage_radius_cm", 3), data_origin="MEASURED_TANK")
        flow["provenance"] = {"calibration_id": next(iter(calibration_ids)),
            "camera_session_id": next(iter(sessions)), "training_recording_ids": training_ids,
            "validation_recording_ids": validation_ids, "frame_splits_disjoint": True}
        return self.store.put("flow", flow)

    def add_case(self, request, *, recording_id=None, demo_fixture_key=None):
        observation = request.model_dump()
        if demo_fixture_key is not None:
            observation["demo_fixture_key"] = demo_fixture_key
        profile = self.store.get("profile", observation["profile_id"])
        if request.mode == "LIVE" and profile["data_origin"] != "MEASURED_TANK":
            raise ValueError("Synthetic profiles cannot be used for LIVE cases")
        if request.mode == "LIVE" and not recording_id:
            raise ValueError("Create LIVE cases from an immutable recording; direct coordinates are replay-only")
        if recording_id:
            observation["recording_id"] = recording_id
        if request.mode == "SYNTHETIC" and profile["data_origin"] != "SYNTHETIC":
            raise ValueError("SYNTHETIC cases require synthetic profiles")
        if request.mode == "LIVE" and request.calibration_id != profile["calibration_id"]:
            raise ValueError("Observation calibration does not match profile")
        if profile.get("observation_polygon_cm"):
            if observation.get("endpoint") and not in_polygon(
                    (observation["endpoint"]["x_cm"], observation["endpoint"]["y_cm"]),
                    profile["observation_polygon_cm"]):
                raise ValueError("Retained endpoint is outside the permitted observation region")
            observation["points"] = [p for p in observation["points"] if in_polygon(
                (p["x_cm"], p["y_cm"]), profile["observation_polygon_cm"])]
        if request.mode == "LIVE":
            self.validate_live(observation, profile)
        return self.store.add_case(observation)

    async def load_demo(self, folder):
        """Load each development fixture once; stopped cases stay stopped.

        A new case replaces a stopped fixture on an explicit demo reload. The
        old case and all its reports remain available for audit.
        """
        from ..schemas.contracts import CaseInput

        async with self.demo_lock:
            profile_file = folder / "synthetic_profile.json"
            case_file = folder / "synthetic_observations.json"
            if not profile_file.exists() or not case_file.exists():
                raise ValueError("Run python scripts/generate_demo.py first")
            profile = json.loads(profile_file.read_text())
            try:
                frozen = self.store.get("profile", profile["id"])
                if any(frozen.get(key) != value for key, value in profile.items()):
                    raise ValueError("Demo profile changed; use a fresh data directory for new fixtures")
            except KeyError:
                self.register_profile(profile)
            loaded = []
            reused = 0
            for item in json.loads(case_file.read_text()):
                clean = {key: value for key, value in item.items() if key in CaseInput.model_fields}
                clean.update(profile_id=profile["id"], mode="SYNTHETIC")
                fixture_key = hashlib.sha256(json.dumps(
                    {"profile": profile, "observation": clean}, sort_keys=True,
                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()
                case = self.store.reusable_demo_case(fixture_key)
                if case is None:
                    case = self.add_case(CaseInput(**clean), demo_fixture_key=fixture_key)
                else:
                    reused += 1
                report = (self.store.get("estimate", case["evidence_id"])
                          if case.get("evidence_id") else await self.compute(case["id"]))
                loaded.append({"case": self.store.case(case["id"]), "evidence": report})
            return {"mode": "SYNTHETIC", "physical_validation": False,
                    "reused_cases": reused, "cases": loaded}

    def validate_live(self, case, profile, *, require_target_fresh=False):
        status = self.camera.status()
        if not status["fresh"] or case.get("camera_session_id") != status["session_id"]:
            raise ValueError("Current USB camera session is unavailable or stale")
        calibration = self.store.get("calibration", profile["calibration_id"])
        if calibration.get("camera_session_id") != status["session_id"]:
            raise ValueError("Validate mapping for this camera session before LIVE use")
        changes = self.store.list("rig_change", 1)
        checks = self.store.list("rig_check", 1)
        if changes and (not checks or checks[0]["checked_at"] <= changes[0]["changed_at"]
                        or checks[0]["profile_id"] != profile["id"]):
            raise ValueError("Rig changed/recovery disturbed flow; record drift and revalidate the frozen profile")
        if not case.get("evidence_frame_ids"):
            raise ValueError("LIVE cases need persisted camera frame evidence")
        newest_frame = None
        for fid in case["evidence_frame_ids"]:
            frame = self.store.get("frame", fid)
            if frame["camera_session_id"] != status["session_id"] or frame["profile_id"] != profile["id"]:
                raise ValueError("Frame belongs to another profile/camera session")
            if changes and frame.get("saved_at", 0) <= changes[0]["changed_at"]:
                raise ValueError("Case observation predates the latest rig disturbance; make a new source observation")
            newest_frame = max(newest_frame or -float("inf"), frame["received_mono_s"])
        if require_target_fresh and (newest_frame is None or
                time.monotonic() - newest_frame > self.settings.target_fresh_s):
            raise ValueError("Target observation is stale; a fresh camera preview does not refresh this case")

    def revalidate_rig(self, profile_id, recording_id, checks):
        import numpy as np

        from apps.transport.reeftrace_transport import FlowField
        from apps.vision.reeftrace_vision.tracking import flow_samples
        required = {"waterline_unchanged", "pump_setting_unchanged", "hose_and_pocket_unchanged",
                    "camera_and_light_unchanged"}
        if set(checks) != required or any(v is not True for v in checks.values()):
            raise ValueError("Confirm all four physical fixture checks")
        profile = self.store.get("profile", profile_id)
        recording = self.store.get("recording", recording_id)
        if (recording.get("calibration_id") != profile["calibration_id"]
                or recording["camera_session_id"] != self.camera.session_id):
            raise ValueError("Revalidation needs a recording from this calibration/camera session")
        changed = self.store.list("rig_change", 1)
        if changed and recording.get("recorded_at", 0) <= changed[0]["changed_at"]:
            raise ValueError("Record new drift after the most recent rig disturbance")
        samples = flow_samples(recording["points"])
        if len(samples) < 3:
            raise ValueError("Need at least three measured drift samples for revalidation")
        xy = np.array([[s["x_cm"], s["y_cm"]] for s in samples])
        velocity = np.array([[s["vx_cm_s"], s["vy_cm_s"]] for s in samples])
        predicted, supported = FlowField(profile["flow"]).evaluate(xy)
        rmse = float(np.sqrt(np.mean(np.sum((predicted - velocity) ** 2, axis=1))))
        tolerance = profile.get("revalidation_max_rmse_cm_s")
        if tolerance is None or not np.isfinite(tolerance) or tolerance <= 0:
            raise ValueError("Freeze revalidation_max_rmse_cm_s on development runs before using the profile")
        if not supported.all() or rmse > tolerance or not self.camera.status()["fresh"]:
            raise ValueError("Drift revalidation failed; recalibrate rather than enlarge the tolerance")
        return self.store.put("rig_check", {"profile_id": profile_id,
            "recording_id": recording_id, "checked_at": time.time(), "rmse_cm_s": rmse,
            "checks": checks})

    async def compute(self, case_id):
        from apps.estimation.reeftrace_estimation import estimate
        lock = self.case_locks.setdefault(case_id, asyncio.Lock())
        async with lock:
            case = self.store.case(case_id)
            if case["state"] in {"STOPPED", "RECOVERING"}:
                raise ValueError("Case is stopped or recovering")
            profile = self.store.get("profile", case["profile_id"])
            if case["mode"] == "LIVE":
                self.validate_live(case, profile)
            async with self.model_budget:
                result = await asyncio.to_thread(estimate, profile, {**case, "case_id": case["id"]})
            evidence = self.store.put_case_result("estimate", {**result, "case_id": case_id,
                "mode": case["mode"], "profile_id": profile["id"],
                "evidence_frame_ids": case["evidence_frame_ids"]}, case_id, case["revision"],
                changes={"state": "INVESTIGATE"})
            return evidence

    async def sensitivity(self, case_id):
        lock = self.case_locks.setdefault(case_id, asyncio.Lock())
        async with lock:
            return await self._sensitivity(case_id, self.store.case(case_id)["revision"])

    async def _sensitivity(self, case_id, expected_revision):
        """Caller owns the case lock; the agent may already hold that lock."""
        from apps.estimation.reeftrace_estimation import estimate
        case = self.store.case(case_id)
        if case["state"] in {"STOPPED", "RECOVERING"} or case["revision"] != expected_revision:
            raise ValueError("Case changed, stopped or recovering; refresh the observation")
        if not case.get("evidence_id"):
            raise ValueError("Compute baseline estimate first")
        profile = self.store.get("profile", case["profile_id"])
        if case["mode"] == "LIVE":
            self.validate_live(case, profile)
        async with self.model_budget:
            result = await asyncio.to_thread(estimate, profile, {**case, "case_id": case_id})
        analysis = {"case_id": case_id, "parent_estimate_id": case["evidence_id"],
                    "preset_id": "predeclared-transport-envelope-v1",
                    "variants": result.get("sensitivity_results", []), "combined_report": result,
                    "scope": "All frozen variants; combined ranking already incorporates assumption-sensitivity gates"}
        return self.store.put_case_result("analysis", analysis, case_id, expected_revision)

    def propose(self, case_id, evidence_id, *, operator):
        case = self.store.case(case_id)
        if not operator:
            raise ValueError("Operator permission required")
        profile = self.store.get("profile", case["profile_id"])
        self.validate_live(case, profile, require_target_fresh=True)
        evidence = self.store.get("estimate", evidence_id)
        if evidence.get("status") == "invalid":
            raise ValueError("Invalid calibration/evidence blocks recovery proposal")
        return self.store.propose(case_id, evidence_id, allowed=case["mode"] == "LIVE")

    def approve(self, action_id):
        action = self.store.action(action_id)
        case = self.store.case(action["case_id"])
        self.validate_live(case, self.store.get("profile", case["profile_id"]), require_target_fresh=True)
        return self.store.transition_action(action_id, "awaiting_human")

    async def investigate(self, case_id, question, *, operator=True):
        from adapters.gemini.agent import investigate
        lock = self.case_locks.setdefault(case_id, asyncio.Lock())
        async with lock:
            case = self.store.case(case_id)
            if case["state"] in {"STOPPED", "RECOVERING"}:
                return {"action": "STOP", "explanation": "Case is stopped or recovering; no model call was made",
                        "evidence_ids": [], "trace": [], "source_report": None,
                        "live_model_response": False}
            report = self.store.get("estimate", case["evidence_id"]) if case.get("evidence_id") else None
            backend = CaseBackend(self, case_id, operator=operator)
            result = None
            try:
                result = await investigate(question, backend,
                    {"case_id": case_id, "role": "operator" if operator else "observer"},
                    self.gemini_settings())
                # STOP bypasses this lock and invalidates a slow agent's result.
                if self.store.case(case_id)["revision"] != case["revision"]:
                    result = {"action": "STOP", "explanation": "Case changed while investigating",
                              "evidence_ids": [], "trace": [], "provider": "gemini",
                              "live_model_response": False}
                    report = None
            finally:
                keep = (result.get("proposal_id") if result and
                        result.get("action") == "REQUEST_APPROVAL" else None)
                for proposal_id in backend.created_proposal_ids:
                    if proposal_id != keep:
                        try:
                            self.store.transition_action(proposal_id, "cancelled")
                        except ValueError:
                            # An operator may already have recorded an immutable
                            # manual outcome through another UI/authorized route.
                            # Preserve that fact without turning cleanup into 500.
                            if self.store.action(proposal_id)["state"] not in {
                                    "manual_recovered", "failed", "uncertain"}:
                                raise
            result["source_report"] = conditional_report(report) if report else None
            self.store.put("investigation", {"case_id": case_id, **result})
            return result

    async def photon_handler(self, message):
        text = message.text.strip()
        # Strict command grammar bypasses LLM. Space/handle authorization is fixed
        # by the route normalizer before it reaches this method.
        parts = text.split()
        if parts and parts[0] in {"STOP", "CANCEL", "APPROVE"} and len(parts) != 2:
            return "Command format: STOP case-id, CANCEL action-id, or APPROVE action-id. No model was called."
        if len(parts) == 2 and parts[0] in {"STOP", "CANCEL", "APPROVE"}:
            command, target = parts
            if command == "STOP":
                case = self.store.case(target)
            else:
                action = self.store.action(target); case = self.store.case(action["case_id"])
            if case["id"] not in message.allowed_cases or message.role != "operator":
                return "Command denied: this conversation has no operator authority for that case."
            if command == "STOP":
                self.store.stop_case(case["id"])
                return "Software tasks stopped. Pump power is unchanged; use its original plug for physical power-off."
            if command == "CANCEL":
                self.store.transition_action(target, "cancelled")
                return "Manual recovery task cancelled."
            self.approve(target)
            return "Manual recovery task approved. A person must recover and record the outcome. No motor was commanded."
        matches = [cid for cid in message.allowed_cases if cid in text]
        if not matches and len(message.allowed_cases) == 1:
            matches = list(message.allowed_cases)
        if len(matches) != 1:
            return "Please include exactly one authorized case ID in your question."
        result = await self.investigate(matches[0], text, operator=message.role == "operator")
        report = result.get("source_report")
        numerical = ""
        if report:
            numerical = "\nSaved source evidence: " + json.dumps(
                {k: report[k] for k in ("id", "status", "relative_support", "reason_codes") if k in report})
        return (result.get("explanation", "Investigation unavailable") + numerical)[:4000]

    async def record(self, profile_id, duration_s, calibration_id=None, *, active_case=None):
        if self.record_lock.locked():
            raise ValueError("A recording is already active")
        async with self.record_lock:
            if profile_id:
                profile = self.store.get("profile", profile_id)
                if profile["data_origin"] != "MEASURED_TANK":
                    raise ValueError("LIVE recording cannot use a synthetic profile")
                calibration_id = profile["calibration_id"]
            if not calibration_id:
                raise ValueError("Provide profile_id, or calibration_id for initial flow recordings")
            calibration = self.store.get("calibration", calibration_id)
            if not calibration.get("approved"):
                raise ValueError("Recording requires an approved water-plane map")
            if calibration.get("camera_session_id") != self.camera.session_id:
                raise ValueError("Camera session does not match calibration")
            session_id = self.camera.session_id
            tracker = SingleTokenTracker()
            run_id, start, previous = uid("recording"), time.monotonic(), None
            folder = self.settings.data_dir / "frames" / run_id
            folder.mkdir(parents=True)
            observations, frame_ids = [], []
            while time.monotonic() - start < duration_s:
                if active_case is not None:
                    case = self.store.case(active_case["id"])
                    if (case["revision"] != active_case["revision"]
                            or case["state"] in {"STOPPED", "RECOVERING"}):
                        raise ValueError("Case changed or stopped during observation; recording discarded")
                image, frame = self.camera.image()
                if frame["session_id"] != session_id or self.camera.session_id != session_id:
                    raise ValueError("Camera restarted during recording; partial frames cannot form a valid recording")
                if frame["sequence"] != previous:
                    if [frame["width"], frame["height"]] != calibration.get("image_size_px"):
                        raise ValueError("Camera dimensions changed after calibration")
                    previous = frame["sequence"]
                    fid = uid("frame")
                    path = folder / (fid + ".jpg")
                    path.write_bytes(frame["jpeg"])
                    if frame["received_mono_s"] < start:
                        await asyncio.sleep(1 / self.settings.camera_sample_hz)
                        continue
                    point = tracker.update(detect_red(image), frame["received_mono_s"] - start, calibration)
                    self.store.put("frame", {"profile_id": profile_id,
                        "camera_session_id": frame["session_id"], "path": str(path),
                        "sequence": frame["sequence"], "received_utc": frame["received_utc"],
                        "saved_at": time.time(),
                        "received_mono_s": frame["received_mono_s"]}, fid)
                    frame_ids.append(fid)
                    observations.append({**point, "frame_id": fid})
                await asyncio.sleep(1 / self.settings.camera_sample_hz)
            if self.camera.session_id != session_id:
                raise ValueError("Camera session changed before recording completion")
            if active_case is not None:
                case = self.store.case(active_case["id"])
                if case["revision"] != active_case["revision"]:
                    raise ValueError("Case changed or stopped before recording completion")
            return self.store.put("recording", {"id": run_id, "profile_id": profile_id,
                "camera_session_id": session_id, "points": observations,
                "calibration_id": calibration_id,
                "recorded_at": time.time(),
                "evidence_frame_ids": frame_ids, "data_origin": "MEASURED_TANK",
                "timestamp_kind": "host_receipt_not_exposure"}, run_id)
