from sqlmodel import Field, SQLModel


class Genero(SQLModel, table=True):
    __tablename__ = "genero"

    id: int | None = Field(default=None, primary_key=True)
    nombre: str = Field(unique=True)
