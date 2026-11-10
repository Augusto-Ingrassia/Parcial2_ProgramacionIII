from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import text
from app.core.database import (
    crear_fabrica_sesiones,
    crear_motor,
    get_engine,
    get_session,
    get_session_factory,
)


def test_get_engine_creates_async_engine():
    engine = get_engine()
    assert isinstance(engine, AsyncEngine)


def test_session_factory_configuration():
    factory = get_session_factory()
    assert factory.kw.get("expire_on_commit") is False
    assert issubclass(factory.class_, AsyncSession)


def test_crear_motor_devuelve_motor_nuevo_en_cada_llamada():
    primero, segundo = crear_motor(), crear_motor()
    assert isinstance(primero, AsyncEngine)
    assert isinstance(segundo, AsyncEngine)
    assert primero is not segundo


def test_crear_fabrica_sesiones_liga_el_motor_recibido(tmp_path):
    motor = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'f.db'}")
    otro = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'g.db'}")
    fabrica = crear_fabrica_sesiones(motor)
    assert fabrica.kw["bind"] is motor
    assert fabrica.kw["bind"] is not otro
    assert fabrica.kw.get("expire_on_commit") is False
    assert issubclass(fabrica.class_, AsyncSession)


def _request_con(fabrica):
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(session_factory=fabrica))
    )


@pytest_asyncio.fixture
async def fabrica_sqlite(tmp_path):
    motor = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}", future=True)
    yield crear_fabrica_sesiones(motor)
    await motor.dispose()


@pytest.mark.asyncio
async def test_get_session_yields_session(fabrica_sqlite):
    generator = get_session(_request_con(fabrica_sqlite))
    session = await anext(generator)
    assert isinstance(session, AsyncSession)
    result = await session.execute(text("SELECT 1"))
    assert result.scalar() == 1
    with pytest.raises(StopAsyncIteration):
        await anext(generator)


@pytest.mark.asyncio
async def test_get_session_no_usa_la_cache_global(monkeypatch, fabrica_sqlite):
    def prohibida():
        raise AssertionError("get_session no debe usar la fábrica global")

    monkeypatch.setattr("app.core.database.get_session_factory", prohibida)
    generator = get_session(_request_con(fabrica_sqlite))
    session = await anext(generator)
    assert (await session.execute(text("SELECT 1"))).scalar() == 1
    with pytest.raises(StopAsyncIteration):
        await anext(generator)


@pytest.mark.asyncio
async def test_get_session_dos_llamadas_dan_sesiones_distintas_de_la_misma_fabrica(
    fabrica_sqlite,
):
    request = _request_con(fabrica_sqlite)
    gen_a, gen_b = get_session(request), get_session(request)
    sesion_a, sesion_b = await anext(gen_a), await anext(gen_b)
    assert sesion_a is not sesion_b
    assert sesion_a.bind is sesion_b.bind is fabrica_sqlite.kw["bind"]
    for gen in (gen_a, gen_b):
        with pytest.raises(StopAsyncIteration):
            await anext(gen)
