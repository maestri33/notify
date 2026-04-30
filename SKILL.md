# Notify — Skill para Agentes de IA

Guia operacional para agentes de IA utilizarem o Notify via CLI com segurança e previsibilidade.

---

## Uso rápido da CLI

**No servidor (native install):**
```bash
notify <command>
```

**Inside Docker:**
```bash
docker compose exec api notify <command>
```

**Remoto (CLI only install):**
```bash
NOTIFY_URL=http://<host>:8000 notify <command>
```

Flag `--json` antes de qualquer comando retorna JSON machine-readable:
```bash
notify --json status
notify --json groups list
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

Filter by external_id:
```bash
notify recipients list --filter <external_id>
```

Update a recipient:
```bash
notify recipients update <id> --phone <number>
```

Consultar recipient por ID:
```bash
notify recipients get <recipient_id>
```

Revalidar WhatsApp de um recipient:
```bash
notify recipients revalidate <recipient_id>
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
notify notifications logs --recipient <external_id> --limit 10

# Filter by status (sent, failed, pending)
notify notifications logs --status sent --limit 5

# Filter by channel
notify notifications logs --channel whatsapp

# Filter by time range
notify notifications logs --since 2026-04-29T00:00:00

# Full detail for a specific log entry
notify notifications get <log_id>
```

---

## System status

```bash
notify status            # overall application health
notify whatsapp status   # WhatsApp connection state + JID
notify whatsapp qr       # renderiza QR no terminal para pareamento
notify whatsapp qr --save notify-qr.png  # opcional: salvar PNG
```

---

## WhatsApp Groups

```bash
# Listar todos os grupos
notify groups list

# Detalhes do grupo (metadados + participantes)
notify groups get <jid>          # ex: 120363267922740326@g.us

# Apenas membros
notify groups members <jid>

# Link de convite
notify groups invite <jid>
```

---

## WhatsApp Users

```bash
# Perfil completo: foto (alta/baixa res), status, contato
notify users get <jid>           # ex: 5511999999999@s.whatsapp.net
```

---

## WhatsApp Validation

```bash
# Verificar se número está no WhatsApp
notify whatsapp validate <number>  # ex: 5511999999999

# Logout / restart
notify whatsapp logout [-y]
notify whatsapp restart
```

---

## Regras obrigatórias para o agente

1. **Sempre rode `check` antes de `create`** para evitar duplicidade.
2. **`external_id` é a chave de negócio** (não use ID interno do Notify para integração).
3. **Use `phone` único** (o sistema normaliza para SMS + WhatsApp automaticamente).
4. **`--tts` é multicanal** (áudio no WhatsApp, texto em SMS/Email na mesma requisição).
5. **Mídias devem ser URL pública acessível** no momento do envio.
6. **Verifique `notify whatsapp status` antes de envios WhatsApp/TTS**; se não estiver `connected`, avise o operador.
7. **`notify whatsapp validate` confirma se um número está registrado no WhatsApp** antes de criar recipient.
8. **Grupos retornam JID no formato `120363XXXXXXXXXX@g.us`** — use esse JID para consultar detalhes/membros.

## Checklist recomendado antes de enviar em produção

```bash
notify status
notify whatsapp status
notify recipients check <phone_or_email>
notify notifications send <external_id> "mensagem de teste" --channel email
```
