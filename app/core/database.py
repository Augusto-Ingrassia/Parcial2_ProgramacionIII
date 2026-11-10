from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import get_settings


def crear_motor() -> AsyncEngine:
    """Motor nuevo y sin caché: lo crea y libera el lifespan de la app."""
    settings = get_settings()
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.SQL_ECHO,
        future=True,
    )


def crear_fabrica_sesiones(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@lru_cache
def get_engine() -> AsyncEngine:
    """Singleton para scripts fuera de la app (initial_data, auditoría)."""
    return crear_motor()


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Singleton para scripts fuera de la app (initial_data, auditoría)."""
    return crear_fabrica_sesiones(get_engine())


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    # La fábrica la crea el lifespan y vive en app.state; sin fallback global.
    async with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
