# Librería API — Base de Conocimiento

Base de conocimiento canónica generada a partir de la consigna oficial del Parcial de Programación III (*"La librería con despliegue en el VPS"*).

## Índice de Archivos

| # | Archivo | Contenido |
|---|---|---|
| 01 | [01_vision_y_objetivos.md](01_vision_y_objetivos.md) | Propósito del sistema, objetivos por actor, alcance v1.0, fuera de alcance y métricas. |
| 02 | [02_descripcion_general.md](02_descripcion_general.md) | Stack tecnológico completo, diagrama de arquitectura modular, endpoints principales. |
| 03 | [03_actores_y_roles.md](03_actores_y_roles.md) | Actores del sistema, matriz de acceso funcional y notas de rutas públicas. |
| 04 | [04_modelo_de_datos.md](04_modelo_de_datos.md) | Diccionario de datos, ERD, tipos de relaciones, restricciones UNIQUE/CHECK, e índices. |
| 05 | [05_reglas_de_negocio.md](05_reglas_de_negocio.md) | Catálogo de reglas RN-01 a RN-12 con sus garantes esperados y respuestas HTTP. |
| 06 | [06_funcionalidades.md](06_funcionalidades.md) | Historias de usuario por épica (health, editoriales, géneros, autores, libros, clientes, ventas). |
| 07 | [07_flujos_principales.md](07_flujos_principales.md) | Flujos extremo a extremo (alta de venta con BackgroundTasks, alta de libros, consultas sin N+1). |
| 08 | [08_arquitectura_propuesta.md](08_arquitectura_propuesta.md) | Estructura obligatoria de carpetas, lifespan, gestión de sesiones y variables de entorno. |
| 09 | [09_decisiones_y_supuestos.md](09_decisiones_y_supuestos.md) | Decisiones arquitectónicas (DD-01 a DD-05) y supuestos inferidos. |
| 10 | [10_preguntas_abiertas.md](10_preguntas_abiertas.md) | Aspectos abiertos de configuración para el entorno de producción en VPS. |
| 11 | [11_despliegue_docker_y_vps.md](11_despliegue_docker_y_vps.md) | Guía técnica de la imagen `python:3.12-alpine`, usuario no-root, healthchecks y DEPLOY.md. |

## Quick Start para Desarrolladores

1. **Entender el alcance y contexto** → [01_vision_y_objetivos.md](01_vision_y_objetivos.md)
2. **Revisar el modelo relacional** → [04_modelo_de_datos.md](04_modelo_de_datos.md)
3. **Comprender las reglas de negocio críticas** → [05_reglas_de_negocio.md](05_reglas_de_negocio.md)
4. **Verificar estructura y patrones** → [08_arquitectura_propuesta.md](08_arquitectura_propuesta.md)
5. **Implementar flujos y endpoints** → [07_flujos_principales.md](07_flujos_principales.md), [06_funcionalidades.md](06_funcionalidades.md)
6. **Empaquetar y desplegar** → [11_despliegue_docker_y_vps.md](11_despliegue_docker_y_vps.md)

## Resumen Ejecutivo
El proyecto consiste en una API REST asincrónica construida con **FastAPI**, **SQLModel**, **SQLAlchemy 2.0 async** y **PostgreSQL 16**. Implementa un modelo de datos con todas las cardinalidades relacionales requeridas (asociación, agregación, composición, 1 a 1 y N a N mediante entidad intermedia `LibroAutor`). Garantiza lecturas optimizadas sin problema N+1 mediante carga anticipada (`joinedload` y `selectinload`), validaciones atómicas en servidor, y empaquetado seguro en Docker sobre `python:3.12-alpine` para puesta en producción en VPS.
