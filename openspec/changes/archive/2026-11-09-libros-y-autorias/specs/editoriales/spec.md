# Spec Delta

## ADDED Requirements

### Requirement: Libros de una editorial
El sistema SHALL listar mediante `GET /editoriales/{id}/libros` los libros cuya `editorial_id` es `id`, paginados (RN-10) y con su editorial y género precargados; y responder `404 Not Found` con mensaje propio si la editorial no existe.

#### Scenario: Editorial con libros
- **WHEN** la editorial 1 tiene dos libros y se envía `GET /editoriales/1/libros`
- **THEN** el sistema responde `200 OK` con esos dos libros en orden de `id`

#### Scenario: Editorial sin libros
- **WHEN** la editorial 2 existe pero no tiene libros y se envía `GET /editoriales/2/libros`
- **THEN** el sistema responde `200 OK` con `[]`

#### Scenario: Editorial inexistente
- **WHEN** se envía `GET /editoriales/999/libros`
- **THEN** el sistema responde `404 Not Found`
