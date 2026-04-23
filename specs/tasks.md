# Notify — Tasks

Ordem sugerida, cada task entregável e testável.

## Fase 0 — Setup

- [ ] **T0.1** Inicializar repo: `pyproject.toml`, `.gitignore`, `.env.example`, `README.md` mínimo
- [ ] **T0.2** `docker-compose.yml` com redis + postgres (ou só redis se SQLite) + placeholders dos apps
- [ ] **T0.3** FastAPI hello world + health check `/health`
- [ ] **T0.4** Configurar Alembic + migração vazia inicial

## Fase 1 — Modelos e persistência

- [ ] **T1.1** Models: Client, Recipient, NotificationLog, EmailTemplate, ServiceConfig (SQLModel)
- [ ] **T1.2** Migração Alembic criando as tabelas
- [ ] **T1.3** Seed: EmailTemplate id=1 default + ServiceConfig id=1 vazio
- [ ] **T1.4** DB session dependency no FastAPI

## Fase 2 — API CRUD básico

- [ ] **T2.1** Endpoints `/clients` (POST, GET, DELETE)
- [ ] **T2.2** Endpoints `/recipients` (POST, GET, PATCH, DELETE) — sem validação WhatsApp ainda
- [ ] **T2.3** Normalização: whatsapp `"5543996648750"` → `"554396648750@s.whatsapp.net"`; phone_sms strip de `55`
- [ ] **T2.4** Tests: CRUD happy path + upsert por (client_id, external_id)

## Fase 3 — Baileys sidecar

- [ ] **T3.1** `baileys-sidecar/` — Express + @whiskeysockets/baileys, persistência em `/data/auth`
- [ ] **T3.2** Endpoints: `/status`, `/qr`, `/validate`, `/send/text`, `/send/media`, `/send/ptt`
- [ ] **T3.3** Dockerfile + adicionar ao compose
- [ ] **T3.4** Teste manual: escanear QR, enviar mensagem de teste
- [ ] **T3.5** Integrar `onWhatsApp()` no POST /recipients — popular `whatsapp_valid`

## Fase 4 — Queue + router

- [ ] **T4.1** Setup RQ: 3 queues (`whatsapp`, `sms`, `email`), workers Docker separados
- [ ] **T4.2** Serviço `router.py`: dado recipient + request, retorna lista de canais
- [ ] **T4.3** Endpoint `POST /notifications` → cria logs em `queued` + enfileira jobs
- [ ] **T4.4** Job genérico com retry (3x, backoff 60/300/900s), atualiza status do log

## Fase 5 — Canais

- [ ] **T5.1** `services/markdown.py` — md → HTML (markdown-it-py) + md → WA format
- [ ] **T5.2** `services/whatsapp.py` + job `send_whatsapp` — texto, mídia por URL, PTT
- [ ] **T5.3** `services/tts.py` — ElevenLabs API, retorna .ogg opus base64
- [ ] **T5.4** Integrar TTS no fluxo WhatsApp quando `is_tts=true`
- [ ] **T5.5** `services/sms.py` + job `send_sms` — POST SMS Gateway, basic auth, strip markdown
- [ ] **T5.6** `services/email.py` + job `send_email` — renderiza Jinja2 template, envia via `aiosmtplib` usando creds de ServiceConfig
- [ ] **T5.7** Anexos: download de `media_urls`, inline em email / anexo em WA

## Fase 6 — Dashboard

- [ ] **T6.1** Mount Jinja2 + HTMX + Pico.css em `/`
- [ ] **T6.2** Home: tabela últimas 100 notificações (auto-refresh HTMX 5s)
- [ ] **T6.3** Página Clients: listar, criar, deletar
- [ ] **T6.4** Página Recipients: busca + form edição
- [ ] **T6.5** Página Logs: filtros (client, channel, status, data) + paginação
- [ ] **T6.6** Página Email Template: editor (textarea subject + html), preview renderizado, salvar
- [ ] **T6.7** Página Service Config: form editável com seções (ElevenLabs, SMS Gateway, SMTP, IMAP) + botão "testar conexão" para cada seção
- [ ] **T6.8** Página Baileys `/baileys`:
  - Proxy endpoints no backend: `GET /dashboard/baileys/status`, `/qr`, `/logs` chamam o sidecar
  - Template com estado reativo (HTMX `hx-get` + `hx-trigger="every 3s"`)
  - Estado `qr_pending`: renderiza `<img src="/dashboard/baileys/qr">` com polling
  - Estado `connected`: card com JID + device + botões Desconectar/Reconectar
  - Painel de logs do sidecar (últimas 50 linhas, auto-scroll)

## Fase 7 — Deploy

- [ ] **T7.1** Docker images finais (backend, baileys) — multi-stage build
- [ ] **T7.2** Compose production com volumes para: postgres/sqlite, baileys auth, redis
- [ ] **T7.3** Provisionar LXC no Proxmox, instalar Docker
- [ ] **T7.4** Primeiro deploy + escanear QR Baileys
- [ ] **T7.5** Preencher ServiceConfig pelo dashboard: SMTP, SMS Gateway, ElevenLabs
- [ ] **T7.6** Smoke test dos 3 canais com recipient real

## Fase 8 — Polish

- [ ] **T8.1** README com setup + diagrama
- [ ] **T8.2** Backup automático do SQLite (ou dump postgres) para volume externo
- [ ] **T8.3** Logrotate / retenção de NotificationLog (cron: apagar > 90 dias)
- [ ] **T8.4** Script `./scripts/send-test.sh` para teste rápido de cada canal

## Dúvidas em aberto (resolver no caminho)

- SQLite vs Postgres para v1 — proposta: começar SQLite
- SMS Gateway: já instalado no celular? IP/porta acessível do LXC? (config vai no dashboard)
- VPN: LXC já está na rede certa? IP fixo?
