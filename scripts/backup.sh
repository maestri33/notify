#!/usr/bin/env bash
# Snapshot Notify state (SQLite DB + Baileys auth) into a timestamped tarball.
#
# Usage: ./scripts/backup.sh [output_dir]
# Default output_dir: ./backups

set -euo pipefail

OUT_DIR="${1:-./backups}"
STAMP=$(date +%Y%m%d-%H%M%S)
TARGET="$OUT_DIR/notify-$STAMP.tar.gz"

mkdir -p "$OUT_DIR"

# Dump the SQLite DB via the api container (consistent backup via .backup)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo "[backup] dumping sqlite..."
docker compose exec -T api sh -c \
  'sqlite3 /app/data/notify.db ".backup /app/data/_backup.db" && cat /app/data/_backup.db' \
  > "$TMP/notify.db"
docker compose exec -T api rm -f /app/data/_backup.db || true

echo "[backup] copying baileys auth..."
docker compose cp baileys:/data/auth "$TMP/baileys-auth" || mkdir -p "$TMP/baileys-auth"

tar -czf "$TARGET" -C "$TMP" notify.db baileys-auth
echo "[backup] wrote $TARGET ($(du -h "$TARGET" | cut -f1))"
