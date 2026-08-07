"""Job ORM model.

The Job table is the single source of truth for discovered jobs. AI
agents and workers read and write it exclusively through the service
layer (``app.job.service``) — never directly.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Enum,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.job.enums import (
    EmploymentType,
    ExperienceLevel,
    JobStatus,
    RemoteType,
    SourcePlatform,
)
from app.shared.database import (
    AuditMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UTCDateTime,
    UUIDMixin,
    VersionMixin,
)
from app.shared.database.base import Base

ENUM_LENGTH = 32


def _enum_values(enum: type) -> list[str]:
    """Return the string values of a StrEnum for database storage."""
    return [member.value for member in enum]


class Job(
    UUIDMixin,
    TimestampMixin,
    SoftDeleteMixin,
    AuditMixin,
    VersionMixin,
    Base,
):
    """A job posting discovered from any source platform."""

    __tablename__ = "jobs"

    # Core fields.
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_url: Mapped[str | None] = mapped_column(String(500))
    location: Mapped[str | None] = mapped_column(String(255), index=True)
    remote_type: Mapped[RemoteType] = mapped_column(
        Enum(
            RemoteType,
            values_callable=_enum_values,
            native_enum=False,
            length=ENUM_LENGTH,
        ),
        nullable=False,
        default=RemoteType.UNKNOWN,
    )
    employment_type: Mapped[EmploymentType | None] = mapped_column(
        Enum(
            EmploymentType,
            values_callable=_enum_values,
            native_enum=False,
            length=ENUM_LENGTH,
        )
    )
    experience_level: Mapped[ExperienceLevel] = mapped_column(
        Enum(
            ExperienceLevel,
            values_callable=_enum_values,
            native_enum=False,
            length=ENUM_LENGTH,
        ),
        nullable=False,
        default=ExperienceLevel.UNKNOWN,
    )
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str | None] = mapped_column(String(3))
    description_raw: Mapped[str | None] = mapped_column(Text)
    description_structured: Mapped[dict | None] = mapped_column(JSON)
    application_url: Mapped[str | None] = mapped_column(String(1000))
    source_platform: Mapped[SourcePlatform] = mapped_column(
        Enum(
            SourcePlatform,
            values_callable=_enum_values,
            native_enum=False,
            length=ENUM_LENGTH,
        ),
        nullable=False,
        default=SourcePlatform.OTHER,
        index=True,
    )
    external_job_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            values_callable=_enum_values,
            native_enum=False,
            length=ENUM_LENGTH,
        ),
        nullable=False,
        default=JobStatus.NEW,
        index=True,
    )
    match_score: Mapped[float | None] = mapped_column(Float)
    posted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)
    discovered_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, server_default=func.now(), index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    # Metadata.
    embedding_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    applied: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint(
            "source_platform",
            "external_job_id",
            name="uq_jobs_source_platform_external_job_id",
        ),
        CheckConstraint(
            "salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max",
            name="salary_range",
        ),
        CheckConstraint(
            "match_score IS NULL OR (match_score >= 0 AND match_score <= 1)",
            name="match_score",
        ),
        Index("ix_jobs_status_discovered_at", "status", "discovered_at"),
        Index("ix_jobs_company_title", "company", "title"),
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id} title={self.title!r} company={self.company!r}>"
