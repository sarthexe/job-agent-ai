"""Custom SQLAlchemy column types shared across the application.

Per project rules, all timestamps are stored in UTC. Prefer
:class:`UTCDateTime` over the plain ``DateTime`` type for any timestamp
column.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    """Timezone-aware datetime type that normalizes to UTC on bind and load.

    Naive values are assumed to already be in UTC (the project convention
    is to always store UTC) and are stamped with the UTC timezone. A
    ``TypeDecorator`` is used — rather than a ``DateTime`` subclass —
    because dialect adaptation bypasses custom ``result_processor``
    overrides on backends such as SQLite; decorators stay in the
    processor chain everywhere.
    """

    impl = DateTime
    cache_ok = True

    def __init__(self) -> None:
        super().__init__(timezone=True)

    def process_bind_param(
        self, value: datetime | None, dialect: object
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value

    def process_result_value(
        self, value: datetime | None, dialect: object
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value
