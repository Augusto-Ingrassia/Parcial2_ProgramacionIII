import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, insert
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel

from app.modules.libros.models import Libro, LibroAutor  # noqa: F401
from app.modules.libros.schemas import LibroCreate, LibroUpdate

FORBIDDEN_TERMS = (
    "UNIQUE", "IntegrityError", "duplicate key", "constraint", "foreign key",
    "libro_isbn", "libro_autor", "sqlite", "asyncpg",
)


def _sin_internos(detail: str) -> None:
    assert detail
    for term in FORBIDDEN_TERMS:
        assert term.lower() not in detail.lower(), term


def _checks(table) -> set[str]:
    return {str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)}


# --- Esquema ---
def test_tabla_libro():
    t = SQLModel.metadata.tables["libro"]
    assert set(t.c.keys()) == {"id", "isbn", "titulo", "precio", "stock", "editorial_id", "genero_id"}
    assert t.c.isbn.unique is True
    assert (t.c.precio.type.precision, t.c.precio.type.scale) == (10, 2)
    assert t.c.editorial_id.nullable is False and t.c.editorial_id.index is True
    assert t.c.genero_id.nullable is True and t.c.genero_id.index is True
    assert {fk.target_fullname for fk in t.foreign_keys} == {"editorial.id", "genero.id"}
    assert _checks(t) == {"precio > 0", "stock >= 0"}


def test_tabla_libro_autor_es_objeto_de_asociacion():
    t = SQLModel.metadata.tables["libro_autor"]
    assert set(t.c.keys()) == {"libro_id", "autor_id", "rol", "orden"}
    assert {c.name for c in t.primary_key.columns} == {"libro_id", "autor_id"}
    assert t.c.libro_id.index is True and t.c.autor_id.index is True
    assert {fk.target_fullname for fk in t.foreign_keys} == {"libro.id", "autor.id"}
    checks = _checks(t)
    assert "orden >= 1" in checks
    assert any("rol IN" in c and "ilustrador" in c for c in checks)


def test_navegacion_en_los_dos_extremos():
    from app.modules.autores.models import Autor
    from app.modules.editoriales.models import Editorial
    from app.modules.generos.models import Genero

    assert Libro.editorial.property.back_populates == "libros"
    assert Editorial.libros.property.back_populates == "editorial"
    assert Genero.libros.property.back_populates == "genero"
    assert Libro.autorias.property.back_populates == "libro"
    assert LibroAutor.autor.property.back_populates == "autorias"
    assert Autor.autorias.property.back_populates == "autor"
    for rel in (Libro.editorial, Libro.genero, Libro.autorias, LibroAutor.autor, Editorial.libros):
        assert rel.property.lazy == "raise"


# --- DTOs ---
BASE = {
    "isbn": "978-1", "titulo": "Rayuela", "precio": "25000.00", "stock": 3,
    "editorial_id": 1, "autores": [{"autor_id": 1, "rol": "autor", "orden": 1}],
}


def test_create_valido_y_sin_id():
    dto = LibroCreate(**BASE, id=9)
    assert not hasattr(dto, "id")
    assert dto.genero_id is None
    assert str(dto.precio) == "25000.00"


@pytest.mark.parametrize(
    "cambio",
    [
        {"precio": "0"}, {"precio": "-1"}, {"precio": "1.234"}, {"stock": -1},
        {"isbn": "  "}, {"autores": []},
        {"autores": [{"autor_id": 1, "rol": "editor", "orden": 1}]},
        {"autores": [{"autor_id": 1, "rol": "autor", "orden": 0}]},
        {"autores": [{"autor_id": 1, "rol": "autor", "orden": 1},
                     {"autor_id": 1, "rol": "coautor", "orden": 2}]},
    ],
)
def test_create_invalido(cambio):
    with pytest.raises(ValidationError):
        LibroCreate(**{**BASE, **cambio})


def test_update_parcial_y_nulls():
    assert LibroUpdate(stock=2).model_dump(exclude_unset=True) == {"stock": 2}
    assert LibroUpdate(genero_id=None).model_dump(exclude_unset=True) == {"genero_id": None}
    for campo in ("titulo", "isbn", "precio", "stock", "editorial_id"):
        with pytest.raises(ValidationError):
            LibroUpdate(**{campo: None})


# --- Helpers HTTP ---
async def _catalogo(client):
    """Crea editorial 1, géneros 1 y 2 y autores 1..4."""
    ed = (await client.post("/editoriales/", json={"nombre": "Sudamericana", "pais": "AR"})).json()
    g1 = (await client.post("/generos/", json={"nombre": "Novela"})).json()
    g2 = (await client.post("/generos/", json={"nombre": "Cuento"})).json()
    autores = [
        (await client.post("/autores/", json={"nombre": n, "nacionalidad": "AR"})).json()
        for n in ("Cortázar", "Borges", "Bioy Casares", "Silvina Ocampo")
    ]
    return ed, g1, g2, autores


def _libro(ed, autores, **extra):
    body = {
        "isbn": "978-950-00-0006-6", "titulo": "Los que aman, odian", "precio": "21000.00",
        "stock": 4, "editorial_id": ed["id"],
        "autores": [
            {"autor_id": a["id"], "rol": "coautor", "orden": i + 1} for i, a in enumerate(autores)
        ],
    }
    body.update(extra)
    return body


# --- POST ---
@pytest.mark.asyncio
async def test_post_alta_con_dos_coautores(client):
    ed, g1, _, autores = await _catalogo(client)
    body = _libro(ed, [autores[3], autores[2]], genero_id=g1["id"])
    r = await client.post("/libros/", json=body)
    assert r.status_code == 201, r.text
    libro = r.json()
    assert isinstance(libro["id"], int)
    assert libro["precio"] == "21000.00"
    assert libro["editorial"] == ed
    assert libro["genero"] == g1
    assert [(a["autor_id"], a["nombre"], a["rol"], a["orden"]) for a in libro["autores"]] == [
        (autores[3]["id"], "Silvina Ocampo", "coautor", 1),
        (autores[2]["id"], "Bioy Casares", "coautor", 2),
    ]


@pytest.mark.asyncio
async def test_post_sin_genero(client):
    ed, _, _, autores = await _catalogo(client)
    r = await client.post("/libros/", json=_libro(ed, autores[:1]))
    assert r.status_code == 201
    assert r.json()["genero"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("campo", ["editorial_id", "genero_id", "autor_id"])
async def test_post_fk_inexistente_409_y_no_persiste(client, campo):
    ed, g1, _, autores = await _catalogo(client)
    body = _libro(ed, autores[:2], genero_id=g1["id"])
    if campo == "autor_id":
        body["autores"][1]["autor_id"] = 999
    else:
        body[campo] = 999
    r = await client.post("/libros/", json=body)
    assert r.status_code == 409
    _sin_internos(r.json()["detail"])
    assert (await client.get("/libros/")).json() == []
    assert (await client.get(f"/autores/{autores[0]['id']}/libros")).json() == []


@pytest.mark.asyncio
async def test_post_sin_select_previo(client, contar_consultas):
    ed, _, _, autores = await _catalogo(client)
    contar_consultas.clear()
    r = await client.post("/libros/", json=_libro(ed, autores[:2], editorial_id=999))
    assert r.status_code == 409
    # Ninguna lectura antes del INSERT: la FK es la que verifica.
    primera_escritura = next(i for i, s in enumerate(contar_consultas) if s.lstrip().upper().startswith("INSERT"))
    assert not any(s.lstrip().upper().startswith("SELECT") for s in contar_consultas[:primera_escritura])


@pytest.mark.asyncio
async def test_post_isbn_repetido_409(client):
    ed, _, _, autores = await _catalogo(client)
    assert (await client.post("/libros/", json=_libro(ed, autores[:1]))).status_code == 201
    r = await client.post("/libros/", json=_libro(ed, autores[1:2], titulo="Otro"))
    assert r.status_code == 409
    assert "ISBN" in r.json()["detail"]
    _sin_internos(r.json()["detail"].replace("ISBN", ""))
    assert len((await client.get("/libros/")).json()) == 1
    # La sesión queda sana tras el conflicto.
    assert (await client.post("/libros/", json=_libro(ed, autores[:1], isbn="978-2"))).status_code == 201


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cambio",
    [{"precio": "0"}, {"stock": -1}, {"autores": []},
     {"autores": [{"autor_id": 1, "rol": "prologuista", "orden": 1}]},
     {"autores": [{"autor_id": 1, "rol": "autor", "orden": 0}]}],
)
async def test_post_invalido_422(client, cambio):
    ed, _, _, autores = await _catalogo(client)
    r = await client.post("/libros/", json={**_libro(ed, autores[:1]), **cambio})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_check_en_la_base_aunque_se_saltee_el_dto(db_engine):
    async with db_engine.begin() as conn:
        await conn.execute(insert(SQLModel.metadata.tables["editorial"]).values(id=1, nombre="E", pais="P"))
    with pytest.raises(IntegrityError):
        async with db_engine.begin() as conn:
            await conn.execute(
                insert(Libro.__table__).values(isbn="x", titulo="t", precio=0, stock=1, editorial_id=1)
            )


# --- GET list ---
async def _tres_libros(client):
    ed, g1, g2, autores = await _catalogo(client)
    datos = [("978-1", "Rayuela", g1), ("978-2", "Ficciones", g2), ("978-3", "Bestiario", g2)]
    for isbn, titulo, g in datos:
        r = await client.post(
            "/libros/", json=_libro(ed, autores[:1], isbn=isbn, titulo=titulo, genero_id=g["id"])
        )
        assert r.status_code == 201
    return ed, g1, g2, autores


@pytest.mark.asyncio
async def test_list_incluye_editorial_y_genero(client):
    ed, g1, _, _ = await _tres_libros(client)
    r = await client.get("/libros/")
    assert r.status_code == 200
    libros = r.json()
    assert [l["titulo"] for l in libros] == ["Rayuela", "Ficciones", "Bestiario"]
    assert libros[0]["editorial"] == ed and libros[0]["genero"] == g1
    assert "autores" not in libros[0]


@pytest.mark.asyncio
async def test_list_filtro_titulo_case_insensitive(client):
    await _tres_libros(client)
    r = await client.get("/libros/", params={"titulo": "RAYU"})
    assert [l["titulo"] for l in r.json()] == ["Rayuela"]
    r = await client.get("/libros/", params={"titulo": "ci"})
    assert [l["titulo"] for l in r.json()] == ["Ficciones"]


@pytest.mark.asyncio
@pytest.mark.parametrize("texto", ["' OR '1'='1", "%", "_"])
async def test_list_titulo_es_parametro_ligado(client, texto):
    await _tres_libros(client)
    r = await client.get("/libros/", params={"titulo": texto})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_filtro_genero_y_paginacion(client):
    _, _, g2, _ = await _tres_libros(client)
    r = await client.get("/libros/", params={"genero_id": g2["id"]})
    assert [l["titulo"] for l in r.json()] == ["Ficciones", "Bestiario"]
    r = await client.get("/libros/?limit=1&offset=1")
    assert [l["titulo"] for l in r.json()] == ["Ficciones"]


@pytest.mark.asyncio
@pytest.mark.parametrize("qs", ["limit=0", "limit=101", "offset=-1", "genero_id=abc"])
async def test_list_parametros_invalidos(client, qs):
    assert (await client.get(f"/libros/?{qs}")).status_code == 422


# --- GET detail ---
@pytest.mark.asyncio
async def test_detalle_y_404_y_422(client):
    ed, _, _, autores = await _catalogo(client)
    creado = (await client.post("/libros/", json=_libro(ed, autores[:2]))).json()
    r = await client.get(f"/libros/{creado['id']}")
    assert r.status_code == 200
    assert r.json() == creado
    r = await client.get("/libros/999")
    assert r.status_code == 404 and r.json()["detail"]
    assert (await client.get("/libros/abc")).status_code == 422


@pytest.mark.asyncio
async def test_detalle_cantidad_fija_de_consultas(client, contar_consultas):
    ed, _, _, autores = await _catalogo(client)
    uno = (await client.post("/libros/", json=_libro(ed, autores[:1], isbn="A"))).json()
    tres = (await client.post("/libros/", json=_libro(ed, autores[:3], isbn="B"))).json()

    contar_consultas.clear()
    await client.get(f"/libros/{uno['id']}")
    con_uno = len(contar_consultas)
    contar_consultas.clear()
    r = await client.get(f"/libros/{tres['id']}")
    assert len(r.json()["autores"]) == 3
    assert len(contar_consultas) == con_uno == 2


# --- PATCH ---
@pytest.mark.asyncio
async def test_patch_parcial(client):
    ed, g1, _, autores = await _catalogo(client)
    libro = (await client.post("/libros/", json=_libro(ed, autores[:1], genero_id=g1["id"]))).json()
    r = await client.patch(f"/libros/{libro['id']}", json={"precio": "30000.00", "stock": 10})
    assert r.status_code == 200
    assert r.json() == {**libro, "precio": "30000.00", "stock": 10}
    r = await client.patch(f"/libros/{libro['id']}", json={"genero_id": None})
    assert r.status_code == 200 and r.json()["genero"] is None
    r = await client.patch(f"/libros/{libro['id']}", json={})
    assert r.status_code == 200 and r.json()["titulo"] == libro["titulo"]


@pytest.mark.asyncio
async def test_patch_conflictos_409(client):
    ed, _, _, autores = await _catalogo(client)
    a = (await client.post("/libros/", json=_libro(ed, autores[:1], isbn="A"))).json()
    b = (await client.post("/libros/", json=_libro(ed, autores[:1], isbn="B"))).json()
    r = await client.patch(f"/libros/{b['id']}", json={"isbn": a["isbn"]})
    assert r.status_code == 409
    assert (await client.get(f"/libros/{b['id']}")).json()["isbn"] == "B"
    r = await client.patch(f"/libros/{b['id']}", json={"editorial_id": 999})
    assert r.status_code == 409
    _sin_internos(r.json()["detail"])


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{"precio": "-1"}, {"stock": -5}, {"titulo": None}])
async def test_patch_invalido_422(client, payload):
    ed, _, _, autores = await _catalogo(client)
    libro = (await client.post("/libros/", json=_libro(ed, autores[:1]))).json()
    assert (await client.patch(f"/libros/{libro['id']}", json=payload)).status_code == 422


@pytest.mark.asyncio
async def test_patch_inexistente_404(client):
    assert (await client.patch("/libros/999", json={"stock": 1})).status_code == 404


# --- Navegación cruzada ---
@pytest.mark.asyncio
async def test_libros_de_editorial_y_genero(client):
    ed, g1, g2, _ = await _tres_libros(client)
    r = await client.get(f"/editoriales/{ed['id']}/libros")
    assert r.status_code == 200 and len(r.json()) == 3
    r = await client.get(f"/editoriales/{ed['id']}/libros?limit=1")
    assert len(r.json()) == 1
    r = await client.get(f"/generos/{g2['id']}/libros")
    assert [l["titulo"] for l in r.json()] == ["Ficciones", "Bestiario"]
    otra = (await client.post("/editoriales/", json={"nombre": "Vacía", "pais": "AR"})).json()
    assert (await client.get(f"/editoriales/{otra['id']}/libros")).json() == []
    assert (await client.get("/editoriales/999/libros")).status_code == 404
    assert (await client.get("/generos/999/libros")).status_code == 404


@pytest.mark.asyncio
async def test_libros_de_autor_con_rol_y_orden(client):
    ed, _, _, autores = await _catalogo(client)
    a, b = autores[0], autores[1]
    await client.post("/libros/", json={**_libro(ed, [], isbn="X", titulo="Uno"),
                                        "autores": [{"autor_id": a["id"], "rol": "coautor", "orden": 1}]})
    await client.post("/libros/", json={**_libro(ed, [], isbn="Y", titulo="Dos"),
                                        "autores": [{"autor_id": b["id"], "rol": "autor", "orden": 1},
                                                    {"autor_id": a["id"], "rol": "traductor", "orden": 2}]})
    r = await client.get(f"/autores/{a['id']}/libros")
    assert r.status_code == 200
    assert [(l["titulo"], l["rol"], l["orden"]) for l in r.json()] == [
        ("Uno", "coautor", 1), ("Dos", "traductor", 2),
    ]
    assert {"id", "isbn", "precio", "stock"} <= set(r.json()[0])
    assert (await client.get("/autores/999/libros")).status_code == 404
