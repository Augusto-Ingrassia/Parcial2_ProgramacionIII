from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, model_validator
from sqlmodel import SQLModel

from app.core.validation import NonEmptyStr
from app.modules.editoriales.schemas import EditorialRead
from app.modules.generos.schemas import GeneroRead

Rol = Literal["autor", "coautor", "traductor", "ilustrador"]
Precio = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
Stock = Annotated[int, Field(ge=0)]


# --- Entrada ---
class LibroAutorCreate(SQLModel):
    autor_id: int
    rol: Rol
    orden: Annotated[int, Field(ge=1)]


class LibroCreate(SQLModel):
    isbn: NonEmptyStr
    titulo: NonEmptyStr
    precio: Precio
    stock: Stock
    editorial_id: int
    genero_id: int | None = None
    autores: Annotated[list[LibroAutorCreate], Field(min_length=1)]

    @model_validator(mode="after")
    def _autores_sin_repetir(self):
        ids = [a.autor_id for a in self.autores]
        if len(ids) != len(set(ids)):
            raise ValueError("Un mismo autor no puede figurar dos veces en el libro")
        return self


class LibroUpdate(SQLModel):
    isbn: NonEmptyStr | None = None
    titulo: NonEmptyStr | None = None
    precio: Precio | None = None
    stock: Stock | None = None
    editorial_id: int | None = None
    genero_id: int | None = None  # null explícito quita el género

    @model_validator(mode="after")
    def _rechazar_null_en_obligatorios(self):
        for campo in self.model_fields_set - {"genero_id"}:
            if getattr(self, campo) is None:
                raise ValueError(f"El campo '{campo}' no puede ser nulo")
        return self


# --- Salida ---
class AutorDeLibroRead(SQLModel):
    autor_id: int
    nombre: str
    rol: str
    orden: int


class LibroRead(SQLModel):
    id: int
    isbn: str
    titulo: str
    precio: Decimal
    stock: int
    editorial: EditorialRead
    genero: GeneroRead | None


class LibroReadDetail(LibroRead):
    autores: list[AutorDeLibroRead]


class LibroDeAutorRead(SQLModel):
    id: int
    isbn: str
    titulo: str
    precio: Decimal
    stock: int
    rol: str
    orden: int
