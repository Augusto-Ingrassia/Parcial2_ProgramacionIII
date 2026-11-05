from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlmodel import SQLModel
from app.core.database import get_engine
from app.modules.health.router import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Inicialización del motor y recursos
    engine = get_engine()
    app.state.engine = engine
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
    except Exception as exc:
        # En caso de error de conexión en startup, registrar y continuar o dejar que health/ready falle
        print(f"Advertencia: No se pudo conectar a la base de datos durante startup: {exc}")

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
app.include_router(health_router)
