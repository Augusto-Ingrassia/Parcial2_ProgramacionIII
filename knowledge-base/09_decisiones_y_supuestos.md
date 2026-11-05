# Decisiones y Supuestos

## Decisiones Documentadas

### DD-01 — Objeto de Asociación Explícito para Libro y Autor (`LibroAutor`)
- **Decisión**: Modelar la relación muchos a muchos entre `Libro` y `Autor` mediante una entidad de asociación dedicada `LibroAutor` con su propia clase, en lugar de un `link_model` implícito.
- **Contexto**: La autoría requiere almacenar datos contextuales que pertenecen a la relación misma y no al autor ni al libro aislados: el `rol` ('autor', 'coautor', 'traductor', 'ilustrador') y el `orden` de aparición en la portada.
- **Alternativas consideradas**: Usar `link_model=...` de SQLModel.
- **Justificación**: Un `link_model` puro ocultaría los atributos de `rol` y `orden`. El objeto de asociación permite navegar `libro.autorias[i].autor` y mantener tipado estricto.
- **Trade-offs aceptados**: Requiere un nivel extra de navegación e importación de modelos (`autorias`), pero respeta el modelo de dominio.

### DD-02 — Copia Estática de Precios en Renglones de Venta
- **Decisión**: Al momento de crear una venta, el servidor consulta el precio vigente del libro en la base de datos y lo copia directamente en `renglon_venta.precio_unitario`.
- **Contexto**: Reglas RN-06 y RN-07. Las ventas representan hechos históricos inmutables.
- **Alternativas consideradas**: Permitir que el cliente envíe el precio unitario en el DTO o referenciar dinámicamente el precio del libro.
- **Justificación**: Si el cliente envía el precio, podría alterar fraudulentamente los montos. Si se referencia dinámicamente, una actualización futura del precio del libro alteraría retroactivamente los totales históricos de ventas pasadas.
- **Trade-offs**: Mayor lectura al momento del alta, garantizando absoluta consistencia financiera.

### DD-03 — Carga Anticipada Mandatoria (`joinedload` y `selectinload`)
- **Decisión**: Toda lectura que involucre relaciones debe declarar explícitamente sus opciones de carga anticipada en la consulta SQLAlchemy.
- **Contexto**: El problema de N+1 consultas degrada severamente el rendimiento en bases de datos relacionales y es motivo de desaprobación explícita en el parcial.
- **Alternativas consideradas**: Carga perezosa (lazy loading).
- **Justificación**: En SQLAlchemy asincrónico, la carga perezosa lanza excepciones de I/O bloqueante (`MissingGreenlet` / `DetachedInstanceError`). `joinedload` resuelve eficientemente relaciones 1 a 1 y N a 1 en un solo `JOIN`, mientras que `selectinload` resuelve colecciones 1 a N en una única consulta secundaria con cláusula `IN`.

### DD-04 — Base `python:3.12-alpine` para el Contenedor Docker
- **Decisión**: Utilizar `python:3.12-alpine` como imagen base oficial del Dockerfile.
- **Contexto**: Requisito de la cátedra de no superar los 100 MB en la imagen base para optimizar ancho de banda, espacio en el VPS y reducir la superficie de ataque.
- **Alternativas consideradas**: `python:3.12-slim` (ocupa ~180 MB, descartada por exceder el límite).
- **Justificación**: Se verificó que las dependencias requeridas (`asyncpg`, `pydantic-core`, `fastapi`, `sqlmodel`) disponen de wheels precompilados o se instalan correctamente en Alpine sin requerir compiladores adicionales ni elevar el peso de la imagen base.

### DD-05 — Healthcheck con IPv4 Local (127.0.0.1)
- **Decisión**: Configurar la comprobación de salud en el contenedor utilizando `wget -qO- http://127.0.0.1:8000/health/ready` (o `/live`).
- **Contexto**: En Alpine no está instalado `curl` por defecto. `wget` resuelve `localhost` primero a `::1` (IPv6), mientras que `uvicorn` con `--host 0.0.0.0` escucha sólo en IPv4.
- **Justificación**: Usar `localhost` provoca errores de `Connection refused` y marca falsamente el contenedor como `unhealthy`. Apuntar a `127.0.0.1` garantiza resolución directa sobre IPv4.

---

## Supuestos Inferidos

### SU-01 — Formato de Códigos de Error y Respuestas
- **Supuesto**: Cuando la base de datos lanza `IntegrityError` (por unicidad o clave foránea inexistente), la API responderá con `HTTP 409 Conflict` conteniendo un JSON con clave `"detail"`.
- **Origen**: Consigna RN-01, RN-02, RN-09, RN-12 y casos C-02, C-03, C-04.
- **Riesgo**: Si el evaluador espera un payload específico distinto de `{"detail": "..."}`.
- **Validación**: La convención estándar de FastAPI para `HTTPException` genera `{"detail": "..."}`.

### SU-02 — Comportamiento de `create_all` frente a Cambios de Esquema
- **Supuesto**: `SQLModel.metadata.create_all` sólo crea tablas que no existen en la base de datos de PostgreSQL. No modifica tablas ya existentes ni agrega columnas faltantes.
- **Origen**: Consigna Ejercicio 1 y Caso D-04.
- **Riesgo**: Si se cambia la definición de un modelo con la base ya poblada, la base no reflejará el cambio automáticamente.
- **Validación**: En caso de requerir modificaciones en tablas existentes durante el desarrollo, se debe limpiar la base de datos de prueba o recrear las tablas.
