# Notify

Internal multi-channel notification service. Accepts a recipient UUID + markdown content and routes to WhatsApp / SMS / Email automatically based on what the recipient has registered.

Consumed by internal apps over a VPN. No authentication.

## Stack

- **API / Dashboard**: FastAPI + SQLModel + Jinja2 + HTMX
- **Queue**: Redis + RQ (one worker per channel)
- **WhatsApp**: Baileys (Node.js sidecar, HTTP)
- **SMS**: [SMS Gateway for Android](https://docs.sms-gate.app/)
- **Email**: `aiosmtplib` (SMTP configured in dashboard)
- **TTS**: ElevenLabs (WhatsApp voice notes)

## Status

🚧 Under active development — see [specs/](specs/) for spec-driven design docs.

## Quick start

```bash
cp .env.example .env
docker compose up -d
# Open http://localhost:8000
```

First run: go to `/baileys` to scan the WhatsApp QR code, then `/config` to fill in SMTP, SMS Gateway, and ElevenLabs credentials.

## Helper scripts

- `./scripts/send-test.sh <recipient_id> "msg"` — fire a test notification
- `./scripts/logs.sh [service]` — tail compose logs
- `./scripts/backup.sh [out_dir]` — snapshot SQLite + Baileys auth

## Docs

- [deploy.md](docs/deploy.md) — LXC on Proxmox deploy guide
- [spec.md](specs/spec.md) — entities, API, routing logic
- [plan.md](specs/plan.md) — stack, architecture, sidecar contract
- [tasks.md](specs/tasks.md) — implementation phases
