# Tasks

## 1. Dependencias y Configuración Base

- [x] 1.1 Crear `requirements.txt` con las versiones mínimas del stack (`fastapi>=0.111.0`, `sqlmodel>=0.0.24`, `asyncpg>=0.30.0`, `uvicorn[standard]>=0.30.0`, `pydantic-settings>=2.3.0`) y plantilla `env.example` con `DATABASE_URL`, `SQL_ECHO` y `APP_PORT`.
- [x] 1.2 Implementar `app/core/config.py` con el modelo `Settings` de `pydantic-settings` y verificar que cargue variables desde `.env` con valores por defecto seguros.

## 2. Motor Asincrónico y Sesiones

- [x] 2.1 Implementar `app/core/database.py` con `create_async_engine`, fábrica de sesiones `async_sessionmaker(expire_on_commit=False)` y la dependencia generadora asincrónica `get_session`.
- [x] 2.2 Verificar la conectividad asincrónica del motor y la correcta inyección de la sesión mediante prueba unitaria/script de comprobación.

## 3. Módulo Health y Ciclo de Vida

- [x] 3.1 Implementar `app/modules/health/router.py` con las rutas `GET /health/live` (respondiendo `{"estado": "vivo"}`) y `GET /health/ready` (ejecutando `SELECT 1` sobre la sesión asincrónica).
- [x] 3.2 Implementar `app/main.py` con la función `@asynccontextmanager def lifespan(app: FastAPI)` que cree las tablas mediante `conn.run_sync(SQLModel.metadata.create_all)`, guarde el motor en `app.state`, ejecute `engine.dispose()` al cerrar y registre el router de health.

## 4. Pruebas y Verificación

- [x] 4.1 Crear el archivo `test/health.http` con las peticiones a `GET /health/live` y `GET /health/ready` con las respuestas y códigos esperados documentados en comentarios.
- [x] 4.2 Probar los endpoints de liveness y readiness levantando el servidor o ejecutando test suite para confirmar respuestas 200 OK y liveness sin I/O a base de datos.
