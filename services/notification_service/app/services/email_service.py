import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from ..config import settings

logger = logging.getLogger(__name__)


class EmailService:
    async def send_email(self, to: str, subject: str, html_body: str) -> bool:
        """Send an HTML email via SMTP. Returns True on success."""
        try:
            message = MIMEMultipart("alternative")
            message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
            message["To"] = to
            message["Subject"] = subject
            message.attach(MIMEText(html_body, "html", "utf-8"))

            kwargs = {
                "hostname": settings.smtp_host,
                "port": settings.smtp_port,
                "use_tls": settings.smtp_use_tls,
            }
            if settings.smtp_username:
                kwargs["username"] = settings.smtp_username
                kwargs["password"] = settings.smtp_password

            await aiosmtplib.send(message, **kwargs)
            logger.info("Email sent to %s: %s", to, subject)
            return True
        except Exception as e:
            logger.error("Failed to send email to %s: %s", to, e)
            return False


email_service = EmailService()
