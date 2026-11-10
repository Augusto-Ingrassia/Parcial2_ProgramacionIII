import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import text
from app.core.database import get_session

MSG_BD_NO_DISPONIBLE = "Base de datos no disponible"

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/health", tags=["Salud y Diagnóstico"])


@router.get("/live", status_code=status.HTTP_200_OK)
async def health_live() -> dict[str, str]:
    """
    Verifica que el proceso del servidor esté vivo (Liveness probe).
    No realiza consultas a la base de datos.
    """
    return {"estado": "vivo"}


@router.get("/ready", status_code=status.HTTP_200_OK)
async def health_ready(
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """
    Verifica que la base de datos esté lista y responda (Readiness probe).
    Ejecuta SELECT 1 de forma asincrónica.
    """
    try:
        result = await session.execute(text("SELECT 1"))
        scalar = result.scalar()
        if scalar != 1:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=MSG_BD_NO_DISPONIBLE,
            )
        return {"estado": "listo", "database": "conectada"}
    except HTTPException:
        raise
    except Exception:
        # No se registra ni se devuelve la excepción original: puede contener
        # host, usuario o la URL completa de la base (RN-12).
        logger.warning("Readiness: la base de datos no respondió a SELECT 1")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=MSG_BD_NO_DISPONIBLE,
        ) from None
