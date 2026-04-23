# Notify — Spec

## 1. Visão geral

Serviço interno de notificações multi-canal (WhatsApp, SMS, Email). Recebe `recipient_id + content (markdown) + flags` e decide automaticamente quais canais usar com base nos dados cadastrados do recipient.

Consumido por múltiplos apps internos. Cada app gerencia seus próprios usuários e envia para o Notify apenas o UUID do usuário + conteúdo; o Notify resolve o resto.

Ambiente: LXC Ubuntu Server em Proxmox, acesso apenas via VPN, sem autenticação.

## 2. Atores e fluxo

### 2.1 App cliente (externo)
- Cria usuário no seu próprio sistema
- Chama `POST /recipients` com `external_id` (UUID do user) + email/phone/whatsapp
- Ao disparar notificação: `POST /notifications` com `external_id` + `content` + flags

### 2.2 Notify (este sistema)
1. Recebe notificação, resolve recipient pelo `external_id + client_id`
2. Determina canais disponíveis (email cadastrado? JID validado? número SMS?)
3. Enfileira job por canal (RQ)
4. Workers executam envio via Baileys / SMS Gateway / Himalaya
5. Grava log de status (metadados apenas)

## 3. Entidades

### 3.1 Client
```
id              UUID PK
name            str
created_at      datetime
```
Criado via dashboard. Usado apenas para namespace do `external_id`. Sem API key (rede fechada).

### 3.2 Recipient
```
id              UUID PK
client_id       FK Client
external_id     str        # UUID vindo do app cliente
email           str?
phone_sms       str?       # formato: DDD+9+numero, sem 55. Ex: 43996648750
whatsapp_jid    str?       # formato: 554396648750@s.whatsapp.net
whatsapp_valid  bool       # validado via Baileys onWhatsApp()
created_at      datetime
updated_at      datetime

UNIQUE(client_id, external_id)
```
Sem campo `name`.

### 3.3 NotificationLog
```
id                UUID PK
recipient_id      FK Recipient
client_id         FK Client
channel           enum(whatsapp, sms, email)
status            enum(queued, sending, sent, failed)
attempts          int
error_msg         str?
provider_msg_id   str?       # ID retornado pelo provider (para link com sqlite wacli, message-id email, etc)
is_tts            bool
created_at        datetime
updated_at        datetime
```

### 3.4 EmailTemplate (singleton)
```
id              int PK (sempre 1)
subject         str          # Jinja2
html_body       str          # Jinja2
updated_at      datetime
```
Variáveis disponíveis: `{{ content_html }}`, `{{ subject }}`.

### 3.5 ServiceConfig (singleton)
```
# ElevenLabs (TTS)
elevenlabs_api_key       str?
elevenlabs_voice_id      str?
elevenlabs_model_id      str        # default: "eleven_multilingual_v2"

# SMS Gateway for Android
sms_gateway_url          str?       # ex: http://192.168.1.50:8080
sms_gateway_user         str?
sms_gateway_pass         str?

# Email SMTP (envio)
smtp_host                str?
smtp_port                int        # default 587
smtp_user                str?
smtp_pass                str?
smtp_use_tls             bool       # default true
smtp_from_email          str?
smtp_from_name           str?

# Email IMAP (opcional — para futuro: ler respostas)
imap_host                str?
imap_port                int        # default 993
imap_user                str?
imap_pass                str?

updated_at               datetime
```
**Tudo editável no dashboard.** Nada de credenciais em `.env` — só conexões internas (Redis, DB, URL do Baileys sidecar).

## 4. API

Base: `/api/v1` — todos endpoints abertos (VPN).

### 4.1 Clients

- `POST /clients` — cria cliente. Body: `{name}`. Retorna `{id, name}`.
- `GET /clients` — lista.
- `DELETE /clients/{id}`

### 4.2 Recipients

- `POST /recipients`
  ```json
  {
    "client_id": "uuid",
    "external_id": "uuid-do-user-no-app",
    "email": "foo@bar.com",
    "phone_sms": "43996648750",
    "whatsapp": "5543996648750"
  }
  ```
  - Normaliza `whatsapp` para JID
  - Valida JID via Baileys `onWhatsApp()` — salva `whatsapp_valid`
  - Upsert por `(client_id, external_id)`
  - Retorna recipient com status de validação

- `GET /recipients?client_id=...&external_id=...` — busca
- `PATCH /recipients/{id}` — atualiza qualquer campo (revalida whatsapp se mudou)
- `DELETE /recipients/{id}`

### 4.3 Notifications

- `POST /notifications`
  ```json
  {
    "client_id": "uuid",
    "external_id": "uuid-do-user",
    "content": "Olá **fulano**, sua consulta foi confirmada.",
    "is_tts": false,
    "media_urls": ["https://..."],
    "channels": null
  }
  ```
  - `is_tts`: default false. Se true, WhatsApp envia PTT (áudio ElevenLabs) em vez de texto. SMS/email seguem com texto.
  - `media_urls`: opcional. Email embeda/anexa, WhatsApp anexa, SMS ignora.
  - `channels`: null = automático (todos disponíveis). Pode forçar `["email"]`, `["whatsapp","email"]`, etc.
  - Enfileira 1 job por canal elegível
  - Retorna `{notification_id, jobs: [{channel, log_id, status:"queued"}]}`

- `GET /notifications?client_id=&external_id=&channel=&status=&since=` — lista logs (paginado)
- `GET /notifications/{log_id}` — detalhe

## 5. Lógica de roteamento

Para cada notificação, determinar canais:

```
canais_elegíveis = []
se recipient.whatsapp_jid e recipient.whatsapp_valid: +whatsapp
se recipient.phone_sms: +sms
se recipient.email: +email

se request.channels: intersecção com canais_elegíveis
senão: todos canais_elegíveis

envia em paralelo (1 job RQ por canal)
```

**Sem fallback entre canais.** Cada canal é independente — se WhatsApp falha, SMS e email não são afetados.

## 6. Processamento por canal

### 6.1 WhatsApp (Baileys)
- **Text mode** (`is_tts=false`):
  - Markdown passa quase direto (Baileys aceita `*bold*`, `_italic_`, `~strike~`, ` ``` `)
  - Conversor markdown → whatsapp-markdown antes de enviar
  - Se `media_urls`: cada URL baixada e enviada como mídia com primeira msg como caption
- **TTS mode** (`is_tts=true`):
  - Converte `content` (markdown strip) → texto puro
  - Chama ElevenLabs TTS → arquivo .ogg opus
  - Envia como PTT (push-to-talk / voice note)
  - `media_urls` anexadas como mídia separada depois do áudio
- Baileys roda como processo sidecar Node.js, expõe HTTP local ao backend Python

### 6.2 SMS (SMS Gateway for Android)
- `POST https://{gateway}/message` com `{phoneNumbers:["43996648750"], message: "texto"}`
- Markdown stripado para texto puro
- `media_urls` ignoradas (SMS não suporta)
- Auth basic (user/pass do gateway)

### 6.3 Email (SMTP Python nativo)
- Stack: `aiosmtplib` + `email.message.EmailMessage` (stdlib)
- Credenciais vêm de `ServiceConfig` (configuradas no dashboard)
- Renderiza template Jinja2 com `content_html = markdown_to_html(content)`
- `media_urls`: imagens (mime image/*) embedadas inline via `cid:`, outros arquivos anexados
- Gera Message-Id próprio antes de enviar → salva como `provider_msg_id`
- Suporta STARTTLS (porta 587) e SSL (porta 465)

## 7. Queue e retry

- **Broker**: Redis
- **Lib**: RQ
- **Queues**: `whatsapp`, `sms`, `email` (workers separados)
- **Retry**: 3 tentativas, backoff exponencial: 60s, 300s, 900s
- **Falha final**: log `status=failed` + `error_msg`
- **Concurrency**: 1 worker para WhatsApp (serializa para evitar ban), 2 para SMS, 4 para email

## 8. Dashboard

Rota `/` (FastAPI + Jinja2 + HTMX, sem SPA).

- **Home**: últimas 100 notificações (tabela: timestamp, client, recipient.external_id, canais, status)
- **Clients**: CRUD
- **Recipients**: busca por client + external_id, editar
- **Logs**: filtros (client, channel, status, período)
- **Template de email**: editor textarea para subject + html_body, preview, salvar
- **Config de serviços**: editar ServiceConfig (ElevenLabs, SMS gateway, Himalaya, Baileys)
- **Status Baileys** (`/baileys`):
  - Estado da sessão: `disconnected | qr_pending | connecting | connected`
  - Se `qr_pending`: exibe QR code (PNG) com auto-refresh HTMX a cada 3s (QR expira ~20s)
  - Se `connected`: mostra JID conectado, nome do device, "última atividade"
  - Botão **Desconectar** (logout + apaga sessão em `/data/auth`)
  - Botão **Reconectar** (força restart do sidecar)
  - Logs recentes do sidecar (últimas 50 linhas via endpoint `GET /logs` do Baileys)

Sem autenticação. Acesso via VPN.

## 9. Observabilidade

Logs internos guardam apenas metadados. Conteúdo vive nos sistemas externos:
- WhatsApp: sqlite do processo Baileys (sincronização nativa)
- Email: servidor IMAP próprio (Himalaya)
- SMS: histórico do celular Android

`provider_msg_id` permite correlacionar log interno com o registro externo.

## 10. Fora de escopo (v1)

- Autenticação / API keys
- Templates nomeados por tipo de notificação (template único global)
- Agendamento de envio futuro
- Webhooks de status de entrega
- Multi-idioma no template
- Rate limiting
- Métricas Prometheus
