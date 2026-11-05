# Reglas de Negocio

A continuación se detallan las 12 reglas de negocio obligatorias evaluadas en el proyecto, clasificadas por su código canónico `RN-XX`, su enunciado y el garante esperado.

## Catálogo de Reglas

| Código | Enunciado | Garante Esperado | Comportamiento HTTP / Error |
|---|---|---|---|
| **RN-01** | El ISBN de un libro es único. | Restricción `UNIQUE` en tabla `libro`. | Responde `409 Conflict` capturando `IntegrityError` con mensaje propio. |
| **RN-02** | El email de un cliente es único. | Restricción `UNIQUE` en tabla `cliente`. | Responde `409 Conflict` capturando `IntegrityError` con mensaje propio. |
| **RN-03** | El precio de un libro es mayor que cero y el stock nunca es negativo. | Restricciones `CHECK (precio > 0)` y `CHECK (stock >= 0)` en base de datos; validación Pydantic en DTO (`gt=0`, `ge=0`). | Validación DTO responde `422 Unprocessable Entity`; base responde `409 Conflict` si se viola. |
| **RN-04** | Una venta se crea con sus renglones: los datos de cada renglón viajan dentro del cuerpo del alta de la venta, y no existe un alta de renglones por separado. | DTO anidado (`VentaCreate` con lista `renglones`); composición atómica en service (`venta.renglones.append(...)`). | Endpoint único `POST /ventas/`. No existe endpoint `/renglones/`. |
| **RN-05** | Una venta tiene al menos un renglón, y un mismo libro no aparece en dos renglones. | Validación en DTO Pydantic (`min_length=1` y `@field_validator` / `@model_validator` comprobando IDs de libros únicos). | Responde `422 Unprocessable Entity` si la lista está vacía o hay libros duplicados en renglones. |
| **RN-06** | El precio de cada renglón se copia del libro al registrar la venta y no cambia aunque después cambie el precio del libro. | Lógica de servidor en `VentaService`: lee el `precio` actual del libro desde la base y lo asigna a `renglon.precio_unitario`. | El cliente NUNCA envía `precio_unitario` en el DTO de creación de renglón. |
| **RN-07** | El total de la venta lo calcula el servidor como suma de `cantidad * precio_unitario`. | Lógica de servidor en `VentaService`: calcula `total = sum(r.cantidad * r.precio_unitario for r in renglones)`. | El cliente NUNCA envía el `total` en el DTO de creación de venta. |
| **RN-08** | Las ventas no se modifican: registran un hecho inmutable. | No existe endpoint `PATCH` ni `PUT` ni `DELETE` para ventas. | Intentar modificar una venta no está soportado (método no permitido o inexistente). |
| **RN-09** | Un cliente tiene como máximo un perfil. | Restricción `UNIQUE` en la columna `perfil_cliente.cliente_id`. | Si ya existe un perfil para ese cliente, responde `409 Conflict` con mensaje propio. |
| **RN-10** | Todo listado se pagina con `limit` (de 1 a 100, por defecto 20) y `offset` (desde 0). | Parámetros declarados con `Query(default=20, ge=1, le=100)` y `Query(default=0, ge=0)`. | Si un parámetro excede límites o es negativo, FastAPI responde automáticamente `422 Unprocessable Entity`. |
| **RN-11** | El listado de libros se puede filtrar por parte del título, sin distinguir mayúsculas. | Consulta con parámetro ligado: `col.ilike(f"%{titulo}%")` en SQLAlchemy. | Previene inyección SQL (parámetro ligado). Si no hay coincidencias, devuelve lista vacía `[]` con `200 OK`. |
| **RN-12** | Ningún error devuelve al cliente texto interno de la base (nombres de tablas, restricciones o trazas). | Middleware / Exception Handler / Service try-except que atrapa `IntegrityError` y emite un mensaje amigable y limpio. | Responde `409 Conflict` con `{"detail": "..."}` propio, sin filtrar nombres de índices o tablas PostgreSQL. |

## Reglas adicionales de dominio y arquitectura
- **Alta de Libro (Sin verificación previa por SELECT)**: En `POST /libros/`, no se ejecuta un `if` que consulte previamente si `editorial_id` o `autor_id` existen en la base. Se intenta escribir directamente: si la clave foránea es rechazada por PostgreSQL, se atrapa la violación y se responde `409 Conflict` con mensaje propio.
- **Inmutabilidad y Auditoría**: Una venta cerrada no puede ser editada ni eliminada.
- **Asincronía de aviso de venta**: Al persistir una venta con éxito, se agenda en `BackgroundTasks` una función asincrónica que simula el envío del comprobante al cliente (`await asyncio.sleep(0.5)` y log), respondiendo de inmediato al cliente HTTP.
