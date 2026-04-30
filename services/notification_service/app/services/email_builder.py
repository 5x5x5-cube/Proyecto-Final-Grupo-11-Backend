import os
from datetime import datetime, timezone
from typing import Any, Dict

from babel.dates import format_date
from babel.numbers import format_currency as babel_format_currency
from jinja2 import Environment, FileSystemLoader

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)

_LOCALE = "es_CO"


def _format_date_es(date_str: str) -> str:
    """Convert 'YYYY-MM-DD' to '20 de diciembre de 2026'."""
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return format_date(dt, format="long", locale=_LOCALE)
    except (ValueError, IndexError):
        return date_str


def _format_currency(value: str | float | int, currency: str = "COP") -> str:
    """Format a numeric value as locale-aware currency: '$5.057.500'."""
    try:
        num = float(value)
        result = babel_format_currency(num, currency, locale=_LOCALE)
        # Drop decimal part for whole amounts (e.g. "$476.000,00" -> "$476.000")
        if num == int(num):
            result = result.replace(",00", "")
        return result
    except (ValueError, TypeError):
        return f"{currency} {value}"


def build_payment_confirmation_email(data: Dict[str, Any]) -> Dict[str, str]:
    """Build subject and HTML body for a payment confirmation email."""
    template = _env.get_template("payment_confirmation.html")
    data.setdefault("current_year", datetime.now(timezone.utc).year)

    currency = data.get("currency", "COP")

    # Format dates for display
    data["check_in"] = _format_date_es(str(data.get("check_in", "")))
    data["check_out"] = _format_date_es(str(data.get("check_out", "")))

    # Format currency values
    data["base_price"] = _format_currency(data.get("base_price", 0), currency)
    data["tax_amount"] = _format_currency(data.get("tax_amount", 0), currency)
    data["service_fee"] = _format_currency(data.get("service_fee", 0), currency)
    data["total_price"] = _format_currency(data.get("total_price", 0), currency)

    html = template.render(**data)
    subject = f"Confirmacion de reserva {data.get('booking_code', '')} - TravelHub"
    return {"subject": subject, "html": html}
