import pytest
from httpx import ASGITransport, AsyncClient
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
