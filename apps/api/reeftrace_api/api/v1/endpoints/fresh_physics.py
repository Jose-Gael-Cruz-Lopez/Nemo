"""Read-only public research plus explicit, operator-authorized Chalk discussion."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import Field

from ....schemas.contracts import StrictModel
from ....services import research_investigation


class ResearchQuestion(StrictModel):
    question: str = Field(min_length=1, max_length=2000)


def create_fresh_physics_router(runtime, operator) -> APIRouter:
    router = APIRouter()

    def unavailable():
        return HTTPException(503, "The pinned fresh drifter study is unavailable locally",
                             headers={"Cache-Control": "no-store"})

    def invalid():
        return HTTPException(409, "The fresh drifter study failed its integrity or snapshot checks",
                             headers={"Cache-Control": "no-store"})

    @router.get("/research/fresh-physics")
    def fresh_physics(response: Response):
        response.headers["Cache-Control"] = "no-store"
        try:
            report = research_investigation.load_fresh_physics_report()
            research_investigation.snapshot_identity(report)
            return report
        except (FileNotFoundError, PermissionError, ImportError):
            raise unavailable() from None
        except (ValueError, TypeError, KeyError):
            raise invalid() from None

    @router.post("/research/fresh-physics/investigate", dependencies=[Depends(operator)])
    async def investigate_fresh_physics(body: ResearchQuestion, response: Response):
        response.headers["Cache-Control"] = "no-store"
        try:
            return await research_investigation.investigate_fresh_physics(runtime, body.question)
        except (FileNotFoundError, PermissionError, ImportError):
            raise unavailable() from None
        except (ValueError, TypeError, KeyError):
            raise invalid() from None

    return router
