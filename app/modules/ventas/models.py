from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.clientes.models import Cliente
    from app.modules.libros.models import Libro

SIN_LAZY = {"lazy": "raise"}


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class Venta(SQLModel, table=True):
    __tablename__ = "venta"
    __table_args__ = (CheckConstraint("total >= 0", name="ck_venta_total_no_negativo"),)

    id: int | None = Field(default=None, primary_key=True)
    # Asociación: la venta conoce al cliente, ninguno es parte del otro.
    cliente_id: int = Field(foreign_key="cliente.id", index=True)
    fecha: datetime = Field(default_factory=_ahora_utc, sa_type=DateTime(timezone=True))
    total: Decimal = Field(max_digits=12, decimal_places=2)

    cliente: Optional["Cliente"] = Relationship(
        back_populates="ventas", sa_relationship_kwargs=SIN_LAZY
    )
    # Composición: los renglones nacen y mueren con la venta.
    renglones: list["RenglonVenta"] = Relationship(
        back_populates="venta", cascade_delete=True, sa_relationship_kwargs=SIN_LAZY
    )


class RenglonVenta(SQLModel, table=True):
    __tablename__ = "renglon_venta"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_renglon_cantidad_positiva"),
        CheckConstraint("precio_unitario > 0", name="ck_renglon_precio_positivo"),
    )

    id: int | None = Field(default=None, primary_key=True)
    venta_id: int = Field(foreign_key="venta.id", index=True, ondelete="CASCADE")
    # Asociación: el renglón nombra un libro que ya existe.
    libro_id: int = Field(foreign_key="libro.id", index=True)
    cantidad: int
    precio_unitario: Decimal = Field(max_digits=10, decimal_places=2)

    venta: Optional["Venta"] = Relationship(
        back_populates="renglones", sa_relationship_kwargs=SIN_LAZY
    )
    libro: Optional["Libro"] = Relationship(
        back_populates="renglones", sa_relationship_kwargs=SIN_LAZY
    )
