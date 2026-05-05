"""
Pacote de modelos Tortoise.

Tortoise descobre os modelos pela lista em `app.db.TORTOISE_ORM["apps"]`,
que aponta pra `app.models`. Para um modelo aparecer na descoberta,
basta o arquivo dele estar dentro deste pacote — Tortoise faz o import.
"""

from app.models.contact import Contact  # noqa: F401
from app.models.log import Log  # noqa: F401
from app.models.message import Message  # noqa: F401
