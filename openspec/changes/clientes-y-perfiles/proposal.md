# Proposal: Clientes y Perfiles

## Why
Las ventas (C-05) se asocian a un cliente, y la consigna evalúa en el **Ejercicio 3** el CRUD de clientes (DTO separados, `201/404/409/422`, PATCH parcial) y en el **Ejercicio 2** la relación uno a uno cliente–perfil, garantizada por un `UNIQUE` en `perfil_cliente.cliente_id` (RN-09) y navegable como objeto único (`Cliente.perfil` no es una lista). El email del cliente es único (RN-02). Este change es la rama paralela del roadmap (`C-01 → C-04`) que converge con C-03 en C-05.

## What Changes
- **Módulo `clientes`** (`app/modules/clientes/`):
  - Modelo `Cliente` (tabla `cliente`): `nombre`, `email` `UNIQUE`.
  - Modelo `PerfilCliente` (tabla `perfil_cliente`): `cliente_id` FK `UNIQUE` + índice, `telefono`, `direccion`.
  - Navegación en los dos extremos: `Cliente.perfil` (objeto único, `uselist=False`) ↔ `PerfilCliente.cliente`, ambas con `lazy="raise"`.
  - DTOs: `ClienteCreate`, `ClienteUpdate`, `ClienteResumen`, `ClienteRead` (con `perfil` embebido o `null`), `PerfilCreate`, `PerfilRead`.
  - Endpoints: `POST /clientes/` (201/409/422), `GET /clientes/` (paginado), `GET /clientes/{id}` (200/404), `PATCH /clientes/{id}` (200/404/409/422), `POST /clientes/{id}/perfil` (201/404/409/422).
- **Pruebas**: `tests/test_clientes.py`, actualización de `tests/test_main.py`, archivo manual `test/clientes.http`.

## Capabilities

### New Capabilities
- `clientes`: Alta, listado, consulta y actualización parcial de clientes con email único, y alta del perfil 1:1 con unicidad garantizada por la base.

### Modified Capabilities
*(Ninguna.)*

## Impact
- **APIs**: 5 rutas nuevas bajo `/clientes`.
- **Base de datos**: tablas `cliente` y `perfil_cliente`, con `UNIQUE (email)` y `UNIQUE (cliente_id)` + FK indexada.
- **Código**: nuevo paquete `app/modules/clientes/`; `app/main.py`.
- **Fuera de alcance**: `GET /clientes/{id}/ventas` y la relación `Cliente.ventas` (requieren el modelo `Venta`; los agrega C-05). Modificar o borrar el perfil, `DELETE` de clientes.
