"""Application configuration loaded from environment variables / .env files.

All settings have safe defaults so the API starts without AI credentials
or a reachable PostgreSQL server (Step 1 requires connection architecture
only, no live database).
"""

from functools import lru_cache

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
    # Not required to boot in Step 1; connections open lazily.
    database_url: str = "postgresql://cmpdi_user:CHANGE_ME@localhost:5432/cmpdi_reporting"

    # --- AI / LLM (unused in Step 1; must not be required to start) ---
    llm_provider: str = ""
    llm_api_key: str = ""

    # --- CORS ---
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the cached Settings instance."""
    return Settings()


settings = get_settings()
