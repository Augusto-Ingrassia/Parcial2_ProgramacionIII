from pydantic import model_validator
from sqlmodel import SQLModel

from app.core.validation import NonEmptyStr


class EditorialCreate(SQLModel):
    nombre: NonEmptyStr
    pais: NonEmptyStr


class EditorialRead(SQLModel):
    id: int
    nombre: str
    pais: str


class EditorialUpdate(SQLModel):
    nombre: NonEmptyStr | None = None
    pais: NonEmptyStr | None = None

    @model_validator(mode="after")
    def _reject_explicit_null(self):
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"El campo '{field}' no puede ser nulo")
        return self
