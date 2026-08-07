"""Soft delete mixin."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.types import UTCDateTime


class SoftDeleteMixin:
    """Provides soft-delete semantics via a nullable ``deleted_at`` column.

    Rows are never physically removed: call :meth:`soft_delete` to mark a
    row deleted and :meth:`restore` to bring it back. Queries must filter
    on ``deleted_at.is_(None)`` for the "active" view — this mixin does
    not install implicit query filtering.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    @property
    def is_deleted(self) -> bool:
        """True when the row has been soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self, *, at: datetime | None = None) -> None:
        """Mark the row as deleted at the given time (defaults to now UTC)."""
        self.deleted_at = at or datetime.now(UTC)

    def restore(self) -> None:
        """Clear the deleted marker, making the row active again."""
        self.deleted_at = None
