from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import initial_data
from app.initial_data import ResumenSeed, sembrar
from app.modules.autores.models import Autor
from app.modules.clientes.models import Cliente, PerfilCliente
from app.modules.editoriales.models import Editorial
from app.modules.generos.models import Genero
from app.modules.libros.models import Libro, LibroAutor

ESPERADO = ResumenSeed(
    editoriales=3, generos=4, autores=5, libros=6, autorias=10, clientes=2, perfiles=2
)
VACIO = ResumenSeed()
TABLAS = [Editorial, Genero, Autor, Libro, LibroAutor, Cliente, PerfilCliente]


def _factory(db_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)


async def _sembrar(db_engine) -> ResumenSeed:
    async with _factory(db_engine)() as session:
        return await sembrar(session)


async def _cantidades(db_engine) -> list[int]:
    async with _factory(db_engine)() as session:
        return [
            (await session.execute(select(func.count()).select_from(t))).scalar_one()
            for t in TABLAS
        ]


# --- 3.1 contenido ------------------------------------------------------------


@pytest.mark.asyncio
async def test_sembrar_sobre_base_vacia_crea_el_conjunto_completo(db_engine):
    resumen = await _sembrar(db_engine)

    assert resumen == ESPERADO
    assert await _cantidades(db_engine) == [3, 4, 5, 6, 10, 2, 2]


@pytest.mark.asyncio
async def test_listados_de_la_api_reflejan_las_cantidades(client, db_engine):
    await _sembrar(db_engine)

    for ruta, cantidad in [
        ("/editoriales/", 3),
        ("/generos/", 4),
        ("/autores/", 5),
        ("/libros/", 6),
        ("/clientes/", 2),
    ]:
        respuesta = await client.get(ruta)
        assert len(respuesta.json()) == cantidad, ruta
    clientes = (await client.get("/clientes/")).json()
    assert all(isinstance(c["perfil"], dict) for c in clientes)


# --- 3.2 roles, multiplicidad, opcionales, Decimal -------------------------------


@pytest.mark.asyncio
async def test_autorias_con_roles_multiples_autores_y_libro_sin_genero(client, db_engine):
    await _sembrar(db_engine)
    ids = [lb["id"] for lb in (await client.get("/libros/")).json()]
    detalles = [(await client.get(f"/libros/{i}")).json() for i in ids]

    assert all(len(d["autores"]) >= 1 for d in detalles)
    assert max(len(d["autores"]) for d in detalles) >= 2
    roles = {a["rol"] for d in detalles for a in d["autores"]}
    assert {"autor", "coautor", "traductor"} <= roles
    assert sum(1 for d in detalles if d["genero"] is None) == 1
    precios = {d["titulo"]: Decimal(str(d["precio"])) for d in detalles}
    assert precios["Rayuela"] == Decimal("25000.00")
    assert precios["Ficciones"] == Decimal("18000.00")
    assert all(d["stock"] > 0 for d in detalles)


# --- 3.3 idempotencia --------------------------------------------------------------


@pytest.mark.asyncio
async def test_segunda_ejecucion_no_crea_nada(db_engine):
    await _sembrar(db_engine)
    antes = await _cantidades(db_engine)

    segundo = await _sembrar(db_engine)

    assert segundo == VACIO
    assert await _cantidades(db_engine) == antes


# --- 3.4 carga parcial previa ------------------------------------------------------


@pytest.mark.asyncio
async def test_reutiliza_la_editorial_creada_por_la_api(client, db_engine):
    previa = await client.post("/editoriales/", json={"nombre": "Sudamericana", "pais": "Chile"})
    assert previa.status_code == 201

    resumen = await _sembrar(db_engine)

    assert resumen.editoriales == 2
    assert resumen.libros == 6
    async with _factory(db_engine)() as session:
        nombres = (await session.execute(select(Editorial.nombre))).scalars().all()
    assert sorted(nombres) == ["Anagrama", "Emecé", "Sudamericana"]


@pytest.mark.asyncio
async def test_reutiliza_un_libro_y_un_cliente_existentes(db_engine):
    await _sembrar(db_engine)
    async with _factory(db_engine)() as session:
        await session.execute(LibroAutor.__table__.delete())
        await session.execute(PerfilCliente.__table__.delete())
        await session.execute(Libro.__table__.delete().where(Libro.isbn == "978-950-00-0001-1"))
        await session.execute(Cliente.__table__.delete().where(Cliente.email == "ana@example.com"))
        await session.commit()

    resumen = await _sembrar(db_engine)

    assert resumen == ResumenSeed(libros=1, autorias=10, clientes=1, perfiles=2)
    assert await _cantidades(db_engine) == [3, 4, 5, 6, 10, 2, 2]


# --- 3.5 atomicidad ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_error_a_mitad_no_deja_filas(db_engine, monkeypatch):
    original = initial_data._obtener_o_crear

    async def _falla_en_clientes(session, modelo, clave, valores):
        if modelo is Cliente:
            raise RuntimeError("fallo simulado")
        return await original(session, modelo, clave, valores)

    monkeypatch.setattr(initial_data, "_obtener_o_crear", _falla_en_clientes)

    with pytest.raises(RuntimeError):
        await _sembrar(db_engine)

    assert await _cantidades(db_engine) == [0] * len(TABLAS)


# --- 3.6 aptos para vender -------------------------------------------------------------


@pytest.mark.asyncio
async def test_se_puede_vender_con_datos_sembrados(client, db_engine):
    await _sembrar(db_engine)
    cliente = (await client.get("/clientes/")).json()[0]
    libros = (await client.get("/libros/")).json()
    rayuela = next(lb for lb in libros if lb["titulo"] == "Rayuela")

    respuesta = await client.post(
        "/ventas/",
        json={"cliente_id": cliente["id"], "renglones": [{"libro_id": rayuela["id"], "cantidad": 2}]},
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert Decimal(str(cuerpo["renglones"][0]["precio_unitario"])) == Decimal("25000.00")
    assert Decimal(str(cuerpo["total"])) == Decimal("50000.00")


# --- 3.7 main() --------------------------------------------------------------------------


@pytest.fixture
def entorno_limpio(monkeypatch):
    from app.core.config import get_settings
    from app.core.database import get_engine, get_session_factory

    def limpiar():
        get_settings.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()

    limpiar()
    yield monkeypatch
    limpiar()


@pytest.mark.asyncio
async def test_main_crea_tablas_siembra_y_es_idempotente(tmp_path, entorno_limpio, capsys):
    from app.core.config import get_settings
    from app.core.database import get_engine, get_session_factory

    entorno_limpio.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'seed.db'}")

    assert await initial_data.main() == 0
    primera = capsys.readouterr().out
    assert "editoriales: 3" in primera and "libros: 6" in primera

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    assert await initial_data.main() == 0
    segunda = capsys.readouterr().out
    assert "editoriales: 0" in segunda and "libros: 0" in segunda


@pytest.mark.asyncio
async def test_main_con_base_inaccesible_devuelve_1_sin_filtrar_la_url(
    tmp_path, entorno_limpio, capsys
):
    url = f"sqlite+aiosqlite:///{tmp_path / 'no_existe' / 'seed.db'}"
    entorno_limpio.setenv("DATABASE_URL", url)

    assert await initial_data.main() == 1

    capturado = capsys.readouterr()
    assert capturado.err.strip() != ""
    assert "no_existe" not in capturado.err
    assert "Traceback" not in capturado.err
