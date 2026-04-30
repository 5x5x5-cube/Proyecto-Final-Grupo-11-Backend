from unittest.mock import AsyncMock, patch

import pytest

from app.services.email_service import EmailService


@pytest.fixture
def service():
    return EmailService()


async def test_send_email_success(service):
    with patch("app.services.email_service.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        result = await service.send_email(
            to="user@example.com",
            subject="Test Subject",
            html_body="<h1>Hello</h1>",
        )
        assert result is True
        mock_send.assert_called_once()


async def test_send_email_failure(service):
    with patch(
        "app.services.email_service.aiosmtplib.send",
        new_callable=AsyncMock,
        side_effect=ConnectionRefusedError("SMTP connection refused"),
    ):
        result = await service.send_email(
            to="user@example.com",
            subject="Test Subject",
            html_body="<h1>Hello</h1>",
        )
        assert result is False


async def test_send_email_builds_correct_message(service):
    with patch("app.services.email_service.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        await service.send_email(
            to="traveler@test.com",
            subject="Confirmacion de reserva BK-ABC123 - TravelHub",
            html_body="<h1>Reserva confirmada</h1>",
        )
        call_args = mock_send.call_args
        message = call_args[0][0]
        assert message["To"] == "traveler@test.com"
        assert "TravelHub" in message["From"]
        assert "BK-ABC123" in message["Subject"]
