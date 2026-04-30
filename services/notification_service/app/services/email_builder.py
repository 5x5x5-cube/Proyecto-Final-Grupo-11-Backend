import os
from datetime import datetime, timezone
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)


def build_payment_confirmation_email(data: Dict[str, Any]) -> Dict[str, str]:
    """Build subject and HTML body for a payment confirmation email.

    Args:
        data: dict with keys: booking_code, hotel_name, room_name, check_in, check_out,
              guests, base_price, tax_amount, service_fee, total_price, currency,
              payment_method_display, transaction_id, user_name

    Returns:
        {"subject": str, "html": str}
    """
    template = _env.get_template("payment_confirmation.html")
    data.setdefault("current_year", datetime.now(timezone.utc).year)
    html = template.render(**data)
    subject = f"Confirmacion de reserva {data.get('booking_code', '')} - TravelHub"
    return {"subject": subject, "html": html}
