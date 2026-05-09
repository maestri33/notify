"""
Servico de templates de email.

Mantem o template HTML em disco (data/email_template.html).
Pode ser editado manualmente ou via AI (DeepSeekClient).
"""

from functools import partial
from pathlib import Path

import anyio

from app.utils.logging import get_logger

log = get_logger(__name__)

TEMPLATE_DIR = Path("data")
TEMPLATE_FILE = TEMPLATE_DIR / "email_template.html"

DEFAULT_TEMPLATE = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f4f4f4;font-family:Arial,sans-serif">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4;padding:20px 0">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:8px;overflow:hidden">
          <tr>
            <td style="padding:40px 48px">
              <h1 style="margin:0 0 16px;color:#1a1a1a;font-size:24px">{{title}}</h1>
              <div style="color:#333333;font-size:16px;line-height:1.6">
                {{content}}
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 48px;background-color:#f8f9fa;border-top:1px solid #e9ecef">
              <p style="margin:0;color:#6c757d;font-size:12px">
                Enviado por {{service_name}}
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def _ensure_template() -> None:
    """Cria o template default se nao existir."""
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    if not TEMPLATE_FILE.exists():
        TEMPLATE_FILE.write_text(DEFAULT_TEMPLATE, encoding="utf-8")
        log.info("template.default_created")


async def get_template() -> str:
    """Retorna o template atual."""
    await anyio.to_thread.run_sync(_ensure_template)
    return await anyio.to_thread.run_sync(
        partial(TEMPLATE_FILE.read_text, encoding="utf-8")
    )


async def update_template(html: str) -> None:
    """Salva um novo template."""
    await anyio.to_thread.run_sync(
        partial(TEMPLATE_DIR.mkdir, parents=True, exist_ok=True)
    )
    await anyio.to_thread.run_sync(
        partial(TEMPLATE_FILE.write_text, html, encoding="utf-8")
    )
    log.info("template.updated")


async def edit_template_with_ai(instruction: str) -> str:
    """Edita o template atual usando DeepSeek AI."""
    import httpx

    from app.integrations.deepseek import DeepSeekClient

    current_html = await get_template()
    async with httpx.AsyncClient() as client:
        ai = DeepSeekClient(client)
        new_html = await ai.edit_html_template(current_html, instruction)
    await update_template(new_html)
    return new_html
