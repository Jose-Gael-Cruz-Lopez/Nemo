"""Field-session router. Lane 3 mounts it; this module never touches main.py.

Mount inside ``create_app`` after ``operator`` is defined::

    from .api.v1.endpoints.field_sessions import create_field_sessions_router
    app.include_router(create_field_sessions_router(runtime, operator), prefix="/api/v1")

Writes require the shared operator dependency. Reads are local and public, like
``GET /profiles``; a receipt holds IDs, hashes and diagnostics, never secrets,
absolute paths, raw images or release truth.
"""
from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from ....schemas.field_sessions import FieldSessionInput, Preflight
from ....services.field_sessions import Blocked, FieldSessionService


def create_field_sessions_router(runtime, operator: Callable) -> APIRouter:
    if not callable(operator):
        raise TypeError("Mount field sessions with the shared operator dependency")
    service = FieldSessionService(runtime)
    router = APIRouter(prefix="/field-sessions", tags=["field-sessions"])

    @router.post("/preflight", response_model=Preflight, dependencies=[Depends(operator)])
    def preflight(body: FieldSessionInput):
        """Explain every workflow step without saving anything."""
        try:
            return service.preflight(body)
        except ValidationError:
            raise HTTPException(409, "Field receipt has invalid public fields; source values were withheld") from None

    @router.post("", dependencies=[Depends(operator)])
    def freeze(body: FieldSessionInput):
        """Re-verify every referenced artifact and save one immutable READY receipt."""
        try:
            return service.create(body)
        except Blocked as blocked:
            raise HTTPException(409, str(blocked)[:600]) from None
        except ValidationError:
            raise HTTPException(409, "Field receipt has invalid public fields; source values were withheld") from None

    @router.get("")
    def list_manifests():
        try:
            return service.list()
        except ValidationError:
            raise HTTPException(409, "Field receipt has invalid public fields; source values were withheld") from None

    @router.get("/{manifest_id}")
    def manifest(manifest_id: str):
        try:
            return service.detail(manifest_id)
        except ValidationError:
            raise HTTPException(409, "Field receipt has invalid public fields; source values were withheld") from None

    return router
