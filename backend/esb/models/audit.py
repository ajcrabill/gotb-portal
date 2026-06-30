import hashlib
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from esb.core.database import Base
from esb.models.base import UUIDMixin


class AuditLog(UUIDMixin, Base):
    """
    WORM audit log with hash-chaining and external anchoring (Sys-13 / M19).

    Stores actor/action/target references and hashes — NOT raw PII. This means
    erasure (GDPR/right-to-erasure) can redact source records without mutating
    audit rows. The 'holds IP/finance/PII' note means it can reference them
    (via IDs + hashes), hence the read-RBAC requirement.

    Writes are fail-closed: if the write fails, the triggering operation fails.
    Even Superuser access is read-only; Superuser read access is itself logged.
    Anonymous link reads and embed-API submissions also emit entries.
    """
    __tablename__ = "audit_log"

    # Who
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)  # None = public/system
    actor_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actor_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # What
    action: Mapped[str] = mapped_column(String(200), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(nullable=True)

    # Payload stored as hash only — never raw PII
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Pipeline verdict if this entry is content-pipeline-related
    pipeline_verdict: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ruleset_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Hash chain: entry_hash = SHA-256(prev_hash + action + resource_id + occurred_at)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # No updated_at — this table is append-only by policy and DB trigger

    @classmethod
    def compute_entry_hash(
        cls,
        prev_hash: str | None,
        action: str,
        resource_id: str | None,
        occurred_at: str,
    ) -> str:
        payload = f"{prev_hash or ''}:{action}:{resource_id or ''}:{occurred_at}"
        return hashlib.sha256(payload.encode()).hexdigest()

    @classmethod
    def hash_payload(cls, payload: dict) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()
