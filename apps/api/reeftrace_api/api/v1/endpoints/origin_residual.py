"""Pinned exploratory artifacts and an operator-initiated read-only Chalk turn."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import Field, field_validator

from ....schemas.contracts import StrictModel
from ....services import origin_residual_investigation


class OriginResidualQuestion(StrictModel):
    question: str = Field(min_length=1, max_length=2000, strict=True)
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    protocol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)

    @field_validator("question")
    @classmethod
    def nonempty_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("An exploratory research question is required")
        return value


def create_origin_residual_router(runtime, operator) -> APIRouter:
    router = APIRouter()

    def unavailable():
        return HTTPException(404, "No externally pinned exploratory diagnostic is available locally",
                             headers={"Cache-Control": "no-store"})

    def invalid():
        return HTTPException(409, "The exploratory diagnostic failed its integrity or snapshot checks",
                             headers={"Cache-Control": "no-store"})

    def unreadable():
        return HTTPException(503, "The local exploratory diagnostic reader is unavailable",
                             headers={"Cache-Control": "no-store"})

    @router.get("/research/origin-residual")
    def origin_residual(response: Response):
        response.headers["Cache-Control"] = "no-store"
        try:
            snapshot = origin_residual_investigation.load_origin_residual_result()
            origin_residual_investigation.snapshot_identity(snapshot)
            return snapshot
        except FileNotFoundError:
            raise unavailable() from None
        except (OSError, ImportError):
            raise unreadable() from None
        except (ValueError, TypeError, KeyError, IndexError, RecursionError, OverflowError):
            raise invalid() from None

    @router.post("/research/origin-residual/investigate", dependencies=[Depends(operator)])
    async def investigate_origin_residual(body: OriginResidualQuestion, response: Response):
        response.headers["Cache-Control"] = "no-store"
        try:
            return await origin_residual_investigation.investigate_origin_residual(
                runtime, body.question, report_sha256=body.report_sha256,
                protocol_sha256=body.protocol_sha256, identity_sha256=body.identity_sha256)
        except FileNotFoundError:
            raise unavailable() from None
        except (OSError, ImportError):
            raise unreadable() from None
        except (ValueError, TypeError, KeyError, IndexError, RecursionError, OverflowError):
            raise invalid() from None

    return router
