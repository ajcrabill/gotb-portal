"""Session management — token lifecycle, revocation, role-change invalidation.

Session tokens are:
  - Generated with secrets.token_urlsafe(32) — 256-bit CSPRNG
  - Stored hashed (SHA-256); the plain token is only returned at creation
  - Re-validated against current role_memberships on every request (rbac.py)
  - Automatically invalidated if roles changed since last_role_check
  - Step-up sessions have shorter TTL and are revoked after a single privileged action
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.core.config import settings
from esb.models.user import RoleMembership, RoleType, UserSession

log = structlog.get_logger()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_session(
    db: AsyncSession,
    person_id: UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
    is_step_up: bool = False,
) -> str:
    """
    Create a new session. Returns the plain-text token (only time it exists in plain text).
    Caller must transmit it securely (HTTPS only, HttpOnly cookie or Authorization header).
    """
    now = datetime.now(timezone.utc)
    ttl = settings.session_ttl_step_up_seconds if is_step_up else settings.session_ttl_seconds
    token = secrets.token_urlsafe(32)

    # Snapshot current roles
    current_roles = await db.scalars(
        select(RoleMembership.role).where(
            and_(
                RoleMembership.person_id == person_id,
                RoleMembership.effective_from <= now,
                RoleMembership.effective_until.is_(None),
            )
        )
    )
    role_list = [r.value for r in current_roles.all()]

    session = UserSession(
        person_id=person_id,
        token_hash=_hash_token(token),
        role_snapshot={"roles": role_list, "snapshotted_at": now.isoformat()},
        is_step_up=is_step_up,
        expires_at=now + timedelta(seconds=ttl),
        last_role_check=now,
        created_at=now,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(session)
    await db.flush()

    log.info(
        "session.created",
        person_id=str(person_id),
        is_step_up=is_step_up,
        roles=role_list,
    )
    return token


async def revoke_session(db: AsyncSession, token: str) -> None:
    """Revoke a session by token (logout or security event)."""
    token_hash = _hash_token(token)
    session = await db.scalar(
        select(UserSession).where(UserSession.token_hash == token_hash)
    )
    if session and not session.revoked_at:
        session.revoked_at = datetime.now(timezone.utc)
        await db.flush()
        log.info("session.revoked", session_id=str(session.id))


async def revoke_all_sessions(db: AsyncSession, person_id: UUID) -> int:
    """Revoke all active sessions for a person (security event, role revocation)."""
    now = datetime.now(timezone.utc)
    sessions = await db.scalars(
        select(UserSession).where(
            and_(
                UserSession.person_id == person_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            )
        )
    )
    count = 0
    for s in sessions.all():
        s.revoked_at = now
        count += 1
    await db.flush()

    log.info("session.revoke_all", person_id=str(person_id), count=count)
    return count
