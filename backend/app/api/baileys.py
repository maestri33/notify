"""WhatsApp / Baileys endpoints — status, actions, contacts, groups, messages."""

import base64
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from app.api.schemas import (
    GroupDetail,
    GroupInvite,
    GroupList,
    GroupMembers,
    GroupMembersEnriched,
    GroupSummary,
    MemberWithContact,
    UserProfile,
    WhatsAppStatus,
)
from app.baileys_db import (
    batch_get_contacts,
    get_pushnames_for_group,
    count_contacts,
    count_messages,
    get_contact,
    get_message,
    list_contacts,
    list_messages,
    recent_messages,
    search_contacts,
)
from app.services.baileys import BaileysClient, BaileysError, get_baileys
from app.services.content_resolver import resolve_remote_content
from app.services.tts import synthesize_b64, TTSError

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


# ── WhatsApp Status / QR / Validate / Logout / Restart ────────────────────

@router.get("/status", response_model=WhatsAppStatus)
def whatsapp_status(baileys: BaileysClient = Depends(get_baileys)) -> WhatsAppStatus:
    try:
        s = baileys.status()
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")
    return WhatsAppStatus(
        state=s.get("state", "unknown"),
        jid=s.get("jid"),
        device_name=s.get("device_name"),
        last_seen=s.get("last_seen"),
    )


@router.get("/qr")
def whatsapp_qr(
    fmt: str = "png",
    baileys: BaileysClient = Depends(get_baileys),
) -> Response:
    try:
        png = baileys.qr_png()
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")
    if png is None:
        raise HTTPException(404, "QR not available — already connected or not yet generated")
    if fmt == "base64":
        return Response(
            content=json.dumps({"qr": base64.b64encode(png).decode()}),
            media_type="application/json",
        )
    return Response(content=png, media_type="image/png")


class ValidateRequest(BaseModel):
    phone: str


class ValidateResponse(BaseModel):
    exists: bool
    jid: str | None = None


@router.post("/validate", response_model=ValidateResponse)
def whatsapp_validate(
    body: ValidateRequest,
    baileys: BaileysClient = Depends(get_baileys),
):
    try:
        result = baileys.validate(body.phone)
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")
    return ValidateResponse(exists=result.get("exists", False), jid=result.get("jid"))


@router.post("/logout")
def whatsapp_logout(baileys: BaileysClient = Depends(get_baileys)) -> dict:
    try:
        baileys.logout()
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")
    return {"ok": True}


@router.post("/restart")
def whatsapp_restart(baileys: BaileysClient = Depends(get_baileys)) -> dict:
    try:
        baileys.restart()
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")
    return {"ok": True}


# ── Send / Broadcast ──────────────────────────────────────────────────────

class SendTextRequest(BaseModel):
    phone: str
    text: str


class SendPhoneResponse(BaseModel):
    message_id: str
    jid: str


@router.post("/send/text", response_model=SendPhoneResponse)
def whatsapp_send_text(
    body: SendTextRequest,
    baileys: BaileysClient = Depends(get_baileys),
):
    resolved_text = resolve_remote_content(body.text)
    try:
        result = baileys.send_text_phone(body.phone, resolved_text)
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")
    if "error" in result:
        raise HTTPException(404, result["error"])
    return SendPhoneResponse(message_id=result["message_id"], jid=result["jid"])


class SendPttRequest(BaseModel):
    phone: str
    audio_base64: str | None = None
    text: str | None = None


@router.post("/send/ptt", response_model=SendPhoneResponse)
def whatsapp_send_ptt(
    body: SendPttRequest,
    baileys: BaileysClient = Depends(get_baileys),
):
    audio_b64 = body.audio_base64
    if not audio_b64 and body.text:
        resolved_text = resolve_remote_content(body.text)
        try:
            audio_b64 = synthesize_b64(resolved_text, strict=True)
        except ValueError as e:
            raise HTTPException(422, str(e))
        except TTSError as e:
            raise HTTPException(503, f"TTS failed: {e}")
    if not audio_b64:
        raise HTTPException(422, "audio_base64 or text required")

    try:
        result = baileys.send_ptt_phone(body.phone, audio_b64)
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")
    if "error" in result:
        raise HTTPException(404, result["error"])
    return SendPhoneResponse(message_id=result["message_id"], jid=result["jid"])


class BroadcastRequest(BaseModel):
    phones: list[str]
    content: str
    is_tts: bool = False
    media_urls: list[str] = []


class BroadcastResultItem(BaseModel):
    phone: str
    jid: str | None = None
    status: str
    message_id: str | None = None
    error: str | None = None


class BroadcastResponse(BaseModel):
    results: list[BroadcastResultItem]


@router.post("/broadcast", response_model=BroadcastResponse)
def whatsapp_broadcast(
    body: BroadcastRequest,
    baileys: BaileysClient = Depends(get_baileys),
):
    from app.services.markdown import md_to_whatsapp

    results: list[BroadcastResultItem] = []
    resolved_content = resolve_remote_content(body.content)

    audio_b64 = None
    if body.is_tts:
        try:
            audio_b64 = synthesize_b64(resolved_content, strict=True)
        except ValueError as e:
            raise HTTPException(422, str(e))
        except TTSError as e:
            raise HTTPException(503, f"TTS failed: {e}")

    try:
        if body.is_tts and audio_b64:
            result = baileys.broadcast_ptt(body.phones, audio_b64)
        else:
            wa_text = md_to_whatsapp(resolved_content)
            result = baileys.broadcast_text(body.phones, wa_text)
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")

    for r in result.get("results", []):
        results.append(BroadcastResultItem(**r))

    if body.media_urls:
        for r in results:
            if r.status == "sent" and r.jid:
                for url in body.media_urls:
                    try:
                        from app.services.senders import _head_mimetype
                        mime = _head_mimetype(url)
                        baileys.send_media(r.jid, url=url, mimetype=mime)
                    except BaileysError:
                        pass

    return BroadcastResponse(results=results)


# ── Contacts (read from shared SQLite) ────────────────────────────────────

@router.get("/contacts")
def api_list_contacts(
    q: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    if q:
        return {"contacts": search_contacts(q, limit, offset)}
    return {"contacts": list_contacts(limit, offset), "total": count_contacts()}


@router.get("/contacts/{jid}")
def api_get_contact(jid: str):
    c = get_contact(jid)
    if not c:
        return {"error": "not found"}, 404
    return c


# ── Messages (read from shared SQLite) ────────────────────────────────────

@router.get("/messages")
def api_list_messages(
    jid: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    if jid:
        return {"messages": list_messages(jid, limit, offset)}
    return {"messages": recent_messages(limit), "total": count_messages()}


@router.get("/messages/{msg_id}")
def api_get_message(msg_id: str):
    m = get_message(msg_id)
    if not m:
        return {"error": "not found"}, 404
    return m


@router.get("/stats")
def api_stats():
    return {
        "contacts": count_contacts(),
        "messages": count_messages(),
    }


# ── Groups (proxied to sidecar) ───────────────────────────────────────────

@router.get("/groups", response_model=GroupList)
def api_list_groups(baileys: BaileysClient = Depends(get_baileys)):
    try:
        groups = baileys.list_groups()
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")
    return GroupList(groups=[GroupSummary(**g) for g in groups])


@router.get("/groups/{jid}", response_model=GroupDetail)
def api_get_group(jid: str, baileys: BaileysClient = Depends(get_baileys)):
    try:
        return baileys.get_group(jid)
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")


@router.get("/groups/{jid}/members", response_model=GroupMembers)
def api_get_group_members(jid: str, baileys: BaileysClient = Depends(get_baileys)):
    try:
        return baileys.get_group_members(jid)
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")


@router.get("/groups/{jid}/invite", response_model=GroupInvite)
def api_get_group_invite(jid: str, baileys: BaileysClient = Depends(get_baileys)):
    try:
        return baileys.get_group_invite(jid)
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")


@router.get("/groups/{jid}/members/contacts", response_model=GroupMembersEnriched)
def api_get_group_members_contacts(
    jid: str, baileys: BaileysClient = Depends(get_baileys)
):
    try:
        members = baileys.get_group_members(jid)
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")

    lids = [p["id"] for p in members["participants"]]
    contacts = batch_get_contacts(lids)
    pushnames = get_pushnames_for_group(jid)

    enriched = []
    for p in members["participants"]:
        c = contacts.get(p["id"])
        name = (c.notify or c.name) if c else None
        if not name:
            name = pushnames.get(p["id"])
        enriched.append(MemberWithContact(
            id=p["id"],
            admin=p.get("admin"),
            name=name,
            contact_jid=None,
        ))

    return GroupMembersEnriched(
        jid=members["jid"],
        subject=members["subject"],
        participants=enriched,
    )


# ── User Profile (proxied to sidecar) ─────────────────────────────────────

@router.get("/users/{jid}", response_model=UserProfile)
def api_get_user(jid: str, baileys: BaileysClient = Depends(get_baileys)):
    try:
        return baileys.get_user(jid)
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")
