"""Dashboard routes (server-rendered Jinja + HTMX)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, select_autoescape
from sqlmodel import Session, select

from app.db import get_session
from app.models import (
    Channel,
    EmailTemplate,
    NotificationLog,
    NotificationStatus,
    Recipient,
    ServiceConfig,
)
from app.models._common import utcnow
from app.services.baileys import BaileysClient, BaileysError, get_baileys
from app.services.markdown import md_to_html
from app.services.normalize import normalize_phone_sms, normalize_whatsapp_jid

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["dashboard"], default_response_class=HTMLResponse)


def _now() -> str:
    return utcnow().strftime("%H:%M:%S")


def _recipient_labels(
    session: Session, logs: list[NotificationLog]
) -> dict[UUID, str]:
    ids = {n.recipient_id for n in logs}
    if not ids:
        return {}
    rs = session.exec(select(Recipient).where(Recipient.id.in_(ids))).all()
    return {r.id: r.external_id for r in rs}


# ---------- Pages ----------

@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> Response:
    return templates.TemplateResponse(request, "home.html", {})


@router.get("/recipients", response_class=HTMLResponse)
def recipients_page(request: Request) -> Response:
    return templates.TemplateResponse(request, "recipients.html", {})


@router.get("/logs", response_class=HTMLResponse)
def logs_page(request: Request) -> Response:
    return templates.TemplateResponse(request, "logs.html", {})


@router.get("/template", response_class=HTMLResponse)
def template_page(request: Request, session: Session = Depends(get_session)) -> Response:
    tpl = session.get(EmailTemplate, 1)
    preview_html = _render_template_preview(tpl)
    return templates.TemplateResponse(
        request, "template.html", {"tpl": tpl, "preview_html": preview_html}
    )


@router.get("/config", response_class=HTMLResponse)
def config_page(request: Request, session: Session = Depends(get_session)) -> Response:
    cfg = session.get(ServiceConfig, 1)
    return templates.TemplateResponse(request, "config.html", {"cfg": cfg})


@router.get("/baileys", response_class=HTMLResponse)
def baileys_page(request: Request) -> Response:
    return templates.TemplateResponse(request, "baileys.html", {})


# ---------- Partials: recent logs ----------

@router.get("/partials/recent-logs", response_class=HTMLResponse)
def partial_recent_logs(
    request: Request, session: Session = Depends(get_session)
) -> Response:
    logs = list(
        session.exec(
            select(NotificationLog).order_by(NotificationLog.created_at.desc()).limit(100)
        ).all()
    )
    return templates.TemplateResponse(
        request,
        "_log_row.html",
        {"logs": logs, "recipient_labels": _recipient_labels(session, logs)},
    )


# ---------- Partials: recipients ----------

@router.get("/partials/recipients", response_class=HTMLResponse)
def partial_recipients(
    request: Request,
    external_id: str | None = None,
    session: Session = Depends(get_session),
) -> Response:
    stmt = select(Recipient).order_by(Recipient.updated_at.desc())
    if external_id:
        stmt = stmt.where(Recipient.external_id.contains(external_id))
    recipients = list(session.exec(stmt.limit(200)).all())
    return templates.TemplateResponse(
        request, "_recipients_rows.html", {"recipients": recipients}
    )


@router.get("/recipients/empty", response_class=HTMLResponse)
def recipient_empty() -> HTMLResponse:
    return HTMLResponse("")


@router.get("/recipients/{recipient_id}/edit", response_class=HTMLResponse)
def recipient_edit_form(
    request: Request, recipient_id: UUID, session: Session = Depends(get_session)
) -> Response:
    r = session.get(Recipient, recipient_id)
    if not r:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "_recipient_edit.html", {"r": r})


@router.post("/recipients/{recipient_id}/edit", response_class=HTMLResponse)
def recipient_edit_submit(
    request: Request,
    recipient_id: UUID,
    email: str = Form(""),
    phone: str = Form(""),
    session: Session = Depends(get_session),
    baileys: BaileysClient = Depends(get_baileys),
) -> Response:
    r = session.get(Recipient, recipient_id)
    if not r:
        raise HTTPException(404)
    r.email = email.strip() or None
    phone_stripped = phone.strip() or None
    try:
        r.phone_sms = normalize_phone_sms(phone_stripped)
    except ValueError:
        r.phone_sms = None
    try:
        new_jid = normalize_whatsapp_jid(phone_stripped)
    except ValueError:
        new_jid = None
    if new_jid != r.whatsapp_jid:
        r.whatsapp_jid = new_jid
        r.whatsapp_valid = False
        if new_jid:
            try:
                res = baileys.validate(new_jid.split("@")[0])
                if res.get("exists"):
                    r.whatsapp_jid = res.get("jid") or new_jid
                    r.whatsapp_valid = True
            except BaileysError:
                pass
    r.updated_at = utcnow()
    session.add(r)
    session.commit()
    session.refresh(r)
    return templates.TemplateResponse(
        request, "_recipient_edit.html", {"r": r, "saved": True, "now": _now()}
    )


@router.delete("/recipients/{recipient_id}", response_class=HTMLResponse)
def dashboard_delete_recipient(
    request: Request, recipient_id: UUID, session: Session = Depends(get_session)
) -> Response:
    r = session.get(Recipient, recipient_id)
    if r:
        session.delete(r)
        session.commit()
    return partial_recipients(request, session=session)


# ---------- Partials: logs ----------

@router.get("/partials/logs", response_class=HTMLResponse)
def partial_logs(
    request: Request,
    channel: Channel | None = None,
    status: NotificationStatus | None = None,
    external_id: str | None = None,
    session: Session = Depends(get_session),
) -> Response:
    stmt = select(NotificationLog).order_by(NotificationLog.created_at.desc())
    if channel:
        stmt = stmt.where(NotificationLog.channel == channel)
    if status:
        stmt = stmt.where(NotificationLog.status == status)
    if external_id:
        rids = session.exec(
            select(Recipient.id).where(Recipient.external_id.contains(external_id))
        ).all()
        if not rids:
            return templates.TemplateResponse(
                request, "_log_row.html", {"logs": [], "recipient_labels": {}}
            )
        stmt = stmt.where(NotificationLog.recipient_id.in_(rids))
    logs = list(session.exec(stmt.limit(200)).all())
    return templates.TemplateResponse(
        request, "_log_row.html",
        {"logs": logs, "recipient_labels": _recipient_labels(session, logs)},
    )


# ---------- Template editor ----------

def _render_template_preview(tpl: EmailTemplate | None) -> str:
    if not tpl:
        return ""
    env = Environment(autoescape=select_autoescape(["html"]))
    sample_md = "Olá **fulano**, sua consulta foi confirmada para amanhã às 14h."
    content_html = md_to_html(sample_md)
    try:
        subject = env.from_string(tpl.subject).render(
            content_html=content_html, subject="Nova notificação"
        )
        html = env.from_string(tpl.html_body).render(
            content_html=content_html, subject=subject
        )
        return html
    except Exception as e:
        return f"<pre style='color:red;padding:12px'>Erro no template: {e}</pre>"


@router.post("/template", response_class=HTMLResponse)
def save_template(
    request: Request,
    subject: str = Form(...),
    html_body: str = Form(...),
    session: Session = Depends(get_session),
) -> Response:
    tpl = session.get(EmailTemplate, 1)
    tpl.subject = subject
    tpl.html_body = html_body
    tpl.updated_at = utcnow()
    session.add(tpl)
    session.commit()
    session.refresh(tpl)
    return templates.TemplateResponse(
        request, "template.html",
        {
            "tpl": tpl,
            "preview_html": _render_template_preview(tpl),
            "saved": True, "now": _now(),
        },
    )


@router.post("/template/preview", response_class=HTMLResponse)
def preview_template(
    subject: str = Form(...), html_body: str = Form(...)
) -> HTMLResponse:
    tpl = EmailTemplate(id=1, subject=subject, html_body=html_body)
    html = _render_template_preview(tpl).replace('"', "&quot;")
    return HTMLResponse(
        f'<iframe srcdoc="{html}" style="width:100%;height:520px;border:0;"></iframe>'
    )


# ---------- Service config ----------

_CFG_FIELDS = [
    "smtp_host", "smtp_user", "smtp_pass",
    "smtp_from_email", "smtp_from_name",
    "sms_gateway_url", "sms_gateway_user", "sms_gateway_pass",
    "sms_gateway_device_id",
    "elevenlabs_api_key", "elevenlabs_voice_id", "elevenlabs_model_id",
    "imap_host", "imap_user", "imap_pass",
]


@router.post("/config", response_class=HTMLResponse)
async def save_config(
    request: Request, session: Session = Depends(get_session)
) -> Response:
    form = await request.form()
    cfg = session.get(ServiceConfig, 1)
    for f in _CFG_FIELDS:
        v = form.get(f)
        setattr(cfg, f, (v.strip() or None) if isinstance(v, str) else v)
    cfg.smtp_port = int(form.get("smtp_port") or 587)
    cfg.imap_port = int(form.get("imap_port") or 993)
    cfg.smtp_use_tls = bool(form.get("smtp_use_tls"))
    cfg.sms_sim_number = int(form.get("sms_sim_number") or 1)
    cfg.updated_at = utcnow()
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return templates.TemplateResponse(
        request, "config.html", {"cfg": cfg, "saved": True, "now": _now()}
    )


@router.post("/config/test/smtp", response_class=HTMLResponse)
async def test_smtp(request: Request) -> HTMLResponse:
    form = await request.form()
    import aiosmtplib

    try:
        smtp = aiosmtplib.SMTP(
            hostname=form.get("smtp_host"),
            port=int(form.get("smtp_port") or 587),
            start_tls=bool(form.get("smtp_use_tls")) and int(form.get("smtp_port") or 587) != 465,
            use_tls=int(form.get("smtp_port") or 587) == 465,
        )
        await smtp.connect()
        if form.get("smtp_user"):
            await smtp.login(form.get("smtp_user"), form.get("smtp_pass") or "")
        await smtp.quit()
        return HTMLResponse("<small style='color:green'>✅ conexão SMTP ok</small>")
    except Exception as e:
        return HTMLResponse(f"<small style='color:#c00'>❌ {e}</small>")


@router.post("/config/test/sms", response_class=HTMLResponse)
async def test_sms(request: Request) -> HTMLResponse:
    form = await request.form()
    url = (form.get("sms_gateway_url") or "").rstrip("/")
    if not url:
        return HTMLResponse("<small style='color:#c00'>❌ URL vazia</small>")
    auth = None
    if form.get("sms_gateway_user"):
        auth = (form.get("sms_gateway_user"), form.get("sms_gateway_pass") or "")
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(f"{url}/health", auth=auth)
        if r.status_code < 400:
            return HTMLResponse("<small style='color:green'>✅ gateway respondeu</small>")
        return HTMLResponse(f"<small style='color:#c00'>❌ {r.status_code}</small>")
    except Exception as e:
        return HTMLResponse(f"<small style='color:#c00'>❌ {e}</small>")


@router.post("/config/test/elevenlabs", response_class=HTMLResponse)
async def test_elevenlabs(request: Request) -> HTMLResponse:
    form = await request.form()
    key = form.get("elevenlabs_api_key")
    if not key:
        return HTMLResponse("<small style='color:#c00'>❌ api key vazia</small>")
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(
                "https://api.elevenlabs.io/v1/user", headers={"xi-api-key": key}
            )
        if r.status_code < 400:
            return HTMLResponse("<small style='color:green'>✅ api key válida</small>")
        return HTMLResponse(f"<small style='color:#c00'>❌ {r.status_code}</small>")
    except Exception as e:
        return HTMLResponse(f"<small style='color:#c00'>❌ {e}</small>")


# ---------- Baileys ----------

@router.get("/partials/baileys-status", response_class=HTMLResponse)
def partial_baileys_status(
    request: Request, baileys: BaileysClient = Depends(get_baileys)
) -> Response:
    try:
        st = baileys.status()
        ctx: dict[str, Any] = {
            "state": st.get("state", "unknown"),
            "jid": st.get("jid"),
            "device_name": st.get("device_name"),
            "last_seen": st.get("last_seen"),
            "cachebust": int(time.time()),
        }
    except BaileysError as e:
        ctx = {"state": "unreachable", "error": str(e), "cachebust": int(time.time())}
    return templates.TemplateResponse(request, "_baileys_status.html", ctx)


@router.get("/partials/baileys-qr")
def partial_baileys_qr(baileys: BaileysClient = Depends(get_baileys)) -> Response:
    try:
        png = baileys.qr_png()
    except BaileysError:
        return Response(status_code=503)
    if not png:
        return Response(status_code=404)
    return Response(content=png, media_type="image/png")


@router.get("/partials/baileys-logs", response_class=HTMLResponse)
def partial_baileys_logs(baileys: BaileysClient = Depends(get_baileys)) -> HTMLResponse:
    try:
        lines = baileys.logs(limit=50)
    except BaileysError as e:
        return HTMLResponse(f"(sidecar unreachable: {e})")
    from html import escape

    return HTMLResponse("\n".join(escape(line) for line in lines) or "(sem logs ainda)")


@router.post("/partials/baileys-restart", response_class=HTMLResponse)
def partial_baileys_restart(
    request: Request, baileys: BaileysClient = Depends(get_baileys)
) -> Response:
    try:
        baileys.restart()
    except BaileysError:
        pass
    time.sleep(1)
    return partial_baileys_status(request, baileys)


@router.post("/partials/baileys-logout", response_class=HTMLResponse)
def partial_baileys_logout(
    request: Request, baileys: BaileysClient = Depends(get_baileys)
) -> Response:
    try:
        baileys.logout()
    except BaileysError:
        pass
    time.sleep(1)
    return partial_baileys_status(request, baileys)
