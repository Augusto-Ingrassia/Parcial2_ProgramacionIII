# Modelo de Datos

## Dominios y módulos
El modelo traduce los conceptos de una librería divididos en los siguientes módulos obligatorios:
1. **Editoriales**: Entidad `Editorial` (agregación con Libro).
2. **Géneros**: Entidad `Genero` (agregación opcional con Libro).
3. **Autores**: Entidad `Autor` (asociación N:N con Libro a través de autoría).
4. **Libros**: Entidades `Libro` y `LibroAutor` (objeto de asociación N:M con rol y orden).
5. **Clientes**: Entidades `Cliente` y `PerfilCliente` (relación 1:1 estricta).
6. **Ventas**: Entidades `Venta` y `RenglonVenta` (composición 1:N atómica).

## ERD (Entity Relationship Diagram)

```
       +------------------+                    +-----------------+
       |    editorial     |                    |     genero      |
       +------------------+                    +-----------------+
       | id (PK)          |                    | id (PK)         |
       | nombre (UQ)      |                    | nombre (UQ)     |
       | pais             |                    +--------+--------+
       +--------+---------+                             |
                | 1                                     | 0..1
                | (agregación)                          | (agregación opcional)
                |                                       |
                |           +-----------------+         |
                +---------->|      libro      |<--------+
                          N +-----------------+ N
                            | id (PK)         |
                            | isbn (UQ)       |
                            | titulo          |
                            | precio (NUM)    |
                            | stock (INT)     |
                            | editorial_id(FK)|
                            | genero_id(FK,N) |
                            +---+--------+----+
                                | 1      ^
                                |        | (asociación)
                   (asociación) |        | 1
                                v        |
                      +------------+   +-------------------+
                      |libro_autor |   |   renglon_venta   |
                      +------------+   +-------------------+
                      |libro_id(PK)|   | id (PK)           |
                      |autor_id(PK)|   | venta_id (FK, IX) |
                      |rol         |   | libro_id (FK, IX) |
                      |orden       |   | cantidad (INT)    |
                      +------+-----+   | precio_unitario   |
                             | N       +---------+---------+
                             |                   ^
                (asociación) |                   | N (composición)
                             v                   |
                      +------------+   +---------+---------+
                      |   autor    |   |       venta       |
                      +------------+   +-------------------+
                      | id (PK)    |   | id (PK)           |
                      | nombre     |   | cliente_id(FK, IX)|
                      |nacionalidad|   | fecha (TIMESTAMPTZ|
                      +------------+   | total (NUMERIC)   |
                                       +---------+---------+
                                                 | N (asociación)
                                                 v 1
       +--------------------+          +-------------------+
       |   perfil_cliente   |          |      cliente      |
       +--------------------+          +-------------------+
       | id (PK)            | 0..1    1| id (PK)           |
       | cliente_id (UQ, FK)|<-------->| nombre            |
       | telefono           | (1 a 1)  | email (UQ)        |
       | direccion          |          +-------------------+
       +--------------------+
```

## Entidades y Diccionario de Datos

### 1. `editorial`
- `id`: `int`, Primary Key, autoincremental.
- `nombre`: `str`, `UNIQUE`, NOT NULL.
- `pais`: `str`, NOT NULL.
- **Relaciones**:
  - `libros: list["Libro"] = Relationship(back_populates="editorial")`

### 2. `genero`
- `id`: `int`, Primary Key, autoincremental.
- `nombre`: `str`, `UNIQUE`, NOT NULL.
- **Relaciones**:
  - `libros: list["Libro"] = Relationship(back_populates="genero")`

### 3. `autor`
- `id`: `int`, Primary Key, autoincremental.
- `nombre`: `str`, NOT NULL.
- `nacionalidad`: `str`, NOT NULL.
- **Relaciones**:
  - `autorias: list["LibroAutor"] = Relationship(back_populates="autor")`

### 4. `libro`
- `id`: `int`, Primary Key, autoincremental.
- `isbn`: `str`, `UNIQUE`, NOT NULL.
- `titulo`: `str`, NOT NULL.
- `precio`: `Decimal`, tipo `NUMERIC(10, 2)`, NOT NULL. Restricción `CHECK (precio > 0)`.
- `stock`: `int`, NOT NULL. Restricción `CHECK (stock >= 0)`.
- `editorial_id`: `int`, Foreign Key a `editorial.id`, con índice explícito (`index=True`), NOT NULL.
- `genero_id`: `Optional[int]`, Foreign Key a `genero.id`, con índice explícito (`index=True`), NULL permitido.
- **Relaciones**:
  - `editorial: Optional["Editorial"] = Relationship(back_populates="libros")`
  - `genero: Optional["Genero"] = Relationship(back_populates="libros")`
  - `autorias: list["LibroAutor"] = Relationship(back_populates="libro")`
  - `renglones: list["RenglonVenta"] = Relationship(back_populates="libro")`

### 5. `libro_autor` (Objeto de Asociación)
- `libro_id`: `int`, Foreign Key a `libro.id`, Primary Key compuesta, con índice explícito.
- `autor_id`: `int`, Foreign Key a `autor.id`, Primary Key compuesta, con índice explícito.
- `rol`: `str`, NOT NULL. Restricción `CHECK (rol IN ('autor', 'coautor', 'traductor', 'ilustrador'))`.
- `orden`: `int`, NOT NULL. Restricción `CHECK (orden >= 1)`.
- **Relaciones**:
  - `libro: Optional["Libro"] = Relationship(back_populates="autorias")`
  - `autor: Optional["Autor"] = Relationship(back_populates="autorias")`

### 6. `cliente`
- `id`: `int`, Primary Key, autoincremental.
- `nombre`: `str`, NOT NULL.
- `email`: `str`, `UNIQUE`, NOT NULL.
- **Relaciones**:
  - `perfil: Optional["PerfilCliente"] = Relationship(back_populates="cliente")` (1:1, retorna un único objeto, no lista)
  - `ventas: list["Venta"] = Relationship(back_populates="cliente")`

### 7. `perfil_cliente`
- `id`: `int`, Primary Key, autoincremental.
- `cliente_id`: `int`, Foreign Key a `cliente.id`, `UNIQUE` (garantía 1 a 1), con índice explícito, NOT NULL.
- `telefono`: `str`, NOT NULL.
- `direccion`: `str`, NOT NULL.
- **Relaciones**:
  - `cliente: Optional["Cliente"] = Relationship(back_populates="perfil")`

### 8. `venta`
- `id`: `int`, Primary Key, autoincremental.
- `cliente_id`: `int`, Foreign Key a `cliente.id`, con índice explícito, NOT NULL.
- `fecha`: `datetime` (con zona horaria UTC / timezone-aware), NOT NULL.
- `total`: `Decimal`, tipo `NUMERIC(12, 2)`, NOT NULL. Restricción `CHECK (total >= 0)`.
- **Relaciones**:
  - `cliente: Optional["Cliente"] = Relationship(back_populates="ventas")`
  - `renglones: list["RenglonVenta"] = Relationship(back_populates="venta", cascade_delete=True)`

### 9. `renglon_venta`
- `id`: `int`, Primary Key, autoincremental.
- `venta_id`: `int`, Foreign Key a `venta.id`, con índice explícito, NOT NULL.
- `libro_id`: `int`, Foreign Key a `libro.id`, con índice explícito, NOT NULL.
- `cantidad`: `int`, NOT NULL. Restricción `CHECK (cantidad > 0)`.
- `precio_unitario`: `Decimal`, tipo `NUMERIC(10, 2)`, NOT NULL. Restricción `CHECK (precio_unitario > 0)`.
- **Relaciones**:
  - `venta: Optional["Venta"] = Relationship(back_populates="renglones")`
  - `libro: Optional["Libro"] = Relationship(back_populates="renglones")`

## Claves foráneas, índices y reglas de integridad
1. **Regla de oro de índices en PostgreSQL**: Toda columna con Foreign Key (`editorial_id`, `genero_id`, `libro_id`, `autor_id`, `cliente_id`, `venta_id`) DEBE llevar `index=True` explícito en su definición de campo.
2. **Valores monetarios**: Usar siempre `Decimal` (`condecimal` o `Decimal` nativo con `sa_column=Column(Numeric(10, 2))`), jamás `float` para prevenir pérdida de precisión binaria.
3. **Seed data inicial**: Se proveerá un script o comando ejecutable (ej. `python -m app.initial_data` o similar) para poblar la base en un estado conocido de prueba con editoriales, autores, géneros y libros.
