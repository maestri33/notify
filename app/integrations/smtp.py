"""
Cliente para a API de mail merge (envio de e-mails em massa via CSV).

API alvo: Settings.smtp_api_base_url.

Fluxos:
    - Em massa: configure_smtp() -> preview_csv() -> send_emails()
    - Unitario: send_single_email() — gera CSV temporario internamente
"""

import tempfile
from pathlib import Path
from typing import Any

import anyio
import httpx

from app.config import get_settings
from app.exceptions import IntegrationError
from app.integrations.http_client import request_with_retry
from app.utils.logging import get_logger

log = get_logger(__name__)


async def _read_file_bytes(path: Path) -> tuple[str, bytes]:
    """Le um arquivo em disco via thread (nao bloqueia o event loop)."""

    def _read() -> tuple[str, bytes]:
        return path.name, path.read_bytes()

    return await anyio.to_thread.run_sync(_read)


class SMTPClient:
    """Cliente de alto nivel para a API de mail merge."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._base_url = get_settings().smtp_api_base_url

    # ------------------------------------------------------------------
    # SMTP
    # ------------------------------------------------------------------

    async def configure_smtp(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_pass: str,
    ) -> dict[str, Any]:
        """Configura o servidor SMTP na API remota (armazena em memoria).

        Sem esta chamada, /send_emails retorna erro 400.
        """
        resp = await request_with_retry(
            self._client,
            "POST",
            f"{self._base_url}/configure_smtp",
            data={
                "smtpHost": smtp_host,
                "smtpPort": str(smtp_port),
                "smtpUser": smtp_user,
                "smtpPass": smtp_pass,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code >= 400:
            raise IntegrationError(
                f"Falha ao configurar SMTP ({resp.status_code}): {resp.text}"
            )
        log.info("smtp.configured", host=smtp_host, port=smtp_port)
        return resp.json()

    # ------------------------------------------------------------------
    # Preview do CSV
    # ------------------------------------------------------------------

    async def preview_csv(self, csv_path: str | Path) -> dict[str, Any]:
        """Envia um CSV para preview — retorna as 5 primeiras linhas como JSON."""
        path = Path(csv_path)
        exists = await anyio.to_thread.run_sync(lambda: path.is_file())
        if not exists:
            raise IntegrationError(f"Arquivo CSV nao encontrado: {csv_path}")

        name, content = await _read_file_bytes(path)
        resp = await request_with_retry(
            self._client,
            "POST",
            f"{self._base_url}/preview_csv",
            files={"csvFile": (name, content, "text/csv")},
        )
        if resp.status_code >= 400:
            raise IntegrationError(
                f"Falha ao fazer preview do CSV ({resp.status_code}): {resp.text}"
            )
        log.info("csv.previewed", file=str(path))
        return resp.json()

    # ------------------------------------------------------------------
    # Envio de e-mails
    # ------------------------------------------------------------------

    async def send_emails(
        self,
        subject: str,
        sender_name: str,
        html_content: str,
        csv_path: str | Path,
    ) -> dict[str, Any]:
        """
        Dispara e-mails em massa via fastapi-mail.

        O CSV precisa ter coluna Email. Subject e htmlContent aceitam
        placeholders Jinja2 {{coluna}} que serao substituidos por linha.

        A API tenta 3x por e-mail com 1s de intervalo.
        Retorna resumo de sucessos e falhas.
        """
        path = Path(csv_path)
        exists = await anyio.to_thread.run_sync(lambda: path.is_file())
        if not exists:
            raise IntegrationError(f"Arquivo CSV nao encontrado: {csv_path}")

        name, content = await _read_file_bytes(path)
        resp = await request_with_retry(
            self._client,
            "POST",
            f"{self._base_url}/send_emails",
            data={
                "subject": subject,
                "senderName": sender_name,
                "htmlContent": html_content,
            },
            files={"csvFile": (name, content, "text/csv")},
        )
        if resp.status_code >= 400:
            raise IntegrationError(
                f"Falha ao enviar e-mails ({resp.status_code}): {resp.text}"
            )
        log.info("emails.sent", subject=subject, file=str(path))
        return resp.json()

    async def send_single_email(
        self,
        to_email: str,
        subject: str,
        sender_name: str,
        html_content: str,
    ) -> dict[str, Any]:
        """
        Envia um e-mail unitario (sem precisar de CSV externo).

        Cria um CSV temporario com o destinatario e chama send_emails.
        """
        import csv
        import io

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Email"])
        writer.writerow([to_email])
        csv_content = buf.getvalue().encode("utf-8")

        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".csv", delete=False
        ) as tmp:
            tmp.write(csv_content)
            tmp_path = tmp.name

        try:
            return await self.send_emails(subject, sender_name, html_content, tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health(self) -> dict[str, Any]:
        """Verifica se a API de mail merge esta no ar."""
        resp = await request_with_retry(
            self._client,
            "GET",
            f"{self._base_url}/vercel",
        )
        if resp.status_code >= 400:
            raise IntegrationError(
                f"API de mail merge indisponivel ({resp.status_code})"
            )
        return resp.json()
