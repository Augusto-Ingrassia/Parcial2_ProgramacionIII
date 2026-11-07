from pydantic import model_validator
from sqlmodel import SQLModel

from app.core.validation import NonEmptyStr


class AutorCreate(SQLModel):
    nombre: NonEmptyStr
    nacionalidad: NonEmptyStr


class AutorRead(SQLModel):
    id: int
    nombre: str
    nacionalidad: str


class AutorUpdate(SQLModel):
    nombre: NonEmptyStr | None = None
    nacionalidad: NonEmptyStr | None = None

    @model_validator(mode="after")
    def _reject_explicit_null(self):
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"El campo '{field}' no puede ser nulo")
        return self
