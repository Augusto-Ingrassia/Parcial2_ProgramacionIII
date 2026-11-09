# Spec Delta

## ADDED Requirements

### Requirement: Libros de un autor con rol y orden
El sistema SHALL listar mediante `GET /autores/{id}/libros` los libros en los que participa el autor, cada uno con el `rol` y el `orden` de esa autoría, paginados (RN-10); y responder `404 Not Found` con mensaje propio si el autor no existe.

#### Scenario: Autor con dos autorías
- **WHEN** el autor 3 figura como `coautor` (orden 1) en el libro 1 y como `traductor` (orden 2) en el libro 2, y se envía `GET /autores/3/libros`
- **THEN** el sistema responde `200 OK` con dos elementos que contienen `id`, `isbn`, `titulo`, `rol` y `orden` de cada autoría

#### Scenario: Autor inexistente
- **WHEN** se envía `GET /autores/999/libros`
- **THEN** el sistema responde `404 Not Found`
