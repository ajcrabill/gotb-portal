#!/usr/bin/env bash
# DR backup — encrypted PostgreSQL dump with restore verification
# Usage: ./dr_backup.sh [--restore /path/to/backup.sql.gpg]
# Env vars: DATABASE_URL, BACKUP_PASSPHRASE, BACKUP_DIR (optional, default /var/backups/esb-portal)

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/esb-portal}"
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%SZ")
LOG_PREFIX="[dr_backup ${TIMESTAMP}]"

log() { echo "${LOG_PREFIX} $*" >&2; }
die() { log "ERROR: $*"; exit 1; }

# ── Parse args ────────────────────────────────────────────────────────────────

RESTORE_FILE=""
if [[ "${1:-}" == "--restore" ]]; then
  RESTORE_FILE="${2:-}"
  [[ -n "$RESTORE_FILE" ]] || die "--restore requires a file path"
fi

# ── Validate env ──────────────────────────────────────────────────────────────

[[ -n "${DATABASE_URL:-}" ]] || die "DATABASE_URL is not set"
[[ -n "${BACKUP_PASSPHRASE:-}" ]] || die "BACKUP_PASSPHRASE is not set"

which gpg  >/dev/null 2>&1 || die "gpg not found"
which psql >/dev/null 2>&1 || die "psql not found"
which pg_dump >/dev/null 2>&1 || die "pg_dump not found"

# ── Parse DATABASE_URL → psql args ───────────────────────────────────────────
# Handles: postgresql+asyncpg://... (strip driver suffix) and standard postgres://...

DB_URL="${DATABASE_URL/postgresql+asyncpg:\/\//postgresql:\/\/}"
DB_URL="${DB_URL/postgresql+psycopg2:\/\//postgresql:\/\/}"

# ── Restore mode ─────────────────────────────────────────────────────────────

if [[ -n "$RESTORE_FILE" ]]; then
  log "Starting restore from ${RESTORE_FILE}"
  [[ -f "$RESTORE_FILE" ]] || die "File not found: ${RESTORE_FILE}"

  RESTORE_TMP="$(mktemp /tmp/esb_restore_XXXXXX.sql)"
  trap 'rm -f "$RESTORE_TMP"' EXIT

  log "Decrypting backup…"
  gpg --quiet --batch --yes --passphrase "${BACKUP_PASSPHRASE}" \
      --output "$RESTORE_TMP" --decrypt "$RESTORE_FILE" \
      || die "Decryption failed"

  log "Restoring to database (this will OVERWRITE existing data)…"
  psql "${DB_URL}" < "$RESTORE_TMP" \
      || die "Restore failed"

  log "Restore complete."
  exit 0
fi

# ── Backup mode ───────────────────────────────────────────────────────────────

mkdir -p "$BACKUP_DIR"
DUMP_FILE="${BACKUP_DIR}/esb_portal_${TIMESTAMP}.sql"
ENC_FILE="${DUMP_FILE}.gpg"

log "Dumping database…"
pg_dump "${DB_URL}" \
  --format=plain \
  --no-password \
  --clean \
  --if-exists \
  --quote-all-identifiers \
  > "$DUMP_FILE" \
  || die "pg_dump failed"

DUMP_SIZE=$(du -sh "$DUMP_FILE" | cut -f1)
log "Dump size: ${DUMP_SIZE}"

log "Encrypting…"
gpg --quiet --batch --yes \
    --passphrase "${BACKUP_PASSPHRASE}" \
    --symmetric --cipher-algo AES256 \
    --output "$ENC_FILE" "$DUMP_FILE" \
    || die "Encryption failed"

# Remove plaintext dump immediately after encryption
rm -f "$DUMP_FILE"

ENC_SIZE=$(du -sh "$ENC_FILE" | cut -f1)
log "Encrypted backup: ${ENC_FILE} (${ENC_SIZE})"

# ── Restore verification (always run against a TEST database if available) ────

if [[ -n "${VERIFY_DATABASE_URL:-}" ]]; then
  log "Verifying backup against VERIFY_DATABASE_URL…"
  VERIFY_TMP="$(mktemp /tmp/esb_verify_XXXXXX.sql)"
  trap 'rm -f "$VERIFY_TMP"' EXIT

  gpg --quiet --batch --yes --passphrase "${BACKUP_PASSPHRASE}" \
      --output "$VERIFY_TMP" --decrypt "$ENC_FILE" \
      || die "Verification decrypt failed"

  VERIFY_DB_URL="${VERIFY_DATABASE_URL/postgresql+asyncpg:\/\//postgresql:\/\/}"
  psql "${VERIFY_DB_URL}" < "$VERIFY_TMP" \
      || die "Restore verification failed"

  # Spot-check: count tables
  TABLE_COUNT=$(psql "${VERIFY_DB_URL}" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d ' ')
  [[ "$TABLE_COUNT" -gt 0 ]] || die "Restore verification: no tables found in restored DB"

  log "Verification passed: ${TABLE_COUNT} tables restored"
  rm -f "$VERIFY_TMP"
else
  log "VERIFY_DATABASE_URL not set — skipping live restore check"
  log "  RECOMMENDATION: set VERIFY_DATABASE_URL in production to verify each backup"
fi

# ── Prune old backups (keep 30 days) ─────────────────────────────────────────

DELETED=0
while IFS= read -r old; do
  rm -f "$old"
  DELETED=$((DELETED + 1))
done < <(find "$BACKUP_DIR" -name "esb_portal_*.sql.gpg" -mtime +30 2>/dev/null)

[[ $DELETED -gt 0 ]] && log "Pruned ${DELETED} backup(s) older than 30 days"

# ── Manifest ──────────────────────────────────────────────────────────────────

MANIFEST="${BACKUP_DIR}/MANIFEST"
{
  echo "timestamp=${TIMESTAMP}"
  echo "file=${ENC_FILE}"
  echo "enc_size=${ENC_SIZE}"
  echo "dump_size_pre_encrypt=${DUMP_SIZE}"
  echo "verify=${VERIFY_DATABASE_URL:+passed}"
  echo "sha256=$(shasum -a 256 "${ENC_FILE}" | awk '{print $1}')"
} > "${MANIFEST}.tmp" && mv "${MANIFEST}.tmp" "$MANIFEST"

log "Backup complete: ${ENC_FILE}"
