# Actores y Roles

## Actores del sistema
| Actor | Descripción | Cómo interactúa |
|---|---|---|
| **Cliente / Consumidor** | Persona que compra libros en la librería. Puede registrar su usuario y un perfil con teléfono y dirección. | Envía peticiones HTTP a los endpoints de `/clientes`, consulta libros en `/libros`, y emite compras en `/ventas`. |
| **Operador / Librero** | Personal de la librería que administra el catálogo y consulta las ventas realizadas. | Registra autores, géneros, editoriales y libros a través de los endpoints REST correspondientes. |
| **Sistema Evaluador (Docente / Script de Test)** | Herramienta automatizada o docente que prueba la API con archivos `.http` y valida el despliegue en el VPS. | Ejecuta suite de pruebas (`test/*.http`), verifica respuestas HTTP, códigos 201/404/409/422, y revisa logs de Docker. |

## Matriz de acceso funcional
> **Nota de alcance**: La consigna especifica explícitamente que autenticación y autorización (Capítulo 5) quedan fuera de evaluación para este parcial. Por lo tanto, no se implementa seguridad basada en roles (RBAC) ni tokens JWT; todos los endpoints están expuestos y abiertos para consumo de la API.

| Recurso | Lectura (GET) | Creación (POST) | Modificación (PATCH) | Eliminación (DELETE) |
|---|---|---|---|---|
| `/health/*` | Pública | No disponible | No disponible | No disponible |
| `/editoriales/` | Pública | Permitida | Permitida | No evaluada |
| `/generos/` | Pública | Permitida | No requerida | No evaluada |
| `/autores/` | Pública | Permitida | Permitida | No evaluada |
| `/libros/` | Pública | Permitida (con autores) | Permitida (campos sueltos) | No evaluada |
| `/clientes/` | Pública | Permitida | Permitida | No evaluada |
| `/clientes/{id}/perfil` | Pública | Permitida (máx 1) | No requerida | No evaluada |
| `/ventas/` | Pública | Permitida (con renglones) | **PROHIBIDA** (RN-08) | **PROHIBIDA** (RN-08) |

## Rutas públicas
Al no requerirse autenticación en esta etapa, **todas las rutas son públicas** y accesibles directamente bajo el host y puerto donde se expone la API.
