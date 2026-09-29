from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Hosted Postgres providers usually expose DATABASE_URL; keep DB_URL for local use.
    DB_URL: str | None = None
    DATABASE_URL: str | None = None
    AI_PROVIDER: str = "openai"
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4.1"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.6-flash"
    CORS_ORIGINS: str = "http://localhost:5173"
    model_config = SettingsConfigDict(env_file=".env.local", env_file_encoding="utf-8")

settings = Settings()

if not settings.DB_URL:
    if not settings.DATABASE_URL:
        raise ValueError("DB_URL or DATABASE_URL must be set")
    settings.DB_URL = settings.DATABASE_URL

# asyncpg needs the SQLAlchemy async dialect explicitly selected.
if settings.DB_URL.startswith("postgres://"):
    settings.DB_URL = settings.DB_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif settings.DB_URL.startswith("postgresql://"):
    settings.DB_URL = settings.DB_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
