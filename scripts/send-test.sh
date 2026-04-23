#!/usr/bin/env bash
# Send a test notification through the Notify API.
#
# Usage:
#   ./scripts/send-test.sh <recipient_id> [content] [--tts] [--channel whatsapp|sms|email ...]
#
# Env:
#   NOTIFY_URL   default: http://localhost:8000
#   CLIENT_ID    required if the recipient was created by a specific client
#
# Examples:
#   ./scripts/send-test.sh 4f3e...uuid "Hello **world**"
#   ./scripts/send-test.sh 4f3e...uuid "Audio test" --tts --channel whatsapp

set -euo pipefail

NOTIFY_URL="${NOTIFY_URL:-http://localhost:8000}"

if [ $# -lt 1 ]; then
  echo "usage: $0 <recipient_id> [content] [--tts] [--channel name ...]" >&2
  exit 1
fi

RECIPIENT_ID="$1"; shift
CONTENT="${1:-Notify test — **markdown** _works_ https://example.com}"
[ $# -gt 0 ] && shift || true

IS_TTS=false
CHANNELS_JSON="null"
CHANNELS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --tts) IS_TTS=true ;;
    --channel) shift; CHANNELS+=("\"$1\"") ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
  shift
done

if [ ${#CHANNELS[@]} -gt 0 ]; then
  CHANNELS_JSON="[$(IFS=,; echo "${CHANNELS[*]}")]"
fi

read -r -d '' BODY <<EOF || true
{
  "recipient_id": "$RECIPIENT_ID",
  "content": $(printf '%s' "$CONTENT" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))'),
  "is_tts": $IS_TTS,
  "channels": $CHANNELS_JSON
}
EOF

echo "POST $NOTIFY_URL/api/v1/notifications"
echo "$BODY"
echo
curl -sS -X POST "$NOTIFY_URL/api/v1/notifications" \
  -H 'Content-Type: application/json' \
  -d "$BODY" | python3 -m json.tool
