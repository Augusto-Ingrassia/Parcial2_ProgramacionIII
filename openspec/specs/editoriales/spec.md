# editoriales Specification

## Purpose
Gestiona el catálogo maestro de editoriales de la librería: alta, consulta, listado paginado y actualización parcial, garantizando que no existan dos editoriales con el mismo nombre.

## Requirements

### Requirement: Alta de editorial
El sistema SHALL permitir registrar una editorial enviando `nombre` y `pais` mediante `POST /editoriales/`, respondiendo `201 Created` con la editorial persistida incluyendo su `id` asignado por el servidor.

#### Scenario: Alta exitosa
- **WHEN** se envía `POST /editoriales/` con `{"nombre": "Planeta", "pais": "España"}` y no existe otra editorial con ese nombre
- **THEN** el sistema responde `201 Created` con un cuerpo JSON que contiene `id` (entero), `nombre` igual a `"Planeta"` y `pais` igual a `"España"`

#### Scenario: Campos obligatorios ausentes o vacíos
- **WHEN** se envía `POST /editoriales/` sin `pais`, o con `nombre` vacío o compuesto solo por espacios
- **THEN** el sistema responde `422 Unprocessable Entity` y no persiste ninguna editorial

#### Scenario: El cliente no puede fijar el id
- **WHEN** se envía `POST /editoriales/` incluyendo un campo `id` en el cuerpo
- **THEN** el sistema ignora ese valor y el `id` de la respuesta es el asignado por la base de datos

### Requirement: Unicidad del nombre de editorial
El sistema SHALL rechazar con `409 Conflict` toda alta o actualización que deje dos editoriales con el mismo `nombre`, delegando la detección en la restricción de unicidad de la base de datos y sin exponer nombres de tablas, restricciones ni trazas internas (RN-12).

#### Scenario: Alta con nombre duplicado
- **WHEN** ya existe la editorial `"Planeta"` y se envía `POST /editoriales/` con `{"nombre": "Planeta", "pais": "Argentina"}`
- **THEN** el sistema responde `409 Conflict` con un cuerpo `{"detail": "<mensaje propio>"}` cuyo texto no contiene los términos `editorial_nombre_key`, `UNIQUE`, `IntegrityError` ni `duplicate key`, y no se crea una segunda editorial

#### Scenario: La API sigue operativa tras un conflicto
- **WHEN** una petición de alta acaba de responder `409 Conflict` por nombre duplicado y a continuación se envía `POST /editoriales/` con un nombre nuevo
- **THEN** el sistema responde `201 Created` para la segunda petición

### Requirement: Listado paginado de editoriales
El sistema SHALL listar editoriales mediante `GET /editoriales/` como un arreglo JSON paginado con `limit` (entero de 1 a 100, por defecto 20) y `offset` (entero desde 0, por defecto 0), en orden estable ascendente por `id` (RN-10).

#### Scenario: Listado con valores por defecto
- **WHEN** existen 25 editoriales y se envía `GET /editoriales/` sin parámetros
- **THEN** el sistema responde `200 OK` con un arreglo de 20 editoriales, las de menor `id`, en orden ascendente

#### Scenario: Paginación con limit y offset
- **WHEN** existen 25 editoriales y se envía `GET /editoriales/?limit=10&offset=20`
- **THEN** el sistema responde `200 OK` con un arreglo de 5 editoriales correspondientes a las posiciones 21 a 25

#### Scenario: Listado vacío
- **WHEN** no existen editoriales y se envía `GET /editoriales/`
- **THEN** el sistema responde `200 OK` con `[]`

#### Scenario: Parámetros de paginación fuera de rango
- **WHEN** se envía `GET /editoriales/` con `limit=0`, `limit=101` u `offset=-1`
- **THEN** el sistema responde `422 Unprocessable Entity`

### Requirement: Consulta de editorial por id
El sistema SHALL devolver una editorial existente mediante `GET /editoriales/{id}` y responder `404 Not Found` con un mensaje propio cuando no exista.

#### Scenario: Editorial existente
- **WHEN** existe la editorial con `id` 1 y se envía `GET /editoriales/1`
- **THEN** el sistema responde `200 OK` con `id`, `nombre` y `pais` de esa editorial

#### Scenario: Editorial inexistente
- **WHEN** no existe ninguna editorial con `id` 999 y se envía `GET /editoriales/999`
- **THEN** el sistema responde `404 Not Found` con un cuerpo `{"detail": "<mensaje propio>"}`

### Requirement: Actualización parcial de editorial
El sistema SHALL permitir modificar mediante `PATCH /editoriales/{id}` únicamente los campos enviados en el cuerpo, conservando sin cambios los omitidos, y responder `200 OK` con la editorial resultante.

#### Scenario: Actualización de un solo campo
- **WHEN** existe la editorial `{"id": 1, "nombre": "Planeta", "pais": "España"}` y se envía `PATCH /editoriales/1` con `{"pais": "Argentina"}`
- **THEN** el sistema responde `200 OK` con `{"id": 1, "nombre": "Planeta", "pais": "Argentina"}`

#### Scenario: Cuerpo vacío
- **WHEN** existe la editorial con `id` 1 y se envía `PATCH /editoriales/1` con `{}`
- **THEN** el sistema responde `200 OK` con la editorial sin modificaciones

#### Scenario: Reenvío del propio nombre
- **WHEN** existe la editorial `"Planeta"` con `id` 1 y se envía `PATCH /editoriales/1` con `{"nombre": "Planeta"}`
- **THEN** el sistema responde `200 OK` sin reportar conflicto

#### Scenario: Nuevo nombre colisiona con otra editorial
- **WHEN** existen las editoriales `"Planeta"` (`id` 1) y `"Anagrama"` (`id` 2) y se envía `PATCH /editoriales/2` con `{"nombre": "Planeta"}`
- **THEN** el sistema responde `409 Conflict` con mensaje propio sin detalles internos de la base, y la editorial `id` 2 conserva el nombre `"Anagrama"`

#### Scenario: Valor nulo o vacío en un campo obligatorio
- **WHEN** se envía `PATCH /editoriales/1` con `{"nombre": null}` o `{"pais": ""}`
- **THEN** el sistema responde `422 Unprocessable Entity` y la editorial no se modifica

#### Scenario: Editorial inexistente
- **WHEN** no existe ninguna editorial con `id` 999 y se envía `PATCH /editoriales/999` con `{"pais": "Chile"}`
- **THEN** el sistema responde `404 Not Found` con mensaje propio

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
