#!/bin/bash
# ====================================================================
# JurisMon VPS Provisioning & Hardening (Ubuntu 22.04 / 24.04 LTS)
#
# Run once, as root, on a fresh server:
#     bash scripts/vps_setup.sh
#
# Idempotent - safe to re-run. Does not deploy the application itself;
# run scripts/deploy.sh for that.
# ====================================================================

set -euo pipefail

APP_USER="jurismon"
APP_DIR="/var/www/jurismon"
DOMAIN="${JURISMON_DOMAIN:-jurismon.com}"
STEPS=9

log() { echo ""; echo "=== [$1/$STEPS] $2 ==="; }

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root." >&2
    exit 1
fi

. /etc/os-release
echo "Detected: ${PRETTY_NAME:-unknown}"
if [ "${ID:-}" != "ubuntu" ]; then
    echo "WARNING: written for Ubuntu. Continuing anyway." >&2
fi

# --------------------------------------------------------------------
log 1 "Updating system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get upgrade -y

# --------------------------------------------------------------------
log 2 "Installing core dependencies, OCR and Nginx"
apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    git \
    curl \
    ufw \
    fail2ban \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    poppler-utils \
    nginx \
    certbot \
    python3-certbot-nginx

tesseract --version | head -1

# --------------------------------------------------------------------
log 3 "Ensuring swap space"
# Chromium and OCR can peak well past 4GB of RAM together. Without swap
# the kernel OOM-kills the crawler mid-run.
if swapon --show | grep -q '/swapfile'; then
    echo "Swap already configured:"
    swapon --show
else
    fallocate -l 4G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    sysctl -w vm.swappiness=10
    grep -q 'vm.swappiness' /etc/sysctl.conf || echo 'vm.swappiness=10' >> /etc/sysctl.conf
    echo "4G swap file created."
fi

# --------------------------------------------------------------------
log 4 "Configuring firewall (UFW)"
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
ufw status verbose

# --------------------------------------------------------------------
log 5 "Enabling Fail2Ban"
systemctl enable fail2ban
systemctl restart fail2ban

# --------------------------------------------------------------------
log 6 "Creating application user"
if id "$APP_USER" &>/dev/null; then
    echo "User '$APP_USER' already exists."
else
    adduser --disabled-password --gecos "" "$APP_USER"
    echo "User '$APP_USER' created."
fi

install -d -o "$APP_USER" -g "$APP_USER" -m 700 "/home/$APP_USER/.ssh"
if [ -s /root/.ssh/authorized_keys ]; then
    cp /root/.ssh/authorized_keys "/home/$APP_USER/.ssh/authorized_keys"
    chown "$APP_USER:$APP_USER" "/home/$APP_USER/.ssh/authorized_keys"
    chmod 600 "/home/$APP_USER/.ssh/authorized_keys"
    echo "Authorized keys copied from root."
fi

# --------------------------------------------------------------------
log 7 "Hardening SSH"
# Disabling password logins is only safe once a key is actually installed,
# otherwise this locks everyone out of the server permanently.
SSHD_DROPIN="/etc/ssh/sshd_config.d/99-jurismon.conf"
mkdir -p /etc/ssh/sshd_config.d

if [ -s "/home/$APP_USER/.ssh/authorized_keys" ] || [ -s /root/.ssh/authorized_keys ]; then
    cat > "$SSHD_DROPIN" <<'SSHCONF'
# JurisMon SSH hardening
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
MaxAuthTries 3
SSHCONF
    if sshd -t; then
        systemctl reload ssh 2>/dev/null || systemctl reload sshd
        echo "Password authentication DISABLED. Key-based login only."
    else
        rm -f "$SSHD_DROPIN"
        echo "sshd config test failed - hardening reverted, password login left enabled." >&2
    fi
else
    echo "!! No SSH key found in /root/.ssh/authorized_keys or /home/$APP_USER/.ssh/"
    echo "!! Password authentication left ENABLED to avoid locking you out."
    echo "!! Install a key, then re-run this script to harden SSH."
fi

# --------------------------------------------------------------------
log 8 "Creating application directory and virtualenv"
install -d -o "$APP_USER" -g "$APP_USER" -m 755 "$APP_DIR"
install -d -o "$APP_USER" -g "$APP_USER" -m 755 /var/log/jurismon

if [ ! -d "$APP_DIR/venv" ]; then
    sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
    echo "Virtualenv created at $APP_DIR/venv"
fi

# Chromium's shared libraries must be present before Playwright can launch.
# Installed system-wide here so the deploy step only fetches the browser.
log 9 "Installing Playwright system libraries"
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet playwright
"$APP_DIR/venv/bin/playwright" install-deps chromium

# --------------------------------------------------------------------
cat <<DONE

====================================================================
 VPS provisioning complete
====================================================================

 Installed : Python, Tesseract OCR, Nginx, Certbot, Fail2Ban
 Swap      : $(swapon --show=SIZE --noheadings | head -1 | tr -d ' ')
 Firewall  : SSH + HTTP/HTTPS only
 App user  : $APP_USER
 App dir   : $APP_DIR

 Next steps:

   1. Point $DOMAIN at this server in Cloudflare (A record)

   2. Deploy the application:
        bash scripts/deploy.sh

   3. Issue the TLS certificate (PayPal webhooks require HTTPS):
        certbot --nginx -d $DOMAIN -d www.$DOMAIN

DONE
