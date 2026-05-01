"""Channel-specific send functions.

Each sender receives (recipient, notification_log, content, media_urls) and
returns the provider_msg_id on success. Raises on failure (RQ will retry).
"""

from __future__ import annotations

import base64
import logging
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import niquests
from aiosmtplib import SMTP
from jinja2 import Environment, select_autoescape

from app.models import Channel, NotificationLog, Recipient
from app.services import media as media_mod
from app.services.baileys import BaileysClient, BaileysError
from app.services.config_store import load_email_template, load_service_config
from app.services.markdown import md_to_html, md_to_plain, md_to_whatsapp
from app.services.tts import synthesize
from app.workers.jobs import ChannelNotReady

log = logging.getLogger(__name__)

_jinja = Environment(autoescape=select_autoescape(["html", "xml"]), enable_async=False)


# ---------- WhatsApp ----------

def send_whatsapp(
    recipient: Recipient, notif: NotificationLog, content: str, media_urls: list[str], audio_base64: str | None = None
) -> str:
    if not recipient.whatsapp_jid or not recipient.whatsapp_valid:
        raise ChannelNotReady("whatsapp not available for recipient")

    baileys = BaileysClient()
    jid = recipient.whatsapp_jid

    try:
        if notif.is_tts:
            # TTS mode: send voice note (no text caption). Media still attached separately.
            if audio_base64:
                audio_b64 = audio_base64
            else:
                cfg = load_service_config()
                plain = md_to_plain(content)
                if not plain:
                    raise ChannelNotReady("content empty — nothing to synthesize")
                audio_bytes = synthesize(plain, cfg)
                audio_b64 = base64.b64encode(audio_bytes).decode()
            msg_id = baileys.send_ptt(jid, audio_b64)
        else:
            wa_text = md_to_whatsapp(content)
            if media_urls:
                # First media carries the caption; remaining media are follow-ups.
                first_url = media_urls[0]
                mime = _head_mimetype(first_url)
                msg_id = baileys.send_media(
                    jid, url=first_url, mimetype=mime, caption=wa_text
                )
            else:
                msg_id = baileys.send_text(jid, wa_text)

        # Extra media (always, regardless of TTS)
        extra = media_urls if notif.is_tts else media_urls[1:]
        for u in extra:
            mime = _head_mimetype(u)
            baileys.send_media(jid, url=u, mimetype=mime)

        return msg_id
    except BaileysError as e:
        raise RuntimeError(f"baileys error: {e}") from e


def _head_mimetype(url: str) -> str:
    """Cheap HEAD request to guess mimetype; falls back to extension."""
    try:
        r = niquests.head(url, timeout=10.0, follow_redirects=True)
        ct = r.headers.get("content-type")
        if ct:
            return ct.split(";")[0].strip()
    except niquests.RequestException:
        pass
    import mimetypes

    guess, _ = mimetypes.guess_type(url)
    return guess or "application/octet-stream"


# ---------- SMS ----------

def send_sms(
    recipient: Recipient, notif: NotificationLog, content: str, media_urls: list[str]
) -> str:
    if not recipient.phone_sms:
        raise ChannelNotReady("phone_sms missing on recipient")

    cfg = load_service_config()
    if not cfg.sms_gateway_url:
        raise ChannelNotReady("SMS Gateway not configured")

    text = md_to_plain(content)
    payload: dict = {"phoneNumbers": [recipient.phone_sms], "message": text}
    if cfg.sms_gateway_device_id:
        payload["deviceId"] = cfg.sms_gateway_device_id
    payload["simNumber"] = cfg.sms_sim_number or 1

    auth = None
    if cfg.sms_gateway_user and cfg.sms_gateway_pass:
        auth = (cfg.sms_gateway_user, cfg.sms_gateway_pass)

    url = f"{cfg.sms_gateway_url.rstrip('/')}/message"
    r = niquests.post(url, json=payload, auth=auth, timeout=30.0)
    if r.status_code >= 400:
        raise RuntimeError(f"sms-gateway {r.status_code}: {r.text[:300]}")
    data = r.json()
    return data.get("id") or data.get("messageId") or "unknown"


# ---------- Email ----------

def send_email(
    recipient: Recipient, notif: NotificationLog, content: str, media_urls: list[str]
) -> str:
    if not recipient.email:
        raise ChannelNotReady("email missing on recipient")

    cfg = load_service_config()
    if not (cfg.smtp_host and cfg.smtp_from_email):
        raise ChannelNotReady("SMTP not configured")

    tpl = load_email_template()
    content_html = md_to_html(content)
    first_line = md_to_plain(content).splitlines()[0] if content else "Notificação"

    # Download media once, split into inline images vs. regular attachments
    medias, failed_urls = media_mod.download_all(media_urls) if media_urls else ([], [])
    inline = [m for m in medias if m.mimetype.startswith("image/")]
    attachments = [m for m in medias if not m.mimetype.startswith("image/")]

    # Assign CIDs to inline images and inject <img> tags at end of body
    if inline:
        gallery = []
        for m in inline:
            m.cid = make_msgid(domain="notify.local").strip("<>")
            gallery.append(
                f'<img src="cid:{m.cid}" alt="" '
                f'style="max-width:100%;margin-top:12px;border-radius:6px;"/>'
            )
        content_html = content_html + "\n<div>" + "\n".join(gallery) + "</div>\n"

    # URLs that couldn't be downloaded: include as clickable links in body
    if failed_urls:
        links = "\n".join(
            f'<p><a href="{u}" style="color:#4f8ef7;">{u}</a></p>' for u in failed_urls
        )
        content_html = content_html + f"\n<div>{links}</div>\n"

    subject = _jinja.from_string(tpl.subject).render(
        content_html=content_html, subject=first_line
    )
    html = _jinja.from_string(tpl.html_body).render(
        content_html=content_html, subject=subject
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((cfg.smtp_from_name or "", cfg.smtp_from_email))
    msg["To"] = recipient.email
    msg_id = make_msgid(domain=cfg.smtp_from_email.split("@", 1)[-1])
    msg["Message-ID"] = msg_id

    msg.set_content(md_to_plain(content) or "")
    msg.add_alternative(html, subtype="html")

    # Attach inline images as related to the HTML part
    html_part = msg.get_payload()[-1]
    for m in inline:
        _, _, sub = m.mimetype.partition("/")
        html_part.add_related(
            m.data, maintype="image", subtype=sub or "png",
            cid=f"<{m.cid}>", filename=m.filename,
        )

    # Regular attachments on the root
    for m in attachments:
        main, _, sub = m.mimetype.partition("/")
        msg.add_attachment(
            m.data, maintype=main or "application",
            subtype=sub or "octet-stream", filename=m.filename,
        )

    import asyncio

    async def _send() -> None:
        async with SMTP(
            hostname=cfg.smtp_host,
            port=cfg.smtp_port,
            start_tls=cfg.smtp_use_tls and cfg.smtp_port != 465,
            use_tls=cfg.smtp_port == 465,
            username=cfg.smtp_user or None,
            password=cfg.smtp_pass or None,
        ) as smtp:
            await smtp.send_message(msg)

    asyncio.run(_send())
    return msg_id.strip("<>")


SENDERS = {
    Channel.whatsapp: send_whatsapp,
    Channel.sms: send_sms,
    Channel.email: send_email,
}
