# Visión y Objetivos

## Propósito del sistema
Construir una API REST asincrónica para la gestión del catálogo y las ventas de una librería de barrio, integrando persistencia relacional avanzada mediante SQLModel y PostgreSQL, ejecución no bloqueante, y empaquetado para despliegue en un VPS con Docker (imagen `python:3.12-alpine`).

El sistema demuestra la aplicación práctica de:
1. Fundamentos y contratos HTTP asincrónicos con FastAPI.
2. Modelado relacional completo: asociación, agregación, composición, 1 a 1 y N a N con entidad intermedia.
3. Consultas optimizadas con carga anticipada (`joinedload` y `selectinload`) eliminando el problema de N+1.
4. Garantías de integridad delegadas en la base de datos (UNIQUE, CHECK, Foreign Keys).
5. Despliegue seguro en contenedor ligero con ejecución no-root y sin fuga de credenciales.

## Objetivos por actor
| Actor | Objetivo principal | Objetivos secundarios |
|---|---|---|
| **Cliente / Comprador** | Consultar catálogo de libros y registrar compras con sus datos de perfil. | Filtrar libros por título/género, recibir notificación asíncrona de comprobante. |
| **Administrador / Librero** | Gestionar el catálogo editorial (autores, géneros, editoriales, libros) y auditar ventas. | Garantizar que no se modifiquen ventas pasadas ni se vendan libros con datos inconsistentes. |
| **Docente / Evaluador (Cátedra)** | Validar cumplimiento técnico estricto, endpoints, pruebas .http y despliegue saludable en VPS. | Comprobar ausencia de bloqueos de hilo, límites de tamaño en Docker, y no filtrado de secretos. |

## Alcance v1.0
- **Catálogo de libros**: CRUD y asociaciones para Editorial, Género, Autor y Libro (con tabla de asociación `LibroAutor` que contiene `rol` y `orden`).
- **Clientes y Perfiles**: Registro de clientes (email único) y gestión de perfil opcional 1:1 (`telefono`, `direccion`).
- **Gestión de Ventas**: Alta de venta transaccional y atómica con sus renglones (composición pura). Copia estática de precio unitario del libro al momento de venta y cálculo server-side del total.
- **Notificaciones en background**: Despacho de comprobante en segundo plano usando `BackgroundTasks` sin bloquear la respuesta HTTP.
- **Endpoints de Salud**: `/health/live` (sin base) y `/health/ready` (`SELECT 1`).
- **Paginación y Filtros**: Paginación uniforme con `limit` (1-100, default 20) y `offset` (default 0), y búsqueda insensible a mayúsculas con parámetros ligados.
- **Empaquetado Docker**: Dockerfile multi-etapa o minimalista basado en `python:3.12-alpine` (< 100 MB imagen base), usuario no-root, variables por `.env`, `HEALTHCHECK` por IPv4.

## Fuera de alcance
- Autenticación y autorización mediante tokens/JWT (tema de capítulos posteriores).
- Patrones Repository y Unit of Work abstractos (la lógica reside directamente en el service recibiendo la sesión).
- Colas de tareas distribuidas externas (Redis / Celery / RQ) — se usa únicamente `BackgroundTasks` nativo de FastAPI.
- Docker Compose y orquestación multi-contenedor (PostgreSQL ya corre en el VPS).
- Sistema de migraciones como Alembic (el esquema se inicializa con `SQLModel.metadata.create_all` en el lifespan).
- Endpoint para modificación o borrado de ventas (las ventas son inmutables, registran un hecho histórico).

## Métricas de éxito
- 100% de los casos de prueba C-01 a C-08 aprobados.
- 100% de los criterios de despliegue en VPS D-01 a D-07 satisfechos.
- Carga de consultas fija en operaciones complejas de libros y ventas (cero consultas N+1).
- Tamaño de imagen base `python:3.12-alpine` < 100 MB.
