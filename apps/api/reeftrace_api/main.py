from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.core.reeftrace_core.service import get_store

from .api.v1.endpoints.bench import router as bench_router
from .api.v1.endpoints.cases import router as cases_router
from .api.v1.endpoints.datasets import router as datasets_router
from .api.v1.endpoints.health import router as health_router

load_dotenv()


@asynccontextmanager
async def lifespan(app):
    get_store().startup_reset()
    yield


app = FastAPI(
    title="ReefTrace API",
    version="0.3.0",
    lifespan=lifespan,
    description="Forward source evidence, bounded investigation and manual net recovery.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(health_router, prefix="/api/v1")
app.include_router(bench_router, prefix="/api/v1")
app.include_router(cases_router, prefix="/v1")
app.include_router(datasets_router, prefix="/v1")


@app.get("/")
def root():
    return {"name": "ReefTrace API", "version": "3.0", "docs": "/docs"}
