# contenedor-docker Specification

## Purpose
Define la imagen de ejecución de la API: liviana sobre Alpine, ejecutada sin privilegios, sin secretos horneados, configurada sólo en tiempo de ejecución y con un healthcheck que refleja la disponibilidad real del servicio.

## Requirements

### Requirement: Imagen base oficial Alpine liviana
La imagen SHALL construirse a partir de la imagen oficial `python:3.12-alpine`, cuyo tamaño base es menor a 100 MB, sin agregar compiladores ni herramientas de build a la imagen final.

#### Scenario: Construcción con la base requerida
- **WHEN** se construye la imagen con `docker build -t libreria .` desde la raíz del repositorio
- **THEN** la construcción finaliza con éxito y la única imagen base declarada es `python:3.12-alpine`

#### Scenario: Imagen final sin toolchain de compilación
- **WHEN** se inspecciona la imagen final construida
- **THEN** no contiene `gcc` ni paquetes de desarrollo de compilación (`build-base`, `musl-dev`)

### Requirement: Ejecución sin privilegios de root
El proceso de la API dentro del contenedor SHALL ejecutarse con un usuario y grupo de sistema sin privilegios llamado `appuser`, nunca como `root`.

#### Scenario: Usuario efectivo del contenedor
- **WHEN** se ejecuta `docker exec libreria id -un` sobre un contenedor en marcha
- **THEN** la salida es `appuser`

#### Scenario: Usuario declarado en la imagen
- **WHEN** se ejecuta `docker image inspect libreria --format '{{.Config.User}}'`
- **THEN** la salida es `appuser`

### Requirement: Configuración inyectada sólo en tiempo de ejecución
La imagen MUST NOT contener contraseñas, usuarios de base de datos, `DATABASE_URL` ni archivos `.env`; toda la configuración sensible SHALL proveerse al ejecutar el contenedor (por ejemplo con `--env-file`).

#### Scenario: Historial de la imagen sin secretos
- **WHEN** se inspeccionan las variables de entorno y el historial de capas de la imagen (`docker image inspect`, `docker history --no-trunc`)
- **THEN** no aparece `DATABASE_URL` ni ninguna contraseña

#### Scenario: Archivos de entorno fuera del contexto de build
- **WHEN** existe un archivo `.env` o `.env.prod` en la raíz y se construye la imagen
- **THEN** ese archivo no queda dentro de la imagen (`docker run --rm --entrypoint ls libreria -a /app` no lo lista)

### Requirement: Contenido de la imagen limitado al código de ejecución
La imagen SHALL contener sólo el paquete de la aplicación y sus dependencias de ejecución; MUST NOT incluir pruebas, evidencias, documentación, artefactos de OpenSpec, el repositorio git ni dependencias exclusivas de pruebas.

#### Scenario: Sin dependencias de prueba
- **WHEN** se lista lo instalado en la imagen (`pip list`)
- **THEN** no aparecen `pytest`, `pytest-asyncio` ni `aiosqlite`

#### Scenario: Sin archivos ajenos a la ejecución
- **WHEN** se lista el directorio de trabajo de la imagen
- **THEN** sólo contiene el paquete `app/` (sin `tests/`, `test/`, `evidencia/`, `.git/`, `docs/` ni `openspec/`)

### Requirement: Escucha HTTP en todas las interfaces del puerto 8000
El contenedor SHALL iniciar el servidor ASGI escuchando en `0.0.0.0:8000` y declarar el puerto `8000` como expuesto.

#### Scenario: API accesible desde el host
- **WHEN** se ejecuta el contenedor con `-p 8000:8000` y una `DATABASE_URL` válida y se envía `GET http://127.0.0.1:8000/health/live` desde el host
- **THEN** la respuesta es HTTP 200 con `{"estado": "vivo"}`

### Requirement: Healthcheck de readiness por IPv4
La imagen SHALL declarar un `HEALTHCHECK` periódico que consulte `GET /health/ready` contra `127.0.0.1:8000` (no `localhost`), de modo que el estado del contenedor refleje la conectividad con la base de datos.

#### Scenario: Contenedor saludable con base accesible
- **WHEN** el contenedor corre con una base de datos accesible y transcurre el período de arranque
- **THEN** `docker inspect --format '{{.State.Health.Status}}' libreria` informa `healthy`

#### Scenario: Contenedor no saludable si la base cae
- **WHEN** la base de datos deja de estar accesible con el contenedor ya en marcha y fallan los reintentos configurados
- **THEN** el estado de salud del contenedor pasa a `unhealthy`

#### Scenario: Healthcheck no depende de la resolución de localhost
- **WHEN** se inspecciona la configuración de salud de la imagen
- **THEN** el comando apunta a `http://127.0.0.1:8000/health/ready` y no contiene `localhost`

### Requirement: Construcción reproducible con caché de dependencias
La construcción SHALL instalar las dependencias antes de copiar el código fuente, sin conservar la caché de `pip`, de modo que un cambio sólo de código reutilice la capa de dependencias.

#### Scenario: Rebuild tras cambiar sólo código
- **WHEN** se modifica un archivo dentro de `app/` sin tocar `requirements.txt` y se reconstruye la imagen
- **THEN** el paso de instalación de dependencias se reporta como reutilizado desde caché (`CACHED`)
