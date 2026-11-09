# Proposal: Catálogos Base — Editoriales, Géneros y Autores

## Why
El catálogo de libros (C-03) depende de tres entidades maestras independientes que hoy no existen: `editorial`, `genero` y `autor`. Sin ellas no se puede dar de alta un libro (sus FKs `editorial_id`, `genero_id` y `autor_id` no tendrían destino), por lo que este change es el siguiente paso del camino crítico `C-01 → C-02 → C-03`. Además, establece por primera vez los patrones transversales que heredarán todos los módulos de dominio siguientes: paginación RN-10 y traducción de `IntegrityError` a `409 Conflict` sin filtrar detalles internos (RN-12).

## What Changes
- **Módulo `editoriales`** (`app/modules/editoriales/`): modelo `Editorial` (tabla `editorial`, `nombre` `UNIQUE` NOT NULL, `pais` NOT NULL), DTOs `EditorialCreate` / `EditorialRead` / `EditorialUpdate`, servicio y router con:
  - `POST /editoriales/` → `201 Created`; `409 Conflict` si el nombre ya existe.
  - `GET /editoriales/` → listado paginado (`limit` 1..100 por defecto 20, `offset` ≥ 0).
  - `GET /editoriales/{id}` → `200` / `404`.
  - `PATCH /editoriales/{id}` → actualización parcial (`exclude_unset`), `200` / `404` / `409` si el nuevo nombre colisiona.
- **Módulo `generos`** (`app/modules/generos/`): modelo `Genero` (tabla `genero`, `nombre` `UNIQUE` NOT NULL), DTOs `GeneroCreate` / `GeneroRead`, con:
  - `POST /generos/` → `201` / `409`.
  - `GET /generos/` → listado paginado.
  - `GET /generos/{id}` → `200` / `404`.
- **Módulo `autores`** (`app/modules/autores/`): modelo `Autor` (tabla `autor`, `nombre` NOT NULL, `nacionalidad` NOT NULL, sin unicidad), DTOs `AutorCreate` / `AutorRead` / `AutorUpdate`, con:
  - `POST /autores/` → `201`.
  - `GET /autores/` → listado paginado.
  - `GET /autores/{id}` → `200` / `404`.
  - `PATCH /autores/{id}` → actualización parcial, `200` / `404`.
- **Piezas transversales reutilizables** en `app/core/`: dependencia de paginación RN-10 compartida y manejador de respaldo que traduce cualquier `IntegrityError` no capturado a `409` con mensaje genérico (RN-12).
- **Registro en `app/main.py`** de los tres routers y de los modelos, para que `SQLModel.metadata.create_all` cree las tablas `editorial`, `genero` y `autor` en el `lifespan`.
- **Pruebas**: suite `pytest` por módulo (`tests/test_editoriales.py`, `tests/test_generos.py`, `tests/test_autores.py`) con fixtures compartidas, y archivos HTTP manuales `test/editoriales.http`, `test/generos.http`, `test/autores.http`.
- **Dependencia de desarrollo**: se declara `aiosqlite` en `requirements.txt` (ya usada implícitamente por los tests de C-01 pero no listada).

## Capabilities

### New Capabilities
- `editoriales`: Alta, listado paginado, consulta por id y actualización parcial de editoriales, con unicidad de nombre garantizada por la base y conflictos reportados como `409` sin detalles internos.
- `generos`: Alta, listado paginado y consulta por id de géneros literarios, con unicidad de nombre garantizada por la base.
- `autores`: Alta, listado paginado, consulta por id y actualización parcial de autores.

### Modified Capabilities
*(Ninguna. `core-infrastructure` y `health` no cambian su comportamiento observable: solo se registran nuevos routers y modelos sobre la misma infraestructura.)*

## Impact
- **APIs**: nuevas rutas bajo `/editoriales`, `/generos` y `/autores` (10 endpoints en total).
- **Base de datos**: tres tablas nuevas creadas por `create_all` (`editorial`, `genero`, `autor`) con restricciones `UNIQUE` en `editorial.nombre` y `genero.nombre`.
- **Código**: nuevos paquetes `app/modules/{editoriales,generos,autores}/` (`models.py`, `schemas.py`, `service.py`, `router.py`); nuevos módulos `app/core/pagination.py` y `app/core/exceptions.py`; modificación de `app/main.py`.
- **Fuera de alcance** (pertenecen a C-03): relaciones `libros` / `autorias` en los modelos y los endpoints de navegación `GET /editoriales/{id}/libros`, `GET /generos/{id}/libros`, `GET /autores/{id}/libros`. Tampoco hay endpoints `DELETE` ni `PATCH` de géneros.
