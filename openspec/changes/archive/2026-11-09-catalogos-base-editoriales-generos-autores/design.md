# Design: Catálogos Base — Editoriales, Géneros y Autores

## Context
C-01 dejó operativa la infraestructura: `app/core/config.py`, `app/core/database.py` (motor `create_async_engine`, `async_sessionmaker(expire_on_commit=False)` y `get_session`, que entrega una `sqlalchemy.ext.asyncio.AsyncSession`), `app/main.py` con `lifespan` que ejecuta `SQLModel.metadata.create_all`, y el módulo `health`. Ver `proposal.md` (Why) para la motivación y `specs/{editoriales,generos,autores}/spec.md` para el contrato observable.

Restricciones que condicionan el diseño:
- Reglas duras del proyecto (`CLAUDE.md`): asincronía pura, integridad delegada en la base (sin `SELECT` previo para detectar duplicados), `IntegrityError` → `409` sin filtrar internos (RN-12), paginación RN-10.
- `create_all` solo crea las tablas de los modelos que fueron **importados** antes de ejecutarse el `lifespan`.
- Los tests de C-01 usan `pytest` + `pytest-asyncio` + `httpx.ASGITransport` con una base SQLite temporal (`sqlite+aiosqlite`) inyectada vía `app.dependency_overrides[get_session]`. `ASGITransport` **no** ejecuta el `lifespan`, así que los tests deben crear el esquema por su cuenta.
- El intérprete local (Python 3.13) no tiene instalados `sqlmodel`, `asyncpg` ni `pytest-asyncio`; `aiosqlite` sí está instalado pero no figura en `requirements.txt`.

## Goals / Non-Goals

**Goals:**
- Fijar el molde de módulo de dominio (`models.py` / `schemas.py` / `service.py` / `router.py`) que replicarán C-03, C-04 y C-05.
- Centralizar la paginación RN-10 y la red de seguridad de RN-12 en `app/core/` para reutilizarlas sin duplicación.
- Dejar cada endpoint cubierto por tests automatizados (TDD estricto) más archivos `.http` para verificación manual contra PostgreSQL.

**Non-Goals:**
- Relaciones ORM hacia `Libro` / `LibroAutor` (`Editorial.libros`, `Genero.libros`, `Autor.autorias`) y endpoints `/{id}/libros`: los agrega C-03, cuando esos modelos existan. Declararlos ahora rompería el mapeo de SQLAlchemy al no poder resolver `"Libro"`.
- Endpoints `DELETE` (ninguna entidad los requiere en v1) y `PATCH /generos/{id}`.
- Unicidad case-insensitive de nombres (ver Decisión 9).
- Migraciones (Alembic): se mantiene `create_all`, como en C-01.
- Corregir el `detail` del 503 de `/health/ready`, que hoy incluye `str(exc)` (ver Riesgos).

## Decisions

### Decisión 1: Estructura modular por dominio
- **Decisión**: Cada dominio vive en `app/modules/<dominio>/` con `__init__.py`, `models.py` (tabla SQLModel), `schemas.py` (DTOs), `service.py` (funciones `async` que reciben la `AsyncSession`) y `router.py` (`APIRouter(prefix="/<dominio>", tags=[...])`). Los routers declaran las rutas raíz como `"/"` para coincidir exactamente con `/editoriales/`, etc.
- **Razón**: Estructura obligatoria de la cátedra (`knowledge-base/08_arquitectura_propuesta.md`). El servicio con funciones planas (no clases) sigue la skill `fastapi-python` (estilo funcional, RORO) y facilita testear la lógica sin HTTP.
- **Alternativas**: Repositorio + servicio en clases (más ceremonia sin beneficio en un CRUD de 2-3 campos).

### Decisión 2: Modelos de tabla separados de los DTOs
- **Decisión**: `models.py` define solo la clase `table=True` con `__tablename__` explícito (`editorial`, `genero`, `autor`), `id: int | None = Field(default=None, primary_key=True)` y los campos `str` NOT NULL; `nombre` de editorial y género con `Field(unique=True)`. `schemas.py` declara los DTOs de forma independiente (`XCreate`, `XRead`, `XUpdate`) como `SQLModel` sin `table=True`.
- **Razón**: Desacopla contrato HTTP y esquema físico (patrón exigido por la KB); el DTO de entrada no tiene `id`, por lo que un `id` enviado por el cliente se ignora (extra ignorado por defecto). La duplicación es de 1–2 campos por entidad y se acepta a cambio del desacople.
- **Alternativas**: Herencia `XBase → X(table=True)` / `XCreate(XBase)` (patrón de la documentación de SQLModel): menos líneas, pero mezcla validaciones de entrada con la definición de la tabla.
- **Nota de tipos**: `id` como `int` (`SERIAL`/`INTEGER`) según el diccionario de datos de la KB; la skill `postgresql-table-design` recomienda `BIGINT IDENTITY`, pero el volumen académico no lo justifica. Los `str` sin longitud se mapean a `VARCHAR` sin límite (equivalente a `TEXT` en PostgreSQL), alineado con la skill.

### Decisión 3: Validación de cadenas en los DTOs
- **Decisión**: Un alias de tipo reutilizable `NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]` (en `app/core/validation.py`, ver Decisión 6) para todos los campos de texto de entrada. Vacíos o solo espacios → `422`.
- **Razón**: La columna es NOT NULL pero la base aceptaría `""`; rechazarlo en el DTO evita datos basura sin consultar la base. `max_length=255` es un tope defensivo de payload, no una restricción de la tabla.
- **Supuesto registrado**: se recortan espacios iniciales/finales antes de persistir (`" Planeta "` se guarda como `"Planeta"`).

### Decisión 4: Semántica de PATCH (`exclude_unset` + rechazo de `null`)
- **Decisión**: `EditorialUpdate` y `AutorUpdate` declaran todos sus campos como `NonEmptyStr | None = None`; un `model_validator(mode="after")` rechaza con `422` cualquier campo **enviado explícitamente** con `null` (usando `model_fields_set`). El servicio aplica `data = payload.model_dump(exclude_unset=True)` y `obj.sqlmodel_update(data)` (o `setattr` por campo). `{}` devuelve la entidad sin cambios con `200`.
- **Razón**: Sin el validador, `{"nombre": null}` llegaría a la base y violaría NOT NULL, terminando en un `409` confuso. Ignorar el `null` en silencio (`exclude_none`) sería sorprendente para el cliente.
- **Alternativas**: `exclude_none=True` (oculta errores del cliente); dejar que la base falle (código HTTP incorrecto).

### Decisión 5: Dónde vive el manejo de `IntegrityError` (RN-12)
- **Decisión** (dos capas):
  1. **Servicio (capa principal)**: `crear_editorial`, `actualizar_editorial` y `crear_genero` envuelven `await session.commit()` en `try/except IntegrityError`; en el `except` ejecutan `await session.rollback()` y lanzan `HTTPException(409, detail="Ya existe una editorial con ese nombre")` (análogo para género). No se inspecciona el nombre de la restricción: en estas tablas la única restricción que el DTO no cubre es el `UNIQUE` de `nombre`, así que el mensaje específico es siempre correcto.
  2. **Red de seguridad global**: `app/core/exceptions.py` expone `register_exception_handlers(app)`, que registra un handler para `sqlalchemy.exc.IntegrityError` respondiendo `409 {"detail": "La operación entra en conflicto con datos existentes"}`; se invoca en `app/main.py`. Cubre cualquier `IntegrityError` que un servicio no capture (p. ej. en `autores`, que no tiene `UNIQUE`, o en futuros módulos).
- **Razón**: El mensaje específico por dominio es más útil para el cliente; el handler global garantiza RN-12 aunque un servicio olvide el `try`. Lanzar `HTTPException` desde el servicio acopla levemente el servicio a HTTP, pero es el patrón que la KB describe ("`service.py` y exception handlers") y evita una jerarquía de excepciones de dominio para tres entidades.
- **Rollback**: tras un `IntegrityError` la sesión queda en estado inválido; el `rollback()` explícito la deja reutilizable dentro de la misma petición. En el caso del handler global, la sesión se cierra (y revierte) al finalizar la dependencia `get_session`. El escenario "la API sigue operativa tras un conflicto" de los specs verifica que el pool no queda contaminado.
- **Sin SELECT previo**: no se consulta si el nombre existe antes de insertar (regla dura 4); la carrera entre dos altas concurrentes la resuelve el `UNIQUE`.
- **Alternativas**: Solo handler global (mensaje genérico idéntico para toda la API); solo `try/except` por servicio (sin red de seguridad).

### Decisión 6: Paginación RN-10 como dependencia compartida
- **Decisión**: `app/core/pagination.py` define un `@dataclass PaginationParams(limit, offset)` construido por una dependencia con `limit: Annotated[int, Query(ge=1, le=100)] = 20` y `offset: Annotated[int, Query(ge=0)] = 0`, expuesta como alias `PaginationDep = Annotated[PaginationParams, Depends(get_pagination)]`. Los servicios de listado reciben `limit`/`offset` y ejecutan `select(X).order_by(X.id).offset(offset).limit(limit)`.
- **Razón**: Un único punto de verdad para RN-10 reutilizado por libros, clientes y ventas; FastAPI devuelve `422` automáticamente fuera de rango. `ORDER BY id` hace la paginación determinista (sin orden explícito PostgreSQL no garantiza el orden entre páginas). El alias `Annotated` sigue la skill `fastapi`.
- **Formato de respuesta**: arreglo JSON plano (`list[XRead]`), sin envoltorio `{items, total}`: la KB y RN-11 hablan de devolver `[]` cuando no hay resultados.
- **Ubicación de `NonEmptyStr`**: `app/core/validation.py`, también transversal.

### Decisión 7: Sesión y acceso a datos
- **Decisión**: Alias `SessionDep = Annotated[AsyncSession, Depends(get_session)]` agregado en `app/core/database.py`. Como `get_session` entrega una `AsyncSession` de SQLAlchemy (no la de SQLModel), las lecturas usan `await session.execute(stmt)` + `.scalars().all()` y la consulta por id `await session.get(X, id)`. Las altas hacen `session.add(obj)` + `await session.commit()`; con `expire_on_commit=False` y el PK ya poblado en el flush (`INSERT ... RETURNING`), no hace falta `refresh` para serializar la respuesta.
- **Razón**: Todo `async def` sin I/O bloqueante (regla dura 1). No hay relaciones que cargar en este change, por lo que no aplica `joinedload`/`selectinload` todavía.
- **404**: el servicio de consulta devuelve `None` y el router (o un helper `obtener_o_404`) lanza `HTTPException(404, "Editorial no encontrada")`. El `id` de ruta es `int` sin restricción de rango: ids `≤ 0` responden `404`.

### Decisión 8: Registro de modelos y routers en `app/main.py`
- **Decisión**: `app/main.py` importa los tres routers e invoca `app.include_router(...)` para cada uno, y además importa explícitamente los módulos `models` (`from app.modules.editoriales import models as _editoriales_models  # noqa: F401`, etc.) antes de definir el `lifespan`.
- **Razón**: Aunque los routers ya importan transitivamente los modelos (router → service → models), el import explícito documenta la intención y protege `create_all` frente a refactors que corten esa cadena.

### Decisión 9: Unicidad sensible a mayúsculas
- **Decisión**: El `UNIQUE` es el estándar de PostgreSQL (sensible a mayúsculas): `"Planeta"` y `"planeta"` son nombres distintos.
- **Razón**: Es lo que pide literalmente el diccionario de datos. Hacerlo insensible requeriría `CITEXT` o un índice único sobre `LOWER(nombre)` (skill `postgresql-table-design`), que además no se comporta igual en SQLite de tests. **A revisar por el usuario** si se desea normalización.

### Decisión 10: Estrategia de pruebas
- **Decisión**: `tests/conftest.py` nuevo con fixtures compartidas: motor `sqlite+aiosqlite` en `tmp_path`, creación del esquema con `SQLModel.metadata.create_all` (importando los modelos), override de `get_session` y un `AsyncClient` (`ASGITransport`) que limpia `dependency_overrides` al terminar. Un archivo por módulo (`tests/test_editoriales.py`, `test_generos.py`, `test_autores.py`) más `tests/test_pagination.py` y `tests/test_exceptions.py` para las piezas de `app/core/`. Se agrega `aiosqlite` a `requirements.txt`.
- **Razón**: Mantiene el patrón de C-01 y no requiere un PostgreSQL local para correr la suite. SQLite sí aplica `UNIQUE` y lanza `IntegrityError`, por lo que el camino `409` se ejerce de verdad. La verificación contra PostgreSQL real queda en los archivos `test/*.http`.
- **Aserción RN-12**: los tests de `409` verifican que `detail` no contenga `UNIQUE`, `IntegrityError`, `duplicate key`, `constraint` ni el nombre de la restricción.

### Decisión 11: UI Mockups
- **Decisión**: `no (no UI)` — API REST backend sin interfaz gráfica.

## Risks / Trade-offs

- **[Riesgo: SQLite ≠ PostgreSQL en tests]** → Los mensajes de `IntegrityError` y algunos tipos difieren entre motores. *Mitigación*: los tests solo afirman código HTTP y ausencia de términos internos en `detail` (válido en ambos motores); los `.http` se ejecutan contra PostgreSQL 16 antes de archivar.
- **[Riesgo: dependencias no instaladas localmente]** → `sqlmodel`, `asyncpg` y `pytest-asyncio` no están en el intérprete actual, por lo que la red de seguridad (tests de C-01) no corre hoy. *Mitigación*: la primera tarea instala `requirements.txt` y captura el baseline antes de tocar código.
- **[Riesgo: tablas no creadas en producción]** → Si un modelo no se importa antes del `lifespan`, `create_all` lo omite en silencio. *Mitigación*: imports explícitos (Decisión 8) y un test que verifica que `SQLModel.metadata.tables` contiene `editorial`, `genero` y `autor` tras importar `app.main`.
- **[Riesgo: sesión inválida tras `IntegrityError`]** → Reusar la sesión sin `rollback` lanza `PendingRollbackError`. *Mitigación*: `rollback()` explícito en el servicio y escenario de spec "la API sigue operativa tras un conflicto".
- **[Trade-off: `HTTPException` en servicios]** → Acopla la capa de servicio a FastAPI. Aceptado por simplicidad; si en C-05 se necesita reutilizar servicios fuera de HTTP, se migrará a excepciones de dominio traducidas por handlers.
- **[Hallazgo fuera de alcance: `/health/ready` filtra `str(exc)`]** → El `503` actual puede incluir texto interno del driver, en tensión con RN-12. No se corrige aquí para no mezclar capacidades; se recomienda un change o tarea menor posterior.
- **[Trade-off: concurrencia en PATCH]** → Dos `PATCH` simultáneos sobre la misma editorial siguen "último en escribir gana". Aceptable para v1 (sin control de versiones optimista).

## Migration Plan
- No hay datos previos: `create_all` crea `editorial`, `genero` y `autor` en el próximo arranque. Es aditivo e idempotente (no altera tablas existentes).
- Rollback: revertir el commit del change; las tablas vacías pueden quedar en la base sin afectar a C-01 o eliminarse con `DROP TABLE` manual.
