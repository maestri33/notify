# Memória — Integrações com outros serviços

> Para **cada serviço externo** com que este fala, registre aqui:
> base URL, endpoints usados, formato de erro, política de retry,
> última vez que foi testado.

## Template de entrada

```
### <nome-do-servico>
- **Tipo:** HTTP | Webhook | Fila (RabbitMQ) | Pub/Sub (Redis)
- **Base URL / queue:** http://...
- **Endpoints / tópicos usados:**
  - GET /api/v1/...
- **Auth:** nenhuma (DMZ) | bearer | hmac
- **Retry:** 3x backoff exponencial (já no http_client)
- **Última verificação:** YYYY-MM-DD
- **Notas:** ...
```

## Integrações ativas

### Mail Merge API (SMTP)
- **Tipo:** HTTP
- **Base URL:** `http://10.10.10.150`
- **Cliente:** `app/integrations/smtp.py` → `SMTPClient`
- **Endpoints usados:**
  - `GET /vercel` — health check, retorna `{"message":"FastAPI is running on Vercel!"}`
  - `POST /configure_smtp` — configura SMTP em memória (form-encoded: `smtpHost`, `smtpPort`, `smtpUser`, `smtpPass`)
  - `POST /preview_csv` — upload CSV, retorna as 5 primeiras linhas como JSON
  - `POST /send_emails` — dispara e-mails em massa (multipart: `subject`, `senderName`, `htmlContent` + csvFile)
- **Fluxo:** configure SMTP → preview CSV → send emails. Sem configurar SMTP antes, `/send_emails` retorna 400.
- **Placeholders:** subject e htmlContent aceitam `{{coluna}}` (Jinja2) referenciando colunas do CSV.
- **CSV:** obrigatório ter coluna `Email`.
- **Entrega:** fastapi-mail, 3 tentativas com 1s de intervalo entre e-mails.
- **Auth:** nenhuma (DMZ)
- **Retry:** 3x backoff exponencial (via `request_with_retry` do `http_client`)
- **Última verificação:** 2026-05-02

### Evolution GO (WhatsApp API v2)
- **Tipo:** HTTP
- **Base URL:** `http://10.10.10.149`
- **Cliente:** `app/integrations/whatsapp.py` → `WhatsAppClient`
- **Instância ativa:** "default" — `5511920062177` (Supletivo BR)
- **Auth:** header `apikey` = `Settings.whatsapp_global_api_key` (`7A3F8C2B...`)
- **Instance:** default "default", sobreponível via `WhatsAppClient(http, instance="...")`
- **Endpoints usados:**
  - `GET /instance/status` — health global da API
  - `POST /chat/whatsappNumbers/{instance}` — verifica números (body: `{"numbers": [...]}`, resposta array plano `[{jid, exists, number, name}]`)
  - `POST /chat/fetchProfile/{instance}` — perfil do usuário (body: `{"number": "5543..."}`, resposta `{wuid, name, picture, status, isBusiness}`)
  - `POST /chat/fetchBusinessProfile/{instance}` — perfil comercial (body: `{"number": "..."}`, resposta `{address, website, category, business_hours}`)
  - `POST /call/reject/{instance}` — rejeita chamada
  - `POST /message/sendText/{instance}` — envia texto
  - `POST /message/sendMedia/{instance}` — envia mídia (campos: `mediatype`, `media`; tipos: image/video/audio/document)
  - `POST /message/sendWhatsAppAudio/{instance}` — nota de voz nativa (PTT, Opus, waveform)
  - `POST /message/sendSticker/{instance}` — sticker WebP
  - `POST /message/sendLocation/{instance}` — localização (pin no mapa)
  - `POST /message/sendContact/{instance}` — contato(s) vCard
  - `POST /message/sendPoll/{instance}` — enquete interativa (até 12 opções)
  - `POST /message/sendButtons/{instance}` — botões interativos (reply/url/copy, máx 3)
  - `POST /message/sendReaction/{instance}` — reação com emoji
  - `POST /message/sendStatus/{instance}` — status/story (texto ou imagem)
- **Body de perfil:** fetchProfile e fetchBusinessProfile recebem `{"number": "5543996648750"}` (número PURO, não JID). Campo é `number`, não `wuid`.
- **Retry:** 3x backoff exponencial (via `request_with_retry` do `http_client`)
- **Timeout audio:** 60s no `send_whatsapp_audio` (conversão para Opus)
- **Última verificação:** 2026-05-05 — todos os endpoints testados
