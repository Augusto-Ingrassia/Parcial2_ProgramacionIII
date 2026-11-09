# Proposal: Suite de Pruebas Integral, Seed y Auditoría N+1

## Why
Con C-01 a C-05 archivados, la API cubre todo el dominio, pero faltan tres entregables de la consigna (`CHANGES.md` §C-06, Fase 4): un **seed reproducible** (`python -m app.initial_data`, KB 04 §Seed data inicial) para poblar la base en un estado conocido antes de la demo y del despliegue (C-07); una **suite `test/*.http` auditada** contra el catálogo RN-01..RN-12; y la **evidencia de que no hay N+1** (`evidencia/queries_libros.log` y `evidencia/queries_ventas.log`, DD-03), mostrando que listar 1, 10 o 50 libros/ventas ejecuta siempre la misma cantidad de sentencias. Hoy el conteo fijo sólo está probado para detalles con 1 y 3 hijos (`tests/test_libros.py`, `tests/test_ventas.py`) y no existe ningún archivo de evidencia.

## What Changes
- **Seed** `app/initial_data.py`:
  - `async def sembrar(session) -> ResumenSeed` con datos determinísticos: 3 editoriales, 4 géneros, 5 autores, 6 libros con autorías múltiples (roles `autor`, `coautor`, `traductor`) y 2 clientes con su perfil.
  - Idempotente: una segunda ejecución no falla ni duplica (busca cada fila por su clave natural y sólo inserta lo que falta, en una única transacción).
  - `main()` crea las tablas faltantes (`create_all`) y siembra; ejecutable con `python -m app.initial_data` (también dentro del contenedor de C-07).
- **Pruebas automáticas de presupuesto de consultas** (`tests/test_auditoria_consultas.py`): parametrizadas en 1, 10 y 50 filas para `GET /libros/`, `GET /libros/{id}` (1/10/50 autores), `GET /ventas/` y `GET /ventas/{id}` (1/10/50 renglones); la cantidad de sentencias es la misma para los tres tamaños.
- **Generador de evidencia** `scripts/auditar_consultas.py` (`python -m scripts.auditar_consultas`): con `SQL_ECHO=true` redirige el log de `sqlalchemy.engine` a `evidencia/queries_libros.log` y `evidencia/queries_ventas.log`, ejecuta los listados con `limit` 1, 10 y 50 a través de la API dentro de una transacción que se revierte al final (no ensucia la base) y anota el total de sentencias de cada corrida.
- **Auditoría de la suite `test/*.http`**: matriz RN → caso; se agregan sólo los casos faltantes (sin reescribir lo existente) y se ejecuta la suite completa contra PostgreSQL.
- **Configuración de pytest**: fijar `asyncio_default_fixture_loop_scope = function` para eliminar la advertencia de pytest-asyncio.

## Capabilities

### New Capabilities
- `seed-data`: carga inicial determinística e idempotente de un catálogo y clientes de demostración, ejecutable como módulo.
- `presupuesto-consultas`: garantía transversal de que los listados y detalles con relaciones ejecutan una cantidad fija de sentencias SQL independiente del tamaño de la página o de la colección, con evidencia reproducible en `evidencia/`.

### Modified Capabilities
- (ninguna: los requisitos funcionales de `libros`, `ventas`, `clientes` y catálogos no cambian; la auditoría `.http` sólo agrega casos manuales sobre comportamiento ya especificado)

## Impact
- **Código nuevo**: `app/initial_data.py`, `scripts/__init__.py`, `scripts/auditar_consultas.py`, `tests/test_initial_data.py`, `tests/test_auditoria_consultas.py`, `pytest.ini`.
- **Artefactos nuevos**: `evidencia/queries_libros.log`, `evidencia/queries_ventas.log`.
- **Archivos tocados**: `test/*.http` (sólo casos faltantes).
- **APIs / esquema**: sin cambios. Ningún endpoint nuevo; ninguna columna nueva.
- **Fuera de alcance**: Dockerfile e invocación del seed desde el contenedor (C-07), migraciones (Alembic), carga masiva o datos aleatorios, cambios de comportamiento en los servicios (si la auditoría encuentra un N+1, se corrige en este change como bug, pero no se esperan).
