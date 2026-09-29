from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


def asyncpg_url(connection_url: str) -> str:
    url = make_url(connection_url)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+asyncpg")
    if url.drivername == "postgresql+asyncpg":
        # SQLAlchemy forwards URL query parameters as asyncpg.connect kwargs.
        query = dict(url.query)
        query.pop("channel_binding", None)
        sslmode = query.pop("sslmode", None)
        if sslmode is not None and "ssl" not in query:
            # asyncpg accepts ssl=require/verify-full, but not the libpq name sslmode.
            query["ssl"] = sslmode
        url = url.set(query=query)
    return url.render_as_string(hide_password=False)


class Settings(BaseSettings):
    DATABASE_URL: str | None = None
    AWS_ENDPOINT_URL_S3: str | None = None
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_REGION: str = "ap-southeast-1"
    S3_BUCKET: str | None = None
    S3_AVATAR_URL_EXPIRY_SECONDS: int = 604800
    AI_PROVIDER: str = "openai"
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4.1"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.6-flash"
    CORS_ORIGINS: str = "http://localhost:5173"
    model_config = SettingsConfigDict(env_file=".env.local", env_file_encoding="utf-8", extra="ignore")

    @property
    def database_url(self) -> str:
        if not self.DATABASE_URL:
            raise ValueError("Set DATABASE_URL in .env.local")
        return asyncpg_url(self.DATABASE_URL)

    @property
    def uses_pooled_database(self) -> bool:
        if not self.DATABASE_URL:
            return False
        host = make_url(self.DATABASE_URL).host or ""
        return "-pooler." in host.lower()

settings = Settings()
