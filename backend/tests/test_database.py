"""Tests for the shared async database infrastructure (engine, session, base, types, mixins)."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import String, Uuid, func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm.exc import StaleDataError

from app.shared.config import settings
from app.shared.database import (
    AuditMixin,
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
    VersionMixin,
    build_engine,
    build_session_factory,
    close_engine,
    configure_session_factory,
    get_db,
    get_engine,
    session_scope,
)
from app.shared.database.types import UTCDateTime


class FullModel(
    UUIDMixin,
    TimestampMixin,
    SoftDeleteMixin,
    AuditMixin,
    VersionMixin,
    Base,
):
    """Model exercising every mixin, used only inside tests."""

    __tablename__ = "full_models"

    name: Mapped[str] = mapped_column(String(100), nullable=False)


class AnnotatedModel(Base):
    """Model relying on Base.type_annotation_map for column types."""

    __tablename__ = "annotated_models"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    created: Mapped[datetime] = mapped_column()
    name: Mapped[str] = mapped_column(String(50))


@pytest.fixture
async def test_engine(tmp_path):
    # File-based sqlite: separate connections per session (the in-memory
    # StaticPool variant cannot serve two concurrent sessions).
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


def _factory(test_engine):
    return build_session_factory(test_engine)


async def _count(session: AsyncSession) -> int:
    return (
        await session.execute(select(func.count()).select_from(FullModel))
    ).scalar_one()


# --- engine -----------------------------------------------------------------


def test_build_engine_uses_centralized_settings() -> None:
    engine = build_engine(echo=True)

    assert engine.url.render_as_string(hide_password=False) == settings.database.url
    assert engine.echo is True


async def test_engine_singleton_and_close() -> None:
    first = get_engine()
    assert get_engine() is first

    await close_engine()

    rebuilt = get_engine()
    assert rebuilt is not first
    await close_engine()


# --- base and types ---------------------------------------------------------


def test_type_annotation_map_resolves_annotation_types() -> None:
    assert isinstance(AnnotatedModel.__table__.c.id.type, Uuid)
    assert isinstance(AnnotatedModel.__table__.c.created.type, UTCDateTime)


def test_naming_convention_is_configured() -> None:
    assert Base.metadata.naming_convention["pk"] == "pk_%(table_name)s"
    assert Base.metadata.naming_convention["fk"].startswith("fk_%(table_name)s")


def test_utcdatetime_normalizes_naive_values_to_utc() -> None:
    column_type = UTCDateTime()

    naive = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None)
    bound = column_type.process_bind_param(naive, "postgresql")
    assert bound.tzinfo == UTC
    assert bound.hour == 12

    aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert column_type.process_bind_param(aware, "postgresql").tzinfo == UTC

    assert column_type.process_bind_param(None, "postgresql") is None

    # SQLite-style naive result values are stamped with UTC on load.
    naive_result = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None)
    assert column_type.process_result_value(naive_result, "sqlite").tzinfo == UTC
    assert column_type.process_result_value(None, "sqlite") is None


# --- mixins -----------------------------------------------------------------


async def test_full_model_round_trip_with_all_mixins(test_engine) -> None:
    async with _factory(test_engine)() as session:
        model = FullModel(name="alpha", created_by=uuid.uuid4())
        session.add(model)
        await session.commit()
        await session.refresh(model)

    assert isinstance(model.id, uuid.UUID)
    assert model.created_at is not None
    assert model.updated_at is not None
    assert model.version == 1
    assert model.is_deleted is False
    assert model.deleted_at is None
    assert model.created_by is not None
    assert model.updated_by is None


async def test_version_increments_on_update(test_engine) -> None:
    async with _factory(test_engine)() as session:
        model = FullModel(name="v1")
        session.add(model)
        await session.commit()

        model.name = "v2"
        await session.commit()

        assert model.version == 2


async def test_concurrent_stale_update_raises(test_engine) -> None:
    factory = _factory(test_engine)
    async with factory() as session:
        session.add(FullModel(name="seeded"))
        await session.commit()

    async with factory() as first, factory() as second:
        stale = (await second.execute(select(FullModel))).scalar_one()
        current = (await first.execute(select(FullModel))).scalar_one()

        current.name = "updated-first"
        await first.commit()

        stale.name = "stale-write"
        with pytest.raises(StaleDataError):
            await second.commit()


async def test_soft_delete_and_restore(test_engine) -> None:
    async with _factory(test_engine)() as session:
        model = FullModel(name="doomed")
        session.add(model)
        await session.commit()
        await session.refresh(model)

        model.soft_delete()
        await session.commit()
        await session.refresh(model)

        assert model.is_deleted is True
        assert model.deleted_at is not None
        assert model.deleted_at.tzinfo is not None

        model.restore()
        await session.commit()
        await session.refresh(model)

        assert model.is_deleted is False
        assert model.deleted_at is None


# --- session management ------------------------------------------------------


async def test_session_scope_commits_on_success(test_engine) -> None:
    configure_session_factory(_factory(test_engine))

    async with session_scope() as session:
        session.add(FullModel(name="scoped"))

    async with _factory(test_engine)() as session:
        assert await _count(session) == 1


async def test_session_scope_rolls_back_on_error(test_engine) -> None:
    configure_session_factory(_factory(test_engine))

    with pytest.raises(RuntimeError, match="boom"):
        async with session_scope() as session:
            session.add(FullModel(name="doomed"))
            raise RuntimeError("boom")

    async with _factory(test_engine)() as session:
        assert await _count(session) == 0


async def test_get_db_yields_session_and_rolls_back(test_engine) -> None:
    configure_session_factory(_factory(test_engine))

    generator = get_db()
    session = await anext(generator)
    assert isinstance(session, AsyncSession)

    session.add(FullModel(name="via-dependency"))
    with pytest.raises(RuntimeError, match="fail"):
        await generator.athrow(RuntimeError("fail"))

    async with _factory(test_engine)() as session:
        assert await _count(session) == 0


def test_get_db_as_fastapi_dependency(test_engine) -> None:
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    configure_session_factory(_factory(test_engine))

    app = FastAPI()

    @app.get("/count")
    async def count(db: AsyncSession = Depends(get_db)) -> dict[str, int]:  # noqa: B008
        return {"count": await _count(db)}

    response = TestClient(app).get("/count")

    assert response.status_code == 200
    assert response.json() == {"count": 0}
