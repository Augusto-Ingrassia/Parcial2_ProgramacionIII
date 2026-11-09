from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import Field, model_validator
from sqlmodel import SQLModel

from app.modules.clientes.schemas import ClienteResumen


# --- Entrada: no viajan precio, subtotal, total ni fecha (RN-06, RN-07) ---
class RenglonVentaCreate(SQLModel):
    libro_id: int
    cantidad: Annotated[int, Field(gt=0)]


class VentaCreate(SQLModel):
    cliente_id: int
    renglones: Annotated[list[RenglonVentaCreate], Field(min_length=1)]

    @model_validator(mode="after")
    def _libros_sin_repetir(self):
        ids = [r.libro_id for r in self.renglones]
        if len(ids) != len(set(ids)):
            raise ValueError("Un mismo libro no puede aparecer en dos renglones")
        return self


# --- Salida ---
class RenglonVentaRead(SQLModel):
    libro_id: int
    titulo: str
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal


class VentaRead(SQLModel):
    id: int
    fecha: datetime
    total: Decimal
    cliente: ClienteResumen
    renglones: list[RenglonVentaRead]
