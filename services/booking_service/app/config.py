from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/travelhub"

    aws_region: str = "us-east-1"
    aws_endpoint_url: Optional[str] = "http://localhost:4566"
    sqs_queue_url: str = "http://localhost:4566/000000000000/payment-booking-queue"

    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"

    sqs_poll_interval: int = 20
    sqs_max_messages: int = 10
    sqs_visibility_timeout: int = 300

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()


@lru_cache()
def get_settings() -> Settings:
    return Settings()
