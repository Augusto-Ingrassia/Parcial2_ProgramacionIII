# API Librería (Parcial Programación III) — Instrucciones para Agentes

> Este archivo (y su copia canónica `CLAUDE.md`) es lo PRIMERO que todo agente lee al ingresar al repositorio.  
> Generado a partir de `knowledge-base/`, `CHANGES.md` y `.atl/skill-registry.md`. No editar a mano sin mantener sincronizados ambos archivos.

---

## Stack Tecnológico

| Capa / Componente | Tecnología | Versión mínima | Uso / Justificación |
|---|---|---|---|
| **Lenguaje** | Python | 3.12 | Tipado estricto, sintaxis moderna async |
| **Framework Web** | FastAPI | 0.111 | Framework asincrónico, OpenAPI, inyección de dependencias `Depends()` |
| **ORM / Modelado** | SQLModel | 0.0.24 | Unificación de esquemas Pydantic y modelos SQLAlchemy |
| **Motor DB / Async** | SQLAlchemy | 2.0 (asincrónico) | Motor asincrónico, sesiones `AsyncSession`, `joinedload`, `selectinload` |
| **Driver PostgreSQL** | asyncpg | 0.30 | Driver de alto rendimiento asíncrono para PostgreSQL |
| **Base de Datos** | PostgreSQL | 16 | Motor relacional estándar (provisto en servidor VPS) |
| **Gestión de Entorno**| python-dotenv / pydantic-settings | 1.0 / 2.3+ | Lectura de configuración y secrets desde `.env` |
| **Servidor ASGI** | uvicorn (fastapi[standard]) | Última compatible | Servidor HTTP asincrónico en `0.0.0.0:8000` |
| **Contenedorización** | Docker | 20.10+ | Empaquetado sobre `python:3.12-alpine` (< 100 MB base), usuario sin privilegios |

Detalle completo: [knowledge-base/02_descripcion_general.md](knowledge-base/02_descripcion_general.md)

---

## Base de Conocimiento

La fuente de verdad del dominio vive en `knowledge-base/`. **Leé el archivo relevante ANTES de implementar cualquier change o tarea.**

| Archivo | Cuándo leerlo |
|---|---|
| [01_vision_y_objetivos.md](knowledge-base/01_vision_y_objetivos.md) | Propósito del sistema, objetivos académicos, alcance v1.0 y exclusiones. |
| [02_descripcion_general.md](knowledge-base/02_descripcion_general.md) | Stack técnico, arquitectura modular por dominio y endpoints principales. |
| [03_actores_y_roles.md](knowledge-base/03_actores_y_roles.md) | Actores (cliente, librero, evaluador) y matriz de acceso funcional. |
| [04_modelo_de_datos.md](knowledge-base/04_modelo_de_datos.md) | Diccionario de datos, ERD, relaciones (asociación, agregación, composición, 1:1, N:M) e índices. |
| [05_reglas_de_negocio.md](knowledge-base/05_reglas_de_negocio.md) | Catálogo de reglas RN-01 a RN-12 con garantes esperados y códigos HTTP. |
| [06_funcionalidades.md](knowledge-base/06_funcionalidades.md) | Historias de usuario por épica modular (`health`, `editoriales`, `generos`, `autores`, `libros`, `clientes`, `ventas`). |
| [07_flujos_principales.md](knowledge-base/07_flujos_principales.md) | Flujos E2E: alta transaccional de venta con `BackgroundTasks` y lecturas sin N+1. |
| [08_arquitectura_propuesta.md](knowledge-base/08_arquitectura_propuesta.md) | Estructura obligatoria de directorios, lifespan, gestión de sesiones y variables de entorno. |
| [09_decisiones_y_supuestos.md](knowledge-base/09_decisiones_y_supuestos.md) | Decisiones arquitectónicas fundamentadas (DD-01 a DD-05). |
| [10_preguntas_abiertas.md](knowledge-base/10_preguntas_abiertas.md) | Aspectos abiertos de configuración para el entorno de producción en VPS. |
| [11_despliegue_docker_y_vps.md](knowledge-base/11_despliegue_docker_y_vps.md) | Requisitos de la imagen Alpine (< 100 MB), usuario no-root, variables por `--env-file` y `DEPLOY.md`. |
| [README.md](knowledge-base/README.md) | Índice navegable general de la base de conocimiento. |

---

## Skills Disponibles

Las skills instaladas para este proyecto viven en `.agents/skills/` y se encuentran catalogadas con reglas compactas en `.atl/skill-registry.md`.

| Agente / Rol | Enfoque de Implementación | Skills que Carga |
|---|---|---|
| **Backend Core** | FastAPI / SQLModel / SQLAlchemy 2.0 Async / PostgreSQL 16 | `fastapi-python`, `fastapi`, `postgresql-table-design` |
| **Testing / QA** | Pruebas HTTP (`test/*.http`), verificación de códigos de estado, validación RN-01..12 y auditoría de consultas N+1 | `fastapi-python`, `postgresql-table-design` |
| **DevOps / Despliegue** | Dockerfile sobre `python:3.12-alpine`, usuario no-root, scripts de inicio, variables `--env-file` y `DEPLOY.md` | `active-orchestrator` |
| **Orquestación Metodológica** | OpenSpec / SDD / Fundaciones / Documentación | `active-orchestrator`, `agent-instruction`, `kb-creator`, `roadmap-generator`, `skill-registry`, `design-system` |

> Los compact rules de cada skill los resuelve el orquestador desde `.atl/skill-registry.md` (generado por `skill-registry`; no versionado — no está en el repo). Esta tabla solo mapea skill → rol.

---

## Roadmap de Changes

El plan de implementación maestro se encuentra en [CHANGES.md](CHANGES.md).

- **Total**: 7 changes distribuidos en 6 fases.
- **Camino Crítico (6 changes — mínimo irreducible)**:
  ```
  C-01 → C-02 → C-03 → C-05 → C-06 → C-07
  ```
- **Primer Change**: `C-01` (`core-infrastructure-and-health`).

**Antes de cualquier `/opsx:propose`**: leé [CHANGES.md](CHANGES.md), identificá las dependencias del change y los documentos indicados en "Leer antes".

---

## Reglas Duras (Específicas del Proyecto)

> Reglas globales ya definidas en la metodología del stack (orquestador, governance, TDD estricto, memoria engram): el proyecto las hereda. Acá viven las reglas obligatorias específicas de este proyecto derivadas de la consigna y el stack.

1. **Asincronía Pura**: NUNCA usar funciones bloqueantes (`time.sleep`, `requests`, I/O síncrono a base de datos) dentro de los handlers de FastAPI → usar siempre `async def`, sentencias `await` y `BackgroundTasks` para despachar avisos en segundo plano (simulado con `await asyncio.sleep(0.5)`).
2. **Eliminación del Problema N+1**: NUNCA realizar lecturas de relaciones con carga perezosa (lazy loading) → usar siempre carga anticipada declarada en la consulta con `joinedload` (relaciones a uno: editorial, género, cliente) o `selectinload` (colecciones: autores, renglones).
3. **Precisión Financiera**: NUNCA usar `float` para montos monetarios o precios → usar siempre `Decimal` (`NUMERIC(10, 2)` o `NUMERIC(12, 2)`).
4. **Integridad Delegada en la Base**: NUNCA reemplazar garantías de la base con validaciones previas inseguras → delegar en restricciones `UNIQUE`, `CHECK` y Foreign Keys de PostgreSQL; capturar `IntegrityError` y traducirlo limpiamente a `HTTP 409 Conflict` con mensaje propio sin exponer trazas internas ni nombres de tablas o restricciones (RN-12).
5. **Índices en Claves Foráneas**: NUNCA declarar una columna de Foreign Key sin índice → incluir siempre `index=True` explícito en todas las FKs (`editorial_id`, `genero_id`, `libro_id`, `autor_id`, `cliente_id`, `venta_id`).
6. **Alta de Libros sin SELECT Previo**: NUNCA ejecutar consultas previas con `if` para verificar si `editorial_id` o `autor_id` existen → intentar escribir directamente; si la base rechaza la clave foránea, atrapar la excepción y responder `409 Conflict`.
7. **Inmutabilidad de Ventas**: NUNCA crear endpoints `PATCH`, `PUT` o `DELETE` para ventas → las ventas son inmutables y registran un hecho histórico (RN-08).
8. **Copia de Precios y Totales en Servidor**: NUNCA confiar en precios unitarios o totales provistos por el cliente en el payload de venta → el servidor lee el precio vigente del libro en la base de datos (RN-06) y calcula el total como suma de cantidades por precio unitario (RN-07).
9. **Empaquetado y Seguridad Docker**: NUNCA usar imágenes base pesadas ni ejecutar como root → imagen base obligatoria `python:3.12-alpine` (< 100 MB), usuario sin privilegios (`USER appuser`), sin secretos ni `.env` horneados en capas, y comprobación de salud (`HEALTHCHECK`) siempre contra `127.0.0.1:8000` en lugar de `localhost`.

---

## Flujo de Trabajo

```
1. Leer la KB relevante (knowledge-base/)        → entender el dominio y contratos
2. Identificar el change en CHANGES.md           → verificar que sus dependencias estén archivadas
3. /opsx:propose C-NN-nombre                     → generar proposal + design + specs + tasks
4. Implementar las tasks (cargando skills)       → cumplir estrictamente las reglas duras
5. /opsx:archive C-NN-nombre + marcar [x]        → sincronizar specs y cerrar el change
```

Aplicar TODAS las reglas duras en cada paso. Ante cualquier duda o conflicto entre la KB y este archivo, las reglas duras prevalecen.
