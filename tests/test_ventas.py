import logging
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, insert
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel

from app.modules.clientes.models import Cliente
from app.modules.libros.models import Libro
from app.modules.ventas import service
from app.modules.ventas.models import RenglonVenta, Venta
from app.modules.ventas.schemas import VentaCreate

FORBIDDEN_TERMS = ("UNIQUE", "IntegrityError", "constraint", "foreign key", "renglon_venta", "venta_cliente")


def _sin_internos(detail: str) -> None:
    assert detail
    for term in FORBIDDEN_TERMS:
        assert term.lower() not in detail.lower(), term


def _checks(table) -> set[str]:
    return {str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)}


# --- Esquema ---
def test_tabla_venta():
    t = SQLModel.metadata.tables["venta"]
    assert set(t.c.keys()) == {"id", "cliente_id", "fecha", "total"}
    assert t.c.fecha.type.timezone is True and t.c.fecha.nullable is False
    assert (t.c.total.type.precision, t.c.total.type.scale) == (12, 2)
    assert t.c.cliente_id.index is True and t.c.cliente_id.nullable is False
    assert {fk.target_fullname for fk in t.foreign_keys} == {"cliente.id"}
    assert _checks(t) == {"total >= 0"}


def test_tabla_renglon_venta():
    t = SQLModel.metadata.tables["renglon_venta"]
    assert set(t.c.keys()) == {"id", "venta_id", "libro_id", "cantidad", "precio_unitario"}
    assert (t.c.precio_unitario.type.precision, t.c.precio_unitario.type.scale) == (10, 2)
    assert t.c.venta_id.index is True and t.c.libro_id.index is True
    fks = {fk.target_fullname: fk for fk in t.foreign_keys}
    assert set(fks) == {"venta.id", "libro.id"}
    assert fks["venta.id"].ondelete == "CASCADE"
    assert _checks(t) == {"cantidad > 0", "precio_unitario > 0"}


def test_navegacion_en_los_dos_extremos():
    assert Venta.cliente.property.back_populates == "ventas"
    assert Cliente.ventas.property.back_populates == "cliente"
    assert Venta.renglones.property.back_populates == "venta"
    assert RenglonVenta.venta.property.back_populates == "renglones"
    assert RenglonVenta.libro.property.back_populates == "renglones"
    assert Libro.renglones.property.back_populates == "libro"
    assert "delete-orphan" in Venta.renglones.property.cascade
    for rel in (Venta.cliente, Venta.renglones, RenglonVenta.libro, Cliente.ventas, Libro.renglones):
        assert rel.property.lazy == "raise"


# --- DTOs ---
def test_create_no_acepta_precio_total_ni_fecha():
    dto = VentaCreate(
        cliente_id=1, total="1", fecha="2020-01-01",
        renglones=[{"libro_id": 1, "cantidad": 2, "precio_unitario": "1"}],
    )
    assert set(dto.model_dump()) == {"cliente_id", "renglones"}
    assert dto.model_dump()["renglones"] == [{"libro_id": 1, "cantidad": 2}]


@pytest.mark.parametrize(
    "renglones",
    [[], [{"libro_id": 1, "cantidad": 0}], [{"libro_id": 1, "cantidad": -1}],
     [{"libro_id": 1, "cantidad": 1}, {"libro_id": 1, "cantidad": 2}]],
)
def test_create_invalido(renglones):
    with pytest.raises(ValidationError):
        VentaCreate(cliente_id=1, renglones=renglones)


# --- Helpers HTTP ---
async def _datos(client):
    """Cliente 1 (Tomás) y 2 (Ana); libros Rayuela 25000 y Respiración artificial 27000."""
    ed = (await client.post("/editoriales/", json={"nombre": "Sudamericana", "pais": "AR"})).json()
    au = (await client.post("/autores/", json={"nombre": "Cortázar", "nacionalidad": "AR"})).json()
    libros = []
    for isbn, titulo, precio in [("1", "Rayuela", "25000.00"), ("4", "Respiración artificial", "27000.00"),
                                 ("5", "Bestiario", "10000.50")]:
        r = await client.post("/libros/", json={
            "isbn": isbn, "titulo": titulo, "precio": precio, "stock": 5, "editorial_id": ed["id"],
            "autores": [{"autor_id": au["id"], "rol": "autor", "orden": 1}],
        })
        libros.append(r.json())
    clientes = [
        (await client.post("/clientes/", json={"nombre": n, "email": e})).json()
        for n, e in [("Tomás Ríos", "tomas@example.com"), ("Ana Gómez", "ana@example.com")]
    ]
    return clientes, libros


@pytest.fixture
def avisos(monkeypatch):
    """Reemplaza la tarea de fondo por un registrador (evita el sleep real)."""
    llamadas = []

    async def _registrar(venta_id, email):
        llamadas.append((venta_id, email))

    monkeypatch.setattr(service, "notificar_comprobante", _registrar)
    return llamadas


def _venta(cliente, *items):
    return {"cliente_id": cliente["id"], "renglones": [{"libro_id": l["id"], "cantidad": c} for l, c in items]}


# --- POST ---
@pytest.mark.asyncio
async def test_post_venta_con_dos_renglones(client, avisos):
    (tomas, _), (rayuela, resp, _) = await _datos(client)
    r = await client.post("/ventas/", json=_venta(tomas, (rayuela, 2), (resp, 1)))
    assert r.status_code == 201, r.text
    v = r.json()
    assert list(v) == ["id", "fecha", "total", "cliente", "renglones"]
    assert v["total"] == "77000.00"
    assert v["cliente"] == {"id": tomas["id"], "nombre": "Tomás Ríos", "email": "tomas@example.com"}
    assert v["renglones"] == [
        {"libro_id": rayuela["id"], "titulo": "Rayuela", "cantidad": 2,
         "precio_unitario": "25000.00", "subtotal": "50000.00"},
        {"libro_id": resp["id"], "titulo": "Respiración artificial", "cantidad": 1,
         "precio_unitario": "27000.00", "subtotal": "27000.00"},
    ]
    assert avisos == [(v["id"], "tomas@example.com")]


@pytest.mark.asyncio
async def test_post_total_con_centavos(client, avisos):
    (tomas, _), (_, _, bestiario) = await _datos(client)
    r = await client.post("/ventas/", json=_venta(tomas, (bestiario, 3)))
    assert r.status_code == 201
    assert Decimal(r.json()["total"]) == Decimal("30001.50")


@pytest.mark.asyncio
async def test_post_ignora_precio_y_total_del_cliente(client, avisos):
    (tomas, _), (rayuela, *_) = await _datos(client)
    body = _venta(tomas, (rayuela, 1))
    body["total"] = "1.00"
    body["fecha"] = "2000-01-01T00:00:00Z"
    body["renglones"][0]["precio_unitario"] = "1.00"
    r = await client.post("/ventas/", json=body)
    assert r.status_code == 201
    assert r.json()["total"] == "25000.00"
    assert r.json()["renglones"][0]["precio_unitario"] == "25000.00"
    assert not r.json()["fecha"].startswith("2000")


@pytest.mark.asyncio
async def test_precio_queda_fijado_aunque_cambie_el_libro(client, avisos):
    (tomas, _), (rayuela, *_) = await _datos(client)
    venta = (await client.post("/ventas/", json=_venta(tomas, (rayuela, 2)))).json()
    assert (await client.patch(f"/libros/{rayuela['id']}", json={"precio": "99999.00"})).status_code == 200
    r = await client.get(f"/ventas/{venta['id']}")
    assert r.json()["total"] == "50000.00"
    assert r.json()["renglones"][0]["precio_unitario"] == "25000.00"


@pytest.mark.asyncio
@pytest.mark.parametrize("caso", ["vacio", "repetido", "cantidad_cero", "sin_cliente"])
async def test_post_invalido_422(client, avisos, caso):
    (tomas, _), (rayuela, *_) = await _datos(client)
    body = {
        "vacio": {"cliente_id": tomas["id"], "renglones": []},
        "repetido": _venta(tomas, (rayuela, 1), (rayuela, 2)),
        "cantidad_cero": _venta(tomas, (rayuela, 0)),
        "sin_cliente": {"renglones": [{"libro_id": rayuela["id"], "cantidad": 1}]},
    }[caso]
    assert (await client.post("/ventas/", json=body)).status_code == 422
    assert (await client.get("/ventas/")).json() == []
    assert avisos == []


@pytest.mark.asyncio
async def test_post_cliente_inexistente_409_atomico(client, avisos):
    _, (rayuela, resp, _) = await _datos(client)
    r = await client.post("/ventas/", json=_venta({"id": 999}, (rayuela, 1), (resp, 1)))
    assert r.status_code == 409
    _sin_internos(r.json()["detail"])
    assert (await client.get("/ventas/")).json() == []
    assert avisos == []


@pytest.mark.asyncio
async def test_post_libro_inexistente_409(client, avisos):
    (tomas, _), (rayuela, *_) = await _datos(client)
    r = await client.post("/ventas/", json=_venta(tomas, (rayuela, 1), ({"id": 999}, 1)))
    assert r.status_code == 409
    _sin_internos(r.json()["detail"])
    assert (await client.get("/ventas/")).json() == []
    assert avisos == []


@pytest.mark.asyncio
async def test_check_en_la_base_aunque_se_saltee_el_dto(db_engine, client):
    (tomas, _), (rayuela, *_) = await _datos(client)
    async with db_engine.begin() as conn:
        venta_id = (await conn.execute(
            insert(Venta.__table__).values(cliente_id=tomas["id"], total=0, fecha=datetime(2026, 1, 1, tzinfo=timezone.utc))
        )).inserted_primary_key[0]
    with pytest.raises(IntegrityError):
        async with db_engine.begin() as conn:
            await conn.execute(insert(RenglonVenta.__table__).values(
                venta_id=venta_id, libro_id=rayuela["id"], cantidad=0, precio_unitario=1))


# --- Background task ---
@pytest.mark.asyncio
async def test_notificar_comprobante_escribe_en_el_log(caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    await service.notificar_comprobante(7, "tomas@example.com")
    assert "venta 7" in caplog.text and "tomas@example.com" in caplog.text


@pytest.mark.asyncio
async def test_post_agenda_la_tarea_real(client, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    (tomas, _), (rayuela, *_) = await _datos(client)
    r = await client.post("/ventas/", json=_venta(tomas, (rayuela, 1)))
    assert r.status_code == 201
    # ASGITransport espera a que terminen las tareas de fondo antes de volver.
    assert f"venta {r.json()['id']} enviado a tomas@example.com" in caplog.text


# --- GET ---
@pytest.mark.asyncio
async def test_get_detalle_404_y_422(client, avisos):
    (tomas, _), (rayuela, resp, _) = await _datos(client)
    creada = (await client.post("/ventas/", json=_venta(tomas, (rayuela, 2), (resp, 1)))).json()
    r = await client.get(f"/ventas/{creada['id']}")
    assert r.status_code == 200
    assert {k: v for k, v in r.json().items() if k != "fecha"} == {
        k: v for k, v in creada.items() if k != "fecha"
    }
    assert (await client.get("/ventas/999")).status_code == 404
    assert (await client.get("/ventas/abc")).status_code == 422


@pytest.mark.asyncio
async def test_detalle_cantidad_fija_de_consultas(client, avisos, contar_consultas):
    (tomas, _), (rayuela, resp, bestiario) = await _datos(client)
    una = (await client.post("/ventas/", json=_venta(tomas, (rayuela, 1)))).json()
    tres = (await client.post("/ventas/", json=_venta(tomas, (rayuela, 1), (resp, 1), (bestiario, 1)))).json()

    contar_consultas.clear()
    await client.get(f"/ventas/{una['id']}")
    con_uno = len(contar_consultas)
    contar_consultas.clear()
    r = await client.get(f"/ventas/{tres['id']}")
    assert len(r.json()["renglones"]) == 3
    assert len(contar_consultas) == con_uno == 2


@pytest.mark.asyncio
async def test_listado_paginado_con_consultas_fijas(client, avisos, contar_consultas):
    (tomas, ana), (rayuela, resp, _) = await _datos(client)
    for c, items in [(tomas, [(rayuela, 1)]), (ana, [(resp, 2)]), (tomas, [(rayuela, 1), (resp, 1)])]:
        assert (await client.post("/ventas/", json=_venta(c, *items))).status_code == 201

    contar_consultas.clear()
    r = await client.get("/ventas/")
    assert len(contar_consultas) == 2
    ventas = r.json()
    assert [v["cliente"]["email"] for v in ventas] == ["tomas@example.com", "ana@example.com", "tomas@example.com"]
    assert len(ventas[2]["renglones"]) == 2

    r = await client.get("/ventas/?limit=2&offset=1")
    assert [v["id"] for v in r.json()] == [ventas[1]["id"], ventas[2]["id"]]
    assert (await client.get("/ventas/?limit=0")).status_code == 422


@pytest.mark.asyncio
async def test_ventas_de_un_cliente(client, avisos):
    (tomas, ana), (rayuela, resp, _) = await _datos(client)
    await client.post("/ventas/", json=_venta(tomas, (rayuela, 1)))
    await client.post("/ventas/", json=_venta(ana, (resp, 1)))
    await client.post("/ventas/", json=_venta(tomas, (resp, 3)))

    r = await client.get(f"/clientes/{tomas['id']}/ventas")
    assert r.status_code == 200
    assert [v["total"] for v in r.json()] == ["25000.00", "81000.00"]
    assert all(v["cliente"]["id"] == tomas["id"] for v in r.json())
    otro = (await client.post("/clientes/", json={"nombre": "Sin", "email": "sin@example.com"})).json()
    assert (await client.get(f"/clientes/{otro['id']}/ventas")).json() == []
    assert (await client.get("/clientes/999/ventas")).status_code == 404


# --- RN-08 ---
@pytest.mark.asyncio
@pytest.mark.parametrize("metodo", ["PATCH", "PUT", "DELETE"])
async def test_ventas_inmutables_405(client, avisos, metodo):
    (tomas, _), (rayuela, *_) = await _datos(client)
    v = (await client.post("/ventas/", json=_venta(tomas, (rayuela, 1)))).json()
    r = await client.request(metodo, f"/ventas/{v['id']}", json={"total": "1.00"})
    assert r.status_code == 405
    assert (await client.get(f"/ventas/{v['id']}")).json()["total"] == "25000.00"
