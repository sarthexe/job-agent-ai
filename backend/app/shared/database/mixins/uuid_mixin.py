"""UUID primary key mixin."""

from __future__ import annotations

import uuid

from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column


class UUIDMixin:
    """Provides a ``id`` UUID primary key with a client-side default.

    The default is generated in Python (``uuid.uuid4``) so models work on
    any backend, including SQLite used in tests.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
