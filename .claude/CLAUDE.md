# CLAUDE.md — Memória e regras deste microserviço

> Este arquivo é a **fonte da verdade** para você (Claude Code) sobre este
> microserviço. Leia ele inteiro antes de fazer qualquer coisa. Se algo aqui
> conflita com o que o usuário pediu agora, **pergunte** — não decida sozinho.

---

## 1. Quem é você aqui

- Você é o Claude Code **exclusivo deste serviço**. Você não conhece outros
  serviços do ecossistema; quando precisar falar com outro serviço, faz isso
  via HTTP, fila ou webhook (ver `app/integrations/`).
- Seu papel: **manter este serviço pequeno, claro e funcional.** Nada de
  abstração prematura, nada de framework dentro de framework.
- Sua missão recorrente: implementar features, corrigir bugs, escrever testes
  e documentar — sempre dentro da estrutura definida abaixo.

## 2. Regras de ouro (não negociáveis)

1. **Não alucine.** Se você não tem certeza de uma assinatura de função, de
   uma versão de pacote ou do nome de uma env var, **consulte o Context7
   MCP** ou pergunte ao usuário. Nunca invente import path, nunca invente
   método de biblioteca.
2. **Faça apenas o que foi pedido.** Não acrescente features "que ficariam
   legais". Se achar que falta algo, comente no fim da resposta com a
   sugestão — não implemente.
3. **Antes de codar, leia.** Sempre leia os arquivos relevantes desta pasta
   (`.claude/memory/*.md`, `app/`) antes de propor mudança. Atualize a
   memória quando aprender algo novo (seção 7).
4. **Stack fixa.** Não troque FastAPI por Flask, Tortoise por SQLAlchemy,
   uv por poetry. Se o usuário pedir, confirme antes.
5. **Porta 80.** Esse serviço expõe **somente** a porta 80 (HTTP). Não mude.
6. **Cada serviço, seu banco.** Não conecte este serviço no banco de outro
   serviço. Se precisa de dado de outro serviço, chama a API dele.

## 3. Stack

| Camada            | Tecnologia                              |
| ----------------- | --------------------------------------- |
| Runtime           | Python 3.12 + `uv`                      |
| Web framework     | FastAPI                                 |
| Servidor ASGI     | Uvicorn (porta 80)                      |
| ORM               | Tortoise ORM (estilo Django)            |
| Migrations        | Aerich                                  |
| Banco padrão      | SQLite local (env-driven, troca p/ PG)  |
| Validação         | Pydantic v2                             |
| Config            | pydantic-settings + `.env`              |
| HTTP cliente      | httpx (async)                           |
| Cache / pub-sub   | redis.asyncio                           |
| Mensageria        | aio-pika (RabbitMQ)                     |
| Testes            | pytest + pytest-asyncio + httpx client  |
| Logs              | structlog (JSON em prod)                |

## 4. Estrutura do projeto — onde cada coisa mora

```
.
├── .claude/                  # você (Claude Code) e sua memória
│   ├── CLAUDE.md             # este arquivo — sempre leia primeiro
│   ├── settings.json         # modelo + permissões
│   └── memory/               # contexto persistente do serviço
│       ├── architecture.md   # decisões arquiteturais
│       ├── conventions.md    # como escrevemos código aqui
│       └── integrations.md   # como falamos com outros serviços
├── .mcp.json                 # MCPs habilitados (Context7)
├── app/
│   ├── main.py               # entrypoint FastAPI, lifespan, porta 80
│   ├── config.py             # Settings (lê .env)
│   ├── db.py                 # init/close Tortoise
│   ├── api/                  # routers HTTP — UMA pasta por feature
│   │   ├── deps.py           # Depends() reutilizáveis
│   │   ├── router.py         # agrega todos os routers
│   │   ├── health.py         # /health, /ready
│   │   └── example.py        # CRUD de exemplo
│   ├── models/               # modelos Tortoise (1 arquivo por entidade)
│   ├── schemas/              # Pydantic schemas (request/response)
│   ├── services/             # regras de negócio (chamadas pelo router)
│   ├── integrations/         # tudo que sai pra fora deste serviço
│   │   ├── http_client.py    # cliente httpx p/ outros microservices
│   │   ├── redis_client.py   # cache + pub/sub
│   │   ├── messaging.py      # publisher/consumer RabbitMQ
│   │   └── webhooks.py       # outbound + inbound webhooks
│   ├── workers/              # consumidores de fila, jobs em background
│   └── utils/                # logging, helpers genéricos
├── tests/                    # pytest
├── scripts/
│   ├── dev.sh                # roda uvicorn em dev
│   └── new_service.sh        # clona este template p/ um novo serviço
├── pyproject.toml
├── .env.example
├── Makefile
└── README.md
```

**Regra das pastas:**
- Endpoint HTTP novo → `app/api/<feature>.py`, registrar em `app/api/router.py`
- Modelo de banco novo → `app/models/<entidade>.py`, importar em
  `app/models/__init__.py` para Tortoise enxergar
- Schema Pydantic → `app/schemas/<feature>.py`
- Lógica de negócio (mais de 5 linhas) → `app/services/<feature>_service.py`
- Chamada pra outro serviço → `app/integrations/<servico>_client.py`
- Consumir mensagem de fila → `app/workers/<topico>_consumer.py`

Se uma coisa nova não cabe em nenhuma dessas pastas, **pergunte** antes
de criar pasta nova.

## 5. Ambiente real

- **Hospedagem:** Proxmox (LXC ou VM) — este serviço é **dev mas roda em
  ambiente real**. Não é localhost de brincadeira.
- **Rede:** está numa **DMZ**. Não há firewall protegendo este serviço de
  outros serviços internos. Por enquanto, **segurança não é prioridade** —
  pode pular auth, CORS aberto, sem rate-limit. O usuário vai pedir essas
  camadas depois, num passe explícito de "agora trava isso".
- **Modelo do Claude Code:** DeepSeek v4 Pro (configurado em `settings.json`
  via `ANTHROPIC_BASE_URL` apontando pra um proxy compatível, ex.:
  claude-code-router ou litellm).

## 6. Comandos que você usa direto

```bash
# bootstrap (uma vez)
uv sync

# rodar local
make dev                  # = uv run uvicorn app.main:app --host 0.0.0.0 --port 80 --reload

# testes
make test                 # = uv run pytest -q

# migrations (Aerich)
uv run aerich init-db     # primeira vez
uv run aerich migrate     # gera migration
uv run aerich upgrade     # aplica
```

## 7. Gerenciamento de memória

- **`.claude/memory/architecture.md`** — sempre que tomar uma decisão
  arquitetural (escolheu RabbitMQ vs NATS, quebrou um modelo em dois,
  mudou estratégia de cache), registre aqui em uma seção datada.
- **`.claude/memory/conventions.md`** — convenções deste serviço
  específico (nomes, padrões de erro, formato de log). Atualize quando
  for combinado algo novo.
- **`.claude/memory/integrations.md`** — para cada serviço externo com
  que este serviço fala: URL base, endpoints usados, formato esperado,
  retry policy. Atualize **toda vez** que adicionar uma chamada nova.
- Antes de implementar algo, leia os 3 arquivos. Antes de terminar a
  tarefa, pergunte-se: "preciso registrar algo aqui?".

## 8. Como pedir ajuda ao usuário

Você está autorizado e **encorajado** a parar e perguntar quando:
- A spec está ambígua
- Falta info de conexão (URL, credencial, formato de evento)
- Existem 2+ caminhos razoáveis e a escolha tem trade-off real

Use perguntas curtas e objetivas, sem opções demais. Não "ofereça menu"
quando uma pergunta direta resolve.

## 9. O que NÃO fazer

- Não criar segundo banco neste serviço.
- Não conectar diretamente no banco de outro serviço.
- Não adicionar dependência sem registrar em `pyproject.toml` via
  `uv add`.
- Não escrever migration manual — usa `aerich migrate`.
- Não logar segredo (token, senha, payload sensível).
- Não escrever README/comentário em inglês — este projeto é em **PT-BR**.

---

**Antes de começar qualquer tarefa**, leia também:
- `.claude/memory/architecture.md`
- `.claude/memory/conventions.md`
- `.claude/memory/integrations.md`
