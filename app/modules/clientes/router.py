from fastapi import APIRouter, status

from app.core.database import SessionDep
from app.core.pagination import PaginationDep
from app.modules.clientes import service
from app.modules.clientes.schemas import (
    ClienteCreate,
    ClienteRead,
    ClienteUpdate,
    PerfilCreate,
    PerfilRead,
)
from app.modules.ventas import service as ventas_service
from app.modules.ventas.schemas import VentaRead

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.post("/", response_model=ClienteRead, status_code=status.HTTP_201_CREATED)
async def crear_cliente(payload: ClienteCreate, session: SessionDep):
    return await service.crear_cliente(session, payload)


@router.get("/", response_model=list[ClienteRead])
async def listar_clientes(session: SessionDep, pagination: PaginationDep):
    return await service.listar_clientes(session, pagination.limit, pagination.offset)


@router.get("/{cliente_id}", response_model=ClienteRead)
async def obtener_cliente(cliente_id: int, session: SessionDep):
    return await service.obtener_cliente(session, cliente_id)


@router.patch("/{cliente_id}", response_model=ClienteRead)
async def actualizar_cliente(cliente_id: int, payload: ClienteUpdate, session: SessionDep):
    return await service.actualizar_cliente(session, cliente_id, payload)


@router.post(
    "/{cliente_id}/perfil", response_model=PerfilRead, status_code=status.HTTP_201_CREATED
)
async def crear_perfil(cliente_id: int, payload: PerfilCreate, session: SessionDep):
    return await service.crear_perfil(session, cliente_id, payload)


@router.get("/{cliente_id}/ventas", response_model=list[VentaRead])
async def listar_ventas_de_cliente(cliente_id: int, session: SessionDep, pagination: PaginationDep):
    return await ventas_service.listar_ventas_de_cliente(
        session, cliente_id, pagination.limit, pagination.offset
    )
