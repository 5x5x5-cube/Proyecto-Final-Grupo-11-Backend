from app.services.email_builder import (
    _format_currency,
    _format_date_localized,
    build_payment_confirmation_email,
)


def _sample_data(**overrides):
    base = {
        "booking_code": "BK-ABC12345",
        "hotel_name": "Hotel Paradise",
        "room_name": "Suite Premium",
        "check_in": "2026-06-01",
        "check_out": "2026-06-05",
        "guests": 2,
        "base_price": "400000",
        "tax_amount": "76000",
        "service_fee": "0",
        "total_price": "476000",
        "currency": "COP",
        "payment_method_display": "Visa **** 4242",
        "transaction_id": "TXN-12345",
        "user_name": "Juan Perez",
    }
    base.update(overrides)
    return base


class TestDateFormatting:
    def test_spanish_date(self):
        assert _format_date_localized("2026-06-01", "es") == "1 de junio de 2026"
        assert _format_date_localized("2026-12-25", "es") == "25 de diciembre de 2026"

    def test_english_date(self):
        assert _format_date_localized("2026-06-01", "en") == "June 1, 2026"
        assert _format_date_localized("2026-12-25", "en") == "December 25, 2026"

    def test_invalid_date_passthrough(self):
        assert _format_date_localized("bad-date", "es") == "bad-date"


class TestCurrencyFormatting:
    def test_cop_spanish(self):
        assert _format_currency("476000", "COP", "es") == "$476.000"
        assert _format_currency("5057500", "COP", "es") == "$5.057.500"

    def test_cop_english(self):
        result = _format_currency("476000", "COP", "en")
        assert "476" in result

    def test_usd_with_decimals(self):
        assert _format_currency("99.99", "USD", "en") == "$99.99"

    def test_fallback_on_invalid(self):
        result = _format_currency("invalid", "COP", "es")
        assert "COP" in result


class TestSpanishEmail:
    def test_builds_spanish_email(self):
        result = build_payment_confirmation_email(_sample_data(), locale="es")

        assert "Confirmacion de reserva BK-ABC12345 - TravelHub" == result["subject"]

        html = result["html"]
        assert "Pago confirmado" in html
        assert "Tu reserva ha sido registrada exitosamente." in html
        assert "Codigo de reserva" in html
        assert "Detalles de la reserva" in html
        assert "Resumen de pago" in html
        assert "Total pagado" in html
        assert "1 de junio de 2026" in html
        assert "$476.000" in html
        assert 'lang="es"' in html

    def test_handles_missing_optional_fields(self):
        data = _sample_data(room_name="", payment_method_display="", transaction_id="")
        result = build_payment_confirmation_email(data, locale="es")
        assert "BK-ABC12345" in result["subject"]


class TestEnglishEmail:
    def test_builds_english_email(self):
        result = build_payment_confirmation_email(_sample_data(), locale="en")

        assert "Booking confirmation BK-ABC12345 - TravelHub" == result["subject"]

        html = result["html"]
        assert "Payment confirmed" in html
        assert "Your booking has been successfully registered." in html
        assert "Booking code" in html
        assert "Booking details" in html
        assert "Payment summary" in html
        assert "Total paid" in html
        assert "June 1, 2026" in html
        assert 'lang="en"' in html


class TestLocaleFallback:
    def test_unknown_locale_falls_back_to_spanish(self):
        result = build_payment_confirmation_email(_sample_data(), locale="fr")
        assert "Pago confirmado" in result["html"]

    def test_none_locale_falls_back_to_spanish(self):
        result = build_payment_confirmation_email(_sample_data(), locale=None)
        assert "Pago confirmado" in result["html"]

    def test_empty_locale_falls_back_to_spanish(self):
        result = build_payment_confirmation_email(_sample_data(), locale="")
        assert "Pago confirmado" in result["html"]


class TestSubjectFormat:
    def test_subject_spanish(self):
        result = build_payment_confirmation_email(
            {"booking_code": "BK-DEADBEEF", "hotel_name": "Hotel"}, locale="es"
        )
        assert result["subject"] == "Confirmacion de reserva BK-DEADBEEF - TravelHub"

    def test_subject_english(self):
        result = build_payment_confirmation_email(
            {"booking_code": "BK-DEADBEEF", "hotel_name": "Hotel"}, locale="en"
        )
        assert result["subject"] == "Booking confirmation BK-DEADBEEF - TravelHub"
