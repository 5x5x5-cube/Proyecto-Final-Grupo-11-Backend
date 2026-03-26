from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Search Service"
    app_version: str = "0.1.0"
    
    redis_url: str = "redis://localhost:6379"
    redis_index_name: str = "idx:accommodations"
    
    aws_region: str = "us-east-1"
    aws_endpoint_url: str | None = None
    sqs_queue_url: str = ""
    
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"
    
    sqs_poll_interval: int = 20
    sqs_max_messages: int = 10
    sqs_visibility_timeout: int = 300
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
