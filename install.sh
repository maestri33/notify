#!/usr/bin/env bash
# =============================================================================
# Notify — native install script for a dedicated Ubuntu 24.04 LXC
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/maestri33/notify/main/install.sh | bash
#   # or, after cloning:
#   sudo bash install.sh
#
# What this script does:
#   1. Installs system deps (Python 3.12, Node 20, Redis, SQLite, ffmpeg)
#   2. Creates a dedicated `notify` system user
#   3. Installs the Python backend in a virtualenv at /opt/notify/.venv
#   4. Installs the Baileys Node.js sidecar at /opt/notify/baileys-sidecar
#   5. Writes /etc/notify.env with sensible defaults
#   6. Runs Alembic migrations
#   7. Creates and enables 6 systemd services:
#        notify-api, notify-worker-whatsapp, notify-worker-sms,
#        notify-worker-email, notify-baileys, (redis via apt)
#
# After install:
#   - Dashboard:   http://<host>:8000
#   - Baileys QR:  http://<host>:8000/baileys
#   - Config:      http://<host>:8000/config
#   - CLI:         notify --help  (runs as root or sudo -u notify)
# =============================================================================

set -euo pipefail

# ── config ────────────────────────────────────────────────────────────────────
NOTIFY_HOME="/opt/notify"
NOTIFY_USER="notify"
NOTIFY_DATA="/var/lib/notify"
VENV="$NOTIFY_HOME/.venv"
REPO_URL="https://github.com/maestri33/notify.git"
API_PORT="8000"
BAILEYS_PORT="3000"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[notify]${NC} $*"; }
warn()    { echo -e "${YELLOW}[warn]${NC}  $*"; }
die()     { echo -e "${RED}[error]${NC} $*" >&2; exit 1; }

[[ $EUID -ne 0 ]] && die "Run as root (sudo bash install.sh)"

# ── 1. system packages ────────────────────────────────────────────────────────
info "Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    python3.12 python3.12-venv python3.12-dev \
    python3-pip \
    redis-server \
    sqlite3 \
    ffmpeg \
    curl git ca-certificates gnupg \
    ufw

# Node 20 via NodeSource
if ! command -v node &>/dev/null || [[ $(node -v | cut -d. -f1 | tr -d 'v') -lt 20 ]]; then
    info "Installing Node.js 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - -qq
    apt-get install -y -qq nodejs
fi

info "Node $(node -v) | Python $(python3.12 --version) | Redis $(redis-server --version | awk '{print $3}')"

# ── 2. notify user + dirs ─────────────────────────────────────────────────────
info "Creating user and directories..."
id "$NOTIFY_USER" &>/dev/null || useradd --system --shell /bin/bash --home "$NOTIFY_HOME" "$NOTIFY_USER"
mkdir -p "$NOTIFY_DATA/auth" "$NOTIFY_DATA/backups"
chown -R "$NOTIFY_USER:$NOTIFY_USER" "$NOTIFY_DATA"

# ── 3. clone or update repo ───────────────────────────────────────────────────
if [[ -d "$NOTIFY_HOME/.git" ]]; then
    info "Updating existing repo at $NOTIFY_HOME..."
    sudo -u "$NOTIFY_USER" git -C "$NOTIFY_HOME" pull --ff-only
else
    info "Cloning repo to $NOTIFY_HOME..."
    # If we're already running from inside the cloned dir, copy instead
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -f "$SCRIPT_DIR/pyproject.toml" ]]; then
        info "Detected local clone at $SCRIPT_DIR — copying..."
        rsync -a --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
              --exclude='data/' --exclude='backups/' --exclude='.env' \
              "$SCRIPT_DIR/" "$NOTIFY_HOME/"
        chown -R "$NOTIFY_USER:$NOTIFY_USER" "$NOTIFY_HOME"
    else
        git clone "$REPO_URL" "$NOTIFY_HOME"
        chown -R "$NOTIFY_USER:$NOTIFY_USER" "$NOTIFY_HOME"
    fi
fi

# ── 4. python virtualenv + package ───────────────────────────────────────────
info "Installing Python package..."
sudo -u "$NOTIFY_USER" python3.12 -m venv "$VENV"
sudo -u "$NOTIFY_USER" "$VENV/bin/pip" install -q --upgrade pip
sudo -u "$NOTIFY_USER" "$VENV/bin/pip" install -q "$NOTIFY_HOME"

# symlink CLI to system path
ln -sf "$VENV/bin/notify" /usr/local/bin/notify
info "CLI available: $(notify --help | head -1)"

# ── 5. baileys sidecar ────────────────────────────────────────────────────────
info "Installing Baileys sidecar..."
cd "$NOTIFY_HOME/baileys-sidecar"
sudo -u "$NOTIFY_USER" npm install --omit=dev --no-audit --no-fund --silent
cd "$NOTIFY_HOME"

# ── 6. env file ──────────────────────────────────────────────────────────────
ENV_FILE="/etc/notify.env"
if [[ ! -f "$ENV_FILE" ]]; then
    info "Writing $ENV_FILE..."
    cat > "$ENV_FILE" <<EOF
# Notify environment — edit as needed, then: systemctl restart notify-api
DATABASE_URL=sqlite:///$NOTIFY_DATA/notify.db
REDIS_URL=redis://localhost:6379/0
BAILEYS_URL=http://localhost:$BAILEYS_PORT
APP_ENV=production
LOG_LEVEL=INFO
NOTIFY_URL=http://localhost:$API_PORT
EOF
    chmod 640 "$ENV_FILE"
    chown root:"$NOTIFY_USER" "$ENV_FILE"
    info "Created $ENV_FILE — review and adjust if needed."
else
    warn "$ENV_FILE already exists — skipping (not overwritten)."
fi

# ── 7. redis config ───────────────────────────────────────────────────────────
info "Configuring Redis..."
sed -i 's/^# appendonly no/appendonly yes/' /etc/redis/redis.conf 2>/dev/null || true
sed -i 's/^appendonly no/appendonly yes/' /etc/redis/redis.conf 2>/dev/null || true
systemctl enable --now redis-server

# ── 8. alembic migrations ─────────────────────────────────────────────────────
info "Running database migrations..."
mkdir -p "$NOTIFY_DATA"
chown "$NOTIFY_USER:$NOTIFY_USER" "$NOTIFY_DATA"
cd "$NOTIFY_HOME/backend"
sudo -u "$NOTIFY_USER" env \
    DATABASE_URL="sqlite:///$NOTIFY_DATA/notify.db" \
    REDIS_URL="redis://localhost:6379/0" \
    BAILEYS_URL="http://localhost:$BAILEYS_PORT" \
    "$VENV/bin/alembic" upgrade head
cd "$NOTIFY_HOME"

# ── 9. systemd services ───────────────────────────────────────────────────────
info "Installing systemd services..."

_service_backend() {
    local name="$1" cmd="$2" desc="$3"
    cat > "/etc/systemd/system/notify-${name}.service" <<EOF
[Unit]
Description=Notify — $desc
After=network.target redis-server.service notify-baileys.service
Wants=redis-server.service

[Service]
Type=simple
User=$NOTIFY_USER
WorkingDirectory=$NOTIFY_HOME/backend
EnvironmentFile=$ENV_FILE
ExecStart=$VENV/bin/$cmd
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=notify-$name

[Install]
WantedBy=multi-user.target
EOF
}

# API
_service_backend "api" \
    "uvicorn app.main:app --host 0.0.0.0 --port $API_PORT" \
    "FastAPI + Dashboard"

# Workers
_service_backend "worker-whatsapp" \
    "rq worker whatsapp --url \${REDIS_URL}" \
    "RQ worker (whatsapp)"

_service_backend "worker-sms" \
    "rq worker sms --url \${REDIS_URL}" \
    "RQ worker (sms)"

_service_backend "worker-email" \
    "rq worker email --url \${REDIS_URL}" \
    "RQ worker (email)"

# Baileys sidecar
cat > "/etc/systemd/system/notify-baileys.service" <<EOF
[Unit]
Description=Notify — Baileys WhatsApp sidecar
After=network.target

[Service]
Type=simple
User=$NOTIFY_USER
WorkingDirectory=$NOTIFY_HOME/baileys-sidecar
Environment=PORT=$BAILEYS_PORT
Environment=AUTH_DIR=$NOTIFY_DATA/auth
ExecStart=$(which node) index.js
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=notify-baileys

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

for svc in notify-baileys notify-api notify-worker-whatsapp notify-worker-sms notify-worker-email; do
    systemctl enable --now "$svc"
    info "  $svc → $(systemctl is-active $svc)"
done

# ── 10. firewall ──────────────────────────────────────────────────────────────
if command -v ufw &>/dev/null; then
    info "Configuring UFW..."
    ufw --force reset -q
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow 22/tcp
    ufw allow "$API_PORT/tcp"
    ufw --force enable
    warn "UFW enabled. Restrict port $API_PORT to your VPN subnet when ready:"
    warn "  ufw delete allow $API_PORT/tcp"
    warn "  ufw allow from <vpn-subnet> to any port $API_PORT"
fi

# ── done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Notify installed successfully!              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  Dashboard  →  http://$(hostname -I | awk '{print $1}'):$API_PORT"
echo "  CLI        →  notify --help"
echo "  Logs       →  journalctl -u notify-api -f"
echo ""
echo "  Next steps:"
echo "    1. Open the dashboard → /baileys and scan the WhatsApp QR"
echo "    2. Open the dashboard → /config and fill in SMTP / SMS / ElevenLabs"
echo "    3. Run: notify status"
echo ""
