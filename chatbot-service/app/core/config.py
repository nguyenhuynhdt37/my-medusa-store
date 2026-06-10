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
    database_url: str | None = None
    chat_auto_migrate: bool = True
    redis_url: str | None = None
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    lex_bot_id: str | None = None
    lex_bot_alias_id: str | None = None
    lex_locale_id: str = "vi_VN"
    fb_app_id: str | None = None
    fb_app_secret: str | None = None
    fb_page_access_token: str | None = None
    fb_verify_token: str | None = None
    fb_graph_version: str = "v20.0"
    facebook_app_secret: str | None = None
    facebook_page_access_token: str | None = None
    facebook_verify_token: str | None = None
    facebook_graph_version: str | None = None
    enable_human_handover: bool = True
    enable_customer_resume_bot: bool = False
    human_handover_confidence_threshold: float = 0.65
    human_handover_ttl_seconds: int = 86400
    webhook_dedupe_ttl_seconds: int = 86400
    storefront_base_url: str = "http://localhost:8000"
    storefront_internal_url: str = "http://localhost:8000"
    storefront_country_code: str = "dk"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    gemini_timeout_seconds: float = 10.0
    gemini_enabled: bool = True
    ai_cost_tracking_enabled: bool = True
    lex_text_request_price_usd: float = 0.00075
    gemini_input_price_per_1m_tokens_usd: float = 0.30
    gemini_output_price_per_1m_tokens_usd: float = 2.50
    lambda_memory_size_mb: int = 128
    lambda_request_price_per_1m_usd: float = 0.20
    lambda_duration_price_per_gb_second_usd: float = 0.0000166667
    ai_usage_snapshot_job_enabled: bool = True
    ai_usage_snapshot_interval_seconds: int = 3600

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
