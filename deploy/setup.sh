#!/usr/bin/env bash
# One-time server setup for the ESB portal on esbcloud.
# Run as root: bash setup.sh
set -euo pipefail

REPO_URL="https://github.com/ajcrabill/gotb-esb-com.git"
APP_USER="esb"
APP_DIR="/home/esb/esb-portal"

echo "==> Creating system user $APP_USER"
if ! id "$APP_USER" &>/dev/null; then
  useradd -m -s /bin/bash "$APP_USER"
fi

echo "==> Cloning repo as $APP_USER"
if [ ! -d "$APP_DIR/.git" ]; then
  sudo -u "$APP_USER" git clone "$REPO_URL" "$APP_DIR"
else
  echo "    Repo already exists at $APP_DIR, skipping clone"
fi

echo "==> Creating .env.production (template)"
if [ ! -f "$APP_DIR/.env.production" ]; then
  cat > "$APP_DIR/.env.production" <<'EOF'
# ESB Portal — production secrets
# Fill in all values before starting the stack.

# Database (used by docker-compose to set POSTGRES_PASSWORD)
POSTGRES_PASSWORD=CHANGE_ME

# App
SECRET_KEY=CHANGE_ME
ENVIRONMENT=production
DOMAIN=gotb.effectiveschoolboards.com

# Stripe
STRIPE_SECRET_KEY=sk_live_CHANGE_ME
STRIPE_WEBHOOK_SECRET=whsec_CHANGE_ME
STRIPE_CONNECT_CLIENT_ID=ca_CHANGE_ME

# Dropbox Sign
DROPBOX_SIGN_API_KEY=CHANGE_ME
DROPBOX_SIGN_TEMPLATE_ID=CHANGE_ME
DROPBOX_SIGN_WEBHOOK_SECRET=CHANGE_ME

# Postmark (transactional email)
POSTMARK_SERVER_TOKEN=CHANGE_ME
EMAIL_FROM=portal@gotb.effectiveschoolboards.com
EOF
  chown "$APP_USER:$APP_USER" "$APP_DIR/.env.production"
  chmod 600 "$APP_DIR/.env.production"
  echo "    Created $APP_DIR/.env.production — fill in all CHANGE_ME values before deploying!"
else
  echo "    .env.production already exists, skipping"
fi

echo ""
echo "Setup complete. Next steps:"
echo "  1. Edit $APP_DIR/.env.production and fill in all secrets"
echo "  2. Run: bash $APP_DIR/deploy/deploy.sh"
