"""FastAPI application for the existing Smart Route Recommendation feature."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routes.advisory_api import router as advisory_router
from backend.app.routes.route_api import router as route_router
from backend.app.routes.traffic_api import router as traffic_router
from backend.app.schemas.route import HealthResponse


def cors_origins() -> list[str]:
    """Read browser origins from the environment, defaulting to local React dev servers."""
    configured_origins = os.getenv("CORS_ALLOWED_ORIGINS")
    if configured_origins:
        return [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
    return ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"]


app = FastAPI(
    title="Bengaluru Smart Route API",
    description="API wrapper for the existing Nominatim and OSRM route recommendation flow.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(route_router)
app.include_router(traffic_router)
app.include_router(advisory_router)


@app.get("/api/health", response_model=HealthResponse, tags=["health"])
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")