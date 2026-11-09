# Tasks

> Modo TDD estricto: cada tarea de implementación se ejecuta como ciclo RED → GREEN → TRIANGULATE → REFACTOR. Primero se escribe el test indicado y se confirma que falla; recién entonces se escribe el código mínimo. Los tests de API usan las fixtures de `tests/conftest.py` (SQLite `aiosqlite` + override de `get_session`), ver design.md Decisión 10.

## 1. Entorno y red de seguridad

- [x] 1.1 Agregar `aiosqlite>=0.20.0` a `requirements.txt`, instalar dependencias con `pip install -r requirements.txt` y verificar que `python -c "import sqlmodel, asyncpg, aiosqlite, pytest_asyncio"` termina sin error.
- [x] 1.2 Ejecutar `pytest` y registrar el baseline de C-01 (se esperan 9 tests pasando en `tests/test_config.py`, `tests/test_database.py`, `tests/test_health.py`); si alguno falla, detenerse y reportarlo como falla preexistente.

## 2. Piezas transversales en `app/core/`

- [x] 2.1 RED: crear `tests/test_pagination.py` montando una app FastAPI mínima con un endpoint que use `PaginationDep` y afirmar: sin parámetros → `limit=20, offset=0`; `limit=100&offset=5` aceptado; `limit=0`, `limit=101` y `offset=-1` → `422`. GREEN: implementar `app/core/pagination.py` (`PaginationParams`, `get_pagination`, `PaginationDep`) y verificar que `pytest tests/test_pagination.py` pasa.
- [x] 2.2 RED: crear `tests/test_validation.py` con un modelo de prueba que use `NonEmptyStr` y afirmar que `" Planeta "` se normaliza a `"Planeta"`, y que `""`, `"   "` y una cadena de 256 caracteres lanzan `ValidationError`. GREEN: implementar `app/core/validation.py` con el alias `NonEmptyStr` y verificar que el test pasa.
- [x] 2.3 RED: crear `tests/test_exceptions.py` con una app FastAPI mínima que registre `register_exception_handlers` y tenga un endpoint que lance `sqlalchemy.exc.IntegrityError("INSERT ...", {}, Exception("duplicate key value violates unique constraint \"x_key\""))`; afirmar `409` y que `detail` no contiene `duplicate key`, `constraint`, `x_key` ni `IntegrityError`. GREEN: implementar `app/core/exceptions.py` y verificar que el test pasa.
- [x] 2.4 Agregar el alias `SessionDep = Annotated[AsyncSession, Depends(get_session)]` en `app/core/database.py` y verificar que `pytest tests/test_database.py` sigue en verde.
- [x] 2.5 Crear `tests/conftest.py` con las fixtures `db_engine` (SQLite temporal en `tmp_path` con `SQLModel.metadata.create_all`), `client` (`AsyncClient` + `ASGITransport` con override de `get_session` y limpieza de `dependency_overrides` y del motor) y verificar que `pytest tests/test_health.py` sigue pasando sin cambios.

## 3. Módulo `editoriales`

- [x] 3.1 RED: crear `tests/test_editoriales.py` con un test que afirme que `SQLModel.metadata.tables["editorial"]` existe con columnas `id`, `nombre` (unique, not null) y `pais` (not null). GREEN: crear `app/modules/editoriales/__init__.py` y `models.py` con `Editorial(table=True)`, `__tablename__ = "editorial"`; verificar que el test pasa.
- [x] 3.2 RED: tests de DTOs en `tests/test_editoriales.py`: `EditorialCreate` exige `nombre` y `pais` no vacíos e ignora `id`; `EditorialUpdate` acepta `{}` y campos parciales, y rechaza `{"nombre": null}` con `ValidationError`. GREEN: implementar `app/modules/editoriales/schemas.py` (`EditorialCreate`, `EditorialRead`, `EditorialUpdate` con validador de `null` explícito) y verificar que los tests pasan.
- [x] 3.3 RED: tests HTTP de `POST /editoriales/`: alta exitosa `201` con `id`; `422` sin `pais` y con `nombre` en blanco; nombre duplicado → `409` con `detail` propio sin términos internos (`UNIQUE`, `IntegrityError`, `duplicate key`, `constraint`); y una segunda alta válida tras el `409` responde `201`. GREEN: implementar `crear_editorial` en `service.py` (commit con `try/except IntegrityError` + `rollback` + `HTTPException(409)`), la ruta en `router.py`, registrar router y `register_exception_handlers` en `app/main.py`; verificar que `pytest tests/test_editoriales.py` pasa.
- [x] 3.4 RED: tests de `GET /editoriales/`: con 25 editoriales y sin parámetros devuelve 20 en orden ascendente de `id`; `?limit=10&offset=20` devuelve 5; sin datos devuelve `[]`; `limit=0`, `limit=101`, `offset=-1` → `422`. GREEN: implementar `listar_editoriales` (`order_by(id).offset().limit()`) y la ruta con `PaginationDep`; verificar que los tests pasan.
- [x] 3.5 RED: tests de `GET /editoriales/{id}`: existente → `200` con `id`, `nombre`, `pais`; inexistente (`999`) → `404` con `detail` propio. GREEN: implementar `obtener_editorial` y la ruta; verificar que los tests pasan.
- [x] 3.6 RED: tests de `PATCH /editoriales/{id}`: actualizar solo `pais` conserva `nombre`; `{}` → `200` sin cambios; reenviar el propio nombre → `200`; renombrar a un nombre de otra editorial → `409` y el nombre original se conserva (verificado con un `GET` posterior); `{"nombre": null}` y `{"pais": ""}` → `422`; id inexistente → `404`. GREEN: implementar `actualizar_editorial` (`model_dump(exclude_unset=True)` + commit con manejo de `IntegrityError`) y la ruta; verificar que `pytest tests/test_editoriales.py` pasa completo.
- [x] 3.7 Crear `test/editoriales.http` (mismo formato que `test/health.http`) con alta exitosa, alta duplicada (409), listado por defecto, paginación válida, paginación inválida (422), consulta existente/inexistente (200/404), PATCH parcial, PATCH con colisión (409) y PATCH inexistente (404), documentando en comentarios el código esperado de cada petición; verificar que cada petición de la spec `editoriales` tiene su caso.

## 4. Módulo `generos`

- [x] 4.1 RED: crear `tests/test_generos.py` afirmando que `SQLModel.metadata.tables["genero"]` existe con `nombre` unique/not null, y que `GeneroCreate` rechaza `nombre` vacío o en blanco. GREEN: crear `app/modules/generos/__init__.py`, `models.py` (`Genero`, `__tablename__ = "genero"`) y `schemas.py` (`GeneroCreate`, `GeneroRead`); verificar que los tests pasan.
- [x] 4.2 RED: tests de `POST /generos/`: `201` con `id`; `{}` y nombre en blanco → `422`; duplicado → `409` sin términos internos; alta válida posterior al `409` → `201`. GREEN: implementar `crear_genero` en `service.py`, la ruta en `router.py` y registrar el router en `app/main.py`; verificar que los tests pasan.
- [x] 4.3 RED: tests de `GET /generos/`: con 3 géneros devuelve los 3 en orden de `id`; `?limit=1&offset=1` devuelve solo el segundo; `limit=0`, `limit=101`, `offset=-1` → `422`. GREEN: implementar `listar_generos` y la ruta con `PaginationDep`; verificar que los tests pasan.
- [x] 4.4 RED: tests de `GET /generos/{id}`: existente → `200`; inexistente → `404` con `detail` propio. GREEN: implementar `obtener_genero` y la ruta; verificar que `pytest tests/test_generos.py` pasa completo.
- [x] 4.5 Crear `test/generos.http` con alta exitosa, alta duplicada (409), alta inválida (422), listado y paginación (incluido un caso 422), consulta existente/inexistente (200/404), con el código esperado documentado en comentarios.

## 5. Módulo `autores`

- [x] 5.1 RED: crear `tests/test_autores.py` afirmando que `SQLModel.metadata.tables["autor"]` existe con `nombre` y `nacionalidad` not null y **sin** restricción unique en `nombre`; y que `AutorCreate` exige ambos campos no vacíos y `AutorUpdate` rechaza `null` explícito. GREEN: crear `app/modules/autores/__init__.py`, `models.py` (`Autor`, `__tablename__ = "autor"`) y `schemas.py` (`AutorCreate`, `AutorRead`, `AutorUpdate`); verificar que los tests pasan.
- [x] 5.2 RED: tests de `POST /autores/`: `201` con `id`; dos autores con el mismo nombre → ambos `201` con `id` distintos; sin `nacionalidad` o con `nombre` en blanco → `422`. GREEN: implementar `crear_autor` en `service.py`, la ruta en `router.py` y registrar el router en `app/main.py`; verificar que los tests pasan.
- [x] 5.3 RED: tests de `GET /autores/`: con 2 autores devuelve ambos en orden de `id`; con 3 autores `?limit=2&offset=2` devuelve solo el tercero; `limit=0`, `limit=101`, `offset=-1` → `422`. GREEN: implementar `listar_autores` y la ruta con `PaginationDep`; verificar que los tests pasan.
- [x] 5.4 RED: tests de `GET /autores/{id}`: existente → `200`; inexistente → `404` con `detail` propio. GREEN: implementar `obtener_autor` y la ruta; verificar que los tests pasan.
- [x] 5.5 RED: tests de `PATCH /autores/{id}`: actualizar solo `nombre` conserva `nacionalidad`; `{"nacionalidad": null}` y `{"nombre": "   "}` → `422`; id inexistente → `404`. GREEN: implementar `actualizar_autor` (`exclude_unset`) y la ruta; verificar que `pytest tests/test_autores.py` pasa completo.
- [x] 5.6 Crear `test/autores.http` con alta exitosa, alta con nombre repetido (201), alta inválida (422), listado y paginación (incluido un caso 422), consulta existente/inexistente (200/404), PATCH parcial y PATCH inexistente (404), con el código esperado documentado en comentarios.

## 6. Integración

- [x] 6.1 RED: crear `tests/test_main.py` que importe `app.main` y afirme que `SQLModel.metadata.tables` contiene `editorial`, `genero` y `autor`, y que el esquema OpenAPI (`app.openapi()["paths"]`) incluye `/editoriales/`, `/editoriales/{id}`, `/generos/`, `/generos/{id}`, `/autores/`, `/autores/{id}` y ninguna operación `delete`. GREEN: completar los imports explícitos de modelos en `app/main.py` (Decisión 8) si faltara alguno; verificar que el test pasa.
- [x] 6.2 Ejecutar la suite completa con `pytest` y verificar que todos los tests pasan (baseline de C-01 + nuevos), sin warnings de `MissingGreenlet` ni `PendingRollbackError`.
- [x] 6.3 Levantar la API contra PostgreSQL 16 (`uvicorn app.main:app` con `DATABASE_URL` real), confirmar que el `lifespan` crea las tablas `editorial`, `genero` y `autor`, y ejecutar `test/editoriales.http`, `test/generos.http` y `test/autores.http` verificando que cada respuesta coincide con el código documentado y que ningún `409` expone nombres de restricciones de PostgreSQL. Si no hay PostgreSQL disponible, dejar la tarea abierta y reportarlo.

## Workflow follow-up

- Archivar el change con `/opsx:archive catalogos-base-editoriales-generos-autores` una vez revisado.
- Marcar `[C-02]` como `[x]` en `CHANGES.md`.
- Considerar un change menor para que `/health/ready` no exponga `str(exc)` en el `503` (RN-12), detectado durante este diseño.
