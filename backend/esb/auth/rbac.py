from datetime import datetime, timezone
from functools import wraps
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.core.database import get_db
from esb.models.user import Person, RoleMembership, RoleType, UserSession


class AuthContext:
    def __init__(self, person_id: UUID, roles: set[RoleType], session_id: UUID, is_step_up: bool, email: str = "", name: str = ""):
        self.person_id = person_id
        self.roles = roles
        self.session_id = session_id
        self.is_step_up = is_step_up
        self.email = email
        self.name = name

    def has_role(self, *roles: RoleType) -> bool:
        return bool(self.roles & set(roles))

    def require_step_up(self) -> None:
        if not self.is_step_up:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This action requires step-up authentication.",
            )


# Deny-by-default: no role = no access.
# Every protected endpoint declares which roles may access it.
# Object-level authz is enforced in the service layer — "their districts only"
# is a server-side check, not a filter applied after the fact.

def require_roles(*allowed: RoleType):
    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, auth: AuthContext = Depends(get_auth_context), **kwargs):
            if not auth.has_role(*allowed):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions.",
                )
            return await fn(*args, auth=auth, **kwargs)
        return wrapper
    return decorator


async def get_auth_context(
    # token extracted from Authorization header by middleware
    token_hash: str,
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    now = datetime.now(timezone.utc)

    session = await db.scalar(
        select(UserSession).where(
            UserSession.token_hash == token_hash,
            UserSession.expires_at > now,
            UserSession.revoked_at.is_(None),
        )
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.")

    # Re-check roles against current memberships on every request.
    # If role_memberships changed since last_role_check, invalidate session.
    current_roles = await db.scalars(
        select(RoleMembership.role).where(
            RoleMembership.person_id == session.person_id,
            RoleMembership.effective_from <= now,
            RoleMembership.effective_until.is_(None),
        )
    )
    current_role_set = set(current_roles.all())
    snapshot_role_set = set(session.role_snapshot.get("roles", []))

    if current_role_set != snapshot_role_set:
        # Role changed since session was issued — force re-auth
        session.revoked_at = now
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalidated due to role change. Please log in again.",
        )

    person = await db.scalar(select(Person).where(Person.id == session.person_id))
    return AuthContext(
        person_id=session.person_id,
        roles=current_role_set,
        session_id=session.id,
        is_step_up=session.is_step_up,
        email=person.email if person else "",
        name=person.name if person else "",
    )


# Privilege escalation helpers
STEP_UP_REQUIRED_ACTIONS = {
    "flip_validation_flag",
    "access_finance",
    "access_superuser_settings",
    "issue_credential",
}
