# Notify

Internal multi-channel notification service. Send a recipient `external_id` + markdown content — Notify routes to **WhatsApp**, **SMS**, and **Email** automatically based on what each recipient has registered.

Consumed by internal apps over a VPN. No authentication.

## Install

**Servidor completo** (Ubuntu 24.04 LXC — API, sidecar, Redis, tudo):

```bash
curl -fsSL https://raw.githubusercontent.com/maestri33/notify/main/install.sh | bash
```

**CLI remota** (qualquer máquina com Python 3.10+ e curl):

```bash
curl -fsSL https://raw.githubusercontent.com/maestri33/notify/main/install_cli.sh | bash -s http://<ip-do-servidor>:8000
```

## Stack

| Layer | Technology |
|-------|-----------|
| **API / Dashboard** | FastAPI + SQLModel + Jinja2 + HTMX |
| **Database** | PostgreSQL 16 (via pgBouncer) |
| **Queue** | Redis + RQ (one worker per channel) |
| **WhatsApp** | [Baileys](https://github.com/whiskeysockets/baileys) (Node.js HTTP + WebSocket sidecar) |
| **SMS** | [SMS Gateway for Android](https://docs.sms-gate.app/) |
| **Email** | `aiosmtplib` (SMTP configured in dashboard) |
| **TTS** | ElevenLabs (WhatsApp voice notes) |

## Architecture

```
┌─────────┐   HTTP POST    ┌──────────────┐   RQ enqueue   ┌──────────┐
│  Client  │ ──────────────>│  FastAPI      │ ──────────────>│  Redis    │
│  (CLI)   │ <──────────────│  :80/:8000    │                │  :6379    │
└─────────┘   JSON response └──────┬───────┘                └─────┬─────┘
                                   │                              │
                                   │ HTTP                         │ dequeue
                                   ▼                              ▼
                          ┌────────────────┐          ┌──────────────────┐
                          │  Baileys        │          │  RQ Workers       │
                          │  Sidecar :3000  │          │  whatsapp | sms   │
                          │  (Node.js)      │          │  email            │
                          │                 │          └──────────────────┘
                          │  • WS events    │
                          │  • HTTP API     │
                          │  • SQLite auth  │
                          └────────────────┘
```

- **Baileys sidecar** handles all WhatsApp Web protocol — auth, messaging, groups, contacts
- **FastAPI** proxies sidecar REST API + reads shared SQLite DB for contacts/messages
- **WebSocket** (port 3000 `/ws`) pushes real-time events: `connection.update`, `messages.upsert`, `contacts.update`
- **CLI** talks to FastAPI via HTTP — works from any machine that can reach the server

## Quick start

### Native Ubuntu 24.04 LXC

```bash
curl -fsSL https://raw.githubusercontent.com/maestri33/notify/main/install.sh | bash
```

Installs everything: Python venv, Node.js sidecar, Redis, 5 systemd services, firewall rules.

After install:

```bash
notify status                   # check everything
notify whatsapp qr              # scan QR to pair WhatsApp
notify config set --smtp-...    # configure channels
```

### Docker

```bash
cp .env.example .env
docker compose up -d
# Open http://localhost:8000
```

First run: go to `/baileys` to scan the WhatsApp QR, then `/config` for SMTP / SMS / ElevenLabs.

### CLI only (remote client)

Install just the CLI pointing at an existing Notify server:

```bash
curl -fsSL https://raw.githubusercontent.com/maestri33/notify/main/install_cli.sh | bash
# Or: bash install_cli.sh http://10.10.10.119:8000
```

Requires Python 3.10+ and curl. Installs to `~/.notify-cli/`, symlinks to `~/.local/bin/notify`.

## CLI reference

```
notify [--json] COMMAND [ARGS...]
```

Pass `--json` before any command for machine-readable output.

### Status

```bash
notify status        # overall system health (API, Redis, WhatsApp, channels)
```

### Recipients

```bash
notify recipients list [--filter external_id]
notify recipients get <uuid>
notify recipients create <external_id> [--email E] [--phone P]
notify recipients update <uuid> [--email E] [--phone P]
notify recipients delete <uuid> [-y]
notify recipients revalidate <uuid>       # re-check WhatsApp registration
notify recipients check <phone-or-email>  # lookup by phone/email
```

### Notifications

```bash
notify notifications send <external_id> "content" [--tts] [--channel whatsapp] [--media URL]
notify notifications broadcast "content" --ids "id1,id2" [--tts] [--channel whatsapp]
notify notifications logs [--recipient ID] [--channel C] [--status S] [--since ISO] [--limit N]
notify notifications get <log-uuid>
```

### WhatsApp

```bash
notify whatsapp status          # connection state + JID
notify whatsapp qr [--save qr.png] [--terminal/--no-terminal]
notify whatsapp validate <number>     # check if number is on WhatsApp
notify whatsapp logout [-y]
notify whatsapp restart
notify whatsapp send-text <phone> "text"
notify whatsapp send-ptt <phone> --text "text to speak" [--audio-file ogg]
notify whatsapp broadcast "content" --phones "p1,p2" [--tts] [--media URL]
```

### Groups

```bash
notify groups list              # all groups (sorted by size)
notify groups get <jid>         # full metadata + participants
notify groups members <jid>     # member list only
notify groups contacts <jid>    # members with contact names
notify groups invite <jid>      # invite link
```

### Users

```bash
notify users get <jid>          # profile picture URLs, status, contact info
```

### Config

```bash
notify config get
notify config set --smtp-host ... --sms-url ... --el-api-key ...
```

## API endpoints

### REST (`/api/v1`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/status` | System health (API, Redis, WhatsApp, configs) |
| `GET` | `/check?phone=&email=` | Lookup phone/email in recipients |
| `GET` | `/skill` | Return SKILL.md — AI agent integration guide |
| `GET` | `/recipients` | List recipients |
| `GET` | `/recipients/{id}` | Get recipient by UUID |
| `POST` | `/recipients` | Create recipient (strict validation) |
| `PATCH` | `/recipients/{id}` | Update recipient channels |
| `DELETE` | `/recipients/{id}` | Delete recipient |
| `POST` | `/recipients/{id}/revalidate` | Re-check WhatsApp validity |
| `POST` | `/notifications` | Send notification |
| `POST` | `/notifications/broadcast` | Send to multiple recipients |
| `GET` | `/notifications` | List notification logs |
| `GET` | `/notifications/{log_id}` | Get log entry |
| `GET/PUT` | `/config` | Read/update service config |

### WhatsApp (`/api/v1/whatsapp`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/status` | Connection state + JID |
| `GET` | `/qr?fmt=png\|base64` | QR code for pairing |
| `POST` | `/validate` | Check if number is on WhatsApp `{"phone":"..."}` |
| `POST` | `/logout` | Disconnect (re-pair needed) |
| `POST` | `/restart` | Restart sidecar |
| `POST` | `/send/text` | Send text to phone `{"phone","text"}` |
| `POST` | `/send/ptt` | Send voice note to phone `{"phone","audio_base64?","text?"}` |
| `POST` | `/broadcast` | Send to multiple phones `{"phones","content","is_tts?","media_urls?"}` |
| `GET` | `/contacts?q=&limit=&offset=` | List/search contacts |
| `GET` | `/contacts/{jid}` | Get contact by JID |
| `GET` | `/messages?jid=&limit=&offset=` | List messages |
| `GET` | `/messages/{msg_id}` | Get message by ID |
| `GET` | `/stats` | Contact + message counts |
| `GET` | `/groups` | List all WhatsApp groups |
| `GET` | `/groups/{jid}` | Group metadata + participants |
| `GET` | `/groups/{jid}/members` | Members only |
| `GET` | `/groups/{jid}/members/contacts` | Members with contact names |
| `GET` | `/groups/{jid}/invite` | Invite code + link |
| `GET` | `/users/{jid}` | Profile picture URLs, status, contact |

### WebSocket (sidecar, port 3000)

Connect to `ws://<host>:3000/ws` — receives real-time events:

| Event | Payload |
|-------|---------|
| `connection.update` | `{status, jid, deviceName, lastSeen}` |
| `messages.upsert` | `{messages: [...]}` |
| `contacts.update` | `{contacts: [...]}` |
| `creds.update` | `{me: "jid"}` |

### Sidecar REST (port 3000, internal)

Direct access to the Node.js sidecar — normally consumed via FastAPI proxy:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/status` | Connection state |
| `GET` | `/qr` | QR PNG |
| `POST` | `/validate` | `{"number":"..."}` → `{exists, jid}` |
| `POST` | `/send/text` | `{"jid","text"}` → `{message_id}` |
| `POST` | `/send/text/phone` | `{"phone","text"}` → `{message_id, jid}` |
| `POST` | `/send/ptt` | `{"jid","audio_base64"}` → voice note |
| `POST` | `/send/ptt/phone` | `{"phone","audio_base64"}` → `{message_id, jid}` |
| `POST` | `/send/media` | `{"jid","url"/"base64","mimetype","caption"}` |
| `POST` | `/broadcast/text` | `{"phones", "text"}` → `{results}` |
| `POST` | `/broadcast/ptt` | `{"phones", "audio_base64"}` → `{results}` |
| `GET` | `/contacts` | List/search contacts |
| `GET` | `/messages` | List messages |
| `GET` | `/groups` | List all groups |
| `GET` | `/groups/{jid}` | Group metadata |
| `GET` | `/groups/{jid}/members` | Members |
| `GET` | `/groups/{jid}/invite` | Invite code |
| `GET` | `/users/{jid}` | Profile picture + status + contact |
| `GET` | `/logs` | Ring-buffer log lines |
| `POST` | `/logout` | Disconnect |
| `POST` | `/restart` | Restart socket |

## Management

### systemd (native install)

```bash
systemctl status notify-api notify-baileys
journalctl -u notify-api -f
systemctl restart notify-api
```

### Docker

```bash
docker compose logs -f api baileys
docker compose restart api
```

## Data

- **App DB**: PostgreSQL `10.10.10.135:6432/main_app`, schema `notify` (recipients, notification_logs, service_config, email_template)
- **Baileys DB**: `/var/lib/notify/baileys.db` (SQLite — auth creds, keys, contacts, messages)
- **Baileys auth**: `/var/lib/notify/auth/` (file-based fallback, migrated to SQLite on first run)
- **Redis**: append-only at default path (survives restarts)

## Docs

- [deploy.md](docs/deploy.md) — LXC on Proxmox deploy guide
- [SKILL.md](SKILL.md) — operational guide for AI agents using Notify
