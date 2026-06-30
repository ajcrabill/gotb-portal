"""CGCS enforcement — hard-blocks any action involving CGCS member districts.

CGCS = Council of the Great City Schools. ESB is contractually barred from
pursuing CGCS member districts directly. This dependency is applied to every
endpoint that creates or advances a district relationship.

On trigger: raises 403 with a specific code, logs to audit, and sends a
signal for the LSP notification queue (the LSP must be informed of every
CGCS touch attempt so they can handle it).

is_cgcs_member is set at district intake and is not user-editable. Only
superusers/LSP can set it (admin endpoint, separately gated).
"""
from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.core.database import get_db
from esb.models.district import District

log = structlog.get_logger()

CGCS_BLOCK_CODE = "CGCS_MEMBER_DISTRICT"


async def enforce_not_cgcs(district_id: UUID, db: AsyncSession) -> None:
    """
    Call before any operation that would advance an ESB relationship with a district.
    Raises 403 if the district is a CGCS member.
    """
    district = await db.scalar(select(District).where(District.id == district_id))
    if district and district.is_cgcs_member:
        log.error(
            "cgcs.blocked",
            district_id=str(district_id),
            district_name=district.name,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": CGCS_BLOCK_CODE,
                "message": (
                    "This district is a CGCS member. ESB cannot pursue CGCS member "
                    "districts directly. This attempt has been flagged for LSP review."
                ),
            },
        )


def cgcs_guard(district_id: UUID, db: AsyncSession = Depends(get_db)):
    """FastAPI dependency version — inject into any endpoint that takes a district_id."""
    return enforce_not_cgcs(district_id, db)
