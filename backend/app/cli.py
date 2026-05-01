"""Notify CLI — wraps every public API endpoint as a Typer command.

Usage:
    notify [command] [subcommand] [options]

Base URL defaults to http://localhost:8000 or NOTIFY_URL env var.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

import niquests
import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="notify",
    help="Notify — multi-channel notification service CLI",
    no_args_is_help=True,
)

console = Console()

# ── Global state ─────────────────────────────────────────────────────────────

_output_json = False


def _json_output(obj) -> None:
    if isinstance(obj, dict):
        console.print_json(json.dumps(obj))
    else:
        console.print_json(json.dumps(list(obj) if hasattr(obj, "__iter__") and not isinstance(obj, str) else obj))


def _output(obj) -> None:
    """Print as JSON if --json flag set, otherwise let caller handle display."""
    if _output_json:
        _json_output(obj)


# ── helpers ──────────────────────────────────────────────────────────────────

def _base() -> str:
    url = os.environ.get("NOTIFY_URL")
    if not url:
        candidates = [
            os.path.expanduser("~/.notify.env"),
            "/etc/notify.env",
        ]
        for path in candidates:
            try:
                with open(path) as fh:
                    for line in fh:
                        line = line.strip()
                        if line.startswith("NOTIFY_URL=") and not line.startswith("#"):
                            url = line.split("=", 1)[1].strip()
                            break
            except OSError:
                pass
            if url:
                break
    return (url or "http://localhost:8000").rstrip("/")


def _api(path: str) -> str:
    return f"{_base()}/api/v1{path}"


def _get(path: str, **params) -> dict:
    r = niquests.get(_api(path), params={k: v for k, v in params.items() if v is not None}, timeout=60)
    _check(r)
    return r.json()


def _post(path: str, body: dict) -> dict:
    r = niquests.post(_api(path), json=body, timeout=60)
    _check(r)
    return r.json()


def _put(path: str, body: dict) -> dict:
    r = niquests.put(_api(path), json=body, timeout=60)
    _check(r)
    return r.json()


def _patch(path: str, body: dict) -> dict:
    r = niquests.patch(_api(path), json=body, timeout=60)
    _check(r)
    return r.json()


def _delete(path: str) -> None:
    r = niquests.delete(_api(path), timeout=60)
    _check(r)


def _check(r: niquests.Response) -> None:
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        rprint(f"[red]Error {r.status_code}:[/red] {detail}")
        raise typer.Exit(1)


def _resolve_content(text: str, md_file: str | None = None) -> str:
    """Resolve message content from a file, URL, or inline text.

    Priority:
      1. --md-file (local path)
      2. text that looks like a URL ending in .md
      3. text as-is
    """
    if md_file:
        try:
            with open(md_file) as fh:
                return fh.read()
        except OSError as e:
            rprint(f"[red]Cannot read file: {e}[/red]")
            raise typer.Exit(1)

    t = text.strip()
    if t.startswith(("http://", "https://")) and t.rsplit("?", 1)[0].endswith(".md"):
        try:
            r = niquests.get(t, timeout=30)
            r.raise_for_status()
            return r.text
        except niquests.RequestException as e:
            rprint(f"[red]Cannot fetch URL: {e}[/red]")
            raise typer.Exit(1)

    return text


def _json(obj) -> None:
    console.print_json(json.dumps(obj))


def _render_qr_in_terminal(png_bytes: bytes) -> None:
    """Render a PNG QR code in terminal using block characters."""
    try:
        from io import BytesIO
        from PIL import Image
    except Exception as e:
        rprint(f"[red]Unable to render QR in terminal:[/red] {e}")
        raise typer.Exit(1) from e

    img = Image.open(BytesIO(png_bytes)).convert("L")
    scale = 2
    img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    bw = img.point(lambda p: 0 if p < 128 else 255, mode="1")
    pixels = bw.load()

    horizontal_margin = " " * 4
    print()
    for y in range(bw.height):
        row = []
        for x in range(bw.width):
            row.append("██" if pixels[x, y] == 0 else "  ")
        print(f"{horizontal_margin}{''.join(row)}")
    print()


# ── Global --json callback ───────────────────────────────────────────────────

@app.callback()
def global_callback(
    json_out: bool = typer.Option(False, "--json", help="Machine-readable JSON output"),
):
    global _output_json
    _output_json = json_out


# ── recipients ───────────────────────────────────────────────────────────────

recipients_app = typer.Typer(help="Manage recipients", no_args_is_help=True)
app.add_typer(recipients_app, name="recipients")


@recipients_app.command("list")
def recipients_list(
    external_id: Optional[str] = typer.Option(None, "--filter", "-f", help="Filter by exact external_id"),
):
    """List all recipients."""
    data = _get("/recipients", external_id=external_id)
    if _output_json:
        return _json_output(data)
    t = Table("external_id", "phone_sms", "email", "whatsapp_jid", "wa_valid", "id")
    for r in data:
        t.add_row(
            r["external_id"],
            r.get("phone_sms") or "—",
            r.get("email") or "—",
            r.get("whatsapp_jid") or "—",
            "✅" if r.get("whatsapp_valid") else "❌",
            r["id"],
        )
    console.print(t)


@recipients_app.command("get")
def recipients_get(
    recipient_id: str = typer.Argument(help="Recipient UUID"),
):
    """Get a recipient by ID."""
    data = _get(f"/recipients/{recipient_id}")
    _json(data)


@recipients_app.command("create")
def recipients_create(
    external_id: str = typer.Argument(help="Unique external ID"),
    email: Optional[str] = typer.Option(None, "--email", "-e"),
    phone: Optional[str] = typer.Option(None, "--phone", "-p", help="Phone number (normalized for SMS + WhatsApp)"),
):
    """Create or upsert a recipient."""
    body: dict = {"external_id": external_id}
    if email:
        body["email"] = email
    if phone:
        body["phone"] = phone
    data = _post("/recipients", body)
    _json(data)


@recipients_app.command("update")
def recipients_update(
    recipient_id: str = typer.Argument(help="Recipient UUID"),
    email: Optional[str] = typer.Option(None, "--email", "-e"),
    phone: Optional[str] = typer.Option(None, "--phone", "-p"),
):
    """Patch a recipient's contact channels."""
    body: dict = {}
    if email is not None:
        body["email"] = email
    if phone is not None:
        body["phone"] = phone
    if not body:
        rprint("[yellow]Nothing to update — pass --email or --phone[/yellow]")
        raise typer.Exit(1)
    data = _patch(f"/recipients/{recipient_id}", body)
    _json(data)


@recipients_app.command("delete")
def recipients_delete(
    recipient_id: str = typer.Argument(help="Recipient UUID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a recipient."""
    if not yes:
        typer.confirm(f"Delete recipient {recipient_id}?", abort=True)
    _delete(f"/recipients/{recipient_id}")
    rprint(f"[green]Deleted {recipient_id}[/green]")


@recipients_app.command("revalidate")
def recipients_revalidate(
    recipient_id: str = typer.Argument(help="Recipient UUID"),
):
    """Force re-check of WhatsApp registration status."""
    data = _post(f"/recipients/{recipient_id}/revalidate", {})
    _json(data)


@recipients_app.command("check")
def recipients_check(
    query: str = typer.Argument(help="Phone number or email to check"),
):
    """Check if a phone/email is registered and/or valid on WhatsApp."""
    data = _get("/recipients/check", q=query)
    _json(data)


# ── notifications ─────────────────────────────────────────────────────────────

notifications_app = typer.Typer(help="Send notifications and view logs", no_args_is_help=True)
app.add_typer(notifications_app, name="notifications")


@notifications_app.command("send")
def notifications_send(
    external_id: str = typer.Argument(help="Recipient external_id"),
    content: str = typer.Argument(help="Message content (markdown, .md URL, or use --md-file)"),
    tts: bool = typer.Option(False, "--tts", help="Generate voice note for WhatsApp"),
    channel: Optional[list[str]] = typer.Option(None, "--channel", "-c", help="Force specific channel(s): whatsapp | sms | email"),
    media: Optional[list[str]] = typer.Option(None, "--media", "-m", help="Media URL(s) to attach"),
    md_file: Optional[str] = typer.Option(None, "--md-file", help="Path to a local .md file with the message content"),
):
    """Send a notification to a recipient."""
    resolved = _resolve_content(content, md_file)
    body: dict = {
        "external_id": external_id,
        "content": resolved,
        "is_tts": tts,
        "media_urls": media or [],
    }
    if channel:
        body["channels"] = channel
    result = _post("/notifications", body)
    if _output_json:
        return _json_output(result)
    rprint(f"[green]notification_id:[/green] {result['notification_id']}")
    t = Table("channel", "status", "log_id")
    for j in result.get("jobs", []):
        t.add_row(j["channel"], j["status"], j["log_id"])
    console.print(t)
    if result.get("skipped"):
        rprint(f"[yellow]skipped:[/yellow] {result['skipped']}")


@notifications_app.command("broadcast")
def notifications_broadcast(
    content: str = typer.Argument(help="Message content (markdown, .md URL, or use --md-file)"),
    tts: bool = typer.Option(False, "--tts", help="Generate voice note for WhatsApp (once for all)"),
    channel: Optional[list[str]] = typer.Option(None, "--channel", "-c", help="Force specific channel(s): whatsapp | sms | email"),
    media: Optional[list[str]] = typer.Option(None, "--media", "-m", help="Media URL(s) to attach"),
    external_ids: Optional[str] = typer.Option(None, "--ids", help="Comma-separated external_ids"),
    ids_file: Optional[str] = typer.Option(None, "--ids-file", "-f", help="File with one external_id per line"),
    md_file: Optional[str] = typer.Option(None, "--md-file", help="Path to a local .md file with the message content"),
):
    """Send the same notification to multiple recipients (by external_id).

    With --tts, audio is synthesized once and reused for all WhatsApp jobs.
    """
    resolved = _resolve_content(content, md_file)
    id_list = []
    if external_ids:
        id_list = [e.strip() for e in external_ids.split(",") if e.strip()]
    if ids_file:
        try:
            with open(ids_file) as fh:
                for line in fh:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        id_list.append(line)
        except OSError as e:
            rprint(f"[red]Cannot read file: {e}[/red]")
            raise typer.Exit(1)
    if not id_list:
        rprint("[red]Provide --ids or --ids-file[/red]")
        raise typer.Exit(1)

    body: dict = {
        "external_ids": id_list,
        "content": resolved,
        "is_tts": tts,
        "media_urls": media or [],
    }
    if channel:
        body["channels"] = channel
    data = _post("/notifications/broadcast", body)
    if _output_json:
        return _json_output(data)

    ok = 0
    err = 0
    for r in data["results"]:
        if r["error"]:
            rprint(f"[red]✗[/red] {r['external_id']}: {r['error']}")
            err += 1
        else:
            channels_used = [j["channel"] for j in r["jobs"]]
            rprint(f"[green]✓[/green] {r['external_id']} → {', '.join(channels_used)} ({r['notification_id']})")
            ok += 1
    rprint(f"\n[green]{ok} ok[/green]  [red]{err} failed[/red]  out of {len(data['results'])}")


@notifications_app.command("logs")
def notifications_logs(
    external_id: Optional[str] = typer.Option(None, "--recipient", "-r"),
    channel: Optional[str] = typer.Option(None, "--channel", "-c"),
    status: Optional[str] = typer.Option(None, "--status", "-s"),
    since: Optional[str] = typer.Option(None, "--since", help="ISO datetime filter (e.g. 2026-04-29T00:00:00)"),
    limit: int = typer.Option(20, "--limit", "-n"),
    offset: int = typer.Option(0, "--offset", "-o"),
):
    """List notification logs."""
    data = _get("/notifications", external_id=external_id, channel=channel, status=status, since=since, limit=limit, offset=offset)
    if _output_json:
        return _json_output(data)
    t = Table("channel", "status", "is_tts", "attempts", "error", "notification_id", "created_at")
    for n in data:
        t.add_row(
            n["channel"],
            n["status"],
            "\U0001F399" if n.get("is_tts") else "",
            str(n.get("attempts", 0)),
            (n.get("error_msg") or "")[:40],
            n["notification_id"],
            n["created_at"][:19],
        )
    console.print(t)


@notifications_app.command("get")
def notifications_get(
    log_id: str = typer.Argument(help="Notification log UUID"),
):
    """Get a specific notification log entry."""
    data = _get(f"/notifications/{log_id}")
    _json(data)


# ── config ────────────────────────────────────────────────────────────────────

config_app = typer.Typer(help="Manage service configuration", no_args_is_help=True)
app.add_typer(config_app, name="config")


@config_app.command("get")
def config_get():
    """Show current service configuration (passwords omitted)."""
    data = _get("/config")
    _json(data)


@config_app.command("set")
def config_set(
    smtp_host: Optional[str] = typer.Option(None, "--smtp-host"),
    smtp_port: Optional[int] = typer.Option(None, "--smtp-port"),
    smtp_user: Optional[str] = typer.Option(None, "--smtp-user"),
    smtp_pass: Optional[str] = typer.Option(None, "--smtp-pass"),
    smtp_from_email: Optional[str] = typer.Option(None, "--smtp-from-email"),
    smtp_from_name: Optional[str] = typer.Option(None, "--smtp-from-name"),
    smtp_use_tls: Optional[bool] = typer.Option(None, "--smtp-tls/--no-smtp-tls"),
    sms_url: Optional[str] = typer.Option(None, "--sms-url"),
    sms_user: Optional[str] = typer.Option(None, "--sms-user"),
    sms_pass: Optional[str] = typer.Option(None, "--sms-pass"),
    sms_device_id: Optional[str] = typer.Option(None, "--sms-device-id"),
    sms_sim: Optional[int] = typer.Option(None, "--sms-sim"),
    el_api_key: Optional[str] = typer.Option(None, "--el-api-key"),
    el_voice_id: Optional[str] = typer.Option(None, "--el-voice-id"),
    el_model_id: Optional[str] = typer.Option(None, "--el-model-id"),
):
    """Update service configuration (only provided fields are changed)."""
    body: dict = {}
    mapping = {
        "smtp_host": smtp_host, "smtp_port": smtp_port, "smtp_user": smtp_user,
        "smtp_pass": smtp_pass, "smtp_from_email": smtp_from_email,
        "smtp_from_name": smtp_from_name, "smtp_use_tls": smtp_use_tls,
        "sms_gateway_url": sms_url, "sms_gateway_user": sms_user,
        "sms_gateway_pass": sms_pass, "sms_gateway_device_id": sms_device_id,
        "sms_sim_number": sms_sim, "elevenlabs_api_key": el_api_key,
        "elevenlabs_voice_id": el_voice_id, "elevenlabs_model_id": el_model_id,
    }
    for k, v in mapping.items():
        if v is not None:
            body[k] = v
    if not body:
        rprint("[yellow]Nothing to update — pass at least one option[/yellow]")
        raise typer.Exit(1)
    data = _put("/config", body)
    _json(data)


# ── status ────────────────────────────────────────────────────────────────────

@app.command("status")
def system_status():
    """Show overall system status."""
    data = _get("/status")
    if _output_json:
        return _json_output(data)
    wa = data["whatsapp_state"]
    wa_color = "green" if wa == "connected" else "yellow" if wa in ("connecting", "qr_pending") else "red"
    redis_color = "green" if data["redis"] == "ok" else "red"

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_row("API", "[green]ok[/green]")
    t.add_row("Redis", f"[{redis_color}]{data['redis']}[/{redis_color}]")
    t.add_row("WhatsApp", f"[{wa_color}]{wa}[/{wa_color}]" + (f"  ({data['whatsapp_device']})" if data.get("whatsapp_device") else ""))
    t.add_row("SMS Gateway", "[green]configured[/green]" if data["sms_configured"] else "[red]not configured[/red]")
    t.add_row("SMTP", "[green]configured[/green]" if data["smtp_configured"] else "[red]not configured[/red]")
    t.add_row("ElevenLabs", "[green]configured[/green]" if data["elevenlabs_configured"] else "[red]not configured[/red]")
    console.print(t)


# ── whatsapp ──────────────────────────────────────────────────────────────────

whatsapp_app = typer.Typer(help="WhatsApp / Baileys management", no_args_is_help=True)
app.add_typer(whatsapp_app, name="whatsapp")


@whatsapp_app.command("status")
def whatsapp_status():
    """Show WhatsApp connection status."""
    data = _get("/whatsapp/status")
    _json(data)


@whatsapp_app.command("qr")
def whatsapp_qr(
    save: Optional[str] = typer.Option(None, "--save", "-o", help="Save QR PNG to file"),
    terminal: bool = typer.Option(
        True,
        "--terminal/--no-terminal",
        help="Render QR directly in terminal.",
    ),
):
    """Show WhatsApp QR code for pairing."""
    url = _api("/whatsapp/qr")
    r = niquests.get(url, timeout=15)
    if r.status_code == 404:
        rprint("[green]Already connected — no QR available.[/green]")
        return
    if r.status_code == 503:
        rprint("[red]Baileys sidecar unreachable.[/red]")
        raise typer.Exit(1)

    if terminal:
        _render_qr_in_terminal(r.content)
        rprint("[green]QR rendered in terminal.[/green]")

    if save:
        with open(save, "wb") as f:
            f.write(r.content)
        rprint(f"[green]QR saved to {save}[/green] — open with any image viewer to scan.")


@whatsapp_app.command("validate")
def whatsapp_validate(
    phone: str = typer.Argument(help="Phone number to validate on WhatsApp (e.g. 5511999999999)"),
):
    """Check if a phone number is registered on WhatsApp."""
    data = _post("/whatsapp/validate", {"phone": phone})
    _json(data)


@whatsapp_app.command("logout")
def whatsapp_logout(
    yes: bool = typer.Option(False, "--yes", "-y"),
):
    """Disconnect WhatsApp (requires new QR pairing)."""
    if not yes:
        typer.confirm("Disconnect WhatsApp? You will need to scan a new QR.", abort=True)
    _post("/whatsapp/logout", {})
    rprint("[green]Logged out.[/green]")


@whatsapp_app.command("restart")
def whatsapp_restart():
    """Restart the Baileys sidecar."""
    _post("/whatsapp/restart", {})
    rprint("[green]Baileys restarted.[/green]")


@whatsapp_app.command("send-text")
def whatsapp_send_text(
    phone: str = typer.Argument(help="Phone number (e.g. 5511999999999)"),
    text: str = typer.Argument(help="Message text (markdown, .md URL, or use --md-file)"),
    md_file: Optional[str] = typer.Option(None, "--md-file", help="Path to a local .md file with the message content"),
):
    """Send a text message directly to a phone number."""
    from app.services.markdown import md_to_whatsapp
    resolved = _resolve_content(text, md_file)
    wa_text = md_to_whatsapp(resolved)
    data = _post("/whatsapp/send/text", {"phone": phone, "text": wa_text})
    if _output_json:
        return _json_output(data)
    rprint(f"[green]Sent![/green] message_id={data['message_id']} jid={data['jid']}")


@whatsapp_app.command("send-ptt")
def whatsapp_send_ptt(
    phone: str = typer.Argument(help="Phone number (e.g. 5511999999999)"),
    text: Optional[str] = typer.Option(None, "--text", "-t", help="Text to synthesize as voice note (markdown, .md URL)"),
    audio_file: Optional[str] = typer.Option(None, "--audio-file", "-a", help="Path to an OGG/Opus audio file to send as voice note"),
    md_file: Optional[str] = typer.Option(None, "--md-file", help="Path to a local .md file with the text to synthesize"),
):
    """Send a voice note (PTT) to a phone number.

    Provide either --text (TTS synthesis), --md-file, or --audio-file (pre-existing audio).
    """
    audio_b64 = None
    if audio_file:
        import base64
        try:
            with open(audio_file, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode()
        except OSError as e:
            rprint(f"[red]Cannot read audio file: {e}[/red]")
            raise typer.Exit(1)
    resolved_text = None
    if md_file:
        resolved_text = _resolve_content("", md_file)
    elif text:
        resolved_text = _resolve_content(text, None)
    body = {"phone": phone}
    if audio_b64:
        body["audio_base64"] = audio_b64
    if resolved_text:
        body["text"] = resolved_text
    if not audio_b64 and not resolved_text:
        rprint("[red]Provide --text, --md-file, or --audio-file[/red]")
        raise typer.Exit(1)
    data = _post("/whatsapp/send/ptt", body)
    if _output_json:
        return _json_output(data)
    rprint(f"[green]PTT sent![/green] message_id={data['message_id']} jid={data['jid']}")


@whatsapp_app.command("broadcast")
def whatsapp_broadcast(
    content: str = typer.Argument(help="Message content (markdown, .md URL, or use --md-file)"),
    tts: bool = typer.Option(False, "--tts", help="Send as voice note (synthesized once for all)"),
    media: Optional[list[str]] = typer.Option(None, "--media", "-m", help="Media URL(s) to attach"),
    phones: Optional[str] = typer.Option(None, "--phones", "-p", help="Comma-separated phone numbers (e.g. 5511999...,5511888...)"),
    phones_file: Optional[str] = typer.Option(None, "--phones-file", "-f", help="File with one phone per line"),
    md_file: Optional[str] = typer.Option(None, "--md-file", help="Path to a local .md file with the message content"),
):
    """Send the same message to multiple phone numbers.

    Provide phones via --phones (comma-separated) or --phones-file (one per line).
    With --tts, audio is synthesized once and reused for all recipients.
    """
    resolved = _resolve_content(content, md_file)
    phone_list = []
    if phones:
        phone_list = [p.strip() for p in phones.split(",") if p.strip()]
    if phones_file:
        try:
            with open(phones_file) as fh:
                for line in fh:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        phone_list.append(line)
        except OSError as e:
            rprint(f"[red]Cannot read file: {e}[/red]")
            raise typer.Exit(1)
    if not phone_list:
        rprint("[red]Provide --phones or --phones-file[/red]")
        raise typer.Exit(1)

    body = {
        "phones": phone_list,
        "content": resolved,
        "is_tts": tts,
        "media_urls": media or [],
    }
    data = _post("/whatsapp/broadcast", body)
    if _output_json:
        return _json_output(data)

    sent = sum(1 for r in data["results"] if r["status"] == "sent")
    failed = len(data["results"]) - sent
    t = Table("phone", "status", "message_id", "error")
    for r in data["results"]:
        err = (r.get("error") or "")[:40]
        t.add_row(r["phone"], r["status"], r.get("message_id") or "—", err)
    console.print(t)
    rprint(f"[green]{sent} sent[/green]  [red]{failed} failed[/red]  out of {len(data['results'])}")


# ── groups ────────────────────────────────────────────────────────────────────

groups_app = typer.Typer(help="WhatsApp groups", no_args_is_help=True)
app.add_typer(groups_app, name="groups")


@groups_app.command("list")
def groups_list():
    """List all WhatsApp groups."""
    data = _get("/baileys/groups")
    if _output_json:
        return _json_output(data)
    groups = data.get("groups", [])
    t = Table("subject", "size", "jid")
    for g in sorted(groups, key=lambda g: g["size"], reverse=True):
        t.add_row(g["subject"][:55], str(g["size"]), g["jid"])
    console.print(t)
    rprint(f"[dim]{len(groups)} groups[/dim]")


@groups_app.command("get")
def groups_get(
    jid: str = typer.Argument(help="Group JID (e.g. 120363286125215485@g.us)"),
):
    """Get full group details including participants."""
    data = _get(f"/baileys/groups/{jid}")
    if _output_json:
        return _json_output(data)
    rprint(f"[bold]Subject:[/bold] {data['subject']}")
    rprint(f"[bold]Owner:[/bold]   {data.get('owner', 'N/A')}")
    rprint(f"[bold]Size:[/bold]    {data['size']}")
    rprint(f"[bold]Created:[/bold] {data.get('creation', 'N/A')}")
    if data.get("desc"):
        rprint(f"[bold]Desc:[/bold]    {data['desc'][:120]}")
    rprint(f"[bold]Participants ({len(data.get('participants', []))}):[/bold]")
    for p in data.get("participants", [])[:20]:
        admin = "[yellow]admin[/yellow]" if p.get("admin") else ""
        rprint(f"  {p['id']} {admin}")
    if len(data.get("participants", [])) > 20:
        rprint(f"  [dim]... +{len(data['participants']) - 20} more[/dim]")


@groups_app.command("members")
def groups_members(
    jid: str = typer.Argument(help="Group JID"),
):
    """List members of a WhatsApp group."""
    data = _get(f"/baileys/groups/{jid}/members")
    if _output_json:
        return _json_output(data)
    rprint(f"[bold]{data['subject']}[/bold] — {len(data['participants'])} members")
    for p in data["participants"]:
        admin = " [yellow]admin[/yellow]" if p.get("admin") else ""
        rprint(f"  {p['id']}{admin}")


@groups_app.command("contacts")
def groups_contacts(
    jid: str = typer.Argument(help="Group JID"),
):
    """List group members with contact names."""
    data = _get(f"/baileys/groups/{jid}/members/contacts")
    if _output_json:
        return _json_output(data)
    rprint(f"[bold]{data["subject"]}[/bold] — {len(data["participants"])} members")
    for p in data["participants"]:
        name = p.get("name") or "-"
        admin = " [yellow]admin[/yellow]" if p.get("admin") else ""
        rprint(f"  {name:40s} {p["id"]}{admin}")


@groups_app.command("invite")
def groups_invite(
    jid: str = typer.Argument(help="Group JID"),
):
    """Get the invite link for a group."""
    data = _get(f"/baileys/groups/{jid}/invite")
    if _output_json:
        return _json_output(data)
    rprint(f"[bold]Invite link:[/bold] [green]{data['invite_link']}[/green]")


# ── users ─────────────────────────────────────────────────────────────────────

users_app = typer.Typer(help="WhatsApp user profiles", no_args_is_help=True)
app.add_typer(users_app, name="users")


@users_app.command("get")
def users_get(
    jid: str = typer.Argument(help="User JID (e.g. 5511999999999@s.whatsapp.net)"),
):
    """Get WhatsApp user profile (picture, status, contact)."""
    data = _get(f"/baileys/users/{jid}")
    _json(data)


if __name__ == "__main__":
    app()
