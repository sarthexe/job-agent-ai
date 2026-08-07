"""Business logic for the Job feature.

The service is the only entry point agents and workers may use to touch
jobs — they never own business logic and never touch the repository or
ORM directly. All rules (duplicate prevention, status transitions,
apply-once semantics) live here. Every operation is async, commits its
own transaction, and emits structured logs.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.job.enums import JobStatus
from app.job.models import Job
from app.job.repository import JobRepository
from app.job.schemas import (
    JobCreate,
    JobFilterRequest,
    JobListResponse,
    JobPagination,
    JobRead,
    JobSearchRequest,
    JobUpdate,
)
from app.job.validators import (
    validate_dates,
    validate_salary_range,
    validate_status_transition,
    validate_url,
)
from app.shared.exceptions import (
    DuplicateError,
    JobAlreadyAppliedError,
    NotFoundError,
)
from app.shared.logging import get_logger, log_execution


class JobService:
    """Application service for the Job domain."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = JobRepository(session)
        self._logger = get_logger("app.job.service")

    # --- queries ------------------------------------------------------------

    async def get_job(self, job_id: uuid.UUID) -> Job:
        """Fetch a job by id or raise NotFoundError."""
        job = await self._repository.get(job_id)
        if job is None:
            raise NotFoundError(f"job {job_id} not found")
        return job

    async def search_jobs(self, request: JobSearchRequest) -> JobListResponse:
        """Search jobs with filters, pagination, and sorting."""
        filter_data = (
            request.filters.model_dump(exclude_none=True)
            if request.filters is not None
            else {}
        )
        if request.query is not None:
            filter_data["query"] = request.query
        filters = JobFilterRequest(**filter_data)
        with log_execution(self._logger, "job_searched", query=request.query):
            items, total = await self._repository.list(
                filters,
                page=request.page,
                page_size=request.page_size,
                sort_by=request.sort_by,
                sort_order=request.sort_order,
            )
        pages = (total + request.page_size - 1) // request.page_size if total else 0
        return JobListResponse(
            items=[JobRead.model_validate(job) for job in items],
            pagination=JobPagination(
                page=request.page,
                page_size=request.page_size,
                total=total,
                pages=pages,
            ),
        )

    # --- mutations -----------------------------------------------------------

    async def create_job(self, data: JobCreate) -> Job:
        """Create a job, rejecting duplicates by URL or source identity."""
        self._validate_payload(data)
        await self._reject_duplicates(
            application_url=data.application_url,
            source_platform=data.source_platform,
            external_job_id=data.external_job_id,
        )
        job = Job(
            **data.model_dump(exclude={"discovered_at"}),
            discovered_at=data.discovered_at or datetime.now(UTC),
        )
        job = await self._repository.create(job)
        await self._session.commit()
        self._logger.info("job_created", job_id=str(job.id), company=job.company)
        return job

    async def _persist(self, job: Job) -> Job:
        """Flush attribute changes on a single job and return the instance."""
        updated = await self._repository.bulk_update([job])
        return updated[0]

    async def update_job(self, job_id: uuid.UUID, data: JobUpdate) -> Job:
        """Partially update a job, enforcing domain rules on changed fields."""
        job = await self.get_job(job_id)
        payload = data.model_dump(exclude_unset=True)
        if "status" in payload:
            validate_status_transition(job.status, data.status or job.status)
        if "salary_min" in payload or "salary_max" in payload:
            validate_salary_range(
                data.salary_min if "salary_min" in payload else job.salary_min,
                data.salary_max if "salary_max" in payload else job.salary_max,
                data.salary_currency or job.salary_currency,
            )
        if data.application_url is not None:
            validate_url(data.application_url, field="application_url")
            existing = await self._repository.get_by_url(data.application_url)
            if existing is not None and existing.id != job.id:
                raise DuplicateError(
                    f"another job already uses application_url {data.application_url!r}"
                )
        validate_dates(
            data.posted_at if "posted_at" in payload else job.posted_at,
            data.expires_at if "expires_at" in payload else job.expires_at,
        )
        for key, value in payload.items():
            setattr(job, key, value)
        job = await self._persist(job)
        await self._session.commit()
        self._logger.info("job_updated", job_id=str(job.id), fields=list(payload))
        return job

    async def delete_job(self, job_id: uuid.UUID) -> None:
        """Soft-delete a job."""
        job = await self.get_job(job_id)
        await self._repository.delete(job)
        await self._session.commit()
        self._logger.info("job_deleted", job_id=str(job.id))

    async def archive_job(self, job_id: uuid.UUID) -> Job:
        """Archive a job: status -> ARCHIVED and the archive flag set."""
        job = await self.get_job(job_id)
        validate_status_transition(job.status, JobStatus.ARCHIVED)
        job.status = JobStatus.ARCHIVED
        job.archived = True
        job = await self._persist(job)
        await self._session.commit()
        self._logger.info("job_archived", job_id=str(job.id))
        return job

    async def restore_job(self, job_id: uuid.UUID) -> Job:
        """Restore a soft-deleted job (clears deletion and archive markers)."""
        job = await self._repository.get(job_id, include_deleted=True)
        if job is None:
            raise NotFoundError(f"job {job_id} not found")
        await self._repository.restore(job)
        job.archived = False
        await self._session.commit()
        # onupdate columns are expired by the flush; reload so the instance
        # stays serializable after the session closes.
        await self._session.refresh(job)
        self._logger.info("job_restored", job_id=str(job.id))
        return job

    async def _transition(self, job_id: uuid.UUID, target: JobStatus) -> Job:
        """Apply an allowed status transition and commit."""
        job = await self.get_job(job_id)
        validate_status_transition(job.status, target)
        job.status = target
        job = await self._persist(job)
        await self._session.commit()
        self._logger.info("job_status_changed", job_id=str(job.id), status=target.value)
        return job

    async def mark_applied(self, job_id: uuid.UUID) -> Job:
        """Mark a job as applied; refuses jobs already applied."""
        job = await self.get_job(job_id)
        if job.applied or job.status == JobStatus.APPLIED:
            raise JobAlreadyAppliedError(f"job {job_id} is already applied")
        validate_status_transition(job.status, JobStatus.APPLIED)
        job.status = JobStatus.APPLIED
        job.applied = True
        job = await self._persist(job)
        await self._session.commit()
        self._logger.info("job_applied", job_id=str(job.id))
        return job

    async def mark_interview(self, job_id: uuid.UUID) -> Job:
        """Move a job into the interview stage."""
        return await self._transition(job_id, JobStatus.INTERVIEW)

    async def mark_offer(self, job_id: uuid.UUID) -> Job:
        """Move a job into the offer stage."""
        return await self._transition(job_id, JobStatus.OFFER)

    async def mark_rejected(self, job_id: uuid.UUID) -> Job:
        """Mark a job as rejected."""
        return await self._transition(job_id, JobStatus.REJECTED)

    async def calculate_match_placeholder(self, job_id: uuid.UUID) -> float:
        """Placeholder scoring until the AI matcher is implemented.

        Returns 0.0 and stores it; future work replaces this with real
        resume-matching logic without changing the call contract.
        """
        job = await self.get_job(job_id)
        job.match_score = 0.0
        job = await self._persist(job)
        await self._session.commit()
        self._logger.warning("job_match_placeholder", job_id=str(job.id), score=0.0)
        return job.match_score or 0.0

    # --- bulk operations -----------------------------------------------------

    async def bulk_create_jobs(self, items: Sequence[JobCreate]) -> Sequence[Job]:
        """Create many jobs, skipping nothing; duplicates raise before insert."""
        jobs: list[Job] = []
        for data in items:
            self._validate_payload(data)
            await self._reject_duplicates(
                application_url=data.application_url,
                source_platform=data.source_platform,
                external_job_id=data.external_job_id,
            )
            jobs.append(
                Job(
                    **data.model_dump(exclude={"discovered_at"}),
                    discovered_at=data.discovered_at or datetime.now(UTC),
                )
            )
        created = await self._repository.bulk_create(jobs)
        await self._session.commit()
        self._logger.info("jobs_bulk_created", count=len(created))
        return created

    async def bulk_archive_jobs(self, job_ids: Sequence[uuid.UUID]) -> int:
        """Archive many jobs at once; returns the number archived."""
        affected = await self._repository.bulk_archive(job_ids)
        await self._session.commit()
        self._logger.info("jobs_bulk_archived", count=affected)
        return affected

    async def upsert_job(self, data: JobCreate) -> Job:
        """Create or update a job keyed by (source_platform, external_job_id).

        Requires ``external_job_id``; falls back to :meth:`create_job`
        semantics (with duplicate checks) when it is absent.
        """
        self._validate_payload(data)
        if data.external_job_id is None:
            return await self.create_job(data)
        values = data.model_dump(
            exclude={"source_platform", "external_job_id"}, exclude_none=True
        )
        job, created = await self._repository.upsert(
            data.source_platform, data.external_job_id, values
        )
        await self._session.commit()
        self._logger.info(
            "job_upserted" if created else "job_upsert_updated",
            job_id=str(job.id),
            created=created,
        )
        return job

    # --- internal helpers ----------------------------------------------------

    async def _reject_duplicates(
        self,
        *,
        application_url: str | None,
        source_platform: object,
        external_job_id: str | None,
    ) -> None:
        """Enforce unique application URLs and unique source identities."""
        if application_url is not None:
            existing = await self._repository.get_by_url(application_url)
            if existing is not None:
                raise DuplicateError(
                    f"a job with application_url {application_url!r} already exists"
                )
        if external_job_id is not None:
            existing = await self._repository.get_by_external_id(
                source_platform, external_job_id
            )
            if existing is not None:
                raise DuplicateError(
                    f"a job from {source_platform} with external id "
                    f"{external_job_id!r} already exists"
                )

    def _validate_payload(self, data: JobCreate) -> None:
        """Run payload-level domain validations before persistence."""
        validate_salary_range(data.salary_min, data.salary_max, data.salary_currency)
        validate_dates(data.posted_at, data.expires_at)
        validate_url(data.application_url, field="application_url")
        validate_url(data.company_url, field="company_url")
