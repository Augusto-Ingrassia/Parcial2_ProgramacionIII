from collections.abc import AsyncGenerator
from functools import lru_cache
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.SQL_ECHO,
        future=True,
    )


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = get_engine()
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session
