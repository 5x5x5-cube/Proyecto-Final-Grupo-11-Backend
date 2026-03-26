from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/travelhub"
    redis_url: str = "redis://localhost:6379/0"
    inventory_service_url: str = "http://localhost:8006"
    lock_timeout: int = 10  # transaction lock TTL in seconds
    lock_retry_attempts: int = 3
    lock_retry_delay: float = 0.1  # base delay for exponential backoff

    model_config = SettingsConfigDict(env_prefix="BOOKING_", env_file=".env")


settings = Settings()
