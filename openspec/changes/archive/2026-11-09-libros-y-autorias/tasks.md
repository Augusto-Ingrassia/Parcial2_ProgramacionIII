# Tasks

> Modo TDD estricto: cada tarea de implementación se ejecuta como ciclo RED → GREEN → REFACTOR. Los tests de API usan las fixtures de `tests/conftest.py` (SQLite `aiosqlite` + override de `get_session`).

## 1. Infraestructura de pruebas y de errores

- [x] 1.1 Crear `.venv`, instalar `requirements.txt` y registrar el baseline (87 tests en verde).
- [x] 1.2 Activar `PRAGMA foreign_keys=ON` en cada conexión SQLite de `tests/conftest.py` para que las violaciones de FK se ejerzan de verdad; agregar la fixture `contar_consultas` (listener `before_cursor_execute`).
- [x] 1.3 Agregar a `app/core/exceptions.py` `tipo_violacion(IntegrityError)` (SQLSTATE `23505/23503/23514/23502` con respaldo por texto) y `commit_o_http(session, errores)` (commit, rollback y `HTTPException` con código y mensaje propios).

## 2. Modelos

- [x] 2.1 RED: tests de esquema de `libro` (columnas, `UNIQUE isbn`, `NUMERIC(10,2)`, FK indexadas, `genero_id` nulo, `CHECK precio > 0` y `stock >= 0`) y de `libro_autor` (PK compuesta, FK indexadas, `CHECK orden >= 1` y de `rol`). GREEN: `app/modules/libros/models.py` con `Libro` y `LibroAutor`.
- [x] 2.2 RED: test de navegación en los dos extremos con `lazy="raise"`. GREEN: relaciones inversas `Editorial.libros`, `Genero.libros`, `Autor.autorias` con imports bajo `TYPE_CHECKING`.
- [x] 2.3 RED: test de que la base rechaza `precio = 0` insertado sin pasar por el DTO. GREEN: ya cubierto por los `CheckConstraint`.

## 3. DTOs

- [x] 3.1 RED: tests de `LibroCreate` (sin `id`, `genero_id` opcional; `422` para precio ≤ 0, más de 2 decimales, stock < 0, ISBN en blanco, autores vacíos, rol inválido, orden < 1, autor repetido) y de `LibroUpdate` (parcial, `null` sólo en `genero_id`). GREEN: `app/modules/libros/schemas.py`.

## 4. Endpoints de libros

- [x] 4.1 RED: `POST /libros/` con dos coautores → `201` con detalle ordenado por `orden`; sin género → `genero: null`; FK inexistente (editorial, género, autor) → `409` sin internos y sin persistir; ISBN repetido → `409` y la API sigue operativa; cuerpos inválidos → `422`; ningún `SELECT` antes del primer `INSERT`. GREEN: `crear_libro` en `service.py` y ruta en `router.py`.
- [x] 4.2 RED: `GET /libros/` con editorial y género, filtro por título case-insensitive, `' OR '1'='1` / `%` / `_` → `[]`, filtro `genero_id`, paginación y `422`. GREEN: `listar_libros` con `joinedload` e `icontains(..., autoescape=True)`.
- [x] 4.3 RED: `GET /libros/{id}` → `200` igual a la respuesta del alta, `404`, `422` para id no entero; detalle con 1 y con 3 autores emite exactamente 2 consultas. GREEN: `obtener_libro` con `joinedload` + `selectinload(...).joinedload(...)`.
- [x] 4.4 RED: `PATCH /libros/{id}` parcial, quitar género, `{}` sin cambios, ISBN de otro libro → `409` conservando el original, editorial inexistente → `409`, valores inválidos o `null` → `422`, inexistente → `404`. GREEN: `actualizar_libro` con `exclude_unset` y recarga del detalle.

## 5. Navegación cruzada

- [x] 5.1 RED: `GET /editoriales/{id}/libros` y `GET /generos/{id}/libros` (lista, paginación, vacío, `404`). GREEN: rutas en los routers de `editoriales` y `generos` que delegan en `libros/service.py`.
- [x] 5.2 RED: `GET /autores/{id}/libros` con `rol` y `orden` de cada autoría y `404`. GREEN: `listar_libros_de_autor` sobre `LibroAutor` con `joinedload(LibroAutor.libro)`.

## 6. Integración

- [x] 6.1 Registrar en `app/main.py` el import de `libros.models` y el router `libros`.
- [x] 6.2 Crear `test/libros.http` con los casos de la spec y el código esperado en comentarios (incluye los casos mínimos C-01, C-02, C-04 y C-08 de la consigna).
- [x] 6.3 Ejecutar la suite completa: todos los tests en verde.
- [x] 6.4 Levantar la API contra PostgreSQL (clúster local temporal, PostgreSQL 17) y ejecutar `test/libros.http`: todas las respuestas coinciden con el código documentado, ningún `409` expone internos y el detalle emite 2 `SELECT` con `SQL_ECHO=true`.

## Workflow follow-up

- Archivar con `/opsx:archive libros-y-autorias` una vez verificada la tarea 6.4.
- Marcar `[C-03]` como `[x]` en `CHANGES.md`.
