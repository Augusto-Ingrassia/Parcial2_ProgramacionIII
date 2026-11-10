"""Invariantes estáticas del empaquetado Docker (no requieren Docker)."""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CMD_ESPERADO = 'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]'

DOCKERFILE_VALIDO = """\
FROM python:3.12-alpine
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN addgroup -S appuser && adduser -S -G appuser -H -D appuser
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --only-binary=:all: -r /tmp/requirements.txt && rm /tmp/requirements.txt
COPY --chown=appuser:appuser app ./app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s CMD wget -qO- http://127.0.0.1:8000/health/ready || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
"""


def _instrucciones(texto: str) -> list[str]:
    """Une continuaciones con barra invertida y descarta comentarios/vacías."""
    unido = re.sub(r"\\\r?\n", " ", texto)
    return [
        linea.strip() for linea in unido.splitlines()
        if linea.strip() and not linea.strip().startswith("#")
    ]


def _indices(ins: list[str], palabra: str) -> list[int]:
    return [i for i, linea in enumerate(ins) if linea.split(None, 1)[0].upper() == palabra]


def verificar_dockerfile(texto: str) -> list[str]:
    """Devuelve la lista de invariantes violadas (vacía si cumple todas)."""
    ins = _instrucciones(texto)
    errores: list[str] = []

    if [ins[i] for i in _indices(ins, "FROM")] != ["FROM python:3.12-alpine"]:
        errores.append("base unica python:3.12-alpine")

    pip = [linea for linea in ins if "pip install" in linea]
    if not pip or not all("--no-cache-dir" in p and "--only-binary=:all:" in p for p in pip):
        errores.append("pip --no-cache-dir --only-binary")

    copias = _indices(ins, "COPY")
    i_req = next((i for i in copias if ins[i].endswith("requirements.txt /tmp/requirements.txt")), None)
    i_app = next((i for i in copias if re.search(r"\sapp\s+\./app$", ins[i])), None)
    if i_req is None or i_app is None or i_req > i_app:
        errores.append("COPY requirements antes de COPY app")
    if any(re.search(r"requirements\S*\.txt\s+(\.|\./|/app\S*)$", ins[i]) for i in copias):
        errores.append("requirements fuera de /app")
    if any(re.search(r"COPY\s+(--\S+\s+)*\.\s+\.", ins[i]) for i in copias):
        errores.append("sin COPY . .")

    if not any("addgroup" in l and "adduser" in l and "appuser" in l for l in ins):
        errores.append("addgroup/adduser appuser")

    users, runs, cmds = _indices(ins, "USER"), _indices(ins, "RUN"), _indices(ins, "CMD")
    if (
        len(users) != 1
        or ins[users[0]] != "USER appuser"
        or not cmds
        or (runs and users[0] < runs[-1])
        or users[0] > cmds[0]
    ):
        errores.append("USER appuser tras el ultimo RUN y antes de CMD")

    if "EXPOSE 8000" not in ins:
        errores.append("EXPOSE 8000")

    hc = [ins[i] for i in _indices(ins, "HEALTHCHECK")]
    if len(hc) != 1 or "http://127.0.0.1:8000/health/ready" not in hc[0] or "localhost" in texto:
        errores.append("HEALTHCHECK 127.0.0.1 sin localhost")

    if not cmds or ins[cmds[-1]] != CMD_ESPERADO:
        errores.append("CMD exacto")

    for i in _indices(ins, "ENV") + _indices(ins, "ARG"):
        if re.search(r"DATABASE_URL|PASSWORD|SECRET", ins[i], re.IGNORECASE):
            errores.append("sin secretos en ENV/ARG")
            break
    return errores


# --- Dockerfile real ---------------------------------------------------------

def test_dockerfile_real_cumple_invariantes():
    assert verificar_dockerfile((RAIZ / "Dockerfile").read_text(encoding="utf-8")) == []


# --- el verificador detecta cada violación (casos negativos) -----------------

def test_verificador_acepta_dockerfile_valido():
    assert verificar_dockerfile(DOCKERFILE_VALIDO) == []


def test_verificador_detecta_base_incorrecta_y_segunda_etapa():
    t = DOCKERFILE_VALIDO.replace("python:3.12-alpine", "python:3.12-slim")
    assert "base unica python:3.12-alpine" in verificar_dockerfile(t)
    t = "FROM python:3.12-alpine AS b\n" + DOCKERFILE_VALIDO
    assert "base unica python:3.12-alpine" in verificar_dockerfile(t)


def test_verificador_detecta_pip_sin_flags():
    t = DOCKERFILE_VALIDO.replace("--no-cache-dir ", "")
    assert "pip --no-cache-dir --only-binary" in verificar_dockerfile(t)
    t = DOCKERFILE_VALIDO.replace("--only-binary=:all: ", "")
    assert "pip --no-cache-dir --only-binary" in verificar_dockerfile(t)


def test_verificador_detecta_orden_de_copy_y_copy_total():
    req = "COPY requirements.txt /tmp/requirements.txt\n"
    t = DOCKERFILE_VALIDO.replace(req, "").replace("USER appuser", req + "USER appuser")
    assert "COPY requirements antes de COPY app" in verificar_dockerfile(t)
    t = DOCKERFILE_VALIDO.replace("COPY --chown=appuser:appuser app ./app", "COPY . .")
    assert "sin COPY . ." in verificar_dockerfile(t)
    t = DOCKERFILE_VALIDO.replace("requirements.txt /tmp/requirements.txt", "requirements.txt .")
    assert "requirements fuera de /app" in verificar_dockerfile(t)


def test_verificador_detecta_falta_de_usuario_y_orden():
    sin_user = DOCKERFILE_VALIDO.replace("USER appuser\n", "")
    assert "USER appuser tras el ultimo RUN y antes de CMD" in verificar_dockerfile(sin_user)
    tarde = DOCKERFILE_VALIDO.replace("USER appuser\n", "USER appuser\nRUN echo x\n")
    assert "USER appuser tras el ultimo RUN y antes de CMD" in verificar_dockerfile(tarde)
    sin_add = DOCKERFILE_VALIDO.replace("RUN addgroup", "RUN true #")
    assert "addgroup/adduser appuser" in verificar_dockerfile(sin_add)


def test_verificador_detecta_healthcheck_con_localhost_o_sin_expose():
    t = DOCKERFILE_VALIDO.replace("127.0.0.1", "localhost")
    assert "HEALTHCHECK 127.0.0.1 sin localhost" in verificar_dockerfile(t)
    t = DOCKERFILE_VALIDO.replace("EXPOSE 8000\n", "")
    assert "EXPOSE 8000" in verificar_dockerfile(t)


def test_verificador_detecta_cmd_y_secretos():
    t = DOCKERFILE_VALIDO.replace("0.0.0.0", "127.0.0.1")
    assert "CMD exacto" in verificar_dockerfile(t)
    t = DOCKERFILE_VALIDO.replace("ENV PYTHONUNBUFFERED=1", "ENV DATABASE_URL=postgresql://x")
    assert "sin secretos en ENV/ARG" in verificar_dockerfile(t)
    t = DOCKERFILE_VALIDO.replace("ENV PYTHONUNBUFFERED=1", "ARG DB_PASSWORD=1")
    assert "sin secretos en ENV/ARG" in verificar_dockerfile(t)


# --- .dockerignore -----------------------------------------------------------

IGNORAR = [
    ".env", ".env.*", ".venv", ".git", "__pycache__", "*.pyc", "evidencia/",
    ".pytest_cache", "tests/", "test/", "docs/", "Discovery/", "openspec/",
]


def faltantes_dockerignore(texto: str) -> list[str]:
    lineas = {
        linea.strip().removeprefix("**/")
        for linea in texto.splitlines()
        if linea.strip() and not linea.startswith("#")
    }
    equivalentes = {"*.pyc": {"*.py[cod]"}}
    return [
        p for p in IGNORAR
        if p not in lineas and not (equivalentes.get(p, set()) & lineas)
    ]


def test_dockerignore_real_excluye_lo_requerido():
    texto = (RAIZ / ".dockerignore").read_text(encoding="utf-8")
    assert faltantes_dockerignore(texto) == []


def test_dockerignore_verificador_detecta_faltantes():
    assert faltantes_dockerignore("") == IGNORAR
    assert faltantes_dockerignore(".env\n.venv\n") == [
        p for p in IGNORAR if p not in (".env", ".venv")
    ]
    assert faltantes_dockerignore("\n".join(IGNORAR)) == []


# --- requirements ------------------------------------------------------------

def _nombres(path: Path) -> list[str]:
    out = []
    for linea in path.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith(("#", "-")):
            out.append(re.split(r"[<>=!~;\s]", linea, maxsplit=1)[0].lower())
    return out


def test_requirements_runtime_sin_dependencias_de_test():
    nombres = _nombres(RAIZ / "requirements.txt")
    for prohibido in ("pytest", "pytest-asyncio", "httpx", "aiosqlite"):
        assert prohibido not in nombres
    for requerido in ("fastapi", "sqlmodel", "asyncpg", "uvicorn[standard]",
                      "pydantic-settings", "greenlet"):
        assert requerido in nombres


def test_requirements_dev_incluye_runtime_y_pruebas():
    texto = (RAIZ / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "-r requirements.txt" in texto.splitlines()
    assert {"pytest", "pytest-asyncio", "httpx", "aiosqlite"} <= set(
        _nombres(RAIZ / "requirements-dev.txt")
    )
