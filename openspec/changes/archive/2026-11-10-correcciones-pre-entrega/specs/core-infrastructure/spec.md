# Spec Delta: core-infrastructure

## MODIFIED Requirements

### Requirement: Inicialización y cierre del motor en el ciclo de vida
La aplicación SHALL inicializar el motor asincrónico y la fábrica de sesiones en su ciclo de vida, guardar ambos en el estado de la aplicación, ejecutar la creación de tablas faltantes al arrancar, y liberar los recursos del motor al apagarse.

#### Scenario: Arranque de la aplicación con creación de tablas
- **WHEN** la aplicación FastAPI inicia su ciclo de vida (`lifespan`)
- **THEN** se inicializa el motor asincrónico `AsyncEngine` con la URL de configuración, se crea a partir de ese motor una fábrica de sesiones asincrónicas con `expire_on_commit=False`, se ejecuta `SQLModel.metadata.create_all` para crear tablas que no existan, y se almacenan el motor en `app.state.engine` y la fábrica en `app.state.session_factory`.

#### Scenario: Apagado ordenado de la aplicación
- **WHEN** la aplicación FastAPI finaliza su ejecución
- **THEN** se invoca `await app.state.engine.dispose()` cerrando todas las conexiones del pool.

#### Scenario: Arranque con base de datos inaccesible
- **WHEN** la aplicación inicia su ciclo de vida y no logra conectarse a la base de datos para crear las tablas
- **THEN** el arranque se aborta (la aplicación no comienza a atender peticiones), se liberan los recursos del motor, se registra un mensaje propio de error que no incluye la URL de conexión ni credenciales, y el proceso termina con código distinto de cero.

### Requirement: Inyección de sesión asincrónica por petición
El sistema SHALL proveer una sesión asincrónica de base de datos por cada petición HTTP, obtenida de la fábrica de sesiones guardada en el estado de la aplicación, con la opción `expire_on_commit=False`.

#### Scenario: Obtención de sesión en handler HTTP
- **WHEN** un handler de FastAPI requiere acceso a base de datos mediante `Depends(get_session)`
- **THEN** se entrega una instancia de `AsyncSession` activa, creada por `app.state.session_factory` y configurada con `expire_on_commit=False`, que se cierra automáticamente al finalizar la petición.

#### Scenario: Una sesión distinta por petición
- **WHEN** se atienden dos peticiones que requieren sesión
- **THEN** cada una recibe su propia instancia de `AsyncSession`, ambas creadas por la misma fábrica de `app.state.session_factory`.

### Requirement: Configuración fuertemente tipada desde variables de entorno
El sistema SHALL leer y validar la configuración del entorno mediante un modelo tipado sin valores secretos predefinidos, y SHALL declarar explícitamente como dependencias de ejecución los componentes de lectura de configuración (`pydantic-settings` y `python-dotenv`).

#### Scenario: Carga exitosa de configuración válida
- **WHEN** la aplicación carga las variables desde el archivo `.env` o variables del sistema
- **THEN** se validan los valores tipados de `DATABASE_URL` (cadena no vacía con driver asyncpg), `SQL_ECHO` (booleano) y `APP_PORT` (entero).

#### Scenario: DATABASE_URL ausente
- **WHEN** la configuración se carga sin `DATABASE_URL` en las variables de entorno ni en el archivo `.env`
- **THEN** la validación falla con un error de configuración y la aplicación no arranca; no se usa ninguna URL ni credencial por defecto.

#### Scenario: Dependencias de configuración declaradas
- **WHEN** se inspecciona `requirements.txt`
- **THEN** figuran `pydantic-settings` y `python-dotenv>=1.0` como dependencias directas, y la imagen se sigue construyendo instalando sólo wheels binarios.
