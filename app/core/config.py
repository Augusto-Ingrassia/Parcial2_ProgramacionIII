from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = Field(
        description="URL asincrónica de conexión a PostgreSQL",
    )
    SQL_ECHO: bool = Field(
        default=False,
        description="Activa el logging de sentencias SQL en consola",
    )
    APP_PORT: int = Field(
        default=8000,
        description="Puerto de escucha del servidor",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
