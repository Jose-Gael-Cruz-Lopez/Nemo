"""Artifact-only matched-current research and explicit read-only Chalk review."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import Field, field_validator

from ....schemas.contracts import StrictModel
from ....services import matched_current_investigation


class MatchedCurrentQuestion(StrictModel):
    study_version: Literal["v1", "v2"] = "v1"
    question: str = Field(min_length=1, max_length=2000, strict=True)
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    protocol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)

    @field_validator("question")
    @classmethod
    def nonempty_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A research question is required")
        return value


def create_matched_current_router(runtime, operator) -> APIRouter:
    router = APIRouter()

    def unavailable():
        return HTTPException(404, "No externally pinned matched-current result is available locally",
                             headers={"Cache-Control": "no-store"})

    def invalid():
        return HTTPException(409, "The matched-current result failed its integrity or snapshot checks",
                             headers={"Cache-Control": "no-store"})

    def unreadable():
        return HTTPException(503, "The local matched-current artifact reader is unavailable",
                             headers={"Cache-Control": "no-store"})

    @router.get("/research/matched-current")
    def matched_current(response: Response, study_version: Literal["v1", "v2"] = "v1"):
        response.headers["Cache-Control"] = "no-store"
        try:
            snapshot = (matched_current_investigation.load_matched_current_result()
                        if study_version == "v1" else
                        matched_current_investigation.load_matched_current_result(study_version="v2"))
            matched_current_investigation.snapshot_identity(
                snapshot, expected_study_id=matched_current_investigation.STUDY_IDS[study_version])
            return snapshot
        except FileNotFoundError:
            raise unavailable() from None
        except (PermissionError, ImportError):
            raise unreadable() from None
        except (ValueError, TypeError, KeyError):
            raise invalid() from None

    @router.post("/research/matched-current/investigate", dependencies=[Depends(operator)])
    async def investigate_matched_current(body: MatchedCurrentQuestion, response: Response):
        response.headers["Cache-Control"] = "no-store"
        try:
            return await matched_current_investigation.investigate_matched_current(
                runtime, body.question, report_sha256=body.report_sha256,
                protocol_sha256=body.protocol_sha256, study_version=body.study_version)
        except FileNotFoundError:
            raise unavailable() from None
        except (PermissionError, ImportError):
            raise unreadable() from None
        except (ValueError, TypeError, KeyError):
            raise invalid() from None

    return router
