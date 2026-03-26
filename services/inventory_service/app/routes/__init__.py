from .webhooks import router as webhooks_router
from .accommodations import router as accommodations_router

__all__ = ["webhooks_router", "accommodations_router"]
