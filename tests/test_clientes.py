import pytest
from pydantic import ValidationError
from sqlmodel import SQLModel

from app.modules.clientes.models import Cliente, PerfilCliente
from app.modules.clientes.schemas import ClienteCreate, ClienteUpdate, PerfilCreate

FORBIDDEN_TERMS = ("UNIQUE", "IntegrityError", "duplicate key", "constraint", "perfil_cliente", "foreign key")


def _sin_internos(detail: str) -> None:
    assert detail
    for term in FORBIDDEN_TERMS:
        assert term.lower() not in detail.lower(), term


# --- Esquema ---
def test_tabla_cliente():
    t = SQLModel.metadata.tables["cliente"]
    assert set(t.c.keys()) == {"id", "nombre", "email"}
    assert t.c.email.unique is True
    assert t.c.nombre.nullable is False and t.c.email.nullable is False


def test_tabla_perfil_cliente_uno_a_uno():
    t = SQLModel.metadata.tables["perfil_cliente"]
    assert set(t.c.keys()) == {"id", "cliente_id", "telefono", "direccion"}
    assert t.c.cliente_id.unique is True
    assert t.c.cliente_id.index is True
    assert t.c.cliente_id.nullable is False
    assert {fk.target_fullname for fk in t.foreign_keys} == {"cliente.id"}


def test_navegacion_perfil_es_objeto_unico():
    assert Cliente.perfil.property.uselist is False
    assert Cliente.perfil.property.back_populates == "cliente"
    assert PerfilCliente.cliente.property.back_populates == "perfil"
    assert Cliente.perfil.property.lazy == PerfilCliente.cliente.property.lazy == "raise"


# --- DTOs ---
def test_create_normaliza_email_y_sin_id():
    dto = ClienteCreate(nombre=" Tomás ", email=" Tomas@Example.COM ", id=3)
    assert (dto.nombre, dto.email) == ("Tomás", "tomas@example.com")
    assert not hasattr(dto, "id")


@pytest.mark.parametrize(
    "payload",
    [{"nombre": "A"}, {"nombre": " ", "email": "a@b.co"}, {"nombre": "A", "email": "sin-arroba"},
     {"nombre": "A", "email": "a@b"}],
)
def test_create_invalido(payload):
    with pytest.raises(ValidationError):
        ClienteCreate(**payload)


def test_update_y_perfil():
    assert ClienteUpdate(nombre="X").model_dump(exclude_unset=True) == {"nombre": "X"}
    with pytest.raises(ValidationError):
        ClienteUpdate(email=None)
    with pytest.raises(ValidationError):
        PerfilCreate(telefono="1")


# --- HTTP ---
async def _crear(client, nombre="Tomás Ríos", email="tomas@example.com"):
    return await client.post("/clientes/", json={"nombre": nombre, "email": email})


PERFIL = {"telefono": "11-5555-0000", "direccion": "Av. Siempre Viva 742"}


@pytest.mark.asyncio
async def test_post_alta(client):
    r = await _crear(client, email="Tomas@Example.com")
    assert r.status_code == 201
    body = r.json()
    assert isinstance(body["id"], int)
    assert body["email"] == "tomas@example.com"
    assert body["perfil"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{"nombre": "A"}, {"nombre": "A", "email": "nada"}])
async def test_post_invalido_422(client, payload):
    assert (await client.post("/clientes/", json=payload)).status_code == 422


@pytest.mark.asyncio
async def test_post_email_repetido_409(client):
    await _crear(client)
    r = await _crear(client, nombre="Otro", email="TOMAS@example.com")
    assert r.status_code == 409
    _sin_internos(r.json()["detail"])
    assert len((await client.get("/clientes/")).json()) == 1
    assert (await _crear(client, email="otro@example.com")).status_code == 201


@pytest.mark.asyncio
async def test_get_y_listado_con_perfil(client):
    a = (await _crear(client)).json()
    await _crear(client, nombre="Ana", email="ana@example.com")
    await client.post(f"/clientes/{a['id']}/perfil", json=PERFIL)

    r = await client.get(f"/clientes/{a['id']}")
    assert r.status_code == 200
    perfil = r.json()["perfil"]
    assert isinstance(perfil, dict)
    assert perfil["cliente_id"] == a["id"] and perfil["telefono"] == PERFIL["telefono"]

    lista = (await client.get("/clientes/")).json()
    assert [c["email"] for c in lista] == ["tomas@example.com", "ana@example.com"]
    assert lista[0]["perfil"]["direccion"] == PERFIL["direccion"]
    assert lista[1]["perfil"] is None
    assert len((await client.get("/clientes/?limit=1&offset=1")).json()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("ruta,codigo", [("/clientes/999", 404), ("/clientes/abc", 422),
                                         ("/clientes/?limit=101", 422), ("/clientes/?offset=-1", 422)])
async def test_get_errores(client, ruta, codigo):
    assert (await client.get(ruta)).status_code == codigo


@pytest.mark.asyncio
async def test_patch_parcial(client):
    c = (await _crear(client)).json()
    r = await client.patch(f"/clientes/{c['id']}", json={"nombre": "Tomás R."})
    assert r.status_code == 200
    assert r.json() == {**c, "nombre": "Tomás R."}
    await client.post(f"/clientes/{c['id']}/perfil", json=PERFIL)
    r = await client.patch(f"/clientes/{c['id']}", json={})
    assert r.status_code == 200 and r.json()["perfil"]["telefono"] == PERFIL["telefono"]


@pytest.mark.asyncio
async def test_patch_email_de_otro_409(client):
    await _crear(client)
    b = (await _crear(client, nombre="Ana", email="ana@example.com")).json()
    r = await client.patch(f"/clientes/{b['id']}", json={"email": "tomas@example.com"})
    assert r.status_code == 409
    _sin_internos(r.json()["detail"])
    assert (await client.get(f"/clientes/{b['id']}")).json()["email"] == "ana@example.com"


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{"email": None}, {"nombre": ""}, {"email": "x"}])
async def test_patch_invalido_422(client, payload):
    c = (await _crear(client)).json()
    assert (await client.patch(f"/clientes/{c['id']}", json=payload)).status_code == 422


@pytest.mark.asyncio
async def test_patch_inexistente_404(client):
    assert (await client.patch("/clientes/999", json={"nombre": "X"})).status_code == 404


@pytest.mark.asyncio
async def test_perfil_alta_y_segundo_perfil_409(client):
    c = (await _crear(client)).json()
    r = await client.post(f"/clientes/{c['id']}/perfil", json=PERFIL)
    assert r.status_code == 201
    assert r.json() == {"id": r.json()["id"], "cliente_id": c["id"], **PERFIL}

    r2 = await client.post(f"/clientes/{c['id']}/perfil", json={"telefono": "1", "direccion": "Otra"})
    assert r2.status_code == 409
    _sin_internos(r2.json()["detail"])
    assert (await client.get(f"/clientes/{c['id']}")).json()["perfil"]["direccion"] == PERFIL["direccion"]


@pytest.mark.asyncio
async def test_perfil_cliente_inexistente_404_y_invalido_422(client):
    r = await client.post("/clientes/999/perfil", json=PERFIL)
    assert r.status_code == 404
    _sin_internos(r.json()["detail"])
    c = (await _crear(client)).json()
    assert (await client.post(f"/clientes/{c['id']}/perfil", json={"telefono": "1"})).status_code == 422
