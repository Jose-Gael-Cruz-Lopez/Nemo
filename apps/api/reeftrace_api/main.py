"""Local control plane: one API worker owns the USB camera."""
from __future__ import annotations

import asyncio
import hmac
import time
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse

from apps.vision.reeftrace_vision.calibration import fit_homography
from apps.vision.reeftrace_vision.tracking import flow_samples

from .api.v1.endpoints.current_forecast import create_current_forecast_router
from .api.v1.endpoints.field_sessions import create_field_sessions_router
from .api.v1.endpoints.fresh_physics import create_fresh_physics_router
from .api.v1.endpoints.health import router as health_router
from .api.v1.endpoints.matched_current import create_matched_current_router
from .api.v1.endpoints.method_validation import create_method_validation_router
from .api.v1.endpoints.ocean_prevention import create_ocean_prevention_router
from .api.v1.endpoints.origin_residual import create_origin_residual_router
from .core.settings import Settings
from .schemas.contracts import (
    CalibrationInput,
    CameraInput,
    CaseInput,
    OutcomeInput,
    ProposalInput,
    Question,
    RecordingCaseInput,
    RecordInput,
    SensitivityInput,
)
from .schemas.prevention import ComparisonInput, TrialInput
from .schemas.validation_reports import PreventionQuestion, ValidationReportInput
from .services.camera_stream import MJPEG_BOUNDARY, iter_camera_mjpeg
from .services.evidence_export import export_comparison
from .services.runtime import Runtime
from .services.validation_reports import (
    accept_validation_report,
    get_validation_report,
    list_validation_reports,
    template_validation_report,
)

ROOT = Path(__file__).resolve().parents[3]


def create_app(settings: Settings | None = None):
    load_dotenv(override=False)
    settings = settings or Settings()
    runtime = Runtime(settings)

    @asynccontextmanager
    async def lifespan(app):
        from adapters.photon.worker import PhotonWorker
        stop = asyncio.Event()
        worker = None
        ps = runtime.photon_settings()
        if ps.readiness()["ready"]:
            runtime.store.bind_photon_project(ps.project_id)
            runtime.photon_worker = PhotonWorker(ps, runtime.store, runtime.photon_handler)
            worker = asyncio.create_task(runtime.photon_worker.run(stop))
            runtime.photon_task = worker
        try:
            yield
        finally:
            runtime.camera.stop()
            stop.set()
            if worker:
                try:
                    await asyncio.wait_for(worker, timeout=3)
                except TimeoutError:
                    worker.cancel()
                    await asyncio.gather(worker, return_exceptions=True)

    app = FastAPI(title="ReefTrace", version="0.2.0", lifespan=lifespan,
                  description="USB observations → measured forward transport → conditional source evidence")
    app.state.runtime = runtime
    # Browser private-network preflights are necessary for the local dashboard.
    # A configured wildcard or external origin must never gain this permission.
    dashboard_origins = [origin for origin in settings.allowed_origins if origin in {
        "http://localhost:3000", "http://127.0.0.1:3000"}]
    app.add_middleware(CORSMiddleware, allow_origins=dashboard_origins,
                       allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"],
                       allow_private_network=True,
                       expose_headers=["X-Evidence-Id", "X-Script-Hash"])
    app.include_router(health_router, prefix="/api/v1")

    @app.exception_handler(KeyError)
    async def missing(request, error):
        return JSONResponse(status_code=404, content={"detail": "Record not found"})

    @app.exception_handler(ValueError)
    async def invalid(request, error):
        return JSONResponse(status_code=409, content={"detail": str(error)[:300]})

    def operator(request: Request):
        if not settings.local_token:
            raise HTTPException(503, "Set REEFTRACE_LOCAL_TOKEN before changing local state",
                                headers={"Cache-Control": "no-store"})
        auth = request.headers.get("Authorization", "")
        if not hmac.compare_digest(auth.encode("utf-8"),
                                   ("Bearer " + settings.local_token).encode("utf-8")):
            raise HTTPException(401, "Operator token required",
                                headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/operator/session", dependencies=[Depends(operator)])
    def operator_session(response: Response):
        """Verify local operator access without changing state or contacting a provider."""
        response.headers["Cache-Control"] = "no-store"
        return {"authenticated": True, "scope": "local_operator"}

    app.include_router(create_method_validation_router(), prefix="/api/v1")
    app.include_router(create_field_sessions_router(runtime, operator), prefix="/api/v1")
    app.include_router(create_fresh_physics_router(runtime, operator), prefix="/api/v1")
    app.include_router(create_matched_current_router(runtime, operator), prefix="/api/v1")
    app.include_router(create_current_forecast_router(runtime, operator), prefix="/api/v1")
    app.include_router(create_ocean_prevention_router(runtime, operator), prefix="/api/v1")
    app.include_router(create_origin_residual_router(runtime, operator), prefix="/api/v1")

    @app.get("/")
    def root():
        return {"name": "ReefTrace API", "docs": "/docs"}

    @app.get("/api/v1/status")
    def status():
        return {"camera": runtime.camera.status(), "chalk": runtime.chalk_settings().readiness(),
                "photon": runtime.photon_status(),
                "grok": runtime.grok_settings().readiness(), "collection_mode": "manual_net",
                "hardware_actuation": False, "operator_configured": bool(settings.local_token)}

    @app.get("/api/v1/research/satellite-context")
    def satellite_context():
        from apps.ocean.reeftrace_ocean.satellite import load_satellite_context
        try:
            return load_satellite_context()
        except (FileNotFoundError, PermissionError):
            raise HTTPException(503, "The pinned satellite dataset is unavailable locally") from None

    @app.get("/api/v1/research/training-diagnostic")
    def training_diagnostic():
        from apps.ocean.reeftrace_ocean.diagnostics import run_training_diagnostic
        try:
            return run_training_diagnostic()
        except (FileNotFoundError, PermissionError):
            raise HTTPException(503, "The pinned training dataset is unavailable locally") from None

    @app.get("/api/v1/research/motion-ablation")
    def motion_ablation():
        from apps.ocean.reeftrace_ocean.ablation import run_motion_ablation
        try:
            return run_motion_ablation()
        except (FileNotFoundError, PermissionError):
            raise HTTPException(503, "The pinned motion dataset is unavailable locally") from None

    @app.get("/api/v1/research/multi-drifter")
    def multi_drifter():
        from apps.ocean.reeftrace_ocean.multidrifter import run_multidrifter_study
        try:
            return run_multidrifter_study()
        except (FileNotFoundError, PermissionError):
            raise HTTPException(503, "The pinned multi-drifter study is unavailable locally") from None

    @app.get("/api/v1/research/dataset-readiness")
    def dataset_readiness():
        from apps.ocean.reeftrace_ocean.dataset_readiness import load_dataset_readiness
        try:
            return load_dataset_readiness()
        except (FileNotFoundError, PermissionError):
            raise HTTPException(503, "The pinned acquisition receipts are unavailable locally") from None

    @app.get("/api/v1/research/lopo-diagnostic")
    def lopo_diagnostic():
        from apps.ocean.reeftrace_ocean.lopo import run_lopo_diagnostic
        try:
            return run_lopo_diagnostic()
        except (FileNotFoundError, PermissionError):
            raise HTTPException(503, "The pinned transfer diagnostic is unavailable locally") from None

    @app.get("/api/v1/research/kalman-diagnostic")
    def kalman_diagnostic(response: Response):
        """Replay a fixed, post-hoc model study without altering operational evidence."""
        from apps.ocean.reeftrace_ocean.kalman_diagnostic import run_kalman_diagnostic
        response.headers["Cache-Control"] = "no-store"
        try:
            return run_kalman_diagnostic()
        except (FileNotFoundError, PermissionError):
            raise HTTPException(503, "The pinned Kalman diagnostic is unavailable locally",
                                headers={"Cache-Control": "no-store"}) from None
        except (ValueError, TypeError):
            raise HTTPException(409, "The fixed Kalman study failed its integrity or numerical checks",
                                headers={"Cache-Control": "no-store"}) from None

    @app.get("/api/v1/research/vector-diagnostic")
    def vector_diagnostic(response: Response):
        """Read-only motion comparison; never acquires evidence or contacts a provider."""
        from apps.ocean.reeftrace_ocean.vector_diagnostics import run_noaa_vector_diagnostic
        from apps.vision.reeftrace_vision.vector_diagnostic import run_synthetic_vector_diagnostic
        response.headers["Cache-Control"] = "no-store"
        try:
            return {
                "schema_version": 1, "kind": "MOTION_VECTOR_DIAGNOSTIC", "status": "COMPLETED",
                "noaa": run_noaa_vector_diagnostic(),
                "synthetic_tank": run_synthetic_vector_diagnostic(),
                "camera_started": False, "hardware_actuation": False,
                "physical_validation": False, "provider_calls": False, "store_written": False,
            }
        except (FileNotFoundError, PermissionError):
            raise HTTPException(503, "The pinned vector dataset is unavailable locally",
                                headers={"Cache-Control": "no-store"}) from None
        except ValueError as error:
            raise HTTPException(409, str(error)[:300],
                                headers={"Cache-Control": "no-store"}) from None

    @app.get("/api/v1/research/cohort-vectors")
    def cohort_vector_diagnostic(response: Response):
        from apps.ocean.reeftrace_ocean.vector_diagnostics import run_noaa_cohort_vector_diagnostic
        response.headers["Cache-Control"] = "no-store"
        try:
            return run_noaa_cohort_vector_diagnostic()
        except (FileNotFoundError, PermissionError):
            raise HTTPException(503, "The pinned cohort vector data is unavailable locally",
                                headers={"Cache-Control": "no-store"}) from None
        except ValueError as error:
            raise HTTPException(409, str(error)[:300],
                                headers={"Cache-Control": "no-store"}) from None

    @app.get("/api/v1/cases/{case_id}/briefing")
    def briefing(case_id: str):
        return runtime.briefing(case_id)

    @app.post("/api/v1/cases/{case_id}/briefing/audio", dependencies=[Depends(operator)])
    async def briefing_audio(case_id: str):
        result = await runtime.speak_briefing(case_id)
        if not result.get("ok"):
            return JSONResponse(status_code=503, content=result)
        return Response(result["audio_bytes"], media_type=result["content_type"],
                        headers={"Cache-Control": "no-store",
                                 "X-Evidence-Id": result["evidence_id"],
                                 "X-Script-Hash": result["script_hash"]})

    @app.get("/api/v1/profiles")
    def profiles():
        return runtime.store.list("profile")

    @app.get("/api/v1/prevention/comparisons")
    def prevention_comparisons():
        return runtime.prevention.list_comparisons()

    @app.post("/api/v1/prevention/comparisons", dependencies=[Depends(operator)])
    async def create_prevention_comparison(body: ComparisonInput):
        return await runtime.prevention.create_comparison(body)

    @app.get("/api/v1/prevention/comparisons/{comparison_id}")
    def prevention_comparison(comparison_id: str):
        return runtime.prevention.comparison_detail(comparison_id)

    @app.get("/api/v1/prevention/comparisons/{comparison_id}/scene")
    def prevention_scene(comparison_id: str, request: Request, response: Response,
                         evaluation_snapshot_hash: str = Query(pattern=r"^[0-9a-f]{64}$")):
        from .services.tank_scene import build_tank_scene

        response.headers["Cache-Control"] = "no-store"
        comparison = runtime.store.get("prevention_comparison", comparison_id)
        if comparison["data_origin"] == "MEASURED_TANK":
            operator(request)
        return build_tank_scene(runtime, comparison_id, evaluation_snapshot_hash)

    @app.get("/api/v1/prevention/comparisons/{comparison_id}/export", dependencies=[Depends(operator)])
    def prevention_export(comparison_id: str):
        return export_comparison(runtime, comparison_id)

    @app.get("/api/v1/prevention/comparisons/{comparison_id}/validation-template", dependencies=[Depends(operator)])
    def prevention_validation_template(comparison_id: str, origin: str = "SYNTHETIC_DEMO"):
        return template_validation_report(runtime, comparison_id, origin)

    @app.get("/api/v1/prevention/comparisons/{comparison_id}/validation-reports", dependencies=[Depends(operator)])
    def prevention_validation_reports(comparison_id: str):
        return list_validation_reports(runtime, comparison_id)

    @app.get("/api/v1/prevention/comparisons/{comparison_id}/validation-reports/{report_id}", dependencies=[Depends(operator)])
    def prevention_validation_report(comparison_id: str, report_id: str):
        result = get_validation_report(runtime, report_id)
        if result["report"]["comparison_id"] != comparison_id:
            raise KeyError(report_id)
        return result

    @app.post("/api/v1/prevention/comparisons/{comparison_id}/validation-reports", dependencies=[Depends(operator)])
    def prevention_accept_validation(comparison_id: str, body: ValidationReportInput):
        return accept_validation_report(runtime, comparison_id, body)

    @app.post("/api/v1/prevention/comparisons/{comparison_id}/trials", dependencies=[Depends(operator)])
    def prevention_trial(comparison_id: str, body: TrialInput):
        return runtime.prevention.add_trial(comparison_id, body)

    @app.post("/api/v1/prevention/comparisons/{comparison_id}/investigate", dependencies=[Depends(operator)])
    async def prevention_investigate(comparison_id: str, body: PreventionQuestion):
        from .services.prevention_investigation import investigate_prevention
        return await investigate_prevention(runtime, comparison_id, body.text,
                                            validation_report_id=body.validation_report_id)

    @app.post("/api/v1/prevention/demo", dependencies=[Depends(operator)])
    async def prevention_demo():
        return await runtime.prevention.load_demo()

    @app.post("/api/v1/profiles", dependencies=[Depends(operator)])
    def add_profile(profile: dict):
        return runtime.register_profile(profile)

    @app.post("/api/v1/vision/calibrate", dependencies=[Depends(operator)])
    def calibrate(body: CalibrationInput):
        report = fit_homography(**body.model_dump())
        return runtime.store.put("calibration", report, report["calibration_id"])

    @app.post("/api/v1/flow/fit", dependencies=[Depends(operator)])
    def fit_flow(body: dict):
        from apps.transport.reeftrace_transport import fit_flow
        allowed = {"samples", "bounds", "validation_samples", "cell_size_cm", "coverage_radius_cm"}
        if set(body) - allowed or not 1 <= len(body.get("samples", [])) <= 10000:
            raise ValueError("Supply 1-10000 measured samples and supported flow-fit fields")
        return fit_flow(**body, data_origin="OPERATOR_SUPPLIED_UNVERIFIED")

    @app.post("/api/v1/flow/fit-recordings", dependencies=[Depends(operator)])
    def fit_recordings(body: dict):
        return runtime.fit_recorded_flow(body)

    @app.get("/api/v1/cases")
    def cases():
        return runtime.store.cases()

    @app.post("/api/v1/cases", dependencies=[Depends(operator)])
    def add_case(body: CaseInput):
        return runtime.add_case(body)

    @app.get("/api/v1/cases/{case_id}")
    def get_case(case_id: str):
        return runtime.store.case(case_id)

    @app.get("/api/v1/cases/{case_id}/evidence")
    def evidence(case_id: str):
        case = runtime.store.case(case_id)
        if not case.get("evidence_id"):
            raise HTTPException(404, "No estimate yet")
        return runtime.store.get("estimate", case["evidence_id"])

    @app.get("/api/v1/cases/{case_id}/actions")
    def case_actions(case_id: str):
        return runtime.store.actions_for_case(case_id)

    @app.post("/api/v1/cases/{case_id}/estimate", dependencies=[Depends(operator)])
    async def estimate_case(case_id: str):
        return await runtime.compute(case_id)

    @app.post("/api/v1/cases/{case_id}/sensitivity", dependencies=[Depends(operator)])
    async def sensitivity(case_id: str, body: SensitivityInput):
        return await runtime.sensitivity(case_id)

    @app.post("/api/v1/cases/{case_id}/investigate", dependencies=[Depends(operator)])
    async def investigate(case_id: str, body: Question):
        return await runtime.investigate(case_id, body.text)

    @app.post("/api/v1/cases/{case_id}/stop", dependencies=[Depends(operator)])
    def stop(case_id: str):
        return runtime.store.stop_case(case_id)

    @app.post("/api/v1/actions/propose", dependencies=[Depends(operator)])
    def propose(body: ProposalInput):
        return runtime.propose(body.case_id, body.evidence_id, operator=True)

    @app.get("/api/v1/actions/{action_id}")
    def action(action_id: str):
        return runtime.store.action(action_id)

    @app.post("/api/v1/actions/{action_id}/approve", dependencies=[Depends(operator)])
    def approve(action_id: str):
        return runtime.approve(action_id)

    @app.post("/api/v1/actions/{action_id}/cancel", dependencies=[Depends(operator)])
    def cancel(action_id: str):
        return runtime.store.transition_action(action_id, "cancelled")

    @app.post("/api/v1/actions/{action_id}/outcome", dependencies=[Depends(operator)])
    def outcome(action_id: str, body: OutcomeInput):
        if body.outcome == "manual_recovered" and body.recovered_count == 0:
            raise ValueError("A recovered outcome requires a counted recovered token")
        action = runtime.store.transition_action(action_id, body.outcome, note=body.model_dump())
        runtime.store.put("rig_change", {"changed_at": time.time(), "reason": "manual_recovery",
                                         "action_id": action_id})
        return action

    @app.post("/api/v1/rig/disturbed", dependencies=[Depends(operator)])
    def disturbed():
        return runtime.store.put("rig_change", {"changed_at": time.time(), "reason": "operator_reported"})

    @app.post("/api/v1/rig/revalidate", dependencies=[Depends(operator)])
    def revalidate(body: dict):
        if set(body) != {"profile_id", "recording_id", "checks"}:
            raise ValueError("Provide profile_id, recording_id and physical checks")
        return runtime.revalidate_rig(**body)

    @app.post("/api/v1/camera/start", dependencies=[Depends(operator)])
    def camera_start(body: CameraInput):
        return runtime.camera.start(body.device_index)

    @app.post("/api/v1/camera/stop", dependencies=[Depends(operator)])
    def camera_stop():
        runtime.camera.stop()
        return runtime.camera.status()

    @app.get("/api/v1/camera/frame.jpg")
    def frame():
        _, metadata = runtime.camera.image()
        return Response(metadata["jpeg"], media_type="image/jpeg",
                        headers={"Cache-Control": "no-store", "X-Frame-Id": str(metadata["sequence"])})

    @app.get("/api/v1/camera/stream.mjpg")
    async def camera_stream(request: Request, session_id: str = Query(min_length=1, max_length=80)):
        try:
            status, _ = runtime.camera.preview_snapshot()
        except ValueError as error:
            raise HTTPException(503, str(error),
                                headers={"Cache-Control": "no-store"}) from None
        if status["session_id"] != session_id:
            raise HTTPException(409, "Camera session changed; reconnect the live preview",
                                headers={"Cache-Control": "no-store"})
        return StreamingResponse(
            iter_camera_mjpeg(runtime.camera, request, session_id),
            media_type=f"multipart/x-mixed-replace; boundary={MJPEG_BOUNDARY}",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/v1/camera/record", dependencies=[Depends(operator)])
    async def record(body: RecordInput):
        return await runtime.record(body.profile_id, body.duration_s, body.calibration_id)

    @app.get("/api/v1/recordings")
    def recordings():
        return runtime.store.list("recording", 30)

    @app.get("/api/v1/flow/{flow_id}/vector-diagnostic")
    def recorded_flow_vectors(flow_id: str, response: Response):
        from apps.vision.reeftrace_vision.field_vector_diagnostic import (
            inspect_recorded_flow_vectors,
        )
        response.headers["Cache-Control"] = "no-store"
        try:
            return inspect_recorded_flow_vectors(runtime.store, flow_id)
        except KeyError:
            raise HTTPException(404, "Recorded flow evidence not found",
                                headers={"Cache-Control": "no-store"}) from None
        except ValueError as error:
            raise HTTPException(409, str(error)[:300],
                                headers={"Cache-Control": "no-store"}) from None

    @app.get("/api/v1/flow/{flow_id}/trajectory-diagnostic")
    def recorded_flow_trajectories(flow_id: str, response: Response):
        from apps.vision.reeftrace_vision.field_trajectory_diagnostic import (
            inspect_recorded_flow_trajectories,
        )
        response.headers["Cache-Control"] = "no-store"
        try:
            return inspect_recorded_flow_trajectories(runtime.store, flow_id)
        except KeyError:
            raise HTTPException(404, "Recorded flow evidence not found",
                                headers={"Cache-Control": "no-store"}) from None
        except ValueError as error:
            raise HTTPException(409, str(error)[:300],
                                headers={"Cache-Control": "no-store"}) from None

    @app.get("/api/v1/recordings/{recording_id}/flow-samples")
    def samples(recording_id: str):
        return {"samples": flow_samples(runtime.store.get("recording", recording_id)["points"])}

    @app.post("/api/v1/recordings/{recording_id}/case", dependencies=[Depends(operator)])
    def case_from_recording(recording_id: str, body: RecordingCaseInput | None = None):
        body = body or RecordingCaseInput()
        recording = runtime.store.get("recording", recording_id)
        profile = runtime.store.get("profile", recording["profile_id"])
        tracks = {p.get("track_id") for p in recording["points"] if p.get("observed")}
        if len(tracks) != 1 or any(not p.get("observed") for p in recording["points"]):
            raise ValueError("Recording has gaps/ambiguous associations; record one continuous permitted segment")
        points = [{k: p[k] for k in ("t_s", "x_cm", "y_cm", "quality", "observed", "frame_id")}
                  for p in recording["points"] if p.get("observed")]
        endpoint = None
        if body.observation_type == "retained_endpoint":
            import numpy as np

            from apps.vision.reeftrace_vision.tracking import in_polygon
            xy = np.array([[p["x_cm"], p["y_cm"]] for p in points])
            center = np.median(xy, axis=0)
            calibration = runtime.store.get("calibration", profile["calibration_id"])
            spread = np.linalg.norm(xy - center, axis=1).max()
            stable = spread <= max(calibration["max_error_cm"] * 2, 0.2)
            supported = any(trap.get("validated") and all(in_polygon(p, trap["polygon_cm"]) for p in xy)
                            for trap in profile.get("traps", []))
            if not stable or not supported:
                raise ValueError("Retained endpoint requires a stable measured token inside the validated surface pocket")
            endpoint = {"x_cm": float(center[0]), "y_cm": float(center[1]), "retained": True}
            points = []  # Raw stationary observations remain in the immutable recording.
        return runtime.add_case(CaseInput(profile_id=profile["id"], calibration_id=profile["calibration_id"],
            token_class=profile["token_class"], points=points, endpoint=endpoint, mode="LIVE",
            camera_session_id=recording["camera_session_id"], evidence_frame_ids=recording["evidence_frame_ids"]),
            recording_id=recording_id)

    @app.post("/api/v1/demo/load", dependencies=[Depends(operator)])
    async def demo():
        return await runtime.load_demo(ROOT / "data/sample_runs")

    @app.get("/api/v1/datasets")
    def datasets():
        path = ROOT / "config/datasets.yaml"
        return yaml.safe_load(path.read_text()) if path.exists() else {"datasets": []}

    @app.get("/api/v1/research/real-data")
    def real_data_example():
        """Replay the pinned public drifter benchmark without touching tank cases."""
        from apps.ocean.reeftrace_ocean.benchmark import run_real_data_example

        try:
            return run_real_data_example()
        except OSError:
            raise HTTPException(503, "The pinned public dataset is unavailable locally") from None

    return app


app = create_app()
