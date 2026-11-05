# Spec Delta

## Purpose
Establece la configuración asincrónica del motor de base de datos, la gestión de ciclo de vida de la aplicación y la inyección de dependencias de sesión.

## ADDED Requirements

### Requirement: Inicialización y cierre del motor en el ciclo de vida
La aplicación SHALL inicializar el motor asincrónico y ejecutar la creación de tablas faltantes al arrancar, y liberar los recursos del motor al apagarse.

#### Scenario: Arranque de la aplicación con creación de tablas
- **WHEN** la aplicación FastAPI inicia su ciclo de vida (`lifespan`)
- **THEN** se inicializa el motor asincrónico `AsyncEngine` con la URL de configuración, se ejecuta `SQLModel.metadata.create_all` para crear tablas que no existan, y se almacena el motor en `app.state.engine`.

#### Scenario: Apagado ordenado de la aplicación
- **WHEN** la aplicación FastAPI finaliza su ejecución
- **THEN** se invoca `await app.state.engine.dispose()` cerrando todas las conexiones del pool.

### Requirement: Inyección de sesión asincrónica por petición
El sistema SHALL proveer una sesión asincrónica de base de datos por cada petición HTTP con la opción `expire_on_commit=False`.

#### Scenario: Obtención de sesión en handler HTTP
- **WHEN** un handler de FastAPI requiere acceso a base de datos mediante `Depends(get_session)`
- **THEN** se entrega una instancia de `AsyncSession` activa configurada con `expire_on_commit=False` que se cierra automáticamente al finalizar la petición.

### Requirement: Configuración fuertemente tipada desde variables de entorno
El sistema SHALL leer y validar la configuración del entorno mediante un modelo tipado sin valores secretos predefinidos.

#### Scenario: Carga exitosa de configuración válida
- **WHEN** la aplicación carga las variables desde el archivo `.env` o variables del sistema
- **THEN** se validan los valores tipados de `DATABASE_URL` (cadena no vacía con driver asyncpg), `SQL_ECHO` (booleano) y `APP_PORT` (entero).
