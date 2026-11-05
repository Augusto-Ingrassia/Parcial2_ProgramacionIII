# Descripción General

## Stack tecnológico
| Capa / Componente | Tecnología | Versión mínima | Uso / Justificación |
|---|---|---|---|
| **Lenguaje** | Python | 3.12 | Tipado estricto, sintaxis moderna async |
| **Framework Web** | FastAPI | 0.111 | Framework asincrónico, OpenAPI, inyección de dependencias `Depends()` |
| **ORM / Modelado** | SQLModel | 0.0.24 | Unificación de esquemas Pydantic y modelos SQLAlchemy |
| **Motor DB / Async** | SQLAlchemy | 2.0 (asincrónico) | Motor asincrónico, sesiones `AsyncSession`, `joinedload`, `selectinload` |
| **Driver PostgreSQL** | asyncpg | 0.30 | Driver de alto rendimiento asíncrono para PostgreSQL |
| **Base de Datos** | PostgreSQL | 16 | Motor relacional estándar (provisto en servidor VPS) |
| **Gestión de Entorno**| python-dotenv | 1.0 | Lectura de configuración y secrets desde `.env` |
| **Servidor ASGI** | uvicorn (fastapi[standard]) | Última compatible | Servidor HTTP asincrónico en `0.0.0.0:8000` |
| **Contenedorización** | Docker | 20.10+ | Empaquetado sobre `python:3.12-alpine`, usuario sin privilegios |

## Arquitectura general
La arquitectura sigue una organización modular por dominio funcional, manteniendo una separación estricta de responsabilidades:
- **`app/main.py`**: Instancia FastAPI, gestiona el ciclo de vida (`lifespan`) creando y cerrando el motor asíncrono en `app.state`, crea las tablas con `create_all`, y registra routers.
- **`app/core/`**: 
  - `config.py`: Carga y valida variables de entorno (`DATABASE_URL`, `SQL_ECHO`).
  - `database.py`: Instancia el motor asíncrono, fábrica de sesiones (`expire_on_commit=False`), y provee la dependencia `get_session`.
- **`app/modules/<modulo>/`**: Módulos independientes (`health`, `editoriales`, `generos`, `autores`, `libros`, `clientes`, `ventas`):
  - `models.py`: Modelos de base de datos SQLModel/SQLAlchemy con constraints, índices y relaciones (`Relationship`).
  - `schemas.py`: DTOs de entrada (`Create`, `Update`) y salida (`Read`) desacoplados de la persistencia.
  - `service.py`: Lógica de negocio, ejecución de queries con carga anticipada, captura y traducción de `IntegrityError`.
  - `router.py`: Endpoints HTTP con `async def`, inyección de dependencias y códigos de estado.

```
                  +-----------------------------------+
                  |          Cliente HTTP             |
                  +-----------------+-----------------+
                                    |
                            [ async requests ]
                                    v
                  +-----------------------------------+
                  |       FastAPI Router              |
                  |  - Parámetros tipados             |
                  |  - Validación de DTOs             |
                  |  - Inyección Depends(get_session) |
                  +-----------------+-----------------+
                                    |
                                    v
                  +-----------------------------------+
                  |        Domain Service             |
                  |  - Reglas de negocio (RN-01..12)  |
                  |  - BackgroundTasks                |
                  |  - Traducción de errores a HTTP   |
                  +-----------------+-----------------+
                                    |
                           [ AsyncSession ]
                                    v
                  +-----------------------------------+
                  |  SQLModel / SQLAlchemy 2.0 Async  |
                  |  - joinedload (relaciones 1:1, N:1)|
                  |  - selectinload (colecciones 1:N) |
                  +-----------------+-----------------+
                                    |
                               [ asyncpg ]
                                    v
                  +-----------------------------------+
                  |      PostgreSQL 16 (VPS)          |
                  |  - Constraints CHECK, UNIQUE, FK  |
                  +-----------------------------------+
```

## Integraciones externas
| Servicio | Propósito | Tipo | Detalle |
|---|---|---|---|
| **PostgreSQL Remoto (VPS)** | Persistencia de datos relacionales | Conexión TCP asyncpg | Servidor provisto por la cátedra, accesible mediante `DATABASE_URL` |
| **Docker Engine** | Aislamiento y ejecución en contenedor | Runtime de contenedores | Corriendo sobre VPS, publicado en puerto específico asignado |

## API REST — Resumen de endpoints principales
- `/health/live` (GET): Salud del proceso vivo (200).
- `/health/ready` (GET): Chequeo de conexión a DB con `SELECT 1` (200).
- `/editoriales/` (POST, GET), `/{id}` (GET, PATCH), `/{id}/libros` (GET).
- `/generos/` (POST, GET), `/{id}/libros` (GET).
- `/autores/` (POST), `/{id}` (GET, PATCH), `/{id}/libros` (GET).
- `/libros/` (POST con autores anidados, GET paginado/filtrado), `/{id}` (GET completo, PATCH).
- `/clientes/` (POST, GET, PATCH), `/{id}/perfil` (POST), `/{id}/ventas` (GET).
- `/ventas/` (POST con renglones anidados, GET paginado), `/{id}` (GET con renglones y cliente).
