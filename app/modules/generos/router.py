from fastapi import APIRouter, status

from app.core.database import SessionDep
from app.core.pagination import PaginationDep
from app.modules.generos import service
from app.modules.generos.schemas import GeneroCreate, GeneroRead

router = APIRouter(prefix="/generos", tags=["Géneros"])


@router.post("/", response_model=GeneroRead, status_code=status.HTTP_201_CREATED)
async def crear_genero(payload: GeneroCreate, session: SessionDep):
    return await service.crear_genero(session, payload)


@router.get("/", response_model=list[GeneroRead])
async def listar_generos(session: SessionDep, pagination: PaginationDep):
    return await service.listar_generos(session, pagination.limit, pagination.offset)


@router.get("/{genero_id}", response_model=GeneroRead)
async def obtener_genero(genero_id: int, session: SessionDep):
    return await service.obtener_genero(session, genero_id)
