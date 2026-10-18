"""Small, image-free local calibration transport and checked-reuse contracts."""
from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import (
    Field,
    FiniteFloat,
    PrivateAttr,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)

from .contracts import StrictModel

Identifier = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")]
CalibrationId = Annotated[str, Field(pattern=r"^cal-[0-9a-f]{16}$")]
Dimension = Annotated[StrictInt, Field(ge=2, le=16384)]
Number = Annotated[FiniteFloat, Field(strict=True)]
Coordinate = Annotated[Number, Field(ge=-1_000_000, le=1_000_000)]
Pair = tuple[Coordinate, Coordinate]
Checks = Annotated[list[Pair], Field(min_length=3, max_length=100)]


class ReuseMetadata(StrictModel):
    method: Literal["fixed_homography_current_checks_v1"]
    source_calibration_id: CalibrationId
    source_content_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    check_pixels: Checks
    check_world_cm: Checks
    water_plane_unchanged: StrictBool


class CalibrationRecord(StrictModel):
    """Validate allowed public fields without rewriting the original JSON values."""

    homography_image_to_cm: Annotated[list[list[Number]], Field(min_length=3, max_length=3)]
    mean_error_cm: Annotated[Number, Field(ge=0)]
    max_error_cm: Annotated[Number, Field(ge=0)]
    validation_count: Annotated[StrictInt, Field(ge=3, le=100)]
    max_allowed_error_cm: Annotated[Number, Field(gt=0, le=5)]
    approved: StrictBool
    image_size_px: tuple[Dimension, Dimension]
    camera_session_id: Identifier
    plane: Literal["measured_water_surface"]
    units: Literal["cm"]
    calibration_id: CalibrationId
    id: CalibrationId
    reuse: ReuseMetadata | None = None

    @field_validator("homography_image_to_cm")
    @classmethod
    def matrix_rows(cls, rows):
        if any(len(row) != 3 for row in rows):
            raise ValueError("Homography must have three columns")
        return rows


class SavedCalibrationBundle(StrictModel):
    schema_version: Literal["nemo_saved_calibration_v1"]
    calibration: dict
    # Python's legacy content hash distinguishes 0.0 from 0. Browsers cannot
    # preserve that distinction in a parsed number, so retain the exact JSON.
    calibration_json: Annotated[str, Field(min_length=2, max_length=32_000)]
    _source_record: dict = PrivateAttr(default_factory=dict)

    @field_validator("calibration")
    @classmethod
    def bounded_public_record(cls, record):
        if len(json.dumps(record, allow_nan=False, separators=(",", ":"))) > 32_000:
            raise ValueError("Saved calibration exceeds the image-free transport limit")
        CalibrationRecord.model_validate(record)
        return record

    @model_validator(mode="after")
    def exact_source_json(self):
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Saved calibration JSON contains duplicate keys")
                result[key] = value
            return result

        def invalid_constant(_value):
            raise ValueError("Saved calibration JSON contains a nonfinite number")

        if len(self.calibration_json.encode("utf-8")) > 32_000:
            raise ValueError("Saved calibration JSON exceeds the image-free transport limit")
        record = json.loads(self.calibration_json, object_pairs_hook=unique_object,
                            parse_constant=invalid_constant)
        CalibrationRecord.model_validate(record)
        if record != self.calibration:
            raise ValueError("Saved calibration JSON does not match the displayed calibration")
        self._source_record = record
        return self

    @property
    def source_record(self):
        return self._source_record


class CalibrationRevalidationInput(StrictModel):
    source: SavedCalibrationBundle
    camera_session_id: Identifier
    image_size_px: tuple[Dimension, Dimension]
    check_pixels: Checks
    check_world_cm: Checks
    water_plane_unchanged: StrictBool

    @field_validator("water_plane_unchanged")
    @classmethod
    def unchanged_water_plane(cls, value):
        if not value:
            raise ValueError("Reuse requires the original water plane; otherwise refit the mapping")
        return value
