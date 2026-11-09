from fastapi import APIRouter, BackgroundTasks, status

from app.core.database import SessionDep
from app.core.pagination import PaginationDep
from app.modules.ventas import service
from app.modules.ventas.schemas import VentaCreate, VentaRead

# RN-08: las ventas son inmutables; no hay PUT, PATCH ni DELETE.
router = APIRouter(prefix="/ventas", tags=["Ventas"])


@router.post("/", response_model=VentaRead, status_code=status.HTTP_201_CREATED)
async def crear_venta(
    payload: VentaCreate, session: SessionDep, background_tasks: BackgroundTasks
):
    venta = await service.crear_venta(session, payload)
    background_tasks.add_task(service.notificar_comprobante, venta.id, venta.cliente.email)
    return venta


@router.get("/", response_model=list[VentaRead])
async def listar_ventas(session: SessionDep, pagination: PaginationDep):
    return await service.listar_ventas(session, pagination.limit, pagination.offset)


@router.get("/{venta_id}", response_model=VentaRead)
async def obtener_venta(venta_id: int, session: SessionDep):
    return await service.obtener_venta(session, venta_id)
