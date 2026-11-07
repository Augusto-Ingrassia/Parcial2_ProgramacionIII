from sqlmodel import SQLModel

from app.main import app


def test_tablas_registradas_en_metadata():
    assert {"editorial", "genero", "autor"} <= set(SQLModel.metadata.tables)


def test_rutas_openapi_sin_delete():
    paths = app.openapi()["paths"]
    for ruta in (
        "/editoriales/", "/editoriales/{editorial_id}",
        "/generos/", "/generos/{genero_id}",
        "/autores/", "/autores/{autor_id}",
    ):
        assert ruta in paths
    for ruta, ops in paths.items():
        assert "delete" not in ops, ruta
