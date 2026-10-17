"""Only measured observations cross inference's boundary; no release/source truth."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Point(StrictModel):
    t_s: FiniteFloat = Field(ge=0)
    x_cm: FiniteFloat
    y_cm: FiniteFloat
    quality: FiniteFloat = Field(default=1, ge=0, le=1)
    observed: bool = True
    frame_id: str | None = None


class Endpoint(StrictModel):
    x_cm: FiniteFloat
    y_cm: FiniteFloat
    retained: bool
    quality: FiniteFloat = Field(default=1, ge=0, le=1)


class CaseInput(StrictModel):
    profile_id: str = Field(min_length=1, max_length=100)
    calibration_id: str = Field(min_length=1, max_length=100)
    token_class: str = Field(min_length=1, max_length=100)
    points: list[Point] = Field(default_factory=list, max_length=1000)
    endpoint: Endpoint | None = None
    evidence_frame_ids: list[str] = Field(default_factory=list, max_length=1000)
    mode: Literal["LIVE", "REPLAY", "SYNTHETIC"] = "REPLAY"
    camera_session_id: str | None = None
    association_valid: bool = True


class Question(StrictModel):
    text: str = Field(min_length=1, max_length=4000)


class SensitivityInput(StrictModel):
    preset_id: Literal["predeclared-transport-envelope-v1"]


class ProposalInput(StrictModel):
    case_id: str
    evidence_id: str


class OutcomeInput(StrictModel):
    outcome: Literal["manual_recovered", "failed", "uncertain"]
    recovered_count: int = Field(ge=0, le=20)
    note: str = Field(min_length=1, max_length=1000)


class CameraInput(StrictModel):
    device_index: int = Field(ge=0, le=20)


class RecordInput(StrictModel):
    profile_id: str | None = None
    calibration_id: str | None = None
    duration_s: FiniteFloat = Field(ge=1, le=20)


class RecordingCaseInput(StrictModel):
    observation_type: Literal["trajectory", "retained_endpoint"] = "trajectory"


class CalibrationInput(StrictModel):
    pixel_points: list[tuple[FiniteFloat, FiniteFloat]] = Field(min_length=4, max_length=100)
    world_cm_points: list[tuple[FiniteFloat, FiniteFloat]] = Field(min_length=4, max_length=100)
    check_pixels: list[tuple[FiniteFloat, FiniteFloat]] = Field(min_length=3, max_length=100)
    check_world_cm: list[tuple[FiniteFloat, FiniteFloat]] = Field(min_length=3, max_length=100)
    max_error_cm: FiniteFloat = Field(default=0.5, gt=0, le=5)
    image_size_px: tuple[int, int]
    camera_session_id: str = Field(min_length=1, max_length=100)
