# Funcionalidades

Las funcionalidades del sistema están estructuradas por épicas modulares correspondientes a los módulos funcionales del proyecto.

---

## Épica 1: Salud y Diagnóstico (`health`)

### US-001 — Health Check de Proceso Vivo (Liveness)
**Como** plataforma de orquestación / Docker  
**Quiero** consultar si la aplicación web está corriendo  
**Para** saber si el contenedor debe seguir activo sin generar tráfico a la base de datos.

**Criterios de aceptación**:
- [ ] Endpoint `GET /health/live`.
- [ ] Responde `200 OK` con payload `{"estado": "vivo"}`.
- [ ] No ejecuta ninguna llamada ni conexión a la base de datos.

### US-002 — Health Check de Disponibilidad de Base de Datos (Readiness)
**Como** balanceador o evaluador  
**Quiero** verificar si la aplicación tiene conectividad operativa con PostgreSQL  
**Para** comprobar si el servicio está listo para recibir tráfico funcional.

**Criterios de aceptación**:
- [ ] Endpoint `GET /health/ready`.
- [ ] Ejecuta una sentencia SQL mínima `SELECT 1` sobre la base de datos de manera asincrónica.
- [ ] Si la base responde, devuelve `200 OK`.
- [ ] Si la base no responde o está caída, la consulta falla y responde con error.

---

## Épica 2: Gestión de Editoriales (`editoriales`)

### US-003 — Crear Editorial
**Como** librero  
**Quiero** registrar una nueva editorial  
**Para** clasificar la procedencia de los libros en el catálogo.

**Criterios de aceptación**:
- [ ] Endpoint `POST /editoriales/` con cuerpo `EditorialCreate(nombre, pais)`.
- [ ] Responde `201 Created` con `EditorialRead`.
- [ ] Si el nombre ya existe, responde `409 Conflict` con mensaje propio.

### US-004 — Listar y Consultar Editorial
**Como** usuario  
**Quiero** listar editoriales con paginación y consultar el detalle de una editorial y sus libros  
**Para** navegar el catálogo por editorial.

**Criterios de aceptación**:
- [ ] `GET /editoriales/` soporta `limit` y `offset` (RN-10). Devuelve `200 OK`.
- [ ] `GET /editoriales/{id}` devuelve `EditorialRead` (200) o `404 Not Found` si no existe.
- [ ] `GET /editoriales/{id}/libros` devuelve la lista de libros de esa editorial (200) o `404` si no existe la editorial.
- [ ] `PATCH /editoriales/{id}` actualiza campos enviados (`exclude_unset`). Devuelve `200 OK` o `409` si el nuevo nombre colisiona.

---

## Épica 3: Gestión de Géneros (`generos`)

### US-005 — Gestión de Géneros Literarios
**Como** librero  
**Quiero** administrar los géneros literarios disponibles  
**Para** agrupar temáticamente las obras.

**Criterios de aceptación**:
- [ ] `POST /generos/` con `GeneroCreate(nombre)`. Responde `201 Created` o `409 Conflict`.
- [ ] `GET /generos/` lista todos los géneros (200).
- [ ] `GET /generos/{id}/libros` lista los libros asociados a ese género (200) o `404` si no existe el género.

---

## Épica 4: Gestión de Autores (`autores`)

### US-006 — Registro y Consulta de Autores
**Como** librero  
**Quiero** registrar autores con su nacionalidad y consultar sus publicaciones  
**Para** gestionar los creadores de las obras.

**Criterios de aceptación**:
- [ ] `POST /autores/` con `AutorCreate(nombre, nacionalidad)`. Responde `201 Created`.
- [ ] `GET /autores/{id}` y `PATCH /autores/{id}` para consultar y actualizar datos del autor (200 o 404).
- [ ] `GET /autores/{id}/libros` devuelve los libros del autor incluyendo su `rol` y `orden` en cada obra (200 o 404).

---

## Épica 5: Catálogo de Libros (`libros`)

### US-007 — Alta Completa de Libro con Autores
**Como** librero  
**Quiero** registrar un libro junto con sus autores asociados en una única operación  
**Para** dar de alta la obra con su información editorial y de autoría completa.

**Criterios de aceptación**:
- [ ] `POST /libros/` recibe `isbn`, `titulo`, `precio`, `stock`, `editorial_id`, `genero_id` (opcional) y lista `autores` (cada uno con `autor_id`, `rol`, `orden`).
- [ ] Cumple validaciones RN-01 (ISBN único) y RN-03 (`precio > 0`, `stock >= 0`).
- [ ] No hace SELECT previo de existencia de editorial ni autores: si la FK es inválida, captura `IntegrityError` y responde `409 Conflict`.
- [ ] Persiste la entidad `Libro` y las filas intermedias `LibroAutor` atómicamente.
- [ ] Responde `201 Created` con el detalle completo del libro (editorial, género y lista de autores).

### US-008 — Consulta y Filtro de Libros sin N+1
**Como** comprador o librero  
**Quiero** listar libros con filtros y ver el detalle completo de un libro  
**Para** encontrar títulos y conocer sus detalles editoriales y autores.

**Criterios de aceptación**:
- [ ] `GET /libros/` soporta paginación (`limit`, `offset`) y filtros por `titulo` (búsqueda parcial case-insensitive, RN-11) y `genero_id`.
- [ ] Carga anticipada de relaciones (`joinedload` para editorial/género, `selectinload` para autores).
- [ ] `GET /libros/{id}` devuelve detalle completo (editorial, género y autores). Responde `200` o `404`.
- [ ] `PATCH /libros/{id}` permite actualizar campos parciales (`precio`, `stock`, `titulo`, etc.) aplicando `exclude_unset`. Responde `200`, `404` o `409`.

---

## Épica 6: Clientes y Perfiles (`clientes`)

### US-009 — Registro de Cliente y Perfil 1:1
**Como** cliente  
**Quiero** registrarme en el sistema y opcionalmente cargar mi perfil con teléfono y dirección  
**Para** quedar habilitado para comprar libros.

**Criterios de aceptación**:
- [ ] `POST /clientes/` con `nombre` y `email`. Responde `201 Created` o `409 Conflict` si el email ya existe (RN-02).
- [ ] `GET /clientes/{id}` devuelve datos del cliente y su `perfil` embebido (objeto único o null, no lista).
- [ ] `PATCH /clientes/{id}` actualiza datos de cliente.
- [ ] `POST /clientes/{id}/perfil` crea el perfil del cliente (`telefono`, `direccion`). Si ya tiene perfil, responde `409 Conflict` (RN-09).
- [ ] `GET /clientes/{id}/ventas` devuelve el historial de compras de ese cliente (200 o 404).

---

## Épica 7: Gestión de Ventas (`ventas`)

### US-010 — Registro Transaccional de Venta
**Como** librero / cliente  
**Quiero** registrar una compra con múltiples libros y cantidades en un único payload  
**Para** formalizar una venta inmutable y calcular el total de forma segura.

**Criterios de aceptación**:
- [ ] `POST /ventas/` recibe `cliente_id` y lista `renglones` (`libro_id`, `cantidad`).
- [ ] RN-04: Los renglones nacen exclusivamente con la venta (composición).
- [ ] RN-05: Valida que haya al menos 1 renglón y no haya libros duplicados en el payload; responde `422` en caso contrario.
- [ ] RN-06: El servidor obtiene el precio unitario vigente de cada libro en la base de datos y lo asigna al renglón.
- [ ] RN-07: El servidor calcula el `subtotal` de cada renglón y el `total` acumulado de la venta.
- [ ] Responde `201 Created` con el detalle completo de la venta, cliente y renglones.
- [ ] Se dispara en segundo plano (`BackgroundTasks`) la tarea asincrónica de notificación/comprobante sin bloquear la respuesta.
- [ ] `GET /ventas/` lista ventas paginadas.
- [ ] `GET /ventas/{id}` devuelve el detalle con cliente y renglones precargados en consultas fijas (sin N+1).
- [ ] RN-08: No existe endpoint de edición ni eliminación de ventas.
