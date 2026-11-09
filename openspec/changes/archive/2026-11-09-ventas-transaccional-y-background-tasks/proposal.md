# Proposal: Ventas Transaccionales y Tareas en Segundo Plano

## Why
La venta es el punto de convergencia del dominio (`C-03 + C-04 → C-05`) y la parte más pesada del **Ejercicio 4** de la consigna: el alta recibe `cliente_id` (asociación: viaja un id) y la lista `renglones` con `libro_id` y `cantidad` (composición: viajan los datos de la parte, que nace con la venta); cumple RN-04 a RN-07 (renglones dentro del alta, al menos uno y sin libros repetidos, precio copiado del libro, total calculado por el servidor). El **Ejercicio 3** exige además su listado paginado y sus códigos HTTP, y RN-08 que las ventas sean inmutables. El aviso del comprobante con `BackgroundTasks` (Ejercicio 6) forma parte del alcance de este change según `CHANGES.md`.

## What Changes
- **Módulo `ventas`** (`app/modules/ventas/`):
  - Modelo `Venta` (tabla `venta`): `cliente_id` FK indexada, `fecha` `TIMESTAMPTZ` asignada por el servidor en UTC, `total` `NUMERIC(12,2)` con `CHECK (total >= 0)`.
  - Modelo `RenglonVenta` (tabla `renglon_venta`): `venta_id` FK indexada (`ON DELETE CASCADE`), `libro_id` FK indexada, `cantidad` con `CHECK (cantidad > 0)`, `precio_unitario` `NUMERIC(10,2)` con `CHECK (precio_unitario > 0)`.
  - Navegación en los dos extremos: `Venta.cliente` ↔ `Cliente.ventas`, `Venta.renglones` (composición, `cascade_delete=True`) ↔ `RenglonVenta.venta`, `RenglonVenta.libro` ↔ `Libro.renglones`. Todas con `lazy="raise"`.
  - DTOs: `RenglonVentaCreate(libro_id, cantidad)`, `VentaCreate(cliente_id, renglones)` sin precio, total ni fecha; `RenglonVentaRead` (con `titulo` y `subtotal`) y `VentaRead` (con cliente y renglones).
  - Endpoints: `POST /ventas/` (201/409/422), `GET /ventas/` (paginado), `GET /ventas/{id}` (200/404). Ningún `PUT`, `PATCH` ni `DELETE` (RN-08 → `405`).
  - Tarea `notificar_comprobante(venta_id, email)` agendada con `BackgroundTasks`: `await asyncio.sleep(0.5)` y un mensaje en el log, después de enviada la respuesta.
- **Módulo `clientes`**: `GET /clientes/{id}/ventas` (historial del cliente, paginado, `404` si no existe).
- **Pruebas**: `tests/test_ventas.py` (incluye conteo fijo de consultas del detalle), `tests/test_main.py`; archivo manual `test/ventas.http`.

## Capabilities

### New Capabilities
- `ventas`: Alta transaccional de venta con sus renglones, precio copiado y total calculado en el servidor, lecturas sin N+1, inmutabilidad y aviso del comprobante en segundo plano.

### Modified Capabilities
- `clientes`: se agrega la consulta de las ventas de un cliente.

## Impact
- **APIs**: 3 rutas bajo `/ventas` y `GET /clientes/{id}/ventas`.
- **Base de datos**: tablas `venta` y `renglon_venta` con 3 `CHECK` y 3 FK indexadas.
- **Código**: nuevo paquete `app/modules/ventas/`; relaciones inversas en `clientes/models.py` y `libros/models.py`; `clientes/router.py`; `app/main.py`.
- **Fuera de alcance**: descontar stock al vender (la consigna no lo pide), anular ventas, envío real de correos, seed (C-06).
