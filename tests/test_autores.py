import pytest
from pydantic import ValidationError
from sqlmodel import SQLModel

from app.modules.autores.models import Autor  # noqa: F401
from app.modules.autores.schemas import AutorCreate, AutorUpdate


def test_autor_table_definition():
    table = SQLModel.metadata.tables["autor"]
    assert set(table.c.keys()) == {"id", "nombre", "nacionalidad"}
    assert table.c.nombre.nullable is False
    assert table.c.nacionalidad.nullable is False
    assert table.c.nombre.unique in (None, False)
    unique_constraints = [
        c for c in table.constraints if c.__class__.__name__ == "UniqueConstraint"
    ]
    assert unique_constraints == []


def test_create_exige_ambos_campos():
    assert AutorCreate(nombre=" Borges ", nacionalidad="Argentina").nombre == "Borges"
    with pytest.raises(ValidationError):
        AutorCreate(nombre="Borges")
    with pytest.raises(ValidationError):
        AutorCreate(nombre="  ", nacionalidad="Argentina")


@pytest.mark.parametrize("payload", [{"nombre": None}, {"nacionalidad": None}, {"nombre": "  "}])
def test_update_rechaza_null_y_vacio(payload):
    with pytest.raises(ValidationError):
        AutorUpdate(**payload)


def test_update_parcial():
    assert AutorUpdate(nombre="X").model_dump(exclude_unset=True) == {"nombre": "X"}


async def _crear(client, nombre="Jorge Luis Borges", nacionalidad="Argentina"):
    return await client.post("/autores/", json={"nombre": nombre, "nacionalidad": nacionalidad})


@pytest.mark.asyncio
async def test_post_alta_exitosa(client):
    r = await _crear(client)
    assert r.status_code == 201
    body = r.json()
    assert isinstance(body["id"], int)
    assert (body["nombre"], body["nacionalidad"]) == ("Jorge Luis Borges", "Argentina")


@pytest.mark.asyncio
async def test_post_nombre_repetido_permitido(client):
    a = await _crear(client)
    b = await _crear(client)
    assert a.status_code == b.status_code == 201
    assert a.json()["id"] != b.json()["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload", [{"nombre": "X"}, {"nombre": "  ", "nacionalidad": "AR"}]
)
async def test_post_invalido_422(client, payload):
    assert (await client.post("/autores/", json=payload)).status_code == 422
    assert (await client.get("/autores/")).json() == []


@pytest.mark.asyncio
async def test_list_orden_y_paginacion(client):
    for n in ("A", "B", "C"):
        await _crear(client, n)
    assert [a["nombre"] for a in (await client.get("/autores/")).json()] == ["A", "B", "C"]
    r = await client.get("/autores/?limit=2&offset=2")
    assert [a["nombre"] for a in r.json()] == ["C"]


@pytest.mark.asyncio
@pytest.mark.parametrize("qs", ["limit=0", "limit=101", "offset=-1"])
async def test_list_paginacion_invalida(client, qs):
    assert (await client.get(f"/autores/?{qs}")).status_code == 422


@pytest.mark.asyncio
async def test_get_existente_e_inexistente(client):
    a = (await _crear(client)).json()
    r = await client.get(f"/autores/{a['id']}")
    assert r.status_code == 200
    assert r.json() == a
    r404 = await client.get("/autores/999")
    assert r404.status_code == 404
    assert r404.json()["detail"]


@pytest.mark.asyncio
async def test_patch_parcial_conserva_otros_campos(client):
    a = (await _crear(client)).json()
    r = await client.patch(f"/autores/{a['id']}", json={"nombre": "J. L. Borges"})
    assert r.status_code == 200
    assert r.json() == {"id": a["id"], "nombre": "J. L. Borges", "nacionalidad": "Argentina"}


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{"nacionalidad": None}, {"nombre": "   "}])
async def test_patch_invalido_422(client, payload):
    a = (await _crear(client)).json()
    assert (await client.patch(f"/autores/{a['id']}", json=payload)).status_code == 422
    assert (await client.get(f"/autores/{a['id']}")).json() == a


@pytest.mark.asyncio
async def test_patch_inexistente_404(client):
    r = await client.patch("/autores/999", json={"nombre": "X"})
    assert r.status_code == 404
    assert r.json()["detail"]
