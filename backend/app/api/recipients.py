from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, or_, select

from app.api.schemas import CheckOut, RecipientCreate, RecipientOut, RecipientUpdate
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


# ── Standalone /check (mounted at /api/v1/check) ─────────────────────────

check_router = APIRouter(tags=["check"])


def _is_email_like(val: str) -> bool:
    """Heuristic: contains @ and no digit-dominant pattern (phone)."""
    return "@" in val and not any(c.isdigit() for c in val)


def _validate_email_format(val: str) -> bool:
    """Basic email format check without heavy libraries."""
    import re
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", val))


@check_router.get("/check", response_model=CheckOut, response_model_exclude_none=True)
def check(
    phone: str | None = Query(None, description="Phone number (any format)"),
    email: str | None = Query(None, description="Email address"),
    session: Session = Depends(get_session),
    baileys: BaileysClient = Depends(get_baileys),
) -> CheckOut:
    """Look up a phone or email in the recipient database.

    If found, returns the registered info.
    If not found, validates the input externally (WhatsApp for phones, format for email).
    """
    q = (phone or "").strip() or (email or "").strip()
    if not q:
        raise HTTPException(422, "phone or email is required")

    # ── Phone path ──────────────────────────────────────────────────────
    if phone and phone.strip():
        raw = phone.strip()

        # Normalize to SMS and WhatsApp formats
        try:
            sms_normalized = normalize_phone_sms(raw)
        except ValueError:
            sms_normalized = None
        try:
            jid_normalized = normalize_whatsapp_jid(raw)
        except ValueError:
            jid_normalized = None

        # Search recipients by normalized phone
        recipient: Recipient | None = None
        conditions = []
        if sms_normalized:
            conditions.append(Recipient.phone_sms == sms_normalized)
        if jid_normalized:
            conditions.append(Recipient.whatsapp_jid == jid_normalized)
        if conditions:
            recipient = session.exec(select(Recipient).where(or_(*conditions))).first()

        if recipient:
            return CheckOut(
                found=True,
                external_id=recipient.external_id,
                phone=recipient.phone_sms,
                email=recipient.email,
            )

        # Not found — check WhatsApp existence externally
        wa_exists: bool | None = None
        if jid_normalized:
            number = jid_normalized.split("@")[0]
            try:
                result = baileys.validate(number)
                wa_exists = bool(result.get("exists"))
            except BaileysError:
                pass

        return CheckOut(found=False, whatsapp=wa_exists)

    # ── Email path ──────────────────────────────────────────────────────
    if email and email.strip():
        raw = email.strip().lower()

        valid_format = _validate_email_format(raw)

        recipient = session.exec(
            select(Recipient).where(Recipient.email == raw)
        ).first()

        if recipient:
            return CheckOut(
                found=True,
                external_id=recipient.external_id,
                phone=recipient.phone_sms,
                email=recipient.email,
            )

        return CheckOut(found=False, email=valid_format)

    raise HTTPException(422, "phone or email is required")


@router.post("", response_model=RecipientOut, status_code=status.HTTP_201_CREATED)
def create_recipient(
    payload: RecipientCreate,
    session: Session = Depends(get_session),
    baileys: BaileysClient = Depends(get_baileys),
) -> Recipient:
    # Must provide at least one contact method
    if not payload.email and not payload.phone:
        raise HTTPException(422, "email or phone is required")

    # external_id must not already exist
    existing = session.exec(
        select(Recipient).where(Recipient.external_id == payload.external_id)
    ).first()
    if existing:
        raise HTTPException(409, f"recipient already exists for external_id: {payload.external_id}")

    recipient = Recipient(external_id=payload.external_id)

    # ── Email validation ──────────────────────────────────────────────
    if payload.email:
        if not _validate_email_format(payload.email):
            raise HTTPException(422, f"invalid email: {payload.email}")
        dup = session.exec(
            select(Recipient).where(Recipient.email == payload.email.lower())
        ).first()
        if dup:
            raise HTTPException(409, f"email already in use: {payload.email}")
        recipient.email = payload.email.lower()

    # ── Phone validation ──────────────────────────────────────────────
    if payload.phone:
        try:
            jid = normalize_whatsapp_jid(payload.phone)
        except ValueError as e:
            raise HTTPException(422, f"invalid phone: {e}") from e

        # Check WhatsApp existence
        number = jid.split("@")[0]
        try:
            result = baileys.validate(number)
        except BaileysError as e:
            raise HTTPException(502, f"whatsapp unavailable: {e}") from e
        if not result.get("exists"):
            raise HTTPException(422, f"whatsapp not registered for this number")

        recipient.whatsapp_jid = result.get("jid") or jid
        recipient.whatsapp_valid = True

        # Normalize SMS phone
        try:
            recipient.phone_sms = normalize_phone_sms(payload.phone)
        except ValueError:
            pass  # SMS format too strict? skip

    recipient.updated_at = utcnow()
    session.add(recipient)
    session.flush()
    session.commit()
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


@router.post("/{recipient_id}/revalidate", response_model=RecipientOut)
def revalidate_recipient(
    recipient_id: UUID,
    session: Session = Depends(get_session),
    baileys: BaileysClient = Depends(get_baileys),
) -> Recipient:
    """Force re-check of WhatsApp registration status via Baileys."""
    r = session.get(Recipient, recipient_id)
    if not r:
        raise HTTPException(404, "recipient not found")
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
