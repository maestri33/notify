# Notify — AI Agent Skill Reference

Reference for an AI agent using the Notify CLI to send notifications and manage recipients.

---

## Quick reference — how the CLI works

**Inside Docker (preferred):**
```bash
docker compose exec api notify <command>
```

**From host (requires Notify installed locally):**
```bash
NOTIFY_URL=http://<host>:8001 notify <command>
```

---

## Recipients

Check if a contact exists (always do this before creating):
```bash
notify recipients check <phone_or_email>
```

Create a recipient:
```bash
notify recipients create <external_id> --phone <number> --email <email>
```

List all recipients:
```bash
notify recipients list
```

Update a recipient:
```bash
notify recipients update <id> --phone <number>
```

---

## Sending notifications

```bash
# Send to all available channels (auto-routed)
notify notifications send <external_id> "Message in **markdown**"

# Force a specific channel
notify notifications send <external_id> "msg" --channel whatsapp

# Voice note on WhatsApp (TTS), plain text on SMS and email simultaneously
notify notifications send <external_id> "msg" --tts

# With a media attachment
notify notifications send <external_id> "msg" --media https://example.com/img.jpg
```

---

## Check delivery

```bash
# Last 10 delivery logs for a recipient
notify notifications logs --recipient <external_id> -n 10

# Full detail for a specific log entry
notify notifications get <log_id>
```

---

## System status

```bash
notify status            # overall application health
notify whatsapp status   # WhatsApp connection state
```

---

## Rules the agent must follow

1. **Always `check` before `create`** — avoid creating duplicate recipients.
2. **`external_id` is the unique key** — use the user's ID from the calling application, not an internal Notify ID.
3. **`phone` handles both SMS and WhatsApp automatically** — one field covers both channels; do not create separate records for each.
4. **`--tts` is multi-channel** — it sends an audio voice note to WhatsApp and plain text to SMS and email in the same call.
5. **Media URLs must be publicly accessible** — no authentication, no signed URLs that expire in seconds.
6. **Check WhatsApp status before TTS or WhatsApp sends** — if `notify whatsapp status` is not `connected`, those sends will fail immediately. Alert the operator rather than retrying silently.
