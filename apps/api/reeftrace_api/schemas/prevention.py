"""Separate intervention/evaluation contracts; release labels never enter CaseInput."""

from typing import Literal

from pydantic import Field, FiniteFloat, StrictBool, field_validator, model_validator

from .contracts import StrictModel


class ComparisonInput(StrictModel):
    case_id: str = Field(min_length=1, max_length=100)
    baseline_profile_id: str = Field(min_length=1, max_length=100)
    intervention_profile_id: str = Field(min_length=1, max_length=100)
    protected_zone_cm: list[tuple[FiniteFloat, FiniteFloat]] = Field(min_length=3, max_length=65)
    name: str = Field(min_length=1, max_length=120)
    horizon_s: FiniteFloat = Field(default=20, ge=1, le=20, strict=True)
    particles: int = Field(default=100, ge=20, le=200, strict=True)
    trials_per_source: int = Field(default=5, ge=1, le=10, strict=True)

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value):
        if not value.strip():
            raise ValueError("Comparison name must not be blank")
        return value.strip()


class TrialInput(StrictModel):
    trial_key: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")
    layout: Literal["baseline", "intervention"]
    source_id: str = Field(min_length=1, max_length=100)
    data_origin: Literal["SYNTHETIC_DEMO", "OPERATOR_REPORTED_PHYSICAL"]
    outcome: Literal["zone_entry", "intercepted_before_entry", "no_entry", "unresolved"]
    entry_time_s: FiniteFloat | None = Field(default=None, ge=0, le=20, strict=True)
    interception_time_s: FiniteFloat | None = Field(default=None, ge=0, le=20, strict=True)
    token_accounted: StrictBool
    physical_confirmed: StrictBool
    horizon_completed: StrictBool
    note: str = Field(min_length=1, max_length=1000)
    recording_id: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("note")
    @classmethod
    def nonblank_note(cls, value):
        if not value.strip():
            raise ValueError("Record an observation note")
        return value.strip()

    @model_validator(mode="after")
    def consistent_events(self):
        if self.outcome == "zone_entry":
            if self.entry_time_s is None or not self.token_accounted:
                raise ValueError("A zone entry requires its observed time and accounted token")
            if self.interception_time_s is not None and self.interception_time_s < self.entry_time_s:
                raise ValueError("A zone-entry trial may report later collection, not prior lasting capture")
        elif self.outcome == "intercepted_before_entry":
            if self.interception_time_s is None or self.entry_time_s is not None or not self.token_accounted:
                raise ValueError("Counted interception requires its time, accounted token and no zone entry")
        elif self.entry_time_s is not None or self.interception_time_s is not None:
            raise ValueError("No-entry/unresolved outcomes cannot claim event times")
        if self.outcome == "no_entry" and not self.token_accounted:
            raise ValueError("An unlocated token cannot be a confirmed no-entry outcome")
        if self.outcome in {"no_entry", "intercepted_before_entry"} and not self.horizon_completed:
            raise ValueError("No-entry and lasting interception require observing the complete fixed horizon")
        if self.data_origin == "SYNTHETIC_DEMO" and (self.physical_confirmed or self.recording_id):
            raise ValueError("Synthetic demo trials cannot claim physical confirmation or a real recording")
        if self.data_origin == "OPERATOR_REPORTED_PHYSICAL" and not self.physical_confirmed:
            raise ValueError("Explicit confirmation is required for an operator-reported physical trial")
        return self
