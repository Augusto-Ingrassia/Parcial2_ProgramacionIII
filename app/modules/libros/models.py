from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.autores.models import Autor
    from app.modules.editoriales.models import Editorial
    from app.modules.generos.models import Genero
    from app.modules.ventas.models import RenglonVenta

# Toda relación se lee con carga anticipada; un acceso perezoso es un error.
SIN_LAZY = {"lazy": "raise"}


class Libro(SQLModel, table=True):
    __tablename__ = "libro"
    __table_args__ = (
        CheckConstraint("precio > 0", name="ck_libro_precio_positivo"),
        CheckConstraint("stock >= 0", name="ck_libro_stock_no_negativo"),
    )

    id: int | None = Field(default=None, primary_key=True)
    isbn: str = Field(unique=True)
    titulo: str
    precio: Decimal = Field(max_digits=10, decimal_places=2)
    stock: int
    # Agregación: el libro incorpora una editorial existente (FK del lado "muchos").
    editorial_id: int = Field(foreign_key="editorial.id", index=True)
    # Agregación opcional: el género puede faltar.
    genero_id: int | None = Field(default=None, foreign_key="genero.id", index=True)

    editorial: Optional["Editorial"] = Relationship(
        back_populates="libros", sa_relationship_kwargs=SIN_LAZY
    )
    genero: Optional["Genero"] = Relationship(
        back_populates="libros", sa_relationship_kwargs=SIN_LAZY
    )
    autorias: list["LibroAutor"] = Relationship(
        back_populates="libro", sa_relationship_kwargs=SIN_LAZY
    )
    renglones: list["RenglonVenta"] = Relationship(
        back_populates="libro", sa_relationship_kwargs=SIN_LAZY
    )


class LibroAutor(SQLModel, table=True):
    """Objeto de asociación libro-autor: el rol y el orden son de la relación."""

    __tablename__ = "libro_autor"
    __table_args__ = (
        CheckConstraint("orden >= 1", name="ck_libro_autor_orden"),
        CheckConstraint(
            "rol IN ('autor', 'coautor', 'traductor', 'ilustrador')",
            name="ck_libro_autor_rol",
        ),
    )

    libro_id: int = Field(foreign_key="libro.id", primary_key=True, index=True)
    autor_id: int = Field(foreign_key="autor.id", primary_key=True, index=True)
    rol: str
    orden: int

    libro: Optional["Libro"] = Relationship(
        back_populates="autorias", sa_relationship_kwargs=SIN_LAZY
    )
    autor: Optional["Autor"] = Relationship(
        back_populates="autorias", sa_relationship_kwargs=SIN_LAZY
    )
