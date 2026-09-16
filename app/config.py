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


@lru_cache()
def get_settings() -> Settings:
    return Settings()
