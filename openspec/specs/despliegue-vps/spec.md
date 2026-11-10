# despliegue-vps Specification

## Purpose
Garantiza que la API quede publicada y operable en el VPS de forma reproducible: URL pública registrada, comandos exactos sin secretos, carga inicial de datos, actualización sin pérdida de datos y documentación suficiente para ejecutarla y validarla desde cero.

## Requirements

### Requirement: API publicada en el VPS
La API SHALL quedar en ejecución en el VPS dentro de un contenedor con política de reinicio `unless-stopped`, accesible públicamente en la URL registrada en `DEPLOY.md`.

#### Scenario: Liveness pública
- **WHEN** un evaluador envía `GET <URL pública>/health/live` desde fuera del VPS
- **THEN** recibe HTTP 200 con `{"estado": "vivo"}`

#### Scenario: Readiness pública
- **WHEN** un evaluador envía `GET <URL pública>/health/ready`
- **THEN** recibe HTTP 200, confirmando que el contenedor alcanza PostgreSQL

#### Scenario: Reinicio del servidor
- **WHEN** el daemon de Docker o el VPS se reinicia
- **THEN** el contenedor vuelve a arrancar automáticamente sin intervención manual

### Requirement: Registro del despliegue
`DEPLOY.md` SHALL registrar la URL pública de la API, el día y la hora (con zona horaria) del despliegue y la versión desplegada (commit o tag de imagen).

#### Scenario: Datos de despliegue completos
- **WHEN** se lee `DEPLOY.md` en la raíz del repositorio
- **THEN** contiene la URL pública, la fecha y hora con zona horaria y el identificador de la versión desplegada, sin marcadores pendientes

### Requirement: Comandos de despliegue reproducibles sin secretos
`DEPLOY.md` SHALL documentar los comandos exactos de `docker build` y `docker run` usados en el VPS, nombrando el archivo de variables (`--env-file`) pero sin exponer su contenido, contraseñas ni la `DATABASE_URL` real.

#### Scenario: Reproducción del despliegue
- **WHEN** un integrante ejecuta en el VPS, en orden, los comandos de `DEPLOY.md` con su propio archivo de variables
- **THEN** obtiene el contenedor `libreria` en marcha y `GET /health/ready` responde 200

#### Scenario: Documentación sin credenciales
- **WHEN** se revisa `DEPLOY.md`, `README.md` y `env.example`
- **THEN** ninguno contiene una contraseña real ni la cadena de conexión de producción

### Requirement: Conectividad documentada con PostgreSQL
`DEPLOY.md` SHALL indicar dónde corre PostgreSQL respecto del contenedor y el host a usar en `DATABASE_URL` desde dentro del contenedor, sabiendo que `localhost` allí refiere al propio contenedor.

#### Scenario: Host de base resoluble desde el contenedor
- **WHEN** se sigue la sección de conectividad de `DEPLOY.md` para el escenario de base elegido
- **THEN** el host configurado en `DATABASE_URL` es alcanzable desde el contenedor y `GET /health/ready` responde 200

### Requirement: Carga inicial de datos en el contenedor
La carga de datos iniciales SHALL poder ejecutarse dentro del contenedor en marcha con `docker exec libreria python -m app.initial_data`, de forma idempotente.

#### Scenario: Primera carga
- **WHEN** se ejecuta el comando de carga sobre una base sin datos
- **THEN** finaliza con código 0 y `GET /libros/` devuelve los libros del seed

#### Scenario: Carga repetida
- **WHEN** se ejecuta el comando de carga por segunda vez
- **THEN** finaliza con código 0 sin duplicar filas

### Requirement: Actualización sin pérdida de datos
`DEPLOY.md` SHALL documentar paso a paso cómo reemplazar el contenedor por una versión nueva de la imagen conservando los datos de la base, y cómo volver a la versión anterior si la nueva no queda saludable.

#### Scenario: Actualización de versión
- **WHEN** se sigue el procedimiento de actualización con datos ya cargados
- **THEN** el contenedor nuevo queda `healthy` y los datos previos (por ejemplo, las ventas registradas) siguen disponibles por la API

#### Scenario: Rollback
- **WHEN** el contenedor nuevo no alcanza el estado `healthy`
- **THEN** el procedimiento documentado permite volver a ejecutar la imagen anterior sin pérdida de datos

### Requirement: README operativo del repositorio
El repositorio SHALL incluir un `README.md` en la raíz con la descripción del sistema, los nombres de los integrantes, el setup local, la ejecución de las pruebas y la validación del contenedor.

#### Scenario: Ejecución local desde cero
- **WHEN** una persona sin contexto previo sigue las instrucciones de setup local del `README.md`
- **THEN** puede instalar dependencias, ejecutar la suite de pruebas y levantar la API

#### Scenario: Integrantes identificados
- **WHEN** se lee el `README.md`
- **THEN** figuran los nombres de todos los integrantes del grupo, sin marcadores pendientes
