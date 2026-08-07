"""Data access for the system feature: dependency probes.

Each probe opens its own short-lived connection against the configured
infrastructure (PostgreSQL via the shared async engine, Redis via the
settings URL, Qdrant via its REST health endpoint) and reports
availability with latency. Probes never raise — failures are reported
as ``unavailable`` statuses.
"""

from __future__ import annotations

import asyncio
import time

import httpx
import redis.asyncio as aioredis
from sqlalchemy import text

from app.shared.config import settings
from app.shared.database import get_engine
from app.system.schemas import ServiceHealth

PROBE_TIMEOUT_SECONDS = 2.0


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 3)


async def check_postgresql() -> ServiceHealth:
    """Probe PostgreSQL by executing ``SELECT 1`` on the shared engine."""
    start = time.perf_counter()
    try:
        async with asyncio.timeout(PROBE_TIMEOUT_SECONDS):
            async with get_engine().connect() as connection:
                await connection.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 — probes report any failure as unavailable
        return ServiceHealth(status="unavailable", latency_ms=_elapsed_ms(start))
    return ServiceHealth(status="ok", latency_ms=_elapsed_ms(start))


async def check_redis() -> ServiceHealth:
    """Probe Redis with a PING on a short-lived client."""
    start = time.perf_counter()
    try:
        client = aioredis.from_url(
            settings.redis.url,
            socket_connect_timeout=PROBE_TIMEOUT_SECONDS,
        )
        try:
            async with asyncio.timeout(PROBE_TIMEOUT_SECONDS):
                await client.ping()
        finally:
            await client.aclose()
    except Exception:  # noqa: BLE001 — probes report any failure as unavailable
        return ServiceHealth(status="unavailable", latency_ms=_elapsed_ms(start))
    return ServiceHealth(status="ok", latency_ms=_elapsed_ms(start))


async def check_qdrant() -> ServiceHealth:
    """Probe Qdrant via its ``/healthz`` REST endpoint."""
    start = time.perf_counter()
    try:
        url = f"{settings.qdrant.url.rstrip('/')}/healthz"
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_SECONDS) as client:
            response = await client.get(url)
        if response.status_code != 200:
            raise RuntimeError(f"qdrant healthz returned {response.status_code}")
    except Exception:  # noqa: BLE001 — probes report any failure as unavailable
        return ServiceHealth(status="unavailable", latency_ms=_elapsed_ms(start))
    return ServiceHealth(status="ok", latency_ms=_elapsed_ms(start))
