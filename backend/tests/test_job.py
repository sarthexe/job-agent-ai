"""Tests for the Job domain: enums, validators, schemas, repository, service, API."""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.job.enums import (
    EmploymentType,
    ExperienceLevel,
    JobStatus,
    RemoteType,
    SourcePlatform,
)
from app.job.models import Job
from app.job.repository import JobRepository
from app.job.schemas import JobCreate, JobFilterRequest, JobUpdate
from app.job.service import JobService
from app.job.validators import (
    STATUS_TRANSITIONS,
    validate_salary_range,
    validate_status_transition,
    validate_url,
)
from app.main import app
from app.shared.database import (
    Base,
    build_session_factory,
    get_db,
)
from app.shared.exceptions import (
    DomainValidationError,
    DuplicateError,
    InvalidStatusTransitionError,
    JobAlreadyAppliedError,
    NotFoundError,
)


def make_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Software Engineer",
        "company": "Acme Corp",
        "location": "Berlin",
        "remote_type": "remote",
        "employment_type": "full_time",
        "experience_level": "senior",
        "salary_min": 80_000,
        "salary_max": 120_000,
        "salary_currency": "USD",
        "application_url": f"https://acme.example/jobs/{uuid.uuid4().hex}",
        "source_platform": "greenhouse",
        "external_job_id": f"gh-{uuid.uuid4().hex[:8]}",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
async def test_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def factory(test_engine):
    return build_session_factory(test_engine)


@pytest.fixture
def client(factory):
    async def override_get_db():
        async with factory() as session:
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


async def create_job_via_service(
    factory, **overrides: object
) -> tuple[Job, JobService]:
    async with factory() as session:
        service = JobService(session)
        job = await service.create_job(JobCreate(**make_payload(**overrides)))
        return job, service


# --- enums -------------------------------------------------------------------


def test_enum_values_are_lowercase_strings() -> None:
    assert JobStatus.NEW == "new"
    assert JobStatus.INTERVIEW == "interview"
    assert RemoteType.REMOTE == "remote"
    assert EmploymentType.CONTRACT == "contract"
    assert ExperienceLevel.STAFF == "staff"
    assert SourcePlatform.COMPANY_SITE == "company_site"


# --- validators --------------------------------------------------------------


def test_salary_range_requires_both_values() -> None:
    with pytest.raises(DomainValidationError):
        validate_salary_range(50_000, None, "USD")


def test_salary_range_rejects_inverted_range() -> None:
    with pytest.raises(DomainValidationError):
        validate_salary_range(120_000, 80_000, "USD")


def test_salary_range_rejects_bad_currency() -> None:
    with pytest.raises(DomainValidationError):
        validate_salary_range(1, 2, "usd")


def test_url_rejects_non_http() -> None:
    with pytest.raises(DomainValidationError):
        validate_url("ftp://example.com")


def test_transitions_allow_forward_moves() -> None:
    validate_status_transition(JobStatus.NEW, JobStatus.APPLIED)
    validate_status_transition(JobStatus.APPLIED, JobStatus.INTERVIEW)
    validate_status_transition(JobStatus.INTERVIEW, JobStatus.OFFER)
    validate_status_transition(JobStatus.OFFER, JobStatus.REJECTED)


def test_transitions_reject_illegal_moves() -> None:
    with pytest.raises(InvalidStatusTransitionError):
        validate_status_transition(JobStatus.NEW, JobStatus.OFFER)
    with pytest.raises(InvalidStatusTransitionError):
        validate_status_transition(JobStatus.APPLIED, JobStatus.NEW)


def test_transition_table_covers_all_statuses() -> None:
    assert set(STATUS_TRANSITIONS) == set(JobStatus)


# --- schemas -----------------------------------------------------------------


def test_job_create_rejects_inverted_salary() -> None:
    with pytest.raises(DomainValidationError):
        JobCreate(**make_payload(salary_min=200_000, salary_max=100_000))


def test_job_create_rejects_missing_salary_pair() -> None:
    with pytest.raises(DomainValidationError):
        JobCreate(**make_payload(salary_min=100_000, salary_max=None))


def test_job_create_rejects_bad_url() -> None:
    with pytest.raises(DomainValidationError):
        JobCreate(**make_payload(application_url="not-a-url"))


def test_job_create_rejects_expiry_before_posting() -> None:
    with pytest.raises(DomainValidationError):
        JobCreate(
            **make_payload(
                posted_at=datetime(2026, 2, 1, tzinfo=UTC),
                expires_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )


# --- repository ---------------------------------------------------------------


async def test_repository_crud_and_soft_delete(factory) -> None:
    async with factory() as session:
        repo = JobRepository(session)
        job = Job(**make_payload())
        await repo.create(job)
        await session.commit()

        fetched = await repo.get(job.id)
        assert fetched is not None and fetched.title == job.title
        assert await repo.get(uuid.uuid4()) is None

        await repo.delete(job)
        await session.commit()
        assert await repo.get(job.id) is None
        assert await repo.get(job.id, include_deleted=True) is not None

        await repo.restore(job)
        await session.commit()
        assert await repo.get(job.id) is not None


async def test_repository_lookup_by_url_and_external_id(factory) -> None:
    payload = make_payload()
    async with factory() as session:
        repo = JobRepository(session)
        job = Job(**payload)
        await repo.create(job)
        await session.commit()

        by_url = await repo.get_by_url(payload["application_url"])
        assert by_url is not None and by_url.id == job.id

        by_external = await repo.get_by_external_id(
            SourcePlatform.GREENHOUSE, payload["external_job_id"]
        )
        assert by_external is not None and by_external.id == job.id


async def test_repository_list_pagination_and_sorting(factory) -> None:
    async with factory() as session:
        repo = JobRepository(session)
        for index in range(5):
            await repo.create(Job(**make_payload(title=f"Job {index}")))
        await session.commit()

        items, total = await repo.list(
            JobFilterRequest(),
            page=1,
            page_size=2,
            sort_by="title",
            sort_order="asc",
        )
        assert total == 5
        assert len(items) == 2
        assert items[0].title == "Job 0"
        assert items[1].title == "Job 1"


async def test_repository_bulk_operations(factory) -> None:
    async with factory() as session:
        repo = JobRepository(session)
        created = await repo.bulk_create([Job(**make_payload()) for _ in range(3)])
        await session.commit()
        assert len(created) == 3
        assert all(job.id is not None for job in created)

        for job in created:
            job.title = f"Renamed {job.title}"
        updated = await repo.bulk_update(created)
        await session.commit()
        assert all(job.title.startswith("Renamed") for job in updated)

        affected = await repo.bulk_archive([job.id for job in created])
        await session.commit()
        assert affected == 3
        async with factory() as session:
            repo = JobRepository(session)
            archived = await repo.list(
                JobFilterRequest(),
                page=1,
                page_size=50,
                sort_by="created_at",
                sort_order="desc",
            )
            assert archived[1] == 3
            assert all(job.status == JobStatus.ARCHIVED for job in archived[0])


async def test_repository_upsert_creates_and_updates(factory) -> None:
    payload = make_payload()
    async with factory() as session:
        repo = JobRepository(session)
        job, created = await repo.upsert(
            SourcePlatform.GREENHOUSE,
            payload["external_job_id"],
            {
                k: v
                for k, v in payload.items()
                if k not in {"source_platform", "external_job_id"}
            },
        )
        await session.commit()
        assert created is True

        job, created = await repo.upsert(
            SourcePlatform.GREENHOUSE,
            payload["external_job_id"],
            {"title": "Updated Title"},
        )
        await session.commit()
        assert created is False
        assert job.title == "Updated Title"


# --- service -----------------------------------------------------------------


async def test_service_create_rejects_duplicate_url(factory) -> None:
    payload = make_payload()
    async with factory() as session:
        service = JobService(session)
        await service.create_job(JobCreate(**payload))
        with pytest.raises(DuplicateError):
            await service.create_job(JobCreate(**payload))


async def test_service_create_rejects_duplicate_external_id(factory) -> None:
    payload = make_payload()
    async with factory() as session:
        service = JobService(session)
        await service.create_job(JobCreate(**payload))
        with pytest.raises(DuplicateError):
            await service.create_job(
                JobCreate(
                    **make_payload(
                        application_url=f"https://other.example/{uuid.uuid4().hex}",
                        external_job_id=payload["external_job_id"],
                    )
                )
            )


async def test_service_update_rejects_invalid_transition(factory) -> None:
    job, _ = await create_job_via_service(factory)
    async with factory() as session:
        service = JobService(session)
        with pytest.raises(InvalidStatusTransitionError):
            await service.update_job(job.id, JobUpdate(status=JobStatus.OFFER))


async def test_service_applied_once_semantics(factory) -> None:
    job, _ = await create_job_via_service(factory)
    async with factory() as session:
        service = JobService(session)
        applied = await service.mark_applied(job.id)
        assert applied.status == JobStatus.APPLIED
        assert applied.applied is True
        with pytest.raises(JobAlreadyAppliedError):
            await service.mark_applied(job.id)


async def test_service_interview_offer_reject_chain(factory) -> None:
    job, _ = await create_job_via_service(factory)
    async with factory() as session:
        service = JobService(session)
        job = await service.mark_applied(job.id)
        job = await service.mark_interview(job.id)
        assert job.status == JobStatus.INTERVIEW
        job = await service.mark_offer(job.id)
        assert job.status == JobStatus.OFFER
        job = await service.mark_rejected(job.id)
        assert job.status == JobStatus.REJECTED


async def test_service_archive_and_restore(factory) -> None:
    job, _ = await create_job_via_service(factory)
    async with factory() as session:
        service = JobService(session)
        archived = await service.archive_job(job.id)
        assert archived.status == JobStatus.ARCHIVED
        assert archived.archived is True
        restored = await service.restore_job(job.id)
        assert restored.deleted_at is None
        assert restored.archived is False


async def test_service_calculate_match_placeholder(factory) -> None:
    job, _ = await create_job_via_service(factory)
    async with factory() as session:
        service = JobService(session)
        score = await service.calculate_match_placeholder(job.id)
        assert score == 0.0


async def test_service_get_missing_job_raises(factory) -> None:
    async with factory() as session:
        service = JobService(session)
        with pytest.raises(NotFoundError):
            await service.get_job(uuid.uuid4())


async def test_service_upsert_updates_existing(factory) -> None:
    payload = make_payload()
    async with factory() as session:
        service = JobService(session)
        created = await service.upsert_job(JobCreate(**payload))
        updated = await service.upsert_job(JobCreate(**payload))
        assert created.id == updated.id


# --- API ---------------------------------------------------------------------


def test_api_create_and_get_job(client) -> None:
    response = client.post("/api/v1/jobs/", json=make_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Software Engineer"
    assert body["status"] == "new"
    assert body["remote_type"] == "remote"
    assert body["source_platform"] == "greenhouse"
    assert body["salary_currency"] == "USD"

    fetched = client.get(f"/api/v1/jobs/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


def test_api_create_duplicate_returns_409(client) -> None:
    payload = make_payload()
    assert client.post("/api/v1/jobs/", json=payload).status_code == 201
    response = client.post("/api/v1/jobs/", json=payload)
    assert response.status_code == 409
    assert response.json()["code"] == "duplicate"


def test_api_create_invalid_salary_returns_422(client) -> None:
    response = client.post(
        "/api/v1/jobs/",
        json=make_payload(salary_min=200_000, salary_max=100_000),
    )
    assert response.status_code == 422


def test_api_get_missing_job_returns_404(client) -> None:
    response = client.get(f"/api/v1/jobs/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_api_list_pagination(client) -> None:
    for index in range(5):
        client.post("/api/v1/jobs/", json=make_payload(title=f"Engineer {index}"))

    response = client.get("/api/v1/jobs/?page=1&page_size=2")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["pagination"]["total"] == 5
    assert body["pagination"]["pages"] == 3


def test_api_list_filters_by_company_and_status(client) -> None:
    client.post("/api/v1/jobs/", json=make_payload(company="Acme Corp"))
    client.post("/api/v1/jobs/", json=make_payload(company="Globex"))
    client.post(
        "/api/v1/jobs/",
        json=make_payload(
            company="Acme Corp", external_job_id="acme-2", status="matched"
        ),
    )

    by_company = client.get("/api/v1/jobs/?company=Acme")
    assert by_company.json()["pagination"]["total"] == 2

    by_status = client.get("/api/v1/jobs/?status=matched")
    assert by_status.json()["pagination"]["total"] == 1


def test_api_list_filters_salary_range(client) -> None:
    client.post(
        "/api/v1/jobs/", json=make_payload(salary_min=50_000, salary_max=80_000)
    )
    client.post(
        "/api/v1/jobs/", json=make_payload(salary_min=90_000, salary_max=130_000)
    )

    low = client.get("/api/v1/jobs/?salary_max=85000")
    assert low.json()["pagination"]["total"] == 1
    high = client.get("/api/v1/jobs/?salary_min=85000")
    assert high.json()["pagination"]["total"] == 1


def test_api_search_payload(client) -> None:
    client.post("/api/v1/jobs/", json=make_payload(company="Acme Corp"))
    client.post("/api/v1/jobs/", json=make_payload(company="Globex"))

    response = client.post(
        "/api/v1/jobs/search",
        json={"query": "acme", "page": 1, "page_size": 20},
    )
    assert response.status_code == 200
    assert response.json()["pagination"]["total"] == 1
    assert response.json()["items"][0]["company"] == "Acme Corp"


def test_api_patch_updates_and_enforces_transitions(client) -> None:
    created = client.post("/api/v1/jobs/", json=make_payload()).json()

    updated = client.patch(
        f"/api/v1/jobs/{created['id']}",
        json={"title": "Senior Software Engineer", "match_score": 0.8},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Senior Software Engineer"
    assert updated.json()["match_score"] == 0.8

    rejected = client.patch(f"/api/v1/jobs/{created['id']}", json={"status": "offer"})
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "invalid_status_transition"


def test_api_delete_soft_deletes(client) -> None:
    created = client.post("/api/v1/jobs/", json=make_payload()).json()

    deleted = client.delete(f"/api/v1/jobs/{created['id']}")
    assert deleted.status_code == 204

    assert client.get(f"/api/v1/jobs/{created['id']}").status_code == 404


def test_api_bulk_create(client) -> None:
    response = client.post(
        "/api/v1/jobs/bulk",
        json=[make_payload(), make_payload()],
    )
    assert response.status_code == 201
    assert len(response.json()) == 2


def test_api_status_action_endpoints(client) -> None:
    created = client.post("/api/v1/jobs/", json=make_payload()).json()
    job_id = created["id"]

    assert client.post(f"/api/v1/jobs/{job_id}/apply").json()["status"] == "applied"
    assert (
        client.post(f"/api/v1/jobs/{job_id}/interview").json()["status"] == "interview"
    )
    assert client.post(f"/api/v1/jobs/{job_id}/offer").json()["status"] == "offer"
    assert client.post(f"/api/v1/jobs/{job_id}/reject").json()["status"] == "rejected"

    again = client.post(f"/api/v1/jobs/{job_id}/offer")
    assert again.status_code == 409


def test_api_archive_restore_cycle(client) -> None:
    created = client.post("/api/v1/jobs/", json=make_payload()).json()
    job_id = created["id"]

    archived = client.post(f"/api/v1/jobs/{job_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert archived.json()["archived"] is True

    client.delete(f"/api/v1/jobs/{job_id}")
    assert client.get(f"/api/v1/jobs/{job_id}").status_code == 404

    restored = client.post(f"/api/v1/jobs/{job_id}/restore")
    assert restored.status_code == 200
    assert restored.json()["deleted_at"] is None
    assert client.get(f"/api/v1/jobs/{job_id}").status_code == 200
