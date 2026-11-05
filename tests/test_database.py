import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import text
from app.core.database import get_engine, get_session_factory, get_session


def test_get_engine_creates_async_engine():
    engine = get_engine()
    assert isinstance(engine, AsyncEngine)


def test_session_factory_configuration():
    factory = get_session_factory()
    assert factory.kw.get("expire_on_commit") is False
    assert issubclass(factory.class_, AsyncSession)


@pytest.mark.asyncio
async def test_get_session_yields_session(monkeypatch, tmp_path):
    test_db_path = tmp_path / "test.db"
    test_url = f"sqlite+aiosqlite:///{test_db_path}"
    test_engine = create_async_engine(test_url, future=True)
    test_factory = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    monkeypatch.setattr("app.core.database.get_session_factory", lambda: test_factory)

    generator = get_session()
    session = await anext(generator)
    assert isinstance(session, AsyncSession)
    result = await session.execute(text("SELECT 1"))
    assert result.scalar() == 1
    with pytest.raises(StopAsyncIteration):
        await anext(generator)

    await test_engine.dispose()
