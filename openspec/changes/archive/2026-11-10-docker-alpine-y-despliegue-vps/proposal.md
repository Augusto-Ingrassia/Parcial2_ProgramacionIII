# Proposal: Contenedor Docker Alpine y Despliegue en VPS

## Why
Con C-01 a C-06 archivados, la API cumple todo el dominio y está probada, pero todavía no es entregable: faltan los Ejercicios 7 y 8 de la consigna (`CHANGES.md` §C-07, Fase 5, último change del camino crítico). No existe `Dockerfile`, `.dockerignore`, `DEPLOY.md` ni `README.md`, y la API no está publicada en el VPS. Además, el arranque actual contradice la KB 11 §Conectividad: `app/main.py` atrapa cualquier error de conexión en el `lifespan` y sigue atendiendo, y `app/core/config.py` trae un `DATABASE_URL` por defecto con credenciales (`postgres:postgres@127.0.0.1`). Dentro de un contenedor, `127.0.0.1` es el propio contenedor: la app arrancaría "sana" a nivel de proceso apuntando a una base inexistente, en estado inconsistente.

## What Changes
- **`Dockerfile`** sobre `python:3.12-alpine` (base < 100 MB): dependencias antes que el código (caché de capas, `--no-cache-dir`, sólo wheels binarios), copia explícita de `app/` únicamente, usuario y grupo sin privilegios `appuser` con `USER appuser`, `EXPOSE 8000`, `HEALTHCHECK` con `wget -qO- http://127.0.0.1:8000/health/ready`, y `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`. Ningún secreto, `ENV DATABASE_URL` ni `.env` en capas.
- **`.dockerignore`**: excluye `.env*` (salvo `env.example`), `.venv`/`venv`, `.git`, `__pycache__`, `*.pyc`, `.pytest_cache`, `evidencia/`, y todo lo que no es código de ejecución (`tests/`, `test/`, `scripts/`, `docs/`, `Discovery/`, `knowledge-base/`, `openspec/`, `design-system/`, `.agents/`, `.claude/`, `.atl/`).
- **Separación de dependencias**: `requirements.txt` queda sólo con lo necesario en ejecución (FastAPI, SQLModel, asyncpg, uvicorn[standard], pydantic-settings, greenlet); las herramientas de prueba (`pytest`, `pytest-asyncio`, `httpx`, `aiosqlite`) pasan a `requirements-dev.txt` (que incluye `-r requirements.txt`). La imagen no carga dependencias de test.
- **Arranque fail-fast** (**BREAKING** para quien dependa del valor por defecto): `DATABASE_URL` pasa a ser obligatoria (sin valor por defecto con credenciales) y el `lifespan` deja de tragarse el error de conexión: si la base no es accesible, el proceso termina con un mensaje propio sin exponer la URL ni la contraseña, y el contenedor se detiene (o se reinicia según `--restart`) en lugar de quedar atendiendo.
- **Verificación automatizada de invariantes** (`tests/test_contenedor.py`): pytest que lee `Dockerfile`, `.dockerignore` y `requirements.txt` y verifica imagen base, usuario no-root, healthcheck por IPv4, orden de capas, ausencia de secretos y de dependencias de test.
- **`DEPLOY.md`**: URL pública, fecha y hora del despliegue, comandos exactos de `docker build` / `docker run --env-file .env.prod` (sin contraseñas), conectividad con PostgreSQL según dónde corra, carga de datos con `docker exec libreria python -m app.initial_data`, y procedimiento de actualización en caliente sin pérdida de datos con rollback.
- **`README.md`** en la raíz: descripción del sistema, integrantes, setup local, ejecución de tests y validación del contenedor.
- **Despliegue real en el VPS** (acción manual del equipo) y registro del resultado en `DEPLOY.md`.

## Capabilities

### New Capabilities
- `contenedor-docker`: imagen de ejecución de la API — base Alpine liviana, ejecución sin privilegios, configuración inyectada sólo en tiempo de ejecución, contexto de build sin secretos, healthcheck de readiness y escucha en `0.0.0.0:8000`.
- `despliegue-vps`: operación documentada de la API en producción — URL pública y registro del despliegue, comandos reproducibles, carga inicial de datos en el contenedor, actualización sin pérdida de datos y documentación de ejecución del repositorio.

### Modified Capabilities
- `core-infrastructure`: el requisito de ciclo de vida agrega el escenario de arranque fallido (sin base accesible el proceso termina, no queda atendiendo) y el requisito de configuración exige `DATABASE_URL` explícita (sin valor por defecto con credenciales).

## Impact
- **Archivos nuevos**: `Dockerfile`, `.dockerignore`, `requirements-dev.txt`, `DEPLOY.md`, `README.md`, `tests/test_contenedor.py`.
- **Archivos tocados**: `requirements.txt` (sólo runtime), `app/main.py` (`lifespan` fail-fast), `app/core/config.py` (`DATABASE_URL` obligatoria), `tests/test_config.py` y tests nuevos del `lifespan`, `env.example` (comentarios de host para contenedor), `CHANGES.md` (marcar C-07 al archivar).
- **APIs / esquema**: sin cambios. Ningún endpoint nuevo ni columna nueva.
- **Operación**: el setup local pasa a `pip install -r requirements-dev.txt`; arrancar sin `DATABASE_URL` o sin base accesible ahora falla en vez de arrancar degradado.
- **Dependencias externas**: Docker en la máquina de build y en el VPS; PostgreSQL 16 accesible desde el contenedor (ubicación por confirmar).
- **Fuera de alcance**: `docker-compose`, CI/CD, TLS/reverse proxy (Nginx/Caddy), dominio propio, migraciones con Alembic, orquestadores, backups de la base.
