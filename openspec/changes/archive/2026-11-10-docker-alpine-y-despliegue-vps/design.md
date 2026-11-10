# Design: Contenedor Docker Alpine y Despliegue en VPS

## Context
Ver `proposal.md` §Why. Estado relevante del código hoy:

- `requirements.txt` mezcla runtime y pruebas (`pytest`, `pytest-asyncio`, `httpx`, `aiosqlite`). `httpx` sólo lo usan `tests/conftest.py` y `scripts/auditar_consultas.py`; ningún módulo de `app/` lo importa.
- `app/core/config.py` define `DATABASE_URL` con valor por defecto `postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/libreria_db` (credenciales embebidas, contradice el requisito "sin valores secretos predefinidos" de `core-infrastructure`) y lee `.env` del directorio de trabajo.
- `app/main.py` envuelve `create_all` del `lifespan` en `try/except Exception` y sólo imprime una advertencia: la app arranca aunque no haya base. KB 11 §Conectividad exige lo contrario.
- Las pruebas usan `httpx.ASGITransport`, que **no** ejecuta el `lifespan`; endurecerlo no afecta la suite existente. `tests/test_config.py::test_settings_cached_singleton` llama a `get_settings()` sin argumentos y hoy depende del valor por defecto.
- `app/initial_data.py` ya es ejecutable como módulo (`python -m app.initial_data`), idempotente, y devuelve 1 con un mensaje propio si la base es inaccesible.
- `/health/ready` ejecuta `SELECT 1` (200 / 500); `/health/live` no toca la base.
- Entorno de desarrollo detectado: Docker 29.8 disponible; en la máquina sólo está Python 3.13 (launcher `py`), sin `.venv` ni Python 3.12. Las pruebas locales pueden correr en 3.13; la imagen fija 3.12.
- No existen `Dockerfile`, `.dockerignore`, `DEPLOY.md` ni `README.md`.

## Goals / Non-Goals

**Goals:**
- Imagen final lo más chica posible sobre `python:3.12-alpine`, sin toolchain, sin dependencias de test, ejecutada como `appuser`.
- Invariantes del Dockerfile verificadas por pytest (TDD) y comportamiento de la imagen verificado con comandos `docker` reproducibles.
- Arranque fail-fast coherente con la política de reinicio de Docker.
- Un `DEPLOY.md` que cualquier integrante pueda seguir de punta a punta.

**Non-Goals:**
- `docker-compose`, CI/CD, TLS, reverse proxy, dominio, Alembic, backups.
- Garantizar que la **imagen final** pese menos de 100 MB: el requisito de la consigna es sobre la imagen **base**. El tamaño final se mide y se registra en `DEPLOY.md`.
- Múltiples workers de uvicorn o tuning de rendimiento.

## Decisions

### D1 — Build de una sola etapa, sólo wheels binarios (`--only-binary=:all:`)
Todas las dependencias de runtime publican wheels `musllinux` para CPython 3.12 en x86_64 y aarch64: `asyncpg` (≥ 0.29), `pydantic-core`, `greenlet` (3.x), y los extras de `uvicorn[standard]` (`uvloop`, `httptools`, `watchfiles`, `websockets`, `pyyaml`). Por eso se instala en una sola etapa:

```dockerfile
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --only-binary=:all: -r /tmp/requirements.txt && rm /tmp/requirements.txt
```

`--only-binary=:all:` convierte un wheel faltante en un **error explícito de build** en vez de un intento de compilación que falla con un mensaje confuso (no hay `gcc`) o que, si alguien agrega `build-base`, engorda la imagen silenciosamente.

- *Alternativa A — multi-stage* (etapa `builder` con `build-base` + `postgresql-dev` que genera wheels/venv y etapa final que sólo copia el resultado): robusta ante wheels faltantes, pero agrega complejidad sin beneficio hoy. **Queda como plan B documentado**: si el build de D1 falla por un wheel faltante, se aplica esta variante sin cambiar specs ni tasks (la imagen final sigue sin toolchain).
- *Alternativa B — instalar y borrar build deps en el mismo `RUN`* (`apk add --virtual .build-deps ... && pip install ... && apk del .build-deps`): funciona, pero es más frágil y más lenta que el multi-stage; descartada.
- *Alternativa C — `python:3.12-slim`*: descartada por DD-04 (base > 100 MB).

### D2 — `requirements.txt` sólo runtime + `requirements-dev.txt`
`requirements.txt` conserva: `fastapi`, `sqlmodel`, `asyncpg`, `uvicorn[standard]`, `pydantic-settings`, `greenlet`. `requirements-dev.txt` = `-r requirements.txt` + `pytest`, `pytest-asyncio`, `httpx`, `aiosqlite`. Mantiene el nombre que piden la consigna y `CHANGES.md` ("copia e instala `requirements.txt`") y deja la imagen sin herramientas de prueba. Alternativa descartada: un único archivo (imagen más pesada y con `pytest` en producción).

### D3 — Copia explícita de `app/` + `.dockerignore` amplio (defensa en profundidad)
El Dockerfile hace `COPY --chown=appuser:appuser app ./app` (nunca `COPY . .`), así un `.env` olvidado no puede entrar aunque falle el `.dockerignore`. El `.dockerignore` además reduce el contexto de build (los PDF de `docs/` y `Discovery/` pesan ~2 MB) y excluye: `.env`, `.env.*`, `!env.example`, `.venv`, `venv`, `.git`, `.gitignore`, `**/__pycache__`, `**/*.py[cod]`, `.pytest_cache`, `.coverage`, `htmlcov`, `evidencia/`, `tests/`, `test/`, `scripts/`, `docs/`, `Discovery/`, `knowledge-base/`, `openspec/`, `design-system/`, `.agents/`, `.claude/`, `.atl/`, `.engram/`, `*.md`, `Dockerfile`, `.dockerignore`.

### D4 — Estructura del Dockerfile
Orden de instrucciones (las pruebas de invariantes lo verifican):
1. `FROM python:3.12-alpine` (única etapa).
2. `ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1` (ningún `ENV` con datos de conexión).
3. `WORKDIR /app`.
4. `RUN addgroup -S appuser && adduser -S -G appuser -H -D appuser` (sintaxis busybox de Alpine).
5. `COPY requirements.txt /tmp/requirements.txt` + `RUN pip install --no-cache-dir --only-binary=:all: -r /tmp/requirements.txt && rm /tmp/requirements.txt`.
6. `COPY --chown=appuser:appuser app ./app`.
7. `USER appuser`.
8. `EXPOSE 8000`.
9. `HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD wget -qO- http://127.0.0.1:8000/health/ready || exit 1` (DD-05; `wget` de busybox viene en Alpine, no se instala `curl`). `start-period` sube de 5 s a 10 s para cubrir la conexión inicial a la base en un VPS chico.
10. `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]` (forma exec: uvicorn es PID 1 y recibe `SIGTERM` de `docker stop` para el apagado ordenado del `lifespan`).

El puerto interno queda fijo en 8000; `APP_PORT` sigue siendo informativo y el puerto público se elige con `-p <puerto>:8000`.

### D5 — Arranque fail-fast
- `config.py`: `DATABASE_URL: str` sin default (pydantic falla si falta). `env_file=".env"` se mantiene: en el contenedor no existe `.env` (D3) y las variables llegan por `--env-file`.
- `main.py`: el `lifespan` deja de atrapar el error de `create_all`; ante fallo hace `await engine.dispose()`, registra con `logging` un mensaje propio ("No se pudo conectar a la base de datos al iniciar; verifique DATABASE_URL") **sin** la URL, y relanza. Uvicorn aborta el arranque y sale con código ≠ 0.
- Con `--restart unless-stopped`, Docker reintenta con back-off exponencial: si la base tarda en levantar (p. ej. tras reboot del VPS), el contenedor termina arrancando solo; si la configuración es incorrecta, el problema es visible en `docker ps` (`Restarting`) y `docker logs`.
- Pruebas: el `lifespan` se prueba directamente (`async with lifespan(app)`) con un motor fallido simulado; `tests/conftest.py` fija `os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")` antes de importar la app, para que `get_settings()` siga funcionando en la suite sin `.env`.
- Alternativa descartada: mantener el arranque degradado y confiar sólo en el healthcheck. Contradice KB 11 y deja un contenedor "corriendo" que nunca podrá servir.

### D6 — Conectividad con PostgreSQL en el VPS (escenario por confirmar)
`localhost` dentro del contenedor es el contenedor. `DEPLOY.md` documenta el escenario real y deja los otros como referencia:

| Escenario | Host en `DATABASE_URL` | Flags extra de `docker run` | Requisitos en el servidor |
|---|---|---|---|
| A. PostgreSQL en el host del VPS | `host.docker.internal` | `--add-host=host.docker.internal:host-gateway` | `listen_addresses` incluye la IP del bridge (`172.17.0.1`) y `pg_hba.conf` permite la subred de Docker |
| B. PostgreSQL en otro contenedor | nombre del contenedor (p. ej. `libreria-db`) | `--network libreria-net` (red de usuario compartida) | volumen con nombre para los datos de PostgreSQL |
| C. Base provista por la cátedra / gestionada | IP o hostname provisto | ninguno | firewall abierto desde el VPS |

La elección **no** cambia specs ni tasks (sólo el contenido de `DEPLOY.md` y del `--env-file`), por eso queda como pregunta abierta diferible.

### D7 — Actualización en caliente sin pérdida de datos
Los datos viven en PostgreSQL, fuera del contenedor de la API; el contenedor es descartable y `create_all` sólo crea lo que falta (no borra ni altera tablas). Procedimiento:
1. `git pull` y `docker build -t libreria:<commit> -t libreria:latest .` (la imagen anterior queda como `libreria:<commit-anterior>`).
2. `docker stop libreria && docker rename libreria libreria-prev`.
3. `docker run -d --name libreria ... libreria:<commit>` con los mismos flags y `--env-file`.
4. Esperar `healthy`; validar `GET /health/ready` y un `GET /ventas/` con datos previos.
5. OK → `docker rm libreria-prev`. Falla → `docker rm -f libreria && docker rename libreria-prev libreria && docker start libreria`.

El corte es de segundos (stop → run). Se descarta blue/green con dos puertos y proxy: fuera de alcance para un único contenedor sin reverse proxy.

### D8 — Verificación: invariantes por pytest + comprobaciones Docker manuales
- `tests/test_contenedor.py` (TDD, corre sin Docker): parsea `Dockerfile`, `.dockerignore` y `requirements.txt` como texto y verifica D1–D4 (base, una sola etapa, `--no-cache-dir` y `--only-binary`, `COPY requirements.txt` antes de `COPY ... app`, sin `COPY . .`, `USER appuser` después del último `RUN` y antes de `CMD`, `EXPOSE 8000`, `HEALTHCHECK` con `127.0.0.1:8000/health/ready` y sin `localhost`, `CMD` exacto, sin `ENV`/`ARG` con `DATABASE_URL`/`PASSWORD`, `.dockerignore` con `.env`, `.venv`, `.git`, `__pycache__`, `*.pyc`, `evidencia/`, `.pytest_cache`, y `requirements.txt` sin `pytest`/`aiosqlite`/`httpx`).
- Comprobaciones de imagen con Docker (no se automatizan en pytest para no exigir Docker en la suite): build, tamaño base y final, usuario, `pip list`, contenido de `/app`, historial sin secretos, `healthy` con un PostgreSQL 16 en contenedor temporal, `unhealthy` al detenerlo, y salida ≠ 0 sin base. Resultados registrados en `DEPLOY.md` §Validación local.

## UI Mockups
- Design system revision: n/a (política del proyecto `visual_design.mode: off`)
- Decision: no (no UI) — 2026-11-09
- Mockups: n/a
- Approval: n/a
- Preview: n/a
- Visual verify: n/a

## Risks / Trade-offs
- [Un wheel `musllinux` falta para la versión resuelta o la arquitectura del VPS (p. ej. ARM)] → `--only-binary` lo hace fallar de forma explícita; aplicar el plan B multi-stage de D1. Verificar la arquitectura del VPS (`uname -m`) antes de construir.
- [`requirements.txt` con rangos `>=`: un build futuro resuelve versiones distintas] → se registra la salida de `pip freeze` de la imagen en `DEPLOY.md`; fijar versiones exactas queda opcional.
- [Fail-fast + `unless-stopped` → bucle de reinicios si la configuración es incorrecta] → visible en `docker ps`/`docker logs`; `DEPLOY.md` incluye la sección de diagnóstico.
- [El healthcheck usa `/health/ready`: una caída de la base marca el contenedor `unhealthy`, pero Docker no lo reinicia solo] → comportamiento deseado (no hay orquestador); se documenta.
- [Cambiar a `requirements-dev.txt` rompe el comando de setup habitual] → `README.md` lo documenta; la suite se valida con el nuevo comando.
- [`DATABASE_URL` obligatoria rompe `get_settings()` en pruebas sin `.env`] → `setdefault` en `conftest.py` (D5).
- [Puerto del VPS expuesto sin TLS] → aceptado para el ámbito académico; fuera de alcance.

## Migration Plan
1. Local: `pip install -r requirements-dev.txt`, suite en verde, `docker build`, validaciones de D8.
2. VPS: crear `.env.prod` (permisos `600`, fuera de git) con `DATABASE_URL` según D6; `docker build`; `docker run`; `docker exec libreria python -m app.initial_data`; validar desde fuera.
3. Registrar URL, fecha/hora y versión en `DEPLOY.md`; commit.
4. Rollback: ver D7 (la imagen anterior sigue etiquetada).

## Open Questions
Deferibles (no cambian specs, enfoque ni tasks; sólo completan `DEPLOY.md`/`README.md` y el `--env-file`):
Resueltas con datos del equipo (2026-11-10):
- VPS `46.202.151.202` (dominio `elgrupo3.tech`), Ubuntu 24.04 `x86_64`, Docker 29.7.1; compartido por tres grupos (Easypanel/Traefik en 80/443, 3000, Swarm 2377/7946). URL pública: `http://46.202.151.202:8001` (`-p 8001:8000`).
- PostgreSQL: escenario **B** de D6 en su variante dedicada: contenedor `libreria-db` (`postgres:16-alpine`), volumen con nombre `libreria-pgdata`, red de usuario `libreria-net`, sin puerto publicado. Host en `DATABASE_URL`: `libreria-db`. Credenciales sólo en `.env.prod`.
- La actualización y el rollback (D7) sólo tocan el contenedor `libreria`; `libreria-db` y su volumen no se modifican. Nunca se operan contenedores de otros grupos.

Pendiente (se completa al desplegar, grupo 6):
- (TBD) Fecha y hora real del despliegue (el reloj del servidor está en UTC) y versión desplegada.
