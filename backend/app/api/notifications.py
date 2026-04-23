import uuid
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.api.schemas import (
    NotificationCreate,
    NotificationCreateResponse,
    NotificationJob,
    NotificationLogOut,
)
from app.db import get_session
from app.models import Channel, NotificationLog, NotificationStatus, Recipient
from app.services.router import eligible_channels
from app.workers.jobs import DISPATCHERS, on_final_failure
from app.workers.queue import DEFAULT_RETRY, get_queue

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("", response_model=NotificationCreateResponse, status_code=status.HTTP_201_CREATED)
def create_notification(
    payload: NotificationCreate,
    session: Session = Depends(get_session),
) -> NotificationCreateResponse:
    recipient = session.exec(
        select(Recipient).where(Recipient.external_id == payload.external_id)
    ).first()
    if not recipient:
        raise HTTPException(404, "recipient not found for external_id")

    channels = eligible_channels(recipient, forced=payload.channels)
    if not channels:
        raise HTTPException(
            422,
            "no eligible channels: recipient has no validated whatsapp/phone/email "
            "or channel filter excluded all of them",
        )

    skipped = []
    if payload.channels:
        skipped = [c for c in payload.channels if c not in channels]

    notification_id = uuid.uuid4()
    jobs: list[NotificationJob] = []

    # Create all logs up-front (atomically) before enqueueing.
    # is_tts only applies to WhatsApp (audio PTT).
    # When is_tts=True, SMS and Email still get dispatched with the plain text.
    logs: list[NotificationLog] = []
    for ch in channels:
        logs.append(
            NotificationLog(
                notification_id=notification_id,
                recipient_id=recipient.id,
                channel=ch,
                status=NotificationStatus.queued,
                is_tts=payload.is_tts and ch == Channel.whatsapp,
            )
        )
    session.add_all(logs)
    session.commit()
    for n in logs:
        session.refresh(n)

    for notif in logs:
        dispatcher = DISPATCHERS[notif.channel]
        queue = get_queue(notif.channel)
        queue.enqueue(
            dispatcher,
            notif.id,
            payload.content,
            payload.media_urls,
            retry=DEFAULT_RETRY,
            on_failure=on_final_failure,
            job_timeout=300,
        )
        jobs.append(
            NotificationJob(channel=notif.channel, log_id=notif.id, status=notif.status)
        )

    return NotificationCreateResponse(
        notification_id=notification_id,
        recipient_id=recipient.id,
        jobs=jobs,
        skipped=skipped,
    )


@router.get("", response_model=list[NotificationLogOut])
def list_logs(
    external_id: str | None = Query(None),
    channel: Channel | None = Query(None),
    status_: NotificationStatus | None = Query(None, alias="status"),
    since: datetime | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> list[NotificationLog]:
    stmt = select(NotificationLog).order_by(NotificationLog.created_at.desc())
    if external_id:
        recipient = session.exec(
            select(Recipient).where(Recipient.external_id == external_id)
        ).first()
        if not recipient:
            return []
        stmt = stmt.where(NotificationLog.recipient_id == recipient.id)
    if channel:
        stmt = stmt.where(NotificationLog.channel == channel)
    if status_:
        stmt = stmt.where(NotificationLog.status == status_)
    if since:
        stmt = stmt.where(NotificationLog.created_at >= since)
    stmt = stmt.limit(limit).offset(offset)
    return list(session.exec(stmt).all())


@router.get("/{log_id}", response_model=NotificationLogOut)
def get_log(log_id: UUID, session: Session = Depends(get_session)) -> NotificationLog:
    n = session.get(NotificationLog, log_id)
    if not n:
        raise HTTPException(404, "log not found")
    return n
