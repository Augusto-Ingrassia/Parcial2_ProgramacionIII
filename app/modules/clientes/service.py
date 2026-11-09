from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import commit_o_http
from app.modules.clientes.models import Cliente, PerfilCliente
from app.modules.clientes.schemas import (
    ClienteCreate,
    ClienteRead,
    ClienteResumen,
    ClienteUpdate,
    PerfilCreate,
)

_MSG_NO_ENCONTRADO = "Cliente no encontrado"
_ERRORES_CLIENTE = {"unique": (status.HTTP_409_CONFLICT, "Ya existe un cliente con ese email")}
_ERRORES_PERFIL = {
    "unique": (status.HTTP_409_CONFLICT, "El cliente ya tiene un perfil"),
    "foreign_key": (status.HTTP_404_NOT_FOUND, _MSG_NO_ENCONTRADO),
}


async def crear_cliente(session: AsyncSession, payload: ClienteCreate) -> ClienteRead:
    cliente = Cliente(**payload.model_dump())
    session.add(cliente)
    await commit_o_http(session, _ERRORES_CLIENTE)
    # Un cliente recién creado no tiene perfil: no hace falta volver a leer.
    return ClienteRead(**ClienteResumen.model_validate(cliente).model_dump(), perfil=None)


async def listar_clientes(session: AsyncSession, limit: int, offset: int) -> list[Cliente]:
    stmt = (
        select(Cliente)
        .options(joinedload(Cliente.perfil))
        .order_by(Cliente.id)
        .offset(offset)
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def obtener_cliente(session: AsyncSession, cliente_id: int) -> Cliente:
    stmt = select(Cliente).where(Cliente.id == cliente_id).options(joinedload(Cliente.perfil))
    cliente = (await session.execute(stmt)).scalar_one_or_none()
    if cliente is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_MSG_NO_ENCONTRADO)
    return cliente


async def actualizar_cliente(
    session: AsyncSession, cliente_id: int, payload: ClienteUpdate
) -> Cliente:
    cliente = await obtener_cliente(session, cliente_id)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(cliente, campo, valor)
    await commit_o_http(session, _ERRORES_CLIENTE)
    return cliente


async def crear_perfil(
    session: AsyncSession, cliente_id: int, payload: PerfilCreate
) -> PerfilCliente:
    # Sin SELECT previo: la FK decide el 404 y el UNIQUE el 409 (RN-09).
    perfil = PerfilCliente(cliente_id=cliente_id, **payload.model_dump())
    session.add(perfil)
    await commit_o_http(session, _ERRORES_PERFIL)
    return perfil
