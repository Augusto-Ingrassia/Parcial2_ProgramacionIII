# Design: Clientes y Perfiles

## Context
Se reutilizan las piezas de C-01/C-02/C-03: `SessionDep`, `PaginationDep`, `NonEmptyStr` y `commit_o_http` / `tipo_violacion` de `app/core/exceptions.py`. Ver `proposal.md` y `specs/clientes/spec.md`.

## Goals / Non-Goals

**Goals:**
- Uno a uno real: a lo sumo un perfil por cliente, garantizado por la base.
- Unicidad de email delegada en la base, sin consulta previa.

**Non-Goals:**
- Historial de compras (`GET /clientes/{id}/ventas`): C-05.
- Editar o borrar perfiles.

## Decisions

### Decisión 1: Lado de la FK en el uno a uno
- **Decisión**: La FK vive en `perfil_cliente.cliente_id` con `UNIQUE` e índice (`Field(foreign_key="cliente.id", unique=True, index=True)`).
- **Razón**: El perfil depende del cliente (un cliente puede no tener perfil: `0..1`), así que la referencia la lleva el lado opcional. El `UNIQUE` convierte el uno a muchos en uno a uno y es el garante de RN-09.

### Decisión 2: `Cliente.perfil` como objeto, no lista
- **Decisión**: `perfil: Optional["PerfilCliente"] = Relationship(back_populates="cliente", sa_relationship_kwargs={"uselist": False, "lazy": "raise"})`.
- **Razón**: La consigna exige que `Cliente.perfil` devuelva un objeto. `lazy="raise"` mantiene la regla de no depender de la carga perezosa: toda lectura que lo serialice usa `joinedload(Cliente.perfil)`.

### Decisión 3: Email normalizado y validado en el DTO
- **Decisión**: `Email = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]`.
- **Razón**: Evita que `Ana@Mail.com` y `ana@mail.com` convivan como clientes distintos sin depender de `CITEXT`, y rechaza con `422` textos que no son emails sin agregar la dependencia `email-validator`.
- **Supuesto**: el email se guarda en minúsculas.

### Decisión 4: Perfil sin `SELECT` previo; FK → 404, UNIQUE → 409
- **Decisión**: `crear_perfil` inserta `PerfilCliente(cliente_id=id, ...)` y confirma con `commit_o_http` usando el mapa `{"unique": (409, "El cliente ya tiene un perfil"), "foreign_key": (404, "Cliente no encontrado")}`.
- **Razón**: El endpoint de referencia declara `201, 404, 409`. El cliente es un recurso de la ruta, así que su inexistencia es `404`; la violación de `UNIQUE` es el `409` de RN-09. Ambos los decide la base, sin carrera entre una verificación y la escritura.

### Decisión 5: Lecturas
- `GET /clientes/{id}`, `GET /clientes/` y la respuesta de `PATCH` cargan `joinedload(Cliente.perfil)` (relación a uno → misma consulta).
- `POST /clientes/` construye la respuesta con `perfil = null` sin volver a leer: un cliente recién creado no tiene perfil.

### Decisión 6: PATCH
- `ClienteUpdate` (`nombre`, `email`) con `exclude_unset`; `null` explícito → `422`; email de otro cliente → `409 "Ya existe un cliente con ese email"`.

### Decisión 7: UI Mockups
- `no (no UI)`.

## Risks / Trade-offs
- **[Email en minúsculas]** → cambia lo que el cliente envió; se documenta en la spec.
- **[Validación de email simple]** → acepta direcciones raras pero sintácticamente plausibles; suficiente para el alcance académico.

## Migration Plan
- Aditivo: `create_all` crea `cliente` y `perfil_cliente` en el próximo arranque.
