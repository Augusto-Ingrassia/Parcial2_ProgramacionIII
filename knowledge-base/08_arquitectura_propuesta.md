# Arquitectura Propuesta

## Patrones aplicados
| Patrón / Técnica | Dónde se usa | Justificación técnica |
|---|---|---|
| **Estructura Modular por Dominio** | `app/modules/<modulo>/` | Cohesión alta y acoplamiento bajo; agrupa modelos, esquemas, servicios y rutas por entidad de negocio. |
| **Separación de Modelos y DTOs** | `models.py` vs `schemas.py` | Desacopla la representación de la base de datos de los contratos HTTP de entrada y salida; evita fugas de campos internos o IDs autoincrementales en altas. |
| **Carga Anticipada (Eager Loading)** | En servicios de lectura (`service.py`) | Utiliza `joinedload` para relaciones uno a uno / muchos a uno y `selectinload` para colecciones uno a muchos. Elimina el problema de consultas N+1. |
| **Inyección de Dependencias** | `Depends(get_session)` en routers | Gestión limpia del ciclo de vida de la sesión por cada petición HTTP, con `expire_on_commit=False`. |
| **Manejo Centralizado de Integridad** | `service.py` y exception handlers | Atrapa excepciones `IntegrityError` de SQLAlchemy y las traduce a códigos HTTP 409 con mensajes amigables sin revelar nombres de tablas ni esquemas (RN-12). |
| **Procesamiento Asincrónico de Fondo** | `BackgroundTasks` en FastAPI | Simulación de notificaciones al cliente tras una venta sin bloquear el event loop ni demorar la respuesta HTTP al usuario. |
| **Contenedorización sin Root** | `Dockerfile` | Ejecución segura bajo usuario sin privilegios en imagen minimalista Alpine Linux. |

## Estructura obligatoria de directorios
El proyecto se organiza estrictamente con la estructura por módulo requerida por la cátedra:

```
parcial-libreria/
├── app/
│   ├── core/
│   │   ├── config.py              # Lectura de variables de entorno (DATABASE_URL, SQL_ECHO)
│   │   └── database.py            # Motor asincrónico, SessionLocal, get_session
│   ├── modules/
│   │   ├── health/                # Endpoints de liveness y readiness
│   │   │   ├── router.py
│   │   │   └── service.py
│   │   ├── editoriales/           # Dominio Editorial
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── router.py
│   │   ├── generos/               # Dominio Género literario
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── router.py
│   │   ├── autores/               # Dominio Autor
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── router.py
│   │   ├── libros/                # Dominio Libro y LibroAutor
│   │   │   ├── models.py          # Incluye Libro y LibroAutor
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── router.py
│   │   ├── clientes/              # Dominio Cliente y PerfilCliente
│   │   │   ├── models.py          # Incluye Cliente y PerfilCliente
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── router.py
│   │   └── ventas/                # Dominio Venta y RenglonVenta
│   │       ├── models.py          # Incluye Venta y RenglonVenta
│   │       ├── schemas.py
│   │       ├── service.py
│   │       └── router.py
│   └── main.py                    # Aplicación FastAPI, lifespan y registro de routers
├── test/                          # Archivos .http con casos de prueba
│   ├── health.http
│   ├── editoriales.http
│   ├── generos.http
│   ├── autores.http
│   ├── libros.http
│   ├── clientes.http
│   └── ventas.http
├── evidencia/                     # Salidas de consola del caso C-07 y casos D
├── Dockerfile                     # Imagen python:3.12-alpine (< 100 MB base), no-root
├── .dockerignore                  # Exclusión de .env, .venv, __pycache__, .git
├── DEPLOY.md                      # Documentación del despliegue en VPS
├── requirements.txt               # Dependencias Python exactas
├── env.example                    # Plantilla de variables sin secretos
└── README.md                      # Instrucciones de ejecución y nombres de integrantes
```

## Seguridad y variables de entorno
- **Gestión de Secretos**: Ninguna contraseña ni URL de base de datos se versiona en git ni se hornea en capas de Docker.
- **Entorno local**: Se lee de un archivo `.env` local (ignorado en `.gitignore`).
- **Entorno contenedor**: Se inyecta mediante `--env-file` al momento de ejecutar `docker run`.

### Tabla de variables de entorno
| Variable | Descripción | Ejemplo | Sensible (Y/N) |
|---|---|---|---|
| `DATABASE_URL` | URL de conexión asincrónica a PostgreSQL | `postgresql+asyncpg://user:pass@host:5432/dbname` | **Y** |
| `SQL_ECHO` | Activa o desactiva el volcado de queries SQL en consola | `false` (o `true` para debug C-07) | N |
| `APP_PORT` | Puerto interno/externo de escucha | `8000` | N |

## Políticas de Ciclo de Vida y Sesiones
- En `app/main.py`: Se implementa `lifespan` asincrónico:
  - **Al inicio**: Se inicializa el `AsyncEngine`, se crean las tablas faltantes con `SQLModel.metadata.create_all`, y se almacena el motor en `app.state.engine`.
  - **Al apagar**: Se ejecuta `await app.state.engine.dispose()`.
- En `app/core/database.py`: La sesión se crea con `async_sessionmaker(..., expire_on_commit=False)`. Esto es indispensable para poder leer atributos y relaciones de los objetos devueltos después del `commit()` sin provocar recargas síncronas ni errores de detached instance.
