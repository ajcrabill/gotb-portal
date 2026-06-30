"""Audit log service — the single write path for all audit entries.

Every action that matters writes here. Writes are fail-closed: if the audit
write fails, the triggering operation fails. This is intentional — a system
that can silently drop audit entries is not trustworthy.

The hash chain: each entry includes a hash of (prev_hash, action, resource_id,
occurred_at). This makes retroactive tampering detectable. An external anchor
(periodic hash publication to an immutable external system) closes the window
for undetectable in-place tampering.

PII rule: store actor/action/target references and hashes, never raw PII.
This allows erasure (GDPR right-to-erasure) to redact source records without
mutating audit rows (which are immutable by DB trigger).
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.models.audit import AuditLog

log = structlog.get_logger()

# Cached last entry hash (in-process; in production back with Redis)
_last_entry_hash: str | None = None


async def _get_last_hash(db: AsyncSession) -> str | None:
    """Get the hash of the most recent audit entry for chain continuity."""
    global _last_entry_hash
    if _last_entry_hash:
        return _last_entry_hash
    result = await db.scalar(
        select(AuditLog.entry_hash).order_by(AuditLog.occurred_at.desc()).limit(1)
    )
    _last_entry_hash = result
    return result


async def record(
    db: AsyncSession,
    *,
    action: str,
    resource_type: str,
    resource_id: UUID | None = None,
    actor_id: UUID | None = None,
    actor_role: str | None = None,
    actor_ip: str | None = None,
    payload: dict | None = None,
    pipeline_verdict: str | None = None,
    ruleset_version: str | None = None,
) -> AuditLog:
    """
    Write an audit entry. Raises on failure (fail-closed).

    payload is hashed before storage — raw PII never written to the audit log.
    """
    now = datetime.now(timezone.utc)
    prev_hash = await _get_last_hash(db)
    payload_hash = AuditLog.hash_payload(payload) if payload else None
    entry_hash = AuditLog.compute_entry_hash(
        prev_hash=prev_hash,
        action=action,
        resource_id=str(resource_id) if resource_id else None,
        occurred_at=now.isoformat(),
    )

    entry = AuditLog(
        actor_id=actor_id,
        actor_role=actor_role,
        actor_ip=actor_ip,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        payload_hash=payload_hash,
        event_meta={"context": payload.get("context")} if payload and "context" in payload else {},
        pipeline_verdict=pipeline_verdict,
        ruleset_version=ruleset_version,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
        occurred_at=now,
    )

    db.add(entry)
    try:
        await db.flush()
    except Exception as exc:
        log.error("audit.write_failed", action=action, error=str(exc))
        raise  # fail-closed: if the audit write fails, the caller fails

    global _last_entry_hash
    _last_entry_hash = entry_hash

    log.debug("audit.recorded", action=action, resource_type=resource_type)
    return entry


# ── Convenience helpers for common actions ────────────────────────────────────

async def record_auth(db: AsyncSession, *, action: str, person_id: UUID, ip: str | None) -> AuditLog:
    return await record(db, action=f"auth.{action}", resource_type="person",
                        resource_id=person_id, actor_id=person_id, actor_ip=ip)


async def record_role_change(
    db: AsyncSession,
    *,
    actor_id: UUID,
    target_person_id: UUID,
    role: str,
    change: str,  # "granted" | "revoked"
) -> AuditLog:
    return await record(
        db,
        action=f"role.{change}",
        resource_type="role_membership",
        resource_id=target_person_id,
        actor_id=actor_id,
        payload={"role": role, "target": str(target_person_id)},
    )


async def record_pipeline_result(
    db: AsyncSession,
    *,
    actor_id: UUID | None,
    resource_type: str,
    resource_id: UUID | None,
    passed: bool,
    held: bool,
    stage1_score: int,
    verdict: str,
    ruleset_version: str,
) -> AuditLog:
    action = "pipeline.passed" if passed else ("pipeline.held" if held else "pipeline.failed")
    return await record(
        db,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        actor_id=actor_id,
        pipeline_verdict=verdict,
        ruleset_version=ruleset_version,
        payload={"stage1_score": stage1_score, "passed": passed, "held": held},
    )
