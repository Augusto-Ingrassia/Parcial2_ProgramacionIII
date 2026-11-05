# Proposal: Core Infrastructure and Health

## Why
Para iniciar el desarrollo del proyecto de la librería y satisfacer los requisitos del Ejercicio 1 de la cátedra de Programación III, es necesario establecer los cimientos arquitectónicos del backend: estructura modular de directorios, configuración asincrónica del motor de base de datos con SQLAlchemy 2.0 / SQLModel y PostgreSQL (asyncpg), ciclo de vida (`lifespan`) de FastAPI con creación automática de tablas al arrancar, y endpoints de salud (`/health/live` y `/health/ready`) para supervisión y monitoreo operativo.

## What Changes
- Creación de la estructura modular del proyecto en `app/core/`, `app/modules/health/` y `test/`.
- Configuración de dependencias base en `requirements.txt` (`fastapi`, `sqlmodel`, `asyncpg`, `uvicorn[standard]`, `pydantic-settings`).
- Módulo de configuración tipada en `app/core/config.py` para variables de entorno (`DATABASE_URL`, `SQL_ECHO`, `APP_PORT`) con plantilla `env.example`.
- Módulo de base de datos en `app/core/database.py`: motor asincrónico `create_async_engine`, generador de sesiones `async_sessionmaker` con `expire_on_commit=False` y dependencia `get_session`.
- Gestión de ciclo de vida en `app/main.py`: `lifespan` asincrónico que ejecuta `SQLModel.metadata.create_all` al inicio, guarda el motor en `app.state`, y ejecuta `await engine.dispose()` al cerrar.
- Módulo `health` en `app/modules/health/` con endpoints:
  - `GET /health/live`: responde `200 OK` con `{"estado": "vivo"}` sin interactuar con la base de datos (liveness).
  - `GET /health/ready`: ejecuta `SELECT 1` asincrónico sobre PostgreSQL y responde `200 OK` con estado de la base o propaga error si la conexión falla (readiness).
- Suite de pruebas de verificación HTTP en `test/health.http`.

## Capabilities

### New Capabilities
- `health`: Endpoints de monitoreo y verificación de salud de la aplicación (`GET /health/live`) y de conectividad con PostgreSQL (`GET /health/ready`).
- `core-infrastructure`: Configuración asincrónica del motor y sesiones con `SQLModel`/`asyncpg`, ciclo de vida `lifespan` de FastAPI, y lectura de variables de entorno tipadas.

### Modified Capabilities
*(Ninguna; es el primer change del proyecto)*

## Impact
- **APIs**: Se exponen las primeras rutas públicas `/health/live` y `/health/ready`.
- **Dependencias**: Se definen las librerías base del backend en `requirements.txt`.
- **Estructura**: Se inicializa el árbol de directorios `app/` que servirá de molde para todos los módulos de dominio subsiguientes.
