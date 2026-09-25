from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
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
    MAX_FILE_SIZE_MB: int = 50
    # MIME types allowed based on file CONTENT (python-magic), not just extension/header
    ALLOWED_MIME_TYPES: str = (
        "application/pdf,"
        "text/plain,"
        "text/markdown,"
        "application/msword,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "application/vnd.ms-excel,"
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "text/csv,"
        "application/vnd.ms-powerpoint,"
        "application/vnd.openxmlformats-officedocument.presentationml.presentation,"
        "application/vnd.oasis.opendocument.text,"
        "application/vnd.oasis.opendocument.spreadsheet,"
        "application/rtf,"
        "application/epub+zip,"
        "application/vnd.ms-outlook,"
        "message/rfc822,"
        "image/tiff,"
        "image/png,"
        "image/jpeg"
    )
    OCR_REQUIRED: bool = False
    OCR_TIMEOUT_SECONDS: int = 90
    OCR_MAX_PAGES: int = 20
    OCR_MAX_TEXT_CHARS: int = 1_000_000
    OCR_RENDER_DPI: int = 200
    OCR_MAX_CONCURRENT_DOCUMENTS: int = 2

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
