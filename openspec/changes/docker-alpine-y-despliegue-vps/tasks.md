# Tasks

> Modo TDD estricto (RED → GREEN → REFACTOR). Comando de pruebas: `.venv/Scripts/python -m pytest -q` (Windows) o `.venv/bin/python -m pytest -q`.
> Las tareas marcadas **[MANUAL-VPS]** requieren acceso del equipo al VPS y datos que sólo el usuario tiene (ver design.md §Open Questions); un agente no puede completarlas. Todo lo demás se hace en local.
> Governance ALTO: el agente de apply presenta el `Dockerfile`, el `.dockerignore` y los cambios de arranque antes de darlos por cerrados.

## 1. Entorno y dependencias

- [x] 1.1 Crear el entorno virtual (`py -3.12 -m venv .venv`; si Python 3.12 no está instalado usar `py -3.13` y anotarlo) e instalar con el `requirements.txt` actual. Safety net: ejecutar la suite y registrar la línea base de tests en verde. Verificación: salida de `pytest -q` sin fallos (cualquier fallo previo se reporta, no se corrige).
- [x] 1.2 RED: `tests/test_contenedor.py::test_requirements_runtime_sin_dependencias_de_test` — `requirements.txt` no contiene `pytest`, `pytest-asyncio`, `httpx` ni `aiosqlite`, y sí `fastapi`, `sqlmodel`, `asyncpg`, `uvicorn[standard]`, `pydantic-settings`, `greenlet`; `requirements-dev.txt` incluye `-r requirements.txt` y las cuatro de prueba. GREEN: separar los archivos (design.md D2). Verificación: `pip install -r requirements-dev.txt` en el `.venv` y suite completa en verde con la misma línea base.

## 2. Arranque fail-fast (core-infrastructure)

- [x] 2.1 RED: en `tests/test_config.py`, `Settings(_env_file=None)` sin `DATABASE_URL` en el entorno (`monkeypatch.delenv`) lanza `ValidationError`. GREEN: quitar el default de `DATABASE_URL` en `app/core/config.py` y agregar `os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")` al inicio de `tests/conftest.py` (design.md D5). Verificación: test nuevo en verde y `test_settings_cached_singleton` sigue en verde.
- [x] 2.2 RED: `tests/test_main.py` — con un `get_engine` simulado cuyo `begin()` falla (`OSError`/`SQLAlchemyError`), `async with lifespan(app)` propaga la excepción, llama a `dispose()` del motor y el mensaje registrado (`caplog`) no contiene la URL ni la contraseña. GREEN: quitar el `try/except` silencioso del `lifespan` según D5 (log propio + `dispose` + relanzar). Verificación: test en verde.
- [x] 2.3 Triangulación: con un motor que conecta (SQLite temporal), `async with lifespan(app)` crea las tablas, deja `app.state.engine` y llama a `dispose()` al salir. REFACTOR: reemplazar el `print` por `logging`. Verificación: suite completa en verde.

## 3. Dockerfile y .dockerignore

- [x] 3.1 RED: `tests/test_contenedor.py` con las invariantes de design.md D8 para el `Dockerfile` (base única `python:3.12-alpine`; `--no-cache-dir` y `--only-binary=:all:`; `COPY requirements.txt` antes del `COPY` de `app`; sin `COPY . .`; `adduser`/`addgroup` de `appuser`; `USER appuser` después del último `RUN` y antes de `CMD`; `EXPOSE 8000`; `HEALTHCHECK` con `http://127.0.0.1:8000/health/ready` y sin `localhost`; `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`; ningún `ENV`/`ARG` con `DATABASE_URL`, `PASSWORD` o `SECRET`). Al menos un caso negativo por invariante usando un Dockerfile de ejemplo en `tmp_path` (p. ej. con `localhost` o sin `USER`) para no escribir aserciones triviales. GREEN: escribir `Dockerfile` según D4. Verificación: tests en verde.
- [x] 3.2 RED: invariantes de `.dockerignore` (`.env`, `.env.*`, `.venv`, `.git`, `__pycache__`, `*.pyc`, `evidencia/`, `.pytest_cache`, `tests/`, `test/`, `docs/`, `Discovery/`, `openspec/`). GREEN: escribir `.dockerignore` según D3. Verificación: tests en verde.
- [x] 3.3 Build local: `docker build -t libreria .`. Verificación: build exitoso sin compilar nada (si falla por un wheel faltante, aplicar el plan B multi-stage de D1, ajustar el test de "una sola etapa" y documentarlo en design.md); `docker image inspect python:3.12-alpine --format '{{.Size}}'` < 100 MB; registrar el tamaño final de `libreria`.
- [x] 3.4 Inspección de la imagen: `docker image inspect libreria --format '{{.Config.User}}'` → `appuser`; `docker run --rm --entrypoint pip libreria list` sin `pytest`/`aiosqlite`; `docker run --rm --entrypoint ls libreria -a /app` sólo `app`; `docker history --no-trunc libreria` y `docker image inspect` sin `DATABASE_URL`; `docker run --rm --entrypoint sh libreria -c 'command -v gcc'` vacío. Con un `.env` de prueba en la raíz, rebuild y confirmar que no entra. Verificación: salidas anotadas para `DEPLOY.md` §Validación local.
- [x] 3.5 Caché de capas: tocar un comentario en `app/main.py`, reconstruir y confirmar `CACHED` en el paso de `pip install`; revertir el cambio. Verificación: salida del build.

## 4. Validación del contenedor con PostgreSQL local

- [x] 4.1 Levantar PostgreSQL 16 temporal en una red de usuario (`docker network create libreria-test`; `docker run -d --name libreria-db-test --network libreria-test -e POSTGRES_PASSWORD=<temporal> -e POSTGRES_DB=libreria_db postgres:16-alpine`) y un `.env.test` local (no versionado) con `DATABASE_URL=postgresql+asyncpg://postgres:<temporal>@libreria-db-test:5432/libreria_db`. Correr `docker run -d --name libreria --network libreria-test -p 8000:8000 --env-file .env.test libreria`. Verificación: `docker exec libreria id -un` → `appuser`; `GET http://127.0.0.1:8000/health/live` → 200; estado `healthy` tras el `start-period`.
- [x] 4.2 Seed en el contenedor: `docker exec libreria python -m app.initial_data` dos veces. Verificación: ambas con código 0, la segunda sin crear filas; `GET /libros/` devuelve 6 libros.
- [x] 4.3 Degradación y fail-fast: `docker stop libreria-db-test` → el contenedor pasa a `unhealthy` y `/health/ready` responde 500; luego `docker run --rm --network libreria-test --env-file .env.test libreria` con la base detenida termina con código ≠ 0 y `docker logs` muestra el mensaje propio sin la URL; sin `--env-file` también termina con código ≠ 0. Verificación: salidas anotadas.
- [x] 4.4 Ensayo del procedimiento de actualización D7 en local (con ventas creadas por `POST /ventas/`): build con nueva etiqueta, `rename` a `libreria-prev`, `run` nuevo, `healthy`, las ventas previas siguen en `GET /ventas/`; ensayar también el rollback. Limpiar contenedores, red y `.env.test`. Verificación: pasos ejecutados tal como quedarán escritos en `DEPLOY.md`.

## 5. Documentación

- [x] 5.1 `README.md` en la raíz: descripción del sistema, stack, integrantes, setup local (`venv`, `pip install -r requirements-dev.txt`, `.env` desde `env.example`, `uvicorn app.main:app --reload`), pruebas (`pytest -q`, `test/*.http`), seed, evidencia N+1 y validación del contenedor (comandos de la sección 4). Agregar a `env.example` un comentario sobre el host de `DATABASE_URL` dentro de un contenedor. Verificación: seguir el setup en un `.venv` limpio y que la suite pase; `grep` sin contraseñas reales.
- [x] 5.2 `DEPLOY.md` en la raíz con: URL pública `(TBD)`, fecha/hora con zona `(TBD)`, versión desplegada `(TBD)`, arquitectura del VPS, comandos exactos de `docker build` y `docker run -d --name libreria -p <puerto>:8000 --restart unless-stopped --env-file .env.prod libreria` (más los flags del escenario D6 elegido), contenido esperado de `.env.prod` sólo con nombres de variables, conectividad (tabla D6), carga inicial, actualización y rollback (D7), diagnóstico (`docker ps`, `docker logs`, `docker inspect ... Health`) y §Validación local con los resultados de las secciones 3 y 4. Verificación: cada comando de la sección 4 copiado de `DEPLOY.md` corre tal cual; ninguna credencial en el archivo.

## 6. Despliegue en el VPS

- [ ] 6.1 **[MANUAL-VPS]** En el VPS: verificar `docker --version` y `uname -m`; clonar o actualizar el repositorio; crear `.env.prod` con permisos `600` según el escenario D6 confirmado; `docker build -t libreria .`; `docker run` con los flags de `DEPLOY.md`. Verificación: `docker ps` muestra `libreria` `healthy`.
- [ ] 6.2 **[MANUAL-VPS]** `docker exec libreria python -m app.initial_data`; desde fuera del VPS: `GET <URL>/health/live`, `GET <URL>/health/ready` y `GET <URL>/libros/` → 200. Verificación: respuestas registradas.
- [ ] 6.3 Completar en `DEPLOY.md` la URL pública, la fecha y hora con zona horaria y la versión desplegada, y en `README.md` los integrantes; eliminar todos los `(TBD)`. Verificación: `grep -n "TBD" DEPLOY.md README.md` sin resultados.

## 7. Cierre

- [ ] 7.1 Suite completa en verde (línea base + tests nuevos) con `requirements-dev.txt`. Revisión de reglas duras sobre los archivos nuevos/tocados: base `python:3.12-alpine`, `USER appuser`, sin secretos en capas ni en docs, `HEALTHCHECK` contra `127.0.0.1:8000`, nada bloqueante agregado al código. Verificación: salida de `pytest -q` y `grep -rn "localhost" Dockerfile` sin resultados.

## Workflow follow-up

- Verificar con `openspec-verify` (incluye comprobar la URL pública en vivo) y archivar con `/opsx:archive docker-alpine-y-despliegue-vps`; marcar `[C-07]` en `CHANGES.md`.
- Hacer `engram sync` + commit de `.engram/` antes del push final (ver CLAUDE.md global), confirmando con el usuario si el repositorio es público.
