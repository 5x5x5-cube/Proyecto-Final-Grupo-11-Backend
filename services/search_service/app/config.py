from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Search Service"
    app_version: str = "0.1.0"

    redis_url: str = "redis://localhost:6379"
    redis_hotel_index: str = "idx:hotels"
    redis_room_index: str = "idx:rooms"

    aws_region: str = "us-east-1"
    aws_endpoint_url: Optional[str] = "http://localhost:4566"
    sqs_queue_url: str = "http://localhost:4566/000000000000/hotel-sync-queue"

    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"

    sqs_poll_interval: int = 20
    sqs_max_messages: int = 10
    sqs_visibility_timeout: int = 300

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
