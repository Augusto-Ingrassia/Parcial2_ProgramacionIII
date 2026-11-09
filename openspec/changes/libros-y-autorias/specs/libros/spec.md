# Spec Delta

## Purpose
Gestiona el catálogo de libros: alta atómica con sus autorías (rol y orden), listado paginado con filtros, detalle completo sin N+1 y actualización parcial, delegando en la base la unicidad del ISBN, las claves foráneas y las comprobaciones de precio, stock, rol y orden.

## ADDED Requirements

### Requirement: Alta de libro con autorías
El sistema SHALL registrar un libro mediante `POST /libros/` recibiendo `isbn`, `titulo`, `precio`, `stock`, `editorial_id`, `genero_id` (opcional) y una lista `autores` no vacía cuyos elementos traen `autor_id`, `rol` y `orden`; SHALL persistir el libro y sus filas de `libro_autor` en una única transacción y responder `201 Created` con el detalle del libro (editorial, género y autores con rol y orden).

#### Scenario: Alta exitosa con dos coautores
- **WHEN** existen la editorial 1, el género 1 y los autores 3 y 4, y se envía `POST /libros/` con `{"isbn": "978-950-00-0006-6", "titulo": "Los que aman, odian", "precio": "21000.00", "stock": 4, "editorial_id": 1, "genero_id": 1, "autores": [{"autor_id": 3, "rol": "coautor", "orden": 1}, {"autor_id": 4, "rol": "coautor", "orden": 2}]}`
- **THEN** el sistema responde `201 Created` con `id` asignado, `precio` `"21000.00"`, el objeto `editorial`, el objeto `genero` y `autores` con dos elementos ordenados por `orden`, cada uno con `autor_id`, `nombre`, `rol` y `orden`

#### Scenario: Alta sin género
- **WHEN** se envía `POST /libros/` válido sin `genero_id`
- **THEN** el sistema responde `201 Created` con `genero` igual a `null`

#### Scenario: Editorial, género o autor inexistente
- **WHEN** se envía `POST /libros/` con un `editorial_id`, `genero_id` o `autor_id` que no existe
- **THEN** el sistema responde `409 Conflict` con un mensaje propio, sin nombres de tablas, restricciones ni trazas, y no persiste el libro ni ninguna autoría

#### Scenario: Sin consulta previa de existencia
- **WHEN** se procesa un alta de libro
- **THEN** el servicio no ejecuta ningún `SELECT` para verificar la existencia de la editorial, el género o los autores: la verificación la hace la clave foránea al escribir

#### Scenario: ISBN repetido (RN-01)
- **WHEN** ya existe un libro con ISBN `"978-1"` y se envía `POST /libros/` con el mismo ISBN
- **THEN** el sistema responde `409 Conflict` con un mensaje propio sobre el ISBN, sin texto interno de la base

#### Scenario: Precio, stock, rol u orden inválidos (RN-03)
- **WHEN** se envía `POST /libros/` con `precio` `0` o negativo, `stock` negativo, un `rol` fuera de `autor`, `coautor`, `traductor`, `ilustrador`, u `orden` menor que 1
- **THEN** el sistema responde `422 Unprocessable Entity` y no persiste nada

#### Scenario: Autores vacíos o repetidos
- **WHEN** se envía `POST /libros/` con `autores` vacío, o con el mismo `autor_id` en dos elementos
- **THEN** el sistema responde `422 Unprocessable Entity`

#### Scenario: El cliente no fija el id
- **WHEN** el cuerpo de `POST /libros/` incluye `id`
- **THEN** el sistema lo ignora y usa el asignado por la base

### Requirement: Restricciones del libro en la base
El esquema SHALL declarar en la base `UNIQUE (isbn)`, `CHECK (precio > 0)`, `CHECK (stock >= 0)`, `precio` como `NUMERIC(10,2)`, FK indexadas `editorial_id` (NOT NULL) y `genero_id` (NULL permitido); y para `libro_autor` la PK compuesta `(libro_id, autor_id)`, FK indexadas, `CHECK (orden >= 1)` y `CHECK` de `rol` dentro de `autor`, `coautor`, `traductor`, `ilustrador`.

#### Scenario: La base rechaza un precio no positivo aunque se saltee el DTO
- **WHEN** se intenta insertar directamente en la base un libro con `precio = 0`
- **THEN** la base rechaza la escritura con una violación de `CHECK`

### Requirement: Listado paginado y filtrado de libros
El sistema SHALL listar libros mediante `GET /libros/` paginados con `limit` (1..100, por defecto 20) y `offset` (≥ 0) en orden ascendente por `id`, incluyendo en cada elemento su `editorial` y su `genero`; SHALL admitir el filtro `titulo` (parte del título, sin distinguir mayúsculas, con parámetro ligado) y el filtro `genero_id`.

#### Scenario: Filtro por parte del título sin distinguir mayúsculas (RN-11)
- **WHEN** existen "Rayuela" y "Ficciones" y se envía `GET /libros/?titulo=RAYU`
- **THEN** el sistema responde `200 OK` con un arreglo que contiene sólo "Rayuela"

#### Scenario: Intento de inyección SQL
- **WHEN** se envía `GET /libros/?titulo=' OR '1'='1`
- **THEN** el sistema responde `200 OK` con `[]`

#### Scenario: Filtro por género
- **WHEN** se envía `GET /libros/?genero_id=2`
- **THEN** el sistema responde `200 OK` sólo con los libros cuyo `genero.id` es 2

#### Scenario: Paginación inválida
- **WHEN** se envía `GET /libros/` con `limit=0`, `limit=101` u `offset=-1`
- **THEN** el sistema responde `422 Unprocessable Entity`

### Requirement: Detalle de libro sin N+1
El sistema SHALL devolver mediante `GET /libros/{id}` el libro con su editorial, su género y sus autores (con rol y orden), obtenidos con carga anticipada declarada en la consulta, con una cantidad fija de consultas independiente de la cantidad de autores; y `404 Not Found` con mensaje propio si no existe.

#### Scenario: Detalle existente
- **WHEN** existe el libro 1 y se envía `GET /libros/1`
- **THEN** el sistema responde `200 OK` con `editorial`, `genero` y `autores`

#### Scenario: Cantidad fija de consultas
- **WHEN** se piden los detalles de un libro con 1 autor y de otro con 3 autores
- **THEN** ambas peticiones ejecutan la misma cantidad de sentencias SQL

#### Scenario: Libro inexistente
- **WHEN** se envía `GET /libros/999`
- **THEN** el sistema responde `404 Not Found` con mensaje propio

#### Scenario: Id no entero
- **WHEN** se envía `GET /libros/abc`
- **THEN** el sistema responde `422 Unprocessable Entity` sin ejecutar el handler

### Requirement: Actualización parcial de libro
El sistema SHALL modificar mediante `PATCH /libros/{id}` sólo los campos enviados (`isbn`, `titulo`, `precio`, `stock`, `editorial_id`, `genero_id`) y responder `200 OK` con el detalle del libro; `404` si no existe, `409` si la base rechaza la escritura (ISBN repetido o FK inexistente) y `422` si el cuerpo no cumple el contrato.

#### Scenario: Cambio de precio y stock
- **WHEN** se envía `PATCH /libros/1` con `{"precio": "30000.00", "stock": 10}`
- **THEN** el sistema responde `200 OK` con los nuevos valores y el resto de los campos sin cambios

#### Scenario: Quitar el género
- **WHEN** se envía `PATCH /libros/1` con `{"genero_id": null}`
- **THEN** el sistema responde `200 OK` con `genero` igual a `null`

#### Scenario: ISBN de otro libro
- **WHEN** se envía `PATCH /libros/2` con el ISBN del libro 1
- **THEN** el sistema responde `409 Conflict` y el libro 2 conserva su ISBN

#### Scenario: Valores inválidos o nulos
- **WHEN** se envía `PATCH /libros/1` con `{"precio": "-1"}`, `{"stock": -5}` o `{"titulo": null}`
- **THEN** el sistema responde `422 Unprocessable Entity`

#### Scenario: Libro inexistente
- **WHEN** se envía `PATCH /libros/999` con `{"stock": 1}`
- **THEN** el sistema responde `404 Not Found`
