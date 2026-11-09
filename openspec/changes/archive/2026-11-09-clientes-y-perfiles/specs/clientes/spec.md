# Spec Delta

## Purpose
Registra a los clientes de la librería con email único y su perfil opcional (teléfono y dirección) en relación uno a uno.

## ADDED Requirements

### Requirement: Alta de cliente
El sistema SHALL registrar un cliente mediante `POST /clientes/` con `nombre` y `email`, y responder `201 Created` con `id`, `nombre`, `email` y `perfil` igual a `null`. El email se normaliza a minúsculas y sin espacios.

#### Scenario: Alta exitosa
- **WHEN** se envía `POST /clientes/` con `{"nombre": "Tomás Ríos", "email": "Tomas@Example.com"}`
- **THEN** el sistema responde `201 Created` con `id` entero, `email` igual a `"tomas@example.com"` y `perfil` igual a `null`

#### Scenario: Datos inválidos
- **WHEN** se envía `POST /clientes/` sin `email`, con `nombre` en blanco o con un `email` sin `@`
- **THEN** el sistema responde `422 Unprocessable Entity`

### Requirement: Email único (RN-02)
El sistema SHALL rechazar con `409 Conflict` y mensaje propio toda alta o actualización que repita el email de otro cliente, delegando la detección en el `UNIQUE` de la base y sin exponer textos internos (RN-12).

#### Scenario: Alta con email repetido
- **WHEN** existe el cliente `tomas@example.com` y se envía `POST /clientes/` con el mismo email
- **THEN** el sistema responde `409 Conflict` con un `detail` propio y no crea el cliente

#### Scenario: PATCH al email de otro cliente
- **WHEN** existen los clientes 1 y 2 y se envía `PATCH /clientes/2` con el email del cliente 1
- **THEN** el sistema responde `409 Conflict` y el cliente 2 conserva su email

### Requirement: Listado y consulta de clientes con su perfil
El sistema SHALL listar clientes mediante `GET /clientes/` paginados (RN-10) y devolver un cliente mediante `GET /clientes/{id}`, incluyendo en ambos casos su `perfil` como objeto único o `null`, precargado en la misma consulta; y `404 Not Found` si el cliente no existe.

#### Scenario: Cliente con perfil
- **WHEN** el cliente 1 tiene perfil y se envía `GET /clientes/1`
- **THEN** el sistema responde `200 OK` con `perfil` como objeto con `id`, `cliente_id`, `telefono` y `direccion` (no una lista)

#### Scenario: Cliente inexistente
- **WHEN** se envía `GET /clientes/999`
- **THEN** el sistema responde `404 Not Found`

#### Scenario: Paginación inválida
- **WHEN** se envía `GET /clientes/?limit=101`
- **THEN** el sistema responde `422 Unprocessable Entity`

### Requirement: Actualización parcial de cliente
El sistema SHALL modificar mediante `PATCH /clientes/{id}` sólo los campos enviados y responder `200 OK` con el cliente y su perfil; `404` si no existe y `422` si el cuerpo es inválido.

#### Scenario: Cambio de nombre
- **WHEN** se envía `PATCH /clientes/1` con `{"nombre": "Tomás R."}`
- **THEN** el sistema responde `200 OK` con el nuevo nombre y el email sin cambios

#### Scenario: Null explícito
- **WHEN** se envía `PATCH /clientes/1` con `{"email": null}`
- **THEN** el sistema responde `422 Unprocessable Entity`

#### Scenario: Cliente inexistente
- **WHEN** se envía `PATCH /clientes/999` con `{"nombre": "X"}`
- **THEN** el sistema responde `404 Not Found`

### Requirement: Perfil uno a uno (RN-09)
El sistema SHALL crear el perfil de un cliente mediante `POST /clientes/{id}/perfil` con `telefono` y `direccion`, respondiendo `201 Created` con el perfil; SHALL responder `409 Conflict` si el cliente ya tiene perfil (garantizado por `UNIQUE` en `perfil_cliente.cliente_id`) y `404 Not Found` si el cliente no existe, en ambos casos sin consulta previa.

#### Scenario: Primer perfil
- **WHEN** el cliente 1 no tiene perfil y se envía `POST /clientes/1/perfil` con `{"telefono": "11-5555-0000", "direccion": "Av. Siempre Viva 742"}`
- **THEN** el sistema responde `201 Created` con `id`, `cliente_id` igual a 1, `telefono` y `direccion`

#### Scenario: Segundo perfil para el mismo cliente
- **WHEN** el cliente 1 ya tiene perfil y se envía otro `POST /clientes/1/perfil`
- **THEN** el sistema responde `409 Conflict` con mensaje propio y el perfil original no cambia

#### Scenario: Cliente inexistente
- **WHEN** se envía `POST /clientes/999/perfil` con un cuerpo válido
- **THEN** el sistema responde `404 Not Found`

#### Scenario: Cuerpo inválido
- **WHEN** se envía `POST /clientes/1/perfil` sin `direccion`
- **THEN** el sistema responde `422 Unprocessable Entity`
