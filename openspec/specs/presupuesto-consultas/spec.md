# presupuesto-consultas Specification

## Purpose
Garantiza que las lecturas con relaciones ejecuten una cantidad fija de sentencias SQL, independiente del tamaño de la página o de la colección (sin N+1), y deja evidencia reproducible de esa garantía en `evidencia/`.

## Requirements

### Requirement: Listado de libros con cantidad fija de consultas
`GET /libros/` SHALL ejecutar exactamente 1 sentencia SQL por petición (libros con su editorial y su género en una consulta con JOIN), sea cual sea la cantidad de libros devueltos.

#### Scenario: Páginas de 1, 10 y 50 libros
- **WHEN** existen al menos 50 libros y se piden `GET /libros/?limit=1`, `?limit=10` y `?limit=50`
- **THEN** cada petición ejecuta exactamente 1 sentencia SQL y devuelve 1, 10 y 50 libros con `editorial` y `genero`

### Requirement: Detalle de libro con cantidad fija de consultas
`GET /libros/{id}` SHALL ejecutar exactamente 2 sentencias SQL (libro con editorial y género por JOIN; autorías con sus autores por una consulta `IN`), sea cual sea la cantidad de autores del libro.

#### Scenario: Libros con 1, 10 y 50 autores
- **WHEN** se piden los detalles de libros con 1, 10 y 50 autorías
- **THEN** cada petición ejecuta exactamente 2 sentencias SQL y devuelve todos sus autores

### Requirement: Listado de ventas con cantidad fija de consultas
`GET /ventas/` SHALL ejecutar exactamente 2 sentencias SQL por petición (ventas con su cliente por JOIN; renglones con sus libros por una consulta `IN`), sea cual sea la cantidad de ventas devueltas y de renglones por venta.

#### Scenario: Páginas de 1, 10 y 50 ventas
- **WHEN** existen al menos 50 ventas con uno o más renglones y se piden `GET /ventas/?limit=1`, `?limit=10` y `?limit=50`
- **THEN** cada petición ejecuta exactamente 2 sentencias SQL y cada venta trae su `cliente` y todos sus `renglones`

### Requirement: Detalle de venta con cantidad fija de consultas
`GET /ventas/{id}` SHALL ejecutar exactamente 2 sentencias SQL, sea cual sea la cantidad de renglones de la venta.

#### Scenario: Ventas con 1, 10 y 50 renglones
- **WHEN** se piden los detalles de ventas con 1, 10 y 50 renglones
- **THEN** cada petición ejecuta exactamente 2 sentencias SQL y devuelve todos sus renglones con `titulo` y `subtotal`

### Requirement: Listado de clientes con cantidad fija de consultas
`GET /clientes/` SHALL ejecutar exactamente 1 sentencia SQL por petición (clientes con su perfil por JOIN), sea cual sea la cantidad de clientes devueltos.

#### Scenario: Páginas de 1, 10 y 50 clientes
- **WHEN** existen al menos 50 clientes, algunos con perfil, y se piden `GET /clientes/?limit=1`, `?limit=10` y `?limit=50`
- **THEN** cada petición ejecuta exactamente 1 sentencia SQL

### Requirement: Evidencia reproducible de consultas
El proyecto SHALL incluir `evidencia/queries_libros.log` y `evidencia/queries_ventas.log` con las sentencias SQL registradas por el motor con `SQL_ECHO=true` al listar 1, 10 y 50 libros y ventas, separadas por corrida e indicando la cantidad de sentencias de cada una, y un comando documentado que las regenera sin dejar datos en la base.

#### Scenario: Regeneración de la evidencia
- **WHEN** se ejecuta el comando de auditoría contra la base configurada
- **THEN** se reescriben ambos archivos; cada uno contiene una sección por tamaño (1, 10, 50) con las sentencias SQL y su cantidad, que es igual en las tres secciones

#### Scenario: Sin efectos sobre la base
- **WHEN** termina el comando de auditoría
- **THEN** las cantidades de libros, ventas, clientes y catálogos de la base son las mismas que antes de ejecutarlo
