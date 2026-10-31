"""Single outbound-mail adapter: Web3Forms first, SMTP fallback.

Every external email in OpsPilot/Igris funnels through send_email() so there is
one delivery path and one error type. Called only by deterministic Python (the
executor guard and owner-notify hooks) — never by the LLM.
"""

from email.message import EmailMessage
import smtplib
from typing import List, Optional

import httpx

from app.config import settings


class DeliveryError(Exception):
    """Raised when an email could not be delivered through any provider."""


WEB3FORMS_URL = "https://api.web3forms.com/submit"


def send_email(subject: str, body: str, to: Optional[str] = None) -> str:
    """Deliver one email and return the provider used ('web3forms' or 'smtp').

    Tries Web3Forms first and falls back to SMTP on rejection — Web3Forms free
    tier refuses server-side calls of any origin. Raises DeliveryError when
    every configured path fails or none is configured — fails closed.
    """
    if not to:
        raise DeliveryError("No recipient configured.")

    errors: List[str] = []

    if settings.WEB3FORMS_ACCESS_KEY:
        try:
            response = httpx.post(
                WEB3FORMS_URL,
                json={
                    "access_key": settings.WEB3FORMS_ACCESS_KEY,
                    "subject": subject,
                    "message": body,
                    "from_name": "OpsPilot",
                    "email": to,
                },
                timeout=30,
            )
            if response.status_code >= 400:
                raise DeliveryError(f"Email provider rejected the message: {response.text[:200]}")
            return "web3forms"
        except (DeliveryError, httpx.HTTPError) as exc:
            errors.append(str(exc))

    if settings.SMTP_HOST:
        try:
            msg = EmailMessage()
            msg["From"] = settings.SMTP_FROM
            msg["To"] = to
            msg["Subject"] = subject
            msg.set_content(body)
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                if settings.SMTP_USER:
                    server.login(settings.SMTP_USER, settings.SMTP_PASS)
                server.send_message(msg)
            return "smtp"
        except Exception as exc:
            errors.append(f"SMTP send failed: {exc}")

    if errors:
        raise DeliveryError(" | ".join(errors))
    raise DeliveryError("No live email provider configured. Set WEB3FORMS_ACCESS_KEY or SMTP_* first.")
