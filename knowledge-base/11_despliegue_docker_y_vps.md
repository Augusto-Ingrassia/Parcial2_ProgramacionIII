# Despliegue en Docker y VPS

Este documento complementario sintetiza los requisitos operativos, de seguridad y de evaluación para el empaquetado del proyecto en contenedor Docker y su puesta en línea en el VPS.

---

## Requisitos de la Imagen Docker (Ejercicio 7)

### 1. Imagen Base
- **Base oficial**: `python:3.12-alpine`.
- **Límite de tamaño**: La imagen base debe ocupar menos de 100 MB en disco (la oficial ocupa ~74.7 MB).
- **Razón**: Menor tiempo de descarga, menor consumo de disco en el VPS y reducción sustancial de superficie de ataque. Las dependencias del stack (`asyncpg`, `pydantic-core`, etc.) se instalan sin requerir compiladores adicionales.

### 2. Capas y Cache de Dockerfile
- Se copia e instala `requirements.txt` con la bandera `--no-cache-dir` antes de copiar el código fuente.
- De esta manera, si el código cambia pero las dependencias no, Docker reutiliza la capa en caché acelerando el build.

### 3. Usuario sin Privilegios (No-Root)
- La aplicación no debe correr como `root`.
- Se crea un grupo y usuario de sistema sin privilegios (ej. `appuser`) y se activa con la directiva `USER appuser`.

### 4. Gestión de Secretos y `.dockerignore`
- En el Dockerfile NO deben aparecer contraseñas, usuarios ni la variable `DATABASE_URL`.
- El archivo `.dockerignore` excluye estrictamente:
  - `.env`
  - `.venv`
  - `.git`
  - `__pycache__` y archivos `*.pyc`

### 5. Escucha de Red y Healthcheck
- El servidor Uvicorn debe iniciarse escuchando en `0.0.0.0:8000`.
- El Dockerfile declara un `HEALTHCHECK` periódico:
  ```dockerfile
  HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8000/health/ready || exit 1
  ```
  *(Se utiliza `127.0.0.1` en lugar de `localhost` para evitar que `wget` intente resolver por IPv6 `::1` fallando la conexión).*

---

## Ejecución en VPS (Ejercicio 8)

### Comando de Ejecución
```bash
docker run -d \
  --name libreria \
  -p <puerto>:8000 \
  --restart unless-stopped \
  --env-file <archivo-de-variables> \
  libreria
```

### Conectividad con la Base de Datos
- `localhost` dentro del contenedor refiere al propio contenedor y no al host VPS.
- Si PostgreSQL corre directamente en el host del VPS bajo Linux, se debe contemplar `--add-host=host.docker.internal:host-gateway` o emplear la IP de red provista por la cátedra.
- Si la base de datos no está accesible o no se provee `DATABASE_URL`, el arranque de la aplicación debe fallar inmediatamente y el contenedor debe detenerse (no quedar atendiendo en estado inconsistente).

---

## Carga de Datos Iniciales
Una vez levantado el contenedor y con las tablas creadas por el lifespan:
```bash
docker exec libreria python -m app.initial_data
```

---

## Documentación `DEPLOY.md`
El repositorio debe incluir en la raíz un archivo `DEPLOY.md` que detalle:
1. URL pública donde quedó desplegada la API en el VPS.
2. Día y hora del despliegue.
3. Comandos exactos de `docker build` y `docker run` (con el nombre del archivo de variables pero sin exponer sus contraseñas).
4. Procedimiento de actualización de la aplicación sin pérdida de datos.
