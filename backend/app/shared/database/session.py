"""Async session factory, FastAPI dependency, and context manager.

Two ways to obtain a session:

* **FastAPI routes / services** — declare the dependency::

      from app.shared.database import get_db

      @router.get("/items")
      async def list_items(db: AsyncSession = Depends(get_db)) -> ...:
          ...

* **Workers / scripts / background tasks** — use the context manager::

      from app.shared.database import session_scope

      async with session_scope() as session:
          session.add(record)

Commits are the caller's responsibility inside the session scope;
``get_db`` rolls back on errors and always closes. ``session_scope``
commits on success and rolls back on any exception.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from app.shared.database.engine import get_engine

_session_factory: async_sessionmaker[AsyncSession] | None = None


def build_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the given engine."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide session factory, creating it on first use."""
    global _session_factory
    if _session_factory is None:
        _session_factory = build_session_factory(get_engine())
    return _session_factory


def configure_session_factory(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """Override the session factory (used by tests to inject a test engine)."""
    global _session_factory
    _session_factory = factory


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session for the lifetime of a request.

    Rolls back on error, always closes the session. Commits are performed
    by the caller (service layer).
    """
    async with get_session_factory()() as session:
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Async context manager yielding a session with commit-on-success.

    Commits when the block exits normally and rolls back when it raises.
    Suitable for workers, scripts, and background tasks.
    """
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


__all__ = [
    "AsyncSession",
    "build_session_factory",
    "configure_session_factory",
    "get_db",
    "get_session_factory",
    "session_scope",
]
