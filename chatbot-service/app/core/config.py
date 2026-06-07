from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "medusa-chatbot-service"
    environment: str = "development"
    medusa_base_url: str = Field(default="http://localhost:9000")
    medusa_publishable_api_key: str | None = None
    medusa_region_id: str | None = None
    medusa_region_country_code: str = "dk"
    medusa_timeout_seconds: float = 8.0
    storefront_base_url: str = "http://localhost:8000"
    storefront_country_code: str = "dk"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_seconds: float = 10.0
    gemini_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
