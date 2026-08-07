"""Creation/update timestamp mixin."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.types import UTCDateTime


class TimestampMixin:
    """Provides ``created_at`` and ``updated_at`` UTC timestamps.

    ``created_at`` is set by the database on insert; ``updated_at`` is
    refreshed by the database on every UPDATE (including soft deletes).
    """

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
