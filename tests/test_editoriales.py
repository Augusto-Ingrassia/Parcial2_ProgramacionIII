import pytest
from pydantic import ValidationError
from sqlmodel import SQLModel

from app.modules.editoriales.models import Editorial  # noqa: F401
from app.modules.editoriales.schemas import EditorialCreate, EditorialUpdate


def test_editorial_table_definition():
    table = SQLModel.metadata.tables["editorial"]
    assert set(table.c.keys()) == {"id", "nombre", "pais"}
    assert table.c.nombre.unique is True
    assert table.c.nombre.nullable is False
    assert table.c.pais.nullable is False
    assert table.c.pais.unique in (None, False)


def test_create_requires_non_empty_fields_and_ignores_id():
    dto = EditorialCreate(nombre=" Planeta ", pais="España", id=99)
    assert dto.nombre == "Planeta"
    assert not hasattr(dto, "id")
    with pytest.raises(ValidationError):
        EditorialCreate(nombre="Planeta")
    with pytest.raises(ValidationError):
        EditorialCreate(nombre="   ", pais="España")


def test_update_accepts_empty_and_partial():
    assert EditorialUpdate().model_dump(exclude_unset=True) == {}
    assert EditorialUpdate(pais="Chile").model_dump(exclude_unset=True) == {"pais": "Chile"}


@pytest.mark.parametrize("payload", [{"nombre": None}, {"pais": None}, {"pais": ""}])
def test_update_rejects_null_and_empty(payload):
    with pytest.raises(ValidationError):
        EditorialUpdate(**payload)


FORBIDDEN_TERMS = ("UNIQUE", "IntegrityError", "duplicate key", "constraint", "editorial_nombre_key")


async def _crear(client, nombre="Planeta", pais="España"):
    return await client.post("/editoriales/", json={"nombre": nombre, "pais": pais})


# --- POST ---
@pytest.mark.asyncio
async def test_post_alta_exitosa(client):
    r = await _crear(client)
    assert r.status_code == 201
    body = r.json()
    assert isinstance(body["id"], int)
    assert (body["nombre"], body["pais"]) == ("Planeta", "España")


@pytest.mark.asyncio
async def test_post_ignora_id_del_cliente(client):
    r = await client.post("/editoriales/", json={"id": 500, "nombre": "A", "pais": "X"})
    assert r.status_code == 201
    assert r.json()["id"] != 500


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [{"nombre": "Planeta"}, {"nombre": "   ", "pais": "ES"}, {"nombre": "", "pais": "ES"}],
)
async def test_post_invalido_422_y_no_persiste(client, payload):
    r = await client.post("/editoriales/", json=payload)
    assert r.status_code == 422
    assert (await client.get("/editoriales/")).json() == []


@pytest.mark.asyncio
async def test_post_duplicado_409_y_api_sigue_operativa(client):
    await _crear(client)
    r = await _crear(client, pais="Argentina")
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail
    for term in FORBIDDEN_TERMS:
        assert term.lower() not in detail.lower()
    assert len((await client.get("/editoriales/")).json()) == 1
    assert (await _crear(client, nombre="Anagrama")).status_code == 201


@pytest.mark.asyncio
async def test_post_nombre_es_sensible_a_mayusculas(client):
    assert (await _crear(client, nombre="Planeta")).status_code == 201
    assert (await _crear(client, nombre="planeta")).status_code == 201


# --- GET list ---
@pytest.mark.asyncio
async def test_list_default_20_orden_por_id(client):
    for i in range(25):
        await _crear(client, nombre=f"E{i}")
    r = await client.get("/editoriales/")
    assert r.status_code == 200
    ids = [e["id"] for e in r.json()]
    assert len(ids) == 20
    assert ids == sorted(ids)
    assert ids[0] == min(ids)


@pytest.mark.asyncio
async def test_list_limit_offset(client):
    for i in range(25):
        await _crear(client, nombre=f"E{i}")
    r = await client.get("/editoriales/?limit=10&offset=20")
    assert r.status_code == 200
    assert [e["nombre"] for e in r.json()] == [f"E{i}" for i in range(20, 25)]


@pytest.mark.asyncio
async def test_list_vacio(client):
    r = await client.get("/editoriales/")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("qs", ["limit=0", "limit=101", "offset=-1"])
async def test_list_paginacion_invalida(client, qs):
    assert (await client.get(f"/editoriales/?{qs}")).status_code == 422


# --- GET by id ---
@pytest.mark.asyncio
async def test_get_por_id_existente(client):
    creada = (await _crear(client)).json()
    r = await client.get(f"/editoriales/{creada['id']}")
    assert r.status_code == 200
    assert r.json() == creada


@pytest.mark.asyncio
@pytest.mark.parametrize("id_", [999, 0, -1])
async def test_get_por_id_inexistente(client, id_):
    r = await client.get(f"/editoriales/{id_}")
    assert r.status_code == 404
    assert r.json()["detail"]


# --- PATCH ---
@pytest.mark.asyncio
async def test_patch_un_solo_campo(client):
    e = (await _crear(client)).json()
    r = await client.patch(f"/editoriales/{e['id']}", json={"pais": "Argentina"})
    assert r.status_code == 200
    assert r.json() == {"id": e["id"], "nombre": "Planeta", "pais": "Argentina"}


@pytest.mark.asyncio
async def test_patch_cuerpo_vacio_sin_cambios(client):
    e = (await _crear(client)).json()
    r = await client.patch(f"/editoriales/{e['id']}", json={})
    assert r.status_code == 200
    assert r.json() == e


@pytest.mark.asyncio
async def test_patch_reenvio_del_propio_nombre(client):
    e = (await _crear(client)).json()
    r = await client.patch(f"/editoriales/{e['id']}", json={"nombre": "Planeta"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_patch_colision_409_conserva_nombre(client):
    await _crear(client, nombre="Planeta")
    b = (await _crear(client, nombre="Anagrama")).json()
    r = await client.patch(f"/editoriales/{b['id']}", json={"nombre": "Planeta"})
    assert r.status_code == 409
    for term in FORBIDDEN_TERMS:
        assert term.lower() not in r.json()["detail"].lower()
    assert (await client.get(f"/editoriales/{b['id']}")).json()["nombre"] == "Anagrama"


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{"nombre": None}, {"pais": ""}])
async def test_patch_null_o_vacio_422(client, payload):
    e = (await _crear(client)).json()
    assert (await client.patch(f"/editoriales/{e['id']}", json=payload)).status_code == 422
    assert (await client.get(f"/editoriales/{e['id']}")).json() == e


@pytest.mark.asyncio
async def test_patch_inexistente_404(client):
    r = await client.patch("/editoriales/999", json={"pais": "Chile"})
    assert r.status_code == 404
    assert r.json()["detail"]
