"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # OpenAI
    openai_api_key: str = ""
    
    # Apify
    apify_api_token: str = ""
    
    # Gmail OAuth2
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_redirect_uri: str = "http://localhost:8000/api/auth/gmail/callback"
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./leadgen.db"
    
    # Security
    secret_key: str = "change-this-in-production"
    
    # Testing/Cost Control
    max_leads_per_run: int = 5
    
    # Rate Limiting
    max_emails_per_day: int = 50
    min_email_interval_seconds: int = 120
    
    # Reply monitoring
    no_reply_followup_days: int = 14
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
