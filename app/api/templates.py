from fastapi import APIRouter
from pydantic import BaseModel

from app.services import template_service

router = APIRouter()


class TemplateUpdate(BaseModel):
    html: str | None = None
    instruction: str | None = None


@router.get("/email")
async def get_email_template() -> dict:
    html = await template_service.get_template()
    return {"html": html}


@router.put("/email")
async def update_email_template(payload: TemplateUpdate) -> dict:
    if payload.instruction:
        html = await template_service.edit_template_with_ai(payload.instruction)
    elif payload.html:
        await template_service.update_template(payload.html)
        html = payload.html
    else:
        html = await template_service.get_template()
    return {"html": html}
