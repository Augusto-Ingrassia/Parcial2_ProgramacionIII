from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.editoriales.models import Editorial
from app.modules.editoriales.schemas import EditorialCreate, EditorialUpdate

_MSG_DUPLICADA = "Ya existe una editorial con ese nombre"
_MSG_NO_ENCONTRADA = "Editorial no encontrada"


async def _commit_o_409(session: AsyncSession) -> None:
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail=_MSG_DUPLICADA) from None


async def crear_editorial(session: AsyncSession, payload: EditorialCreate) -> Editorial:
    editorial = Editorial(**payload.model_dump())
    session.add(editorial)
    await _commit_o_409(session)
    return editorial


async def listar_editoriales(session: AsyncSession, limit: int, offset: int) -> list[Editorial]:
    stmt = select(Editorial).order_by(Editorial.id).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def obtener_editorial(session: AsyncSession, editorial_id: int) -> Editorial:
    editorial = await session.get(Editorial, editorial_id)
    if editorial is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_MSG_NO_ENCONTRADA)
    return editorial


async def actualizar_editorial(
    session: AsyncSession, editorial_id: int, payload: EditorialUpdate
) -> Editorial:
    editorial = await obtener_editorial(session, editorial_id)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(editorial, campo, valor)
    await _commit_o_409(session)
    return editorial
