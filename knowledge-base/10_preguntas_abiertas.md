# Preguntas Abiertas

## Inconsistencias Detectadas
No se detectaron inconsistencias entre secciones de la consigna. La consigna oficial del parcial es autocontenida, exhaustiva y fija un contrato de dominio estricto.

## Preguntas Abiertas y Aspectos de Implementación

| Prioridad | Pregunta / Aspecto | Bloquea | Decisor / Acción |
|---|---|---|---|
| **Alta** | ¿Cuáles son las credenciales exactas del servidor VPS y base de datos provista por la cátedra para el despliegue final? | Despliegue en VPS (Ejercicio 8 / Casos D) | Docente / Cátedra. Se configuran en el servidor en el archivo `--env-file` sin subirlas a git. |
| **Media** | ¿Qué puerto específico tiene asignado el grupo en el VPS para el mapeo `-p <puerto>:8000`? | Despliegue en VPS y DEPLOY.md | Docente / Cátedra. |
| **Media** | ¿Cómo se estructurará el script de datos iniciales para el comando `docker exec libreria ...`? | Caso D-03 y Carga Inicial | Equipo de desarrollo. Se implementará un script de seed asincrónico (ej. `python -m app.initial_data`) que cargue libros, autores, géneros y editoriales base. |
| **Baja** | ¿Se requiere un logging formateado específico para la tarea de segundo plano de envío de comprobante? | Caso D-07 | Consigna pide `await asyncio.sleep(0.5)` y un mensaje descriptivo en el log estándar (`logging.info(...)`). |
