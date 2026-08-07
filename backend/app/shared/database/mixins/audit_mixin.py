"""Audit trail mixin."""

from __future__ import annotations

import uuid

from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column


class AuditMixin:
    """Provides ``created_by`` and ``updated_by`` actor columns.

    Columns are plain UUIDs for now; wire foreign keys to the user table
    once it exists (e.g. ``ForeignKey("users.id")``).
    """

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
