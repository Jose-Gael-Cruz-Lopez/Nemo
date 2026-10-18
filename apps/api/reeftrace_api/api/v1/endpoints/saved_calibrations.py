"""Operator-only, image-free calibration reuse for the local capture companion."""
from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import ValidationError

from ....schemas.saved_calibrations import CalibrationRevalidationInput
from ....services.saved_calibrations import SavedCalibrationService


def create_saved_calibrations_router(runtime, operator: Callable) -> APIRouter:
    service = SavedCalibrationService(runtime)

    def local_only(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        if getattr(request.app.state, "deployment_profile", None) == "cloud_software_demo":
            raise HTTPException(503, "Saved tank calibrations stay in the local capture companion",
                                headers={"Cache-Control": "no-store"})

    router = APIRouter(prefix="/vision/calibrations", tags=["saved-calibrations"],
                       dependencies=[Depends(local_only), Depends(operator)])

    def checked(call):
        try:
            return call()
        except ValidationError:
            raise HTTPException(409, "Saved calibration has invalid public fields") from None

    @router.get("")
    def list_calibrations():
        return checked(service.list)

    # Static POST precedes the ID route to make the intended resource explicit.
    @router.post("/revalidate")
    def revalidate(body: CalibrationRevalidationInput):
        return checked(lambda: service.revalidate(body))

    @router.get("/{calibration_id}")
    def export_calibration(calibration_id: str):
        return checked(lambda: service.export(calibration_id))

    return router
