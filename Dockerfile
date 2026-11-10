# Imagen de ejecución de la API Librería (una sola etapa, sólo wheels binarios).
FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Usuario y grupo de sistema sin privilegios (sintaxis busybox de Alpine).
RUN addgroup -S appuser && adduser -S -G appuser -H -D appuser

# Dependencias primero: un cambio sólo de código reutiliza esta capa.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --only-binary=:all: -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Sólo el paquete de la aplicación (nunca COPY . .).
COPY --chown=appuser:appuser app ./app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8000/health/ready || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
