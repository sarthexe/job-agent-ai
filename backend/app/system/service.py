"""Business logic for the system feature.

Operational services: dependency health aggregation, version information
(including the git commit when available), and process/runtime metrics.
The metrics endpoint is extensible — future features can register metric
providers via :func:`register_metric_provider` without touching this
module's contract.
"""

from __future__ import annotations

import asyncio
import inspect
import platform
import subprocess
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import psutil

from app.shared.config import settings
from app.system import repository
from app.system.schemas import (
    HealthResponse,
    LivenessResponse,
    MetricsResponse,
    ProcessMetrics,
    RootResponse,
    RuntimeMetrics,
    ServiceHealth,
    VersionResponse,
)

STARTUP_TIME: datetime = datetime.now(UTC)
_STARTUP_MONOTONIC: float = time.monotonic()

METRICS_VERSION = 1

MetricProvider = Callable[[], dict[str, object] | Awaitable[dict[str, object]]]
_metric_providers: dict[str, MetricProvider] = {}


def register_metric_provider(name: str, provider: MetricProvider) -> None:
    """Register a custom metric provider surfaced under ``custom``.

    Providers may be sync or async and must return a JSON-serializable
    dict. Intended for future features (agents, queues, vector store
    statistics, ...).
    """
    _metric_providers[name] = provider


@lru_cache
def _repo_root() -> Path | None:
    """Return the git repository root by walking up from this module."""
    current = Path(__file__).resolve().parent
    for parent in current.parents:
        if (parent / ".git").exists():
            return parent
    return None


@lru_cache
def _git_commit() -> str | None:
    """Return the short HEAD commit hash, or None when unavailable."""
    root = _repo_root()
    if root is None:
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = result.stdout.strip()
    return commit or None


async def get_dependency_health() -> HealthResponse:
    """Probe all dependencies in parallel and aggregate their status."""
    postgresql, redis, qdrant = await asyncio.gather(
        repository.check_postgresql(),
        repository.check_redis(),
        repository.check_qdrant(),
    )
    services: dict[str, ServiceHealth] = {
        "postgresql": postgresql,
        "redis": redis,
        "qdrant": qdrant,
    }
    overall = (
        "ok"
        if all(service.status == "ok" for service in services.values())
        else "unavailable"
    )
    return HealthResponse(status=overall, services=services)


def get_liveness() -> LivenessResponse:
    """Liveness probe: the process is up and serving requests."""
    return LivenessResponse(status="alive")


def get_root() -> RootResponse:
    """Basic service identification for the root endpoint."""
    return RootResponse(
        name=settings.app.name,
        version=settings.app.version,
        docs="/docs",
    )


def _uptime_seconds() -> float:
    return round(time.monotonic() - _STARTUP_MONOTONIC, 3)


async def get_version() -> VersionResponse:
    """Application version, git commit, and runtime information."""
    return VersionResponse(
        name=settings.app.name,
        version=settings.app.version,
        git_commit=_git_commit(),
        python_version=platform.python_version(),
        environment=settings.app.environment,
        startup_time=STARTUP_TIME,
        uptime_seconds=_uptime_seconds(),
    )


async def get_metrics() -> MetricsResponse:
    """Process and runtime statistics plus registered provider output."""
    process = psutil.Process()
    memory = process.memory_info()
    open_files: int | None = None
    if hasattr(process, "num_fds"):
        open_files = process.num_fds()
    elif hasattr(process, "num_handles"):
        open_files = process.num_handles()

    custom: dict[str, object] = {}
    for name, provider in _metric_providers.items():
        value = provider()
        if inspect.isawaitable(value):
            value = await value
        custom[name] = value

    return MetricsResponse(
        metrics_version=METRICS_VERSION,
        process=ProcessMetrics(
            pid=process.pid,
            memory_rss_bytes=memory.rss,
            memory_vms_bytes=memory.vms,
            cpu_percent=process.cpu_percent(interval=0.1),
            threads=process.num_threads(),
            open_files=open_files,
            uptime_seconds=_uptime_seconds(),
        ),
        runtime=RuntimeMetrics(
            python_version=platform.python_version(),
            startup_time=STARTUP_TIME,
            uptime_seconds=_uptime_seconds(),
        ),
        custom=custom,
    )
