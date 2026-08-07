"""Async SQLAlchemy database infrastructure (shared foundation).

Provides the declarative ``Base``, custom column types, the async engine
built from centralized settings, session management (``get_db`` FastAPI
dependency and ``session_scope`` context manager), and reusable model
mixins. No business models live here.
"""

from app.shared.database.base import NAMING_CONVENTION, Base
from app.shared.database.engine import (
    AsyncEngine,
    build_engine,
    close_engine,
    get_engine,
)
from app.shared.database.mixins import (
    AuditMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
    VersionMixin,
)
from app.shared.database.session import (
    AsyncSession,
    build_session_factory,
    configure_session_factory,
    get_db,
    get_session_factory,
    session_scope,
)
from app.shared.database.types import UTCDateTime

__all__ = [
    "NAMING_CONVENTION",
    "AsyncEngine",
    "AsyncSession",
    "AuditMixin",
    "Base",
    "SoftDeleteMixin",
    "TimestampMixin",
    "UTCDateTime",
    "UUIDMixin",
    "VersionMixin",
    "build_engine",
    "build_session_factory",
    "close_engine",
    "configure_session_factory",
    "get_db",
    "get_engine",
    "get_session_factory",
    "session_scope",
]
