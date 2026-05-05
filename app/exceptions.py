"""
Excecoes de dominio.

Levante estas excecoes na camada `services/`. O handler global em `main.py`
converte em HTTPException — services NAO devem importar HTTPException.
"""


class DomainError(Exception):
    """Base de todas as excecoes de dominio deste servico."""

    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.__class__.__name__)
        self.message = message or self.__class__.__name__


class NotFound(DomainError):  # noqa: N818  (sufixo Error omitido por design)
    status_code = 404
    code = "not_found"


class Conflict(DomainError):  # noqa: N818  (sufixo Error omitido por design)
    status_code = 409
    code = "conflict"


class IntegrationError(DomainError):
    """Falha ao chamar um servico externo (HTTP, fila, webhook)."""

    status_code = 502
    code = "integration_error"
