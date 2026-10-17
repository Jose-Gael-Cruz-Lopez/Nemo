"""Field-session request and frozen field-manifest v1 contracts.

A request only names immutable server artifacts. It cannot claim that a gate
passed: the service re-reads every referenced object and decides. Operator
attestations are recorded as attestations, never as independent verification.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, FiniteFloat, model_validator

from .contracts import StrictModel

SCHEMA_VERSION = "field_manifest_v1"
FAKE_CAPTURE_BACKEND = "SYNTHETIC_FAKE_CAPTURE"
STEP_IDS = ("camera_session", "water_plane_mapping", "drift_recordings", "recorded_flow",
            "measured_profile", "rig_state", "first_source_observation", "operator_attestations")
ATTESTATION_KEYS = ("waterline_unchanged", "pump_setting_unchanged", "hose_and_pocket_unchanged",
                    "camera_and_light_unchanged", "coordinates_measured_in_cm")

Id = Field(min_length=1, max_length=100)


class OperatorAttestations(StrictModel):
    """The operator's own physical statements; recorded, not proven by software."""
    waterline_unchanged: bool
    pump_setting_unchanged: bool
    hose_and_pocket_unchanged: bool
    camera_and_light_unchanged: bool
    coordinates_measured_in_cm: bool


OptionalId = Field(default=None, min_length=1, max_length=100)


class FieldSessionInput(StrictModel):
    """References only. Later steps may be absent while the operator is still working;
    preflight then reports them MISSING, and freezing is refused."""
    camera_session_id: str = Id
    calibration_id: str | None = OptionalId
    training_recording_ids: list[str] = Field(default_factory=list, max_length=100)
    validation_recording_ids: list[str] = Field(default_factory=list, max_length=100)
    flow_id: str | None = OptionalId
    profile_id: str | None = OptionalId
    first_case_id: str | None = OptionalId
    rig_check_id: str | None = OptionalId
    attestations: OperatorAttestations | None = None

    @model_validator(mode="after")
    def splits_are_disjoint(self):
        for ids in (self.training_recording_ids, self.validation_recording_ids):
            if len(set(ids)) != len(ids) or any(not 1 <= len(i) <= 100 for i in ids):
                raise ValueError("Recording IDs must be distinct non-empty strings")
        if set(self.training_recording_ids) & set(self.validation_recording_ids):
            raise ValueError("Training and validation recording IDs must be disjoint")
        return self


StepStatus = Literal["PASSED", "BLOCKED", "MISSING"]


class StepResult(StrictModel):
    step: Literal[STEP_IDS]
    status: StepStatus
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=400)
    help: str = Field(default="", max_length=400)


class Preflight(StrictModel):
    status: Literal["READY", "BLOCKED"]
    steps: list[StepResult]
    content_hash: str | None = None
    manifest_id: str | None = None


# Frozen receipt -----------------------------------------------------------------

class CaptureRef(StrictModel):
    camera_session_id: str = Id
    device_index: int | None = Field(ge=0, le=20)
    backend: str = Field(min_length=1, max_length=80)
    capture_origin: Literal["USB_CAMERA_DEVICE", "SYNTHETIC_FAKE_CAPTURE"]
    image_size_px: tuple[int, int]


class CalibrationRef(StrictModel):
    calibration_id: str = Id
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_count: int = Field(ge=3)
    mean_error_cm: FiniteFloat = Field(ge=0)
    max_error_cm: FiniteFloat = Field(ge=0)
    max_allowed_error_cm: FiniteFloat = Field(gt=0)
    units: Literal["cm"]


class RecordingsRef(StrictModel):
    training_recording_ids: list[str] = Field(min_length=1)
    validation_recording_ids: list[str] = Field(min_length=1)
    training_sample_count: int = Field(ge=1)
    validation_sample_count: int = Field(ge=1)
    frame_splits_disjoint: Literal[True]
    timestamp_kind: Literal["host_receipt_not_exposure"]


class FlowRef(StrictModel):
    flow_id: str = Id
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_origin: Literal["MEASURED_TANK"]
    validation_rmse_cm_s: FiniteFloat = Field(ge=0)
    validation_coverage_fraction: FiniteFloat = Field(ge=0.9, le=1)
    node_count: int = Field(ge=1)


class ProfileRef(StrictModel):
    profile_id: str = Id
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_origin: Literal["MEASURED_TANK"]
    source_ids: list[str] = Field(min_length=2, max_length=5)
    max_validation_rmse_cm_s: FiniteFloat = Field(gt=0)
    revalidation_max_rmse_cm_s: FiniteFloat = Field(gt=0)


class ObservationRef(StrictModel):
    case_id: str = Id
    recording_id: str = Id
    mode: Literal["LIVE"]
    evidence_frame_count: int = Field(ge=1)


class Provenance(StrictModel):
    producer: Literal["reeftrace_api.field_sessions"]
    gates: Literal["server_reverified_from_stored_artifacts"]
    hardware_independently_verified: Literal[False]
    physical_attestation: Literal["operator_attested_not_independently_verified"]
    excludes: list[str]


class ManifestBody(StrictModel):
    schema_version: Literal["field_manifest_v1"]
    status: Literal["READY"]
    capture: CaptureRef
    calibration: CalibrationRef
    recordings: RecordingsRef
    flow: FlowRef
    profile: ProfileRef
    rig_check_id: str | None
    first_observation: ObservationRef
    operator_attestations: OperatorAttestations
    checks: list[StepResult]
    warnings: list[str]
    provenance: Provenance

    @model_validator(mode="after")
    def complete(self):
        if [c.step for c in self.checks] != list(STEP_IDS) or any(c.status != "PASSED" for c in self.checks):
            raise ValueError("A READY manifest lists every workflow step as PASSED, in order")
        if not all(getattr(self.operator_attestations, key) for key in ATTESTATION_KEYS):
            raise ValueError("A READY manifest needs every operator attestation")
        if (self.capture.capture_origin == "SYNTHETIC_FAKE_CAPTURE") != (
                self.capture.backend == FAKE_CAPTURE_BACKEND):
            raise ValueError("Capture origin must follow the recorded capture backend")
        if (self.capture.capture_origin == "SYNTHETIC_FAKE_CAPTURE"
                and "SYNTHETIC_FAKE_CAPTURE_NOT_PHYSICAL" not in self.warnings):
            raise ValueError("A synthetic fake-capture manifest must carry its synthetic warning")
        return self


class FieldManifestV1(ManifestBody):
    """Sealed receipt: `content_hash` covers ManifestBody; `created_at` is detached."""
    manifest_id: str = Field(pattern=r"^fm-[0-9a-f]{16}$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: FiniteFloat | None = None
