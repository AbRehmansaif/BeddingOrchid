#!/usr/bin/env bash
# ==============================================================================
# BeddingOrchid Deployment & Update Script for Ubuntu / Debian VPS
# Path: /var/www/beddingorchid/deploy/scripts/deploy.sh
# Usage: sudo bash deploy/scripts/deploy.sh
# ==============================================================================

set -e # Exit immediately if a command exits with a non-zero status

APP_DIR="/var/www/beddingorchid"
VENV_DIR="$APP_DIR/.venv"
LOG_DIR="/var/log/beddingorchid"
RUN_DIR="/run/beddingorchid"

echo "=== [1/7] Navigating to Application Directory ==="
cd "$APP_DIR"

echo "=== [2/7] Ensuring Runtime and Log Directories Exist ==="
mkdir -p "$LOG_DIR" "$RUN_DIR" "$APP_DIR/media" "$APP_DIR/staticfiles"
chown -R www-data:www-data "$LOG_DIR" "$RUN_DIR" "$APP_DIR/media" "$APP_DIR/staticfiles"
chmod 755 "$RUN_DIR" "$LOG_DIR"

echo "=== [3/7] Setting Up Python Virtual Environment ==="
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt

echo "=== [4/7] Applying Database Migrations to PostgreSQL ==="
python manage.py migrate --noinput

echo "=== [5/7] Initializing Clean Store Baseline (No Dummy Data) ==="
python manage.py init_production_store --skip-admin

echo "=== [6/7] Collecting Static Files with WhiteNoise ==="
python manage.py collectstatic --noinput

echo "=== [7/7] Restarting Services ==="
systemctl daemon-reload
systemctl restart beddingorchid
if systemctl is-active --quiet beddingorchid-celery; then
    systemctl restart beddingorchid-celery
fi
if systemctl is-active --quiet beddingorchid-celerybeat; then
    systemctl restart beddingorchid-celerybeat
fi

nginx -t && systemctl reload nginx

echo "=== Deployment Completed Successfully! ==="
echo "Store URL: https://beddingorchid.com"

