import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import register_exception_handlers


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom():
        raise IntegrityError(
            "INSERT INTO x ...",
            {},
            Exception('duplicate key value violates unique constraint "x_key"'),
        )

    @app.get("/ok")
    async def ok():
        return {"ok": True}

    return app


@pytest.mark.asyncio
async def test_integrity_error_becomes_409_without_internals():
    async with AsyncClient(transport=ASGITransport(app=_build_app()), base_url="http://t") as c:
        r = await c.get("/boom")
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail
    for forbidden in ("duplicate key", "constraint", "x_key", "IntegrityError", "INSERT"):
        assert forbidden not in detail


@pytest.mark.asyncio
async def test_non_failing_endpoint_unaffected():
    async with AsyncClient(transport=ASGITransport(app=_build_app()), base_url="http://t") as c:
        r = await c.get("/ok")
    assert r.status_code == 200
