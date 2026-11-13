from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "DataForge AI"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./dataforge.db"
    redis_url: str = "redis://localhost:6379/0"
    job_execution: str = "inline"  # inline for local learning; celery for Docker/production.
    jwt_secret_key: str = "unsafe-development-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    llm_provider: str = "local"
    llm_model: str = "local-template-generator"
    export_directory: Path = Path("data/exports")
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
