from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.ventas.models import Venta

SIN_LAZY = {"lazy": "raise"}


class Cliente(SQLModel, table=True):
    __tablename__ = "cliente"

    id: int | None = Field(default=None, primary_key=True)
    nombre: str
    email: str = Field(unique=True)

    # Uno a uno: objeto único (no lista), 0..1 perfil por cliente.
    perfil: Optional["PerfilCliente"] = Relationship(
        back_populates="cliente", sa_relationship_kwargs={**SIN_LAZY, "uselist": False}
    )
    ventas: list["Venta"] = Relationship(back_populates="cliente", sa_relationship_kwargs=SIN_LAZY)


class PerfilCliente(SQLModel, table=True):
    __tablename__ = "perfil_cliente"

    id: int | None = Field(default=None, primary_key=True)
    # La FK la lleva el lado opcional; UNIQUE la vuelve uno a uno (RN-09).
    cliente_id: int = Field(foreign_key="cliente.id", unique=True, index=True)
    telefono: str
    direccion: str

    cliente: Optional["Cliente"] = Relationship(
        back_populates="perfil", sa_relationship_kwargs=SIN_LAZY
    )
