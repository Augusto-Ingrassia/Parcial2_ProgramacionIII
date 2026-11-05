# Design: Core Infrastructure and Health

## Context
El sistema parte de una base en blanco y debe cumplir estrictamente con la estructura modular exigida por la cátedra de Programación III (Ejercicio 1). Se requiere una arquitectura asincrónica limpia utilizando FastAPI y SQLModel con el motor SQLAlchemy 2.0 async sobre el driver `asyncpg`. Ver `proposal.md` para la motivación general.

## Goals / Non-Goals

**Goals:**
- Configurar el motor asincrónico con `create_async_engine` y sesiones generadas por `async_sessionmaker(expire_on_commit=False)`.
- Diseñar la inyección de dependencias `get_session` como generador asincrónico (`AsyncGenerator[AsyncSession, None]`).
- Implementar el ciclo de vida de la aplicación con `@asynccontextmanager def lifespan(app: FastAPI)` que cree las tablas mediante `conn.run_sync(SQLModel.metadata.create_all)` y limpie recursos con `engine.dispose()`.
- Exponer las rutas de diagnóstico `/health/live` (sin I/O a DB) y `/health/ready` (con `SELECT 1` asincrónico).
- Crear el archivo de casos de prueba HTTP `test/health.http`.

**Non-Goals:**
- No incluye modelos de tablas de negocio (editoriales, libros, etc.) que corresponden a changes posteriores.
- No incluye migraciones con Alembic (la cátedra especifica `SQLModel.metadata.create_all`).
- No incluye configuración de Docker ni despliegue en VPS (asignado al change C-07).

## Decisions

### Decision 1: Gestión de Ciclo de Vida con `lifespan` Asincrónico
- **Decisión**: Utilizar el manejador de contexto `@asynccontextmanager def lifespan(app: FastAPI)` en lugar de los eventos obsoletos `@app.on_event("startup")` y `@app.on_event("shutdown")`.
- **Razón**: `lifespan` es el estándar moderno en FastAPI 0.111+, asegura que los recursos de `app.state.engine` se inicialicen antes de que el servidor acepte peticiones y se liberen de forma determinística al cerrarse.
- **Alternativas consideradas**: Eventos de startup/shutdown (deprecados en FastAPI).

### Decision 2: `expire_on_commit=False` en Fábrica de Sesiones
- **Decisión**: Configurar `async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)`.
- **Razón**: En operaciones asincrónicas, si los atributos expiran al hacer `commit()`, cualquier acceso posterior genera una carga perezosa bloqueante que SQLAlchemy async rechaza con `MissingGreenlet`. Desactivar la expiración permite devolver entidades con sus relaciones precargadas de forma segura.

### Decision 3: Configuración Tipada con `pydantic-settings`
- **Decisión**: Crear una clase `Settings(BaseSettings)` en `app/core/config.py` con `model_config = SettingsConfigDict(env_file=".env", extra="ignore")`.
- **Razón**: Valida en tiempo de arranque que `DATABASE_URL` esté presente y tenga el formato adecuado, con defaults seguros para `SQL_ECHO` (false) y `APP_PORT` (8000).

### Decision 4: Separación de Liveness y Readiness
- **Decisión**: Implementar `/health/live` respondiendo `{ "estado": "vivo" }` de forma inmediata sin consultar la base de datos, y `/health/ready` ejecutando `await session.exec(text("SELECT 1"))`.
- **Razón**: Cumple con el estándar de orquestación de contenedores y los requisitos explícitos del Ejercicio 1 del parcial.

### Decision 5: UI Mockups
- **Decision**: `no (no UI)` — Proyecto de API REST backend sin interfaz gráfica.

## Risks / Trade-offs

- **[Riesgo: Formato de DATABASE_URL incorrecto]** → Si se usa `postgresql://` en lugar de `postgresql+asyncpg://`, SQLAlchemy intentará usar drivers síncronos bloqueantes.  
  *Mitigación*: Validar en `Settings` o helper que la URL utilice el driver asíncrono `postgresql+asyncpg://`.
- **[Riesgo: create_all síncrono en contexto asincrónico]** → `SQLModel.metadata.create_all` es una operación de metadatos síncrona.  
  *Mitigación*: Ejecutarla dentro de `async with engine.begin() as conn: await conn.run_sync(SQLModel.metadata.create_all)`.
