import logging

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.core.database import get_session


@pytest.mark.asyncio
async def test_health_live_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"estado": "vivo"}


@pytest.mark.asyncio
async def test_health_ready_endpoint_success(tmp_path):
    test_db_path = tmp_path / "test_ready.db"
    test_url = f"sqlite+aiosqlite:///{test_db_path}"
    test_engine = create_async_engine(test_url, future=True)
    test_factory = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_session():
        async with test_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health/ready")
            assert response.status_code == 200
            assert response.json().get("estado") == "listo"
    finally:
        app.dependency_overrides.clear()
        await test_engine.dispose()


@pytest.mark.asyncio
async def test_health_ready_endpoint_failure():
    class FailingSession:
        async def execute(self, *args, **kwargs):
            raise ConnectionError("Database unreachable")

    async def override_failing_session():
        yield FailingSession()

    app.dependency_overrides[get_session] = override_failing_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            response = await client.get("/health/ready")
            assert response.status_code == 503
            assert "Base de datos no disponible" in response.json().get("detail", "")
    finally:
        app.dependency_overrides.clear()


URL_SECRETA = "postgresql+asyncpg://admin:S3cr3t-pw@db-host:5432/libreria_db"
MSG_FIJO = {"detail": "Base de datos no disponible"}


class _ResultadoInesperado:
    def scalar(self):
        return 2


class _SesionResultadoInesperado:
    async def execute(self, *args, **kwargs):
        return _ResultadoInesperado()


def _sesion_que_lanza(exc: Exception):
    class _Sesion:
        async def execute(self, *args, **kwargs):
            raise exc

    return _Sesion()


async def _get_ready_con_sesion(sesion):
    async def override():
        yield sesion

    app.dependency_overrides[get_session] = override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            return await client.get("/health/ready")
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [
        OSError(f"connect failed {URL_SECRETA}"),
        SQLAlchemyError(f"(asyncpg) no conecta a {URL_SECRETA}"),
    ],
)
async def test_health_ready_no_filtra_internos_de_la_base(exc, caplog):
    with caplog.at_level(logging.DEBUG):
        response = await _get_ready_con_sesion(_sesion_que_lanza(exc))

    assert response.status_code == 503
    assert response.json() == MSG_FIJO
    for prohibido in ("S3cr3t-pw", "db-host", "postgresql+asyncpg"):
        assert prohibido not in response.text
        assert prohibido not in caplog.text


@pytest.mark.asyncio
async def test_health_ready_respuesta_inesperada_usa_el_mismo_mensaje_fijo():
    response = await _get_ready_con_sesion(_SesionResultadoInesperado())

    assert response.status_code == 503
    assert response.json() == MSG_FIJO
