from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    booking_service_url: str = "http://localhost:8002"
    auth_service_url: str = ""
    search_service_url: str = ""
    cart_service_url: str = ""
    payment_service_url: str = ""
    reports_service_url: str = ""
    notification_service_url: str = ""
    monitor_service_url: str = ""
    default_user_id: str = ""  # Injected as X-User-Id when no auth service exists
    default_hotel_id: str = ""  # Injected as X-Hotel-Id when no auth service exists

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()


def get_service_routes() -> dict[str, str | None]:
    """
    Map API path prefixes to backend service URLs.
    Empty string means the service is not yet configured → returns 501.
    """
    return {
        "bookings": settings.booking_service_url or None,
        "auth": settings.auth_service_url or None,
        "search": settings.search_service_url or None,
        "cart": settings.cart_service_url or None,
        "payments": settings.payment_service_url or None,
        "gateway": settings.payment_service_url or None,
        "reports": settings.reports_service_url or None,
        "notifications": settings.notification_service_url or None,
        "monitor": settings.monitor_service_url or None,
    }
