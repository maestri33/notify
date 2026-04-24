# Notify — Skill para Agentes de IA

Guia operacional para agentes de IA utilizarem o Notify via CLI com segurança e previsibilidade.

---

## Uso rápido da CLI

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

Consultar recipient por ID:
```bash
notify recipients get <recipient_id>
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
notify whatsapp qr       # renderiza QR no terminal para pareamento
notify whatsapp qr --save notify-qr.png  # opcional: salvar PNG
```

---

## Regras obrigatórias para o agente

1. **Sempre rode `check` antes de `create`** para evitar duplicidade.
2. **`external_id` é a chave de negócio** (não use ID interno do Notify para integração).
3. **Use `phone` único** (o sistema normaliza para SMS + WhatsApp automaticamente).
4. **`--tts` é multicanal** (áudio no WhatsApp, texto em SMS/Email na mesma requisição).
5. **Mídias devem ser URL pública acessível** no momento do envio.
6. **Verifique `notify whatsapp status` antes de envios WhatsApp/TTS**; se não estiver `connected`, avise o operador.

## Checklist recomendado antes de enviar em produção

```bash
notify status
notify whatsapp status
notify recipients check <phone_or_email>
notify notifications send <external_id> "mensagem de teste" --channel email
```
