from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    payment_service_url: str = "http://localhost:8000"
    gateway_url: str = "http://localhost:8000"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/travelhub"
    cart_service_url: str = "http://localhost:8004"
    booking_service_url: str = "http://localhost:8002"
    sns_topic_arn: str = "arn:aws:sns:us-east-1:000000000000:command-update"
    aws_region: str = "us-east-1"
    aws_endpoint_url: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # Fraud detection (HU4.7)
    redis_url: str = "redis://localhost:6379/2"
    # Duplicate window: same user+amount+method within this many seconds → flagged
    fraud_duplicate_window_seconds: int = 300  # 5 min
    # Velocity window: more than N transactions for the same user within W seconds → flagged
    fraud_velocity_window_seconds: int = 600  # 10 min
    fraud_velocity_threshold: int = 5
    # 3D Secure: consecutive failures per method before temporary block
    fraud_3ds_max_failures: int = 3
    fraud_3ds_block_seconds: int = 900  # 15 min
    # TTL for the user transaction history sorted set
    fraud_history_ttl_seconds: int = 1800  # 30 min — comfortably > both windows

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
