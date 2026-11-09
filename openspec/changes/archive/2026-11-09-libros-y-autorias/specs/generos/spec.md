# Spec Delta

## ADDED Requirements

### Requirement: Libros de un género
El sistema SHALL listar mediante `GET /generos/{id}/libros` los libros cuyo `genero_id` es `id`, paginados (RN-10) y con su editorial y género precargados; y responder `404 Not Found` con mensaje propio si el género no existe.

#### Scenario: Género con libros
- **WHEN** el género 1 tiene un libro y se envía `GET /generos/1/libros`
- **THEN** el sistema responde `200 OK` con ese libro

#### Scenario: Género inexistente
- **WHEN** se envía `GET /generos/999/libros`
- **THEN** el sistema responde `404 Not Found`
