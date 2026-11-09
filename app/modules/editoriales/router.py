from fastapi import APIRouter, status

from app.core.database import SessionDep
from app.core.pagination import PaginationDep
from app.modules.editoriales import service
from app.modules.editoriales.schemas import EditorialCreate, EditorialRead, EditorialUpdate
from app.modules.libros import service as libros_service
from app.modules.libros.schemas import LibroRead

router = APIRouter(prefix="/editoriales", tags=["Editoriales"])


@router.post("/", response_model=EditorialRead, status_code=status.HTTP_201_CREATED)
async def crear_editorial(payload: EditorialCreate, session: SessionDep):
    return await service.crear_editorial(session, payload)


@router.get("/", response_model=list[EditorialRead])
async def listar_editoriales(session: SessionDep, pagination: PaginationDep):
    return await service.listar_editoriales(session, pagination.limit, pagination.offset)


@router.get("/{editorial_id}", response_model=EditorialRead)
async def obtener_editorial(editorial_id: int, session: SessionDep):
    return await service.obtener_editorial(session, editorial_id)


@router.patch("/{editorial_id}", response_model=EditorialRead)
async def actualizar_editorial(editorial_id: int, payload: EditorialUpdate, session: SessionDep):
    return await service.actualizar_editorial(session, editorial_id, payload)


@router.get("/{editorial_id}/libros", response_model=list[LibroRead])
async def listar_libros_de_editorial(
    editorial_id: int, session: SessionDep, pagination: PaginationDep
):
    return await libros_service.listar_libros_de_editorial(
        session, editorial_id, pagination.limit, pagination.offset
    )
