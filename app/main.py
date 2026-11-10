import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlmodel import SQLModel
from app.core.database import get_engine
from app.core.exceptions import register_exception_handlers
from app.modules.autores import models as _autores_models  # noqa: F401
from app.modules.autores.router import router as autores_router
from app.modules.clientes import models as _clientes_models  # noqa: F401
from app.modules.clientes.router import router as clientes_router
from app.modules.editoriales import models as _editoriales_models  # noqa: F401
from app.modules.editoriales.router import router as editoriales_router
from app.modules.generos import models as _generos_models  # noqa: F401
from app.modules.generos.router import router as generos_router
from app.modules.health.router import router as health_router
from app.modules.libros import models as _libros_models  # noqa: F401
from app.modules.libros.router import router as libros_router
from app.modules.ventas import models as _ventas_models  # noqa: F401
from app.modules.ventas.router import router as ventas_router

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Inicialización del motor y recursos
    engine = get_engine()
    app.state.engine = engine
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
    except Exception:
        # Fail-fast: sin base no se atiende ninguna petición. No se registra la
        # excepción original porque puede contener la URL con credenciales.
        logger.error(
            "No se pudo conectar a la base de datos al iniciar; verifique DATABASE_URL"
        )
        await engine.dispose()
        raise

    yield

    # Liberación de recursos al apagar
    if hasattr(app.state, "engine") and app.state.engine is not None:
        await app.state.engine.dispose()


app = FastAPI(
    title="API Librería - Parcial Programación III",
    description="API REST asincrónica para catálogo y ventas de librería",
    version="1.0.0",
    lifespan=lifespan,
)

# Registro de routers modulares
register_exception_handlers(app)
app.include_router(health_router)
app.include_router(editoriales_router)
app.include_router(generos_router)
app.include_router(autores_router)
app.include_router(libros_router)
app.include_router(clientes_router)
app.include_router(ventas_router)