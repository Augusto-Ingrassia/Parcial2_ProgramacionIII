# Spec Delta

## Purpose
Gestiona el registro de autores (creadores de las obras) con su nacionalidad: alta, consulta, listado paginado y actualización parcial. Los nombres de autor no son únicos, ya que dos personas distintas pueden compartir nombre.

## ADDED Requirements

### Requirement: Alta de autor
El sistema SHALL permitir registrar un autor enviando `nombre` y `nacionalidad` mediante `POST /autores/`, respondiendo `201 Created` con el autor persistido incluyendo su `id` asignado por el servidor.

#### Scenario: Alta exitosa
- **WHEN** se envía `POST /autores/` con `{"nombre": "Jorge Luis Borges", "nacionalidad": "Argentina"}`
- **THEN** el sistema responde `201 Created` con un cuerpo JSON que contiene `id` (entero), `nombre` y `nacionalidad` enviados

#### Scenario: Nombres repetidos permitidos
- **WHEN** ya existe un autor llamado `"Juan Pérez"` y se envía `POST /autores/` con `{"nombre": "Juan Pérez", "nacionalidad": "Uruguay"}`
- **THEN** el sistema responde `201 Created` con un nuevo `id` distinto del autor existente

#### Scenario: Campos obligatorios ausentes o vacíos
- **WHEN** se envía `POST /autores/` sin `nacionalidad`, o con `nombre` vacío o compuesto solo por espacios
- **THEN** el sistema responde `422 Unprocessable Entity` y no persiste ningún autor

### Requirement: Listado paginado de autores
El sistema SHALL listar autores mediante `GET /autores/` como un arreglo JSON paginado con `limit` (entero de 1 a 100, por defecto 20) y `offset` (entero desde 0, por defecto 0), en orden estable ascendente por `id` (RN-10).

#### Scenario: Listado con valores por defecto
- **WHEN** existen 2 autores y se envía `GET /autores/` sin parámetros
- **THEN** el sistema responde `200 OK` con un arreglo de los 2 autores en orden ascendente de `id`

#### Scenario: Paginación con limit y offset
- **WHEN** existen 3 autores y se envía `GET /autores/?limit=2&offset=2`
- **THEN** el sistema responde `200 OK` con un arreglo que contiene solo el tercer autor

#### Scenario: Parámetros de paginación fuera de rango
- **WHEN** se envía `GET /autores/` con `limit=0`, `limit=101` u `offset=-1`
- **THEN** el sistema responde `422 Unprocessable Entity`

### Requirement: Consulta de autor por id
El sistema SHALL devolver un autor existente mediante `GET /autores/{id}` y responder `404 Not Found` con un mensaje propio cuando no exista.

#### Scenario: Autor existente
- **WHEN** existe el autor con `id` 1 y se envía `GET /autores/1`
- **THEN** el sistema responde `200 OK` con `id`, `nombre` y `nacionalidad` de ese autor

#### Scenario: Autor inexistente
- **WHEN** no existe ningún autor con `id` 999 y se envía `GET /autores/999`
- **THEN** el sistema responde `404 Not Found` con un cuerpo `{"detail": "<mensaje propio>"}`

### Requirement: Actualización parcial de autor
El sistema SHALL permitir modificar mediante `PATCH /autores/{id}` únicamente los campos enviados en el cuerpo, conservando sin cambios los omitidos, y responder `200 OK` con el autor resultante.

#### Scenario: Actualización de un solo campo
- **WHEN** existe el autor `{"id": 1, "nombre": "J. L. Borges", "nacionalidad": "Argentina"}` y se envía `PATCH /autores/1` con `{"nombre": "Jorge Luis Borges"}`
- **THEN** el sistema responde `200 OK` con `{"id": 1, "nombre": "Jorge Luis Borges", "nacionalidad": "Argentina"}`

#### Scenario: Valor nulo o vacío en un campo obligatorio
- **WHEN** se envía `PATCH /autores/1` con `{"nacionalidad": null}` o `{"nombre": "   "}`
- **THEN** el sistema responde `422 Unprocessable Entity` y el autor no se modifica

#### Scenario: Autor inexistente
- **WHEN** no existe ningún autor con `id` 999 y se envía `PATCH /autores/999` con `{"nacionalidad": "Chile"}`
- **THEN** el sistema responde `404 Not Found` con mensaje propio
