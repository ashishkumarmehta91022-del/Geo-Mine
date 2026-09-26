"""Application configuration loaded from environment variables / .env files.

All settings have safe defaults so the API starts without AI credentials
or a reachable PostgreSQL server. No real credentials are ever stored here.

Database connection can be provided either as a single DATABASE_URL or as
discrete variables (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD).
"""

from functools import lru_cache
from urllib.parse import quote

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central, typed application settings (12-factor style)."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),  # backend/.env then repo root .env
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    environment: str = "development"
    debug: bool = True
    project_name: str = "cmpdi-ai-reporting-platform"

    # --- Database ---
    # Option 1: full connection string (wins when set).
    database_url: str = ""
    # Option 2: discrete variables (composed into a URL when DATABASE_URL is empty).
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "cmpdi_reporting"
    db_user: str = "cmpdi_user"
    db_password: str = ""  # comes from the environment only; never hard-coded

    # --- AI / LLM (unused until later steps; not required to start) ---
    llm_provider: str = ""
    llm_api_key: str = ""

    # --- Document storage / uploads (Step 3) ---
    # Local filesystem root for uploaded originals (dev). Swappable for object storage later.
    document_storage_path: str = "./storage/documents"
    # Maximum accepted upload size in megabytes.
    max_upload_size_mb: int = 25

    # --- CORS ---
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def effective_database_url(self) -> str:
        """DATABASE_URL if provided, otherwise composed from discrete variables."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql://{quote(self.db_user, safe='')}:{quote(self.db_password, safe='')}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the cached Settings instance."""
    return Settings()


settings = get_settings()
