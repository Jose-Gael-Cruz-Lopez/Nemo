from fastapi import FastAPI

from .api.v1.endpoints.health import router as health_router

app = FastAPI(
    title="Reeftrace API",
    description="Local API for observation, source inference, and approved response actions.",
    version="0.1.0",
)

app.include_router(health_router, prefix="/api/v1")


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"name": "Reeftrace API", "docs": "/docs"}
