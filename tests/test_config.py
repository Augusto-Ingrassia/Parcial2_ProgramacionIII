import os
import pytest
from app.core.config import Settings, get_settings

def test_settings_default_values():
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/test_db",
        _env_file=None
    )
    assert settings.DATABASE_URL == "postgresql+asyncpg://postgres:postgres@localhost:5432/test_db"
    assert settings.SQL_ECHO is False
    assert settings.APP_PORT == 8000

def test_settings_custom_values():
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/custom_db",
        SQL_ECHO=True,
        APP_PORT=9000,
        _env_file=None
    )
    assert settings.SQL_ECHO is True
    assert settings.APP_PORT == 9000

def test_settings_cached_singleton():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
