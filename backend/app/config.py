"""Application configuration loaded from environment variables / .env files.

All settings have safe defaults so the API starts without AI credentials
or a reachable PostgreSQL server. No real credentials are ever stored here.

Database connection can be provided either as a single DATABASE_URL or as
discrete variables (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD).
"""

from functools import lru_cache
from urllib.parse import quote

from pydantic import Field
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
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str = "cmpdi_reporting"
    db_user: str = "cmpdi_user"
    db_password: str = ""  # comes from the environment only; never hard-coded

    # --- AI / LLM (Step 10: AI Query; optional — everything works without it) ---
    # Empty provider name ⇒ LLM unavailable ⇒ /api/ai/query answers 503
    # llm_unavailable. Never fabricate answers; keys come from the env only.
    llm_provider: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    # OpenAI-compatible base URL (e.g. a local server or a cloud endpoint).
    llm_base_url: str = ""
    llm_timeout_seconds: float = Field(default=60.0, ge=1.0)

    # --- Document storage / uploads (Step 3) ---
    # Local filesystem root for uploaded originals (dev). Swappable for object storage later.
    document_storage_path: str = "./storage/documents"
    # Maximum accepted upload size in megabytes (bounded: 1 MB .. 4 GB).
    max_upload_size_mb: int = Field(default=25, ge=1, le=4096)

    # --- OCR (Step 5) ---
    # Box/mean confidences below this flag the unit `review_required`.
    # Never used to ALTER text — OCR output is always preserved verbatim.
    ocr_confidence_threshold: float = Field(default=0.70, gt=0.0, le=1.0)
    # Wall-clock cap per OCR call (protects against pathological inputs).
    ocr_timeout_seconds: float = Field(default=120.0, gt=0.0)
    # Reject absurd images before OCR (decompression-bomb guardrail).
    ocr_max_image_pixels: int = Field(default=40_000_000, gt=0)
    # Render zoom for scanned PDF pages before OCR (~2.0 ≈ 144 dpi).
    pdf_ocr_zoom: float = Field(default=2.0, gt=0.0)

    # --- Semantic embeddings (Step 9) ---
    # Bounded safeguards for the local embedding pipeline (see embeddings/config.py).
    embedding_max_input_chars: int = Field(default=4000, gt=0)
    embedding_max_batch_size: int = Field(default=32, gt=0)
    embedding_max_units_per_document: int = Field(default=500, gt=0)
    embedding_timeout_seconds: float = Field(default=120.0, gt=0.0)

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
