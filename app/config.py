from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    openrouter_api_key: str = ""
    llm_model: str = "minimax/minimax-m2.5"
    database_url: str = "sqlite+aiosqlite:///./eventops.db"
    environment: str = "development"
    debug: bool = True
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
