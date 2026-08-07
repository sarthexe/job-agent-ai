"""Statement builders for filtering and sorting jobs.

Pure query composition — no business rules live here. The repository
combines these builders with its base (active, non-deleted) query.
"""

from __future__ import annotations

from sqlalchemy import Select, or_, select

from app.job.models import Job
from app.job.schemas import JobFilterRequest

SORT_COLUMNS: dict[str, object] = {
    "created_at": Job.created_at,
    "updated_at": Job.updated_at,
    "posted_at": Job.posted_at,
    "match_score": Job.match_score,
    "title": Job.title,
}


def base_job_query() -> Select:
    """Base query over active (non-deleted) jobs."""
    return select(Job).where(Job.deleted_at.is_(None))


def apply_filters(statement: Select, filters: JobFilterRequest) -> Select:
    """Apply every populated filter in ``filters`` to the statement."""
    if filters.query:
        pattern = f"%{filters.query}%"
        statement = statement.where(
            or_(
                Job.title.ilike(pattern),
                Job.company.ilike(pattern),
                Job.description_raw.ilike(pattern),
            )
        )
    if filters.company:
        statement = statement.where(Job.company.ilike(f"%{filters.company}%"))
    if filters.location:
        statement = statement.where(Job.location.ilike(f"%{filters.location}%"))
    if filters.remote_type is not None:
        statement = statement.where(Job.remote_type == filters.remote_type)
    if filters.employment_type is not None:
        statement = statement.where(Job.employment_type == filters.employment_type)
    if filters.experience_level is not None:
        statement = statement.where(Job.experience_level == filters.experience_level)
    if filters.status is not None:
        statement = statement.where(Job.status == filters.status)
    if filters.source_platform is not None:
        statement = statement.where(Job.source_platform == filters.source_platform)
    if filters.salary_min is not None:
        statement = statement.where(Job.salary_max >= filters.salary_min)
    if filters.salary_max is not None:
        statement = statement.where(Job.salary_min <= filters.salary_max)
    if filters.match_score_min is not None:
        statement = statement.where(Job.match_score >= filters.match_score_min)
    if filters.posted_from is not None:
        statement = statement.where(Job.posted_at >= filters.posted_from)
    if filters.posted_to is not None:
        statement = statement.where(Job.posted_at <= filters.posted_to)
    return statement


def apply_sorting(statement: Select, sort_by: str, sort_order: str) -> Select:
    """Apply a whitelisted sort column and direction to the statement."""
    column = SORT_COLUMNS[sort_by]
    return statement.order_by(column.asc() if sort_order == "asc" else column.desc())
