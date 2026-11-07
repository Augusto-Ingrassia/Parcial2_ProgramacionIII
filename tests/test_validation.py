import pytest
from pydantic import BaseModel, ValidationError

from app.core.validation import NonEmptyStr


class Sample(BaseModel):
    nombre: NonEmptyStr


def test_non_empty_str_strips_whitespace():
    assert Sample(nombre=" Planeta ").nombre == "Planeta"


def test_non_empty_str_accepts_max_length():
    assert len(Sample(nombre="a" * 255).nombre) == 255


@pytest.mark.parametrize("value", ["", "   ", "a" * 256])
def test_non_empty_str_rejects_invalid(value):
    with pytest.raises(ValidationError):
        Sample(nombre=value)
