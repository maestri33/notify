# Notify API — Documentacao Completa

> Base URL: `http://10.10.10.144:80`
> Versao: 0.3.0
> Formato: JSON

---

## 1. Health

### `GET /health`

Health check simples.

**Response 200:**
```json
{"status": "ok", "service": "notify"}
```

### `GET /ready`

Ready probe (verifica se a app esta viva).

**Response 200:**
```json
{"status": "ok"}
```

---

## 2. Contactos

### `GET /contacts/check`

Verifica se um contacto existe por telefone ou email, validando externamente.
**Nunca cria contacto** — apenas consulta.

**Query params:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `phone` | string | nao* | Numero DDI+DDD+numero (ex: `5543996648750`) |
| `email` | string | nao* | Endereco de email |

> *Pelo menos um dos dois deve ser informado.

**Response 200 — Encontrado:**
```json
{
  "found": true,
  "external_id": "victor-001",
  "phone": "5543996648750",
  "email": "victor@exemplo.com",
  "phone_valid": null,
  "email_valid": null
}
```

**Response 200 — Nao encontrado (email valido):**
```json
{
  "found": false,
  "external_id": null,
  "phone": null,
  "email": null,
  "phone_valid": null,
  "email_valid": true
}
```

**Response 200 — Nao encontrado (email invalido):**
```json
{
  "found": false,
  "external_id": null,
  "phone": null,
  "email": null,
  "phone_valid": null,
  "email_valid": false
}
```

**Response 200 — Nao encontrado (telefone validado via WhatsApp):**
```json
{
  "found": false,
  "external_id": null,
  "phone": null,
  "email": null,
  "phone_valid": true,
  "email_valid": null
}
```

**Response 400 — Nenhum parametro:**
```json
{"code": "domain_error", "message": "Pelo menos telefone ou email deve ser informado"}
```

---

### `POST /contacts`

Cria um contacto com pipeline de enriquecimento via IA e WhatsApp.

**Request body:**
```json
{
  "external_id": "victor-001",
  "phone": "5543996648750",
  "email": "victor@exemplo.com"
}
```

| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `external_id` | string | sim | Identificador externo (source of truth) |
| `phone` | string | nao | Numero WhatsApp (DDI+DDD+numero) |
| `email` | string | nao | Endereco de email |

**Pipeline de enriquecimento:**
1. Verifica duplicata por phone/email (se informados)
2. Se `email` informado → DeepSeek Pro analisa: extrai nome, genero, data de nascimento
3. Se `phone` informado e validado no WhatsApp:
   - Busca perfil (`fetch_profile`): nome, foto, status, isBusiness
   - Se `isBusiness=true` → busca perfil comercial
   - Se tem foto → Gemini descreve a imagem
4. DeepSeek Pro consolida todos os dados → extracao estruturada + analise inicial
5. Persiste contacto com campos enriquecidos

**Response 201:**
```json
{
  "id": 1,
  "external_id": "victor-001",
  "phone": "5543996648750",
  "email": "victor@exemplo.com",
  "name": "Victor Silva",
  "gender": "masculino",
  "birth_date": "1990",
  "avatar_url": "https://pps.whatsapp.net/v/...",
  "profile_data": {
    "email_analysis": {"name": "Victor", "gender": null, "birth_date": null},
    "whatsapp_profile": {"wuid": "...", "name": "Victor Silva", "picture": "https://...", "isBusiness": false},
    "photo_description": "Homem jovem, camiseta azul, fundo neutro..."
  },
  "initial_analysis": "## Analise Inicial do Contacto\n\n### Dados obtidos\n- **Nome:** Victor Silva (confirmado via WhatsApp)\n- **Genero:** Masculino (confianca alta — foto de perfil)...\n",
  "is_business": false,
  "is_active": true,
  "created_at": "2026-05-05T18:00:00Z",
  "updated_at": "2026-05-05T18:00:00Z"
}
```

**Response 201 — Basico (sem phone/email):**
```json
{
  "id": 2,
  "external_id": "sem-dados",
  "phone": null,
  "email": null,
  "name": null,
  "gender": null,
  "birth_date": null,
  "avatar_url": null,
  "profile_data": null,
  "initial_analysis": null,
  "is_business": false,
  "is_active": true,
  "created_at": "2026-05-05T18:00:00Z",
  "updated_at": "2026-05-05T18:00:00Z"
}
```

**Response 409 — Duplicata:**
```json
{"code": "conflict", "message": "Contacto ja existe com external_id=victor-001"}
```

---

### `GET /contacts`

Lista todos os contactos (paginado).

**Query params:**
| Param | Tipo | Default | Descricao |
|-------|------|---------|-----------|
| `limit` | int | 50 | Maximo de registros |
| `offset` | int | 0 | Offset de paginacao |

**Response 200:**
```json
[
  {
    "id": 1,
    "external_id": "victor-001",
    "phone": "5543996648750",
    "email": "victor@exemplo.com",
    "name": "Victor Silva",
    "gender": "masculino",
    "birth_date": "1990",
    "avatar_url": "https://pps.whatsapp.net/v/...",
    "profile_data": {...},
    "initial_analysis": "...",
    "is_business": false,
    "is_active": true,
    "created_at": "2026-05-05T18:00:00Z",
    "updated_at": "2026-05-05T18:00:00Z"
  }
]
```

---

### `GET /contacts/{external_id}`

Obtem um contacto pelo `external_id`.

**Response 200:**
```json
{
  "id": 1,
  "external_id": "victor-001",
  "phone": "5543996648750",
  "email": "victor@exemplo.com",
  "name": "Victor Silva",
  "gender": "masculino",
  "birth_date": "1990",
  "avatar_url": "https://pps.whatsapp.net/v/...",
  "profile_data": {...},
  "initial_analysis": "...",
  "is_business": false,
  "is_active": true,
  "created_at": "2026-05-05T18:00:00Z",
  "updated_at": "2026-05-05T18:00:00Z"
}
```

**Response 404:**
```json
{"code": "not_found", "message": "Contacto inexistente nao encontrado"}
```

---

## 3. Mensagens

### `POST /messages/send`

Envia uma mensagem multicanal (WhatsApp + Email) com opcoes de IA, TTS e geracao de imagem.

**Request body:**
```json
{
  "external_id": "victor-001",
  "content": "Ola! Sua entrega chegou.",
  "media_url": null,
  "flags": {
    "tts": false,
    "ai": false,
    "img": false
  },
  "instruction": null
}
```

| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `external_id` | string | sim | ID do contacto destinatario |
| `content` | string | sim | Texto, URL de .md, ou prompt para IA (se `flags.ai`) |
| `media_url` | string | nao | URL ou data URI base64 de midia |
| `flags.tts` | bool | nao | Gera audio via ElevenLabs e envia nota de voz |
| `flags.ai` | bool | nao | DeepSeek Pro gera o texto da mensagem |
| `flags.img` | bool | nao | Gemini gera/edita imagem |
| `instruction` | string | nao | Refinamento extra para IA (`--ai`) ou prompt da imagem (`--img`) |

**Flags:**
| Flag | Efeito | Incompativel com |
|------|--------|-------------------|
| `ai` | DeepSeek Pro gera o texto | — |
| `tts` | ElevenLabs gera voz → WhatsApp audio | `--img` (img vence) |
| `img` | Gemini gera/edita imagem | `--tts` (img vence) |

**Fluxo completo:**
1. Resolve contacto por `external_id`
2. Extrai texto (URL .md → download, senao direto)
3. Detecta midia (URL ou base64)
4. Se `--ai`: DeepSeek Pro gera texto baseado no `content` (prompt) + `instruction`
5. Se `--img`: Gemini gera imagem — `content`=caption, `instruction`=prompt da imagem
6. Cria registo Message
7. Gera titulo via DeepSeek Flash
8. Prepara HTML do email (adapta midia)
9. Envia WhatsApp (texto ou midia com caption)
10. Envia Email (HTML com template)
11. Se `--tts` (so texto): ElevenLabs gera audio → WhatsApp audio nativo (PTT)
12. Atualiza statuses

**Response 201:**
```json
{
  "id": 1,
  "contact_id": 1,
  "type": "text",
  "content_text": "Ola! Sua entrega chegou.",
  "whatsapp_status": "sent",
  "email_status": "sent",
  "email_subject": "Sua entrega chegou",
  "tts_audio_url": null,
  "created_at": "2026-05-05T18:00:00Z",
  "updated_at": "2026-05-05T18:00:00Z"
}
```

**Response 201 — Com midia:**
```json
{
  "id": 2,
  "contact_id": 1,
  "type": "media",
  "content_text": "Confira a foto!",
  "whatsapp_status": "sent",
  "email_status": "sent",
  "email_subject": "Nova imagem",
  "tts_audio_url": null,
  "created_at": "2026-05-05T18:00:00Z",
  "updated_at": "2026-05-05T18:00:00Z"
}
```

**Response 201 — Com TTS:**
```json
{
  "id": 3,
  "contact_id": 1,
  "type": "text",
  "content_text": "Mensagem de voz.",
  "whatsapp_status": "sent",
  "email_status": "sent",
  "email_subject": "Nova mensagem",
  "tts_audio_url": "http://10.10.10.144:80/files/audio/abc123.mp3",
  "created_at": "2026-05-05T18:00:00Z",
  "updated_at": "2026-05-05T18:00:00Z"
}
```

**Response 404 — Contacto nao encontrado:**
```json
{"code": "not_found", "message": "Contacto inexistente nao encontrado"}
```

---

### `GET /messages`

Lista mensagens (paginado, filtravel por contacto).

**Query params:**
| Param | Tipo | Default | Descricao |
|-------|------|---------|-----------|
| `contact_id` | int | — | Filtra por ID do contacto |
| `limit` | int | 50 | Maximo de registros |
| `offset` | int | 0 | Offset de paginacao |

**Response 200:**
```json
[
  {
    "id": 1,
    "contact_id": 1,
    "type": "text",
    "content_text": "Ola! Sua entrega chegou.",
    "whatsapp_status": "sent",
    "email_status": "sent",
    "email_subject": "Sua entrega chegou",
    "tts_audio_url": null,
    "created_at": "2026-05-05T18:00:00Z",
    "updated_at": "2026-05-05T18:00:00Z"
  }
]
```

---

### `GET /messages/{message_id}`

Obtem uma mensagem pelo ID.

**Response 200:**
```json
{
  "id": 1,
  "contact_id": 1,
  "type": "text",
  "content_text": "Ola! Sua entrega chegou.",
  "whatsapp_status": "sent",
  "email_status": "sent",
  "email_subject": "Sua entrega chegou",
  "tts_audio_url": null,
  "created_at": "2026-05-05T18:00:00Z",
  "updated_at": "2026-05-05T18:00:00Z"
}
```

**Response 404:**
```json
{"code": "not_found", "message": "Mensagem 999 nao encontrada"}
```

---

## 4. Templates de Email

### `GET /templates/email`

Obtem o template HTML de email atual.

**Response 200:**
```json
{
  "html": "<!DOCTYPE html>\n<html lang=\"pt-BR\">\n<head>...</html>"
}
```

### `PUT /templates/email`

Atualiza o template HTML de email (manual ou via IA).

**Request body — Manual:**
```json
{
  "html": "<!DOCTYPE html><html>...</html>"
}
```

**Request body — Edicao via IA (DeepSeek Flash):**
```json
{
  "instruction": "Adiciona um rodape com os dados da empresa"
}
```

| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `html` | string | nao* | HTML completo do template |
| `instruction` | string | nao* | Instrucao para IA editar o template |

> *Informar `html` ou `instruction` (mutuamente exclusivos). Se nenhum, retorna o atual.

**Response 200:**
```json
{
  "html": "<!DOCTYPE html>\n<html lang=\"pt-BR\">...</html>"
}
```

---

## 5. Logs

### `GET /logs`

Lista logs de acoes do sistema (criacao de contactos, envios, enriquecimento, falhas).

**Query params:**
| Param | Tipo | Default | Descricao |
|-------|------|---------|-----------|
| `message_id` | int | — | Filtra por ID da mensagem |
| `limit` | int | 50 | Maximo de registros |
| `offset` | int | 0 | Offset de paginacao |

**Response 200:**
```json
[
  {
    "id": 1,
    "message_id": null,
    "action": "contact.created_enriched",
    "details": {"external_id": "victor-001", "has_name": true, "is_business": false},
    "created_at": "2026-05-05T18:00:00Z"
  },
  {
    "id": 2,
    "message_id": 1,
    "action": "message.sent",
    "details": {"type": "text", "whatsapp": "sent", "email": "sent"},
    "created_at": "2026-05-05T18:01:00Z"
  }
]
```

---

## 6. Arquivos Estaticos

### `GET /files/{path}`

Arquivos estaticos gerados pelo servico (audio TTS, imagens geradas/decodificadas).

**Subpastas:**
| Pasta | Conteudo |
|-------|----------|
| `/files/audio/{uuid}.mp3` | Audios TTS (ElevenLabs) |
| `/files/media/{uuid}.{ext}` | Imagens Gemini e base64 decoded |

---

## 7. Webhooks (Inbound)

### `POST /webhooks/{source}`

Recebe webhooks de sistemas externos.

**Path params:**
| Param | Tipo | Descricao |
|-------|------|-----------|
| `source` | string | Identificador do sistema de origem |

**Response 200:**
```json
{"status": "ok"}
```

---

## Codigos de Erro

| Codigo | code | Descricao |
|--------|------|-----------|
| 400 | `domain_error` | Erro de dominio generico |
| 404 | `not_found` | Recurso nao encontrado |
| 409 | `conflict` | Conflito (ex: duplicata) |
| 422 | — | Erro de validacao Pydantic |
| 502 | `integration_error` | Falha ao chamar servico externo |

---

## Exemplos de Uso

### Fluxo completo: cadastrar contacto e enviar mensagem

```bash
# 1. Verificar se contacto existe
curl -s http://10.10.10.144:80/contacts/check?phone=5543996648750

# 2. Criar contacto com enriquecimento
curl -s -X POST http://10.10.10.144:80/contacts \
  -H "Content-Type: application/json" \
  -d '{"external_id":"victor-001","phone":"5543996648750","email":"victor@exemplo.com"}'

# 3. Enviar mensagem de texto
curl -s -X POST http://10.10.10.144:80/messages/send \
  -H "Content-Type: application/json" \
  -d '{"external_id":"victor-001","content":"Ola Victor! Tudo bem?"}'

# 4. Enviar mensagem com IA (DeepSeek gera o texto)
curl -s -X POST http://10.10.10.144:80/messages/send \
  -H "Content-Type: application/json" \
  -d '{"external_id":"victor-001","content":"Notificar sobre atraso na entrega, tom educado","flags":{"ai":true}}'

# 5. Enviar mensagem com TTS (voz)
curl -s -X POST http://10.10.10.144:80/messages/send \
  -H "Content-Type: application/json" \
  -d '{"external_id":"victor-001","content":"Ola, sua entrega chegou!","flags":{"tts":true}}'

# 6. Enviar mensagem com imagem gerada por IA
curl -s -X POST http://10.10.10.144:80/messages/send \
  -H "Content-Type: application/json" \
  -d '{"external_id":"victor-001","content":"Notificacao de entrega confirmada","flags":{"img":true},"instruction":"Uma caixa de papelao lacrada com um selo de 'aprovado' verde"}'

# 7. Consultar logs
curl -s http://10.10.10.144:80/logs
```
