# Design: Libros y Autorías

## Context
C-01 dejó el motor asincrónico, `get_session` (`expire_on_commit=False`) y el `lifespan` con `create_all`. C-02 fijó el molde de módulo (`models.py` / `schemas.py` / `service.py` / `router.py`), la paginación compartida `PaginationDep`, el alias `NonEmptyStr` y la red de seguridad global de `IntegrityError → 409`. Ver `proposal.md` para la motivación y `specs/` para el contrato observable.

Restricciones (reglas duras de `CLAUDE.md`): sin `SELECT` previo para validar FKs en el alta del libro (regla 6), `Decimal` para dinero (regla 3), `index=True` en toda FK (regla 5), carga anticipada siempre (regla 2), traducción de `IntegrityError` sin filtrar internos (regla 4, RN-12).

## Goals / Non-Goals

**Goals:**
- Modelar `libro` y el objeto de asociación `libro_autor` con todas sus restricciones en la base.
- Alta atómica de libro + autorías en una única transacción, delegando en la base la existencia de editorial, género y autores.
- Lecturas con un número fijo de consultas, independiente de la cantidad de autores.

**Non-Goals:**
- Editar o quitar autorías de un libro existente.
- Decrementar stock al vender (no lo pide la consigna; ver C-05).
- Unicidad de `orden` dentro de un mismo libro (la consigna no la exige).

## Decisions

### Decisión 1: `LibroAutor` como objeto de asociación, no `link_model`
- **Decisión**: Clase propia `LibroAutor(table=True)` con PK compuesta `(libro_id, autor_id)` y columnas `rol` y `orden`. Se navega `libro.autorias[i].autor`.
- **Razón**: `rol` y `orden` pertenecen a la relación, no al libro ni al autor. Un `link_model` los escondería. La PK compuesta impide que el mismo autor figure dos veces en el mismo libro.

### Decisión 2: Lado de cada clave foránea
- `libro.editorial_id` (NOT NULL) y `libro.genero_id` (NULL): agregación; el libro *incorpora* una editorial/género existente y la misma la comparten muchos libros → la FK va del lado "muchos" (`libro`).
- `libro_autor.libro_id` / `libro_autor.autor_id`: muchos a muchos → ambas FK en la tabla intermedia.
- Todas con `index=True` (PostgreSQL no indexa las FK por su cuenta).

### Decisión 3: Restricciones en la base con nombre propio
- **Decisión**: `__table_args__` con `CheckConstraint` nombrados (`ck_libro_precio_positivo`, `ck_libro_stock_no_negativo`, `ck_libro_autor_rol`, `ck_libro_autor_orden`). `precio` se declara `Decimal` con `max_digits=10, decimal_places=2` → `NUMERIC(10,2)`.
- **Razón**: RN-03 exige `CHECK` en la base además del DTO. Nombrarlos hace legibles los errores en logs (nunca se envían al cliente).

### Decisión 4: Navegación con `lazy="raise"`
- **Decisión**: Todas las `Relationship` declaran `sa_relationship_kwargs={"lazy": "raise"}` en ambos extremos. Las relaciones inversas en `Editorial`, `Genero` y `Autor` usan imports bajo `TYPE_CHECKING` y referencias por nombre (`list["Libro"]`), resueltas por el registro de SQLAlchemy cuando `app.main` importa todos los modelos.
- **Razón**: Con sesión asincrónica la carga perezosa ya falla (`MissingGreenlet`), pero `raise` lo vuelve un error explícito y determinista: cualquier lectura que olvide precargar una relación falla en los tests en vez de degradar a N+1.

### Decisión 5: Alta sin `SELECT` previo y traducción de errores
- **Decisión**: `crear_libro` construye `Libro(...)` con `libro.autorias = [LibroAutor(...), ...]`, hace `session.add` y `commit` directamente. Un helper central `commit_o_http(session, errores)` captura `IntegrityError`, hace `rollback`, clasifica la violación con `tipo_violacion(exc)` y lanza `HTTPException` con el código y mensaje propios del mapa:
  - `unique` → `409 "Ya existe un libro con ese ISBN"`.
  - `foreign_key` → `409 "La editorial, el género o alguno de los autores indicados no existe"`.
  - otro → `409` genérico.
- **Clasificación**: por `SQLSTATE` (`23505` unique, `23503` FK, `23514` check, `23502` not null) cuando el driver lo expone (asyncpg vía SQLAlchemy), con respaldo por palabras clave del mensaje (SQLite en tests). El texto de la base **nunca** llega al cliente.
- **Alternativas**: verificar con `session.get` cada id antes de insertar (prohibido por la consigna: es carrera e I/O extra).

### Decisión 6: Validaciones del DTO (422 antes de tocar la base)
- `LibroCreate`: `isbn`, `titulo` → `NonEmptyStr`; `precio: Decimal` con `gt=0, max_digits=10, decimal_places=2`; `stock: int` con `ge=0`; `editorial_id: int`; `genero_id: int | None = None`; `autores: list[LibroAutorCreate]` con `min_length=1` (el diagrama de clases fija `1..*` autorías por libro).
- `LibroAutorCreate`: `autor_id: int`, `rol: Literal["autor","coautor","traductor","ilustrador"]`, `orden: int` con `ge=1`.
- Un `model_validator` rechaza `autor_id` repetidos (`422`), en vez de dejar que choque con la PK compuesta.
- `LibroUpdate`: todos opcionales (`isbn`, `titulo`, `precio`, `stock`, `editorial_id`, `genero_id`); `null` explícito → `422` salvo en `genero_id` (que es opcional: `null` quita el género).

### Decisión 7: Lecturas sin N+1
- **Detalle** (`GET /libros/{id}`, respuesta de `POST` y `PATCH`): `select(Libro).options(joinedload(Libro.editorial), joinedload(Libro.genero), selectinload(Libro.autorias).joinedload(LibroAutor.autor))` → **2 consultas** fijas (libro+editorial+género con JOIN; autorías+autores con `IN`).
- **Listado** (`GET /libros/`): "libros con editorial y género" → `joinedload` de ambos, **1 consulta** con `ORDER BY id LIMIT/OFFSET`.
- Tras `commit` en alta/PATCH se recarga el detalle con `populate_existing=True` para reemplazar el estado en memoria por el de la base.
- Los autores del detalle se ordenan por `orden` (y `autor_id` como desempate) al construir el DTO.

### Decisión 8: Búsqueda por título (RN-11)
- **Decisión**: `Libro.titulo.icontains(titulo, autoescape=True)`. Genera `lower(titulo) LIKE '%' || lower(:param) || '%'` con **parámetro ligado**; `autoescape` además neutraliza `%` y `_` del usuario. `' OR '1'='1` busca ese texto literal y devuelve `[]`.
- **Alternativa**: `ilike(f"%{titulo}%")` (también ligado, pero trata `%` del usuario como comodín).

### Decisión 9: Navegación cruzada
- `GET /editoriales/{id}/libros` y `GET /generos/{id}/libros`: `404` si el padre no existe (`session.get`), luego listado paginado de `LibroRead` filtrado por la FK, con `joinedload` de editorial y género.
- `GET /autores/{id}/libros`: `select(LibroAutor).where(autor_id=...).options(joinedload(LibroAutor.libro))` paginado → `[{id, isbn, titulo, precio, stock, rol, orden}]`.
- Viven en los routers de cada módulo y delegan en funciones de `libros/service.py` (la consulta es sobre `libro`).

### Decisión 10: Pruebas
- SQLite no aplica FK por defecto: `tests/conftest.py` registra `PRAGMA foreign_keys=ON` en cada conexión para que el camino `409` por FK se ejerza de verdad.
- Test de conteo de consultas con un listener `before_cursor_execute`: el detalle de un libro con 1 y con 3 autores emite la misma cantidad de sentencias.

### Decisión 11: UI Mockups
- `no (no UI)` — API REST.

## Risks / Trade-offs
- **[SQLite ≠ PostgreSQL]** → mensajes y `SQLSTATE` difieren; el clasificador tiene respaldo por texto y los tests sólo afirman código y ausencia de términos internos. Verificación final con `test/libros.http` contra PostgreSQL.
- **[`Decimal` en SQLite]** → SQLAlchemy emite un aviso porque SQLite no tiene `NUMERIC` nativo; los valores se devuelven como `Decimal` con escala 2. Sin efecto en PostgreSQL.
- **[`lazy="raise"`]** → un acceso olvidado falla en vez de degradar. Es intencional.
- **[FK de `genero_id` nula]** → un `genero_id` inexistente también produce `409` (misma regla que editorial).

## Migration Plan
- Aditivo: `create_all` crea `libro` y `libro_autor` en el próximo arranque; no altera `editorial`, `genero` ni `autor` (las relaciones inversas son sólo ORM, no cambian columnas).
