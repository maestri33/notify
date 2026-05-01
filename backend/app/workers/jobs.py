"""Channel dispatcher jobs.

Each `dispatch_<channel>` is the RQ-invoked entry point. It:
  1. Loads the NotificationLog + Recipient in a fresh DB session
  2. Marks status=sending, increments attempts
  3. Calls the channel-specific sender (stubbed in Phase 5)
  4. On success: status=sent + provider_msg_id
  5. On failure: re-raises so RQ retries; on final failure, hook marks failed
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlmodel import Session, select

from app.db import engine
from app.models import Channel, NotificationLog, NotificationStatus, Recipient
from app.models._common import utcnow

log = logging.getLogger(__name__)


class ChannelNotReady(RuntimeError):
    """Raise when recipient is missing data for this channel (permanent failure — do not retry)."""


def _load(session: Session, log_id: UUID) -> tuple[NotificationLog, Recipient]:
    notif = session.get(NotificationLog, log_id)
    if not notif:
        raise ChannelNotReady(f"log {log_id} not found")
    recipient = session.get(Recipient, notif.recipient_id)
    if not recipient:
        raise ChannelNotReady(f"recipient {notif.recipient_id} not found")
    return notif, recipient


def _run(channel: Channel, log_id: UUID, content: str, media_urls: list[str] | None, audio_base64: str | None = None) -> None:
    with Session(engine) as session:
        notif, recipient = _load(session, log_id)
        notif.status = NotificationStatus.sending
        notif.attempts += 1
        notif.updated_at = utcnow()
        session.add(notif)
        session.commit()

        try:
            from app.services import senders  # lazy import to avoid import cycles

            send_fn = senders.SENDERS[channel]
            provider_msg_id = send_fn(recipient, notif, content, media_urls or [], audio_base64=audio_base64)
        except ChannelNotReady as e:
            notif.status = NotificationStatus.failed
            notif.error_msg = str(e)
            notif.updated_at = utcnow()
            session.add(notif)
            session.commit()
            log.warning("channel %s not ready: %s", channel, e)
            return  # do not retry
        except Exception as e:
            notif.error_msg = f"{type(e).__name__}: {e}"
            notif.updated_at = utcnow()
            session.add(notif)
            session.commit()
            log.exception("send failed for %s", channel.value)
            raise  # let RQ retry

        notif.status = NotificationStatus.sent
        notif.provider_msg_id = provider_msg_id
        notif.error_msg = None
        notif.updated_at = utcnow()
        session.add(notif)
        session.commit()


def dispatch_whatsapp(log_id: UUID, content: str, media_urls: list[str] | None = None, audio_base64: str | None = None) -> None:
    _run(Channel.whatsapp, log_id, content, media_urls, audio_base64=audio_base64)


def dispatch_sms(log_id: UUID, content: str, media_urls: list[str] | None = None) -> None:
    _run(Channel.sms, log_id, content, media_urls)


def dispatch_email(log_id: UUID, content: str, media_urls: list[str] | None = None) -> None:
    _run(Channel.email, log_id, content, media_urls)


DISPATCHERS = {
    Channel.whatsapp: dispatch_whatsapp,
    Channel.sms: dispatch_sms,
    Channel.email: dispatch_email,
}


def on_final_failure(job, connection, type, value, traceback):
    """RQ failure callback — called when all retries are exhausted."""
    log_id_arg = job.args[0] if job.args else None
    if not log_id_arg:
        return
    with Session(engine) as session:
        notif = session.get(NotificationLog, log_id_arg)
        if notif and notif.status != NotificationStatus.sent:
            notif.status = NotificationStatus.failed
            notif.error_msg = f"max retries: {value}"[:500]
            notif.updated_at = utcnow()
            session.add(notif)
            session.commit()
