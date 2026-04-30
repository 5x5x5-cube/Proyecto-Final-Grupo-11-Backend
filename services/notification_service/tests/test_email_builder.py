from app.services.email_builder import build_payment_confirmation_email


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

    assert "subject" in result
    assert "html" in result
    assert "BK-ABC12345" in result["subject"]
    assert "TravelHub" in result["subject"]

    html = result["html"]
    assert "BK-ABC12345" in html
    assert "Hotel Paradise" in html
    assert "Suite Premium" in html
    assert "2026-06-01" in html
    assert "2026-06-05" in html
    assert "476000" in html
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


def test_subject_format():
    data = {
        "booking_code": "BK-DEADBEEF",
        "hotel_name": "Hotel",
    }
    result = build_payment_confirmation_email(data)
    assert result["subject"] == "Confirmacion de reserva BK-DEADBEEF - TravelHub"
