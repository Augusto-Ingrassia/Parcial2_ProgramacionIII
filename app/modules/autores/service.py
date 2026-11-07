from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.autores.models import Autor
from app.modules.autores.schemas import AutorCreate, AutorUpdate


async def crear_autor(session: AsyncSession, payload: AutorCreate) -> Autor:
    autor = Autor(**payload.model_dump())
    session.add(autor)
    await session.commit()
    return autor


async def listar_autores(session: AsyncSession, limit: int, offset: int) -> list[Autor]:
    stmt = select(Autor).order_by(Autor.id).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def obtener_autor(session: AsyncSession, autor_id: int) -> Autor:
    autor = await session.get(Autor, autor_id)
    if autor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Autor no encontrado")
    return autor


async def actualizar_autor(session: AsyncSession, autor_id: int, payload: AutorUpdate) -> Autor:
    autor = await obtener_autor(session, autor_id)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(autor, campo, valor)
    await session.commit()
    return autor
