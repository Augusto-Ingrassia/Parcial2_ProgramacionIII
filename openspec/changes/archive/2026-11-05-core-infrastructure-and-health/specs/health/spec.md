# Spec Delta

## Purpose
Provee los endpoints de monitoreo operativo y diagnóstico de salud para verificar si la aplicación está viva y si la conexión a PostgreSQL está lista.

## ADDED Requirements

### Requirement: Health check de proceso vivo (liveness)
El sistema SHALL exponer un endpoint HTTP `GET /health/live` que confirme que el proceso de la aplicación está en ejecución sin interactuar con la base de datos.

#### Scenario: Consulta de estado de vida exitosa
- **WHEN** se envía una petición HTTP `GET` a `/health/live`
- **THEN** el sistema responde con código HTTP 200 y cuerpo JSON conteniendo `{"estado": "vivo"}` sin realizar consultas a la base de datos.

### Requirement: Health check de disponibilidad de base de datos (readiness)
El sistema SHALL exponer un endpoint HTTP `GET /health/ready` que ejecute una consulta de prueba asincrónica `SELECT 1` sobre PostgreSQL para verificar conectividad.

#### Scenario: Conectividad exitosa con PostgreSQL
- **WHEN** se envía una petición HTTP `GET` a `/health/ready` y la base de datos responde
- **THEN** el sistema responde con código HTTP 200 indicando que el servicio está listo para operar.

#### Scenario: Falla de conexión con PostgreSQL
- **WHEN** se envía una petición HTTP `GET` a `/health/ready` y la base de datos no está disponible o rechaza la conexión
- **THEN** el sistema propaga un error HTTP 500 indicando indisponibilidad de la base de datos.
