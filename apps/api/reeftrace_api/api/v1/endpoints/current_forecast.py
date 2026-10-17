"""Pinned current-forced preview and explicit read-only Chalk discussion."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import Field, field_validator

from ....schemas.contracts import StrictModel
from ....services import current_forecast_investigation


class CurrentForecastQuestion(StrictModel):
    question: str = Field(min_length=1, max_length=2000, strict=True)
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    method_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)

    @field_validator("question")
    @classmethod
    def nonempty_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A research question is required")
        return value


def create_current_forecast_router(runtime, operator) -> APIRouter:
    router = APIRouter()

    def unavailable():
        return HTTPException(503, "The pinned current forecast is unavailable locally",
                             headers={"Cache-Control": "no-store"})

    def invalid():
        return HTTPException(409, "The current forecast failed its integrity or snapshot checks",
                             headers={"Cache-Control": "no-store"})

    @router.get("/research/current-forecast")
    def current_forecast(response: Response):
        response.headers["Cache-Control"] = "no-store"
        try:
            report = current_forecast_investigation.load_current_forecast_report()
            current_forecast_investigation.snapshot_identity(report)
            return report
        except (FileNotFoundError, PermissionError, ImportError):
            raise unavailable() from None
        except (ValueError, TypeError, KeyError):
            raise invalid() from None

    @router.post("/research/current-forecast/investigate", dependencies=[Depends(operator)])
    async def investigate_current_forecast(body: CurrentForecastQuestion, response: Response):
        response.headers["Cache-Control"] = "no-store"
        try:
            return await current_forecast_investigation.investigate_current_forecast(
                runtime, body.question, snapshot_sha256=body.snapshot_sha256,
                method_sha256=body.method_sha256)
        except (FileNotFoundError, PermissionError, ImportError):
            raise unavailable() from None
        except (ValueError, TypeError, KeyError):
            raise invalid() from None

    return router
