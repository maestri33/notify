"""
Configuracao do Tortoise ORM.

- TORTOISE_ORM e' o dict de configuracao usado tanto pelo lifespan do app
  quanto pelo Aerich (migrations). NAO renomeie.
- A descoberta de modelos e' por convencao: tudo em `app.models` + tabelas
  internas do Aerich.
"""

from pathlib import Path

from tortoise import Tortoise

from app.config import get_settings

settings = get_settings()


def _ensure_sqlite_dir(url: str) -> None:
    """
    Cria a pasta do arquivo SQLite se nao existir.

    Tortoise aceita:
    - `sqlite://data/app.db`           (path relativo, 2 barras)
    - `sqlite:///abs/path/app.db`      (path absoluto, 3 barras)
    - `sqlite://:memory:`              (em memoria)
    """
    if not url.startswith("sqlite"):
        return
    after = url.split("://", 1)[1]
    if after in (":memory:", "") or after.startswith(":memory:"):
        return
    # 3 barras viram path absoluto: sqlite:///x -> /x
    path_part = "/" + after.lstrip("/") if url.startswith("sqlite:///") else after
    Path(path_part).parent.mkdir(parents=True, exist_ok=True)

TORTOISE_ORM = {
    "connections": {"default": settings.database_url},
    "apps": {
        "models": {
            "models": ["app.models", "aerich.models"],
            "default_connection": "default",
        },
    },
    "use_tz": True,
    "timezone": "UTC",
}


async def init_db() -> None:
    """Inicializa conexoes e (em dev/sqlite) cria as tabelas se nao existirem."""
    _ensure_sqlite_dir(settings.database_url)
    await Tortoise.init(config=TORTOISE_ORM)
    if settings.env == "dev" and settings.database_url.startswith("sqlite"):
        # em dev com sqlite e' conveniente auto-criar; em prod use aerich.
        await Tortoise.generate_schemas(safe=True)


async def close_db() -> None:
    """Fecha as conexoes — chamado no shutdown do FastAPI."""
    await Tortoise.close_connections()
