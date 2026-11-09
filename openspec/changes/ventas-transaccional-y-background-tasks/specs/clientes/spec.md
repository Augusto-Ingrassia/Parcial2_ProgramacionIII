# Spec Delta

## ADDED Requirements

### Requirement: Ventas de un cliente
El sistema SHALL listar mediante `GET /clientes/{id}/ventas` las ventas del cliente, paginadas (RN-10), con el mismo formato y la misma carga anticipada que `GET /ventas/`; y responder `404 Not Found` si el cliente no existe.

#### Scenario: Cliente con compras
- **WHEN** el cliente 2 tiene dos ventas y el cliente 1 una, y se envía `GET /clientes/2/ventas`
- **THEN** el sistema responde `200 OK` con las dos ventas del cliente 2, cada una con sus renglones

#### Scenario: Cliente sin compras
- **WHEN** el cliente 3 existe y no tiene ventas
- **THEN** `GET /clientes/3/ventas` responde `200 OK` con `[]`

#### Scenario: Cliente inexistente
- **WHEN** se envía `GET /clientes/999/ventas`
- **THEN** el sistema responde `404 Not Found`
