# Spec Delta

## Purpose
Puebla la base con un estado conocido y reproducible de catálogo y clientes para demostrar la API, ejecutar las pruebas manuales y preparar el despliegue, sin duplicar datos si se ejecuta más de una vez.

## ADDED Requirements

### Requirement: Comando de carga inicial
El sistema SHALL proveer un comando ejecutable como módulo (`python -m app.initial_data`) que, usando la configuración de conexión vigente (`DATABASE_URL`), cree las tablas que falten y cargue los datos iniciales, terminando con código de salida 0 y un resumen de las filas creadas por entidad.

#### Scenario: Ejecución sobre una base vacía
- **WHEN** se ejecuta `python -m app.initial_data` contra una base sin tablas
- **THEN** el comando crea las tablas, carga los datos iniciales, informa las cantidades creadas por entidad y termina con código 0

#### Scenario: Base inaccesible
- **WHEN** se ejecuta el comando y la base no responde
- **THEN** el comando termina con código distinto de 0 y un mensaje propio, sin dejar datos a medio cargar

### Requirement: Contenido determinístico de la carga inicial
La carga inicial SHALL crear siempre el mismo conjunto: 3 editoriales, 4 géneros, 5 autores, 6 libros y 2 clientes, cada cliente con su perfil; los libros SHALL tener al menos una autoría cada uno y, entre todos, autorías con los roles `autor`, `coautor` y `traductor`, y al menos un libro con más de un autor. Los montos SHALL ser decimales exactos.

#### Scenario: Cantidades por entidad
- **WHEN** se ejecuta la carga sobre una base vacía
- **THEN** `GET /editoriales/`, `GET /generos/`, `GET /autores/`, `GET /libros/` y `GET /clientes/` devuelven 3, 4, 5, 6 y 2 elementos respectivamente, y cada cliente devuelve su `perfil` como objeto

#### Scenario: Autorías múltiples con roles
- **WHEN** se consulta el detalle de cada libro sembrado
- **THEN** todos tienen al menos un autor, al menos uno tiene dos o más autores, y entre todos aparecen los roles `autor`, `coautor` y `traductor`

#### Scenario: Datos válidos para vender
- **WHEN** después de la carga se envía `POST /ventas/` con un cliente y un libro sembrados
- **THEN** el sistema responde `201 Created` con el precio copiado del libro sembrado

### Requirement: Carga inicial idempotente
La carga inicial SHALL poder ejecutarse más de una vez sin fallar ni duplicar filas: cada fila se identifica por su clave natural (nombre de editorial, de género y de autor; ISBN del libro; email del cliente) y sólo se inserta lo que falta, todo dentro de una única transacción.

#### Scenario: Segunda ejecución
- **WHEN** se ejecuta la carga dos veces seguidas
- **THEN** la segunda ejecución termina con código 0, informa 0 filas creadas y las cantidades por entidad no cambian

#### Scenario: Carga parcial previa
- **WHEN** la base ya contiene una de las editoriales del seed (mismo nombre) y se ejecuta la carga
- **THEN** la carga reutiliza esa editorial, crea el resto sin responder error de unicidad y no queda ninguna editorial duplicada
