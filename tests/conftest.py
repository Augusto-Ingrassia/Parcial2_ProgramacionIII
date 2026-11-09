import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.core.database import get_session
from app.main import app  # importa también los modelos registrados en metadata


def _activar_foreign_keys(dbapi_connection, _record):
    # SQLite no aplica las claves foráneas salvo que se lo pida en cada conexión.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest_asyncio.fixture
async def db_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}", future=True)
    event.listen(engine.sync_engine, "connect", _activar_foreign_keys)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def client(db_engine):
    factory = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def contar_consultas(db_engine):
    """Devuelve una lista que acumula cada sentencia SQL emitida por el motor."""
    sentencias: list[str] = []

    def _registrar(conn, cursor, statement, *args):
        sentencias.append(statement)

    event.listen(db_engine.sync_engine, "before_cursor_execute", _registrar)
    yield sentencias
    event.remove(db_engine.sync_engine, "before_cursor_execute", _registrar)
