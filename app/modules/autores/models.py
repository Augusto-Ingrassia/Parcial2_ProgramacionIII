from sqlmodel import Field, SQLModel


class Autor(SQLModel, table=True):
    __tablename__ = "autor"

    id: int | None = Field(default=None, primary_key=True)
    nombre: str
    nacionalidad: str
