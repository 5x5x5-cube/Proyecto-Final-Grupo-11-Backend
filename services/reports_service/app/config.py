from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Reports Service"
    app_version: str = "0.2.0"

    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/bookings"

    # Services URLs
    booking_service_url: str = "http://booking-service:8000"
    payment_service_url: str = "http://payment-service:8000"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
