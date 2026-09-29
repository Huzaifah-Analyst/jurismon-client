#!/bin/bash
# ====================================================================
# JurisMon Application Deploy
#
# Run as root after scripts/vps_setup.sh:
#     bash scripts/deploy.sh [git-repo-url]
#
# Idempotent: first run clones, later runs pull and restart.
# ====================================================================

set -euo pipefail

APP_USER="jurismon"
APP_DIR="/var/www/jurismon"
REPO_URL="${1:-${JURISMON_REPO:-}}"
BRANCH="${JURISMON_BRANCH:-master}"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() { echo ""; echo "=== $1 ==="; }

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root." >&2
    exit 1
fi

if [ ! -d "$APP_DIR" ]; then
    echo "$APP_DIR does not exist. Run scripts/vps_setup.sh first." >&2
    exit 1
fi

# --------------------------------------------------------------------
log "Fetching application code"
if [ -d "$APP_DIR/.git" ]; then
    sudo -u "$APP_USER" git -C "$APP_DIR" fetch --quiet origin
    sudo -u "$APP_USER" git -C "$APP_DIR" reset --hard "origin/$BRANCH"
    echo "Updated to $(sudo -u "$APP_USER" git -C "$APP_DIR" rev-parse --short HEAD)"
elif [ -n "$REPO_URL" ]; then
    sudo -u "$APP_USER" git clone --quiet --branch "$BRANCH" "$REPO_URL" "$APP_DIR/_checkout"
    shopt -s dotglob
    mv "$APP_DIR/_checkout"/* "$APP_DIR/"
    shopt -u dotglob
    rmdir "$APP_DIR/_checkout"
    chown -R "$APP_USER:$APP_USER" "$APP_DIR"
    echo "Cloned $REPO_URL"
else
    echo "No git repository here and no repo URL given." >&2
    echo "Usage: bash scripts/deploy.sh https://github.com/<owner>/jurismon.git" >&2
    exit 1
fi

# --------------------------------------------------------------------
log "Installing Python dependencies"
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

# --------------------------------------------------------------------
log "Installing Chromium for Playwright"
# The crawler falls back to a headless browser for JavaScript portals, so a
# missing browser silently costs us every dynamic source.
sudo -u "$APP_USER" "$APP_DIR/venv/bin/playwright" install chromium
echo "Chromium ready."

# --------------------------------------------------------------------
log "Checking environment configuration"
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    echo ""
    echo "!! A .env was created from .env.example and is NOT yet filled in."
    echo "!! The API will refuse to start until these are set:"
    echo "!!     APP_ENV=production"
    echo "!!     SECRET_KEY             (python3 -c \"import secrets; print(secrets.token_urlsafe(48))\")"
    echo "!!     ADMIN_PASSWORD_HASH    (python3 scripts/generate_admin_hash.py)"
    echo "!!     CORS_ALLOWED_ORIGINS   (https://jurismon.com)"
    echo "!!     SUPABASE_URL / SUPABASE_KEY"
    echo "!!     PAYPAL_* credentials"
    echo ""
    echo "Edit $APP_DIR/.env, then re-run this script."
    exit 1
fi
chmod 600 "$APP_DIR/.env"

missing=""
for key in APP_ENV SECRET_KEY ADMIN_PASSWORD_HASH; do
    value="$(grep -E "^${key}=" "$APP_DIR/.env" | cut -d= -f2- || true)"
    [ -z "$value" ] && missing="$missing $key"
done
if [ -n "$missing" ]; then
    echo "!! These are empty in .env and the API will not start:$missing" >&2
    exit 1
fi

# --------------------------------------------------------------------
log "Installing systemd service"
cp "$APP_DIR/deploy/jurismon.service" /etc/systemd/system/jurismon.service
systemctl daemon-reload
systemctl enable jurismon

# --------------------------------------------------------------------
log "Installing Nginx site"
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/jurismon
ln -sf /etc/nginx/sites-available/jurismon /etc/nginx/sites-enabled/jurismon
rm -f /etc/nginx/sites-enabled/default

if nginx -t; then
    systemctl reload nginx
    echo "Nginx reloaded."
else
    echo "Nginx config test failed - not reloading." >&2
    exit 1
fi

# --------------------------------------------------------------------
log "Starting the API"
systemctl restart jurismon
sleep 3

if ! systemctl is-active --quiet jurismon; then
    echo "Service failed to start. Recent log:" >&2
    journalctl -u jurismon -n 30 --no-pager >&2
    exit 1
fi

# --------------------------------------------------------------------
log "Verifying the service responds"
if curl -fsS --max-time 10 http://127.0.0.1:8000/api/sources > /dev/null; then
    echo "API responding on 127.0.0.1:8000"
else
    echo "API did not respond. Recent log:" >&2
    journalctl -u jurismon -n 30 --no-pager >&2
    exit 1
fi

# --------------------------------------------------------------------
cat <<DONE

====================================================================
 Deploy complete
====================================================================

 Commit    : $(sudo -u "$APP_USER" git -C "$APP_DIR" rev-parse --short HEAD 2>/dev/null || echo 'n/a')
 Service   : $(systemctl is-active jurismon)
 Logs      : journalctl -u jurismon -f
             /var/log/jurismon/api.log

 If TLS is not yet issued:
     certbot --nginx -d jurismon.com -d www.jurismon.com

 To apply database migrations:
     $APP_DIR/venv/bin/python scripts/run_migrations.py

 To run the crawler once by hand:
     sudo -u $APP_USER $APP_DIR/venv/bin/python $APP_DIR/scripts/run_crawler.py

DONE
