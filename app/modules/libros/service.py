from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.exceptions import commit_o_http
from app.modules.autores.models import Autor
from app.modules.editoriales.models import Editorial
from app.modules.generos.models import Genero
from app.modules.libros.models import Libro, LibroAutor
from app.modules.libros.schemas import (
    AutorDeLibroRead,
    LibroCreate,
    LibroDeAutorRead,
    LibroRead,
    LibroReadDetail,
    LibroUpdate,
)

_ERRORES_ESCRITURA = {
    "unique": (status.HTTP_409_CONFLICT, "Ya existe un libro con ese ISBN"),
    "foreign_key": (
        status.HTTP_409_CONFLICT,
        "La editorial, el género o alguno de los autores indicados no existe",
    ),
}

# Relaciones a uno: joinedload (misma consulta). Colección: selectinload (una consulta IN).
# Son funciones para no configurar los mappers al importar el módulo.
def _con_editorial_y_genero():
    return joinedload(Libro.editorial), joinedload(Libro.genero)


def _con_detalle():
    return (
        *_con_editorial_y_genero(),
        selectinload(Libro.autorias).joinedload(LibroAutor.autor),
    )


def _a_detalle(libro: Libro) -> LibroReadDetail:
    autorias = sorted(libro.autorias, key=lambda a: (a.orden, a.autor_id))
    return LibroReadDetail(
        **LibroRead.model_validate(libro).model_dump(),
        autores=[
            AutorDeLibroRead(autor_id=a.autor_id, nombre=a.autor.nombre, rol=a.rol, orden=a.orden)
            for a in autorias
        ],
    )


async def _cargar_detalle(session: AsyncSession, libro_id: int) -> Libro | None:
    stmt = (
        select(Libro)
        .where(Libro.id == libro_id)
        .options(*_con_detalle())
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).unique().scalar_one_or_none()


async def _obtener_o_404(session: AsyncSession, modelo, id_: int, mensaje: str):
    obj = await session.get(modelo, id_)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=mensaje)
    return obj


async def crear_libro(session: AsyncSession, payload: LibroCreate) -> LibroReadDetail:
    # Sin SELECT previo: si algún id no existe, la FK rechaza la escritura → 409.
    libro = Libro(**payload.model_dump(exclude={"autores"}))
    libro.autorias = [LibroAutor(**a.model_dump()) for a in payload.autores]
    session.add(libro)
    await commit_o_http(session, _ERRORES_ESCRITURA)
    return _a_detalle(await _cargar_detalle(session, libro.id))


async def listar_libros(
    session: AsyncSession,
    limit: int,
    offset: int,
    titulo: str | None = None,
    genero_id: int | None = None,
    editorial_id: int | None = None,
) -> list[Libro]:
    stmt = select(Libro).options(*_con_editorial_y_genero())
    if titulo:
        # Parámetro ligado (RN-11): lower(titulo) LIKE '%' || lower(:p) || '%'.
        stmt = stmt.where(Libro.titulo.icontains(titulo, autoescape=True))
    if genero_id is not None:
        stmt = stmt.where(Libro.genero_id == genero_id)
    if editorial_id is not None:
        stmt = stmt.where(Libro.editorial_id == editorial_id)
    stmt = stmt.order_by(Libro.id).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def obtener_libro(session: AsyncSession, libro_id: int) -> LibroReadDetail:
    libro = await _cargar_detalle(session, libro_id)
    if libro is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Libro no encontrado")
    return _a_detalle(libro)


async def actualizar_libro(
    session: AsyncSession, libro_id: int, payload: LibroUpdate
) -> LibroReadDetail:
    libro = await _obtener_o_404(session, Libro, libro_id, "Libro no encontrado")
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(libro, campo, valor)
    await commit_o_http(session, _ERRORES_ESCRITURA)
    return _a_detalle(await _cargar_detalle(session, libro_id))


# --- Navegación cruzada ---
async def listar_libros_de_editorial(
    session: AsyncSession, editorial_id: int, limit: int, offset: int
) -> list[Libro]:
    await _obtener_o_404(session, Editorial, editorial_id, "Editorial no encontrada")
    return await listar_libros(session, limit, offset, editorial_id=editorial_id)


async def listar_libros_de_genero(
    session: AsyncSession, genero_id: int, limit: int, offset: int
) -> list[Libro]:
    await _obtener_o_404(session, Genero, genero_id, "Género no encontrado")
    return await listar_libros(session, limit, offset, genero_id=genero_id)


async def listar_libros_de_autor(
    session: AsyncSession, autor_id: int, limit: int, offset: int
) -> list[LibroDeAutorRead]:
    await _obtener_o_404(session, Autor, autor_id, "Autor no encontrado")
    stmt = (
        select(LibroAutor)
        .where(LibroAutor.autor_id == autor_id)
        .options(joinedload(LibroAutor.libro))
        .order_by(LibroAutor.libro_id)
        .offset(offset)
        .limit(limit)
    )
    autorias = (await session.execute(stmt)).scalars().all()
    return [
        LibroDeAutorRead(
            id=a.libro.id,
            isbn=a.libro.isbn,
            titulo=a.libro.titulo,
            precio=a.libro.precio,
            stock=a.libro.stock,
            rol=a.rol,
            orden=a.orden,
        )
        for a in autorias
    ]
