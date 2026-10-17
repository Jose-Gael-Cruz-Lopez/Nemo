"""Public read-only route for the distinct pinned Trace 2 replay envelope."""

from fastapi import APIRouter, HTTPException

from ....services import method_validation


def create_method_validation_router() -> APIRouter:
    router = APIRouter()

    @router.get("/research/prevention-method-example")
    def prevention_method_example():
        try:
            return method_validation.run_prevention_method_example()
        except (FileNotFoundError, PermissionError):
            raise HTTPException(503, "Pinned prevention-method examples are unavailable locally") from None
        except ValueError:
            raise HTTPException(409, "Pinned prevention-method replay failed its integrity or numerical check") from None

    return router
