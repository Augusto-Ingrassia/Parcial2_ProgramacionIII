# Spec Delta: presupuesto-consultas

## MODIFIED Requirements

### Requirement: Evidencia reproducible de consultas
El proyecto SHALL incluir `evidencia/queries_libros.log` y `evidencia/queries_ventas.log` con las sentencias SQL registradas por el motor con `SQL_ECHO=true` al listar 1, 10 y 50 libros y ventas, y al pedir el detalle de un libro con 1, 10 y 50 autores y de una venta con 1, 10 y 50 renglones, separadas por corrida e indicando la cantidad de sentencias de cada una, y un comando documentado que las regenera sin dejar datos en la base.

#### Scenario: Regeneración de la evidencia
- **WHEN** se ejecuta el comando de auditoría contra la base configurada
- **THEN** se reescriben ambos archivos; cada uno contiene una sección de listado por tamaño (1, 10, 50) con las sentencias SQL y su cantidad, que es igual en las tres secciones

#### Scenario: Evidencia del detalle de libro
- **WHEN** se ejecuta el comando de auditoría
- **THEN** `queries_libros.log` contiene una sección de `GET /libros/{id}` para un libro con 1 autor, otra con 10 y otra con 50, cada una con sus sentencias SQL y la cantidad, que es 2 en las tres (libro con editorial y género por JOIN; autorías con sus autores por una consulta `IN`), y cada respuesta trae todos los autores del libro

#### Scenario: Evidencia del detalle de venta
- **WHEN** se ejecuta el comando de auditoría
- **THEN** `queries_ventas.log` contiene una sección de `GET /ventas/{id}` para una venta con 1 renglón, otra con 10 y otra con 50, cada una con sus sentencias SQL y la cantidad, que es 2 en las tres, y cada respuesta trae todos los renglones de la venta

#### Scenario: Sin efectos sobre la base
- **WHEN** termina el comando de auditoría
- **THEN** las cantidades de libros, autores, autorías, ventas, renglones, clientes y catálogos de la base son las mismas que antes de ejecutarlo
