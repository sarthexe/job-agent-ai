"""System feature: operational endpoints.

Provides root identification, health/readiness probes (PostgreSQL, Redis,
Qdrant), liveness, version, and metrics. No business logic lives here.
"""

from app.system.api import router

__all__ = ["router"]
