#!/bin/bash
# ====================================================================
# JurisMon VPS Provisioning & Hardening Script (Ubuntu 24.04 LTS)
# ====================================================================

set -e

echo "=== [1/6] Updating System Packages ==="
apt-get update && apt-get upgrade -y

echo "=== [2/6] Installing Core Dependencies & OCR ==="
apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    curl \
    ufw \
    fail2ban \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
    nginx

echo "=== [3/6] Configuring Firewall (UFW) ==="
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow http
ufw allow https
ufw --force enable

echo "=== [4/6] Setting up Fail2Ban ==="
systemctl enable fail2ban
systemctl start fail2ban

echo "=== [5/6] Creating Application User ==="
if ! id "jurismon" &>/dev/null; then
    adduser --disabled-password --gecos "" jurismon
    usermod -aG sudo jurismon
    mkdir -p /home/jurismon/.ssh
    if [ -f /root/.ssh/authorized_keys ]; then
        cp /root/.ssh/authorized_keys /home/jurismon/.ssh/
        chown -R jurismon:jurismon /home/jurismon/.ssh
        chmod 700 /home/jurismon/.ssh
        chmod 600 /home/jurismon/.ssh/authorized_keys
    fi
fi

echo "=== [6/6] Creating App Directory & Virtualenv ==="
mkdir -p /var/www/jurismon
chown -R jurismon:jurismon /var/www/jurismon

echo "=== VPS Hardening & Base Setup Completed Successfully! ==="
echo "Next: Clone repository to /var/www/jurismon, configure .env, and start systemd service."
