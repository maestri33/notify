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
#   7. Creates and enables 5 systemd services:
#        notify-api, notify-worker-whatsapp, notify-worker-sms,
#        notify-worker-email, notify-baileys  (+ redis via apt)
#
# After install:
#   - Dashboard:   http://<host>:8000
#   - Baileys QR:  http://<host>:8000/baileys
#   - Config:      http://<host>:8000/config
#   - CLI:         notify --help
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
info() { echo -e "${GREEN}[notify]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC}  $*"; }
die()  { echo -e "${RED}[error]${NC} $*" >&2; exit 1; }

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
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y -qq nodejs
fi

info "Node $(node -v) | Python $(python3.12 --version) | Redis $(redis-server --version | awk '{print $3}')"

# ── 2. notify user + dirs ─────────────────────────────────────────────────────
info "Creating user and directories..."
id "$NOTIFY_USER" &>/dev/null || useradd --system --shell /bin/bash --home "$NOTIFY_HOME" "$NOTIFY_USER"
mkdir -p "$NOTIFY_DATA/auth" "$NOTIFY_DATA/backups" "$NOTIFY_HOME"
chown -R "$NOTIFY_USER:$NOTIFY_USER" "$NOTIFY_DATA" "$NOTIFY_HOME"

# ── 3. clone or update repo ───────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

git config --global --add safe.directory "$NOTIFY_HOME" 2>/dev/null || true

if [[ -d "$NOTIFY_HOME/.git" ]]; then
    info "Updating existing repo at $NOTIFY_HOME..."
    git -C "$NOTIFY_HOME" pull --ff-only
elif [[ -f "$SCRIPT_DIR/pyproject.toml" && "$SCRIPT_DIR" != "$NOTIFY_HOME" ]]; then
    info "Detected local clone at $SCRIPT_DIR — copying to $NOTIFY_HOME..."
    cp -a "$SCRIPT_DIR/." "$NOTIFY_HOME/"
    rm -rf "$NOTIFY_HOME/.venv" "$NOTIFY_HOME/data" "$NOTIFY_HOME/backups" \
           "$NOTIFY_HOME/.env"
    find "$NOTIFY_HOME" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
else
    info "Cloning from $REPO_URL..."
    git clone "$REPO_URL" "$NOTIFY_HOME"
fi
chown -R "$NOTIFY_USER:$NOTIFY_USER" "$NOTIFY_HOME"

# ── 4. python virtualenv + package ───────────────────────────────────────────
info "Installing Python package..."
python3.12 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q "$NOTIFY_HOME"
chown -R "$NOTIFY_USER:$NOTIFY_USER" "$VENV"

# symlink CLI to system path
ln -sf "$VENV/bin/notify" /usr/local/bin/notify

# make NOTIFY_URL available in every shell session
echo "export NOTIFY_URL=http://localhost:$API_PORT" > /etc/profile.d/notify.sh
chmod 644 /etc/profile.d/notify.sh

info "CLI installed → $(NOTIFY_URL=http://localhost:$API_PORT notify --version 2>/dev/null || echo ok)"

# ── 5. baileys sidecar ────────────────────────────────────────────────────────
info "Installing Baileys sidecar..."
cd "$NOTIFY_HOME/baileys-sidecar"
npm install --omit=dev --no-audit --no-fund --silent
chown -R "$NOTIFY_USER:$NOTIFY_USER" "$NOTIFY_HOME/baileys-sidecar/node_modules"
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
    info "Created $ENV_FILE"
else
    warn "$ENV_FILE already exists — skipping (not overwritten)."
fi

# ── 7. redis ──────────────────────────────────────────────────────────────────
info "Configuring Redis..."
if [[ -f /etc/redis/redis.conf ]]; then
    sed -i 's/^# appendonly no/appendonly yes/' /etc/redis/redis.conf || true
    sed -i 's/^appendonly no/appendonly yes/'   /etc/redis/redis.conf || true
fi
systemctl enable --now redis-server 2>/dev/null || true

# ── 8. alembic migrations ─────────────────────────────────────────────────────
info "Running database migrations..."
cd "$NOTIFY_HOME/backend"
DATABASE_URL="sqlite:///$NOTIFY_DATA/notify.db" \
REDIS_URL="redis://localhost:6379/0" \
BAILEYS_URL="http://localhost:$BAILEYS_PORT" \
    "$VENV/bin/alembic" upgrade head
cd "$NOTIFY_HOME"

# ── 9. systemd services ───────────────────────────────────────────────────────
info "Installing systemd services..."

_write_service() {
    local name="$1" desc="$2" cmd="$3" wdir="$4"
    cat > "/etc/systemd/system/notify-${name}.service" <<EOF
[Unit]
Description=Notify — $desc
After=network.target redis-server.service
Wants=redis-server.service

[Service]
Type=simple
User=$NOTIFY_USER
WorkingDirectory=$wdir
EnvironmentFile=$ENV_FILE
ExecStart=$cmd
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=notify-$name

[Install]
WantedBy=multi-user.target
EOF
}

_write_service "api" \
    "FastAPI + Dashboard" \
    "$VENV/bin/uvicorn app.main:app --host 0.0.0.0 --port $API_PORT" \
    "$NOTIFY_HOME/backend"

_write_service "worker-whatsapp" \
    "RQ worker (whatsapp)" \
    "$VENV/bin/rq worker whatsapp --url \${REDIS_URL}" \
    "$NOTIFY_HOME/backend"

_write_service "worker-sms" \
    "RQ worker (sms)" \
    "$VENV/bin/rq worker sms --url \${REDIS_URL}" \
    "$NOTIFY_HOME/backend"

_write_service "worker-email" \
    "RQ worker (email)" \
    "$VENV/bin/rq worker email --url \${REDIS_URL}" \
    "$NOTIFY_HOME/backend"

# Baileys — no EnvironmentFile, uses its own env vars
NODE_BIN="$(which node)"
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
ExecStart=$NODE_BIN index.js
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=notify-baileys

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload 2>/dev/null || true

FAILED=()
for svc in notify-baileys notify-api notify-worker-whatsapp notify-worker-sms notify-worker-email; do
    if systemctl enable --now "$svc" 2>/dev/null; then
        info "  ✅ $svc"
    else
        warn "  ⚠️  $svc — could not start (normal in containers; will start on boot)"
        FAILED+=("$svc")
    fi
done

# ── 10. firewall ──────────────────────────────────────────────────────────────
if command -v ufw &>/dev/null && [[ -z "${SKIP_UFW:-}" ]]; then
    info "Configuring UFW..."
    if ufw --force reset 2>/dev/null && \
       ufw default deny incoming 2>/dev/null && \
       ufw default allow outgoing 2>/dev/null && \
       ufw allow 22/tcp 2>/dev/null && \
       ufw allow "$API_PORT/tcp" 2>/dev/null && \
       ufw --force enable 2>/dev/null; then
        warn "UFW active. Restrict port $API_PORT to your VPN subnet when ready:"
        warn "  ufw delete allow $API_PORT/tcp && ufw allow from <vpn-subnet> to any port $API_PORT"
    else
        warn "UFW could not be configured (normal in containers — configure manually on the LXC)."
    fi
fi

# ── done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Notify installed successfully!              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || echo '<host>')"
echo "  Dashboard  →  http://$HOST_IP:$API_PORT"
echo "  CLI        →  notify --help"
echo "  Logs       →  journalctl -u notify-api -f"
echo ""
echo "  Next steps:"
echo "    1. Open /baileys in the dashboard and scan the WhatsApp QR"
echo "    2. Open /config and fill in SMTP / SMS Gateway / ElevenLabs"
echo "    3. Run: notify status"
if [[ ${#FAILED[@]} -gt 0 ]]; then
    echo ""
    warn "Services not started (start manually after boot):"
    for s in "${FAILED[@]}"; do warn "  systemctl start $s"; done
fi
echo ""
