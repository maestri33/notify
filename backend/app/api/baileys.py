"""API endpoints — Baileys WhatsApp sidecar (groups, users, contacts, messages)."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.schemas import (
    GroupMembersEnriched,
    MemberWithContact,
    GroupDetail,
    GroupInvite,
    GroupList,
    GroupMembers,
    GroupSummary,
    UserProfile,
)
from app.baileys_db import (
    batch_get_contacts,
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

router = APIRouter(prefix="/baileys", tags=["baileys"])


# ── Contacts (read from shared SQLite) ──────────────────────────────────

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


# ── Messages (read from shared SQLite) ──────────────────────────────────

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


# ── Groups (proxied to sidecar) ─────────────────────────────────────────

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


# ── User Profile (proxied to sidecar) ───────────────────────────────────

@router.get("/users/{jid}", response_model=UserProfile)
def api_get_user(jid: str, baileys: BaileysClient = Depends(get_baileys)):
    try:
        return baileys.get_user(jid)
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")

# ── Enriched Members (members + contact names from DB) ─────────────────

@router.get("/groups/{jid}/members/contacts", response_model=GroupMembersEnriched)
def api_get_group_members_contacts(
    jid: str, baileys: BaileysClient = Depends(get_baileys)
):
    """Get group members with contact names from the shared SQLite DB."""
    try:
        members = baileys.get_group_members(jid)
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")

    lids = [p["id"] for p in members["participants"]]
    contacts = batch_get_contacts(lids)

    enriched = []
    for p in members["participants"]:
        c = contacts.get(p["id"])
        enriched.append(MemberWithContact(
            id=p["id"],
            admin=p.get("admin"),
            name=c.notify or c.name if c else None,
            contact_jid=None,
        ))

    return GroupMembersEnriched(
        jid=members["jid"],
        subject=members["subject"],
        participants=enriched,
    )
