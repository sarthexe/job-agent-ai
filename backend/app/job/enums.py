"""Enumerations for the Job domain.

StrEnum members serialize to their (lowercase) string values, so they are
safe to store in the database, use in URLs, and return from the API.
"""

from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    """Lifecycle status of a job."""

    NEW = "new"
    MATCHED = "matched"
    SHORTLISTED = "shortlisted"
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class RemoteType(StrEnum):
    """Work arrangement of the position."""

    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class EmploymentType(StrEnum):
    """Employment arrangement of the position."""

    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    FREELANCE = "freelance"


class ExperienceLevel(StrEnum):
    """Required experience level of the position."""

    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    STAFF = "staff"
    LEAD = "lead"
    UNKNOWN = "unknown"


class SourcePlatform(StrEnum):
    """Platform where the job was discovered."""

    LINKEDIN = "linkedin"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WELLFOUND = "wellfound"
    YC = "yc"
    COMPANY_SITE = "company_site"
    OTHER = "other"
