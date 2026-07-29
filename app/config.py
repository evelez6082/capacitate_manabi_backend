from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Capacitate Manabi API"
    environment: str = "local"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/capacitate_manabi_bd_v2"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    smtp_enabled: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_from_name: str = "Capacitate Manabi"
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    support_email: str = "formacion@manabi.gob.ec"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
