import re

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.autores.models import Autor
from app.modules.clientes.models import Cliente
from app.modules.editoriales.models import Editorial
from app.modules.generos.models import Genero
from app.modules.libros.models import Libro
from app.modules.ventas.models import Venta
from scripts import auditar_consultas
from scripts.auditar_consultas import auditar

TABLAS = [Libro, Venta, Cliente, Editorial, Genero, Autor]


async def _cantidades(db_engine) -> list[int]:
    factory = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        return [
            (await session.execute(select(func.count()).select_from(t))).scalar_one()
            for t in TABLAS
        ]


def _secciones(texto: str) -> dict[int, str]:
    """Parte el log en {limit: contenido} según los marcadores `=== GET ...?limit=N ===`."""
    partes = re.split(r"^=== GET \S+\?limit=(\d+) ===$", texto, flags=re.MULTILINE)
    return {int(partes[i]): partes[i + 1] for i in range(1, len(partes), 2)}


@pytest.mark.asyncio
async def test_auditar_escribe_los_logs_y_devuelve_los_conteos(db_engine, tmp_path):
    conteos = await auditar(db_engine, tmp_path)

    assert conteos == {
        "libros": {1: 1, 10: 1, 50: 1},
        "ventas": {1: 2, 10: 2, 50: 2},
    }
    for nombre, esperado in [("queries_libros.log", 1), ("queries_ventas.log", 2)]:
        secciones = _secciones((tmp_path / nombre).read_text(encoding="utf-8"))
        assert sorted(secciones) == [1, 10, 50]
        for contenido in secciones.values():
            assert f"--- sentencias: {esperado} ---" in contenido
            assert "SELECT" in contenido


@pytest.mark.asyncio
async def test_el_log_muestra_join_en_la_principal_e_in_en_la_secundaria(db_engine, tmp_path):
    await auditar(db_engine, tmp_path)

    libros = (tmp_path / "queries_libros.log").read_text(encoding="utf-8")
    ventas = (tmp_path / "queries_ventas.log").read_text(encoding="utf-8")

    assert "JOIN editorial" in libros and "JOIN genero" in libros
    assert "JOIN cliente" in ventas
    assert re.search(r"renglon_venta\.venta_id IN \(", ventas)


@pytest.mark.asyncio
async def test_auditar_no_deja_datos_en_la_base(db_engine, tmp_path):
    antes = await _cantidades(db_engine)

    await auditar(db_engine, tmp_path)

    assert await _cantidades(db_engine) == antes == [0] * len(TABLAS)


@pytest.mark.asyncio
async def test_auditar_es_repetible(db_engine, tmp_path):
    primera = await auditar(db_engine, tmp_path / "a")
    segunda = await auditar(db_engine, tmp_path / "b")

    assert primera == segunda


@pytest.mark.asyncio
async def test_main_genera_ambos_archivos_con_encabezado(tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.core.database import get_engine, get_session_factory

    destino = tmp_path / "salida"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'aud.db'}")
    for f in (get_settings, get_engine, get_session_factory):
        f.cache_clear()
    try:
        assert await auditar_consultas.main(["--salida", str(destino)]) == 0
    finally:
        for f in (get_settings, get_engine, get_session_factory):
            f.cache_clear()

    for nombre in ("queries_libros.log", "queries_ventas.log"):
        texto = (destino / nombre).read_text(encoding="utf-8")
        assert texto.startswith("# Comando: python -m scripts.auditar_consultas")
        assert "# Motor: sqlite" in texto
        assert "# Fecha:" in texto
        assert "aud.db" not in texto  # sin rutas ni credenciales de la conexión
