"""
Configuration and settings management using pydantic-settings.
Reads values from .env file automatically.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings ,SettingsConfigDict


class Settings(BaseSettings):
    # Database
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = "password"
    db_name: str = "lost_and_found_db"
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"  # Isse .env ke extra fields se error nahi aayega
    )

    # JWT
    secret_key: str = "changeme-use-a-long-random-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # App
    app_name: str = "Lost & Found Portal"
    app_version: str = "1.0.0"
    debug: bool = False

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

 


@lru_cache()
def get_settings() -> Settings:
    return Settings()
