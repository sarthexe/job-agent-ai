"""Job domain feature.

The single source of truth for discovered jobs. AI agents and workers
must consume this module (via the service layer) and never own business
logic. No AI, LangGraph, scraping, or browser automation lives here.
"""

from app.job.api import router
from app.job.enums import (
    EmploymentType,
    ExperienceLevel,
    JobStatus,
    RemoteType,
    SourcePlatform,
)
from app.job.models import Job
from app.job.service import JobService

__all__ = [
    "EmploymentType",
    "ExperienceLevel",
    "Job",
    "JobService",
    "JobStatus",
    "RemoteType",
    "SourcePlatform",
    "router",
]
