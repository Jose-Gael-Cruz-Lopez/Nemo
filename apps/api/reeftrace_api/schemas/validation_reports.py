"""A bounded split manifest, not a caller-authoritative table of model metrics."""

from typing import Literal

from pydantic import Field, field_validator, model_validator

from .contracts import Question, StrictModel
from .evidence_export import Identifier, Origin, Sha256, TrialOrigin

VERIFICATION = "IDENTITY_AND_ACCOUNTING_CHECKED_METHOD_NOT_RERUN"


class ValidationReportManifest(StrictModel):
    schema_version: Literal["validation_report_v1"]
    comparison_id: Identifier
    input_payload_sha256: Sha256
    evaluation_snapshot_hash: Sha256
    data_origin: Origin
    outcome_origin: TrialOrigin
    protocol_id: Identifier
    purpose: Literal["CONTRACT_REHEARSAL", "DECLARED_VALIDATION_SPLIT"]
    development_trial_ids: list[Identifier] = Field(max_length=200)
    validation_trial_ids: list[Identifier] = Field(min_length=1, max_length=200)

    @field_validator("development_trial_ids", "validation_trial_ids")
    @classmethod
    def unique_canonical_ids(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Each trial ID may appear only once in a split manifest")
        return sorted(value)

    @model_validator(mode="after")
    def split_identity(self):
        if set(self.development_trial_ids) & set(self.validation_trial_ids):
            raise ValueError("Development and validation trial IDs must be disjoint")
        if self.purpose == "CONTRACT_REHEARSAL" and self.development_trial_ids:
            raise ValueError("A contract rehearsal uses existing origin trials without a development split")
        return self


class ValidationReportInput(StrictModel):
    report: ValidationReportManifest


class PreventionQuestion(Question):
    validation_report_id: Identifier | None = None
