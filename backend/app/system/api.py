"""API routes for the system feature.

Operational endpoints live at the root (not under ``/api/v1``) so
infrastructure probes, load balancers, and monitoring tools can reach
them without version-prefixed paths.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.system import service
from app.system.schemas import (
    HealthResponse,
    LivenessResponse,
    MetricsResponse,
    RootResponse,
    VersionResponse,
)

router = APIRouter(tags=["system"])


@router.get("/", response_model=RootResponse)
async def root() -> RootResponse:
    """Service identification."""
    return service.get_root()


@router.get("/health", response_model=HealthResponse)
async def health(response: Response) -> HealthResponse:
    """Dependency health; 503 when any dependency is unavailable."""
    result = await service.get_dependency_health()
    if result.status == "unavailable":
        response.status_code = 503
    return result


@router.get("/ready", response_model=HealthResponse)
async def ready(response: Response) -> HealthResponse:
    """Readiness probe; 503 until every dependency is available."""
    result = await service.get_dependency_health()
    if result.status == "unavailable":
        response.status_code = 503
    return result


@router.get("/live", response_model=LivenessResponse)
async def live() -> LivenessResponse:
    """Liveness probe; 200 while the process serves requests."""
    return service.get_liveness()


@router.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    """Application and runtime version information."""
    return await service.get_version()


@router.get("/metrics", response_model=MetricsResponse)
async def metrics() -> MetricsResponse:
    """Process and runtime metrics (extensible via metric providers)."""
    return await service.get_metrics()
