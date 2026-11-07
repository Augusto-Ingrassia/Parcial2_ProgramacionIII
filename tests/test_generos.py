import pytest
from pydantic import ValidationError
from sqlmodel import SQLModel

from app.modules.generos.models import Genero  # noqa: F401
from app.modules.generos.schemas import GeneroCreate

FORBIDDEN_TERMS = ("UNIQUE", "IntegrityError", "duplicate key", "constraint", "genero_nombre_key")


def test_genero_table_definition():
    table = SQLModel.metadata.tables["genero"]
    assert set(table.c.keys()) == {"id", "nombre"}
    assert table.c.nombre.unique is True
    assert table.c.nombre.nullable is False


@pytest.mark.parametrize("nombre", ["", "   "])
def test_create_rechaza_nombre_vacio(nombre):
    with pytest.raises(ValidationError):
        GeneroCreate(nombre=nombre)


def test_create_normaliza_espacios():
    assert GeneroCreate(nombre=" Novela ").nombre == "Novela"


async def _crear(client, nombre="Ciencia Ficción"):
    return await client.post("/generos/", json={"nombre": nombre})


@pytest.mark.asyncio
async def test_post_alta_exitosa(client):
    r = await _crear(client)
    assert r.status_code == 201
    assert isinstance(r.json()["id"], int)
    assert r.json()["nombre"] == "Ciencia Ficción"


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{}, {"nombre": "   "}])
async def test_post_invalido_422(client, payload):
    assert (await client.post("/generos/", json=payload)).status_code == 422
    assert (await client.get("/generos/")).json() == []


@pytest.mark.asyncio
async def test_post_duplicado_409_y_api_operativa(client):
    await _crear(client)
    r = await _crear(client)
    assert r.status_code == 409
    for term in FORBIDDEN_TERMS:
        assert term.lower() not in r.json()["detail"].lower()
    assert len((await client.get("/generos/")).json()) == 1
    assert (await _crear(client, "Terror")).status_code == 201


@pytest.mark.asyncio
async def test_list_orden_y_paginacion(client):
    for n in ("A", "B", "C"):
        await _crear(client, n)
    assert [g["nombre"] for g in (await client.get("/generos/")).json()] == ["A", "B", "C"]
    r = await client.get("/generos/?limit=1&offset=1")
    assert [g["nombre"] for g in r.json()] == ["B"]


@pytest.mark.asyncio
async def test_list_vacio(client):
    assert (await client.get("/generos/")).json() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("qs", ["limit=0", "limit=101", "offset=-1"])
async def test_list_paginacion_invalida(client, qs):
    assert (await client.get(f"/generos/?{qs}")).status_code == 422


@pytest.mark.asyncio
async def test_get_existente(client):
    g = (await _crear(client)).json()
    r = await client.get(f"/generos/{g['id']}")
    assert r.status_code == 200
    assert r.json() == g


@pytest.mark.asyncio
async def test_get_inexistente_404(client):
    r = await client.get("/generos/999")
    assert r.status_code == 404
    assert r.json()["detail"]
