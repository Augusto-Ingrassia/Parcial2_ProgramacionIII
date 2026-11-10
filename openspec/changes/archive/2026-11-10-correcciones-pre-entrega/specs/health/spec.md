# Spec Delta: health

## MODIFIED Requirements

### Requirement: Health check de disponibilidad de base de datos (readiness)
El sistema SHALL exponer un endpoint HTTP `GET /health/ready` que ejecute una consulta de prueba asincrónica `SELECT 1` sobre PostgreSQL para verificar conectividad. Ante una falla, la respuesta MUST contener únicamente un mensaje propio fijo y MUST NOT exponer el texto de la excepción, la URL de conexión, credenciales, hosts ni nombres internos de la base (RN-12).

#### Scenario: Conectividad exitosa con PostgreSQL
- **WHEN** se envía una petición HTTP `GET` a `/health/ready` y la base de datos responde
- **THEN** el sistema responde con código HTTP 200 indicando que el servicio está listo para operar.

#### Scenario: Falla de conexión con PostgreSQL
- **WHEN** se envía una petición HTTP `GET` a `/health/ready` y la base de datos no está disponible o rechaza la conexión
- **THEN** el sistema responde con código HTTP 503 y cuerpo `{"detail": "Base de datos no disponible"}`, idéntico sea cual sea la causa de la falla.

#### Scenario: La falla no filtra internos de la base
- **WHEN** la consulta de prueba falla con un error cuyo texto incluye la URL de conexión con usuario, contraseña y host
- **THEN** ni el cuerpo de la respuesta 503 ni los registros del servidor contienen ese texto, la contraseña ni el host.
