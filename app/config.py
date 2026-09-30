from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql+asyncpg://vaultiq:vaultiq_secret@localhost:5433/vaultiq"
    DATABASE_URL_SYNC: str = "postgresql://vaultiq:vaultiq_secret@localhost:5433/vaultiq"
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    MAX_FAILED_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    STORAGE_ROOT: str = "./storage"
    # Browser origins permitted to call the API. Comma-separated, exact match,
    # no wildcards: the API is credentialed (Bearer token) and a wildcard with
    # allow_credentials is rejected by browsers anyway.
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
