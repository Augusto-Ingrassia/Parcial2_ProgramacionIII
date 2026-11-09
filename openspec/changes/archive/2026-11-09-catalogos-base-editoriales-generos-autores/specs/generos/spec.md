# Spec Delta

## Purpose
Gestiona el catálogo maestro de géneros literarios usados para agrupar temáticamente las obras: alta, consulta y listado paginado, garantizando que no existan dos géneros con el mismo nombre.

## ADDED Requirements

### Requirement: Alta de género
El sistema SHALL permitir registrar un género enviando `nombre` mediante `POST /generos/`, respondiendo `201 Created` con el género persistido incluyendo su `id` asignado por el servidor.

#### Scenario: Alta exitosa
- **WHEN** se envía `POST /generos/` con `{"nombre": "Ciencia Ficción"}` y no existe otro género con ese nombre
- **THEN** el sistema responde `201 Created` con un cuerpo JSON que contiene `id` (entero) y `nombre` igual a `"Ciencia Ficción"`

#### Scenario: Nombre ausente o vacío
- **WHEN** se envía `POST /generos/` con `{}`, o con `nombre` vacío o compuesto solo por espacios
- **THEN** el sistema responde `422 Unprocessable Entity` y no persiste ningún género

### Requirement: Unicidad del nombre de género
El sistema SHALL rechazar con `409 Conflict` toda alta que repita el `nombre` de un género existente, delegando la detección en la restricción de unicidad de la base de datos y sin exponer nombres de tablas, restricciones ni trazas internas (RN-12).

#### Scenario: Alta con nombre duplicado
- **WHEN** ya existe el género `"Policial"` y se envía `POST /generos/` con `{"nombre": "Policial"}`
- **THEN** el sistema responde `409 Conflict` con un cuerpo `{"detail": "<mensaje propio>"}` cuyo texto no contiene los términos `genero_nombre_key`, `UNIQUE`, `IntegrityError` ni `duplicate key`, y no se crea un segundo género

#### Scenario: La API sigue operativa tras un conflicto
- **WHEN** una petición de alta acaba de responder `409 Conflict` por nombre duplicado y a continuación se envía `POST /generos/` con un nombre nuevo
- **THEN** el sistema responde `201 Created` para la segunda petición

### Requirement: Listado paginado de géneros
El sistema SHALL listar géneros mediante `GET /generos/` como un arreglo JSON paginado con `limit` (entero de 1 a 100, por defecto 20) y `offset` (entero desde 0, por defecto 0), en orden estable ascendente por `id` (RN-10).

#### Scenario: Listado con valores por defecto
- **WHEN** existen 3 géneros y se envía `GET /generos/` sin parámetros
- **THEN** el sistema responde `200 OK` con un arreglo de los 3 géneros en orden ascendente de `id`

#### Scenario: Paginación con limit y offset
- **WHEN** existen 3 géneros y se envía `GET /generos/?limit=1&offset=1`
- **THEN** el sistema responde `200 OK` con un arreglo que contiene solo el segundo género

#### Scenario: Parámetros de paginación fuera de rango
- **WHEN** se envía `GET /generos/` con `limit=0`, `limit=101` u `offset=-1`
- **THEN** el sistema responde `422 Unprocessable Entity`

### Requirement: Consulta de género por id
El sistema SHALL devolver un género existente mediante `GET /generos/{id}` y responder `404 Not Found` con un mensaje propio cuando no exista.

#### Scenario: Género existente
- **WHEN** existe el género con `id` 1 y se envía `GET /generos/1`
- **THEN** el sistema responde `200 OK` con `id` y `nombre` de ese género

#### Scenario: Género inexistente
- **WHEN** no existe ningún género con `id` 999 y se envía `GET /generos/999`
- **THEN** el sistema responde `404 Not Found` con un cuerpo `{"detail": "<mensaje propio>"}`
