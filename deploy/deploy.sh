#!/usr/bin/env bash
# Rolling deploy for the ESB portal.
# Run from the server as the esb user (or as root — compose will still run correctly).
#
# Usage:
#   bash deploy/deploy.sh              # deploy from main
#   bash deploy/deploy.sh --no-pull    # rebuild without pulling (useful when git is ahead)
set -euo pipefail

APP_DIR="/home/esb/esb-portal"
COMPOSE="docker compose -f $APP_DIR/deploy/docker-compose.yml --project-directory $APP_DIR"
NO_PULL=0

for arg in "$@"; do
  [[ "$arg" == "--no-pull" ]] && NO_PULL=1
done

echo "==> [$(date '+%Y-%m-%d %H:%M:%S')] ESB Portal deploy started"

# ── 1. Pull latest code ───────────────────────────────────────────────────────
if [[ "$NO_PULL" -eq 0 ]]; then
  echo "==> Pulling latest code"
  git -C "$APP_DIR" pull --ff-only
fi

# ── 2. Verify secrets exist ───────────────────────────────────────────────────
ENV_FILE="$APP_DIR/.env.production"
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found. Run deploy/setup.sh first."
  exit 1
fi
if grep -q "CHANGE_ME" "$ENV_FILE"; then
  echo "ERROR: $ENV_FILE still has CHANGE_ME placeholder values. Fill them in first."
  exit 1
fi

# ── 3. Load POSTGRES_PASSWORD for compose (other secrets come from env_file) ─
set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a

# ── 4. Build images ───────────────────────────────────────────────────────────
echo "==> Building images"
$COMPOSE build --pull

# ── 5. Run migrations (one-shot container) ───────────────────────────────────
echo "==> Running Alembic migrations"
$COMPOSE run --rm migrate

# ── 6. Restart services ───────────────────────────────────────────────────────
echo "==> Starting services"
$COMPOSE up -d --remove-orphans backend frontend

# ── 7. Health check ──────────────────────────────────────────────────────────
echo "==> Waiting for health checks"
sleep 8
$COMPOSE ps
if $COMPOSE exec backend curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
  echo "==> Backend healthy"
else
  echo "WARNING: Backend health check failed — check logs: docker compose -f deploy/docker-compose.yml logs backend"
fi

echo "==> [$(date '+%Y-%m-%d %H:%M:%S')] Deploy complete"
