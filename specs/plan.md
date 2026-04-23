# Notify — Implementation Plan

## Stack

- **Backend**: Python 3.12 + FastAPI + SQLModel (SQLAlchemy + Pydantic)
- **DB**: PostgreSQL 16 (LXC) — alternativa: SQLite se quiser simplificar v1
- **Queue**: Redis 7 + RQ
- **Dashboard**: Jinja2 + HTMX + Pico.css (zero JS build step)
- **WhatsApp**: Baileys (Node.js) como sidecar HTTP
- **SMS**: SMS Gateway for Android (HTTP externo)
- **Email**: `aiosmtplib` + stdlib `email.message` (SMTP configurado via dashboard)
- **TTS**: ElevenLabs API (httpx)
- **Markdown**: `markdown-it-py` (HTML) + conversor custom WA
- **Deploy**: Docker Compose no LXC Ubuntu 24.04

## Arquitetura

```
┌─────────────┐      ┌──────────────────────────────┐
│  App cliente├─────▶│ FastAPI (api + dashboard)    │
└─────────────┘      │  :8000                       │
                     └──────┬───────────────────────┘
                            │ enqueue
                            ▼
                     ┌──────────────┐
                     │  Redis       │
                     └──────┬───────┘
                            │ RQ
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
     ┌──────────┐   ┌──────────┐   ┌──────────┐
     │ worker   │   │ worker   │   │ worker   │
     │ whatsapp │   │ sms      │   │ email    │
     └────┬─────┘   └────┬─────┘   └────┬─────┘
          │              │              │
          ▼              ▼              ▼
   ┌───────────┐   ┌──────────┐   ┌───────────┐
   │ Baileys   │   │ SMS GW   │   │ SMTP ext. │
   │ (Node)    │   │ Android  │   │ (aiosmtp) │
   │ HTTP:3000 │   │ HTTP     │   │           │
   └───────────┘   └──────────┘   └───────────┘
```

Containers no compose:
- `api` (FastAPI)
- `worker-whatsapp` (RQ, concurrency=1)
- `worker-sms` (RQ, concurrency=2)
- `worker-email` (RQ, concurrency=4)
- `baileys` (Node.js sidecar)
- `redis`
- `postgres`

## Estrutura de pastas

```
notify/
├── docker-compose.yml
├── .env.example
├── pyproject.toml
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + mount dashboard
│   │   ├── config.py            # Settings (env vars + ServiceConfig DB)
│   │   ├── db.py                # engine, session
│   │   ├── models/
│   │   │   ├── client.py
│   │   │   ├── recipient.py
│   │   │   ├── notification_log.py
│   │   │   ├── email_template.py
│   │   │   └── service_config.py
│   │   ├── api/
│   │   │   ├── clients.py
│   │   │   ├── recipients.py
│   │   │   └── notifications.py
│   │   ├── services/
│   │   │   ├── router.py        # decide canais
│   │   │   ├── whatsapp.py      # client Baileys HTTP
│   │   │   ├── sms.py           # client SMS Gateway
│   │   │   ├── email.py         # wrapper Himalaya
│   │   │   ├── tts.py           # ElevenLabs
│   │   │   └── markdown.py      # md → WA + md → HTML
│   │   ├── workers/
│   │   │   ├── queue.py         # RQ setup
│   │   │   └── jobs.py          # send_whatsapp, send_sms, send_email
│   │   └── dashboard/
│   │       ├── routes.py
│   │       └── templates/
│   └── alembic/
├── baileys-sidecar/
│   ├── package.json
│   ├── index.js                 # Express + Baileys, endpoints: /send, /validate, /qr, /status
│   └── Dockerfile
└── specs/
    ├── spec.md
    ├── plan.md
    └── tasks.md
```

## Baileys sidecar (contrato HTTP)

- `GET /status` → `{state: "disconnected|qr_pending|connecting|connected", jid?, device_name?, last_seen?}`
- `GET /qr` → PNG do QR code atual (404 se já conectado)
- `POST /logout` → desconecta + apaga credenciais em `/data/auth`
- `POST /restart` → restart soft da conexão (sem apagar sessão)
- `GET /logs?limit=50` → últimas N linhas do log do sidecar (ring buffer)
- `POST /validate` `{number:"5543996648750"}` → `{exists, jid}`
- `POST /send/text` `{jid, text}` → `{message_id}`
- `POST /send/media` `{jid, url|base64, caption?, mimetype}` → `{message_id}`
- `POST /send/ptt` `{jid, audio_base64}` → `{message_id}`

Persistência de sessão em volume Docker (`/data/auth`).

## Config precedence

1. `.env` → **apenas** conexões internas (DATABASE_URL, REDIS_URL, BAILEYS_URL). Nada de credenciais externas.
2. `ServiceConfig` (DB, editável via dashboard) → **todas** as credenciais/tokens externos: SMTP, IMAP, SMS Gateway, ElevenLabs.

Helper `get_service_config()` cacheado com invalidação ao salvar no dashboard.

## Migrations

Alembic. Migração inicial cria todas as tabelas + seed:
- `EmailTemplate` id=1 com template default
- `ServiceConfig` id=1 vazio

## Testes

- `pytest` para API + router (mocks dos canais)
- Testes E2E manuais para canais reais (test recipient)

## Open items (decidir durante implementação)

- **PostgreSQL vs SQLite**: sugiro SQLite para v1 (menos 1 container, backup = 1 arquivo). Upgrade fácil depois.
- **Validação JID em PATCH**: revalidar apenas se `whatsapp` mudou (optimization)
- **Markdown → WhatsApp**: pacote `python-markdown-whatsapp` não existe maduro; provavelmente conversor custom de 50 linhas
