# Design: Correcciones pre-entrega

## Context
Motivación en `proposal.md` §Why; requisitos en los deltas de `specs/` (`health`, `core-infrastructure`, `presupuesto-consultas`). Estado actual relevante, observado en el código:

- `app/modules/health/router.py` arma el `503` con `detail=f"Base de datos no disponible: {str(exc)}"`. El texto de la excepción de asyncpg/SQLAlchemy puede incluir host, usuario y, según el error, la URL completa.
- `app/core/database.py` expone `get_engine()` y `get_session_factory()` como singletons `@lru_cache`, y `get_session()` (sin parámetros) toma la fábrica de esa caché global. `app/main.py` llama a `get_engine()` en el `lifespan` y guarda sólo `app.state.engine`.
- Consumidores fuera de la app: `app/initial_data.py` (`get_engine()` + `get_session_factory()()`) y `scripts/auditar_consultas.py` (limpia las cachés, usa `get_engine()` y sobreescribe `get_session` con `dependency_overrides`).
- Tests: `tests/conftest.py` sobreescribe `get_session` con `app.dependency_overrides` y usa `ASGITransport`, que **no** ejecuta el `lifespan`; `tests/test_main.py` sustituye `main_mod.get_engine` para probar el `lifespan`; `tests/test_database.py` sustituye `app.core.database.get_session_factory` para probar `get_session`; `tests/test_initial_data.py` y `tests/test_auditar_consultas.py` limpian las cachés `get_settings`/`get_engine`/`get_session_factory`. Línea base: 238 tests en verde.
- `tests/test_contenedor.py::test_requirements_runtime_sin_dependencias_de_test` lista las dependencias de ejecución requeridas.
- `scripts/auditar_consultas.py` inserta 50 libros (sin autorías) y 50 ventas de 1 o 2 renglones dentro de una transacción externa que revierte, y sólo mide `GET /libros/?limit=N` y `GET /ventas/?limit=N`. Los presupuestos de detalle ya están garantizados por `tests/test_auditoria_consultas.py` (2 sentencias para 1, 10 y 50 autores/renglones), pero no hay evidencia escrita.

## Goals / Non-Goals

**Goals:**
- La ruta HTTP de la app obtiene sus sesiones exclusivamente de `app.state.session_factory`, creada en el `lifespan`.
- Scripts y suite actual siguen funcionando sin reescrituras de fondo: sólo se ajustan los tests que fijaban detalles internos ahora cambiados.
- El readiness no filtra nada de la base, ni en la respuesta ni en los logs.

**Non-Goals:**
- No se cambia ningún router de dominio ni `SessionDep` (sigue siendo `Annotated[AsyncSession, Depends(get_session)]`).
- No se eliminan `get_engine()` / `get_session_factory()` ni se cambia cómo los usan los scripts.
- No se agrega `load_dotenv()` explícito: `pydantic-settings` ya usa `python-dotenv` para `env_file`; sólo se declara la dependencia.
- No se regeneran evidencias D-xx ni se toca `DEPLOY.md`/`README.md`.

## Decisions

### D1. Readiness con mensaje fijo y log genérico
Constante de módulo `MSG_BD_NO_DISPONIBLE = "Base de datos no disponible"` en `app/modules/health/router.py`. Tanto la rama de excepción como la de "respuesta inesperada" (`SELECT 1` distinto de 1) responden `HTTPException(503, detail=MSG_BD_NO_DISPONIBLE)`; en la de excepción se lanza `from None` (igual que `commit_o_http` en `app/core/exceptions.py`) para no encadenar la causa. Se registra con `logging.getLogger("uvicorn.error").warning("Readiness: la base de datos no respondió a SELECT 1")`, **sin** `exc_info` ni el texto de `exc`, por el mismo motivo que el `lifespan` (la causa puede contener `DATABASE_URL`).

- *Alternativa descartada*: registrar `type(exc).__name__` para diagnóstico. Es inofensivo, pero no aporta frente al HEALTHCHECK/`docker logs` del lifespan y abre la puerta a que alguien agregue luego el mensaje; se mantiene la línea genérica.
- *Status*: se mantiene `503` (lo que el código ya devuelve y documenta `DEPLOY.md`); el delta de `health` corrige el `500` que figuraba por error en la spec principal.
- El test existente `"Base de datos no disponible" in detail` sigue pasando; se agrega uno que exige igualdad exacta y ausencia de un secreto inyectado en el texto de la excepción, en la respuesta y en `caplog`.

### D2. Constructores puros + singletons sólo para scripts
En `app/core/database.py`:

```python
def crear_motor() -> AsyncEngine:                        # sin caché
    settings = get_settings()
    return create_async_engine(settings.DATABASE_URL, echo=settings.SQL_ECHO, future=True)

def crear_fabrica_sesiones(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

@lru_cache
def get_engine() -> AsyncEngine:                         # scripts fuera de la app
    return crear_motor()

@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return crear_fabrica_sesiones(get_engine())
```

La configuración del motor y de la fábrica vive en un solo lugar (`crear_*`); los singletons cacheados quedan como envoltorio para `app/initial_data.py` y `scripts/auditar_consultas.py`, que no cambian.

- *Por qué el `lifespan` no usa `get_engine()`*: el singleton sobrevive al `dispose()` del apagado y se compartiría entre ciclos de vida (tests, recargas); con `crear_motor()` el `lifespan` es dueño exclusivo de sus recursos, que es lo que pide la consigna ("se crean en el lifespan"). Además, si se usara `get_session_factory()` en el `lifespan`, la fábrica quedaría ligada al motor cacheado y no al del `lifespan` cuando éste se sustituye en pruebas.
- *Alternativa descartada*: borrar los singletons y que los scripts llamen a `crear_*`. Obligaría a reescribir `initial_data.py`, el script de auditoría y sus tests (limpieza de cachés) sin beneficio para la consigna.

### D3. `lifespan` guarda motor y fábrica
`app/main.py` importa `crear_motor` y `crear_fabrica_sesiones`:

```python
engine = crear_motor()
app.state.engine = engine
app.state.session_factory = crear_fabrica_sesiones(engine)
# create_all fail-fast idéntico al actual (log propio, dispose, raise)
yield
await app.state.engine.dispose()
```

El bloque fail-fast no cambia. `tests/test_main.py` pasa a sustituir `main_mod.crear_motor` en lugar de `main_mod.get_engine` (los dos tests existentes del `lifespan`), y el test de arranque exitoso agrega aserciones sobre `app.state.session_factory` (ligada al motor del `lifespan`, `expire_on_commit=False`).

### D4. `get_session(request: Request)` desde `app.state`
```python
async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with request.app.state.session_factory() as session:
        yield session
```

Una sesión por petición, cerrada al salir del `async with`. Sin fallback a la caché global: si la app se usara sin `lifespan` y sin override, falla con `AttributeError` (500) en vez de crear un motor oculto fuera del ciclo de vida, lo que haría la regla del Ejercicio 1 decorativa.

Compatibilidad:
- `tests/conftest.py`, `tests/test_health.py` y `scripts/auditar_consultas.py` sobreescriben `get_session` por identidad de función en `app.dependency_overrides`; el override sin parámetros sigue siendo válido (FastAPI resuelve la firma del override, no la del original). No cambian.
- Los routers usan `SessionDep` / `Depends(get_session)`; FastAPI inyecta `Request` solo. No cambian.
- `tests/test_database.py::test_get_session_yields_session` se reescribe: en lugar de sustituir `get_session_factory`, construye un request mínimo (`SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(session_factory=fabrica)))`) y verifica la sesión; se agregan la triangulación (dos llamadas → sesiones distintas de la misma fábrica) y la prueba de que la ruta no toca la caché global (sustituir `get_session_factory` por una función que falla no afecta a `get_session`).
- Prueba de integración nueva en `tests/test_main.py`: `async with lifespan(app)` sobre la app real con `crear_motor` sustituido por un SQLite temporal y **sin** `dependency_overrides`; `GET /health/ready` por `ASGITransport` responde 200, demostrando el camino completo `lifespan → app.state.session_factory → get_session`.

### D5. `python-dotenv` explícita
Línea `python-dotenv>=1.0` en `requirements.txt` y `"python-dotenv"` en la lista de requeridas de `test_requirements_runtime_sin_dependencias_de_test` (RED primero). Es wheel `py3-none-any`, compatible con `--only-binary=:all:`; ya se instala como transitiva de `pydantic-settings`, así que el tamaño de la imagen no cambia.

### D6. Auditoría con secciones de detalle
`scripts/auditar_consultas.py`:

- **Volumen**: `_insertar_volumen` además crea 50 autores; asigna autorías a tres libros con 1, 10 y 50 autores (`DETALLES = (1, 10, 50)`, mismos tamaños que la spec de presupuesto) y crea tres ventas adicionales con 1, 10 y 50 renglones sobre `libros[:k]` (total = `PRECIO * k`). Devuelve los ids: `{"libros": {k: id}, "ventas": {k: id}}`. Los listados no cambian de resultado: el listado de libros no carga autores y el de ventas sigue devolviendo exactamente `limit` filas (hay ≥ 50). Todo sigue dentro de la transacción externa que se revierte.
- **Medición**: `_medir` se generaliza para recibir la URL, el rótulo de la sección y un validador de la respuesta (listado: `len(json) == n`; detalle de libro: `len(json["autores"]) == k`; detalle de venta: `len(json["renglones"]) == k`). Formato de marcadores, después de las tres secciones de listado del mismo archivo:
  - `=== GET /libros/<id> (detalle, autores=<k>) ===`
  - `=== GET /ventas/<id> (detalle, renglones=<k>) ===`

  seguidos de las sentencias y `--- sentencias: <n> ---` como hoy. El id real va en la URL (en PostgreSQL las secuencias no se revierten, así que cambia entre corridas; el rótulo `k` es lo estable).
- **Retorno de `auditar`**: se agregan dos claves: `{"libros": {...}, "ventas": {...}, "detalle_libro": {1: 2, 10: 2, 50: 2}, "detalle_venta": {1: 2, 10: 2, 50: 2}}`. `main()` imprime las cuatro.
- **Tests** (`tests/test_auditar_consultas.py`): el parser `_secciones` pasa a partir por cualquier marcador `^=== GET (.+?) ===$` y devuelve `{rótulo: contenido}`; se actualiza la aserción de conteos; se agregan aserciones de las secciones de detalle (presentes para 1, 10 y 50 y con `--- sentencias: 2 ---`; la de detalle de libro muestra la consulta `IN` sobre `libro_autor`); `TABLAS` de `test_auditar_no_deja_datos_en_la_base` suma `LibroAutor` y `RenglonVenta`; `test_main_genera_ambos_archivos_con_encabezado` verifica la presencia de los marcadores de detalle. `tests/test_auditoria_consultas.py` no necesita cambios (ya cubre los presupuestos de detalle sobre la API); sólo se revisa que siga en verde.

## Risks / Trade-offs
- [Un test o script que llame a un endpoint con sesión sin `lifespan` y sin override pasa a fallar] → Revisado: todos los que usan sesión sobreescriben `get_session`; `test_health_live_endpoint` no usa sesión. La suite completa es la verificación.
- [El conteo de sentencias del detalle en SQLite difiere del de PostgreSQL] → Los tests de presupuesto ya validan 2 en SQLite y la evidencia de listados muestra el mismo patrón en PostgreSQL; la regeneración real (tarea manual) lo confirma.
- [Insertar 50 autorías y 61 renglones extra alarga el script] → Volumen chico, dentro de una transacción; impacto despreciable.
- [El log genérico del readiness dificulta el diagnóstico] → El `lifespan` y `docker logs` de PostgreSQL siguen siendo la fuente; se prioriza RN-12.

## Migration Plan
Sin migraciones de datos ni de esquema. Tras el apply: regenerar `evidencia/*.log` contra PostgreSQL (`python -m scripts.auditar_consultas --salida evidencia` con `DATABASE_URL` apuntando a PostgreSQL 16) y commitear los logs. Rollback: revertir el commit; no hay estado persistente afectado.
