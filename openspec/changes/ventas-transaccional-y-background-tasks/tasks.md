# Tasks

> Modo TDD estricto (RED → GREEN → REFACTOR) con las fixtures de `tests/conftest.py` (SQLite con `PRAGMA foreign_keys=ON`, `contar_consultas`).

## 1. Modelos

- [x] 1.1 RED: tests de esquema de `venta` (`fecha` con zona horaria, `total NUMERIC(12,2)`, `CHECK total >= 0`, FK `cliente_id` indexada) y `renglon_venta` (`NUMERIC(10,2)`, `CHECK cantidad > 0` y `precio_unitario > 0`, FK indexadas, `venta_id ON DELETE CASCADE`). GREEN: `app/modules/ventas/models.py`.
- [x] 1.2 RED: test de navegación en los dos extremos (`Venta.cliente` ↔ `Cliente.ventas`, `Venta.renglones` ↔ `RenglonVenta.venta` con `delete-orphan`, `RenglonVenta.libro` ↔ `Libro.renglones`), todas con `lazy="raise"`. GREEN: relaciones inversas en `clientes/models.py` y `libros/models.py`.
- [x] 1.3 Mover las opciones de carga anticipada de `libros/service.py` a funciones: construirlas a nivel de módulo configuraba los mappers al importar, antes de que existiera `RenglonVenta`.
- [x] 1.4 RED: la base rechaza un renglón con `cantidad = 0` insertado sin pasar por el DTO. GREEN: cubierto por los `CheckConstraint`.

## 2. DTOs

- [x] 2.1 RED: `VentaCreate` descarta `total`, `fecha` y `precio_unitario`; rechaza renglones vacíos, cantidad ≤ 0 y libros repetidos. GREEN: `app/modules/ventas/schemas.py` (`RenglonVentaCreate`, `VentaCreate`, `RenglonVentaRead`, `VentaRead`).

## 3. Alta transaccional

- [x] 3.1 RED: venta con dos renglones → `201` con `total "77000.00"`, cliente y renglones con precio copiado y subtotal, en el orden de campos del ejemplo de la consigna; total con centavos; precio y total del cliente ignorados. GREEN: `crear_venta` (una lectura de precios, cálculo en `Decimal`, `venta.renglones = [...]`, `commit_o_http`, recarga del detalle).
- [x] 3.2 RED: cambiar el precio del libro después de la venta no altera el renglón ni el total. GREEN: cubierto por la copia de precio.
- [x] 3.3 RED: `422` para vacío, repetido, cantidad 0 y sin cliente; cliente inexistente → `409` sin internos y sin persistir; libro inexistente → `409`; ninguno agenda aviso. GREEN: validación del DTO + mapa de errores.

## 4. Aviso del comprobante

- [x] 4.1 RED: `notificar_comprobante` escribe en el logger `uvicorn.error` el id de la venta y el email. GREEN: `async def` con `await asyncio.sleep(0.5)`.
- [x] 4.2 RED: `POST /ventas/` agenda la tarea con `(venta.id, email)` (registrador por `monkeypatch`) y la tarea real deja el mensaje en el log. GREEN: `BackgroundTasks.add_task` en el router.

## 5. Lecturas

- [x] 5.1 RED: `GET /ventas/{id}` igual a la respuesta del alta, `404`, `422`; detalle con 1 y con 3 renglones emite exactamente 2 consultas. GREEN: `obtener_venta` con `joinedload` + `selectinload(...).joinedload(...)`.
- [x] 5.2 RED: `GET /ventas/` con 3 ventas emite 2 consultas, paginación y `422`. GREEN: `listar_ventas`.
- [x] 5.3 RED: `GET /clientes/{id}/ventas` (sólo las del cliente, `[]` sin compras, `404`). GREEN: `listar_ventas_de_cliente` y ruta en `clientes/router.py`.
- [x] 5.4 RED: `PATCH`, `PUT` y `DELETE` sobre `/ventas/{id}` → `405` y la venta no cambia. GREEN: el router no los declara.

## 6. Integración

- [x] 6.1 Registrar en `app/main.py` el import de `ventas.models` y el router `ventas`; ampliar `tests/test_main.py` (todas las tablas, todas las rutas, toda FK con índice, ventas sin `PUT`/`PATCH`/`DELETE`).
- [x] 6.2 Crear `test/ventas.http` (casos mínimos C-05, C-06 y C-07 de la consigna, RN-04 a RN-08).
- [x] 6.3 Ejecutar la suite completa: 190 tests en verde.
- [x] 6.4 Ejecutar `test/health.http`, `test/libros.http`, `test/clientes.http` y `test/ventas.http` en orden contra PostgreSQL (clúster local temporal, PostgreSQL 17) con `SQL_ECHO=true`: 64/64 respuestas con el código esperado; `fecha` serializada en UTC con `Z`; el comprobante aparece en el log después de la línea `POST /ventas/ 201`.

## Workflow follow-up

- Archivar con `/opsx:archive ventas-transaccional-y-background-tasks` y marcar `[C-05]` en `CHANGES.md`.
- Para C-06: capturar en `evidencia/` las consultas del detalle de libro y de venta (caso C-07) y crear el seed `app/initial_data.py`.
