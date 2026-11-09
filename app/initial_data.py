"""Carga inicial determinística e idempotente.

Uso: `python -m app.initial_data` (usa `DATABASE_URL`). Cada fila se identifica
por su clave natural y sólo se inserta lo que falta, en una única transacción.
"""

import asyncio
import sys
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from app.core.database import get_engine, get_session_factory
from app.modules.autores import models as _autores_models  # noqa: F401
from app.modules.autores.models import Autor
from app.modules.clientes import models as _clientes_models  # noqa: F401
from app.modules.clientes.models import Cliente, PerfilCliente
from app.modules.editoriales import models as _editoriales_models  # noqa: F401
from app.modules.editoriales.models import Editorial
from app.modules.generos import models as _generos_models  # noqa: F401
from app.modules.generos.models import Genero
from app.modules.libros import models as _libros_models  # noqa: F401
from app.modules.libros.models import Libro, LibroAutor
from app.modules.ventas import models as _ventas_models  # noqa: F401

# --- Datos (única fuente para el seed y sus pruebas) ---------------------------------

EDITORIALES = [
    ("Sudamericana", "Argentina"),
    ("Emecé", "Argentina"),
    ("Anagrama", "España"),
]
GENEROS = ["Novela", "Cuento", "Poesía", "Ensayo"]
AUTORES = [
    ("Julio Cortázar", "Argentina"),
    ("Jorge Luis Borges", "Argentina"),
    ("Adolfo Bioy Casares", "Argentina"),
    ("Silvina Ocampo", "Argentina"),
    ("Edgar Allan Poe", "Estados Unidos"),
]
# (isbn, título, precio, stock, editorial, género|None, [(autor, rol, orden)])
LIBROS: list[tuple[str, str, Decimal, int, str, str | None, list[tuple[str, str, int]]]] = [
    (
        "978-950-00-0001-1", "Rayuela", Decimal("25000.00"), 20, "Sudamericana", "Novela",
        [("Julio Cortázar", "autor", 1)],
    ),
    (
        "978-950-00-0002-8", "Ficciones", Decimal("18000.00"), 30, "Emecé", "Cuento",
        [("Jorge Luis Borges", "autor", 1)],
    ),
    (
        "978-950-00-0003-5", "Los que aman, odian", Decimal("21000.00"), 15, "Emecé", "Novela",
        [("Adolfo Bioy Casares", "coautor", 1), ("Silvina Ocampo", "coautor", 2)],
    ),
    (
        "978-950-00-0004-2", "Cuentos de Poe", Decimal("27000.00"), 12, "Anagrama", "Cuento",
        [("Edgar Allan Poe", "autor", 1), ("Julio Cortázar", "traductor", 2)],
    ),
    (
        "978-950-00-0005-9", "Antología de la literatura fantástica", Decimal("32000.00"), 8,
        "Sudamericana", None,
        [
            ("Jorge Luis Borges", "coautor", 1),
            ("Silvina Ocampo", "coautor", 2),
            ("Adolfo Bioy Casares", "coautor", 3),
        ],
    ),
    (
        "978-950-00-0006-6", "El otro, el mismo", Decimal("15000.00"), 25, "Emecé", "Poesía",
        [("Jorge Luis Borges", "autor", 1)],
    ),
]
CLIENTES = [
    ("Tomás Pérez", "tomas@example.com", "11-5555-0001", "Av. Corrientes 1234, CABA"),
    ("Ana Gómez", "ana@example.com", "11-5555-0002", "Calle Falsa 742, Rosario"),
]


@dataclass
class ResumenSeed:
    """Filas creadas por entidad en una ejecución."""

    editoriales: int = 0
    generos: int = 0
    autores: int = 0
    libros: int = 0
    autorias: int = 0
    clientes: int = 0
    perfiles: int = 0


async def _obtener_o_crear[M: SQLModel](
    session: AsyncSession, modelo: type[M], clave: dict[str, Any], valores: dict[str, Any]
) -> tuple[M, bool]:
    """Busca por clave natural (la fila de menor id si hubiera varias) o la inserta."""
    consulta = select(modelo).order_by(*modelo.__table__.primary_key.columns).limit(1)
    for campo, valor in clave.items():
        consulta = consulta.where(getattr(modelo, campo) == valor)
    existente = (await session.execute(consulta)).scalars().first()
    if existente is not None:
        return existente, False
    nuevo = modelo(**clave, **valores)
    session.add(nuevo)
    await session.flush()
    return nuevo, True


async def _sembrar_en_sesion(session: AsyncSession) -> ResumenSeed:
    r = ResumenSeed()
    editoriales: dict[str, Editorial] = {}
    for nombre, pais in EDITORIALES:
        editoriales[nombre], creada = await _obtener_o_crear(
            session, Editorial, {"nombre": nombre}, {"pais": pais}
        )
        r.editoriales += creada
    generos: dict[str, Genero] = {}
    for nombre in GENEROS:
        generos[nombre], creado = await _obtener_o_crear(session, Genero, {"nombre": nombre}, {})
        r.generos += creado
    autores: dict[str, Autor] = {}
    for nombre, nacionalidad in AUTORES:
        autores[nombre], creado = await _obtener_o_crear(
            session, Autor, {"nombre": nombre}, {"nacionalidad": nacionalidad}
        )
        r.autores += creado
    for isbn, titulo, precio, stock, editorial, genero, autorias in LIBROS:
        libro, creado = await _obtener_o_crear(
            session,
            Libro,
            {"isbn": isbn},
            {
                "titulo": titulo,
                "precio": precio,
                "stock": stock,
                "editorial_id": editoriales[editorial].id,
                "genero_id": generos[genero].id if genero else None,
            },
        )
        r.libros += creado
        for nombre_autor, rol, orden in autorias:
            _, creada = await _obtener_o_crear(
                session,
                LibroAutor,
                {"libro_id": libro.id, "autor_id": autores[nombre_autor].id},
                {"rol": rol, "orden": orden},
            )
            r.autorias += creada
    for nombre, email, telefono, direccion in CLIENTES:
        cliente, creado = await _obtener_o_crear(
            session, Cliente, {"email": email}, {"nombre": nombre}
        )
        r.clientes += creado
        _, creado = await _obtener_o_crear(
            session,
            PerfilCliente,
            {"cliente_id": cliente.id},
            {"telefono": telefono, "direccion": direccion},
        )
        r.perfiles += creado
    return r


async def sembrar(session: AsyncSession) -> ResumenSeed:
    """Carga los datos que falten en una única transacción (rollback ante error)."""
    try:
        resumen = await _sembrar_en_sesion(session)
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
    return resumen


async def main() -> int:
    engine = get_engine()
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        async with get_session_factory()() as session:
            resumen = await sembrar(session)
    except (OSError, SQLAlchemyError):
        print(
            "Error: no se pudo cargar la base de datos inicial. "
            "Verifique que la base esté accesible y que DATABASE_URL sea correcta.",
            file=sys.stderr,
        )
        return 1
    finally:
        await engine.dispose()
    print("Carga inicial completada. Filas creadas:")
    for campo, cantidad in vars(resumen).items():
        print(f"  {campo}: {cantidad}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
