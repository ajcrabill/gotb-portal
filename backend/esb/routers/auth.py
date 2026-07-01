"""Auth router — OTP request/verify, step-up, logout, /me.

Email delivery: the OTP is sent via Postmark (esb.services.email). In
development (ENVIRONMENT=development), the OTP is also returned in the
response JSON so the developer doesn't need a mail server. In production
that field is always null.
"""
from __future__ import annotations

import hashlib
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from esb.auth.otp import generate_otp, validate_otp
from esb.auth.rbac import AuthContext, get_auth_context
from esb.auth.sessions import create_session, revoke_session
from esb.core.config import settings
from esb.core.database import get_db
from esb.services import audit as audit_svc
from esb.services.email import send_otp_email
from esb.services.people import get_or_create

log = structlog.get_logger()

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    xff = request.headers.get("X-Forwarded-For")
    return xff.split(",")[0].strip() if xff else request.client.host if request.client else None


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ── Request OTP ──────────────────────────────────────────────────────────────

class OTPRequest(BaseModel):
    email: EmailStr
    name: str = ""


class OTPResponse(BaseModel):
    sent: bool
    # Only populated in development to avoid needing a mail server
    dev_otp: str | None = None


@router.post("/request-otp", response_model=OTPResponse)
async def request_otp(
    body: OTPRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> OTPResponse:
    person, created = await get_or_create(db, email=body.email, name=body.name)
    ip = _client_ip(request)

    code = await generate_otp(db, person_id=person.id, purpose="login", ip_address=ip)
    if not code:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests. Please wait before trying again.",
        )

    await audit_svc.record_auth(db, action="otp_requested", person_id=person.id, ip=ip)
    await db.commit()

    email_sent = await send_otp_email(body.email, code)
    log.info("auth.otp_requested", person_id=str(person.id), created=created, email_sent=email_sent)

    dev_otp = code if settings.environment == "development" else None
    return OTPResponse(sent=True, dev_otp=dev_otp)


# ── Verify OTP → issue session ─────────────────────────────────────────────

class OTPVerify(BaseModel):
    email: EmailStr
    code: str


class SessionResponse(BaseModel):
    token: str
    person_id: str
    roles: list[str]


@router.post("/verify-otp", response_model=SessionResponse)
async def verify_otp(
    body: OTPVerify,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    from esb.services.people import get_by_email
    person = await get_by_email(db, body.email)
    if not person:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    ip = _client_ip(request)
    ok = await validate_otp(db, person_id=person.id, code=body.code, purpose="login")
    if not ok:
        await audit_svc.record_auth(db, action="otp_failed", person_id=person.id, ip=ip)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired code.")

    token = await create_session(
        db,
        person_id=person.id,
        ip_address=ip,
        user_agent=request.headers.get("User-Agent"),
    )

    await audit_svc.record_auth(db, action="login", person_id=person.id, ip=ip)
    await db.commit()

    # Re-read roles from the session we just created (they're snapshotted there)
    from datetime import datetime, timezone

    from sqlalchemy import select

    from esb.models.user import RoleMembership
    now = datetime.now(timezone.utc)
    roles_q = await db.scalars(
        select(RoleMembership.role).where(
            RoleMembership.person_id == person.id,
            RoleMembership.effective_from <= now,
            RoleMembership.effective_until.is_(None),
        )
    )
    roles = [r.value for r in roles_q.all()]

    return SessionResponse(token=token, person_id=str(person.id), roles=roles)


# ── Step-up ───────────────────────────────────────────────────────────────────

class StepUpRequest(BaseModel):
    code: str


class StepUpResponse(BaseModel):
    token: str


@router.post("/step-up", response_model=StepUpResponse)
async def step_up(
    body: StepUpRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> StepUpResponse:
    ip = _client_ip(request)
    ok = await validate_otp(db, person_id=auth.person_id, code=body.code, purpose="step_up")
    if not ok:
        await audit_svc.record_auth(db, action="step_up_failed", person_id=auth.person_id, ip=ip)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired code.")

    token = await create_session(
        db,
        person_id=auth.person_id,
        ip_address=ip,
        is_step_up=True,
    )
    await audit_svc.record_auth(db, action="step_up_granted", person_id=auth.person_id, ip=ip)
    await db.commit()
    return StepUpResponse(token=token)


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    raw = request.headers.get("Authorization", "")
    if raw.startswith("Bearer "):
        token = raw[7:]
        await revoke_session(db, token)
    await db.commit()


# ── Me ────────────────────────────────────────────────────────────────────────

class MeResponse(BaseModel):
    person_id: str
    roles: list[str]
    is_step_up: bool


@router.get("/me", response_model=MeResponse)
async def me(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> MeResponse:
    return MeResponse(
        person_id=str(auth.person_id),
        roles=[r.value for r in auth.roles],
        is_step_up=auth.is_step_up,
    )
