# CHANGES — Secuencia de Implementación

> Índice canónico de todos los changes del proyecto **API Librería (Parcial Programación III)**.  
> Cada change es atómico: un agente puede implementarlo en una sesión (~4-6 horas).  
> **Leer este archivo antes de ejecutar cualquier `/opsx:propose`.**

---

## Cómo usar este documento

1. Identificar el change a implementar (verificar que sus dependencias están archivadas en `openspec/changes/archive/`).
2. Leer los documentos de la `knowledge-base/` indicados en la sección "Leer antes" de cada change.
3. Ejecutar `/opsx:propose <nombre-del-change>` para iniciar la especificación y diseño del change.
4. Al culminar la implementación y verificación con tests, archivar con `/opsx:archive <nombre-del-change>`.
5. Marcar el checkbox correspondiente `[x]` en este archivo maestro.

---

## Árbol de dependencias

```
C-01 core-infrastructure-and-health
  │
  ├── C-02 catalogos-base-editoriales-generos-autores
  │     └── C-03 libros-y-autorias ─────────────────────────┐
  │                                                         │
  └── C-04 clientes-y-perfiles ─────────────────────────────┼── C-05 ventas-transaccional-y-background-tasks
                                                            │         └── C-06 suite-pruebas-integral-seed-y-auditoria-n1
                                                            │               └── C-07 docker-alpine-y-despliegue-vps
```

### Paralelismo por fase

> Cada "gate" representa un punto de sincronización. Los changes agrupados bajo el mismo gate pueden ejecutarse en paralelo sin colisión de dominio.

```
GATE 0: ninguna
  → C-01 core-infrastructure-and-health               (solo)

GATE 1: C-01 ✓                                         ← PRIMER FORK (2 paralelos)
  → C-02 catalogos-base-editoriales-generos-autores   [Agente A]
  → C-04 clientes-y-perfiles                         [Agente B]

GATE 2: C-02 ✓
  → C-03 libros-y-autorias                           [Agente A]

GATE 3: C-03 + C-04 ✓                                  ← CONVERGENCIA TRANSACCIONAL
  → C-05 ventas-transaccional-y-background-tasks     [Agente A]

GATE 4: C-05 ✓
  → C-06 suite-pruebas-integral-seed-y-auditoria-n1   [Agente B]

GATE 5: C-06 ✓
  → C-07 docker-alpine-y-despliegue-vps              [Agente C]
```

### Camino crítico (6 changes — mínimo irreducible)

```
C-01 → C-02 → C-03 → C-05 → C-06 → C-07
```

### Plan óptimo con 3 agentes

```
Paso │ Agente A (Backend Core)       │ Agente B (Backend Aux)        │ Agente C (Testing / Infra)
─────┼───────────────────────────────┼───────────────────────────────┼───────────────────────────
  1  │ C-01 core-infrastructure      │               —               │             —
  2  │ C-02 catalogos-base           │ C-04 clientes-y-perfiles      │             —
  3  │ C-03 libros-y-autorias        │               —               │             —
  4  │ C-05 ventas-transaccional     │               —               │             —
  5  │               —               │ C-06 suite-pruebas-seed       │             —
  6  │               —               │               —               │ C-07 docker-despliegue-vps
```

---

## FASE 0 — Cimientos e Infraestructura

### [C-01] `core-infrastructure-and-health`
- **Estado**: `[x]` completado (archivado 2026-11-05)
- **Scope**: Estructura modular base, motor asincrónico SQLModel/PostgreSQL, lifespan y health checks
  - Estructura de paquetes: `app/core/`, `app/modules/health/`, `app/main.py`, `test/`.
  - Configuración asincrónica en `app/core/database.py`: `create_async_engine` sobre `postgresql+asyncpg://`, `async_sessionmaker` configurado con `expire_on_commit=False` y dependencia `get_session`.
  - Configuración tipada en `app/core/config.py`: lectura con `pydantic-settings` de `DATABASE_URL`, `SQL_ECHO` (bool) y `APP_PORT` (int, default 8000). Plantilla `env.example` en raíz.
  - Gestión de ciclo de vida en `app/main.py`: `lifespan` asincrónico con creación automática de tablas vía `SQLModel.metadata.create_all` al inicio y `await engine.dispose()` al cierre.
  - Módulo Health en `app/modules/health/`:
    - `GET /health/live`: responde `200 OK` con `{"estado": "vivo"}` sin interactuar con la base de datos (liveness).
    - `GET /health/ready`: ejecuta `SELECT 1` asincrónico sobre PostgreSQL; responde `200 OK` si la conexión es exitosa o propaga error si falla (readiness).
  - Dependencias del proyecto en `requirements.txt`: `fastapi>=0.111.0`, `sqlmodel>=0.0.24`, `asyncpg>=0.30.0`, `uvicorn[standard]>=0.30.0`, `pydantic-settings>=2.3.0`.
  - Pruebas HTTP: `test/health.http` cubriendo `/health/live` y `/health/ready`.
- **Dependencias**: ninguna
- **Governance**: BAJO
- **Leer antes**:
  - `knowledge-base/01_vision_y_objetivos.md` §Objetivo General
  - `knowledge-base/02_descripcion_general.md` §Tecnologías Utilizadas
  - `knowledge-base/06_funcionalidades.md` §Épica 1: Salud y Diagnóstico
  - `knowledge-base/08_arquitectura_propuesta.md` §Estructura obligatoria de directorios y §Políticas de Ciclo de Vida
  - `knowledge-base/09_decisiones_y_supuestos.md` §SU-02

---

## FASE 1 — Catálogos y Entidades Base

> Los changes C-02 y C-04 pueden implementarse en paralelo por distintos agentes una vez archivado C-01.

### [C-02] `catalogos-base-editoriales-generos-autores`
- **Estado**: `[x]` completado (archivado 2026-11-09)
- **Scope**: Modelos, DTOs, routers y servicios para entidades maestras independientes
  - Modelos SQLModel con claves foráneas e índices:
    - `Editorial`: tabla `editorial`, `id` (PK autoincremental), `nombre` (`UNIQUE`, NOT NULL), `pais` (NOT NULL).
    - `Genero`: tabla `genero`, `id` (PK autoincremental), `nombre` (`UNIQUE`, NOT NULL).
    - `Autor`: tabla `autor`, `id` (PK autoincremental), `nombre` (NOT NULL), `nacionalidad` (NOT NULL).
  - DTOs / Schemas Pydantic (`Create`, `Read`, `Update` con `exclude_unset`):
    - `EditorialCreate`, `EditorialRead`, `EditorialUpdate`.
    - `GeneroCreate`, `GeneroRead`.
    - `AutorCreate`, `AutorRead`, `AutorUpdate`.
  - Endpoints REST modulares:
    - `app/modules/editoriales/`: `POST /editoriales/` (201 Created), `GET /editoriales/` (paginado RN-10 con `limit` 1..100 y `offset` >= 0), `GET /editoriales/{id}` (200 / 404), `PATCH /editoriales/{id}` (200 / 404 / 409).
    - `app/modules/generos/`: `POST /generos/` (201 Created), `GET /generos/` (paginado RN-10), `GET /generos/{id}` (200 / 404).
    - `app/modules/autores/`: `POST /autores/` (201 Created), `GET /autores/` (paginado RN-10), `GET /autores/{id}` (200 / 404), `PATCH /autores/{id}` (200 / 404).
  - Manejo de excepciones e integridad: captura de `IntegrityError` en altas y actualizaciones que colisionen en `nombre` único, respondiendo `409 Conflict` con mensaje amigable sin exponer tablas ni restricciones internas (RN-12).
  - Pruebas HTTP: `test/editoriales.http`, `test/generos.http` y `test/autores.http` con casos de éxito, paginación y conflictos de duplicidad.
- **Dependencias**: C-01
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §1. editorial, §2. genero, §3. autor
  - `knowledge-base/05_reglas_de_negocio.md` §RN-10 y §RN-12
  - `knowledge-base/06_funcionalidades.md` §Épica 2, §Épica 3 y §Épica 4
  - `knowledge-base/08_arquitectura_propuesta.md` §Manejo Centralizado de Integridad

---

### [C-04] `clientes-y-perfiles`
- **Estado**: `[x]` completado (archivado 2026-11-09)
- **Scope**: Entidad Cliente y PerfilCliente con relación 1:1 estricta, validaciones de unicidad e historial de compras
  - Modelos SQLModel relacionales:
    - `Cliente`: tabla `cliente`, `id` (PK autoincremental), `nombre` (NOT NULL), `email` (`UNIQUE`, NOT NULL). Relación 1:1 con `perfil` (`Relationship(back_populates="cliente")`, objeto único, no lista).
    - `PerfilCliente`: tabla `perfil_cliente`, `id` (PK autoincremental), `cliente_id` (FK `cliente.id`, `UNIQUE`, `index=True`, NOT NULL), `telefono` (NOT NULL), `direccion` (NOT NULL).
  - DTOs / Schemas Pydantic:
    - `ClienteCreate(nombre, email)`, `ClienteUpdate`, `ClienteRead(id, nombre, email, perfil: Optional[PerfilClienteRead])`.
    - `PerfilClienteCreate(telefono, direccion)`, `PerfilClienteRead(id, cliente_id, telefono, direccion)`.
  - Endpoints REST en `app/modules/clientes/`:
    - `POST /clientes/`: alta de cliente. Si el email ya existe, responde `409 Conflict` (RN-02, RN-12). Responde `201 Created`.
    - `GET /clientes/`: listado paginado (RN-10) con `joinedload(Cliente.perfil)`.
    - `GET /clientes/{id}`: detalle del cliente con su perfil 1:1 embebido o null (200 o 404).
    - `PATCH /clientes/{id}`: actualización parcial del cliente.
    - `POST /clientes/{id}/perfil`: alta de perfil vinculada al cliente. Si el cliente ya posee un perfil asignado, responde `409 Conflict` (RN-09).
    - `GET /clientes/{id}/ventas`: endpoint para consulta de compras del cliente (conector hacia el módulo de ventas).
  - Pruebas HTTP: `test/clientes.http` verificando alta, perfil 1:1, rechazo de segundo perfil (409) y colisión de email (409).
- **Dependencias**: C-01
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §6. cliente y §7. perfil_cliente
  - `knowledge-base/05_reglas_de_negocio.md` §RN-02 y §RN-09
  - `knowledge-base/06_funcionalidades.md` §Épica 6: Clientes y Perfiles
  - `knowledge-base/08_arquitectura_propuesta.md` §Separación de Modelos y DTOs

---

## FASE 2 — Obras y Relaciones N:M

### [C-03] `libros-y-autorias`
- **Estado**: `[x]` completado (archivado 2026-11-09)
- **Scope**: Modelado de Libro, tabla intermedia LibroAutor N:M con rol y orden, alta directa y consultas sin N+1
  - Modelos SQLModel relacionales:
    - `Libro`: tabla `libro`, `id` (PK autoincremental), `isbn` (`UNIQUE`, NOT NULL), `titulo` (NOT NULL), `precio` (`NUMERIC(10, 2)`, check `precio > 0`), `stock` (int, check `stock >= 0`), `editorial_id` (FK `editorial.id`, `index=True`, NOT NULL), `genero_id` (FK `genero.id`, `index=True`, NULL permitido).
    - `LibroAutor`: tabla `libro_autor` (objeto de asociación explícito), `libro_id` (PK compuesta, FK `libro.id`, `index=True`), `autor_id` (PK compuesta, FK `autor.id`, `index=True`), `rol` (str, check in `'autor','coautor','traductor','ilustrador'`), `orden` (int, check `orden >= 1`).
  - DTOs / Schemas Pydantic:
    - `LibroAutorCreate(autor_id, rol, orden)`, `LibroAutorRead(autor_id, nombre, rol, orden)`.
    - `LibroCreate(isbn, titulo, precio, stock, editorial_id, genero_id, autores: list[LibroAutorCreate])`. Validaciones RN-01 y RN-03.
    - `LibroReadDetail`: incluye información completa de `editorial`, `genero` y lista `autores` desanidada con rol y orden.
    - `LibroUpdate`: actualización parcial de datos bibliográficos (`exclude_unset`).
  - Endpoints REST en `app/modules/libros/`:
    - `POST /libros/`: creación atómica de libro y autorías en una sola transacción. Sin verificación previa `SELECT` de FKs: si `editorial_id` o `autor_id` no existen o el ISBN colisiona, captura `IntegrityError` y devuelve `409 Conflict` (RN-01, RN-12). Responde `201 Created` con `LibroReadDetail`.
    - `GET /libros/`: listado paginado (RN-10) con filtro case-insensitive por `titulo` (`ilike`, RN-11) y filtro opcional por `genero_id`. Carga anticipada obligatoria con `joinedload(Libro.editorial)`, `joinedload(Libro.genero)` y `selectinload(Libro.autorias).joinedload(LibroAutor.autor)` para evitar consultas N+1.
    - `GET /libros/{id}`: detalle completo con relaciones cargadas sin N+1 (200 o 404).
    - `PATCH /libros/{id}`: edición parcial de stock, precio o título (200, 404 o 409).
  - Endpoints de navegación cruzada en módulos respectivos:
    - `GET /editoriales/{id}/libros` (libros de una editorial).
    - `GET /generos/{id}/libros` (libros de un género).
    - `GET /autores/{id}/libros` (libros de un autor con rol y orden).
  - Pruebas HTTP: `test/libros.http` con altas con autores múltiples, violación de ISBN único (409), búsqueda con `ilike`, filtros y validaciones de stock/precio.
- **Dependencias**: C-02
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §4. libro y §5. libro_autor
  - `knowledge-base/05_reglas_de_negocio.md` §RN-01, §RN-03, §RN-11 y §Reglas adicionales (Alta de Libro)
  - `knowledge-base/06_funcionalidades.md` §Épica 5: Catálogo de Libros
  - `knowledge-base/07_flujos_principales.md` §Flujo 2 y §Flujo 3 (Sin N+1)
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-01 y §DD-03

---

## FASE 3 — Transaccionalidad y Tareas en Segundo Plano

### [C-05] `ventas-transaccional-y-background-tasks`
- **Estado**: `[x]` completado (archivado 2026-11-09)
- **Scope**: Composición 1:N Venta/Renglones, inmutabilidad, cálculo en servidor, transaccionalidad atómica y tarea asincrónica de notificación
  - Modelos SQLModel relacionales:
    - `Venta`: tabla `venta`, `id` (PK autoincremental), `cliente_id` (FK `cliente.id`, `index=True`, NOT NULL), `fecha` (`TIMESTAMPTZ` con timezone UTC, NOT NULL), `total` (`NUMERIC(12, 2)`, check `total >= 0`, NOT NULL). Relación `renglones: list[RenglonVenta] = Relationship(back_populates="venta", cascade_delete=True)`.
    - `RenglonVenta`: tabla `renglon_venta`, `id` (PK autoincremental), `venta_id` (FK `venta.id`, `index=True`, NOT NULL), `libro_id` (FK `libro.id`, `index=True`, NOT NULL), `cantidad` (int, check `cantidad > 0`, NOT NULL), `precio_unitario` (`NUMERIC(10, 2)`, check `precio_unitario > 0`, NOT NULL).
  - DTOs / Schemas Pydantic:
    - `RenglonVentaCreate(libro_id: int, cantidad: int)`: no expone ni acepta `precio_unitario` desde el cliente (RN-06).
    - `VentaCreate(cliente_id: int, renglones: list[RenglonVentaCreate])`: no expone ni acepta `total` (RN-07). Validación con `@model_validator` asegurando al menos 1 renglón (`min_length=1`) y sin `libro_id` duplicados, retornando `422 Unprocessable Entity` si falla (RN-04, RN-05).
    - `VentaReadDetail`: serializa ID de venta, cliente completo, fecha ISO, total calculado y detalle de cada renglón (con libro, cantidad, precio unitario y subtotal).
  - Endpoints REST en `app/modules/ventas/`:
    - `POST /ventas/`: alta transaccional en bloque:
      1. Obtiene libros de la base de datos y copia sus precios vigentes a `precio_unitario` de cada renglón (RN-06).
      2. Calcula el total como suma de `cantidad * precio_unitario` en servidor (RN-07).
      3. Persiste `Venta` y `RenglonVenta` en la misma transacción atómica (RN-04).
      4. Si el cliente o algún libro no existen, captura la excepción de integridad y responde `409 Conflict` (RN-12).
      5. Despacha en `BackgroundTasks` la función `notificar_comprobante(venta_id, cliente_email)` simulando envío asincrónico (`await asyncio.sleep(0.5)` y log de consola) sin demorar el retorno HTTP.
      6. Responde `201 Created` con `VentaReadDetail`.
    - `GET /ventas/`: listado paginado (RN-10) con carga anticipada de relaciones.
    - `GET /ventas/{id}`: detalle completo precargando `joinedload(Venta.cliente)` y `selectinload(Venta.renglones).joinedload(RenglonVenta.libro)` sin N+1.
    - Inmutabilidad estricta: NO se implementa ningún método `PUT`, `PATCH` ni `DELETE` sobre ventas (RN-08).
  - Pruebas HTTP: `test/ventas.http` cubriendo compra exitosa, cálculo automático de total, rechazo de renglones vacíos / libros duplicados (422), cliente inexistente (409) e inmutabilidad (405).
- **Dependencias**: C-03, C-04
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §8. venta y §9. renglon_venta
  - `knowledge-base/05_reglas_de_negocio.md` §RN-04, §RN-05, §RN-06, §RN-07, §RN-08 y §RN-12
  - `knowledge-base/06_funcionalidades.md` §Épica 7: Gestión de Ventas
  - `knowledge-base/07_flujos_principales.md` §Flujo 1: Alta Transaccional de Venta
  - `knowledge-base/08_arquitectura_propuesta.md` §Procesamiento Asincrónico de Fondo
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-02

---

## FASE 4 — Calidad, Seed y Auditoría de Rendimiento

### [C-06] `suite-pruebas-integral-seed-y-auditoria-n1`
- **Estado**: `[x]` completado (archivado 2026-11-09)
- **Scope**: Script de seed reproducible, suite completa de archivos .http y auditoría de consultas fijas sin N+1
  - Script ejecutable de datos iniciales `app/initial_data.py`:
    - Función asincrónica ejecutable vía `python -m app.initial_data` o invocada desde Docker.
    - Crea datos determinísticos: 3 editoriales, 4 géneros, 5 autores, 6 libros con autorías múltiples (roles autor, coautor, traductor), y 2 clientes con sus respectivos perfiles.
  - Consolidación y validación de suite `test/*.http`:
    - `test/health.http`: liveness y readiness.
    - `test/editoriales.http`, `test/generos.http`, `test/autores.http`: CRUDs, paginación (RN-10) y unicidad (RN-12).
    - `test/libros.http`: alta con autores, validación RN-01, RN-03, filtros parciales RN-11, relaciones cruzadas.
    - `test/clientes.http`: alta, unicidad email RN-02, perfil 1:1 y rechazo de segundo perfil RN-09.
    - `test/ventas.http`: flujo completo, validación RN-04, RN-05, comprobación de copia de precios RN-06, total RN-07, inmutabilidad RN-08 y comprobante en segundo plano.
  - Auditoría de rendimiento y consultas fijas (sin N+1):
    - Configurar `SQL_ECHO=true` y capturar trazas en `evidencia/queries_libros.log` y `evidencia/queries_ventas.log`.
    - Demostrar que listar 1, 10 o 50 libros/ventas ejecuta exactamente una cantidad constante y fija de sentencias SQL (1 consulta principal con JOINs + 1 consulta IN para colecciones uno a muchos).
- **Dependencias**: C-05
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Claves foráneas e integridad y §Seed data inicial
  - `knowledge-base/05_reglas_de_negocio.md` (todas las reglas RN-01 a RN-12)
  - `knowledge-base/07_flujos_principales.md` §Flujo 3: Detalle sin N+1
  - `knowledge-base/08_arquitectura_propuesta.md` §Carga Anticipada y §Tabla de variables
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-03

---

## FASE 5 — Contenedorización y Despliegue en Producción

### [C-07] `docker-alpine-y-despliegue-vps`
- **Estado**: `[ ]` pendiente
- **Scope**: Contenedorización segura en Alpine Linux, usuario no-root, variables desacopladas, despliegue en VPS y manual operativo
  - `Dockerfile` optimizado:
    - Imagen base oficial `python:3.12-alpine` (tamaño base < 100 MB).
    - Capas ordenadas para aprovechar caché: copia e instala `requirements.txt` con `--no-cache-dir` antes de copiar el código fuente.
    - Seguridad: creación de usuario y grupo sin privilegios `appuser` y ejecución con `USER appuser`.
    - Instrucción `EXPOSE 8000`.
    - `HEALTHCHECK` periódico con `wget -qO- http://127.0.0.1:8000/health/ready || exit 1` (apuntando a IPv4 para evitar fallo de resolución IPv6 en Alpine).
    - Comando de arranque: `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`.
  - Archivo `.dockerignore`:
    - Exclusión de `.env`, `.venv`, `.git`, `__pycache__`, `*.pyc`, `evidencia/`, `.pytest_cache/`.
  - Despliegue en VPS y archivo `DEPLOY.md`:
    - URL pública activa donde responde la API en el servidor VPS.
    - Registro formal de día y hora del despliegue.
    - Comandos exactos de construcción y ejecución:  
      `docker build -t libreria .`  
      `docker run -d --name libreria -p <puerto>:8000 --restart unless-stopped --env-file .env.prod libreria`
    - Invocación de carga de datos iniciales en el contenedor:  
      `docker exec libreria python -m app.initial_data`
    - Procedimiento documentado paso a paso para actualizar la versión del contenedor en caliente sin pérdida de datos en la base.
  - `README.md` operativo en la raíz con descripción del sistema, nombres de integrantes de la cátedra, setup local y validación del contenedor.
- **Dependencias**: C-06
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/02_descripcion_general.md` §Stack tecnológico
  - `knowledge-base/08_arquitectura_propuesta.md` §Contenedorización sin Root y §Tabla de variables de entorno
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-04 y §DD-05
  - `knowledge-base/11_despliegue_docker_y_vps.md` (requisitos completos de Docker y VPS)
