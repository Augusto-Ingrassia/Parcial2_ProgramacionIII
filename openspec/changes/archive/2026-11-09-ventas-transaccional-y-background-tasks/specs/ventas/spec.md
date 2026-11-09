# Spec Delta

## Purpose
Registra las ventas de la librería como hechos inmutables: cada venta nace con sus renglones, con el precio de cada libro copiado y el total calculado por el servidor, y dispara el aviso del comprobante en segundo plano.

## ADDED Requirements

### Requirement: Alta de venta con sus renglones
El sistema SHALL registrar mediante `POST /ventas/` una venta con `cliente_id` y `renglones` (`libro_id`, `cantidad`), copiando el precio vigente de cada libro (RN-06), calculando el total en el servidor (RN-07) y persistiendo venta y renglones en una única transacción (RN-04); y SHALL responder `201 Created` con `id`, `fecha`, `total`, `cliente` y `renglones`.

#### Scenario: Venta válida con dos renglones
- **WHEN** el libro 1 cuesta `25000.00`, el libro 4 cuesta `27000.00`, existe el cliente 2 y se envía `POST /ventas/` con `{"cliente_id": 2, "renglones": [{"libro_id": 1, "cantidad": 2}, {"libro_id": 4, "cantidad": 1}]}`
- **THEN** el sistema responde `201 Created` con `total` `"77000.00"`, el `cliente` 2 y dos renglones con `precio_unitario` `"25000.00"` / `"27000.00"` y `subtotal` `"50000.00"` / `"27000.00"`

#### Scenario: El cliente no fija precio, total ni fecha
- **WHEN** el cuerpo incluye `total`, `fecha` o `precio_unitario` en un renglón
- **THEN** el sistema los ignora y usa los valores calculados por el servidor

#### Scenario: El precio queda fijado en la venta
- **WHEN** después de registrar la venta se cambia el precio del libro 1 con `PATCH /libros/1`
- **THEN** `GET /ventas/{id}` sigue mostrando el `precio_unitario` y el `total` originales

#### Scenario: Sin renglones o con libros repetidos (RN-05)
- **WHEN** se envía `POST /ventas/` con `renglones` vacío, o con el mismo `libro_id` en dos renglones
- **THEN** el sistema responde `422 Unprocessable Entity` y no persiste nada

#### Scenario: Cantidad inválida
- **WHEN** un renglón trae `cantidad` `0` o negativa
- **THEN** el sistema responde `422 Unprocessable Entity`

#### Scenario: Cliente inexistente
- **WHEN** se envía `POST /ventas/` con un `cliente_id` que no existe
- **THEN** el sistema responde `409 Conflict` con mensaje propio, sin texto interno de la base, y no persiste la venta ni sus renglones

#### Scenario: Libro inexistente
- **WHEN** algún renglón trae un `libro_id` que no existe
- **THEN** el sistema responde `409 Conflict` con mensaje propio y no persiste nada

### Requirement: Restricciones de la venta en la base
El esquema SHALL declarar `venta.total` como `NUMERIC(12,2)` con `CHECK (total >= 0)`, `venta.fecha` con zona horaria, `renglon_venta.precio_unitario` como `NUMERIC(10,2)` con `CHECK (precio_unitario > 0)`, `CHECK (cantidad > 0)`, y FK indexadas `venta.cliente_id`, `renglon_venta.venta_id` y `renglon_venta.libro_id`.

#### Scenario: La base rechaza una cantidad no positiva aunque se saltee el DTO
- **WHEN** se inserta directamente en la base un renglón con `cantidad = 0`
- **THEN** la base rechaza la escritura con una violación de `CHECK`

### Requirement: Aviso del comprobante en segundo plano
Al registrar una venta el sistema SHALL agendar con `BackgroundTasks` el aviso del comprobante al cliente, que espera `await asyncio.sleep(0.5)` y escribe un mensaje en el log con el id de la venta y el email del cliente, y que corre después de enviar la respuesta sin bloquear otras peticiones.

#### Scenario: Se agenda el aviso con los datos de la venta
- **WHEN** se registra la venta 1 del cliente `tomas@example.com`
- **THEN** se agenda una tarea de fondo con `venta_id` 1 y ese email, y la respuesta `201` no espera a que termine

#### Scenario: El aviso aparece en el log
- **WHEN** corre la tarea de aviso de la venta 1
- **THEN** el log contiene un mensaje con `venta 1` y el email del cliente

#### Scenario: Una venta rechazada no agenda aviso
- **WHEN** el alta responde `409` o `422`
- **THEN** no se agenda ninguna tarea de fondo

### Requirement: Lecturas de ventas sin N+1
El sistema SHALL listar ventas mediante `GET /ventas/` paginadas (RN-10) y devolver una venta mediante `GET /ventas/{id}`, en ambos casos con su cliente y sus renglones obtenidos con carga anticipada en una cantidad fija de consultas, independiente de la cantidad de renglones; y `404 Not Found` si la venta no existe.

#### Scenario: Cantidad fija de consultas
- **WHEN** se piden los detalles de una venta con 1 renglón y de otra con 3 renglones
- **THEN** ambas peticiones ejecutan la misma cantidad de sentencias SQL

#### Scenario: Venta inexistente
- **WHEN** se envía `GET /ventas/999`
- **THEN** el sistema responde `404 Not Found`

#### Scenario: Paginación
- **WHEN** existen 3 ventas y se envía `GET /ventas/?limit=2&offset=1`
- **THEN** el sistema responde `200 OK` con las ventas 2 y 3; y con `limit=0` responde `422`

### Requirement: Ventas inmutables (RN-08)
El sistema SHALL NOT exponer operaciones para modificar o eliminar ventas.

#### Scenario: Intento de modificar o borrar
- **WHEN** se envía `PATCH`, `PUT` o `DELETE` a `/ventas/1`
- **THEN** el sistema responde `405 Method Not Allowed` y la venta no cambia
