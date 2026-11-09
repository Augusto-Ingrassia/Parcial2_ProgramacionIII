# Design: Suite de Pruebas Integral, Seed y Auditoría N+1

## Context
Ver `proposal.md` (Why). Estado actual relevante:
- Todas las relaciones usan `lazy="raise"`; las lecturas declaran `joinedload` (a uno) y `selectinload` (colecciones). `listar_libros` sólo carga editorial y género (sin autores); `listar_ventas`/`obtener_venta` cargan cliente + renglones con su libro; `listar_clientes` carga el perfil.
- `tests/conftest.py` ya ofrece `db_engine` (SQLite temporal con `PRAGMA foreign_keys=ON`), `client` (ASGI con override de `get_session`) y `contar_consultas` (listener `before_cursor_execute`). Hoy el conteo fijo se prueba sólo con detalles de 1 y 3 hijos y con un listado de 3 ventas.
- `get_engine()` toma `echo=settings.SQL_ECHO`; con `echo=True` SQLAlchemy registra cada sentencia en el logger `sqlalchemy.engine.Engine`.
- `app/main.py` crea las tablas en el `lifespan` con `create_all`; no hay migraciones.
- No hay configuración de pytest (`pytest.ini`/`pyproject.toml`): pytest-asyncio advierte por `asyncio_default_fixture_loop_scope`.
- Los `test/*.http` asumen una base **vacía** (ids desde 1) y crean sus propios datos.

## Goals / Non-Goals

**Goals:**
- Seed determinístico, idempotente y atómico, probado con TDD sobre la misma fixture SQLite.
- Presupuesto de consultas verificado por pytest para 1, 10 y 50 filas (no sólo evidencia manual).
- Evidencia `evidencia/*.log` regenerable con un comando, sin ensuciar la base.

**Non-Goals:**
- Invocar el seed desde el `Dockerfile`/entrypoint (C-07 decide cuándo; este change sólo garantiza que `python -m app.initial_data` funcione en cualquier entorno con `DATABASE_URL`).
- Cambiar servicios o contratos HTTP. Si la auditoría detecta un N+1 se trata como bug puntual.
- Reemplazar los `.http` por pruebas automáticas: los `tests/*.py` ya cubren el comportamiento; los `.http` son la evidencia manual que pide la consigna.

## Decisions

### Decisión 1: Seed idempotente por clave natural ("buscar o crear") en una transacción
- **Decisión**: `sembrar(session)` recorre los datos en orden de dependencia (editoriales → géneros → autores → libros + autorías → clientes → perfiles). Para cada fila busca por su clave natural y sólo inserta si no existe; hace `flush` para obtener ids y un único `commit` al final (`rollback` ante cualquier error). Devuelve `ResumenSeed` (filas creadas por entidad).
  - Claves: `editorial.nombre`, `genero.nombre`, `autor.nombre`, `libro.isbn`, `cliente.email`; el perfil por `cliente_id`; la autoría por `(libro_id, autor_id)`.
- **Alternativas**:
  - *Capturar `IntegrityError` por fila* (coherente con la regla dura 4/6): `autor.nombre` no tiene `UNIQUE`, así que duplicaría autores; además cada intento fallido obliga a un `SAVEPOINT` por fila y ensucia el log.
  - *`INSERT ... ON CONFLICT DO NOTHING`*: específico de dialecto (PostgreSQL vs SQLite en tests) y tampoco cubre `autor`.
  - *Centinela "si existe la primera editorial, no hacer nada"*: no repara cargas parciales ni tolera datos creados a mano con el mismo nombre (escenario "Carga parcial previa").
- **Razón**: la regla dura 6 ("sin SELECT previo") rige el **alta de libros por la API**, donde la FK es la garantía. El seed es una herramienta operativa cuyo requisito es la idempotencia; el `SELECT` por clave natural es la forma portable y explícita de lograrla. Las restricciones de la base siguen activas: si una carrera concurrente insertara lo mismo, el `UNIQUE` falla y la transacción entera se revierte (no queda nada a medias).

### Decisión 2: Datos del seed
Determinísticos, en `Decimal`, coherentes con los ejemplos de la consigna y de los `.http`:

| Entidad | Datos |
|---|---|
| Editoriales (3) | Sudamericana (Argentina), Emecé (Argentina), Anagrama (España) |
| Géneros (4) | Novela, Cuento, Poesía, Ensayo |
| Autores (5) | Julio Cortázar, Jorge Luis Borges, Adolfo Bioy Casares, Silvina Ocampo (Argentina); Edgar Allan Poe (Estados Unidos) |
| Libros (6) | *Rayuela* (Cortázar `autor`; Sudamericana; Novela; 25000.00) · *Ficciones* (Borges `autor`; Emecé; Cuento; 18000.00) · *Los que aman, odian* (Bioy `coautor` 1, Ocampo `coautor` 2; Emecé; Novela; 21000.00) · *Cuentos de Poe* (Poe `autor` 1, Cortázar `traductor` 2; Anagrama; Cuento; 27000.00) · *Antología de la literatura fantástica* (Borges, Ocampo, Bioy `coautor` 1..3; Sudamericana; sin género) · *El otro, el mismo* (Borges `autor`; Emecé; Poesía) |
| Clientes (2) | Tomás Pérez `tomas@example.com`, Ana Gómez `ana@example.com`, cada uno con perfil (teléfono, dirección) |

ISBN ficticios con formato fijo (`978-950-00-0001-1` … `-0006-6`) y stock > 0. El género *Ensayo* queda sin libros a propósito (listado de libros por género vacío). Un libro sin género ejercita `genero_id` opcional. Los valores exactos viven en constantes del módulo (una única fuente para el seed y sus tests).

### Decisión 3: Punto de entrada `python -m app.initial_data`
- `async def main() -> int`: importa los módulos `models` de los seis dominios (para que `SQLModel.metadata` esté completo, igual que `app/main.py`), ejecuta `create_all` con `get_engine()`, abre una sesión de `get_session_factory()`, llama a `sembrar`, imprime el resumen y hace `dispose` del motor. Captura `OSError` y `SQLAlchemyError` → mensaje propio a `stderr` y código 1 (sin traza ni URL con contraseña).
- `if __name__ == "__main__": sys.exit(asyncio.run(main()))`.
- Todo asincrónico (regla dura 1): no se usa un motor sincrónico ni `psycopg`.

### Decisión 4: Presupuesto de consultas probado por pytest (fuente de verdad)
- `tests/test_auditoria_consultas.py`, parametrizado con `n ∈ {1, 10, 50}`, usando `client` + `contar_consultas`:
  - `GET /libros/?limit=n` → **1** sentencia (sin colección en el listado).
  - `GET /libros/{id}` de un libro con `n` autorías → **2**.
  - `GET /ventas/?limit=n` (ventas de 1 y 2 renglones) → **2**.
  - `GET /ventas/{id}` de una venta con `n` renglones → **2**.
  - `GET /clientes/?limit=n` (mitad con perfil) → **1**.
- Los datos de volumen se insertan directamente con el ORM en una sesión sobre `db_engine` (fixture/helper local), no con 50 `POST`, para que la prueba sea rápida; el conteo se mide **sólo** sobre la petición `GET` (`contar_consultas.clear()` antes).
- Se afirma el número exacto (no sólo "igual entre tamaños") porque el número es el contrato de la spec.
- `selectinload` agrupa hasta 500 claves por consulta `IN`; como `limit ≤ 100` (RN-10) el presupuesto es constante en todo el rango válido. Se documenta en el test.

### Decisión 5: Evidencia generada por script, no a mano
- **Decisión**: `scripts/auditar_consultas.py` (paquete `scripts/`), ejecutable con `python -m scripts.auditar_consultas [--salida evidencia]`:
  1. Fuerza `SQL_ECHO=true` (variable de entorno + `get_settings.cache_clear()`/`get_engine.cache_clear()`), así la traza es exactamente la del motor de la aplicación con echo activo.
  2. Abre **una conexión** y una transacción externa; inserta el volumen (50 libros, 50 ventas, catálogo y clientes mínimos) en esa transacción.
  3. Sobrescribe `get_session` con sesiones ligadas a esa conexión (modo de unión por defecto: sólo lecturas, no hay `commit` ni `SAVEPOINT` que ensucie el conteo) y llama a la API vía `httpx.AsyncClient(ASGITransport(app))`.
  4. Para cada tamaño (1, 10, 50) agrega un `logging.FileHandler` al logger `sqlalchemy.engine.Engine`, escribe un encabezado `=== GET /libros/?limit=N ===`, hace la petición, escribe `--- sentencias: K ---` (contadas con el mismo listener `before_cursor_execute`) y quita el handler.
  5. `rollback` de la transacción externa: la base queda como estaba (escenario "Sin efectos sobre la base").
- El núcleo es una función `async def auditar(engine, destino: Path) -> dict[str, dict[int, int]]` probada con TDD sobre `db_engine` (archivos escritos, conteos iguales por tamaño, sin filas nuevas tras el rollback). `main()` sólo resuelve el motor configurado.
- **Alternativa**: copiar a mano la salida de `uvicorn` con `SQL_ECHO=true` → no reproducible, mezcla logs de acceso y depende de cargar 50 filas a mano.
- La evidencia que se versiona en `evidencia/` se genera **contra PostgreSQL** (motor objetivo); cada archivo empieza con un comentario con el comando y la fecha de generación.

### Decisión 6: Auditoría de `test/*.http` como matriz, no reescritura
- Se arma la matriz RN-01..RN-12 × archivo y se agregan sólo los casos faltantes, al final de cada archivo, manteniendo la convención existente (`### N. Título (RN-xx)` + `# Esperado:`). Huecos detectados al preparar este diseño (a confirmar en la auditoría):
  - RN-04: `POST /renglones/` inexistente → `404` (no hay alta de renglones por separado).
  - RN-10: paginación inválida en `test/clientes.http`.
  - RN-12: anotar en los `409` existentes que el `detail` no contiene nombres de tablas/restricciones.
  - Comprobante en segundo plano: anotar en el caso 1 de `test/ventas.http` qué línea debe verse en el log después del `201`.
- Precondición documentada en cada archivo: **base vacía** (sin seed). El seed no se usa como precondición de los `.http` porque cambiaría los ids que estos archivos fijan.

### Decisión 7: Configuración de pytest
- `pytest.ini` en la raíz con `testpaths = tests` y `asyncio_default_fixture_loop_scope = function`. Se mantiene el modo `strict` (los tests ya usan `@pytest.mark.asyncio`).

## UI Mockups
- Design system revision: n/a
- Decision: no (no UI) — 2026-11-09
- Mockups: n/a

## Risks / Trade-offs
- **[Conteos distintos entre SQLite y PostgreSQL]** → los conteos de las consultas de la aplicación no dependen del dialecto (mismas opciones de carga). El driver asyncpg puede emitir sentencias propias al conectar (p. ej. consulta de versión); ocurren en la primera conexión, antes de los marcadores, y no entran en las secciones. Si apareciera alguna dentro, el script la registra y la diferencia se explica en el encabezado del log.
- **[Seed choca con datos de los `.http`]** → *Sudamericana* o *Rayuela* existen en ambos; ejecutar un `.http` sobre una base sembrada da `409` donde espera `201`. Mitigación: precondición "base vacía" explícita en los `.http`; el seed es para demo/despliegue.
- **[`autor.nombre` sin `UNIQUE`]** → dos autores homónimos creados a mano harían ambigua la búsqueda; el seed toma el de menor `id`. Aceptable para datos de demostración.
- **[Evidencia desactualizada]** → si cambia un servicio, el pytest de presupuesto falla primero; el log se regenera con un comando.

## Migration Plan
- Aditivo: no hay cambios de esquema ni de API. Rollback = borrar los archivos nuevos. El seed puede ejecutarse en el VPS después del primer arranque (C-07 documenta el paso en `DEPLOY.md`).
