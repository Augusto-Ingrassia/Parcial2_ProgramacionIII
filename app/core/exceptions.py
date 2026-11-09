from collections.abc import Mapping

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

MSG_CONFLICTO = "La operación entra en conflicto con datos existentes"

# SQLSTATE de PostgreSQL para cada clase de violación de integridad.
_SQLSTATE = {
    "23505": "unique",
    "23503": "foreign_key",
    "23514": "check",
    "23502": "not_null",
}
# Respaldo por texto (SQLite en tests no expone SQLSTATE). El orden importa.
_PALABRAS = (
    ("unique", "unique"),
    ("duplicate key", "unique"),
    ("foreign key", "foreign_key"),
    ("check", "check"),
    ("not null", "not_null"),
)


def tipo_violacion(exc: IntegrityError) -> str | None:
    """Clasifica un IntegrityError en unique / foreign_key / check / not_null.

    Sólo se usa para elegir un mensaje propio: el texto de la base nunca
    llega al cliente (RN-12).
    """
    orig = exc.orig
    codigo = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    if codigo in _SQLSTATE:
        return _SQLSTATE[codigo]
    texto = str(orig).lower()
    for palabra, tipo in _PALABRAS:
        if palabra in texto:
            return tipo
    return None


async def commit_o_http(
    session: AsyncSession, errores: Mapping[str, tuple[int, str]]
) -> None:
    """Confirma la transacción; si la base la rechaza, revierte y responde
    con el (código, mensaje) propio que corresponda al tipo de violación."""
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        codigo, detalle = errores.get(
            tipo_violacion(exc), (status.HTTP_409_CONFLICT, MSG_CONFLICTO)
        )
        raise HTTPException(codigo, detail=detalle) from None


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Red de seguridad RN-12: 409 genérico sin exponer internos de la base."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": MSG_CONFLICTO},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(IntegrityError, integrity_error_handler)
