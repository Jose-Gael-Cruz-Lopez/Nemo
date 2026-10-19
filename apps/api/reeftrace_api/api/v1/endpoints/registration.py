"""Additive operator-only registration endpoints; no image uploads or camera starts."""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field, StrictBool

from apps.vision.reeftrace_vision.registration import RegistrationConfig, RigContext, Strict


class Approval(Strict):
    proposal_id: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    water_surface_and_scale_confirmed: StrictBool
    confirmed_layers: Annotated[list[Literal["tray_boundary", "filter_border"]],
                                Field(max_length=2)] = Field(default_factory=list)


def create_registration_router(runtime, operator):
    def local_only(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        if getattr(request.app.state, "deployment_profile", None) == "cloud_software_demo":
            raise HTTPException(503, "Registration requires the local capture companion",
                                headers={"Cache-Control": "no-store"})

    router = APIRouter(prefix="/vision/registration", tags=["registration"],
                       dependencies=[Depends(local_only), Depends(operator)])

    @router.post("/configure")
    def configure(body: RegistrationConfig):
        return runtime.registration.configure(body)

    @router.get("/status")
    def status():
        return runtime.registration.sample()

    @router.post("/approve")
    def approve(body: Approval):
        if not body.water_surface_and_scale_confirmed:
            raise ValueError("Operator must confirm measured scale and water-surface reference height")
        return runtime.registration.approve(body.proposal_id, body.confirmed_layers)

    @router.post("/context")
    def context(body: RigContext):
        return runtime.registration.change_context(body)

    return router
