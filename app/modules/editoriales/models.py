from sqlmodel import Field, SQLModel


class Editorial(SQLModel, table=True):
    __tablename__ = "editorial"

    id: int | None = Field(default=None, primary_key=True)
    nombre: str = Field(unique=True)
    pais: str
