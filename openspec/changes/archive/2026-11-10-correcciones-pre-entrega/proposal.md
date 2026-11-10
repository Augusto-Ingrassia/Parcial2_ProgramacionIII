# Proposal: Correcciones pre-entrega

## Why
Con C-01 a C-07 archivados, una revisión contra la rúbrica de la consigna (`docs/Parcial_Cap1a4_Consigna.pdf`) encontró cuatro desvíos puntuales que restan puntos en la entrega: el readiness probe filtra el texto de la excepción de la base (viola RN-12 y puede exponer la `DATABASE_URL` con credenciales), la fábrica de sesiones no vive en `app.state` como exige el Ejercicio 1, `python-dotenv` no figura como dependencia explícita aunque la consigna la lista como componente obligatorio, y la evidencia del Caso C-07 sólo cubre listados, no los endpoints de detalle. Hay que corregirlos antes de entregar, sin tocar nada más.

## What Changes
- **Readiness sin internos de la base (RN-12)**: `GET /health/ready` ante una falla de la base responde `503` con un mensaje propio fijo (`"Base de datos no disponible"`), sin el texto de la excepción. Del lado del servidor se registra, a lo sumo, una línea genérica sin la excepción (mismo criterio que el `lifespan` de `app/main.py`). El escenario de la spec `health` se corrige de `500` a `503`, que es lo que el código ya devuelve y lo que documenta `DEPLOY.md`.
- **Motor y fábrica de sesiones en `app.state` (Ejercicio 1)**: el `lifespan` crea el motor **y** la fábrica de sesiones (`expire_on_commit=False`) y los guarda en `app.state.engine` y `app.state.session_factory`; al apagar cierra el motor. `get_session(request: Request)` entrega una sesión por petición tomada de `request.app.state.session_factory`. Los helpers `get_engine()` / `get_session_factory()` siguen disponibles para los scripts fuera de la app (`app/initial_data.py`, `scripts/auditar_consultas.py`); la ruta de la app ya no pasa por la caché global.
- **`python-dotenv` explícita**: se agrega `python-dotenv>=1.0` a `requirements.txt` (hoy sólo llega transitivamente vía `pydantic-settings`). Es una wheel pura, compatible con el `pip install --only-binary=:all:` del `Dockerfile`.
- **Evidencia C-07 de detalle**: `scripts/auditar_consultas.py` además de los listados mide `GET /libros/{id}` con 1, 10 y 50 autores y `GET /ventas/{id}` con 1, 10 y 50 renglones, y escribe esas secciones en `evidencia/queries_libros.log` y `evidencia/queries_ventas.log`, mostrando la misma cantidad fija de sentencias (2) en cada caso. La regeneración real de los `.log` contra PostgreSQL queda como tarea manual final.

## Capabilities

### New Capabilities
_(ninguna)_

### Modified Capabilities
- `health`: el escenario de falla del readiness pasa a `503` con mensaje propio fijo que no expone el texto de la excepción, la URL ni credenciales.
- `core-infrastructure`: el ciclo de vida guarda también la fábrica de sesiones en `app.state.session_factory`; la inyección de sesión toma la fábrica de `app.state`; la configuración declara `python-dotenv` como dependencia explícita de ejecución.
- `presupuesto-consultas`: la evidencia reproducible incluye las secciones de detalle de libro (1, 10, 50 autores) y de venta (1, 10, 50 renglones).

## Impact
- **Archivos tocados**: `app/modules/health/router.py`, `app/main.py`, `app/core/database.py`, `requirements.txt`, `scripts/auditar_consultas.py`, `evidencia/queries_libros.log`, `evidencia/queries_ventas.log` (regenerados).
- **Tests tocados**: `tests/test_health.py`, `tests/test_main.py`, `tests/test_database.py`, `tests/test_contenedor.py` (dependencia requerida), `tests/test_auditar_consultas.py`. `tests/conftest.py` no cambia: sigue sobreescribiendo `get_session` por `dependency_overrides`.
- **APIs**: sin endpoints nuevos ni cambios de esquema. Único cambio observable: el cuerpo del `503` de `/health/ready` deja de incluir el texto de la excepción.
- **Dependencias**: `python-dotenv>=1.0` explícita (ya estaba instalada como transitiva; la imagen no crece).
- **Fuera de alcance**: despliegue, `DEPLOY.md`, evidencias D-xx, cualquier otro refactor.
