"""Optimistic locking version mixin."""

from __future__ import annotations

from sqlalchemy import Integer, text
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class VersionMixin:
    """Provides a ``version`` column for optimistic locking.

    SQLAlchemy's ``version_id_col`` machinery appends
    ``WHERE version = <expected>`` to every UPDATE and increments the
    version on success; a concurrent update that changed the row first
    raises :class:`~sqlalchemy.orm.exc.StaleDataError` instead of
    silently overwriting it.
    """

    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )

    @declared_attr
    def __mapper_args__(cls) -> dict[str, object]:
        return {"version_id_col": cls.__table__.c.version}
