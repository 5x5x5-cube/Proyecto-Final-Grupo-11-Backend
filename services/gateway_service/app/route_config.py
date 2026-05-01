"""Route-level auth configuration for the API gateway.

Each route is classified as PUBLIC, TRAVELER, HOTEL_ADMIN, or OPTIONAL_AUTH.
Rules are evaluated top-to-bottom; first match wins.
"""

import re
from enum import Enum


class AuthMode(str, Enum):
    PUBLIC = "public"
    TRAVELER = "traveler"
    HOTEL_ADMIN = "hotel_admin"
    OPTIONAL_AUTH = "optional_auth"


# (method_or_ANY, path_regex, AuthMode) — first match wins
ROUTE_RULES: list[tuple[str, str, AuthMode]] = [
    # --- Fully public ---
    ("ANY", r"^/api/v1/auth/", AuthMode.PUBLIC),
    ("ANY", r"^/api/v1/search/", AuthMode.PUBLIC),
    # --- Inventory: mostly public, holds need traveler auth, tariffs need hotel admin ---
    ("POST", r"^/api/v1/inventory/holds$", AuthMode.TRAVELER),
    ("GET", r"^/api/v1/inventory/holds/check/", AuthMode.TRAVELER),
    ("ANY", r"^/api/v1/inventory/tariffs", AuthMode.HOTEL_ADMIN),
    ("ANY", r"^/api/v1/inventory/discounts", AuthMode.HOTEL_ADMIN),
    ("ANY", r"^/api/v1/inventory/", AuthMode.PUBLIC),
    # --- Bookings: mixed ---
    ("ANY", r"^/api/v1/bookings/hotel(/|$|\?)", AuthMode.HOTEL_ADMIN),
    ("ANY", r"^/api/v1/bookings/discounts", AuthMode.HOTEL_ADMIN),
    ("POST", r"^/api/v1/bookings$", AuthMode.TRAVELER),
    ("GET", r"^/api/v1/bookings$", AuthMode.TRAVELER),
    ("GET", r"^/api/v1/bookings/[^/]+/qr$", AuthMode.TRAVELER),
    ("GET", r"^/api/v1/bookings/[^/]+$", AuthMode.PUBLIC),
    ("ANY", r"^/api/v1/bookings/", AuthMode.OPTIONAL_AUTH),
    # --- Payments: mostly public ---
    ("POST", r"^/api/v1/payments/initiate$", AuthMode.TRAVELER),
    ("ANY", r"^/api/v1/payments/", AuthMode.PUBLIC),
    ("ANY", r"^/api/v1/gateway/", AuthMode.PUBLIC),
    # --- Reports: hotel admin only ---
    ("ANY", r"^/api/v1/reports/", AuthMode.HOTEL_ADMIN),
    # --- Fully protected (traveler) ---
    ("ANY", r"^/api/v1/cart", AuthMode.TRAVELER),
    ("ANY", r"^/api/v1/notifications/", AuthMode.TRAVELER),
    # --- Default: fail-closed ---
    ("ANY", r"^/api/v1/", AuthMode.TRAVELER),
]

_compiled_rules = [(method, re.compile(pattern), mode) for method, pattern, mode in ROUTE_RULES]


def get_auth_mode(method: str, path: str) -> AuthMode:
    """Determine the auth mode for a given request method + path."""
    for rule_method, pattern, mode in _compiled_rules:
        if rule_method != "ANY" and rule_method != method.upper():
            continue
        if pattern.search(path):
            return mode
    return AuthMode.TRAVELER
