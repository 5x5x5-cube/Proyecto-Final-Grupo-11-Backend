from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/travelhub"
    redis_url: str = "redis://localhost:6379/0"
    hold_ttl: int = 900
    cleanup_interval: int = 60

    aws_region: str = "us-east-1"
    aws_endpoint_url: str = "http://localhost:4566"
    sns_topic_arn: str = "arn:aws:sns:us-east-1:000000000000:command-update"
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
