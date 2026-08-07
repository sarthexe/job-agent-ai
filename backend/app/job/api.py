"""HTTP API for the Job feature, mounted at ``/api/v1/jobs``."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.job.enums import (
    EmploymentType,
    ExperienceLevel,
    JobStatus,
    RemoteType,
    SourcePlatform,
)
from app.job.schemas import (
    JobCreate,
    JobFilterRequest,
    JobListResponse,
    JobRead,
    JobSearchRequest,
    JobUpdate,
)
from app.job.service import JobService
from app.shared.database import get_db

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def get_job_service(db: AsyncSession = Depends(get_db)) -> JobService:
    """Build a request-scoped JobService from the database dependency."""
    return JobService(db)


@router.post("/", response_model=JobRead, status_code=status.HTTP_201_CREATED)
async def create_job(
    data: JobCreate, service: JobService = Depends(get_job_service)
) -> JobRead:
    """Create a job."""
    return await service.create_job(data)


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    service: JobService = Depends(get_job_service),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    q: str | None = Query(default=None, max_length=255),
    company: str | None = Query(default=None, max_length=255),
    location: str | None = Query(default=None, max_length=255),
    remote_type: RemoteType | None = None,
    employment_type: EmploymentType | None = None,
    experience_level: ExperienceLevel | None = None,
    status_filter: JobStatus | None = Query(default=None, alias="status"),
    source_platform: SourcePlatform | None = None,
    salary_min: int | None = Query(default=None, ge=0),
    salary_max: int | None = Query(default=None, ge=0),
    match_score_min: float | None = Query(default=None, ge=0, le=1),
    posted_from: str | None = None,
    posted_to: str | None = None,
) -> JobListResponse:
    """List jobs with filtering, pagination, and sorting."""
    filters = JobFilterRequest(
        query=q,
        company=company,
        location=location,
        remote_type=remote_type,
        employment_type=employment_type,
        experience_level=experience_level,
        status=status_filter,
        source_platform=source_platform,
        salary_min=salary_min,
        salary_max=salary_max,
        match_score_min=match_score_min,
        posted_from=datetime.fromisoformat(posted_from) if posted_from else None,
        posted_to=datetime.fromisoformat(posted_to) if posted_to else None,
    )
    return await service.search_jobs(
        JobSearchRequest(
            filters=filters,
            page=page,
            page_size=page_size,
            sort_by=sort_by,  # type: ignore[arg-type]
            sort_order=sort_order,  # type: ignore[arg-type]
        )
    )


@router.post("/search", response_model=JobListResponse)
async def search_jobs(
    request: JobSearchRequest,
    service: JobService = Depends(get_job_service),
) -> JobListResponse:
    """Search jobs with a structured payload (filters, pagination, sorting)."""
    filters = request.filters or JobFilterRequest()
    if request.query and filters.query is None:
        filters.query = request.query
    return await service.search_jobs(
        JobSearchRequest(
            query=request.query,
            filters=filters,
            page=request.page,
            page_size=request.page_size,
            sort_by=request.sort_by,
            sort_order=request.sort_order,
        )
    )


@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: uuid.UUID, service: JobService = Depends(get_job_service)
) -> JobRead:
    """Fetch a job by id."""
    return await service.get_job(job_id)


@router.patch("/{job_id}", response_model=JobRead)
async def update_job(
    job_id: uuid.UUID,
    data: JobUpdate,
    service: JobService = Depends(get_job_service),
) -> JobRead:
    """Partially update a job."""
    return await service.update_job(job_id, data)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: uuid.UUID, service: JobService = Depends(get_job_service)
) -> None:
    """Soft-delete a job."""
    await service.delete_job(job_id)


@router.post("/bulk", response_model=list[JobRead], status_code=status.HTTP_201_CREATED)
async def bulk_create_jobs(
    items: list[JobCreate],
    service: JobService = Depends(get_job_service),
) -> Sequence[JobRead]:
    """Create many jobs in a single request."""
    created = await service.bulk_create_jobs(items)
    return [JobRead.model_validate(job) for job in created]


@router.post("/{job_id}/archive", response_model=JobRead)
async def archive_job(
    job_id: uuid.UUID, service: JobService = Depends(get_job_service)
) -> JobRead:
    """Archive a job."""
    return await service.archive_job(job_id)


@router.post("/{job_id}/restore", response_model=JobRead)
async def restore_job(
    job_id: uuid.UUID, service: JobService = Depends(get_job_service)
) -> JobRead:
    """Restore a soft-deleted job."""
    return await service.restore_job(job_id)


@router.post("/{job_id}/apply", response_model=JobRead)
async def mark_applied(
    job_id: uuid.UUID, service: JobService = Depends(get_job_service)
) -> JobRead:
    """Mark a job as applied."""
    return await service.mark_applied(job_id)


@router.post("/{job_id}/interview", response_model=JobRead)
async def mark_interview(
    job_id: uuid.UUID, service: JobService = Depends(get_job_service)
) -> JobRead:
    """Move a job to the interview stage."""
    return await service.mark_interview(job_id)


@router.post("/{job_id}/offer", response_model=JobRead)
async def mark_offer(
    job_id: uuid.UUID, service: JobService = Depends(get_job_service)
) -> JobRead:
    """Move a job to the offer stage."""
    return await service.mark_offer(job_id)


@router.post("/{job_id}/reject", response_model=JobRead)
async def mark_rejected(
    job_id: uuid.UUID, service: JobService = Depends(get_job_service)
) -> JobRead:
    """Mark a job as rejected."""
    return await service.mark_rejected(job_id)
