#!/usr/bin/env bash
# Tail all Notify service logs.
# Usage: ./scripts/logs.sh [service]
set -euo pipefail
if [ $# -ge 1 ]; then
  exec docker compose logs -f --tail=200 "$1"
fi
exec docker compose logs -f --tail=200 api worker-whatsapp worker-sms worker-email baileys
