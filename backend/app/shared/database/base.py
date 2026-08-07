"""Declarative base and shared metadata for all ORM models.

Every model in the application must inherit from :class:`Base`, which
provides a consistent metadata object (with a full naming convention for
Alembic autogenerate) and a type annotation map so that ``uuid.UUID`` and
``datetime`` annotations resolve to the project's preferred column types
without repeating them on every column.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import ClassVar

from sqlalchemy import MetaData, Uuid
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeEngine

from app.shared.database.types import UTCDateTime

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    type_annotation_map: ClassVar[dict[type, TypeEngine]] = {
        uuid.UUID: Uuid(as_uuid=True),
        datetime: UTCDateTime(),
    }
