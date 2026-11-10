# API Librería — Parcial Programación III

API REST asincrónica para la gestión de una librería: catálogo (editoriales, géneros, autores, libros), clientes con perfil y ventas inmutables con renglones. Los precios y totales de las ventas los calcula el servidor y la integridad de los datos la garantiza PostgreSQL.

## Integrantes

- Lautaro Mejías
- Augusto Ingrassia
- Franco Squillo
- Uriel Vega
- Matheo Bazán
- Elías Pérez

## Stack

Python 3.12 · FastAPI · SQLModel · SQLAlchemy 2.0 asincrónico · asyncpg · PostgreSQL 16 · pydantic-settings · uvicorn · Docker (`python:3.12-alpine`).

La documentación de dominio está en `knowledge-base/` y el plan de changes en `CHANGES.md`. El despliegue en producción está en [DEPLOY.md](DEPLOY.md).

## Setup local

Requisitos: Python 3.12 o superior y una base PostgreSQL 16 accesible.

```bash
python -m venv .venv
# Windows (Git Bash): source .venv/Scripts/activate   |   Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt     # runtime + pruebas (requirements.txt es sólo runtime)
cp env.example .env                     # editar DATABASE_URL con sus credenciales
uvicorn app.main:app --reload
```

`DATABASE_URL` es obligatoria y no tiene valor por defecto: si falta, o si la base no es alcanzable al iniciar, la aplicación termina con error (arranque fail-fast). La documentación interactiva queda en `http://127.0.0.1:8000/docs`.

### Carga de datos iniciales (seed)

```bash
python -m app.initial_data
```

Es idempotente: ejecutarlo más de una vez no duplica filas.

## Pruebas

```bash
pytest -q
```

La suite usa SQLite en memoria/temporal (no requiere PostgreSQL ni Docker). Las colecciones de requests manuales están en `test/*.http`.

Evidencia de la auditoría de consultas (sin problema N+1): `evidencia/queries_libros.log` y `evidencia/queries_ventas.log`, generadas con `scripts/auditar_consultas.py`.

## Contenedor Docker

La imagen se construye sobre `python:3.12-alpine`, corre como `appuser` (sin root), no contiene secretos y expone el puerto 8000 con un `HEALTHCHECK` contra `http://127.0.0.1:8000/health/ready`.

Validación local (requiere Docker):

```bash
docker build -t libreria .
docker network create libreria-test
docker run -d --name libreria-db-test --network libreria-test \
  -e POSTGRES_PASSWORD=<password-temporal> -e POSTGRES_DB=libreria_db postgres:16-alpine
# .env.test (no versionado): DATABASE_URL=postgresql+asyncpg://postgres:<password-temporal>@libreria-db-test:5432/libreria_db
docker run -d --name libreria --network libreria-test -p 8000:8000 --env-file .env.test libreria
curl http://127.0.0.1:8000/health/live
docker inspect --format '{{.State.Health.Status}}' libreria
docker exec libreria python -m app.initial_data
```

Dentro de un contenedor `localhost` es el propio contenedor: el host de `DATABASE_URL` debe ser el nombre del contenedor de PostgreSQL (o el que corresponda al escenario). Los resultados de la validación y el procedimiento completo de despliegue, actualización y rollback están en [DEPLOY.md](DEPLOY.md).
