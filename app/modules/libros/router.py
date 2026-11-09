from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.database import SessionDep
from app.core.pagination import PaginationDep
from app.modules.libros import service
from app.modules.libros.schemas import LibroCreate, LibroRead, LibroReadDetail, LibroUpdate

router = APIRouter(prefix="/libros", tags=["Libros"])


@router.post("/", response_model=LibroReadDetail, status_code=status.HTTP_201_CREATED)
async def crear_libro(payload: LibroCreate, session: SessionDep):
    return await service.crear_libro(session, payload)


@router.get("/", response_model=list[LibroRead])
async def listar_libros(
    session: SessionDep,
    pagination: PaginationDep,
    titulo: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
    genero_id: int | None = None,
):
    return await service.listar_libros(
        session, pagination.limit, pagination.offset, titulo=titulo, genero_id=genero_id
    )


@router.get("/{libro_id}", response_model=LibroReadDetail)
async def obtener_libro(libro_id: int, session: SessionDep):
    return await service.obtener_libro(session, libro_id)


@router.patch("/{libro_id}", response_model=LibroReadDetail)
async def actualizar_libro(libro_id: int, payload: LibroUpdate, session: SessionDep):
    return await service.actualizar_libro(session, libro_id, payload)
