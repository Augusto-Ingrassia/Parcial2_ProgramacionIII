# Proposal: Libros y Autorías

## Why
El catálogo de libros es el centro del dominio: lo referencian las autorías, los renglones de venta y las navegaciones desde editoriales, géneros y autores. La consigna del parcial lo evalúa en dos ejercicios: el **Ejercicio 3** (contratos y CRUD: DTO separados, `201/404/409/422`, PATCH con `exclude_unset`, paginación RN-10 y búsqueda por título con parámetros ligados RN-11) y el **Ejercicio 4** (el alta del libro recibe *ids* de lo que ya existe —`editorial_id`, `genero_id` y `autores[].autor_id`— más los datos propios de la relación —`rol` y `orden`—, y **ningún `if` consulta antes si un id existe**: se escribe y, si la base rechaza la clave foránea, se responde `409`). Es el siguiente paso del camino crítico `C-02 → C-03 → C-05`.

## What Changes
- **Módulo `libros`** (`app/modules/libros/`):
  - Modelo `Libro` (tabla `libro`): `isbn` `UNIQUE`, `titulo`, `precio` `NUMERIC(10,2)` con `CHECK (precio > 0)`, `stock` con `CHECK (stock >= 0)`, `editorial_id` (FK, índice, NOT NULL), `genero_id` (FK, índice, NULL permitido).
  - Objeto de asociación `LibroAutor` (tabla `libro_autor`): PK compuesta (`libro_id`, `autor_id`), ambas FK con índice, `rol` con `CHECK` en `('autor','coautor','traductor','ilustrador')`, `orden` con `CHECK (orden >= 1)`.
  - Navegación en los dos extremos: `Libro.editorial` ↔ `Editorial.libros`, `Libro.genero` ↔ `Genero.libros`, `Libro.autorias` ↔ `LibroAutor.libro`, `LibroAutor.autor` ↔ `Autor.autorias`. Todas con `lazy="raise"`: ninguna lectura puede depender de la carga perezosa.
  - DTOs: `LibroAutorCreate`, `LibroCreate` (sin `id`), `LibroUpdate`, `LibroRead` (con editorial y género), `LibroReadDetail` (con editorial, género y autores con rol y orden), `AutorDeLibroRead`.
  - Endpoints: `POST /libros/` (201/409/422), `GET /libros/` (paginado, filtros `titulo` y `genero_id`), `GET /libros/{id}` (200/404), `PATCH /libros/{id}` (200/404/409/422).
- **Navegación cruzada** en los módulos de C-02: `GET /editoriales/{id}/libros`, `GET /generos/{id}/libros`, `GET /autores/{id}/libros` (este último con `rol` y `orden`), paginados y con `404` si el padre no existe.
- **`app/core/exceptions.py`**: clasificador `tipo_violacion(IntegrityError)` (por `SQLSTATE` de PostgreSQL con respaldo por texto para SQLite) y helper `commit_o_http(session, errores)` para traducir cada tipo de violación a un código y un mensaje propio (RN-12) sin exponer internos.
- **Pruebas**: `tests/test_libros.py` (incluye conteo fijo de consultas del detalle), actualización de `tests/conftest.py` (`PRAGMA foreign_keys=ON` en SQLite) y `tests/test_main.py`; archivo manual `test/libros.http`.

## Capabilities

### New Capabilities
- `libros`: Alta atómica de libro con autorías, listado paginado con filtros, detalle sin N+1 y actualización parcial, con unicidad de ISBN y claves foráneas garantizadas por la base.

### Modified Capabilities
- `editoriales`: se agrega la consulta de libros de una editorial.
- `generos`: se agrega la consulta de libros de un género.
- `autores`: se agrega la consulta de libros de un autor con su rol y orden.

## Impact
- **APIs**: 4 rutas nuevas bajo `/libros` y 3 rutas de navegación cruzada.
- **Base de datos**: tablas `libro` y `libro_autor` creadas por `create_all`, con 3 `CHECK`, 1 `UNIQUE`, 4 FK indexadas.
- **Código**: nuevo paquete `app/modules/libros/`; modificación de los `models.py` y `router.py` de `editoriales`, `generos` y `autores` (relaciones inversas y rutas `/libros`); `app/main.py`; `app/core/exceptions.py`.
- **Fuera de alcance**: modificar las autorías de un libro existente (el PATCH sólo toca datos bibliográficos), `DELETE` de libros, seed de datos (C-06).
