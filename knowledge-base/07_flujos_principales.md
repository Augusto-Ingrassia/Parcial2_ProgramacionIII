# Flujos Principales

Este documento describe los flujos extremo a extremo más críticos del sistema, detallando el intercambio de datos entre Router, Service, ORM y Base de Datos.

---

## Flujo 1: Alta Transaccional de Venta con Renglones y Tarea Asíncrona (POST /ventas/)

### Disparador
Un cliente o cajero realiza una compra y envía la solicitud HTTP `POST /ventas/` con el ID de cliente y la lista de renglones.

### Actores
Cliente / Frontend HTTP → `VentaRouter` → `VentaService` → `AsyncSession` (PostgreSQL) → `BackgroundTasks`.

### Secuencia de Pasos
1. **Validación de Contrato (FastAPI / Pydantic)**:
   - Valida el payload de entrada contra `VentaCreate`.
   - Verifica RN-05: que la lista `renglones` contenga al menos 1 elemento y que no existan `libro_id` duplicados en el listado. Si falla, retorna `422 Unprocessable Entity` de inmediato.
2. **Obtención y Copia de Precios (Service)**:
   - El service extrae los IDs de libros involucrados y consulta los libros en la base de datos de manera eficiente.
   - Si algún libro o el cliente no existe, la base o el service detectan la inconsistencia y se traduce a `409 Conflict` (o `404` según corresponda).
   - Para cada renglón, se extrae el `precio` del libro y se copia en `precio_unitario` del renglón (RN-06).
   - Se calcula el subtotal de cada renglón y el `total` final de la venta (RN-07).
3. **Persistencia Atómica (Unit of Work implícito en sesión)**:
   - Se instancia el modelo de tabla `Venta(cliente_id=..., fecha=datetime.now(timezone.utc), total=total)`.
   - Se instancian los `RenglonVenta` y se vinculan a la venta: `venta.renglones.extend(...)`.
   - Se añade la venta a la sesión `session.add(venta)` y se realiza `await session.commit()`.
   - Se refresca o recarga la venta con sus relaciones usando `selectinload(Venta.renglones)` y `joinedload(Venta.cliente)`.
4. **Despacho de Tarea en Segundo Plano (Asincronía sin bloqueos)**:
   - Se añade la función `notificar_comprobante(venta_id, cliente_email)` a `background_tasks.add_task(...)`.
   - La tarea ejecutará `await asyncio.sleep(0.5)` e imprimirá en el log del servidor el aviso de comprobante.
5. **Respuesta HTTP**:
   - Se retorna `201 Created` con el esquema `VentaReadDetail` con el total, fecha ISO, cliente y detalle de renglones.
   - La respuesta viaja al cliente mientras la tarea de background sigue ejecutándose en el event loop.

```
Cliente            VentaRouter            VentaService           PostgreSQL            Background
   |                    |                      |                      |                     |
   |-- POST /ventas/ -->|                      |                      |                     |
   |                    |-- validar DTO ------>|                      |                     |
   |                    |   (RN-05: 422 si dup)|                      |                     |
   |                    |                      |-- SELECT libros ---->|                     |
   |                    |                      |<-- precios ---------|                     |
   |                    |                      |  (copia precio RN-06)|                     |
   |                    |                      |  (calcula total RN-07|                     |
   |                    |                      |-- INSERT venta+reng->|                     |
   |                    |                      |<-- commit OK --------|                     |
   |                    |-- add background ----|------------------------------------------->|
   |<-- 201 Created ----|                      |                      |                     |
   |    (con VentaRead) |                      |                      |                     |
   |                    |                      |                      |     [sleep 0.5s]    |
   |                    |                      |                      |     [log comprobante]
```

### Casos de Error
- Renglones vacíos o con libro repetido: `422 Unprocessable Entity` (FastAPI/Pydantic).
- Cliente inexistente o libro inexistente: `409 Conflict` (violación de clave foránea atrapada limpiamente).
- Error de conectividad a la base: `500 Internal Server Error`.

---

## Flujo 2: Alta de Libro con Autores Múltiples (POST /libros/)

### Disparador
El librero registra un nuevo libro vinculando editorial, género opcional y una lista de autorías con su rol y orden.

### Pasos
1. Se recibe `POST /libros/` con `LibroCreate`.
2. El service crea la instancia de `Libro` y las filas asociadas en `LibroAutor`.
3. **No se ejecuta consulta previa `SELECT`** para verificar si la editorial o autores existen: se ejecuta directamente el `INSERT`.
4. Si la base de datos rechaza la clave foránea (`editorial_id` o `autor_id` inexistente), el bloque `try...except IntegrityError` intercepta la excepción de PostgreSQL y responde `409 Conflict` con un mensaje amigable y sin filtrar trazas internas (RN-12).
5. Si el ISBN ya existe, la base de datos lanza violación de unicidad y se responde `409 Conflict` ("El ISBN ya se encuentra registrado") (RN-01).
6. Se confirman los cambios (`await session.commit()`) y se retorna `201 Created` con el detalle del libro creado.

---

## Flujo 3: Consulta de Detalle sin Problema N+1 (GET /libros/{id})

### Disparador
Se solicita el detalle completo de un libro para visualizar su ficha bibliográfica.

### Pasos
1. El router recibe `GET /libros/{id}` e invoca `LibroService.get_by_id(id)`.
2. El service formula una consulta única optimizada usando SQLAlchemy:
   ```python
   stmt = (
       select(Libro)
       .where(Libro.id == id)
       .options(
           joinedload(Libro.editorial),
           joinedload(Libro.genero),
           selectinload(Libro.autorias).joinedload(LibroAutor.autor)
       )
   )
   ```
3. Se ejecutan exactamente las consultas necesarias predecibles (fijas), independientemente de que el libro tenga 1, 5 o 20 autores:
   - 1 consulta con `JOIN` para el libro, su editorial y su género.
   - 1 consulta `SELECT ... IN` para cargar la colección de autorías y sus autores asociados.
4. Si el libro no existe, devuelve `404 Not Found`.
5. Se serializa a `LibroDetailRead` y responde `200 OK`.
