"""Presupuesto de consultas: cada lectura emite una cantidad FIJA de sentencias.

El número no depende del tamaño de la página ni de la colección (sin N+1).
`selectinload` agrupa hasta 500 claves por consulta `IN`; como `limit <= 100`
(RN-10), el presupuesto es constante en todo el rango válido de paginación.
"""

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.autores.models import Autor
from app.modules.clientes.models import Cliente, PerfilCliente
from app.modules.editoriales.models import Editorial
from app.modules.generos.models import Genero
from app.modules.libros.models import Libro, LibroAutor
from app.modules.ventas.models import RenglonVenta, Venta

TAMANIOS = [1, 10, 50]
PRECIO = Decimal("10.50")


def _sesion(db_engine) -> AsyncSession:
    return async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)()


async def _catalogo_minimo(session: AsyncSession) -> tuple[Editorial, Genero]:
    editorial = Editorial(nombre="Editorial Volumen", pais="Argentina")
    genero = Genero(nombre="Genero Volumen")
    session.add_all([editorial, genero])
    await session.flush()
    return editorial, genero


def _libro(n: int, editorial: Editorial, genero: Genero) -> Libro:
    return Libro(
        isbn=f"978-0-00-{n:06d}-0",
        titulo=f"Libro {n}",
        precio=PRECIO,
        stock=100,
        editorial_id=editorial.id,
        genero_id=genero.id,
    )


async def insertar_libros(db_engine, cantidad: int) -> None:
    async with _sesion(db_engine) as session:
        editorial, genero = await _catalogo_minimo(session)
        session.add_all([_libro(i, editorial, genero) for i in range(cantidad)])
        await session.commit()


async def insertar_libro_con_autorias(db_engine, cantidad: int) -> int:
    async with _sesion(db_engine) as session:
        editorial, genero = await _catalogo_minimo(session)
        libro = _libro(0, editorial, genero)
        autores = [Autor(nombre=f"Autor {i}", nacionalidad="Argentina") for i in range(cantidad)]
        session.add_all([libro, *autores])
        await session.flush()
        session.add_all(
            LibroAutor(libro_id=libro.id, autor_id=a.id, rol="coautor", orden=i + 1)
            for i, a in enumerate(autores)
        )
        await session.commit()
        return libro.id


async def insertar_ventas(db_engine, cantidad: int) -> None:
    """`cantidad` ventas con 1 o 2 renglones (alternados)."""
    async with _sesion(db_engine) as session:
        editorial, genero = await _catalogo_minimo(session)
        libros = [_libro(i, editorial, genero) for i in range(2)]
        cliente = Cliente(nombre="Cliente Volumen", email="volumen@example.com")
        session.add_all([*libros, cliente])
        await session.flush()
        for i in range(cantidad):
            renglones = 1 + i % 2
            venta = Venta(cliente_id=cliente.id, total=PRECIO * renglones)
            session.add(venta)
            await session.flush()
            session.add_all(
                RenglonVenta(
                    venta_id=venta.id, libro_id=lb.id, cantidad=1, precio_unitario=PRECIO
                )
                for lb in libros[:renglones]
            )
        await session.commit()


async def insertar_venta_con_renglones(db_engine, cantidad: int) -> int:
    async with _sesion(db_engine) as session:
        editorial, genero = await _catalogo_minimo(session)
        libros = [_libro(i, editorial, genero) for i in range(cantidad)]
        cliente = Cliente(nombre="Cliente Volumen", email="volumen@example.com")
        session.add_all([*libros, cliente])
        await session.flush()
        venta = Venta(cliente_id=cliente.id, total=PRECIO * cantidad)
        session.add(venta)
        await session.flush()
        session.add_all(
            RenglonVenta(venta_id=venta.id, libro_id=lb.id, cantidad=1, precio_unitario=PRECIO)
            for lb in libros
        )
        await session.commit()
        return venta.id


async def insertar_clientes(db_engine, cantidad: int) -> None:
    """`cantidad` clientes; los de índice par tienen perfil."""
    async with _sesion(db_engine) as session:
        clientes = [
            Cliente(nombre=f"Cliente {i}", email=f"c{i}@example.com") for i in range(cantidad)
        ]
        session.add_all(clientes)
        await session.flush()
        session.add_all(
            PerfilCliente(cliente_id=c.id, telefono="11-0000", direccion="Calle 1")
            for i, c in enumerate(clientes)
            if i % 2 == 0
        )
        await session.commit()


async def medir(client, contar_consultas, url: str):
    """Hace el GET y devuelve (respuesta, cantidad de sentencias emitidas)."""
    contar_consultas.clear()
    respuesta = await client.get(url)
    return respuesta, len(contar_consultas)


async def contar(db_engine, modelo) -> int:
    async with _sesion(db_engine) as session:
        return (await session.execute(select(func.count()).select_from(modelo))).scalar_one()


# --- 2.1 helpers de volumen -------------------------------------------------


@pytest.mark.asyncio
async def test_helpers_insertan_las_cantidades_pedidas(db_engine):
    await insertar_ventas(db_engine, 7)
    assert await contar(db_engine, Venta) == 7
    assert await contar(db_engine, RenglonVenta) == 10  # 1,2,1,2,1,2,1

    await insertar_clientes(db_engine, 5)
    assert await contar(db_engine, Cliente) == 6  # el de las ventas + 5
    assert await contar(db_engine, PerfilCliente) == 3  # índices 0, 2 y 4


# --- 2.2 a 2.6 presupuestos -------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("n", TAMANIOS)
async def test_listado_de_libros_emite_una_sentencia(client, db_engine, contar_consultas, n):
    await insertar_libros(db_engine, 50)

    respuesta, sentencias = await medir(client, contar_consultas, f"/libros/?limit={n}")

    assert respuesta.status_code == 200
    libros = respuesta.json()
    assert len(libros) == n
    assert all(lb["editorial"]["nombre"] == "Editorial Volumen" for lb in libros)
    assert all(lb["genero"]["nombre"] == "Genero Volumen" for lb in libros)
    assert sentencias == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("n", TAMANIOS)
async def test_detalle_de_libro_emite_dos_sentencias(client, db_engine, contar_consultas, n):
    libro_id = await insertar_libro_con_autorias(db_engine, n)

    respuesta, sentencias = await medir(client, contar_consultas, f"/libros/{libro_id}")

    assert respuesta.status_code == 200
    assert len(respuesta.json()["autores"]) == n
    assert sentencias == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("n", TAMANIOS)
async def test_listado_de_ventas_emite_dos_sentencias(client, db_engine, contar_consultas, n):
    await insertar_ventas(db_engine, 50)

    respuesta, sentencias = await medir(client, contar_consultas, f"/ventas/?limit={n}")

    assert respuesta.status_code == 200
    ventas = respuesta.json()
    assert len(ventas) == n
    assert all(v["cliente"]["email"] == "volumen@example.com" for v in ventas)
    assert {len(v["renglones"]) for v in ventas} == ({1} if n == 1 else {1, 2})
    assert sentencias == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("n", TAMANIOS)
async def test_detalle_de_venta_emite_dos_sentencias(client, db_engine, contar_consultas, n):
    venta_id = await insertar_venta_con_renglones(db_engine, n)

    respuesta, sentencias = await medir(client, contar_consultas, f"/ventas/{venta_id}")

    assert respuesta.status_code == 200
    renglones = respuesta.json()["renglones"]
    assert len(renglones) == n
    assert all(r["titulo"] and Decimal(str(r["subtotal"])) == PRECIO for r in renglones)
    assert sentencias == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("n", TAMANIOS)
async def test_listado_de_clientes_emite_una_sentencia(client, db_engine, contar_consultas, n):
    await insertar_clientes(db_engine, 50)

    respuesta, sentencias = await medir(client, contar_consultas, f"/clientes/?limit={n}")

    assert respuesta.status_code == 200
    clientes = respuesta.json()
    assert len(clientes) == n
    assert sentencias == 1
    if n > 1:
        assert any(c["perfil"] is not None for c in clientes)
        assert any(c["perfil"] is None for c in clientes)
