from app.services.email_builder import (
    _format_currency,
    _format_date_es,
    build_payment_confirmation_email,
)


def test_format_date_es():
    assert _format_date_es("2026-06-01") == "1 de junio de 2026"
    assert _format_date_es("2026-12-25") == "25 de diciembre de 2026"
    assert _format_date_es("2027-01-10") == "10 de enero de 2027"
    assert _format_date_es("bad-date") == "bad-date"


def test_format_currency_cop():
    assert _format_currency("476000", "COP") == "$476.000"
    assert _format_currency("5057500", "COP") == "$5.057.500"
    assert _format_currency("0", "COP") == "$0"
    assert _format_currency("1190000", "COP") == "$1.190.000"


def test_format_currency_with_decimals():
    assert _format_currency("99.99", "USD") == "US$99,99"


def test_format_currency_fallback():
    result = _format_currency("invalid", "COP")
    assert "COP" in result


def test_builds_email_with_all_fields():
    data = {
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
    result = build_payment_confirmation_email(data)

    assert "BK-ABC12345" in result["subject"]
    assert "TravelHub" in result["subject"]

    html = result["html"]
    assert "BK-ABC12345" in html
    assert "Hotel Paradise" in html
    assert "Suite Premium" in html
    assert "1 de junio de 2026" in html
    assert "5 de junio de 2026" in html
    assert "$476.000" in html
    assert "$400.000" in html
    assert "$76.000" in html
    assert "Visa **** 4242" in html
    assert "TXN-12345" in html
    assert "soporte@travelhub.com" in html


def test_handles_missing_optional_fields():
    data = {
        "booking_code": "BK-XYZ",
        "hotel_name": "Hotel Test",
        "room_name": "",
        "check_in": "2026-07-01",
        "check_out": "2026-07-03",
        "guests": 1,
        "base_price": "100000",
        "tax_amount": "19000",
        "service_fee": "0",
        "total_price": "119000",
        "currency": "COP",
        "payment_method_display": "",
        "transaction_id": "",
        "user_name": "",
    }
    result = build_payment_confirmation_email(data)

    assert "BK-XYZ" in result["subject"]
    assert "Hotel Test" in result["html"]
    assert "1 de julio de 2026" in result["html"]
    assert "$119.000" in result["html"]


def test_subject_format():
    data = {
        "booking_code": "BK-DEADBEEF",
        "hotel_name": "Hotel",
    }
    result = build_payment_confirmation_email(data)
    assert result["subject"] == "Confirmacion de reserva BK-DEADBEEF - TravelHub"
