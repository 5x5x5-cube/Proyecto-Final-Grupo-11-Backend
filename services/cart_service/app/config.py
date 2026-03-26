from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/travelhub"
    redis_url: str = "redis://localhost:6379/0"
    inventory_service_url: str = "http://localhost:8006"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
