from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/travelhub"
    redis_url: str = "redis://localhost:6379/0"
    hold_ttl: int = 900  # 15 minutes in seconds
    cleanup_interval: int = 60  # seconds between cleanup sweeps

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
