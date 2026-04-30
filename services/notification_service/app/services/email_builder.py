import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

from babel.dates import format_date
from babel.numbers import format_currency as babel_format_currency
from jinja2 import Environment, FileSystemLoader

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
_LOCALES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "locales")
_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)

_BABEL_LOCALES = {
    "es": "es_CO",
    "en": "en_US",
}

# Load translation files once at module init
_TRANSLATIONS: Dict[str, Dict[str, str]] = {}
for _locale_file in os.listdir(_LOCALES_DIR):
    if _locale_file.endswith(".json"):
        _lang = _locale_file.replace(".json", "")
        with open(os.path.join(_LOCALES_DIR, _locale_file), encoding="utf-8") as f:
            _TRANSLATIONS[_lang] = json.load(f)


def _get_translations(locale: str) -> Dict[str, str]:
    """Get translations for a locale, falling back to Spanish."""
    return _TRANSLATIONS.get(locale, _TRANSLATIONS.get("es", {}))


def _format_date_localized(date_str: str, locale: str = "es") -> str:
    """Convert 'YYYY-MM-DD' to a locale-aware long date string."""
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        babel_locale = _BABEL_LOCALES.get(locale, "es_CO")
        return format_date(dt, format="long", locale=babel_locale)
    except (ValueError, IndexError):
        return date_str


def _format_currency(value: str | float | int, currency: str = "COP", locale: str = "es") -> str:
    """Format a numeric value as locale-aware currency."""
    try:
        num = float(value)
        babel_locale = _BABEL_LOCALES.get(locale, "es_CO")
        result = babel_format_currency(num, currency, locale=babel_locale)
        if num == int(num):
            for sep in [",00", ".00"]:
                if result.endswith(sep):
                    result = result[: -len(sep)]
                    break
        return result
    except (ValueError, TypeError):
        return f"{currency} {value}"


def build_payment_confirmation_email(data: Dict[str, Any], locale: str = "es") -> Dict[str, str]:
    """Build subject and HTML body for a payment confirmation email."""
    template = _env.get_template("payment_confirmation.html")
    data.setdefault("current_year", datetime.now(timezone.utc).year)

    # Normalize locale
    locale = locale.lower()[:2] if locale else "es"
    if locale not in _BABEL_LOCALES:
        locale = "es"

    translations = _get_translations(locale)
    currency = data.get("currency", "COP")

    # Format dates
    data["check_in"] = _format_date_localized(str(data.get("check_in", "")), locale)
    data["check_out"] = _format_date_localized(str(data.get("check_out", "")), locale)

    # Check for non-zero service fee before formatting
    try:
        data["has_service_fee"] = float(data.get("service_fee", 0)) > 0
    except (ValueError, TypeError):
        data["has_service_fee"] = False

    # Format currency values
    data["base_price"] = _format_currency(data.get("base_price", 0), currency, locale)
    data["tax_amount"] = _format_currency(data.get("tax_amount", 0), currency, locale)
    data["service_fee"] = _format_currency(data.get("service_fee", 0), currency, locale)
    data["total_price"] = _format_currency(data.get("total_price", 0), currency, locale)

    # Rename guests to avoid collision with i18n key
    data["guests_count"] = data.pop("guests", 0)

    # Translation function for the template
    def t(key: str, **kwargs: Any) -> str:
        text = translations.get(key, key)
        if kwargs:
            for k, v in kwargs.items():
                text = text.replace(f"%{{{k}}}", str(v))
        return text

    data["t"] = t
    data["lang"] = locale

    html = template.render(**data)
    booking_code = data.get("booking_code", "")
    subject = t("subject", code=booking_code)
    return {"subject": subject, "html": html}
