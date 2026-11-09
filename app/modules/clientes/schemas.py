from typing import Annotated

from pydantic import StringConstraints, model_validator
from sqlmodel import SQLModel

from app.core.validation import NonEmptyStr

Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        max_length=255,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    ),
]


# --- Entrada ---
class ClienteCreate(SQLModel):
    nombre: NonEmptyStr
    email: Email


class ClienteUpdate(SQLModel):
    nombre: NonEmptyStr | None = None
    email: Email | None = None

    @model_validator(mode="after")
    def _rechazar_null(self):
        for campo in self.model_fields_set:
            if getattr(self, campo) is None:
                raise ValueError(f"El campo '{campo}' no puede ser nulo")
        return self


class PerfilCreate(SQLModel):
    telefono: NonEmptyStr
    direccion: NonEmptyStr


# --- Salida ---
class PerfilRead(SQLModel):
    id: int
    cliente_id: int
    telefono: str
    direccion: str


class ClienteResumen(SQLModel):
    id: int
    nombre: str
    email: str


class ClienteRead(ClienteResumen):
    perfil: PerfilRead | None
