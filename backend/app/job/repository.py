"""Data access layer for the Job feature.

Pure persistence operations over ``AsyncSession`` — no business rules.
All reads default to active (non-deleted) jobs unless a method explicitly
opts into deleted rows.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.job.enums import JobStatus, SourcePlatform
from app.job.filters import apply_filters, apply_sorting, base_job_query
from app.job.models import Job
from app.job.schemas import JobFilterRequest


class JobRepository:
    """SQLAlchemy repository for the ``jobs`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, job: Job) -> Job:
        """Persist a new job and return it with its generated identity."""
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def get(
        self, job_id: uuid.UUID, *, include_deleted: bool = False
    ) -> Job | None:
        """Fetch a job by id (active only unless ``include_deleted``)."""
        statement = base_job_query().where(Job.id == job_id)
        if include_deleted:
            statement = select(Job).where(Job.id == job_id)
        return await self._session.scalar(statement)

    async def get_by_url(self, application_url: str) -> Job | None:
        """Fetch an active job by its application URL."""
        statement = base_job_query().where(Job.application_url == application_url)
        return await self._session.scalar(statement)

    async def get_by_external_id(
        self,
        source_platform: SourcePlatform,
        external_job_id: str,
    ) -> Job | None:
        """Fetch a job by its source identity (includes deleted rows)."""
        statement = select(Job).where(
            Job.source_platform == source_platform,
            Job.external_job_id == external_job_id,
        )
        return await self._session.scalar(statement)

    async def list(
        self,
        filters: JobFilterRequest,
        *,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> tuple[Sequence[Job], int]:
        """Return a filtered, sorted page of active jobs and the total count."""
        base = apply_filters(base_job_query(), filters)
        count = await self._session.scalar(
            select(func.count()).select_from(base.subquery())
        )
        total = int(count or 0)
        statement = (
            apply_sorting(base, sort_by, sort_order)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = (await self._session.scalars(statement)).all()
        return items, total

    async def delete(self, job: Job) -> None:
        """Soft-delete a job (sets ``deleted_at``; row stays in the table)."""
        job.soft_delete()
        await self._session.flush()

    async def restore(self, job: Job) -> None:
        """Restore a soft-deleted job."""
        job.restore()
        await self._session.flush()

    async def bulk_create(self, jobs: Sequence[Job]) -> Sequence[Job]:
        """Persist many jobs in one flush and return them with identities."""
        self._session.add_all(jobs)
        await self._session.flush()
        for job in jobs:
            await self._session.refresh(job)
        return jobs

    async def bulk_update(self, jobs: Sequence[Job]) -> Sequence[Job]:
        """Flush attribute changes on many already-persisted jobs."""
        for job in jobs:
            self._session.add(job)
        await self._session.flush()
        for job in jobs:
            await self._session.refresh(job)
        return jobs

    async def bulk_archive(self, job_ids: Sequence[uuid.UUID]) -> int:
        """Set status and archive flag for many jobs; returns affected rows."""
        result = await self._session.execute(
            update(Job)
            .where(Job.id.in_(job_ids), Job.deleted_at.is_(None))
            .values(status=JobStatus.ARCHIVED, archived=True)
        )
        return result.rowcount or 0

    async def upsert(
        self,
        source_platform: SourcePlatform,
        external_job_id: str,
        values: dict[str, object],
    ) -> tuple[Job, bool]:
        """Update a job by source identity or create it; returns (job, created)."""
        job = await self.get_by_external_id(source_platform, external_job_id)
        if job is None:
            job = Job(
                source_platform=source_platform,
                external_job_id=external_job_id,
                **values,
            )
            return await self.create(job), True
        for key, value in values.items():
            setattr(job, key, value)
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return job, False
