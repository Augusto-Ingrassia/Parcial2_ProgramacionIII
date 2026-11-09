from sqlmodel import SQLModel

from app.main import app


def test_tablas_registradas_en_metadata():
    assert {
        "editorial", "genero", "autor", "libro", "libro_autor",
        "cliente", "perfil_cliente", "venta", "renglon_venta",
    } <= set(SQLModel.metadata.tables)


def test_toda_fk_tiene_indice():
    for tabla in SQLModel.metadata.tables.values():
        for fk in tabla.foreign_keys:
            assert fk.parent.index is True, f"{tabla.name}.{fk.parent.name}"


def test_rutas_openapi_sin_delete():
    paths = app.openapi()["paths"]
    for ruta in (
        "/editoriales/", "/editoriales/{editorial_id}", "/editoriales/{editorial_id}/libros",
        "/generos/", "/generos/{genero_id}", "/generos/{genero_id}/libros",
        "/autores/", "/autores/{autor_id}", "/autores/{autor_id}/libros",
        "/libros/", "/libros/{libro_id}",
        "/clientes/", "/clientes/{cliente_id}", "/clientes/{cliente_id}/perfil",
        "/clientes/{cliente_id}/ventas",
        "/ventas/", "/ventas/{venta_id}",
    ):
        assert ruta in paths, ruta
    for ruta, ops in paths.items():
        assert "delete" not in ops, ruta


def test_ventas_sin_put_ni_patch():
    paths = app.openapi()["paths"]
    for ruta in ("/ventas/", "/ventas/{venta_id}"):
        assert not {"put", "patch", "delete"} & set(paths[ruta])
