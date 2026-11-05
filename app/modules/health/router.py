from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import text
from app.core.database import get_session

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
                detail="Respuesta inesperada de la base de datos",
            )
        return {"estado": "listo", "database": "conectada"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Base de datos no disponible: {str(exc)}",
        ) from exc
