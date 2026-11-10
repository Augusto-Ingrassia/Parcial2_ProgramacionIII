# Tasks

> Modo TDD estricto (RED → GREEN → TRIANGULATE → REFACTOR). Comando de pruebas: `python -m pytest -q` con el entorno de desarrollo (`pip install -r requirements-dev.txt`).
> Governance MEDIO (infra/core): implementar por grupos y reportar al cierre de cada grupo las decisiones no obvias.
> La tarea marcada **[MANUAL-PG]** requiere un PostgreSQL 16 accesible; la ejecuta el orquestador/equipo, no el agente de apply.

## 1. Línea base

- [x] 1.1 Safety net: ejecutar la suite completa y registrar la línea base (se esperan 238 tests en verde). Cualquier fallo previo se reporta y no se corrige. Verificación: salida de `python -m pytest -q`.

## 2. Readiness sin internos de la base (health, RN-12)

- [x] 2.1 RED: en `tests/test_health.py`, test con una sesión falsa cuyo `execute` lanza `OSError("connect failed postgresql+asyncpg://admin:S3cr3t-pw@db-host:5432/libreria_db")`: `GET /health/ready` responde 503 con `response.json() == {"detail": "Base de datos no disponible"}`, y ni el cuerpo ni `caplog.text` contienen `S3cr3t-pw`, `db-host` ni `postgresql+asyncpg`. Verificación: el test falla con el código actual (el detalle incluye el texto de la excepción).
- [x] 2.2 GREEN: en `app/modules/health/router.py` introducir `MSG_BD_NO_DISPONIBLE`, responder `HTTPException(503, detail=MSG_BD_NO_DISPONIBLE)` lanzada `from None` y registrar sólo la línea genérica de design.md D1 (sin `exc_info` ni texto de la excepción). Verificación: test 2.1 y los tres tests existentes de `tests/test_health.py` en verde.
- [x] 2.3 TRIANGULATE: test con una sesión cuyo `execute` devuelve un resultado con `scalar()` distinto de 1 → 503 con el mismo cuerpo exacto; y caso parametrizado con `SQLAlchemyError(<url secreta>)` además de `OSError`. REFACTOR: unificar ambas ramas en la constante. Verificación: `tests/test_health.py` en verde.

## 3. Constructores de motor y fábrica (core-infrastructure)

- [x] 3.1 RED: en `tests/test_database.py`, tests de `crear_fabrica_sesiones(engine)`: la fábrica queda ligada al motor recibido (`factory.kw["bind"] is engine`), `expire_on_commit is False` y `class_` subclase de `AsyncSession`; y de `crear_motor()`: devuelve `AsyncEngine` y dos llamadas devuelven instancias distintas (sin caché). Verificación: fallan por `ImportError`.
- [x] 3.2 GREEN: agregar `crear_motor()` y `crear_fabrica_sesiones(engine)` en `app/core/database.py` y reescribir `get_engine()` / `get_session_factory()` como envoltorios `@lru_cache` sobre ellos (design.md D2). Verificación: tests nuevos y `test_get_engine_creates_async_engine` / `test_session_factory_configuration` en verde; `tests/test_initial_data.py` y `tests/test_auditar_consultas.py` en verde sin cambios.

## 4. Lifespan guarda motor y fábrica en app.state

- [x] 4.1 RED: en `tests/test_main.py`, cambiar los dos tests del `lifespan` para sustituir `main_mod.crear_motor` (en lugar de `main_mod.get_engine`), y en `test_lifespan_exitoso_crea_tablas_y_libera_motor` agregar: `app_.state.session_factory` existe, `app_.state.session_factory.kw["bind"] is app_.state.engine` y `expire_on_commit is False`. Verificación: fallan (el `lifespan` actual no usa `crear_motor` ni guarda la fábrica).
- [x] 4.2 GREEN: en `app/main.py`, el `lifespan` usa `crear_motor()` y `crear_fabrica_sesiones(engine)` y guarda `app.state.engine` y `app.state.session_factory` (design.md D3), sin tocar el bloque fail-fast. Verificación: `tests/test_main.py` en verde, incluido `test_lifespan_propaga_error_y_libera_motor` (URL secreta ausente del log).

## 5. get_session desde app.state

- [x] 5.1 RED: reescribir `tests/test_database.py::test_get_session_yields_session` para pasar un request mínimo con `app.state.session_factory` (design.md D4) y verificar que entrega una `AsyncSession` funcional (`SELECT 1`) y que el generador termina; agregar un test que sustituye `app.core.database.get_session_factory` por una función que lanza y comprueba que `get_session(request)` igual funciona. Verificación: fallan con el `get_session()` actual (no acepta `request` / usa la caché global).
- [x] 5.2 GREEN: `get_session(request: Request)` hace `async with request.app.state.session_factory() as session: yield session`; `SessionDep` sin cambios. Verificación: tests de 5.1 en verde.
- [x] 5.3 TRIANGULATE: test de dos llamadas a `get_session` con el mismo request → dos sesiones distintas creadas por la misma fábrica, cada una cerrada al agotar su generador. Test de integración en `tests/test_main.py`: `async with main_mod.lifespan(main_mod.app)` con `crear_motor` sustituido por un SQLite temporal, sin `dependency_overrides`; `GET /health/ready` vía `ASGITransport` → 200. Verificación: ambos en verde y `app.dependency_overrides` vacío al terminar.
- [x] 5.4 Compatibilidad: suite completa en verde sin tocar `tests/conftest.py`, los routers ni `app/initial_data.py`. Verificación: `python -m pytest -q` con la línea base + tests nuevos.

## 6. python-dotenv explícita

- [x] 6.1 RED: agregar `"python-dotenv"` a la lista de requeridas en `tests/test_contenedor.py::test_requirements_runtime_sin_dependencias_de_test`. Verificación: el test falla.
- [x] 6.2 GREEN: agregar `python-dotenv>=1.0` a `requirements.txt`. Verificación: test 6.1 y el resto de `tests/test_contenedor.py` en verde; `pip install --dry-run --only-binary=:all: "python-dotenv>=1.0"` resuelve una wheel (compatibilidad con el `Dockerfile`).

## 7. Evidencia de detalle en la auditoría (presupuesto-consultas)

- [x] 7.1 RED: en `tests/test_auditar_consultas.py`, generalizar `_secciones` a cualquier marcador `^=== GET (.+?) ===$` (clave = rótulo completo); actualizar `test_auditar_escribe_los_logs_y_devuelve_los_conteos` para esperar además `"detalle_libro": {1: 2, 10: 2, 50: 2}` y `"detalle_venta": {1: 2, 10: 2, 50: 2}` y secciones `(detalle, autores=1|10|50)` en `queries_libros.log` y `(detalle, renglones=1|10|50)` en `queries_ventas.log`, cada una con `--- sentencias: 2 ---`; las de listado conservan sus conteos. Verificación: falla con el script actual.
- [x] 7.2 GREEN: en `scripts/auditar_consultas.py`, ampliar `_insertar_volumen` (50 autores, libros con 1/10/50 autorías, ventas con 1/10/50 renglones, devolviendo los ids) y generalizar `_medir` con URL, rótulo y validador de respuesta según design.md D6; escribir las secciones de detalle después de las de listado; `main()` imprime las cuatro claves. Verificación: test 7.1 en verde.
- [x] 7.3 TRIANGULATE: en `test_el_log_muestra_join_en_la_principal_e_in_en_la_secundaria`, la sección de detalle de libro muestra `JOIN editorial` y una consulta sobre `libro_autor` con `IN (`, y la de detalle de venta `JOIN cliente` y `renglon_venta.venta_id IN (`; agregar `LibroAutor` y `RenglonVenta` a `TABLAS` en `test_auditar_no_deja_datos_en_la_base`; en `test_main_genera_ambos_archivos_con_encabezado` verificar la presencia de los marcadores de detalle. `test_auditar_es_repetible` sigue en verde. REFACTOR: constantes `DETALLES` y rótulos sin duplicación. Verificación: `tests/test_auditar_consultas.py` y `tests/test_auditoria_consultas.py` en verde.

## 8. Cierre

- [x] 8.1 Suite completa en verde (línea base + nuevos). Revisión de reglas duras sobre lo tocado: nada bloqueante en handlers, ningún texto de excepción de la base en respuestas o logs (`grep -n "str(exc)" app/` sin resultados), FKs y `Decimal` sin cambios. Verificación: salida de `python -m pytest -q`.
- [x] 8.2 **[MANUAL-PG]** Regenerar la evidencia contra PostgreSQL 16: `python -m scripts.auditar_consultas --salida evidencia` con `DATABASE_URL` de PostgreSQL. Verificar que `evidencia/queries_libros.log` y `evidencia/queries_ventas.log` tienen encabezado `# Motor: postgresql (asyncpg)`, las tres secciones de listado y las tres de detalle, con 1/2 sentencias en listados y 2 en todos los detalles, y que no contienen la URL ni credenciales. Commitear los logs.

## Workflow follow-up

- Verificar y archivar con `/opsx:archive correcciones-pre-entrega` (sincroniza los deltas de `health`, `core-infrastructure` y `presupuesto-consultas`).
