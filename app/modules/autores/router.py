from fastapi import APIRouter, status

from app.core.database import SessionDep
from app.core.pagination import PaginationDep
from app.modules.autores import service
from app.modules.autores.schemas import AutorCreate, AutorRead, AutorUpdate
from app.modules.libros import service as libros_service
from app.modules.libros.schemas import LibroDeAutorRead

router = APIRouter(prefix="/autores", tags=["Autores"])


@router.post("/", response_model=AutorRead, status_code=status.HTTP_201_CREATED)
async def crear_autor(payload: AutorCreate, session: SessionDep):
    return await service.crear_autor(session, payload)


@router.get("/", response_model=list[AutorRead])
async def listar_autores(session: SessionDep, pagination: PaginationDep):
    return await service.listar_autores(session, pagination.limit, pagination.offset)


@router.get("/{autor_id}", response_model=AutorRead)
async def obtener_autor(autor_id: int, session: SessionDep):
    return await service.obtener_autor(session, autor_id)


@router.patch("/{autor_id}", response_model=AutorRead)
async def actualizar_autor(autor_id: int, payload: AutorUpdate, session: SessionDep):
    return await service.actualizar_autor(session, autor_id, payload)


@router.get("/{autor_id}/libros", response_model=list[LibroDeAutorRead])
async def listar_libros_de_autor(autor_id: int, session: SessionDep, pagination: PaginationDep):
    return await libros_service.listar_libros_de_autor(
        session, autor_id, pagination.limit, pagination.offset
    )
