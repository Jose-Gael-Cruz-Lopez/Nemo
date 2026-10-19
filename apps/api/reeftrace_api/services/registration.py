"""Local marker monitor. Reads an existing frame buffer only; never starts a camera."""
from __future__ import annotations

import copy
import json
import threading
import time

from apps.vision.reeftrace_vision.registration import POLICY, RegistrationMonitor


class RegistrationService:
    def __init__(self, runtime):
        self.runtime = runtime
        self.monitor = None
        self.context = None
        self.lock = threading.RLock()
        self._invalidated = False

    def configure(self, config):
        with self.lock:
            if self.runtime.record_lock.locked():
                raise ValueError("Stop the recording before proposing a mapping")
            if self.monitor and self.monitor.approved:
                self._invalidate("Explicit replacement of registered mapping")
            self.monitor = RegistrationMonitor(config)
            self.context = config.context.model_dump()
            self._invalidated = False
            return self.status()

    def _invalidate(self, reason):
        if self.monitor:
            self.monitor.invalidate(reason)
        if not self._invalidated:
            self.runtime.store.put("rig_change", {"changed_at": time.time(),
                "reason": "marker_registration_stale", "detail": reason[:250]})
            self._invalidated = True

    def observe(self, image, frame):
        with self.lock:
            if self.monitor is None:
                raise ValueError("Configure surveyed references first")
            previously_approved = self.monitor.approved
            age = time.monotonic() - frame["received_mono_s"]
            if not 0 <= age <= POLICY["max_age_s"]:
                self.monitor.invalidate("Camera frame too old or timestamp in future")
            else:
                self.monitor.observe(image, session_id=frame["session_id"],
                    sequence=frame["sequence"], t_s=frame["received_mono_s"], context=self.context)
            if previously_approved and self.monitor.stale:
                self._invalidate(self.monitor.reason)
            return self.status()

    def sample(self):
        with self.lock:
            if self.monitor is None:
                raise ValueError("Configure surveyed references first")
            status = self.runtime.camera.status()
            if not status.get("fresh") or not status.get("running"):
                if self.monitor.candidate:
                    self._invalidate("Camera/reference stream unavailable")
                return self.status()
            try:
                image, frame = self.runtime.camera.image()
                if (frame["session_id"] != status.get("session_id")
                        or [image.shape[1], image.shape[0]] != [status.get("width"), status.get("height")]):
                    self._invalidate("Camera status/frame session or dimensions disagree")
                    return self.status()
                return self.observe(image, frame)
            except (ValueError, KeyError) as error:
                self._invalidate(str(error))
                return self.status()

    def status(self):
        if self.monitor is None:
            return {"state": "NO_REFERENCE", "reason": "Configure surveyed references first",
                    "mapping_current": False, "proposal": None, "calibration_id": None}
        return copy.deepcopy(self.monitor.snapshot())

    def approve(self, proposal_id, confirmed_layers):
        with self.lock:
            if self.runtime.record_lock.locked():
                raise ValueError("Stop recording before approving a different mapping")
            self.sample()
            if self.monitor.config.data_origin != "OPERATOR_SURVEYED":
                raise ValueError("Synthetic proposals cannot authorize physical recording")
            result = self.monitor.approve(proposal_id, confirmed_layers)
            report = self.monitor.candidate["calibration"]
            # Existing immutable calibration format/ID is unchanged. Registration
            # metadata is a sidecar, so old reports retain their original hashes.
            cid = report["calibration_id"]
            sidecar = {"calibration_id": cid, "method": "tank_registration_v1"}
            # Persist the managed gate first, so a later write failure is closed.
            try:
                for kind, payload, identity in (
                    ("marker_registration", sidecar, cid), ("calibration", report, cid),
                    ("marker_approval", {"calibration_id": cid, "proposal_id": proposal_id,
                     "proposal": self.monitor.candidate, "config": self.monitor.config.model_dump(mode="json"),
                     "policy": POLICY, "confirmed_layers": confirmed_layers}, proposal_id),
                ):
                    try:
                        self.runtime.store.put(kind, payload, identity)
                    except ValueError:
                        if self.runtime.store.get(kind, identity) != json.loads(json.dumps(
                                {**payload, "id": identity}, allow_nan=False)):
                            raise ValueError("Immutable registration identity collision") from None
            except Exception:
                self._invalidate("Could not persist immutable marker approval")
                raise
            return result

    def change_context(self, context):
        with self.lock:
            self.context = context.model_dump()
            self._invalidate("Operator declared changed waterline/layout/pump/outlet/token class")
            return self.status()

    def is_managed(self, calibration_id):
        try:
            self.runtime.store.get("marker_registration", calibration_id)
            return True
        except KeyError:
            return False

    def provenance(self, calibration_id):
        if not self.is_managed(calibration_id):
            return {}
        with self.lock:
            if not self.monitor or not self.monitor.approved or self.monitor.stale:
                raise ValueError("Marker mapping stale; no current approval receipt")
            return {"marker_approval_id": self.monitor.snapshot()["proposal_id"]}

    def supported_detections(self, calibration_id, detections):
        if not self.is_managed(calibration_id):
            return detections
        from apps.vision.reeftrace_vision.calibration import project
        from apps.vision.reeftrace_vision.tracking import in_polygon
        with self.lock:
            if not self.monitor or not self.monitor.approved or self.monitor.stale:
                raise ValueError("Marker mapping stale; centimetres withheld")
            polygon = self.monitor.config.water_polygon_cm
            matrix = self.monitor.candidate["calibration"]["homography_image_to_cm"]
            # Do not turn multiple detections into an apparently unambiguous token.
            if len(detections) != 1:
                return detections
            point = project(matrix, [[detections[0]["pixel_x"], detections[0]["pixel_y"]]])[0]
            return detections if in_polygon(point, polygon) else []

    def assert_current(self, calibration_id, *, image=None, frame=None):
        if not self.is_managed(calibration_id):
            return  # Existing manual mapping path retains its admission contract.
        with self.lock:
            if self.monitor is None:
                raise ValueError("Marker mapping requires fresh proposal/approval after process restart")
            state = self.observe(image, frame) if image is not None else self.sample()
            if not state["mapping_current"] or state["calibration_id"] != calibration_id:
                raise ValueError("Marker mapping stale/withheld: " + state["reason"])
            saved = self.runtime.store.get("calibration", calibration_id)
            expected = {**self.monitor.candidate["calibration"], "id": calibration_id}
            if saved != expected:
                self._invalidate("Managed calibration content changed")
                raise ValueError("Marker calibration integrity failed; coordinates withheld")
            self.runtime.store.get("marker_approval", state["proposal_id"])
