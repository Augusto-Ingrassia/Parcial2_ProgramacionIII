# Tasks

> Modo TDD estricto (RED → GREEN → REFACTOR) con las fixtures de `tests/conftest.py` (`db_engine` SQLite con `PRAGMA foreign_keys=ON`, `client`, `contar_consultas`). Comando: `.venv/Scripts/python -m pytest -q`. Línea base esperada: 190 tests en verde.

## 1. Configuración de pytest

- [x] 1.1 Safety net: ejecutar la suite y registrar la línea base (190 en verde). Crear `pytest.ini` con `testpaths = tests` y `asyncio_default_fixture_loop_scope = function`. Verificación: la suite sigue en 190 y desaparece la advertencia `PytestDeprecationWarning` de pytest-asyncio.

## 2. Presupuesto de consultas (tests de caracterización)

- [x] 2.1 Helper de volumen en `tests/test_auditoria_consultas.py`: inserta con el ORM sobre `db_engine` N libros (con editorial/género), libros con N autorías, N ventas con 1–2 renglones, ventas con N renglones y N clientes (mitad con perfil). Verificación: un test que comprueba las cantidades insertadas.
- [x] 2.2 RED/GREEN: `GET /libros/?limit=n` para n ∈ {1, 10, 50} devuelve n libros con `editorial`/`genero` y emite exactamente 1 sentencia. Verificación: test parametrizado en verde (si falla, el N+1 es un bug a corregir en `libros/service.py`).
- [x] 2.3 RED/GREEN: `GET /libros/{id}` con 1, 10 y 50 autorías → 2 sentencias y todos los autores. Verificación: test parametrizado.
- [x] 2.4 RED/GREEN: `GET /ventas/?limit=n` (n ∈ {1, 10, 50}) → 2 sentencias, cada venta con `cliente` y todos sus `renglones`. Verificación: test parametrizado.
- [x] 2.5 RED/GREEN: `GET /ventas/{id}` con 1, 10 y 50 renglones → 2 sentencias. Verificación: test parametrizado.
- [x] 2.6 RED/GREEN: `GET /clientes/?limit=n` (n ∈ {1, 10, 50}) → 1 sentencia. Verificación: test parametrizado.
- [x] 2.7 REFACTOR: extraer el helper de volumen y una función `medir(client, contar_consultas, url) -> int` si se repite; documentar en el módulo el límite de 500 claves de `selectinload` frente a `limit ≤ 100`. Verificación: suite en verde.

## 3. Seed `app/initial_data.py`

- [x] 3.1 RED: `tests/test_initial_data.py` — `sembrar(session)` sobre base vacía crea 3 editoriales, 4 géneros, 5 autores, 6 libros y 2 clientes con perfil, y devuelve un `ResumenSeed` con esas cantidades. GREEN: constantes de datos (design.md Decisión 2) y `sembrar` con "buscar o crear" por clave natural y un único `commit`.
- [x] 3.2 RED/GREEN (triangulación): roles `autor`, `coautor` y `traductor` presentes; al menos un libro con ≥ 2 autores; un libro sin género; precios `Decimal` exactos. Verificación: leer por la API (`GET /libros/{id}`) con el `client` sobre la base sembrada.
- [x] 3.3 RED/GREEN: idempotencia — segunda llamada devuelve 0 creados y las cantidades por entidad no cambian. Verificación: test.
- [x] 3.4 RED/GREEN: carga parcial previa — con "Sudamericana" ya creada por `POST /editoriales/`, `sembrar` la reutiliza, no lanza `IntegrityError` y queda una sola. Verificación: test.
- [x] 3.5 RED/GREEN: atomicidad — si falla una inserción a mitad (p. ej. `monkeypatch` que fuerza un error al crear los clientes), no queda ninguna fila del seed. Verificación: test.
- [x] 3.6 RED/GREEN: datos aptos para vender — tras sembrar, `POST /ventas/` con un cliente y un libro del seed → `201` con el `precio_unitario` del libro. Verificación: test.
- [x] 3.7 RED/GREEN: `main()` — con `DATABASE_URL` apuntando a un SQLite temporal (vía `monkeypatch.setenv` + `cache_clear()` de `get_settings`/`get_engine`/`get_session_factory`) crea tablas, siembra y devuelve 0; con una URL inaccesible devuelve 1 y escribe en `stderr` un mensaje propio sin la URL. Implementar `if __name__ == "__main__": sys.exit(asyncio.run(main()))`. Verificación: tests + `python -m app.initial_data` manual contra SQLite temporal dos veces (la segunda informa 0 creados).
- [x] 3.8 REFACTOR: helper `_obtener_o_crear(session, modelo, clave, valores)`; nada bloqueante; type hints completos. Verificación: suite en verde.

## 4. Generador de evidencia `scripts/auditar_consultas.py`

- [x] 4.1 RED: `tests/test_auditar_consultas.py` — `auditar(engine, destino)` sobre `db_engine` escribe `queries_libros.log` y `queries_ventas.log` con secciones `limit=1`, `limit=10`, `limit=50`, cada una con sentencias SQL y la línea de cantidad; devuelve `{"libros": {1: 1, 10: 1, 50: 1}, "ventas": {1: 2, 10: 2, 50: 2}}`. GREEN: `scripts/__init__.py` y `auditar` según design.md Decisión 5 (transacción externa, override de `get_session`, `FileHandler` en `sqlalchemy.engine.Engine`, listener de conteo).
- [x] 4.2 RED/GREEN: sin efectos — tras `auditar`, las cantidades de `libro`, `venta`, `cliente`, `editorial`, `genero` y `autor` son las mismas que antes. Verificación: test.
- [x] 4.3 GREEN: `main()` con `--salida` (por defecto `evidencia/`), fuerza `SQL_ECHO=true`, usa el motor configurado y escribe en cada log un encabezado con el comando, el motor (dialecto, sin credenciales) y la fecha. Verificación: `python -m scripts.auditar_consultas --salida <tmp>` contra SQLite temporal genera ambos archivos.
- [x] 4.4 Generar la evidencia versionada contra PostgreSQL 16 (o el disponible; anotar la versión): `SQL_ECHO=true DATABASE_URL=postgresql+asyncpg://... python -m scripts.auditar_consultas`. Verificación: `evidencia/queries_libros.log` (1/1/1) y `evidencia/queries_ventas.log` (2/2/2) presentes, con JOIN en la principal y `IN` en la secundaria; la base conserva sus cantidades. **Resultado (2026-11-09)**: ejecutado contra PostgreSQL 17.11 local (desvío aceptable respecto de PG 16); `queries_libros.log` 1/1/1 (JOIN en la principal) y `queries_ventas.log` 2/2/2 (JOIN + `IN` secundaria); la base conservó 0 filas tras el rollback; sin credenciales en los logs.

## 5. Auditoría de `test/*.http`

- [x] 5.1 Armar la matriz RN-01..RN-12 × archivo `.http` (en el resumen del apply, no en un archivo nuevo) y confirmar los huecos de design.md Decisión 6. Verificación: cada RN tiene al menos un caso que la ejercita o una justificación.
- [x] 5.2 Agregar sólo los casos faltantes con la convención existente (`### N. Título (RN-xx)` + `# Esperado:`): `POST /renglones/` → `404` (RN-04); paginación inválida en `test/clientes.http` (RN-10); nota RN-12 en los `409`; nota del comprobante en el caso 1 de `test/ventas.http`. Precondición "base vacía (sin seed)" visible al inicio de cada archivo. Verificación: diff limitado a casos nuevos y comentarios.
- [x] 5.3 Ejecutar `health`, `editoriales`, `generos`, `autores`, `libros`, `clientes` y `ventas` `.http` en ese orden contra PostgreSQL sobre base vacía con `SQL_ECHO=true`. Verificación: todas las respuestas con el código `# Esperado`; registrar el total en el resumen. **Resultado (2026-11-09)**: PostgreSQL 17.11, base vacía (reiniciada antes de cada archivo salvo `clientes` y `ventas`, que dependen de datos previos), `SQL_ECHO=true`: 98 peticiones, 89 con `# Esperado` coinciden y 9 son de preparación/sin código esperado (2xx); 0 discrepancias. Se corrigió `test/editoriales.http` (caso 10 sin precondición ejecutable: se agregó 10.0 que crea "Anagrama" y el PATCH apunta al id 3, porque el 409 del caso 2 consume el id 2 de la secuencia). El comprobante en segundo plano se registró en el log del servidor.
- [x] 5.4 Smoke del seed contra PostgreSQL: `python -m app.initial_data` dos veces sobre una base limpia; luego `GET /libros/` (6) y `GET /clientes/` (2). Verificación: la primera corrida informa 3 editoriales, 4 géneros, 5 autores, 6 libros, 10 autorías, 2 clientes y 2 perfiles; la segunda informa 0. **Resultado (2026-11-09)**: 1.ª corrida 3/4/5/6/10/2/2; 2.ª corrida todo 0; `GET /libros/` devuelve 6 y `GET /clientes/` devuelve 2.

## 6. Cierre

- [x] 6.1 Ejecutar la suite completa: 190 previos + nuevos en verde, sin advertencias de pytest-asyncio. Verificación: salida de `pytest -q`.
- [x] 6.2 Revisar reglas duras: nada bloqueante en seed/script (todo `async`), montos en `Decimal`, sin lazy loading, ningún endpoint nuevo. Verificación: `grep` de `time.sleep|requests|float(` sobre los archivos nuevos sin resultados.

## Workflow follow-up

- Verificar con `openspec-verify` y archivar con `/opsx:archive suite-pruebas-integral-seed-y-auditoria-n1`; marcar `[C-06]` en `CHANGES.md`.
- C-07: invocar `python -m app.initial_data` desde el contenedor (paso opcional en `DEPLOY.md`).
