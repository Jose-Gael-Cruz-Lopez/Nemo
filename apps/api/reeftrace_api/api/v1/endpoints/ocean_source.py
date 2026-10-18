"""Saved ocean earlier-position evidence and an explicit read-only Chalk review."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import Field, field_validator

from ....schemas.contracts import StrictModel
from ....services import ocean_source_investigation


class OceanSourceQuestion(StrictModel):
    question: str = Field(min_length=1, max_length=2000, strict=True)
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    protocol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)

    @field_validator("question")
    @classmethod
    def nonempty_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("An ocean earlier-position question is required")
        return value


def create_ocean_source_router(runtime, operator) -> APIRouter:
    router = APIRouter()

    def unavailable():
        return HTTPException(404, "No externally pinned ocean source diagnostic is available locally",
                             headers={"Cache-Control": "no-store"})

    def invalid():
        return HTTPException(409, "The ocean source diagnostic failed its integrity or snapshot checks",
                             headers={"Cache-Control": "no-store"})

    def unreadable():
        return HTTPException(503, "The local ocean source diagnostic reader is unavailable",
                             headers={"Cache-Control": "no-store"})

    @router.get("/research/ocean-source")
    def ocean_source(response: Response):
        response.headers["Cache-Control"] = "no-store"
        try:
            snapshot = ocean_source_investigation.load_ocean_source_result()
            ocean_source_investigation.snapshot_identity(snapshot)
            return snapshot
        except FileNotFoundError:
            raise unavailable() from None
        except (OSError, ImportError):
            raise unreadable() from None
        except (ValueError, TypeError, KeyError, IndexError, RecursionError, OverflowError):
            raise invalid() from None

    @router.post("/research/ocean-source/investigate", dependencies=[Depends(operator)])
    async def investigate_ocean_source(body: OceanSourceQuestion, response: Response):
        response.headers["Cache-Control"] = "no-store"
        try:
            return await ocean_source_investigation.investigate_ocean_source(
                runtime, body.question, report_sha256=body.report_sha256,
                protocol_sha256=body.protocol_sha256, identity_sha256=body.identity_sha256)
        except FileNotFoundError:
            raise unavailable() from None
        except (OSError, ImportError):
            raise unreadable() from None
        except (ValueError, TypeError, KeyError, IndexError, RecursionError, OverflowError):
            raise invalid() from None

    return router
