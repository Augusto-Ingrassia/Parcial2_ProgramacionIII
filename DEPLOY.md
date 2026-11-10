# Despliegue — API Librería

## Datos del despliegue

| Dato | Valor |
|---|---|
| URL pública | http://46.202.151.202:8001 |
| Documentación interactiva | http://46.202.151.202:8001/docs |
| Fecha y hora del despliegue | (TBD) — completar al desplegar; el reloj del servidor está en UTC |
| Versión desplegada (commit / tag de imagen) | (TBD) |
| Servidor | VPS Ubuntu 24.04, arquitectura `x86_64`, Docker 29.7.1 |
| Dominio del VPS | `elgrupo3.tech` (la API se publica por IP y puerto, sin proxy ni TLS) |

> **El VPS es compartido por tres grupos de la cátedra** (Easypanel con Traefik en los puertos 80/443, panel de Easypanel en 3000 y Docker Swarm en 2377/7946). Operar **sólo** sobre los contenedores, la red y el volumen de este proyecto (`libreria`, `libreria-db`, `libreria-net`, `libreria-pgdata`). **Nunca** detener, borrar ni modificar contenedores, redes, volúmenes o imágenes de otros proyectos; no usar `docker system prune`, `docker container prune`, `docker volume prune` ni `docker image prune -a`. Los puertos 80, 443, 3000, 2377 y 7946 están ocupados.

## Arquitectura

```
Internet --> 46.202.151.202:8001 --> contenedor "libreria" (API, puerto interno 8000)
                                            |  red de usuario "libreria-net"
                                            v
                                     contenedor "libreria-db" (postgres:16-alpine)
                                            |  volumen con nombre "libreria-pgdata"
                                            v
                                     /var/lib/postgresql/data
```

- PostgreSQL **no publica ningún puerto** en el host: sólo la API lo alcanza por `libreria-net`, usando el nombre del contenedor como host (dentro de un contenedor `localhost` es el propio contenedor).
- Los datos viven en el volumen `libreria-pgdata`; el contenedor de la API es descartable.

## Variables de entorno (`.env.prod`)

Archivo en el VPS, fuera de git (`.env.*` está en `.gitignore` y `.dockerignore`), con permisos `600`. Nunca se hornea en la imagen. Contenido esperado (reemplazar los marcadores por los valores reales, que **no** se documentan aquí):

```
DATABASE_URL=postgresql+asyncpg://<usuario>:<password>@libreria-db:5432/<base>
SQL_ECHO=false
APP_PORT=8000
```

Para crear el contenedor de PostgreSQL se usan las mismas credenciales (`<usuario>`, `<password>`, `<base>`) en `POSTGRES_USER`, `POSTGRES_PASSWORD` y `POSTGRES_DB`.

## Despliegue inicial (en el VPS)

```bash
# 0. Verificaciones
docker --version
uname -m                                   # x86_64

# 1. Código
git clone <url-del-repositorio> libreria && cd libreria     # o: git pull

# 2. Secretos (una sola vez): crear .env.prod y restringirlo
chmod 600 .env.prod

# 3. Red y base de datos (una sola vez)
docker network create libreria-net
docker volume create libreria-pgdata
docker run -d --name libreria-db --network libreria-net \
  --restart unless-stopped \
  -e POSTGRES_USER=<usuario> -e POSTGRES_PASSWORD=<password> -e POSTGRES_DB=<base> \
  -v libreria-pgdata:/var/lib/postgresql/data \
  postgres:16-alpine

# 4. Imagen de la API
docker build -t libreria .

# 5. API (publicada en el puerto 8001 del host)
docker run -d --name libreria --network libreria-net \
  -p 8001:8000 --restart unless-stopped --env-file .env.prod libreria

# 6. Esperar a "healthy"
docker ps --filter name=libreria
docker inspect --format '{{.State.Health.Status}}' libreria

# 7. Carga inicial de datos (idempotente)
docker exec libreria python -m app.initial_data
```

> Si `<password>` contiene caracteres especiales (`@`, `:`, `/`, `%`), debe ir codificada como URL en `DATABASE_URL`.

Validación desde fuera del VPS:

```bash
curl http://46.202.151.202:8001/health/live    # {"estado":"vivo"}
curl http://46.202.151.202:8001/health/ready   # 200, confirma la conexión a PostgreSQL
curl http://46.202.151.202:8001/libros/        # 200 con los libros del seed
```

El contenedor se reinicia solo si cae el daemon o se reinicia el VPS (`--restart unless-stopped`). Si PostgreSQL todavía no está listo, la API termina al arrancar y Docker la reintenta con back-off hasta que conecta.

## Actualización en caliente sin pérdida de datos

Sólo se reemplaza el contenedor **`libreria`**. El contenedor `libreria-db` y el volumen `libreria-pgdata` **no se tocan**; `create_all` únicamente crea tablas que faltan, nunca borra ni altera datos. El corte es de unos segundos.

```bash
# 1. Traer el código nuevo y construir la imagen con una etiqueta de versión
git pull
V=$(git rev-parse --short HEAD)
docker build -t libreria:$V -t libreria:latest .       # la imagen anterior queda con su etiqueta

# 2. Apartar el contenedor actual (no se borra)
docker stop libreria
docker rename libreria libreria-prev

# 3. Levantar la versión nueva con los mismos flags
docker run -d --name libreria --network libreria-net \
  -p 8001:8000 --restart unless-stopped --env-file .env.prod libreria:$V

# 4. Esperar "healthy" y verificar con datos previos
docker inspect --format '{{.State.Health.Status}}' libreria
curl http://46.202.151.202:8001/health/ready
curl http://46.202.151.202:8001/ventas/               # las ventas anteriores siguen presentes

# 5a. Todo OK: descartar el contenedor anterior
docker rm libreria-prev

# 5b. Rollback si no queda "healthy": volver a la versión anterior
docker rm -f libreria
docker rename libreria-prev libreria
docker start libreria
```

Cuando `libreria-prev` ya no existe, `docker stop libreria-prev` no aplica; la imagen anterior sigue disponible por su etiqueta (`docker images libreria`) para recrear el contenedor con `docker run ... libreria:<versión-anterior>`.

## Diagnóstico

```bash
docker ps --filter name=libreria                         # estado: Up / (healthy) / Restarting
docker logs --tail 100 libreria                          # arranque y errores (sin credenciales)
docker inspect --format '{{json .State.Health}}' libreria
docker exec libreria id -un                              # appuser
docker logs --tail 50 libreria-db                        # lado PostgreSQL
```

- `Restarting` en `docker ps`: la API no logra arrancar (arranque fail-fast); casi siempre `DATABASE_URL` incorrecta o `libreria-db` caído. El log muestra "No se pudo conectar a la base de datos al iniciar; verifique DATABASE_URL" o el error de configuración de `DATABASE_URL` ausente.
- `unhealthy`: la API corre pero `/health/ready` falla (la base dejó de responder). Docker **no** reinicia el contenedor por estar `unhealthy`; revisar `libreria-db`.
- La API y la base deben estar en la misma red: `docker network inspect libreria-net`.

## Validación local (resultados)

Ejecutada en la máquina de desarrollo (Docker 29.8.2, Windows, Docker Desktop) antes del despliegue. El procedimiento completo es el de [README.md](README.md) §Contenedor Docker.

| Comprobación | Resultado |
|---|---|
| `docker build -t libreria .` | Exitoso, sin compilar nada (todas las dependencias instalan como wheels `musllinux`, `--only-binary=:all:`) |
| Tamaño de la base `python:3.12-alpine` | 74,1 MB (74.102.118 bytes), menor a 100 MB |
| Tamaño de la imagen final `libreria` | 187 MB (187.102.651 bytes) — el requisito de 100 MB aplica a la imagen base |
| `docker image inspect libreria --format '{{.Config.User}}'` | `appuser` |
| `docker run --rm --entrypoint pip libreria list` | Sin `pytest`, `pytest-asyncio`, `aiosqlite` ni `httpx` |
| `docker run --rm --entrypoint ls libreria -a /app` | Sólo `app` |
| `command -v gcc` dentro de la imagen | Vacío (código 127) |
| `docker history --no-trunc` / `docker image inspect` | Sin `DATABASE_URL` ni contraseñas |
| Reconstrucción tras tocar `app/main.py` | `pip install` reportado como `CACHED` |
| Contenedor con PostgreSQL 16 temporal | `docker exec libreria id -un` = `appuser`; `GET /health/live` 200; estado `healthy` |
| `python -m app.initial_data` x2 | Ambas código 0; la primera crea 3 editoriales, 4 géneros, 5 autores, 6 libros, 10 autorías, 2 clientes y 2 perfiles; la segunda crea 0 filas; `GET /libros/` devuelve 6 libros |
| Base detenida | Contenedor pasa a `unhealthy`; `/health/ready` responde 503 con detalle de base no disponible |
| `docker run` con la base detenida | Termina con código 3 ("Application startup failed"); el log muestra el mensaje propio y no contiene la URL ni la contraseña |
| `docker run` sin `--env-file` | Termina con código 3 por `DATABASE_URL` ausente |
| Procedimiento de actualización y rollback | Ensayado con una venta creada previamente: la venta siguió en `GET /ventas/` con el contenedor nuevo `healthy` y tras el rollback |

Dependencias resueltas en la imagen (`pip freeze`, fecha del build): fastapi 0.162.2, sqlmodel 0.0.48, SQLAlchemy 2.1.8, asyncpg 0.32.0, pydantic 2.14.3, pydantic-settings 2.16.2, uvicorn 0.54.0, uvloop 0.23.0, greenlet 3.5.6.

Nota: `/app/.env` no puede entrar en la imagen porque el `Dockerfile` copia únicamente `app/` (nunca `COPY . .`) y el `.dockerignore` además excluye `.env` y `.env.*`.
