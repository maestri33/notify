from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models._common import utcnow

DEFAULT_SUBJECT = "{{ subject | default('Nova notificação') }}"

DEFAULT_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ subject | default('Notificação') }}</title>
</head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0"
               style="max-width:600px;background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
          <tr>
            <td style="padding:32px;color:#111827;font-size:16px;line-height:1.6;">
              {{ content_html | safe }}
            </td>
          </tr>
          <tr>
            <td style="padding:16px 32px;background:#f9fafb;border-top:1px solid #e5e7eb;
                       color:#6b7280;font-size:12px;text-align:center;">
              Notificação automática — não responda este email.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


class EmailTemplate(SQLModel, table=True):
    __tablename__ = "email_template"

    id: int = Field(default=1, primary_key=True)
    subject: str = Field(default=DEFAULT_SUBJECT)
    html_body: str = Field(default=DEFAULT_HTML)
    updated_at: datetime = Field(default_factory=utcnow)
