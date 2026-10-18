"""Operator-only local rehearsal; never admitted as measured scientific evidence."""
from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field, FiniteFloat, StrictBool, field_validator

from ....schemas.contracts import StrictModel
from ....schemas.saved_calibrations import Dimension, Identifier, SavedCalibrationBundle
from ....services.estimated_rehearsal import EstimatedRehearsalService


class EstimatedRehearsalInput(StrictModel):
    source: SavedCalibrationBundle
    camera_session_id: Identifier
    image_size_px: tuple[Dimension, Dimension]
    duration_s: Annotated[FiniteFloat, Field(ge=1, le=10)]
    detector: Literal["foreground_reference_v1", "red_hsv"]
    reference_id: Identifier | None = None
    acknowledge_estimated_mapping: StrictBool

    @field_validator("acknowledge_estimated_mapping")
    @classmethod
    def require_acknowledgement(cls, value):
        if not value:
            raise ValueError("Acknowledge that this rehearsal uses estimated, unvalidated coordinates")
        return value


def create_estimated_rehearsal_router(runtime, operator: Callable) -> APIRouter:
    service = EstimatedRehearsalService(runtime)

    def local_only(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        if getattr(request.app.state, "deployment_profile", None) == "cloud_software_demo":
            raise HTTPException(503, "Estimated tank rehearsals stay in the local capture companion",
                                headers={"Cache-Control": "no-store"})

    router = APIRouter(prefix="/camera/rehearsals", tags=["estimated-rehearsals"],
                       dependencies=[Depends(local_only), Depends(operator)])

    @router.post("")
    async def capture(body: EstimatedRehearsalInput):
        return await service.capture(body)

    @router.get("/{rehearsal_id}")
    def get_rehearsal(rehearsal_id: str):
        return service.get(rehearsal_id)

    return router
