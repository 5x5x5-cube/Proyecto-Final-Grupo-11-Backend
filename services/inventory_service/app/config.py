from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Inventory Service"
    app_version: str = "0.1.0"
    
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/inventory_db"
    
    aws_region: str = "us-east-1"
    aws_endpoint_url: str | None = None
    sqs_queue_url: str = ""
    
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
