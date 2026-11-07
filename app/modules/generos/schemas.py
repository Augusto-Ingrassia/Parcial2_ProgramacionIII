from sqlmodel import SQLModel

from app.core.validation import NonEmptyStr


class GeneroCreate(SQLModel):
    nombre: NonEmptyStr


class GeneroRead(SQLModel):
    id: int
    nombre: str
