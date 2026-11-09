# Design: Ventas Transaccionales y Tareas en Segundo Plano

## Context
Dependen de este change los modelos `Libro` (C-03) y `Cliente` (C-04). Se reutilizan `SessionDep`, `PaginationDep`, `commit_o_http` y el patrón de relaciones con `lazy="raise"`. Ver `proposal.md` y `specs/`.

## Goals / Non-Goals

**Goals:**
- Alta atómica de venta + renglones (composición) con precio y total decididos por el servidor.
- Detalle de venta con una cantidad fija de consultas.
- Aviso del comprobante que no demora la respuesta.

**Non-Goals:**
- Control ni descuento de stock.
- Endpoints de modificación o baja de ventas (RN-08).

## Decisions

### Decisión 1: Lado de cada clave foránea
- `venta.cliente_id`: asociación — la venta conoce al cliente, ninguno es parte del otro → FK en el lado "muchos" (`venta`).
- `renglon_venta.venta_id`: composición — el renglón no existe sin su venta → FK en la parte, con `ON DELETE CASCADE` y `Relationship(cascade_delete=True)` del lado del todo.
- `renglon_venta.libro_id`: asociación — el renglón nombra un libro existente.
- Todas con `index=True`.

### Decisión 2: Contrato de entrada (RN-04, RN-05, RN-06, RN-07)
- `VentaCreate(cliente_id: int, renglones: list[RenglonVentaCreate])` con `min_length=1` y un `model_validator` que rechaza `libro_id` repetidos → `422`.
- `RenglonVentaCreate(libro_id: int, cantidad: int > 0)`.
- Precio, subtotal, total y fecha **no forman parte del DTO**: si el cliente los envía se ignoran (configuración por defecto de SQLModel, igual que el `id` en los demás DTO de alta).

### Decisión 3: Alta en una transacción
1. Una única consulta `SELECT id, precio FROM libro WHERE id IN (...)` obtiene los precios vigentes. Es la lectura que exige RN-06 (no una verificación de existencia previa a la escritura); si falta algún libro no hay precio que copiar → `409 "Alguno de los libros indicados no existe"`.
2. Se construyen los `RenglonVenta` con `precio_unitario` copiado y se calcula `total = Σ cantidad × precio_unitario` en `Decimal`.
3. `Venta(cliente_id, total, fecha=now(UTC))` con `venta.renglones = [...]`; `session.add` + `commit_o_http`. El cliente **no** se consulta antes: si no existe la FK rechaza la escritura → `409 "El cliente o alguno de los libros indicados no existe"`. Todo o nada: ante cualquier error se hace `rollback` y no queda ni la venta ni sus renglones.
4. Se recarga el detalle con carga anticipada y `populate_existing=True`.

### Decisión 4: Lecturas sin N+1
- Detalle y listado: `joinedload(Venta.cliente)` + `selectinload(Venta.renglones).joinedload(RenglonVenta.libro)` → **2 consultas** fijas por petición (venta+cliente con JOIN; renglones+libros con `IN`), sin importar la cantidad de renglones o de ventas de la página.
- La respuesta sigue el ejemplo de la consigna: `id`, `fecha`, `total`, `cliente {id, nombre, email}`, `renglones [{libro_id, titulo, cantidad, precio_unitario, subtotal}]`, montos como cadenas decimales (`"77000.00"`).

### Decisión 5: Aviso del comprobante con `BackgroundTasks`
- **Decisión**: el router recibe `background_tasks: BackgroundTasks` y, con la venta ya confirmada, agenda `service.notificar_comprobante(venta.id, venta.cliente.email)`. La función es `async def`, hace `await asyncio.sleep(0.5)` y registra `Comprobante de la venta N enviado a <email>` en el logger `uvicorn.error`.
- **Razón**: Starlette ejecuta las tareas de fondo después de enviar la respuesta, sobre el mismo event loop, así que el `await` no bloquea otras peticiones. Se usa el logger de uvicorn porque ya tiene handler configurado y su salida aparece en `docker logs` después de la línea de acceso (caso D-07), sin duplicar el echo de SQLAlchemy como haría un `basicConfig` sobre el root.
- **Alternativa**: `asyncio.create_task` (sin garantía de ejecución tras la respuesta ni manejo por el framework).

### Decisión 6: Inmutabilidad (RN-08)
- Sólo se declaran `POST /ventas/`, `GET /ventas/` y `GET /ventas/{id}`. FastAPI responde `405 Method Not Allowed` para `PUT`, `PATCH` y `DELETE` sobre `/ventas/{id}`.

### Decisión 7: Historial del cliente
- `GET /clientes/{id}/ventas` vive en el router de `clientes` y delega en `ventas/service.py`: `404` si el cliente no existe (`session.get`), luego el mismo listado de ventas filtrado por `cliente_id`, paginado.

### Decisión 8: Pruebas
- Conteo de consultas con la fixture `contar_consultas`: el detalle de una venta de 1 y de 3 renglones emite la misma cantidad.
- El agendado se verifica reemplazando `service.notificar_comprobante` por un registrador; la tarea real se verifica por separado con `caplog`.

### Decisión 9: UI Mockups
- `no (no UI)`.

## Risks / Trade-offs
- **[Zona horaria en SQLite]** → SQLite devuelve `fecha` sin zona; en PostgreSQL `TIMESTAMPTZ` vuelve en UTC y se serializa con `Z`. Los tests no dependen del sufijo.
- **[Precio leído y luego escrito]** → si el precio de un libro cambia entre la lectura y el commit, la venta usa el leído: es el precio vigente al registrar, que es lo que pide RN-06.
- **[Stock no controlado]** → una venta puede superar el stock. Fuera de alcance; anotado para un change futuro.

## Migration Plan
- Aditivo: `create_all` crea `venta` y `renglon_venta`. Las relaciones inversas en `Cliente` y `Libro` no cambian columnas.
