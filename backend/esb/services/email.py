"""Transactional email via Postmark."""
from __future__ import annotations

import httpx
import structlog

from esb.core.config import settings

log = structlog.get_logger()

POSTMARK_API_URL = "https://api.postmarkapp.com/email"


async def send_email(to: str, subject: str, text_body: str) -> bool:
    """Send a transactional email via Postmark. Returns True on success."""
    if not settings.postmark_server_token:
        log.warning("email.skipped_no_token", to=to, subject=subject)
        return False

    async with httpx.AsyncClient() as client:
        response = await client.post(
            POSTMARK_API_URL,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": settings.postmark_server_token,
            },
            json={
                "From": settings.email_from,
                "To": to,
                "Subject": subject,
                "TextBody": text_body,
                "MessageStream": "outbound",
            },
            timeout=10.0,
        )

    if response.status_code != 200:
        log.error("email.send_failed", to=to, status=response.status_code, body=response.text[:500])
        return False

    log.info("email.sent", to=to, subject=subject)
    return True


async def send_otp_email(to: str, code: str) -> bool:
    return await send_email(
        to=to,
        subject="Your Effective School Boards sign-in code",
        text_body=(
            f"Your sign-in code is: {code}\n\n"
            "This code expires in 5 minutes. If you didn't request this, you can ignore this email."
        ),
    )
