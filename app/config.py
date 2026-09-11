from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Capacitate Manabi API"
    environment: str = "local"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/capacitate_manabi_bd_v2"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    auth_secret_key: str = "change-this-secret-in-production"
    auth_token_expire_minutes: int = 720
    public_form_min_seconds: int = 3
    public_form_max_seconds: int = 1800
    rate_limit_ip_attempts: int = 10
    rate_limit_ip_window_seconds: int = 900
    rate_limit_identity_attempts: int = 3
    rate_limit_identity_window_seconds: int = 3600
    rate_limit_email_attempts: int = 3
    rate_limit_email_window_seconds: int = 3600
    client_ip_header: str | None = None
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
