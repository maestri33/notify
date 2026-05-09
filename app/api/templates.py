"""Endpoints de templates de email."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services import template_service

router = APIRouter()


class TemplateUpdate(BaseModel):
    """Body para atualizacao de template de email.

    Informe html OU instruction — sao mutuamente exclusivos.
    Se nenhum for informado, retorna o template atual (no-op).
    """

    html: str | None = Field(
        default=None,
        description="HTML completo do template email. Use {{title}}, "
        "{{content}} e {{service_name}} como placeholders Jinja2.",
    )
    instruction: str | None = Field(
        default=None,
        description="Instrucao em linguagem natural para a IA (DeepSeek) "
        "editar o template. Ex: 'adiciona um rodape com endereco da empresa'",
    )


@router.get(
    "/email",
    summary="Obter template de email",
)
async def get_email_template() -> dict:
    """Retorna o template HTML atual usado nos emails.

    O template usa Jinja2 com os placeholders:
    - {{title}} — titulo do email
    - {{content}} — corpo (texto ou HTML de midia)
    - {{service_name}} — nome do servico (ex: 'notify')
    """
    html = await template_service.get_template()
    return {"html": html}


@router.put(
    "/email",
    summary="Atualizar template de email",
)
async def update_email_template(payload: TemplateUpdate) -> dict:
    """Atualiza o template HTML de email (manual ou via IA).

    - Se payload.instruction: DeepSeek edita o template atual conforme a instrucao
    - Se payload.html: substitui o template diretamente
    - Se nenhum: retorna o template atual sem modificar
    """
    if payload.instruction:
        html = await template_service.edit_template_with_ai(payload.instruction)
    elif payload.html:
        await template_service.update_template(payload.html)
        html = payload.html
    else:
        html = await template_service.get_template()
    return {"html": html}
