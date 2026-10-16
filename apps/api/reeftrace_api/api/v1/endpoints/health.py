from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Report API process health; dependent-service checks will be added separately."""
    return {"status": "ok"}
