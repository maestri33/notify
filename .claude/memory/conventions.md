# Memória — Convenções de código

## Idioma

- Código, nomes de função e classe: **inglês**.
- Comentários, docstrings, mensagens de erro pro usuário, README e
  documentação interna: **português**.

## Nomes

- Pacotes/módulos: `snake_case`.
- Classes: `PascalCase`.
- Modelos Tortoise: substantivo no singular (`User`, `Order`, não `Users`).
- Schemas Pydantic: sufixo de intenção — `UserCreate`, `UserRead`,
  `UserUpdate`. Nunca usar o mesmo schema pra entrada e saída.

## Estrutura de uma feature nova

Quando o usuário pede "implementa CRUD de X":
1. `app/models/x.py` → modelo Tortoise.
2. `app/models/__init__.py` → adiciona o import (Tortoise descobre).
3. `app/schemas/x.py` → `XCreate`, `XRead`, `XUpdate`.
4. `app/services/x_service.py` → funções `create_x`, `get_x`, etc.
   Sem FastAPI aqui, só lógica + ORM.
5. `app/api/x.py` → router com endpoints, chama `services/`.
6. `app/api/router.py` → `include_router`.
7. `tests/test_x.py` → testes com `httpx.AsyncClient`.

## Erros

- Erros de domínio: `app/exceptions.py` (`NotFound`, `Conflict`, etc).
- Handler global em `app/main.py` converte pra HTTPException.
- **Nunca** levantar `HTTPException` direto do `services/`.

## Logging

- `structlog` configurado em `app/utils/logging.py`.
- Sempre logar com contexto: `log.info("user.created", user_id=u.id)`.
- **Nunca** logar token, senha, body completo de webhook.

## Async em todo lugar

- Endpoints, services, integrações: tudo `async def`.
- Sincronizar (`asyncio.to_thread`) só pra lib que não tem versão async.

## Clientes de API externa (`app/services/clients/`)

Quando este serviço precisa consumir uma API externa:

1. Adicionar URL e credenciais em `app/config.py` (Settings).
2. Criar `app/services/clients/<nome>.py` com uma classe `XxxClient`.
3. O `__init__` recebe `httpx.AsyncClient` (injeção, não cria internamente).
4. Métodos `async def`, usando `request_with_retry` do `http_client.py`.
5. Erros da API externa → `IntegrationError`.
6. Logging via structlog (`log.info("acao", key=value)`).
7. Docstrings em português, detalhando parâmetros e formato de resposta.
8. Registrar em `.claude/memory/integrations.md` com endpoints, auth e
   última verificação.

Exemplo de assinatura:

```python
class FooClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._base_url = get_settings().foo_api_base_url

    async def do_thing(self, ...) -> dict[str, Any]:
        resp = await request_with_retry(self._client, "POST", ...)
        ...
```

## Testes

- `pytest-asyncio` em modo `auto`.
- Banco de teste: SQLite in-memory (`sqlite://:memory:`).
- Cada teste limpa o que cria; sem fixture global de "popula tudo".
