import asyncio
import logging
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.exceptions import commit_o_http
from app.modules.clientes.models import Cliente
from app.modules.clientes.schemas import ClienteResumen
from app.modules.libros.models import Libro
from app.modules.ventas.models import RenglonVenta, Venta
from app.modules.ventas.schemas import RenglonVentaRead, VentaCreate, VentaRead

# Logger ya configurado por uvicorn: el aviso aparece en `docker logs`.
logger = logging.getLogger("uvicorn.error")

_MSG_LIBRO_INEXISTENTE = "Alguno de los libros indicados no existe"
_ERRORES_ALTA = {
    "foreign_key": (
        status.HTTP_409_CONFLICT,
        "El cliente o alguno de los libros indicados no existe",
    ),
}

# Cliente (a uno): joinedload. Renglones (colección): selectinload, con su libro.
def _con_detalle():
    return (
        joinedload(Venta.cliente),
        selectinload(Venta.renglones).joinedload(RenglonVenta.libro),
    )


def _a_read(venta: Venta) -> VentaRead:
    return VentaRead(
        id=venta.id,
        fecha=venta.fecha,
        total=venta.total,
        cliente=ClienteResumen.model_validate(venta.cliente),
        renglones=[
            RenglonVentaRead(
                libro_id=r.libro_id,
                titulo=r.libro.titulo,
                cantidad=r.cantidad,
                precio_unitario=r.precio_unitario,
                subtotal=r.cantidad * r.precio_unitario,
            )
            for r in sorted(venta.renglones, key=lambda r: r.id)
        ],
    )


async def crear_venta(session: AsyncSession, payload: VentaCreate) -> VentaRead:
    # RN-06: el precio vigente se lee de la base en una sola consulta.
    ids = [r.libro_id for r in payload.renglones]
    precios = dict((await session.execute(select(Libro.id, Libro.precio).where(Libro.id.in_(ids)))).all())
    if len(precios) != len(ids):
        raise HTTPException(status.HTTP_409_CONFLICT, detail=_MSG_LIBRO_INEXISTENTE)

    renglones = [
        RenglonVenta(libro_id=r.libro_id, cantidad=r.cantidad, precio_unitario=precios[r.libro_id])
        for r in payload.renglones
    ]
    # RN-07: el total lo calcula el servidor.
    total = sum((r.cantidad * r.precio_unitario for r in renglones), Decimal("0.00"))

    # RN-04: la venta nace con sus renglones, en la misma transacción.
    # El cliente no se consulta antes: si no existe, la FK rechaza la escritura.
    venta = Venta(cliente_id=payload.cliente_id, total=total)
    venta.renglones = renglones
    session.add(venta)
    await commit_o_http(session, _ERRORES_ALTA)
    return await obtener_venta(session, venta.id)


async def obtener_venta(session: AsyncSession, venta_id: int) -> VentaRead:
    stmt = (
        select(Venta)
        .where(Venta.id == venta_id)
        .options(*_con_detalle())
        .execution_options(populate_existing=True)
    )
    venta = (await session.execute(stmt)).unique().scalar_one_or_none()
    if venta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
    return _a_read(venta)


async def listar_ventas(
    session: AsyncSession, limit: int, offset: int, cliente_id: int | None = None
) -> list[VentaRead]:
    stmt = select(Venta).options(*_con_detalle())
    if cliente_id is not None:
        stmt = stmt.where(Venta.cliente_id == cliente_id)
    stmt = stmt.order_by(Venta.id).offset(offset).limit(limit)
    return [_a_read(v) for v in (await session.execute(stmt)).unique().scalars().all()]


async def listar_ventas_de_cliente(
    session: AsyncSession, cliente_id: int, limit: int, offset: int
) -> list[VentaRead]:
    if await session.get(Cliente, cliente_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")
    return await listar_ventas(session, limit, offset, cliente_id=cliente_id)


async def notificar_comprobante(venta_id: int, email: str) -> None:
    """Simula el envío del comprobante; corre después de enviada la respuesta."""
    await asyncio.sleep(0.5)
    logger.info("Comprobante de la venta %s enviado a %s", venta_id, email)
