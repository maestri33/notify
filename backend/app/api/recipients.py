from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, or_, select

from app.api.schemas import CheckResult, RecipientCreate, RecipientOut, RecipientUpdate
from app.db import get_session
from app.models import Recipient
from app.models._common import utcnow
from app.services.baileys import BaileysClient, BaileysError, get_baileys
from app.services.normalize import normalize_phone_sms, normalize_whatsapp_jid

router = APIRouter(prefix="/recipients", tags=["recipients"])


def _validate_whatsapp(recipient: Recipient, baileys: BaileysClient) -> None:
    """Best-effort: query Baileys onWhatsApp(), update jid + whatsapp_valid.

    Silent on sidecar errors so recipient CRUD never blocks on WA availability.
    """
    if not recipient.whatsapp_jid:
        recipient.whatsapp_valid = False
        return
    number = recipient.whatsapp_jid.split("@")[0]
    try:
        result = baileys.validate(number)
    except BaileysError:
        # Leave as-is; can be revalidated later via an explicit endpoint or retry.
        return
    if result.get("exists"):
        recipient.whatsapp_jid = result.get("jid") or recipient.whatsapp_jid
        recipient.whatsapp_valid = True
    else:
        recipient.whatsapp_valid = False


def _apply_phone(
    recipient: Recipient,
    phone: str | None,
    *,
    patch: bool = False,
) -> None:
    """Normalize a single `phone` field into both phone_sms and whatsapp_jid."""
    if patch and phone is None:
        return
    if phone is None:
        recipient.phone_sms = None
        recipient.whatsapp_jid = None
        recipient.whatsapp_valid = False
        return
    try:
        recipient.phone_sms = normalize_phone_sms(phone)
    except ValueError as e:
        raise HTTPException(422, f"phone: {e}") from e
    try:
        new_jid = normalize_whatsapp_jid(phone)
    except ValueError as e:
        raise HTTPException(422, f"phone (whatsapp): {e}") from e
    if new_jid != recipient.whatsapp_jid:
        recipient.whatsapp_jid = new_jid
        recipient.whatsapp_valid = False  # revalidate via Baileys below


@router.get("/check", response_model=CheckResult)
def check_recipient(
    q: str = Query(..., description="phone number or email to look up"),
    session: Session = Depends(get_session),
    baileys: BaileysClient = Depends(get_baileys),
) -> CheckResult:
    """Check whether a phone/email exists in the system and optionally validate via WhatsApp."""
    q = q.strip()

    # Determine if it looks like a phone number (contains digits, may have +/spaces/dashes/parens)
    is_phone = any(c.isdigit() for c in q) and "@" not in q

    # Try to find in the system
    recipient: Recipient | None = None
    if is_phone:
        try:
            sms_normalized = normalize_phone_sms(q)
        except ValueError:
            sms_normalized = None
        try:
            jid_normalized = normalize_whatsapp_jid(q)
        except ValueError:
            jid_normalized = None

        conditions = []
        if sms_normalized:
            conditions.append(Recipient.phone_sms == sms_normalized)
        if jid_normalized:
            conditions.append(Recipient.whatsapp_jid == jid_normalized)
        if conditions:
            recipient = session.exec(select(Recipient).where(or_(*conditions))).first()
    else:
        # Treat as email
        recipient = session.exec(
            select(Recipient).where(Recipient.email == q)
        ).first()

    # WhatsApp validation for phone numbers
    wa_valid: bool | None = None
    wa_jid: str | None = None
    if is_phone:
        try:
            candidate_jid = normalize_whatsapp_jid(q)
        except ValueError:
            candidate_jid = None
        if candidate_jid:
            number = candidate_jid.split("@")[0]
            try:
                result = baileys.validate(number)
                wa_valid = bool(result.get("exists"))
                wa_jid = result.get("jid") if wa_valid else None
            except BaileysError:
                pass

    if recipient:
        recipient_out = RecipientOut(
            id=recipient.id,
            external_id=recipient.external_id,
            email=recipient.email,
            phone_sms=recipient.phone_sms,
            whatsapp_jid=recipient.whatsapp_jid,
            whatsapp_valid=recipient.whatsapp_valid,
            created_at=recipient.created_at,
            updated_at=recipient.updated_at,
        )
        return CheckResult(
            found=True,
            external_id=recipient.external_id,
            recipient=recipient_out,
            whatsapp_valid=wa_valid,
            whatsapp_jid=wa_jid,
        )

    return CheckResult(
        found=False,
        whatsapp_valid=wa_valid,
        whatsapp_jid=wa_jid,
    )


@router.post("", response_model=RecipientOut, status_code=status.HTTP_201_CREATED)
def upsert_recipient(
    payload: RecipientCreate,
    session: Session = Depends(get_session),
    baileys: BaileysClient = Depends(get_baileys),
) -> Recipient:
    existing = session.exec(
        select(Recipient).where(Recipient.external_id == payload.external_id)
    ).first()

    recipient = existing or Recipient(external_id=payload.external_id)
    prev_jid = recipient.whatsapp_jid

    recipient.email = payload.email
    _apply_phone(recipient, payload.phone)

    if recipient.whatsapp_jid and recipient.whatsapp_jid != prev_jid:
        _validate_whatsapp(recipient, baileys)

    recipient.updated_at = utcnow()
    session.add(recipient)
    session.commit()
    session.refresh(recipient)
    return recipient


@router.get("", response_model=list[RecipientOut])
def list_recipients(
    external_id: str | None = Query(None),
    session: Session = Depends(get_session),
) -> list[Recipient]:
    stmt = select(Recipient)
    if external_id:
        stmt = stmt.where(Recipient.external_id == external_id)
    return list(session.exec(stmt).all())


@router.get("/{recipient_id}", response_model=RecipientOut)
def get_recipient(recipient_id: UUID, session: Session = Depends(get_session)) -> Recipient:
    r = session.get(Recipient, recipient_id)
    if not r:
        raise HTTPException(404, "recipient not found")
    return r


@router.patch("/{recipient_id}", response_model=RecipientOut)
def patch_recipient(
    recipient_id: UUID,
    payload: RecipientUpdate,
    session: Session = Depends(get_session),
    baileys: BaileysClient = Depends(get_baileys),
) -> Recipient:
    r = session.get(Recipient, recipient_id)
    if not r:
        raise HTTPException(404, "recipient not found")
    prev_jid = r.whatsapp_jid

    if payload.email is not None:
        r.email = payload.email

    _apply_phone(r, payload.phone, patch=True)

    if r.whatsapp_jid and r.whatsapp_jid != prev_jid:
        _validate_whatsapp(r, baileys)

    r.updated_at = utcnow()
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


@router.delete("/{recipient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipient(recipient_id: UUID, session: Session = Depends(get_session)) -> None:
    r = session.get(Recipient, recipient_id)
    if not r:
        raise HTTPException(404, "recipient not found")
    session.delete(r)
    session.commit()
