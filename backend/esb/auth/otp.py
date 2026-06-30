"""OTP generation and validation — hardened per Sys-13.

Rules:
  - Codes are 6-digit numeric, TTL-bound, single-use, hashed at rest
  - After OTP_MAX_ATTEMPTS failed attempts the code is voided (not just counted)
  - Rate limit: max 3 OTP requests per email per 10 minutes (checked at generation)
  - Step-up OTPs have a shorter TTL (SESSION_TTL_STEP_UP_SECONDS from config)
  - Codes are never logged or returned in error messages
"""
from __future__ import annotations

import hashlib
import random
import string
from datetime import datetime, timedelta, timezone
from uuid import UUID

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.core.config import settings
from esb.models.user import OTPCode

log = structlog.get_logger()

OTP_RATE_LIMIT_WINDOW_MINUTES = 10
OTP_RATE_LIMIT_MAX = 3


def _generate_code() -> str:
    return "".join(random.SystemRandom().choices(string.digits, k=6))


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


async def _check_rate_limit(db: AsyncSession, person_id: UUID) -> bool:
    """Return True if within rate limit (ok to generate), False if exceeded."""
    window_start = datetime.now(timezone.utc) - timedelta(minutes=OTP_RATE_LIMIT_WINDOW_MINUTES)
    count = await db.scalar(
        select(func.count(OTPCode.id)).where(
            and_(
                OTPCode.person_id == person_id,
                OTPCode.created_at >= window_start,
            )
        )
    )
    return (count or 0) < OTP_RATE_LIMIT_MAX


async def generate_otp(
    db: AsyncSession,
    person_id: UUID,
    purpose: str = "login",
    ip_address: str | None = None,
    is_step_up: bool = False,
) -> str | None:
    """
    Generate a new OTP for the given person. Returns the plain-text code
    (the ONLY time it exists in plain text — send it immediately, don't store it).
    Returns None if rate-limited.
    """
    within_limit = await _check_rate_limit(db, person_id)
    if not within_limit:
        log.warning("otp.rate_limited", person_id=str(person_id), purpose=purpose)
        return None

    code = _generate_code()
    ttl = settings.session_ttl_step_up_seconds if is_step_up else settings.otp_ttl_seconds
    now = datetime.now(timezone.utc)

    otp = OTPCode(
        person_id=person_id,
        code_hash=_hash_code(code),
        purpose=purpose,
        expires_at=now + timedelta(seconds=ttl),
        attempt_count=0,
        created_at=now,
        ip_address=ip_address,
    )
    db.add(otp)
    await db.flush()

    log.info("otp.generated", person_id=str(person_id), purpose=purpose)
    return code


async def validate_otp(
    db: AsyncSession,
    person_id: UUID,
    code: str,
    purpose: str = "login",
) -> bool:
    """
    Validate an OTP. On success: marks it used. On failure: increments attempt count
    and voids the code if max attempts exceeded. Returns True on success.
    """
    now = datetime.now(timezone.utc)
    code_hash = _hash_code(code)

    otp = await db.scalar(
        select(OTPCode).where(
            and_(
                OTPCode.person_id == person_id,
                OTPCode.purpose == purpose,
                OTPCode.used_at.is_(None),
                OTPCode.expires_at > now,
                OTPCode.attempt_count < settings.otp_max_attempts,
            )
        ).order_by(OTPCode.created_at.desc())
    )

    if not otp:
        log.warning("otp.no_valid_code", person_id=str(person_id), purpose=purpose)
        return False

    if otp.code_hash != code_hash:
        otp.attempt_count += 1
        if otp.attempt_count >= settings.otp_max_attempts:
            # Void the code — too many failures
            otp.used_at = now
            log.warning("otp.voided_max_attempts", person_id=str(person_id))
        await db.flush()
        return False

    otp.used_at = now
    await db.flush()
    log.info("otp.validated", person_id=str(person_id), purpose=purpose)
    return True
