# Notify

Internal multi-channel notification service. Accepts a recipient `external_id` + markdown content and routes to WhatsApp / SMS / Email automatically based on what the recipient has registered.

Consumed by internal apps over a VPN. No authentication.

## Stack

- **API / Dashboard**: FastAPI + SQLModel + Jinja2 + HTMX
- **Queue**: Redis + RQ (one worker per channel)
- **WhatsApp**: Baileys (Node.js sidecar, HTTP)
- **SMS**: [SMS Gateway for Android](https://docs.sms-gate.app/)
- **Email**: `aiosmtplib` (SMTP configured in dashboard)
- **TTS**: ElevenLabs (WhatsApp voice notes)

## Quick start

```bash
cp .env.example .env
docker compose up -d
# Open http://localhost:8000
```

First run: go to `/baileys` to scan the WhatsApp QR code, then `/config` to fill in SMTP, SMS Gateway, and ElevenLabs credentials.

If you prefer CLI pairing, run:

```bash
docker compose exec api notify whatsapp qr
```

This renders the WhatsApp pairing QR directly in the terminal (you can still save PNG with `--save`).

## Helper scripts

- `./scripts/send-test.sh <recipient_id> "msg"` — fire a test notification
- `./scripts/logs.sh [service]` — tail compose logs
- `./scripts/backup.sh [out_dir]` — snapshot SQLite + Baileys auth

## Docs

- [deploy.md](docs/deploy.md) — LXC on Proxmox deploy guide
- [SKILL.md](SKILL.md) — operational guide for AI agents using Notify
