"""Genera la evidencia de consultas SQL (`evidencia/queries_*.log`).

Uso: `python -m scripts.auditar_consultas [--salida evidencia]`

Inserta un volumen de datos dentro de una transacción externa, lista 1, 10 y 50
libros y ventas y consulta el detalle de libros con 1, 10 y 50 autores y de
ventas con 1, 10 y 50 renglones a través de la API real, registra las sentencias
que emite el motor y revierte la transacción: la base queda como estaba.
"""

import argparse
import asyncio
import logging
import os
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlmodel import SQLModel

from app.core.config import get_settings
from app.core.database import get_engine, get_session, get_session_factory
from app.main import app
from app.modules.autores.models import Autor
from app.modules.clientes.models import Cliente
from app.modules.editoriales.models import Editorial
from app.modules.generos.models import Genero
from app.modules.libros.models import Libro, LibroAutor
from app.modules.ventas.models import RenglonVenta, Venta

TAMANIOS = (1, 10, 50)
VOLUMEN = max(TAMANIOS)
DETALLES = (1, 10, 50)  # autores por libro / renglones por venta en las consultas de detalle
PRECIO = Decimal("10.50")
LOGGER_SQL = "sqlalchemy.engine.Engine"
COMANDO = "python -m scripts.auditar_consultas"


async def _insertar_volumen(session: AsyncSession) -> dict[str, dict[int, int]]:
    """Datos de volumen; sólo `flush` (la transacción es externa).

    50 libros, 50 ventas de 1 o 2 renglones, 3 libros con 1/10/50 autores y 3
    ventas con 1/10/50 renglones. Devuelve los ids de estas últimas por tamaño.
    """
    editorial = Editorial(nombre="Editorial Auditoria", pais="Argentina")
    genero = Genero(nombre="Genero Auditoria")
    cliente = Cliente(nombre="Cliente Auditoria", email="auditoria@example.com")
    autores = [
        Autor(nombre=f"Autor {i}", nacionalidad="Argentina") for i in range(max(DETALLES))
    ]
    session.add_all([editorial, genero, cliente, *autores])
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
    ids: dict[str, dict[int, int]] = {"libros": {}, "ventas": {}}
    for libro, k in zip(libros, DETALLES):
        ids["libros"][k] = libro.id
        session.add_all(
            LibroAutor(libro_id=libro.id, autor_id=a.id, rol="autor", orden=orden)
            for orden, a in enumerate(autores[:k], start=1)
        )
    # Primero las 50 ventas del listado y luego las de detalle, para que el
    # listado (más recientes primero o no) siga devolviendo exactamente `limit` filas.
    for i, renglones in [(i, 1 + i % 2) for i in range(VOLUMEN)] + [(None, k) for k in DETALLES]:
        venta = Venta(cliente_id=cliente.id, total=PRECIO * renglones)
        session.add(venta)
        await session.flush()
        if i is None:
            ids["ventas"][renglones] = venta.id
        session.add_all(
            RenglonVenta(venta_id=venta.id, libro_id=lb.id, cantidad=1, precio_unitario=PRECIO)
            for lb in libros[:renglones]
        )
    await session.flush()
    return ids


async def auditar(
    engine: AsyncEngine, destino: Path, encabezado: str = ""
) -> dict[str, dict[int, int]]:
    """Escribe `queries_libros.log` y `queries_ventas.log` en `destino`.

    Devuelve la cantidad de sentencias por recurso y tamaño de página
    (`libros`, `ventas`) y por tamaño de detalle (`detalle_libro`, `detalle_venta`).
    """
    destino.mkdir(parents=True, exist_ok=True)
    sentencias: list[str] = []

    def _contar(conn, cursor, statement, *args):
        sentencias.append(statement)

    logger = logging.getLogger(LOGGER_SQL)
    nivel_previo = logger.level
    logger.setLevel(logging.INFO)  # la conexión toma el nivel al abrirse
    conteos: dict[str, dict[int, int]] = {
        "libros": {},
        "ventas": {},
        "detalle_libro": {},
        "detalle_venta": {},
    }
    try:
        async with engine.connect() as conn:
            transaccion = await conn.begin()
            try:
                async with AsyncSession(bind=conn, expire_on_commit=False) as sesion:
                    ids = await _insertar_volumen(sesion)

                async def _sesion_auditoria():
                    async with AsyncSession(bind=conn, expire_on_commit=False) as s:
                        yield s

                app.dependency_overrides[get_session] = _sesion_auditoria
                event.listen(engine.sync_engine, "before_cursor_execute", _contar)
                try:
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as http:
                        for recurso, clave, campo in (
                            ("libros", "detalle_libro", "autores"),
                            ("ventas", "detalle_venta", "renglones"),
                        ):
                            ruta = destino / f"queries_{recurso}.log"
                            ruta.write_text(
                                (encabezado + "\n" if encabezado else ""), encoding="utf-8"
                            )
                            for n in TAMANIOS:
                                conteos[recurso][n] = await _medir(
                                    http, logger, ruta, f"/{recurso}/?limit={n}",
                                    f"/{recurso}/?limit={n}",
                                    lambda r, n=n: len(r.json()) == n, sentencias,
                                )
                            for k in DETALLES:
                                url = f"/{recurso}/{ids[recurso][k]}"
                                conteos[clave][k] = await _medir(
                                    http, logger, ruta, url,
                                    f"{url} (detalle, {campo}={k})",
                                    lambda r, k=k, campo=campo: len(r.json()[campo]) == k,
                                    sentencias,
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
    url: str,
    rotulo: str,
    valida: Callable[[Response], bool],
    sentencias: list[str],
) -> int:
    with ruta.open("a", encoding="utf-8") as f:
        f.write(f"=== GET {rotulo} ===\n")
    handler = logging.FileHandler(ruta, mode="a", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    sentencias.clear()
    try:
        respuesta = await http.get(url)
    finally:
        logger.removeHandler(handler)
        handler.close()
    if respuesta.status_code != 200 or not valida(respuesta):
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
