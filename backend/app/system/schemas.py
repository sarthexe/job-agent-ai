"""Pydantic schemas for the system feature.

Response models for the operational endpoints: root info, health and
readiness (per-service dependency status), liveness, version, and metrics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ServiceStatus = Literal["ok", "unavailable"]


class ServiceHealth(BaseModel):
    """Health of a single dependency probe."""

    status: ServiceStatus
    latency_ms: float


class HealthResponse(BaseModel):
    """Overall dependency health with a per-service breakdown."""

    status: ServiceStatus
    services: dict[str, ServiceHealth]


class LivenessResponse(BaseModel):
    """Liveness probe payload."""

    status: Literal["alive"]


class RootResponse(BaseModel):
    """Root endpoint payload."""

    name: str
    version: str
    docs: str


class VersionResponse(BaseModel):
    """Application version and runtime information."""

    name: str
    version: str
    git_commit: str | None
    python_version: str
    environment: str
    startup_time: datetime
    uptime_seconds: float


class ProcessMetrics(BaseModel):
    """Process-level statistics."""

    pid: int
    memory_rss_bytes: int
    memory_vms_bytes: int
    cpu_percent: float
    threads: int
    open_files: int | None
    uptime_seconds: float


class RuntimeMetrics(BaseModel):
    """Runtime-level statistics."""

    python_version: str
    startup_time: datetime
    uptime_seconds: float


class MetricsResponse(BaseModel):
    """Metrics payload; ``custom`` holds registered provider output.

    ``metrics_version`` and the provider registry (see
    ``app.system.service.register_metric_provider``) allow future features
    to extend the payload without changing the base contract.
    """

    metrics_version: int
    process: ProcessMetrics
    runtime: RuntimeMetrics
    custom: dict[str, object]
