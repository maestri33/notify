#!/usr/bin/env bash
# =============================================================================
# Notify CLI — local install pointing at a remote Notify server
#
# Usage:
#   bash install_cli.sh                          # prompts for URL
#   bash install_cli.sh http://10.10.10.119:8000 # non-interactive
#
# What this script does:
#   1. Asks for (or accepts) the Notify API URL
#   2. Tests the connection — aborts if the server is unreachable
#   3. Installs the notify package in a venv at ~/.notify-cli/
#   4. Symlinks `notify` into ~/.local/bin (added to PATH if needed)
#   5. Saves NOTIFY_URL to ~/.notify.env so the CLI needs no env vars
#
# Requirements: Python 3.10+ and curl
# =============================================================================

set -euo pipefail

REPO_URL="https://github.com/maestri33/notify.git"
INSTALL_DIR="$HOME/.notify-cli"
VENV="$INSTALL_DIR/venv"
BIN_DIR="$HOME/.local/bin"
CONFIG_FILE="$HOME/.notify.env"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${GREEN}[notify-cli]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC}  $*"; }
die()  { echo -e "${RED}[error]${NC} $*" >&2; exit 1; }

# ── 1. get URL ────────────────────────────────────────────────────────────────
if [[ -n "${1:-}" ]]; then
    NOTIFY_URL="${1%/}"
else
    echo ""
    read -rp "  Notify API URL (e.g. http://10.10.10.119:8000): " NOTIFY_URL
    NOTIFY_URL="${NOTIFY_URL%/}"
fi

[[ -z "$NOTIFY_URL" ]] && die "URL cannot be empty."

# ── 2. test connection ────────────────────────────────────────────────────────
info "Testing connection to $NOTIFY_URL ..."
if ! curl -fsSL --max-time 6 "$NOTIFY_URL/health" >/dev/null 2>&1; then
    die "Cannot reach $NOTIFY_URL/health — is the server running and accessible?"
fi
info "Connection OK ✅"

# ── 3. check Python ───────────────────────────────────────────────────────────
PYTHON=""
for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" -c "import sys; print(sys.version_info >= (3,10))" 2>/dev/null || echo False)
        if [[ "$ver" == "True" ]]; then
            PYTHON="$candidate"
            break
        fi
    fi
done
[[ -z "$PYTHON" ]] && die "Python 3.10+ is required. Install it and re-run."
info "Using $($PYTHON --version)"

# ── 4. create venv + install package ─────────────────────────────────────────
info "Installing Notify CLI to $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
"$PYTHON" -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q "notify[cli] @ git+$REPO_URL"

# ── 5. symlink binary ─────────────────────────────────────────────────────────
mkdir -p "$BIN_DIR"
ln -sf "$VENV/bin/notify" "$BIN_DIR/notify"
info "Symlinked: $BIN_DIR/notify"

# ── 6. save config ────────────────────────────────────────────────────────────
cat > "$CONFIG_FILE" <<EOF
# Notify CLI config — edit NOTIFY_URL to point at a different server
NOTIFY_URL=$NOTIFY_URL
EOF
info "Config saved to $CONFIG_FILE"

# ── 7. PATH check ─────────────────────────────────────────────────────────────
if ! echo ":${PATH}:" | grep -q ":${BIN_DIR}:"; then
    warn "$BIN_DIR is not in your PATH. Add it:"
    if [[ "$SHELL" == *zsh* ]]; then
        warn "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc && source ~/.zshrc"
    else
        warn "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc && source ~/.bashrc"
    fi
    NOTIFY_BIN="$BIN_DIR/notify"
else
    NOTIFY_BIN="notify"
fi

# ── 8. smoke test ─────────────────────────────────────────────────────────────
echo ""
info "Running: notify status"
"$VENV/bin/notify" status

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Notify CLI installed successfully!          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  Server  →  $NOTIFY_URL"
echo "  Config  →  $CONFIG_FILE"
echo "  Binary  →  $BIN_DIR/notify"
echo ""
echo "  Usage:"
echo "    notify status"
echo "    notify recipients list"
echo "    notify groups list"
echo "    notify users get <jid>"
echo "    notify groups get <jid>"
echo "    notify groups members <jid>"
echo "    notify whatsapp validate <number>"
echo "    notify notifications send <id> \"Hello\" --channel whatsapp"
echo "    notify --json status     # machine-readable output"
echo "    notify --help"
echo ""
