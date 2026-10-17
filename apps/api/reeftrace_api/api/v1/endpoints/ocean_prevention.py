"""Pinned dynamic-current ocean prevention research, with no action authority."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import Field, field_validator

from ....schemas.contracts import StrictModel
from ....services import ocean_prevention_investigation


class OceanPreventionQuestion(StrictModel):
    question: str = Field(min_length=1, max_length=2000, strict=True)
    scenario_id: Literal["downstream-corridor-v2", "initial-proxy-v1"]
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    method_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    scenario_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)

    @field_validator("question")
    @classmethod
    def nonempty_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("An ocean prevention research question is required")
        return value


def create_ocean_prevention_router(runtime, operator) -> APIRouter:
    router = APIRouter()

    def unavailable():
        return HTTPException(503, "The pinned ocean comparison is unavailable locally",
                             headers={"Cache-Control": "no-store"})

    def invalid():
        return HTTPException(409, "The ocean comparison failed its integrity or snapshot checks",
                             headers={"Cache-Control": "no-store"})

    @router.get("/research/ocean-prevention")
    def ocean_prevention(response: Response, scenario_id: Literal[
        "downstream-corridor-v2", "initial-proxy-v1"] = "downstream-corridor-v2"):
        response.headers["Cache-Control"] = "no-store"
        try:
            report = ocean_prevention_investigation.load_ocean_prevention_report(scenario_id)
            ocean_prevention_investigation.snapshot_identity(report)
            if report["scenario"].get("id") != scenario_id:
                raise ValueError("The returned scenario differs from the selected preset")
            return report
        except (FileNotFoundError, PermissionError, ImportError):
            raise unavailable() from None
        except (ValueError, TypeError, KeyError):
            raise invalid() from None

    @router.post("/research/ocean-prevention/investigate", dependencies=[Depends(operator)])
    async def investigate_ocean_prevention(body: OceanPreventionQuestion, response: Response):
        response.headers["Cache-Control"] = "no-store"
        try:
            return await ocean_prevention_investigation.investigate_ocean_prevention(
                runtime, body.question, snapshot_sha256=body.snapshot_sha256,
                method_sha256=body.method_sha256, scenario_sha256=body.scenario_sha256,
                report_sha256=body.report_sha256, scenario_id=body.scenario_id)
        except (FileNotFoundError, PermissionError, ImportError):
            raise unavailable() from None
        except (ValueError, TypeError, KeyError):
            raise invalid() from None

    return router
