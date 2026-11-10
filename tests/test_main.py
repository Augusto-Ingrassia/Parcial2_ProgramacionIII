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


# --- lifespan fail-fast (C-07) ------------------------------------------------

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

import app.main as main_mod

URL_SECRETA = "postgresql+asyncpg://admin:S3cr3t-pw@db-host:5432/libreria_db"


def _motor_fallido(exc: Exception) -> MagicMock:
    motor = MagicMock()
    motor.begin.side_effect = exc
    motor.dispose = AsyncMock()
    return motor


@pytest.mark.parametrize("exc", [OSError(f"connect failed {URL_SECRETA}"), SQLAlchemyError(URL_SECRETA)])
@pytest.mark.asyncio
async def test_lifespan_propaga_error_y_libera_motor(monkeypatch, caplog, exc):
    motor = _motor_fallido(exc)
    monkeypatch.setattr(main_mod, "get_engine", lambda: motor)
    with caplog.at_level(logging.ERROR), pytest.raises(type(exc)):
        async with main_mod.lifespan(FastAPI()):
            pytest.fail("no debe llegar al yield")  # pragma: no cover
    motor.dispose.assert_awaited_once()
    registrado = caplog.text
    assert "DATABASE_URL" in registrado
    assert "S3cr3t-pw" not in registrado
    assert "db-host" not in registrado


@pytest.mark.asyncio
async def test_lifespan_exitoso_crea_tablas_y_libera_motor(monkeypatch, tmp_path):
    motor = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'ls.db'}")
    dispose = AsyncMock(wraps=motor.dispose)
    espia = MagicMock(wraps=motor, dispose=dispose)
    monkeypatch.setattr(main_mod, "get_engine", lambda: espia)
    app_ = FastAPI()
    async with main_mod.lifespan(app_):
        assert app_.state.engine is espia
        async with espia.connect() as conn:
            tablas = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
        assert {"libro", "venta", "cliente"} <= tablas
        dispose.assert_not_awaited()
    dispose.assert_awaited_once()
