# Tasks

> Modo TDD estricto (RED → GREEN → REFACTOR) con las fixtures de `tests/conftest.py` (SQLite con `PRAGMA foreign_keys=ON`).

## 1. Modelos

- [x] 1.1 RED: tests de esquema de `cliente` (`UNIQUE email`, NOT NULL) y `perfil_cliente` (`cliente_id` FK `UNIQUE` + índice, NOT NULL). GREEN: `app/modules/clientes/models.py` con `Cliente` y `PerfilCliente`.
- [x] 1.2 RED: test de navegación: `Cliente.perfil` con `uselist=False`, `back_populates` en los dos extremos y `lazy="raise"`. GREEN: relaciones en ambos modelos.

## 2. DTOs

- [x] 2.1 RED: `ClienteCreate` normaliza email (minúsculas, sin espacios), ignora `id` y rechaza email sin `@` o sin dominio, nombre en blanco; `ClienteUpdate` parcial y `null` → error; `PerfilCreate` exige ambos campos. GREEN: `app/modules/clientes/schemas.py` (`ClienteCreate`, `ClienteUpdate`, `ClienteResumen`, `ClienteRead`, `PerfilCreate`, `PerfilRead`).

## 3. Endpoints

- [x] 3.1 RED: `POST /clientes/` → `201` con `perfil: null`; `422` inválido; email repetido (con otra capitalización) → `409` sin internos y la API sigue operativa. GREEN: `crear_cliente` con `commit_o_http`.
- [x] 3.2 RED: `GET /clientes/{id}` con perfil como objeto y `GET /clientes/` con perfil o `null`, paginación; `404`, `422` (id no entero, paginación inválida). GREEN: `obtener_cliente` / `listar_clientes` con `joinedload(Cliente.perfil)`.
- [x] 3.3 RED: `PATCH /clientes/{id}` parcial y `{}`; email de otro → `409` conservando el original; `null`/vacío/email inválido → `422`; inexistente → `404`. GREEN: `actualizar_cliente`.
- [x] 3.4 RED: `POST /clientes/{id}/perfil` → `201`; segundo perfil → `409` sin modificar el original; cliente inexistente → `404`; cuerpo incompleto → `422`. GREEN: `crear_perfil` sin `SELECT` previo (FK → 404, UNIQUE → 409).

## 4. Integración

- [x] 4.1 Registrar en `app/main.py` el import de `clientes.models` y el router `clientes`.
- [x] 4.2 Crear `test/clientes.http` con los casos de la spec (incluye los casos mínimos C-02 y C-03 de la consigna).
- [x] 4.3 Ejecutar la suite completa: todos los tests en verde.
- [x] 4.4 Ejecutar `test/clientes.http` contra PostgreSQL (clúster local temporal, PostgreSQL 17): todas las respuestas coinciden con el código documentado.

## Workflow follow-up

- `GET /clientes/{id}/ventas` y `Cliente.ventas` se implementan en C-05.
- Archivar con `/opsx:archive clientes-y-perfiles` y marcar `[C-04]` en `CHANGES.md`.
