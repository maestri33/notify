# notify

Servico de notificacao multicanal para o ecossistema interno (Proxmox / DMZ).
Stack: **FastAPI + Tortoise ORM + Uvicorn + uv**, com **Claude Code ja configurado**
por dentro (memoria, regras, Context7, DeepSeek v4 Pro).

Dispara notificacoes via dois canais:
- **E-mail em massa** — Mail Merge API (`app/integrations/smtp.py`), CSV + Jinja2.
- **WhatsApp** — Evolution GO / whatsmeow (`app/integrations/whatsapp.py`), texto, midia, sticker.

> **Filosofia.** Cada microservico deve ser **generico, reutilizavel, simples e
> completo**. Cada servico tem o **seu proprio Claude Code** (com memoria propria),
> o **seu proprio banco**, e fala com os outros servicos via HTTP, fila ou webhook —
> nunca via banco compartilhado.

---

## Estrutura

```
.
├── .claude/                  # Claude Code: memoria + regras + modelo
├── .mcp.json                 # Context7 MCP
├── app/
│   ├── main.py               # FastAPI entrypoint, porta 80
│   ├── config.py             # pydantic-settings (inclui SMTP/WhatsApp)
│   ├── db.py                 # Tortoise init/close
│   ├── api/                  # routers HTTP (1 arquivo por feature)
│   ├── models/               # modelos Tortoise
│   ├── schemas/              # Pydantic request/response
│   ├── integrations/         # httpx, redis, rabbitmq, webhooks + clientes API externa
│   ├── workers/              # consumers de fila
│   └── utils/                # logging estruturado (structlog)
├── tests/
├── scripts/                  # dev.sh (rodar local), new_service.sh (clonar template)
├── pyproject.toml
├── Makefile
└── .env.example
```

Detalhes de **onde colocar cada coisa nova** estao em
`.claude/memory/conventions.md`.

---

## Como rodar

```bash
cp .env.example .env          # ajusta valores reais
uv sync
make dev                      # sobe na porta 80
```

O Claude Code deste servico:

```bash
export ANTHROPIC_BASE_URL="http://proxy.local:8787"
export ANTHROPIC_AUTH_TOKEN="..."
export CONTEXT7_API_KEY="..."

claude
```

---

## Contexto operacional (Proxmox / DMZ)

- Roda em LXC ou VM no Proxmox.
- Esta em **zona desmilitarizada** — sem firewall entre servicos internos.
- Ambiente e **dev**, mas **infra e real**: portas, hosts, banco.
- **Seguranca nao e prioridade agora** (auth, CORS, rate-limit).

## Comandos

```bash
make install     # uv sync
make dev         # uvicorn --reload na porta 80
make run         # uvicorn 2 workers
make test        # pytest
make lint        # ruff + mypy
make fmt         # ruff format
make migrate     # aerich migrate && upgrade
```

## Banco

Default: **SQLite** em `./data/app.db` (zero infra). Para trocar pra Postgres:

```env
DATABASE_URL=postgres://user:pass@db.proxmox.local:5432/notify
```

> **Lembrete arquitetural:** este banco e **so deste servico**. Outro servico
> que precise destes dados consulta pela API.

## Configuracao (env vars)

| Variavel                  | Descricao                          | Default                                   |
| ------------------------- | ---------------------------------- | ----------------------------------------- |
| `SERVICE_NAME`            | Nome do servico                    | `notify`                                  |
| `ENV`                     | Ambiente (`dev`, `staging`, `prod`) | `dev`                                    |
| `LOG_LEVEL`               | Nivel de log                       | `INFO`                                    |
| `PORT`                    | Porta HTTP                         | `80`                                      |
| `DATABASE_URL`            | Banco de dados                     | `sqlite://data/app.db`                    |
| `REDIS_URL`               | Redis (cache + pub/sub)            | `redis://localhost:6379/0`                |
| `AMQP_URL`                | RabbitMQ (mensageria)              | `amqp://guest:guest@localhost:5672/`      |
| `WEBHOOK_OUTBOUND_TIMEOUT_S` | Timeout de webhook              | `10`                                      |
| `SMTP_API_BASE_URL`       | Mail Merge API                     | `http://10.10.10.150`                     |
| `WHATSAPP_API_BASE_URL`   | Evolution GO API                   | `http://10.10.10.149`                     |
| `WHATSAPP_API_KEY`        | Chave da instancia WhatsApp        | —                                         |

## Integracoes ativas

| Modulo                            | Pra que                                  |
| --------------------------------- | ---------------------------------------- |
| `app/integrations/http_client.py` | Falar com outros microservices via HTTP   |
| `app/integrations/redis_client.py` | Cache + pub/sub leve                     |
| `app/integrations/messaging.py`   | RabbitMQ (eventos entre servicos)        |
| `app/integrations/webhooks.py`    | Receber e enviar webhooks                |
| `app/integrations/smtp.py`    | Mail Merge API — e-mail em massa (CSV)   |
| `app/integrations/whatsapp.py` | Evolution GO — WhatsApp (texto, midia)  |
| `app/workers/`                    | Consumers de fila / jobs em background   |

Detalhes de cada integracao (endpoints, auth, retry) estao em
`.claude/memory/integrations.md`.
