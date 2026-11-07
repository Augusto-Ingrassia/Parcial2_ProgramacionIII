from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.generos.models import Genero
from app.modules.generos.schemas import GeneroCreate


async def crear_genero(session: AsyncSession, payload: GeneroCreate) -> Genero:
    genero = Genero(**payload.model_dump())
    session.add(genero)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Ya existe un género con ese nombre"
        ) from None
    return genero


async def listar_generos(session: AsyncSession, limit: int, offset: int) -> list[Genero]:
    stmt = select(Genero).order_by(Genero.id).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def obtener_genero(session: AsyncSession, genero_id: int) -> Genero:
    genero = await session.get(Genero, genero_id)
    if genero is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Género no encontrado")
    return genero
