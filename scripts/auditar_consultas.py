"""Genera la evidencia de consultas SQL (`evidencia/queries_*.log`).

Uso: `python -m scripts.auditar_consultas [--salida evidencia]`

Inserta un volumen de datos dentro de una transacción externa, lista 1, 10 y 50
libros y ventas a través de la API real, registra las sentencias que emite el
motor y revierte la transacción: la base queda como estaba.
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlmodel import SQLModel

from app.core.config import get_settings
from app.core.database import get_engine, get_session, get_session_factory
from app.main import app
from app.modules.clientes.models import Cliente
from app.modules.editoriales.models import Editorial
from app.modules.generos.models import Genero
from app.modules.libros.models import Libro
from app.modules.ventas.models import RenglonVenta, Venta

TAMANIOS = (1, 10, 50)
VOLUMEN = max(TAMANIOS)
PRECIO = Decimal("10.50")
LOGGER_SQL = "sqlalchemy.engine.Engine"
COMANDO = "python -m scripts.auditar_consultas"


async def _insertar_volumen(session: AsyncSession) -> None:
    """50 libros y 50 ventas con 1 o 2 renglones; sólo `flush` (la transacción es externa)."""
    editorial = Editorial(nombre="Editorial Auditoria", pais="Argentina")
    genero = Genero(nombre="Genero Auditoria")
    cliente = Cliente(nombre="Cliente Auditoria", email="auditoria@example.com")
    session.add_all([editorial, genero, cliente])
    await session.flush()
    libros = [
        Libro(
            isbn=f"978-0-99-{i:06d}-0",
            titulo=f"Libro {i}",
            precio=PRECIO,
            stock=100,
            editorial_id=editorial.id,
            genero_id=genero.id,
        )
        for i in range(VOLUMEN)
    ]
    session.add_all(libros)
    await session.flush()
    for i in range(VOLUMEN):
        renglones = 1 + i % 2
        venta = Venta(cliente_id=cliente.id, total=PRECIO * renglones)
        session.add(venta)
        await session.flush()
        session.add_all(
            RenglonVenta(venta_id=venta.id, libro_id=lb.id, cantidad=1, precio_unitario=PRECIO)
            for lb in libros[:renglones]
        )
    await session.flush()


async def auditar(
    engine: AsyncEngine, destino: Path, encabezado: str = ""
) -> dict[str, dict[int, int]]:
    """Escribe `queries_libros.log` y `queries_ventas.log` en `destino`.

    Devuelve la cantidad de sentencias por recurso y tamaño de página.
    """
    destino.mkdir(parents=True, exist_ok=True)
    sentencias: list[str] = []

    def _contar(conn, cursor, statement, *args):
        sentencias.append(statement)

    logger = logging.getLogger(LOGGER_SQL)
    nivel_previo = logger.level
    logger.setLevel(logging.INFO)  # la conexión toma el nivel al abrirse
    conteos: dict[str, dict[int, int]] = {"libros": {}, "ventas": {}}
    try:
        async with engine.connect() as conn:
            transaccion = await conn.begin()
            try:
                async with AsyncSession(bind=conn, expire_on_commit=False) as sesion:
                    await _insertar_volumen(sesion)

                async def _sesion_auditoria():
                    async with AsyncSession(bind=conn, expire_on_commit=False) as s:
                        yield s

                app.dependency_overrides[get_session] = _sesion_auditoria
                event.listen(engine.sync_engine, "before_cursor_execute", _contar)
                try:
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as http:
                        for recurso in ("libros", "ventas"):
                            ruta = destino / f"queries_{recurso}.log"
                            ruta.write_text(
                                (encabezado + "\n" if encabezado else ""), encoding="utf-8"
                            )
                            for n in TAMANIOS:
                                conteos[recurso][n] = await _medir(
                                    http, logger, ruta, recurso, n, sentencias
                                )
                finally:
                    event.remove(engine.sync_engine, "before_cursor_execute", _contar)
                    app.dependency_overrides.pop(get_session, None)
            finally:
                await transaccion.rollback()
    finally:
        logger.setLevel(nivel_previo)
    return conteos


async def _medir(
    http: AsyncClient,
    logger: logging.Logger,
    ruta: Path,
    recurso: str,
    n: int,
    sentencias: list[str],
) -> int:
    url = f"/{recurso}/?limit={n}"
    with ruta.open("a", encoding="utf-8") as f:
        f.write(f"=== GET {url} ===\n")
    handler = logging.FileHandler(ruta, mode="a", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    sentencias.clear()
    try:
        respuesta = await http.get(url)
    finally:
        logger.removeHandler(handler)
        handler.close()
    if respuesta.status_code != 200 or len(respuesta.json()) != n:
        raise RuntimeError(f"Respuesta inesperada en {url}: {respuesta.status_code}")
    cantidad = len(sentencias)
    with ruta.open("a", encoding="utf-8") as f:
        f.write(f"--- sentencias: {cantidad} ---\n\n")
    return cantidad


def _encabezado(engine: AsyncEngine, salida: Path) -> str:
    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"# Comando: {COMANDO} --salida {salida.as_posix()}\n"
        f"# Motor: {engine.dialect.name} ({engine.dialect.driver})\n"
        f"# Fecha: {fecha}\n"
        "# SQL_ECHO=true; datos de volumen insertados en una transacción que se revierte.\n"
    )


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=COMANDO, description=__doc__.splitlines()[0])
    parser.add_argument("--salida", type=Path, default=Path("evidencia"))
    args = parser.parse_args(argv)

    eco_previo = os.environ.get("SQL_ECHO")
    os.environ["SQL_ECHO"] = "true"
    for cache in (get_settings, get_engine, get_session_factory):
        cache.cache_clear()
    engine = get_engine()
    try:
        async with engine.begin() as conn:  # igual que el lifespan de la app: no toca lo existente
            await conn.run_sync(SQLModel.metadata.create_all)
        conteos = await auditar(engine, args.salida, _encabezado(engine, args.salida))
    finally:
        await engine.dispose()
        if eco_previo is None:
            os.environ.pop("SQL_ECHO", None)
        else:
            os.environ["SQL_ECHO"] = eco_previo
        for cache in (get_settings, get_engine, get_session_factory):
            cache.cache_clear()
    for recurso, por_tamanio in conteos.items():
        print(f"{recurso}: {por_tamanio}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
