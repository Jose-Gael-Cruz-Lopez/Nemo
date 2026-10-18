"""Authenticated local live overlays without admitting camera evidence."""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field, FiniteFloat

from ....schemas.contracts import StrictModel
from ....schemas.saved_calibrations import Identifier, SavedCalibrationBundle
from ....services.detector_preview import DetectorPreviewService


class DetectorPreviewInput(StrictModel):
    reference_id: Identifier
    source: SavedCalibrationBundle
    detection_polygon_px: Annotated[list[tuple[FiniteFloat, FiniteFloat]], Field(min_length=3, max_length=32)]
    detector_mode: Literal["foreground_surface_v2", "saved_green_marker_preview_v2"] = "foreground_surface_v2"


def create_detector_preview_router(runtime, operator):
    service = DetectorPreviewService(runtime)

    def local_only(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        if getattr(request.app.state, "deployment_profile", None) == "cloud_software_demo":
            raise HTTPException(503, "Live camera frames stay on the local capture companion",
                                headers={"Cache-Control": "no-store"})

    router = APIRouter(prefix="/camera/detector-preview", tags=["detector-preview"],
                       dependencies=[Depends(local_only), Depends(operator)])

    @router.get("/references")
    def references():
        return service.references()

    @router.post("/config")
    def configure(body: DetectorPreviewInput):
        return service.configure(body)

    @router.get("/{preview_id}")
    def frame(preview_id: Identifier):
        return service.get(preview_id)

    return router
