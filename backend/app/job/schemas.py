"""Pydantic v2 schemas for the Job feature.

Create/update payloads run the domain validators from
``app.job.validators``; read responses mirror the ORM model. Enums are
accepted and serialized by their string values.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.job.enums import (
    EmploymentType,
    ExperienceLevel,
    JobStatus,
    RemoteType,
    SourcePlatform,
)
from app.job.validators import (
    ensure_aware,
    normalize_currency,
    validate_dates,
    validate_salary_range,
    validate_url,
)

MAX_STRING_LENGTH = 500


class JobCreate(BaseModel):
    """Payload for creating a job."""

    title: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    company: str = Field(min_length=1, max_length=255)
    company_url: str | None = Field(default=None, max_length=MAX_STRING_LENGTH)
    location: str | None = Field(default=None, max_length=255)
    remote_type: RemoteType = RemoteType.UNKNOWN
    employment_type: EmploymentType | None = None
    experience_level: ExperienceLevel = ExperienceLevel.UNKNOWN
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, max_length=3)
    description_raw: str | None = None
    description_structured: dict[str, Any] | None = None
    application_url: str | None = Field(default=None, max_length=MAX_STRING_LENGTH)
    source_platform: SourcePlatform = SourcePlatform.OTHER
    external_job_id: str | None = Field(default=None, max_length=255)
    status: JobStatus = JobStatus.NEW
    match_score: float | None = Field(default=None, ge=0, le=1)
    posted_at: datetime | None = None
    discovered_at: datetime | None = None
    expires_at: datetime | None = None
    notes: str | None = None

    @field_validator("salary_currency")
    @classmethod
    def _currency_upper(cls, value: str | None) -> str | None:
        return normalize_currency(value)

    @field_validator("company_url", "application_url")
    @classmethod
    def _check_url(cls, value: str | None, info: Any) -> str | None:
        return validate_url(value, field=info.field_name)

    @field_validator("posted_at", "discovered_at", "expires_at")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        return ensure_aware(value)

    @model_validator(mode="after")
    def _check_cross_field_rules(self) -> JobCreate:
        validate_salary_range(self.salary_min, self.salary_max, self.salary_currency)
        validate_dates(self.posted_at, self.expires_at)
        return self


class JobUpdate(BaseModel):
    """Payload for partially updating a job; all fields optional."""

    title: str | None = Field(default=None, min_length=1, max_length=MAX_STRING_LENGTH)
    company: str | None = Field(default=None, min_length=1, max_length=255)
    company_url: str | None = Field(default=None, max_length=MAX_STRING_LENGTH)
    location: str | None = Field(default=None, max_length=255)
    remote_type: RemoteType | None = None
    employment_type: EmploymentType | None = None
    experience_level: ExperienceLevel | None = None
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, max_length=3)
    description_raw: str | None = None
    description_structured: dict[str, Any] | None = None
    application_url: str | None = Field(default=None, max_length=MAX_STRING_LENGTH)
    status: JobStatus | None = None
    match_score: float | None = Field(default=None, ge=0, le=1)
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    notes: str | None = None

    @field_validator("salary_currency")
    @classmethod
    def _currency_upper(cls, value: str | None) -> str | None:
        return normalize_currency(value)

    @field_validator("company_url", "application_url")
    @classmethod
    def _check_url(cls, value: str | None, info: Any) -> str | None:
        return validate_url(value, field=info.field_name)

    @field_validator("posted_at", "expires_at")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        return ensure_aware(value)

    @model_validator(mode="after")
    def _check_cross_field_rules(self) -> JobUpdate:
        if self.salary_min is not None or self.salary_max is not None:
            validate_salary_range(
                self.salary_min, self.salary_max, self.salary_currency
            )
        validate_dates(self.posted_at, self.expires_at)
        return self


class JobRead(BaseModel):
    """Full job representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: Any
    title: str
    company: str
    company_url: str | None
    location: str | None
    remote_type: RemoteType
    employment_type: EmploymentType | None
    experience_level: ExperienceLevel
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    description_raw: str | None
    description_structured: dict[str, Any] | None
    application_url: str | None
    source_platform: SourcePlatform
    external_job_id: str | None
    status: JobStatus
    match_score: float | None
    posted_at: datetime | None
    discovered_at: datetime | None
    expires_at: datetime | None
    embedding_generated: bool
    applied: bool
    archived: bool
    notes: str | None
    deleted_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class JobPagination(BaseModel):
    """Pagination metadata."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    total: int = Field(ge=0)
    pages: int = Field(ge=0)


class JobListResponse(BaseModel):
    """Paginated job list."""

    items: list[JobRead]
    pagination: JobPagination


class JobFilterRequest(BaseModel):
    """Filtering criteria shared by list and search operations."""

    query: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    remote_type: RemoteType | None = None
    employment_type: EmploymentType | None = None
    experience_level: ExperienceLevel | None = None
    status: JobStatus | None = None
    source_platform: SourcePlatform | None = None
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    match_score_min: float | None = Field(default=None, ge=0, le=1)
    posted_from: datetime | None = None
    posted_to: datetime | None = None


class JobSearchRequest(BaseModel):
    """Search payload with filters, pagination, and sorting."""

    query: str | None = Field(default=None, max_length=255)
    filters: JobFilterRequest | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: Literal[
        "created_at", "updated_at", "posted_at", "match_score", "title"
    ] = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"
