import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.pagination import PaginationDep


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/items")
    async def items(p: PaginationDep) -> dict[str, int]:
        return {"limit": p.limit, "offset": p.offset}

    return app


@pytest.mark.asyncio
async def test_pagination_defaults():
    async with AsyncClient(transport=ASGITransport(app=_build_app()), base_url="http://t") as c:
        r = await c.get("/items")
    assert r.status_code == 200
    assert r.json() == {"limit": 20, "offset": 0}


@pytest.mark.asyncio
async def test_pagination_valid_values():
    async with AsyncClient(transport=ASGITransport(app=_build_app()), base_url="http://t") as c:
        r = await c.get("/items?limit=100&offset=5")
    assert r.status_code == 200
    assert r.json() == {"limit": 100, "offset": 5}


@pytest.mark.asyncio
@pytest.mark.parametrize("qs", ["limit=0", "limit=101", "offset=-1"])
async def test_pagination_out_of_range(qs):
    async with AsyncClient(transport=ASGITransport(app=_build_app()), base_url="http://t") as c:
        r = await c.get(f"/items?{qs}")
    assert r.status_code == 422
