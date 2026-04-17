from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    payment_service_url: str = "http://localhost:8000"
    gateway_url: str = "http://localhost:8000"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/travelhub"
    cart_service_url: str = "http://localhost:8004"
    booking_service_url: str = "http://localhost:8002"
    sqs_queue_url: str = ""
    aws_region: str = "us-east-1"
    aws_endpoint_url: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
