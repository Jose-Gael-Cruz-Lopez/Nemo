"""Guided field commissioning: re-verify stored artifacts, then freeze one receipt.

This service creates nothing physical and repeats no fitting. It only reads the
immutable objects produced by the existing camera, mapping, recording, flow,
profile, rig and case endpoints, checks them against the same gates, and seals a
content-addressed field-manifest v1 when every step passes. A caller can name
objects; it cannot declare that a gate passed.
"""
from __future__ import annotations

import hashlib
import json
import math
import time

from ..schemas.field_sessions import (
    ATTESTATION_KEYS,
    FAKE_CAPTURE_BACKEND,
    SCHEMA_VERSION,
    STEP_IDS,
    FieldManifestV1,
    FieldSessionInput,
    ManifestBody,
    public_identifiers,
)

KIND = "field_manifest"
# Scope guard for the tabletop rig (a 6 qt bin is ~35 cm). Not a calibration tolerance.
MAX_TABLETOP_SPAN_CM = 200.0
EXCLUDES = ["source_release_truth", "credentials", "absolute_paths", "raw_camera_images",
            "free_text_notes"]


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def seal(body: dict) -> dict:
    """Validate a manifest body and attach its content hash and derived ID.

    The body is hashed in its normalized schema form, so a parser re-deriving it
    (for example 1 versus 1.0) computes the same digest.
    """
    body = ManifestBody.model_validate(body).model_dump(mode="json")
    content_hash = digest(body)
    return {**body, "manifest_id": "fm-" + content_hash[:16], "content_hash": content_hash}


def verify_manifest(document: dict) -> FieldManifestV1:
    """Parse a stored or exported manifest and reject any hash/ID mismatch."""
    manifest = FieldManifestV1.model_validate(document)
    body = manifest.model_dump(mode="json", exclude={"manifest_id", "content_hash", "created_at"})
    expected = digest(body)
    if manifest.content_hash != expected or manifest.manifest_id != "fm-" + expected[:16]:
        raise ValueError("Field manifest content hash does not match its body")
    return manifest


def calibration_intact(calibration: dict) -> bool:
    """`fit_homography` derives calibration_id from its own report; recompute it."""
    report = {k: v for k, v in calibration.items() if k not in {"id", "calibration_id"}}
    expected = "cal-" + hashlib.sha256(json.dumps(report, sort_keys=True, allow_nan=False)
                                       .encode()).hexdigest()[:16]
    return calibration.get("calibration_id") == expected == calibration.get("id")


DEFAULT_HELP = {
    "camera_session": "Start the external webcam yourself in the session you will use throughout.",
    "water_plane_mapping": "Fit a new mapping in this session; do not edit a saved one.",
    "drift_recordings": "Record separate training and validation drift runs in this session and mapping.",
    "recorded_flow": "Fit flow from exactly these recordings with the recorded-flow endpoint.",
    "measured_profile": "Register a MEASURED_TANK profile containing the exact flow object.",
    "rig_state": "Revalidate the profile with new drift after restoring the setup.",
    "first_source_observation": "Record a new source case with this profile in this session.",
    "operator_attestations": "Confirm each physical check only after you have made it.",
}


def _detection_key(recording):
    """Recordings made before detector selection existed used the red HSV detector."""
    detection = recording.get("detection") or {"detector": "red_hsv"}
    return (detection.get("detector"), detection.get("reference_id"))


def _step(step, status, code, message, help_text=""):
    if status != "PASSED" and not help_text:
        help_text = DEFAULT_HELP[step]
    return {"step": step, "status": status, "code": code, "message": message[:400],
            "help": help_text[:400]}


def _passed(step, code, message):
    return _step(step, "PASSED", code, message)


class Blocked(ValueError):
    def __init__(self, steps):
        self.steps = steps
        failing = [f"{s['step']}: {s['code']}" for s in steps if s["status"] != "PASSED"]
        super().__init__("Field session is not ready; " + "; ".join(failing))


class FieldSessionService:
    def __init__(self, runtime):
        self.runtime = runtime

    def _rig_change_id(self):
        # Invocation timestamps can precede a queued INSERT. Commit/insertion
        # order, not changed_at or created_at, defines the frozen generation.
        with self.runtime.store.connection() as db:
            row = db.execute("SELECT id FROM records WHERE kind='rig_change' "
                             "ORDER BY rowid DESC LIMIT 1").fetchone()
        return row[0] if row else None

    def _get(self, kind, record_id):
        try:
            return self.runtime.store.get(kind, record_id)
        except KeyError:
            return None

    @staticmethod
    def _mapped_span_cm(calibration):
        from apps.vision.reeftrace_vision.calibration import project
        try:
            w, h = (int(v) - 1 for v in calibration["image_size_px"])
            corners = project(calibration["homography_image_to_cm"], [[0, 0], [w, 0], [w, h], [0, h]])
        except (KeyError, TypeError, ValueError):
            return None
        xs, ys = [c[0] for c in corners], [c[1] for c in corners]
        return max(max(xs) - min(xs), max(ys) - min(ys))

    # One linear check per workflow step. Each returns (step_result, facts or None).
    def _camera(self, request):
        status = self.runtime.camera.status()
        name = "camera_session"
        if not status.get("running") or not status.get("session_id"):
            return _step(name, "MISSING", "CAMERA_NOT_RUNNING", "No USB camera session is running.",
                         "Select the external webcam's device index and start it yourself. "
                         "The wizard never opens a camera automatically."), None
        if status["session_id"] != request.camera_session_id:
            return _step(name, "BLOCKED", "CAMERA_SESSION_CHANGED",
                         f"The selected session {request.camera_session_id} is not the current "
                         f"session {status['session_id']}; the camera was restarted.",
                         "Map the water plane, record drift and observe again in the current session. "
                         "Artifacts from an ended session stay readable but cannot be reused."), None
        if not status.get("fresh"):
            return _step(name, "BLOCKED", "CAMERA_STALE", "The camera session has no fresh frame.",
                         "Check the USB cable and lighting, then wait for fresh frames."), None
        return _passed(name, "CAMERA_SESSION_CURRENT", "The selected camera session is current and fresh."), status

    def _mapping(self, request, camera):
        name = "water_plane_mapping"
        if not request.calibration_id:
            return _step(name, "MISSING", "MAPPING_NOT_FITTED", "No water-plane mapping is attached yet.",
                         "Fit the mapping with four or more correspondences and three separate check points."), None
        calibration = self._get("calibration", request.calibration_id)
        if calibration is None:
            return _step(name, "MISSING", "CALIBRATION_NOT_FOUND", "No saved water-plane mapping has that ID.",
                         "Fit the mapping with four or more correspondences and three separate check points."), None
        if not calibration_intact(calibration):
            return _step(name, "BLOCKED", "CALIBRATION_INTEGRITY",
                         "The saved mapping no longer matches its content-derived ID."), None
        if calibration.get("camera_session_id") != request.camera_session_id:
            return _step(name, "BLOCKED", "CALIBRATION_OTHER_SESSION",
                         "The mapping was fitted for a different camera session.",
                         "Refit the mapping in the selected camera session."), None
        if calibration.get("units") != "cm" or calibration.get("plane") != "measured_water_surface":
            return _step(name, "BLOCKED", "CALIBRATION_UNITS",
                         "The mapping is not a centimetre water-surface mapping."), None
        if not calibration.get("approved") or (calibration.get("validation_count") or 0) < 3:
            return _step(name, "BLOCKED", "MAPPING_NOT_APPROVED",
                         f"Check-point error {calibration.get('max_error_cm', float('nan')):.3g} cm exceeds the "
                         f"declared {calibration.get('max_allowed_error_cm', float('nan')):.3g} cm tolerance.",
                         "Confirm every world coordinate is measured on the water surface in centimetres "
                         "(not millimetres or inches), and that check points are separate marks. "
                         "Do not enlarge the tolerance to pass."), None
        if camera and [camera.get("width"), camera.get("height")] != list(calibration.get("image_size_px") or []):
            return _step(name, "BLOCKED", "IMAGE_SIZE_CHANGED",
                         "Current frames have different dimensions from the mapping."), None
        try:
            self.runtime.registration.assert_current(request.calibration_id)
        except ValueError as error:
            return _step(name, "BLOCKED", "MARKER_MAPPING_STALE", str(error)), None
        span = self._mapped_span_cm(calibration)
        if span is None or span > MAX_TABLETOP_SPAN_CM:
            # A mapping entered entirely in millimetres is self-consistent and passes
            # the check-point gate, so scale is checked against the tabletop scope.
            return _step(name, "BLOCKED", "MAPPING_SCALE_IMPLAUSIBLE",
                         "The mapped camera view spans "
                         + ("an invalid region" if span is None else f"{span:.0f} cm")
                         + f", beyond the {MAX_TABLETOP_SPAN_CM:.0f} cm tabletop scope.",
                         "World coordinates look like millimetres or inches. Re-measure in centimetres "
                         "(1 in = 2.54 cm, 10 mm = 1 cm) and refit."), None
        return _passed(name, "MAPPING_APPROVED",
                       f"Approved on {calibration['validation_count']} separate check points; "
                       f"max error {calibration['max_error_cm']:.3g} cm."), calibration

    def _recordings(self, request):
        from apps.vision.reeftrace_vision.tracking import flow_samples
        name = "drift_recordings"
        if not request.training_recording_ids or not request.validation_recording_ids:
            return _step(name, "MISSING", "RECORDINGS_MISSING",
                         "Both a training and a separate validation drift recording are required."), None
        splits = {}
        for split, ids in (("training", request.training_recording_ids),
                           ("validation", request.validation_recording_ids)):
            records = []
            for rid in ids:
                record = self._get("recording", rid)
                if record is None:
                    return _step(name, "MISSING", "RECORDING_NOT_FOUND", f"Recording {rid} was not found."), None
                if record.get("data_origin") != "MEASURED_TANK":
                    return _step(name, "BLOCKED", "RECORDING_NOT_MEASURED", f"Recording {rid} is not a measured capture."), None
                if record.get("camera_session_id") != request.camera_session_id:
                    return _step(name, "BLOCKED", "RECORDING_OTHER_SESSION",
                                 f"Recording {rid} belongs to another camera session."), None
                if record.get("calibration_id") != request.calibration_id:
                    return _step(name, "BLOCKED", "RECORDING_OTHER_CALIBRATION",
                                 f"Recording {rid} used a different water-plane mapping."), None
                if not record.get("evidence_frame_ids"):
                    return _step(name, "BLOCKED", "RECORDING_HAS_NO_FRAMES", f"Recording {rid} has no saved frames."), None
                records.append(record)
            splits[split] = records
        frames = {s: {f for r in rs for f in r["evidence_frame_ids"]} for s, rs in splits.items()}
        if frames["training"] & frames["validation"]:
            return _step(name, "BLOCKED", "SPLIT_FRAMES_OVERLAP",
                         "Training and validation recordings share frames.",
                         "Record validation drift as a separate run."), None
        detections = {_detection_key(r) for rs in splits.values() for r in rs}
        if len(detections) != 1:
            return _step(name, "BLOCKED", "DETECTOR_MIXED",
                         "Drift recordings used different token detectors or empty-tank references.",
                         "Record every drift run with the same detector and reference."), None
        # Samples come from the existing helper: gaps and track changes are never joined.
        counts = {s: sum(len(flow_samples(r["points"])) for r in rs) for s, rs in splits.items()}
        if not all(counts.values()):
            return _step(name, "BLOCKED", "NO_DRIFT_SAMPLES",
                         "A split has no continuous drift samples (gaps or multiple tokens).",
                         "Release one token per run and keep it visible; gaps are never bridged."), None
        facts = {"training_recording_ids": list(request.training_recording_ids),
                 "validation_recording_ids": list(request.validation_recording_ids),
                 "training_sample_count": counts["training"], "validation_sample_count": counts["validation"],
                 "frame_splits_disjoint": True, "timestamp_kind": "host_receipt_not_exposure"}
        if any(r.get("timestamp_kind") != "host_receipt_not_exposure" for rs in splits.values() for r in rs):
            return _step(name, "BLOCKED", "RECORDING_TIMESTAMP_KIND", "Unexpected recording timestamp kind."), None
        return _passed(name, "SPLITS_DISJOINT",
                       f"{counts['training']} training and {counts['validation']} validation drift samples "
                       "from disjoint recordings."), facts

    def _flow(self, request):
        name = "recorded_flow"
        if not request.flow_id:
            return _step(name, "MISSING", "FLOW_NOT_FITTED", "No recorded-flow result is attached yet."), None
        flow = self._get("flow", request.flow_id)
        if flow is None:
            return _step(name, "MISSING", "FLOW_NOT_FOUND", "No recorded-flow result has that ID.",
                         "Fit flow from the training and validation recordings."), None
        provenance = flow.get("provenance") or {}
        if (provenance.get("calibration_id") != request.calibration_id
                or provenance.get("camera_session_id") != request.camera_session_id
                or provenance.get("training_recording_ids") != list(request.training_recording_ids)
                or provenance.get("validation_recording_ids") != list(request.validation_recording_ids)):
            return _step(name, "BLOCKED", "FLOW_SPLIT_MISMATCH",
                         "The flow was fitted from different recordings, mapping or session.",
                         "Use the exact flow returned for these recordings."), None
        diagnostics = flow.get("diagnostics") or {}
        rmse, coverage = diagnostics.get("validation_rmse_cm_s"), diagnostics.get("validation_coverage_fraction")
        if flow.get("data_origin") != "MEASURED_TANK":
            return _step(name, "BLOCKED", "FLOW_NOT_MEASURED", "The flow is not a measured tank flow."), None
        if rmse is None or coverage is None or coverage < 0.9:
            return _step(name, "BLOCKED", "FLOW_UNSUPPORTED",
                         f"Only {(coverage or 0) * 100:.0f}% of validation drift lies inside measured support (90% required).",
                         "Record more independent training drift across the region the validation runs "
                         "cover. Do not widen coverage_radius_cm after seeing validation results."), None
        return _passed(name, "FLOW_VALIDATED",
                       f"Held-out RMSE {rmse:.3g} cm/s with {coverage * 100:.0f}% supported coverage."), flow

    def _profile(self, request, flow):
        name = "measured_profile"
        if not request.profile_id:
            return _step(name, "MISSING", "PROFILE_NOT_ADMITTED", "No measured profile is attached yet."), None
        profile = self._get("profile", request.profile_id)
        if profile is None:
            return _step(name, "MISSING", "PROFILE_NOT_FOUND", "No registered profile has that ID.",
                         "Register the measured profile with the exact flow object."), None
        if profile.get("data_origin") != "MEASURED_TANK":
            return _step(name, "BLOCKED", "PROFILE_NOT_MEASURED", "Synthetic profiles cannot commission a tank."), None
        if profile.get("calibration_id") != request.calibration_id:
            return _step(name, "BLOCKED", "PROFILE_OTHER_CALIBRATION", "The profile uses a different mapping."), None
        if flow is None or profile.get("flow") != flow:
            return _step(name, "BLOCKED", "PROFILE_FLOW_MISMATCH",
                         "The profile does not contain the exact immutable recorded flow."), None
        limit, tolerance = profile.get("max_validation_rmse_cm_s"), profile.get("revalidation_max_rmse_cm_s")
        rmse = flow["diagnostics"]["validation_rmse_cm_s"]
        if not all(isinstance(v, int | float) and math.isfinite(v) and v > 0 for v in (limit, tolerance)):
            return _step(name, "BLOCKED", "PROFILE_THRESHOLDS", "Profile thresholds are not frozen positive values."), None
        if rmse > limit:
            return _step(name, "BLOCKED", "PROFILE_RMSE_EXCEEDED", "Held-out drift error exceeds the profile limit."), None
        sources = [s.get("id") for s in profile.get("sources") or []]
        if not public_identifiers(sources):
            return _step(name, "BLOCKED", "UNSAFE_SOURCE_IDENTIFIERS",
                         "Source identifiers must be bounded public labels; private values were withheld."), None
        if not 2 <= len(sources) <= 5 or not profile.get("observation_polygon_cm"):
            return _step(name, "BLOCKED", "PROFILE_GEOMETRY", "The profile lacks 2-5 sources or an observation region."), None
        return _passed(name, "PROFILE_ADMITTED", f"Measured profile with sources {', '.join(map(str, sources))}."), profile

    def _rig(self, request):
        name = "rig_state"
        if not request.profile_id:
            return _step(name, "MISSING", "PROFILE_REQUIRED", "Rig state is checked against an admitted profile."), None
        changes = self.runtime.store.list("rig_change", 1)
        checks = self.runtime.store.list("rig_check", 1)
        if changes:
            latest = checks[0] if checks else None
            if (latest is None or latest["checked_at"] <= changes[0]["changed_at"]
                    or latest["profile_id"] != request.profile_id):
                return _step(name, "BLOCKED", "RIG_REVALIDATION_REQUIRED",
                             f"The rig was disturbed ({changes[0].get('reason', 'reported')}) after the last "
                             "check for this profile.",
                             "Restore the frozen setup, record new drift with this profile and revalidate it. "
                             "Earlier observations cannot be reused."), None
            if request.rig_check_id and request.rig_check_id != latest["id"]:
                return _step(name, "BLOCKED", "RIG_CHECK_NOT_LATEST", "The named rig check is not the latest one."), None
            return _passed(name, "RIG_REVALIDATED", "The profile was revalidated after the latest disturbance."), latest["id"]
        if request.rig_check_id:
            check = self._get("rig_check", request.rig_check_id)
            if check is None or check.get("profile_id") != request.profile_id:
                return _step(name, "BLOCKED", "RIG_CHECK_INVALID", "The named rig check does not belong to this profile."), None
            return _passed(name, "RIG_REVALIDATED", "No disturbance recorded since this rig check."), check["id"]
        return _passed(name, "NO_RIG_CHANGE_RECORDED", "No rig disturbance has been recorded."), ""

    def _observation(self, request, profile):
        name = "first_source_observation"
        if not request.first_case_id:
            return _step(name, "MISSING", "NO_SOURCE_OBSERVATION", "No first source observation is attached yet.",
                         "Record a new source case with this profile. A fresh preview frame is not case evidence."), None
        case = None
        try:
            case = self.runtime.store.case(request.first_case_id)
        except KeyError:
            pass
        if case is None:
            return _step(name, "MISSING", "CASE_NOT_FOUND", "No case has that ID."), None
        if (case.get("mode") != "LIVE" or case.get("profile_id") != request.profile_id
                or case.get("calibration_id") != request.calibration_id or not case.get("recording_id")):
            return _step(name, "BLOCKED", "CASE_NOT_FROM_PROFILE",
                         "The case is not a LIVE recording-based observation with this profile."), None
        if case.get("state") in {"STOPPED", "RECOVERING"}:
            return _step(name, "BLOCKED", "CASE_INACTIVE", "The case is stopped or recovering."), None
        if profile is None:
            return _step(name, "BLOCKED", "PROFILE_REQUIRED", "Admit the measured profile first."), None
        try:
            # The existing LIVE gate: current fresh session, mapping, rig state and frame lineage.
            self.runtime.validate_live(case, profile)
        except (ValueError, KeyError) as error:
            return _step(name, "BLOCKED", "OBSERVATION_NOT_CURRENT", str(error) or "Observation is not current.",
                         "Make a new source observation with the current setup."), None
        drift = self._get("recording", request.training_recording_ids[0]) if request.training_recording_ids else None
        observed = self._get("recording", case["recording_id"])
        if drift and observed and _detection_key(observed) != _detection_key(drift):
            return _step(name, "BLOCKED", "DETECTOR_MIXED",
                         "The source observation used a different token detector or reference than the drift runs.",
                         "Record the source case with the same detector and empty-tank reference."), None
        facts = {"case_id": case["id"], "recording_id": case["recording_id"], "mode": "LIVE",
                 "evidence_frame_count": len(case.get("evidence_frame_ids") or [])}
        return _passed(name, "OBSERVATION_CURRENT", "A new LIVE source observation passed the existing gate."), facts

    def _attestations(self, request):
        name = "operator_attestations"
        if request.attestations is None:
            return _step(name, "MISSING", "ATTESTATIONS_MISSING", "The operator has not confirmed the physical setup.",
                         "Confirm each fixture check yourself; software cannot verify them."), None
        missing = [k for k in ATTESTATION_KEYS if not getattr(request.attestations, k)]
        if missing:
            return _step(name, "BLOCKED", "ATTESTATION_INCOMPLETE", "Unconfirmed: " + ", ".join(missing) + ".",
                         "Restore the setup until each statement is true; do not confirm a check you did not make."), None
        return _passed(name, "OPERATOR_ATTESTED", "Operator confirmed the physical setup (not independently verified)."), True

    def evaluate(self, request: FieldSessionInput):
        identifiers = [value for key, value in request.model_dump().items()
                       if key not in {"attestations", "training_recording_ids", "validation_recording_ids"}
                       and value is not None]
        identifiers += request.training_recording_ids + request.validation_recording_ids
        if not public_identifiers(identifiers):
            return [_step(step, "BLOCKED", "UNSAFE_IDENTIFIER",
                          "Artifact identifiers must be bounded public labels; private values were withheld.")
                    for step in STEP_IDS], None
        camera_step, camera = self._camera(request)
        mapping_step, calibration = self._mapping(request, camera)
        recordings_step, recordings = self._recordings(request)
        flow_step, flow = self._flow(request)
        profile_step, profile = self._profile(request, flow)
        rig_step, rig_check_id = self._rig(request)
        observation_step, observation = self._observation(request, profile)
        attest_step, _ = self._attestations(request)
        steps = [camera_step, mapping_step, recordings_step, flow_step, profile_step, rig_step,
                 observation_step, attest_step]
        assert [s["step"] for s in steps] == list(STEP_IDS)
        if any(s["status"] != "PASSED" for s in steps):
            return steps, None
        backend = str(camera.get("backend") or "unknown")
        fake = backend == FAKE_CAPTURE_BACKEND
        diagnostics = flow["diagnostics"]
        warnings = ["HOST_RECEIPT_TIMESTAMPS_NOT_EXPOSURE", "OPERATOR_ATTESTATIONS_NOT_INDEPENDENTLY_VERIFIED",
                    "SCORES_CONDITIONAL_ON_THIS_FROZEN_SETUP"]
        if fake:
            warnings.insert(0, "SYNTHETIC_FAKE_CAPTURE_NOT_PHYSICAL")
        if diagnostics["validation_coverage_fraction"] < 1:
            warnings.append("PARTIAL_VALIDATION_COVERAGE")
        body = {
            "schema_version": SCHEMA_VERSION, "status": "READY",
            "capture": {"camera_session_id": request.camera_session_id,
                        "device_index": camera.get("device_index"), "backend": backend,
                        "capture_origin": "SYNTHETIC_FAKE_CAPTURE" if fake else "USB_CAMERA_DEVICE",
                        "image_size_px": list(calibration["image_size_px"])},
            "calibration": {"calibration_id": calibration["calibration_id"], "content_hash": digest(calibration),
                            "validation_count": calibration["validation_count"],
                            "mean_error_cm": calibration["mean_error_cm"], "max_error_cm": calibration["max_error_cm"],
                            "max_allowed_error_cm": calibration["max_allowed_error_cm"], "units": "cm"},
            "recordings": recordings,
            "flow": {"flow_id": flow["id"], "content_hash": digest(flow), "data_origin": "MEASURED_TANK",
                     "validation_rmse_cm_s": diagnostics["validation_rmse_cm_s"],
                     "validation_coverage_fraction": diagnostics["validation_coverage_fraction"],
                     "node_count": diagnostics["node_count"]},
            "profile": {"profile_id": profile["id"], "content_hash": digest(profile), "data_origin": "MEASURED_TANK",
                        "source_ids": [s["id"] for s in profile["sources"]],
                        "max_validation_rmse_cm_s": profile["max_validation_rmse_cm_s"],
                        "revalidation_max_rmse_cm_s": profile["revalidation_max_rmse_cm_s"]},
            "rig_check_id": rig_check_id or None,
            "rig_change_id": self._rig_change_id(),
            "first_observation": observation,
            "operator_attestations": request.attestations.model_dump(),
            "checks": steps, "warnings": warnings,
            "provenance": {"producer": "reeftrace_api.field_sessions",
                           "gates": "server_reverified_from_stored_artifacts",
                           "hardware_independently_verified": False,
                           "physical_attestation": "operator_attested_not_independently_verified",
                           "excludes": EXCLUDES},
        }
        return steps, body

    def preflight(self, request: FieldSessionInput) -> dict:
        steps, body = self.evaluate(request)
        if body is None:
            return {"status": "BLOCKED", "steps": steps, "content_hash": None, "manifest_id": None}
        sealed = seal(body)
        return {"status": "READY", "steps": steps, "content_hash": sealed["content_hash"],
                "manifest_id": sealed["manifest_id"]}

    def create(self, request: FieldSessionInput) -> dict:
        steps, body = self.evaluate(request)
        if body is None:
            raise Blocked(steps)
        # The first evaluation gives quick diagnostics. The committing check
        # must exclude camera restarts and committed case/rig changes until the
        # insert completes. Store reads use separate read connections; the WAL
        # writer reservation keeps their source data fixed without Store changes.
        with self.runtime.camera.lock, self.runtime.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            steps, body = self.evaluate(request)
            if body is None:
                raise Blocked(steps)
            sealed = seal(body)
            row = db.execute("SELECT payload FROM records WHERE kind=? AND id=?",
                             (KIND, sealed["manifest_id"])).fetchone()
            if row is None:
                created_at = time.time()
                existing = {**sealed, "created_at": created_at, "id": sealed["manifest_id"]}
                db.execute("INSERT INTO records VALUES(?,?,?,?)", (
                    KIND, sealed["manifest_id"], json.dumps(existing, allow_nan=False), created_at))
            else:
                existing = json.loads(row[0])
            stored = {k: v for k, v in existing.items() if k != "id"}
            if stored["content_hash"] != sealed["content_hash"]:
                raise ValueError("A different manifest already uses this ID")
        return self.detail(sealed["manifest_id"])

    def detail(self, manifest_id: str) -> dict:
        stored = {k: v for k, v in self.runtime.store.get(KIND, manifest_id).items() if k != "id"}
        manifest = verify_manifest(stored).model_dump(mode="json")
        reasons = []
        if self._rig_change_id() != manifest["rig_change_id"]:
            reasons.append("RIG_CHANGED_AFTER_RECEIPT")
        camera = self.runtime.camera.status()
        if camera.get("session_id") != manifest["capture"]["camera_session_id"]:
            reasons.append("CAMERA_SESSION_ENDED")
        elif not camera.get("running") or not camera.get("fresh"):
            reasons.append("CAMERA_STALE_OR_UNAVAILABLE")
        try:
            if self.runtime.store.case(manifest["first_observation"]["case_id"])["state"] in {"STOPPED", "RECOVERING"}:
                reasons.append("FIRST_OBSERVATION_INACTIVE")
        except KeyError:
            reasons.append("FIRST_OBSERVATION_MISSING")
        return {"manifest": manifest, "is_current": not reasons, "stale_reasons": reasons}

    def list(self) -> list[dict]:
        rows = []
        for record in self.runtime.store.list(KIND, 50):
            verify_manifest({key: value for key, value in record.items() if key != "id"})
            capture, profile = record.get("capture", {}), record.get("profile", {})
            rows.append({"manifest_id": record["id"], "content_hash": record.get("content_hash"),
                         "created_at": record.get("created_at"), "profile_id": profile.get("profile_id"),
                         "camera_session_id": capture.get("camera_session_id"),
                         "capture_origin": capture.get("capture_origin"),
                         "case_id": (record.get("first_observation") or {}).get("case_id")})
        return rows
