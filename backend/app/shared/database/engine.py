"""Async SQLAlchemy engine lifecycle.

The engine is built from the centralized settings
(``settings.database``) and managed as a process-wide singleton. Call
:func:`close_engine` on application shutdown — ``app.main`` does this in
its lifespan handler.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.shared.config import settings

_engine: AsyncEngine | None = None


def build_engine(*, echo: bool | None = None) -> AsyncEngine:
    """Create a new async engine from the centralized database settings.

    ``echo`` overrides ``settings.database.echo`` when provided (used by
    tests to keep output clean).
    """
    database = settings.database
    return create_async_engine(
        database.url,
        echo=database.echo if echo is None else echo,
        pool_size=database.pool_size,
        max_overflow=database.max_overflow,
        pool_pre_ping=True,
    )


def get_engine() -> AsyncEngine:
    """Return the process-wide async engine, creating it on first use."""
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


async def close_engine() -> None:
    """Dispose the engine and release all pooled connections."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


__all__ = ["AsyncEngine", "build_engine", "close_engine", "get_engine"]
